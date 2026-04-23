from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM — HuggingFace Inference API (OpenAI-compatible router)
    hf_api_key: str = ""
    hf_model_id: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_timeout_sec: int = 60
    upstream_timeout_sec: int = 10

    # Dialogue Generator upstream URLs (self-referential — all on same server)
    persona_api_base_url: str = "http://localhost:8000"
    scenario_api_base_url: str = "http://localhost:8000"

    # Databases
    database_url: str = "dialogue.db"
    audio_db_url: str = "audio.db"
    voice_db_url: str = "voice.db"
    persona_db_url: str = "persona.db"
    scenario_db_url: str = "scenario.db"

    # Audio Production Engine
    elevenlabs_api_key: str = ""
    dialogue_api_base_url: str = "http://localhost:8000"
    voice_api_base_url: str = "http://localhost:8000"
    audio_files_dir: str = "audio_files"
    assets_dir: str = "assets"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
