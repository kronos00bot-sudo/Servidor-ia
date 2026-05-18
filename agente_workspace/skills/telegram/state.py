"""Persistent lightweight Telegram state for proactive behavior."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .utils.config import TelegramConfig


class TelegramState:
    """JSON-backed conversation state for Telegram chats."""

    def __init__(self, state_path: Path | None = None):
        self.path = state_path or (TelegramConfig.PROJECT_DIR / "data" / "telegram_state.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _default(self) -> Dict[str, Any]:
        return {
            "last_update_id": 0,
            "chats": {},
            "next_pending_id": 1,
            "pending_approvals": {},
        }

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self._default()
            data.setdefault("last_update_id", 0)
            data.setdefault("chats", {})
            data.setdefault("next_pending_id", 1)
            data.setdefault("pending_approvals", {})
            return data
        except Exception:
            return self._default()

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_last_update_id(self) -> int:
        return int(self.data.get("last_update_id") or 0)

    def set_last_update_id(self, update_id: int) -> None:
        current = self.get_last_update_id()
        if update_id > current:
            self.data["last_update_id"] = update_id
            self.save()

    def touch_chat(self, chat_id: str, incoming: Dict[str, Any], reply: str = "") -> None:
        chats = self.data.setdefault("chats", {})
        chat = chats.setdefault(chat_id, {
            "message_count": 0,
            "media_count": 0,
            "last_message": "",
            "last_reply": "",
            "last_seen": "",
            "last_proactive_at": "",
        })
        chat["message_count"] = int(chat.get("message_count") or 0) + 1
        if incoming.get("has_media"):
            chat["media_count"] = int(chat.get("media_count") or 0) + 1
        chat["last_message"] = (incoming.get("text") or incoming.get("raw_type") or "")[:1000]
        chat["last_reply"] = (reply or "")[:1000]
        chat["last_seen"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def get_chat_summary(self, chat_id: str) -> Dict[str, Any]:
        return dict(self.data.get("chats", {}).get(chat_id, {}))

    def list_chats(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.data.get("chats", {}))

    def set_chat_proactive_at(self, chat_id: str) -> None:
        chats = self.data.setdefault("chats", {})
        chat = chats.setdefault(chat_id, {})
        chat["last_proactive_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def create_pending_approval(
        self,
        source_chat_id: str,
        source_chat_name: str,
        sender: str,
        transcript: str,
        transcript_es: str,
        draft_reply_en: str,
        source_message_id: int | None,
        media_kind: str,
    ) -> str:
        pending = self.data.setdefault("pending_approvals", {})
        next_id = int(self.data.get("next_pending_id") or 1)
        approval_id = str(next_id)
        pending[approval_id] = {
            "id": approval_id,
            "status": "pending",
            "source_chat_id": str(source_chat_id),
            "source_chat_name": source_chat_name,
            "sender": sender,
            "transcript": (transcript or "")[:4000],
            "transcript_es": (transcript_es or "")[:4000],
            "draft_reply_en": (draft_reply_en or "")[:4000],
            "source_message_id": source_message_id,
            "media_kind": media_kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": "",
            "resolution_note": "",
        }
        self.data["next_pending_id"] = next_id + 1
        self.save()
        return approval_id

    def get_pending_approval(self, approval_id: str) -> Dict[str, Any]:
        pending = self.data.get("pending_approvals", {})
        item = pending.get(str(approval_id), {})
        return dict(item)

    def list_pending_approvals(self, limit: int = 10) -> list[Dict[str, Any]]:
        pending = self.data.get("pending_approvals", {})
        items = [dict(value) for value in pending.values() if value.get("status") == "pending"]
        items.sort(key=lambda x: int(x.get("id") or 0), reverse=True)
        return items[: max(1, limit)]

    def resolve_pending_approval(self, approval_id: str, status: str, resolution_note: str = "") -> bool:
        if status not in {"approved", "rejected"}:
            return False
        pending = self.data.setdefault("pending_approvals", {})
        item = pending.get(str(approval_id))
        if not item or item.get("status") != "pending":
            return False
        item["status"] = status
        item["resolved_at"] = datetime.now(timezone.utc).isoformat()
        item["resolution_note"] = (resolution_note or "")[:1000]
        self.save()
        return True
