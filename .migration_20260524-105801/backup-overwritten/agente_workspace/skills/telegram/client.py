"""Telegram outbound client."""

from typing import Optional

from skills.telegram.utils.http_client import HttpClient

from .utils.config import TelegramConfig


class TelegramClient:
    """Send outbound messages through the Telegram Bot API."""

    def __init__(self, token: Optional[str] = None, http_client: Optional[HttpClient] = None):
        self.token = token or TelegramConfig.TELEGRAM_BOT_TOKEN
        self.http = http_client or HttpClient()

    def send_text(self, chat_id: str, text: str) -> dict:
        if not self.token:
            return {"ok": False, "error": "Missing OPENCLAW_TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN"}
        if not chat_id:
            return {"ok": False, "error": "Missing chat_id"}

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        try:
            resp = self.http.post(url, json=payload, timeout=30)
            return {"ok": True, "response": resp.json()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
