from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LiveKit ───────────────────────────────────────────
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # ── LLM ──────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── STT ──────────────────────────────────────────────
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-2"

    # ── TTS ──────────────────────────────────────────────
    cartesia_api_key: str = ""
    cartesia_model: str = "sonic-2"

    # ── App behaviour ─────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"
    max_session_minutes: int = 20
    max_tool_steps: int = 5
    llm_timeout_seconds: float = 8.0
    enable_call_recording: bool = False
    logfire_token: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()