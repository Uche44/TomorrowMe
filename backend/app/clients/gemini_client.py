import asyncio
import logging

import google.generativeai as genai

from app.config import settings
from app.exceptions import LLMProviderError, LLMTimeoutError

logger = logging.getLogger(__name__)

# Token budget by length variant — raised for gemini-2.5-flash
_MAX_TOKENS = {"short": 1024, "long": 2048}


class GeminiClient:
    def __init__(self, length: str = "short") -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=genai.GenerationConfig(
                temperature=0.85,
                max_output_tokens=_MAX_TOKENS.get(length, 512),
            ),
        )
        self._timeout = settings.llm_timeout_sec

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        combined = f"{system_prompt}\n\n{user_prompt}"
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._model.generate_content, combined),
                timeout=self._timeout,
            )
            return response.text
        except asyncio.TimeoutError as exc:
            logger.error("GeminiClient timeout after %ds", self._timeout)
            raise LLMTimeoutError(f"Gemini timed out after {self._timeout}s") from exc
        except Exception as exc:
            logger.error("GeminiClient error: %s", exc)
            raise LLMProviderError(f"Gemini error: {exc}") from exc
