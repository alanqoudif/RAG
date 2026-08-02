"""Thin async client for a local Ollama server. Model name is always read from configuration
(`OLLAMA_MODEL` / `OLLAMA_FALLBACK_MODEL`) — never hardcoded — per the assignment's requirement
that the platform not be tied to one specific local model.
"""

import httpx

from app.config import Settings
from app.exceptions import AppError
from app.logging_config import get_logger

logger = get_logger(__name__)


class LLMUnavailableError(AppError):
    status_code = 503
    code = "LLM_UNAVAILABLE"

    def __init__(self, message: str = "The local language model is not available."):
        super().__init__(message)


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(self, prompt: str, *, system: str | None = None, temperature: float = 0.0) -> str:
        models_to_try = [self.settings.ollama_model, self.settings.ollama_fallback_model]
        last_error: Exception | None = None

        async with httpx.AsyncClient(
            base_url=self.settings.ollama_base_url,
            timeout=self.settings.ollama_request_timeout_seconds,
        ) as client:
            for model in models_to_try:
                if not model:
                    continue
                try:
                    payload = {
                        "model": model,
                        "prompt": prompt,
                        "system": system,
                        "stream": False,
                        "options": {"temperature": temperature},
                    }
                    response = await client.post("/api/generate", json=payload)
                    response.raise_for_status()
                    body = response.json()
                    return body.get("response", "")
                except Exception as exc:  # noqa: BLE001 -- try the fallback model on any failure
                    logger.warning("ollama_generate_failed", model=model, error_type=type(exc).__name__)
                    last_error = exc
                    continue

        raise LLMUnavailableError(
            f"Could not reach the local Ollama server or model ({type(last_error).__name__ if last_error else 'unknown error'})."
        )
