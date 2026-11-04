from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_KEYS = {"", "sk-placeholder", "sk-ant-...", "..."}


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./bmcc_catalog.db"
    GEMINI_API_KEY: str = "sk-placeholder"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ANTHROPIC_API_KEY: str = "sk-placeholder"
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    APP_ENV: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def has_anthropic_key(self) -> bool:
        return self.ANTHROPIC_API_KEY not in _PLACEHOLDER_KEYS

    @property
    def has_gemini_key(self) -> bool:
        return self.GEMINI_API_KEY not in _PLACEHOLDER_KEYS


settings = Settings()
