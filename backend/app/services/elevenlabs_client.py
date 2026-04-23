import logging
from typing import Iterator

from elevenlabs import ElevenLabs, VoiceSettings
from elevenlabs.core import ApiError

from app.config import settings

logger = logging.getLogger(__name__)

# ElevenLabs voice settings per emotion type (Req 4.4, 4.5)
EMOTION_VOICE_SETTINGS: dict[str, dict] = {
    "success": {"stability": 0.35, "similarity_boost": 0.75},
    "regret":  {"stability": 0.55, "similarity_boost": 0.75},
    "neutral": {"stability": 0.50, "similarity_boost": 0.75},
}


class ElevenLabsError(Exception):
    pass


class ElevenLabsTimeoutError(ElevenLabsError):
    pass


class ElevenLabsClient:
    """Wraps the ElevenLabs Python SDK. ElevenLabs is the ONLY permitted TTS provider."""

    def __init__(self) -> None:
        self._client = ElevenLabs(api_key=settings.elevenlabs_api_key)

    def synthesize(self, text: str, voice_id: str, emotion_type: str) -> bytes:
        """
        Synthesize speech from text using the cloned voice.
        Returns raw audio bytes (mp3 stream).
        Raises ElevenLabsError on API failure, ElevenLabsTimeoutError on timeout.
        """
        vs = EMOTION_VOICE_SETTINGS.get(emotion_type, EMOTION_VOICE_SETTINGS["neutral"])
        voice_settings = VoiceSettings(
            stability=vs["stability"],
            similarity_boost=vs["similarity_boost"],
        )

        try:
            audio_stream: Iterator[bytes] = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=voice_settings,
            )
            return b"".join(audio_stream)
        except ApiError as exc:
            logger.error("ElevenLabsClient API error: status=%s body=%s", exc.status_code, exc.body)
            raise ElevenLabsError(f"ElevenLabs API error: {exc.status_code}") from exc
        except Exception as exc:
            logger.error("ElevenLabsClient unexpected error: %s", exc)
            raise ElevenLabsError(f"ElevenLabs error: {exc}") from exc
