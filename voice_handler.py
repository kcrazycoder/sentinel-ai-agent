import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Constants
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam" - Standard American / Deep Voice
MODEL_ID = "eleven_turbo_v2" # Low latency model

def generate_voice(text: str, voice_id: str = DEFAULT_VOICE_ID) -> Optional[bytes]:
    """
    Generates audio from text using ElevenLabs API.
    Returns raw audio bytes (MP3) or None if failed.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("ELEVENLABS_API_KEY not set. Voice generation disabled.")
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
            logger.info(f"Generated voice audio ({len(response.content)} bytes).")
            return response.content
        elif response.status_code in [401, 403]:
            logger.warning(f"ElevenLabs Auth Failed ({response.status_code}). Enabling Text-Only Fallback.")
            return None
        else:
            logger.error(f"ElevenLabs API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Voice generation exception: {e}")
        return None
