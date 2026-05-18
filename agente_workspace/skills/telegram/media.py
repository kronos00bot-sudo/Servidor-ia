"""Telegram media download and processing helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from skills.telegram.routing.task_router import TaskRouter
from skills.telegram.transcriber import transcribe_file
from skills.telegram.utils.http_client import HttpClient

from .utils.config import TelegramConfig


class TelegramMediaClient:
    """Download Telegram files via Bot API."""

    def __init__(self, token: Optional[str] = None, http_client: Optional[HttpClient] = None):
        self.token = token or TelegramConfig.TELEGRAM_BOT_TOKEN
        self.http = http_client or HttpClient()
        self.download_root = TelegramConfig.PROJECT_DIR / "media" / "telegram"
        self.download_root.mkdir(parents=True, exist_ok=True)

    def get_file(self, file_id: str) -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/getFile"
        resp = self.http.get(url, params={"file_id": file_id}, timeout=30)
        return resp.json()

    def download_file(self, file_path: str, destination: Path) -> Path:
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        resp = self.http.get(url, timeout=60)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(resp.content)
        return destination

    def download_attachment(self, message: Dict[str, Any], chat_id: str, msg_id: Any) -> Dict[str, Any]:
        raw_type = message.get("raw_type") or message.get("type")
        file_id = message.get("file_id")
        if not file_id:
            return {"ok": False, "error": "Missing file_id"}

        file_info = self.get_file(file_id)
        result = file_info.get("result") if isinstance(file_info, dict) else None
        file_path = (result or {}).get("file_path")
        if not file_path:
            return {"ok": False, "error": "Missing file_path from Telegram API"}

        file_name = message.get("file_name") or Path(file_path).name
        ext = Path(file_name).suffix or Path(file_path).suffix or _default_suffix(raw_type)
        dest_dir = self.download_root / str(chat_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        destination = dest_dir / f"{int(msg_id):04d}_{Path(file_name).stem}{ext}"
        saved = self.download_file(file_path, destination)
        return {
            "ok": True,
            "kind": raw_type,
            "file_id": file_id,
            "file_path": file_path,
            "file_name": file_name,
            "saved_path": str(saved),
        }


def _default_suffix(raw_type: str) -> str:
    return {
        "voice": ".oga",
        "audio": ".mp3",
        "video": ".mp4",
        "photo": ".jpg",
        "document": ".bin",
    }.get(raw_type, ".bin")


def process_telegram_media(message: Dict[str, Any], router: TaskRouter, media_client: Optional[TelegramMediaClient] = None) -> Dict[str, Any]:
    """Download and process a Telegram media message using the shared core processors."""
    media_client = media_client or TelegramMediaClient()
    chat_id = message.get("chat_id") or "unknown"
    msg_id = message.get("message_id") or 0
    raw_type = message.get("raw_type") or message.get("type")

    if raw_type not in {"voice", "audio", "photo", "document", "video"}:
        return {"ok": False, "error": f"Unsupported media type: {raw_type}"}

    downloaded = media_client.download_attachment(message, chat_id=chat_id, msg_id=msg_id)
    if not downloaded.get("ok"):
        return downloaded

    saved_path = Path(downloaded["saved_path"])
    result: Dict[str, Any]

    if raw_type in {"voice", "audio"}:
        result = transcribe_file(str(saved_path), int(msg_id))
    elif raw_type in {"photo", "document", "video"}:
        result = {
            "id": msg_id,
            "text": None,
            "error": f"{raw_type} processing is disabled in telegram-only mode",
        }
    else:
        result = {"id": msg_id, "text": None, "error": f"Unsupported media type: {raw_type}"}

    return {
        "ok": True,
        "kind": raw_type,
        "download": downloaded,
        "result": result,
        "text": result.get("text"),
        "error": result.get("error"),
    }
