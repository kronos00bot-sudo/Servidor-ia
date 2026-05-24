"""Simple proactive rules for Telegram chats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .client import TelegramClient
from .state import TelegramState
from .utils.config import TelegramConfig


class TelegramProactiveEngine:
    """Evaluate chat state and emit lightweight proactive messages."""

    def __init__(self, state: Optional[TelegramState] = None, tg_client: Optional[TelegramClient] = None):
        self.state = state or TelegramState()
        self.tg_client = tg_client or TelegramClient()

    def _should_send_summary(self, chat_id: str, chat: Dict[str, object]) -> bool:
        last_seen = str(chat.get("last_seen") or "")
        last_proactive = str(chat.get("last_proactive_at") or "")
        if not last_seen:
            return False

        try:
            last_seen_dt = datetime.fromisoformat(last_seen)
        except Exception:
            return False

        threshold = timedelta(hours=TelegramConfig.TELEGRAM_PROACTIVE_INACTIVITY_HOURS)
        if datetime.now(timezone.utc) - last_seen_dt < threshold:
            return False

        if last_proactive:
            try:
                last_proactive_dt = datetime.fromisoformat(last_proactive)
                if last_proactive_dt >= last_seen_dt:
                    return False
            except Exception:
                pass

        return int(chat.get("message_count") or 0) > 0

    def build_summary_message(self, chat_id: str, chat: Dict[str, object]) -> str:
        message_count = int(chat.get("message_count") or 0)
        media_count = int(chat.get("media_count") or 0)
        last_message = str(chat.get("last_message") or "").strip()
        last_reply = str(chat.get("last_reply") or "").strip()
        pieces = [
            "Resumen proactivo de OpenClaw por Telegram:",
            f"- Mensajes procesados: {message_count}",
            f"- Elementos multimedia: {media_count}",
        ]
        if last_message:
            pieces.append(f"- Ultimo mensaje visto: {last_message[:180]}")
        if last_reply:
            pieces.append(f"- Ultima respuesta: {last_reply[:180]}")
        pieces.append("Si quieres, puedo seguir con un resumen mas detallado o con una accion concreta.")
        return "\n".join(pieces)

    def run_once(self, max_chats: Optional[int] = None) -> List[Dict[str, object]]:
        max_chats = max_chats or TelegramConfig.TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE
        sent: List[Dict[str, object]] = []
        for chat_id, chat in self.state.list_chats().items():
            if len(sent) >= max_chats:
                break
            if not self._should_send_summary(chat_id, chat):
                continue
            text = self.build_summary_message(chat_id, chat)
            outbound = self.tg_client.send_text(chat_id, text)
            if outbound.get("ok"):
                self.state.set_chat_proactive_at(chat_id)
            sent.append({"chat_id": chat_id, "text": text, "outbound": outbound})
        return sent
