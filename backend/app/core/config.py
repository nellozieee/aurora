"""Centralized application configuration.

All configuration is loaded from environment variables (see .env.example).
Every field has a safe default so the application can start even when
optional providers are not configured; callers must treat empty/blank
provider settings as "not configured" rather than assuming a value.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repo root is three levels up from `backend/`.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- APPLICATION -----
    app_name: str = Field(default="Aurora", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_secret_key: str = Field(default="", alias="APP_SECRET_KEY")
    app_timezone: str = Field(default="", alias="APP_TIMEZONE")
    app_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="APP_CORS_ORIGINS"
    )

    # ----- DATABASE -----
    database_url: str = Field(
        default="postgresql+asyncpg://aurora:aurora@localhost:5432/aurora",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # ----- REDIS -----
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ----- AI -----
    ai_default_provider: str = Field(default="ollama", alias="AI_DEFAULT_PROVIDER")
    ai_fallback_provider: str = Field(default="", alias="AI_FALLBACK_PROVIDER")

    # ----- OPENAI -----
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # ----- OPENROUTER -----
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    openrouter_model: str = Field(default="", alias="OPENROUTER_MODEL")

    # ----- ANTHROPIC -----
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")

    # ----- OLLAMA -----
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")

    # ----- VOICE -----
    # Safe default: microphone/voice features are off until the user opts in,
    # even though the underlying local STT/TTS providers need no credentials.
    voice_enabled: bool = Field(default=False, alias="VOICE_ENABLED")
    voice_mode: str = Field(default="disabled", alias="VOICE_MODE")  # disabled|push_to_talk|wake_word
    wake_word: str = Field(default="Hey Aurora", alias="WAKE_WORD")
    voice_models_dir: str = Field(default="./models", alias="VOICE_MODELS_DIR")

    # ----- STT -----
    stt_provider: str = Field(default="local", alias="STT_PROVIDER")  # local|openai
    stt_model: str = Field(default="tiny.en", alias="STT_MODEL")

    # ----- TTS -----
    tts_provider: str = Field(default="local", alias="TTS_PROVIDER")  # local|openai
    tts_voice: str = Field(default="", alias="TTS_VOICE")
    tts_speed: float = Field(default=1.0, alias="TTS_SPEED")

    # ----- VISION -----
    # Screen capture always runs locally; only the *analysis* of the image
    # goes to an AI provider, so this picks which provider/model does that.
    vision_provider: str = Field(default="ollama", alias="VISION_PROVIDER")
    vision_model: str = Field(default="moondream", alias="VISION_MODEL")

    # ----- TELEGRAM -----
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # ----- WEB -----
    web_search_provider: str = Field(default="", alias="WEB_SEARCH_PROVIDER")
    web_request_timeout_seconds: int = Field(default=15, alias="WEB_REQUEST_TIMEOUT_SECONDS")
    web_max_response_bytes: int = Field(default=2_000_000, alias="WEB_MAX_RESPONSE_BYTES")

    # ----- SECURITY -----
    # Off by default: this is the single riskiest capability in the system
    # (arbitrary mouse/keyboard control of the user's real desktop), so it
    # needs an explicit opt-in on top of each individual action's own
    # confirm=true requirement.
    security_computer_control_enabled: bool = Field(default=False, alias="SECURITY_COMPUTER_CONTROL_ENABLED")
    security_allowed_filesystem_paths: str = Field(default="", alias="SECURITY_ALLOWED_FILESYSTEM_PATHS")
    security_confirmation_timeout_seconds: int = Field(default=120, alias="SECURITY_CONFIRMATION_TIMEOUT_SECONDS")
    security_sandbox_timeout_seconds: int = Field(default=30, alias="SECURITY_SANDBOX_TIMEOUT_SECONDS")
    security_max_file_read_bytes: int = Field(default=500_000, alias="SECURITY_MAX_FILE_READ_BYTES")
    security_max_file_write_bytes: int = Field(default=5_000_000, alias="SECURITY_MAX_FILE_WRITE_BYTES")
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests_per_minute: int = Field(default=120, alias="RATE_LIMIT_REQUESTS_PER_MINUTE")

    # ----- MEMORY -----
    memory_privacy_mode: bool = Field(default=False, alias="MEMORY_PRIVACY_MODE")
    memory_embedding_provider: str = Field(default="", alias="MEMORY_EMBEDDING_PROVIDER")
    memory_embedding_model: str = Field(default="", alias="MEMORY_EMBEDDING_MODEL")
    memory_embedding_dimensions: int = Field(default=384, alias="MEMORY_EMBEDDING_DIMENSIONS")
    memory_retrieval_top_k: int = Field(default=5, alias="MEMORY_RETRIEVAL_TOP_K")
    memory_retrieval_max_distance: float = Field(default=0.6, alias="MEMORY_RETRIEVAL_MAX_DISTANCE")

    # ----- AUTOMATION -----
    automation_max_concurrent_tasks: int = Field(default=5, alias="AUTOMATION_MAX_CONCURRENT_TASKS")

    # ----- LOGGING -----
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def allowed_filesystem_paths(self) -> list[str]:
        raw = self.security_allowed_filesystem_paths
        if not raw.strip():
            return []
        paths = [p.strip() for p in raw.split(",") if p.strip()]
        # A relative path (e.g. "./sandbox/workspace") is resolved against the
        # repo root, not the process's CWD, so it works the same whether
        # uvicorn is launched from backend/ or from the repo root.
        return [
            str(_REPO_ROOT / p) if not Path(p).expanduser().is_absolute() else p for p in paths
        ]

    @property
    def voice_models_path(self) -> Path:
        raw = Path(self.voice_models_dir).expanduser()
        return raw if raw.is_absolute() else _REPO_ROOT / raw


@lru_cache
def get_settings() -> Settings:
    return Settings()
