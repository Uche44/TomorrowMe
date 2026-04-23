import os
from pydantic_settings import BaseSettings, SettingsConfigDict


def _tmp(filename: str) -> str:
    """Use /tmp on Render (ephemeral), local path in dev."""
    if os.environ.get("RENDER"):
        return f"/tmp/{filename}"
    return filename


class Settings(BaseSettings):
    # LLM — HuggingFace Inference API (OpenAI-compatible router)
    hf_api_key: str = ""
    hf_model_id: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_timeout_sec: int = 60
    upstream_timeout_sec: int = 10

    # CORS — comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # Upstream URLs (self-referential — all modules on same server)
    persona_api_base_url: str = "http://localhost:8000"
    scenario_api_base_url: str = "http://localhost:8000"
    dialogue_api_base_url: str = "http://localhost:8000"
    voice_api_base_url: str = "http://localhost:8000"

    # Databases — default to /tmp on Render
    database_url: str = _tmp("dialogue.db")
    audio_db_url: str = _tmp("audio.db")
    voice_db_url: str = _tmp("voice.db")
    persona_db_url: str = _tmp("persona.db")
    scenario_db_url: str = _tmp("scenario.db")

    # File storage — default to /tmp on Render
    audio_files_dir: str = _tmp("audio_files")
    assets_dir: str = "assets"

    # ElevenLabs
    elevenlabs_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
