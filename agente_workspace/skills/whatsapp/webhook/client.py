"""Minimal WhatsApp Business API outbound client."""

from typing import Optional

from skills.whatsapp.utils.config import Config
from skills.whatsapp.utils.http_client import HttpClient


class WhatsAppClient:
    """Send outbound messages through Meta Graph API."""

    def __init__(self, token: Optional[str] = None, phone_number_id: Optional[str] = None):
        self.token = token or Config.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or Config.WHATSAPP_PHONE_NUMBER_ID
        self.http = HttpClient()

    def send_text(self, to: str, text: str) -> dict:
        if not self.token or not self.phone_number_id:
            return {"ok": False, "error": "Missing WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID"}

        url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = self.http.post(url, json=payload, headers=headers, timeout=30)
            return {"ok": True, "response": resp.json()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
