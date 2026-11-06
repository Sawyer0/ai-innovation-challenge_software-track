from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_KEYS = {"", "sk-placeholder", "sk-ant-...", "gsk_...", "..."}


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./bmcc_catalog.db"
    GEMINI_API_KEY: str = "sk-placeholder"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ANTHROPIC_API_KEY: str = "sk-placeholder"
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    # Groq: free-tier, OpenAI-compatible fallback (https://console.groq.com/docs/models)
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_VISION_MODEL: str = "qwen/qwen3.8-27b"
    APP_ENV: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    # Per-client-IP limits on the endpoints that call an LLM (advisement, transcript).
    AI_RATE_LIMIT_PER_MINUTE: int = 5
    AI_RATE_LIMIT_PER_HOUR: int = 30
    # Cap on LLM-backed requests across all visitors per 24 hours, to bound spend on the
    # provider key. In-memory like the per-IP limits, so it is per serverless instance.
    AI_DAILY_LIMIT: int = 500
    # Read the client IP from X-Real-IP / X-Forwarded-For. Only enable behind a proxy
    # that sets these headers itself (Vercel does); otherwise clients can spoof them.
    TRUST_PROXY_HEADERS: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def has_anthropic_key(self) -> bool:
        return self.ANTHROPIC_API_KEY not in _PLACEHOLDER_KEYS

    @property
    def has_gemini_key(self) -> bool:
        return self.GEMINI_API_KEY not in _PLACEHOLDER_KEYS

    @property
    def has_groq_key(self) -> bool:
        return self.GROQ_API_KEY not in _PLACEHOLDER_KEYS

    @property
    def has_any_ai_key(self) -> bool:
        return self.has_anthropic_key or self.has_gemini_key or self.has_groq_key


settings = Settings()
