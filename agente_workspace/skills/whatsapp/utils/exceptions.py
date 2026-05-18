"""Custom exceptions for the WhatsApp OpenClaw skill."""


class WhatsAppSkillError(Exception):
    """Base exception for the skill."""


class ConfigError(WhatsAppSkillError):
    """Raised when required configuration is missing or invalid."""


class NetworkError(WhatsAppSkillError):
    """Raised when HTTP/network interactions fail."""


class RetryableError(NetworkError):
    """Raised for transient errors that can be retried."""


class FatalError(WhatsAppSkillError):
    """Raised for non-recoverable errors."""


class TranscriberError(WhatsAppSkillError):
    """Raised for STT/transcription failures."""


class LLMError(WhatsAppSkillError):
    """Raised for generation/LLM failures."""


class WebhookError(WhatsAppSkillError):
    """Raised for webhook validation or processing failures."""
