"""Configuration for the Telegram OpenClaw adapter."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

from .exceptions import ConfigError


def _load_env() -> None:
    project_dir = Path(os.getenv("PROJECT_DIR", "")).expanduser()
    if project_dir:
        env_path = project_dir / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return
    load_dotenv()


_load_env()


def _load_openclaw_config() -> dict:
    """Load OpenClaw JSON configuration from common runtime locations."""
    candidates = []
    explicit_path = os.getenv("OPENCLAW_CONFIG_PATH", "").strip()
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    openclaw_home = Path.home() / ".openclaw"
    candidates.extend(
        [
            openclaw_home / "openclaw.json",
            openclaw_home / "openclaw.json.novo",
            openclaw_home / "openclaw.json.template",
        ]
    )

    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
            with candidate.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return {}


def _nested_value(data: dict, *keys, default=""):
    """Return nested dict value or default if path does not exist."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if current is None:
        return default
    return current


def _owner_allow_from(config: dict) -> str:
    """Extract first owner id from OpenClaw commands.ownerAllowFrom."""
    allow_from = _nested_value(config, "commands", "ownerAllowFrom", default=[])
    if not isinstance(allow_from, list) or not allow_from:
        return ""

    owner = str(allow_from[0])
    if ":" in owner:
        return owner.split(":", 1)[1]
    return owner


class TelegramConfig:
    """Runtime settings for the Telegram channel adapter."""

    PROJECT_DIR = Path(os.getenv("PROJECT_DIR", "/home/mloco/Escritorio/Servidor-ia/moderation-bot")).expanduser()
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

    OPENCLAW_JSON = _load_openclaw_config()

    TELEGRAM_BOT_TOKEN = os.getenv(
        "OPENCLAW_TELEGRAM_BOT_TOKEN",
        os.getenv(
            "TELEGRAM_BOT_TOKEN",
            _nested_value(OPENCLAW_JSON, "channels", "telegram", "botToken", default=""),
        ),
    )
    TELEGRAM_WEBHOOK_SECRET = os.getenv(
        "OPENCLAW_TELEGRAM_WEBHOOK_SECRET",
        os.getenv(
            "TELEGRAM_WEBHOOK_SECRET",
            _nested_value(OPENCLAW_JSON, "channels", "telegram", "webhookSecret", default=""),
        ),
    )
    TELEGRAM_WEBHOOK_PORT = int(
        os.getenv(
            "TELEGRAM_WEBHOOK_PORT",
            os.getenv(
                "OPENCLAW_TELEGRAM_WEBHOOK_PORT",
                str(_nested_value(OPENCLAW_JSON, "channels", "telegram", "webhookPort", default="8085")),
            ),
        )
    )
    TELEGRAM_ALLOWED_CHAT_ID = os.getenv(
        "OPENCLAW_TELEGRAM_OWNER_ID",
        os.getenv("TELEGRAM_ALLOWED_CHAT_ID", _owner_allow_from(OPENCLAW_JSON)),
    )
    TELEGRAM_APPROVAL_CHAT_ID = os.getenv(
        "OPENCLAW_TELEGRAM_APPROVAL_CHAT_ID",
        os.getenv("TELEGRAM_APPROVAL_CHAT_ID", TELEGRAM_ALLOWED_CHAT_ID),
    )
    TELEGRAM_MONITORED_CHAT_ID = os.getenv(
        "OPENCLAW_TELEGRAM_MONITORED_CHAT_ID",
        os.getenv("TELEGRAM_MONITORED_CHAT_ID", ""),
    )
    TELEGRAM_WEBHOOK_BASE_PATH = os.getenv("TELEGRAM_WEBHOOK_BASE_PATH", "/telegram/webhook")
    TELEGRAM_RATE_LIMIT_SECONDS = int(os.getenv("TELEGRAM_RATE_LIMIT_SECONDS", "1"))
    TELEGRAM_PROACTIVE_INACTIVITY_HOURS = int(os.getenv("TELEGRAM_PROACTIVE_INACTIVITY_HOURS", "24"))
    TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE = int(os.getenv("TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE", "5"))

    @classmethod
    def validate(cls) -> None:
        """Validate the Telegram adapter configuration."""
        if not cls.PROJECT_DIR:
            raise ConfigError("PROJECT_DIR no puede estar vacio")
        if cls.MACHINE_TYPE not in {"um890", "dgx"}:
            raise ConfigError("MACHINE_TYPE debe ser 'um890' o 'dgx'")
        if not cls.DGX_OLLAMA_URL.startswith("http"):
            raise ConfigError("DGX_OLLAMA_URL invalida")
        if not cls.LOCAL_OLLAMA_URL.startswith("http"):
            raise ConfigError("LOCAL_OLLAMA_URL invalida")
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ConfigError("OPENCLAW_TELEGRAM_BOT_TOKEN o TELEGRAM_BOT_TOKEN es obligatorio")
        if cls.TELEGRAM_WEBHOOK_PORT <= 0:
            raise ConfigError("TELEGRAM_WEBHOOK_PORT invalido")
        if cls.TELEGRAM_RATE_LIMIT_SECONDS < 0:
            raise ConfigError("TELEGRAM_RATE_LIMIT_SECONDS invalido")
        if cls.TELEGRAM_PROACTIVE_INACTIVITY_HOURS < 0:
            raise ConfigError("TELEGRAM_PROACTIVE_INACTIVITY_HOURS invalido")
        if cls.TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE <= 0:
            raise ConfigError("TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE invalido")

    @classmethod
    def webhook_path(cls) -> str:
        if cls.TELEGRAM_WEBHOOK_SECRET:
            return f"{cls.TELEGRAM_WEBHOOK_BASE_PATH}/{cls.TELEGRAM_WEBHOOK_SECRET}"
        return cls.TELEGRAM_WEBHOOK_BASE_PATH
