"""
HuggingFace Inference API client using the OpenAI-compatible router endpoint.
Base URL: https://router.huggingface.co/v1
Model: mistralai/Mistral-7B-Instruct-v0.3
"""
import asyncio
import logging

import httpx

from app.config import settings
from app.exceptions import LLMProviderError, LLMTimeoutError

logger = logging.getLogger(__name__)

HF_ROUTER_BASE = "https://router.huggingface.co/v1"
HF_CHAT_URL = f"{HF_ROUTER_BASE}/chat/completions"
DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"


class HFClient:
    """
    Calls the HuggingFace Inference Router using the OpenAI-compatible
    chat completions API. Works with any instruction-tuned model on HF Hub.
    """

    def __init__(self, max_tokens: int = 1024, temperature: float = 0.7) -> None:
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = settings.llm_timeout_sec
        # Allow overriding model via config; fall back to Mistral
        self._model = getattr(settings, "hf_model_id", DEFAULT_MODEL)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a chat completion request and return the assistant reply text.
        system_prompt can be empty — user_prompt carries the full instruction.
        """
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

        headers = {
            "Authorization": f"Bearer {settings.hf_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await asyncio.wait_for(
                    client.post(HF_CHAT_URL, json=payload, headers=headers),
                    timeout=self._timeout,
                )

            if response.status_code == 503:
                raise LLMProviderError(
                    "HuggingFace model is loading — please retry in ~20 seconds"
                )

            if response.status_code == 401:
                raise LLMProviderError(
                    "HuggingFace API key is invalid or missing the 'Inference Providers' permission"
                )

            if response.status_code != 200:
                raise LLMProviderError(
                    f"HuggingFace API error {response.status_code}: {response.text[:300]}"
                )

            data = response.json()

            # OpenAI-compatible response shape
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")

            raise LLMProviderError(
                f"Unexpected HF response shape: {str(data)[:200]}"
            )

        except asyncio.TimeoutError as exc:
            logger.error("HFClient timeout after %ds", self._timeout)
            raise LLMTimeoutError(
                f"HuggingFace request timed out after {self._timeout}s"
            ) from exc
        except (LLMProviderError, LLMTimeoutError):
            raise
        except Exception as exc:
            logger.error("HFClient unexpected error: %s", exc)
            raise LLMProviderError(f"HuggingFace client error: {exc}") from exc
