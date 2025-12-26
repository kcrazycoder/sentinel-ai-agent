import os
import requests
import logging
from typing import Optional

# Google GenAI SDK
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Constants
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
# "Adam" - Standard American / Deep Voice
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB" 
FEMALE_VOICE_ID = "21m00Tcm4TlvDq8ikWAM" # "Rachel"
MODEL_ID = "eleven_turbo_v2" # Low latency model


def _generate_elevenlabs(text: str, voice_id: str = DEFAULT_VOICE_ID) -> Optional[bytes]:
    """
    Generates audio using ElevenLabs API.
    Returns None if generation fails or key is missing.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        logger.warning("ElevenLabs skipped: API Key missing.")
        return None

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    data = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            logger.info(f"Generated voice audio via ElevenLabs ({len(response.content)} bytes).")
            return response.content
        elif response.status_code == 401:
             logger.error("Audio generation failed: ElevenLabs authentication failed (401).")
             return None
        else:
            logger.error(f"ElevenLabs API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"ElevenLabs generation exception: {e}")
        return None

def _generate_gemini(text: str) -> Optional[bytes]:
    """
    Generates audio using Gemini Native Audio (via google-genai SDK).
    """
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.warning("Gemini Audio skipped: API Key missing.")
        return None
    
    try:
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"Please generate audio for the following text using a professional female voice: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"]
            )
        )
        
        # Check if response has audio data
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("audio"):
                     raw_audio = part.inline_data.data
                     logger.info(f"Generated voice audio via Gemini ({len(raw_audio)} bytes). Wrapping in WAV.")
                     
                     # Wrap in WAV container (24kHz, Mono, 16-bit)
                     import io
                     import wave
                     
                     wav_buffer = io.BytesIO()
                     with wave.open(wav_buffer, "wb") as wav_file:
                         wav_file.setnchannels(1) # Mono
                         wav_file.setsampwidth(2) # 16-bit
                         wav_file.setframerate(24000) # Standard for Gemini
                         wav_file.writeframes(raw_audio)
                         
                     return wav_buffer.getvalue()
        
        logger.warning("Gemini did not return audio data.")
        return None

    except Exception as e:
        # Check for auth errors in exception message as SDK might raise generic errors
        if "401" in str(e) or "Unauthenticated" in str(e):
             logger.error("Audio generation failed: Gemini authentication failed.")
        else:
             logger.error(f"Gemini generation exception: {e}")
        return None

def generate_voice(text: str, voice_id: str = DEFAULT_VOICE_ID, preferred_provider: str = None) -> Optional[bytes]:
    """
    Generates audio from text using the configured provider with fallback.
    Priority: Preferred -> ElevenLabs -> Gemini -> None
    """
    # 1. Determine Preference
    if not preferred_provider:
        # Fallback to generic env if not specified
        preferred_provider = os.getenv("VOICE_PROVIDER", "elevenlabs").lower().strip()
    
    preferred_provider = preferred_provider.lower().strip()
    
    if preferred_provider == "none":
        logger.info("Voice generation disabled (Provider=none).")
        return None
        
    logger.info(f"Attempting audio generation. Preference: {preferred_provider}")

    # 2. Try Preferred
    audio = None
    if preferred_provider == "elevenlabs":
        audio = _generate_elevenlabs(text, voice_id)
    elif preferred_provider == "gemini":
        audio = _generate_gemini(text)
    
    if audio:
        return audio
        
    # 3. Fallback logic
    # If preferred failed (and wasn't just skipped), try the other one.
    
    if preferred_provider == "elevenlabs":
        logger.info("ElevenLabs failed or missing. Falling back to Gemini.")
        audio = _generate_gemini(text)
    elif preferred_provider == "gemini":
        logger.info("Gemini failed or missing. Falling back to ElevenLabs.")
        audio = _generate_elevenlabs(text, voice_id)
    else: 
        # If random string provided, try defaults in order
        logger.warning(f"Unknown provider '{preferred_provider}'. Trying defaults.")
        audio = _generate_elevenlabs(text, voice_id)
        if not audio:
             audio = _generate_gemini(text)

    if audio:
        return audio

    # 4. Give up
    logger.warning("All voice providers failed. Proceeding without audio.")
    return None
