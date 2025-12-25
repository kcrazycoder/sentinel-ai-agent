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
MODEL_ID = "eleven_turbo_v2" # Low latency model

def _generate_elevenlabs(text: str, voice_id: str = DEFAULT_VOICE_ID) -> Optional[bytes]:
    """
    Generates audio using ElevenLabs API.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        # Only log error if this was explicitly the chosen provider or default fallback failure
        logger.error("ELEVENLABS_API_KEY not set.")
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
    # Prefer GOOGLE_API_KEY, fallback to inference from environment if SDK handles it, 
    # but explicit key is safer for simple scripts.
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.error("GOOGLE_API_KEY not set.")
        return None
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Using gemini-2.5-flash for native audio generation
        # We request audio/mp3 as the response logic if supported.
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"Please generate audio for the following text: {text}",
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
        logger.error(f"Gemini generation exception: {e}")
        return None

def generate_voice(text: str, voice_id: str = DEFAULT_VOICE_ID) -> Optional[bytes]:
    """
    Generates audio from text using the configured provider.
    ENV 'VOICE_PROVIDER': "elevenlabs" (default), "gemini", "none"
    """
    provider = os.getenv("VOICE_PROVIDER", "elevenlabs").lower().strip()
    
    if provider == "none":
        logger.info("Voice generation disabled (VOICE_PROVIDER=none).")
        return None
        
    if provider == "gemini":
        return _generate_gemini(text)
    else:
        # Default to ElevenLabs
        return _generate_elevenlabs(text, voice_id)
