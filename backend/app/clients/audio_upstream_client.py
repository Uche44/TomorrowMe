import asyncio
import logging

import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

_UPSTREAM_TIMEOUT = 10
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


# Upstream response models
class DialogueScript(BaseModel):
    script_id: str
    text: str
    estimated_duration_sec: float
    emotional_markers: list[str]


class VoiceProfile(BaseModel):
    voice_id: str
    provider: str = "elevenlabs"
    sample_duration_sec: float = 0.0
    created_at: str = ""


# Exceptions
class AudioUpstreamError(Exception):
    pass


class DialogueScriptNotFoundError(AudioUpstreamError):
    pass


class VoiceProfileNotFoundError(AudioUpstreamError):
    pass


class UpstreamServiceError(AudioUpstreamError):
    pass


class UpstreamTimeoutError(AudioUpstreamError):
    pass


class AudioUpstreamClient:
    def __init__(self) -> None:
        self._timeout = _UPSTREAM_TIMEOUT

    async def get_dialogue_script(self, script_id: str) -> DialogueScript:
        url = f"{settings.dialogue_api_base_url}/dialogue/{script_id}"
        return await self._get_with_retry(url, script_id, "DialogueGenerator_API", "script")

    async def get_voice_profile(self, voice_id: str) -> VoiceProfile:
        url = f"{settings.voice_api_base_url}/voice/{voice_id}"
        return await self._get_with_retry(url, voice_id, "VoiceCapture_API", "voice")

    async def _get_with_retry(
        self, url: str, resource_id: str, service: str, resource_type: str
    ):
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url)
            except httpx.TimeoutException as exc:
                logger.error(
                    "UpstreamTimeout: service=%s url=%s attempt=%d/%d",
                    service, url, attempt + 1, _MAX_RETRIES + 1,
                )
                raise UpstreamTimeoutError(f"Timeout fetching {resource_type} {resource_id}") from exc

            if response.status_code == 404:
                logger.error("%s 404: %s_id=%s url=%s", service, resource_type, resource_id, url)
                if resource_type == "script":
                    raise DialogueScriptNotFoundError(f"DialogueScript '{resource_id}' not found")
                raise VoiceProfileNotFoundError(f"VoiceProfile '{resource_id}' not found")

            if response.status_code >= 500:
                logger.warning(
                    "UpstreamRetry: service=%s status=%d attempt=%d/%d reason=HTTP_%d",
                    service, response.status_code, attempt + 1, _MAX_RETRIES + 1, response.status_code,
                )
                last_exc = UpstreamServiceError(
                    f"{service} returned {response.status_code} for {resource_type} {resource_id}"
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAY)
                    continue
                raise last_exc

            response.raise_for_status()
            data = response.json()
            if resource_type == "script":
                return DialogueScript.model_validate(data)
            return VoiceProfile.model_validate(data)

        raise last_exc  # type: ignore[misc]
