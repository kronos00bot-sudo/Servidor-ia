"""Configuration model for the WhatsApp OpenClaw skill."""

import os
from pathlib import Path
from dotenv import load_dotenv

from .exceptions import ConfigError


def _load_env() -> None:
    # Prefer explicit env file for OpenClaw runtime, fallback to cwd .env.
    project_dir = Path(os.getenv("PROJECT_DIR", "")).expanduser()
    if project_dir:
        env_path = project_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return
    load_dotenv()


_load_env()


class Config:
    """Runtime configuration loaded from environment variables."""

    PROJECT_DIR = Path(
        os.getenv("PROJECT_DIR", "/home/mloco/Escritorio/Servidor-ia/whatsapp-agent")
    ).expanduser()

    DGX_WHISPER_URL = os.getenv("DGX_WHISPER_URL", "http://100.64.129.87:8765/inference")
    DGX_OLLAMA_URL = os.getenv("DGX_OLLAMA_URL", "http://100.64.129.87:11434")
    LOCAL_OLLAMA_URL = os.getenv("LOCAL_OLLAMA_URL", "http://127.0.0.1:11434")

    VISION_MODEL = os.getenv("VISION_MODEL", "gemma4-es")
    DGX_VISION_MODEL = os.getenv("DGX_VISION_MODEL", "gemma4:26b")
    FAST_MODEL = os.getenv("FAST_MODEL", "qwen35-es")
    REASONING_MODEL = os.getenv("REASONING_MODEL", "qwen36-es")
    AGENT_LOCAL_MODEL = os.getenv("AGENT_LOCAL_MODEL", "nemotron3:33b")
    DGX_LLM_MODEL = os.getenv("DGX_LLM_MODEL", "nemotron-3-super:120b")
    FALLBACK_DGX_MODEL = os.getenv("FALLBACK_DGX_MODEL", "gpt-oss:120b")

    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_WEBHOOK_PORT = int(os.getenv("WHATSAPP_WEBHOOK_PORT", "8000"))

    TARGET_LANG = os.getenv("TARGET_LANG", "es")
    AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    VIDEO_FRAME_INTERVAL = int(os.getenv("VIDEO_FRAME_INTERVAL", "30"))
    FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

    TIMEOUTS = {
        "whisper": int(os.getenv("TIMEOUT_WHISPER", "300")),
        "vision": int(os.getenv("TIMEOUT_VISION", "180")),
        "vision_fallback": int(os.getenv("TIMEOUT_VISION_FALLBACK", "240")),
        "chat": int(os.getenv("TIMEOUT_CHAT", "120")),
        "reasoning": int(os.getenv("TIMEOUT_REASONING", "180")),
        "translation": int(os.getenv("TIMEOUT_TRANSLATION", "600")),
        "document": int(os.getenv("TIMEOUT_DOCUMENT", "180")),
    }

    MACHINE_TYPE = os.getenv("MACHINE_TYPE", "um890").lower()

    @classmethod
    def validate(cls) -> None:
        """Validate mandatory runtime values."""
        if not cls.PROJECT_DIR:
            raise ConfigError("PROJECT_DIR no puede estar vacio")
        if cls.MACHINE_TYPE not in {"um890", "dgx"}:
            raise ConfigError("MACHINE_TYPE debe ser 'um890' o 'dgx'")
        if not cls.DGX_OLLAMA_URL.startswith("http"):
            raise ConfigError("DGX_OLLAMA_URL invalida")
        if not cls.LOCAL_OLLAMA_URL.startswith("http"):
            raise ConfigError("LOCAL_OLLAMA_URL invalida")
        if cls.WHATSAPP_WEBHOOK_PORT <= 0:
            raise ConfigError("WHATSAPP_WEBHOOK_PORT invalido")
