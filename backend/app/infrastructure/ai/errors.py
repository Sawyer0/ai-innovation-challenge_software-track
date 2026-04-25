"""
AI-specific exceptions.
"""


class AIError(Exception):
    """Base exception for AI-related errors."""

    def __init__(self, message: str = "AI service error", original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class AIResponseError(AIError):
    """Exception for invalid AI responses."""

    def __init__(self, message: str = "Invalid AI response", response_text: str = None, original_error: Exception = None):
        super().__init__(message, original_error)
        self.response_text = response_text


class AITimeoutError(AIError):
    """Exception for AI request timeouts."""

    def __init__(self, message: str = "AI request timed out", timeout_seconds: float = None):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
