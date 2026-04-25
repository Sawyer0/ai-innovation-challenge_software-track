"""
Centralized AI client for Gemini API.

Provides a singleton pattern for AI client initialization
to ensure consistent configuration across the application.
"""

from functools import lru_cache
from typing import Optional

from ...config import settings

# Import genai module - this allows proper mocking in tests
# even if the package is not actually installed
try:
    from google import genai
except ImportError:
    # Create a mock module for testing purposes
    # The Client class exists but will raise an error when actually used
    # This allows tests to patch it properly
    class _MockModels:
        def generate_content(self, **kwargs):
            raise RuntimeError(
                "Google genai package not installed. "
                "Install with: pip install google-generativeai"
            )

    class _MockClient:
        """Mock client that raises error when used."""
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.models = _MockModels()

    class _MockGenai:
        Client = _MockClient

    genai = _MockGenai()


class AIClient:
    """Singleton wrapper for Gemini AI client."""

    _instance: Optional["AIClient"] = None
    _client: Optional = None

    def __new__(cls) -> "AIClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize the Gemini client."""
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @property
    def client(self):
        """Get the underlying Gemini client."""
        if self._client is None:
            self._initialize()
        return self._client

    @property
    def model(self) -> str:
        """Get the configured model name."""
        return settings.GEMINI_MODEL

    def generate_content(
        self,
        contents: list,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate content using the AI model.

        Args:
            contents: List of content pieces (strings, dicts with mime_type/data)
            model: Optional model override (defaults to settings.GEMINI_MODEL)
            **kwargs: Additional parameters for generate_content

        Returns:
            Generated text response
        """
        model_name = model or self.model
        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            **kwargs
        )
        return response.text


@lru_cache()
def get_ai_client() -> AIClient:
    """
    Get the singleton AI client instance.

    Uses lru_cache to ensure only one instance is created
    across the application lifecycle.
    """
    return AIClient()
