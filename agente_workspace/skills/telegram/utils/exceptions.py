"""Custom exceptions for the Telegram OpenClaw skill."""


class TelegramSkillError(Exception):
    """Base exception for the Telegram skill."""


class ConfigError(TelegramSkillError):
    """Raised when required configuration is missing or invalid."""


class NetworkError(TelegramSkillError):
    """Raised when HTTP/network interactions fail."""


class RetryableError(NetworkError):
    """Raised for transient errors that can be retried."""


class FatalError(TelegramSkillError):
    """Raised for non-recoverable errors."""


class TranscriberError(TelegramSkillError):
    """Raised for STT/transcription failures."""


class LLMError(TelegramSkillError):
    """Raised for generation/LLM failures."""


class WebhookError(TelegramSkillError):
    """Raised for webhook validation or processing failures."""
