"""Telegram long-polling runner for local/sandbox usage."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from skills.telegram.utils.http_client import HttpClient
from skills.telegram.utils.logger import get_logger

from .client import TelegramClient
from .media import TelegramMediaClient
from .service import process_update, run_proactive_cycle
from .state import TelegramState
from .utils.config import TelegramConfig


LOGGER = get_logger(__name__)


class TelegramPollingClient:
    """Minimal Telegram Bot API client for polling updates."""

    def __init__(self, token: Optional[str] = None, http_client: Optional[HttpClient] = None):
        self.token = token or TelegramConfig.TELEGRAM_BOT_TOKEN
        self.http = http_client or HttpClient()

    def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        resp = self.http.get(url, params=params, timeout=timeout + 5)
        return resp.json()


class TelegramPoller:
    """Poll Telegram updates and route them through the shared service layer."""

    def __init__(self, router, remote, tg_client: Optional[TelegramClient] = None, polling_client: Optional[TelegramPollingClient] = None, state: Optional[TelegramState] = None, media_client: Optional[TelegramMediaClient] = None):
        self.router = router
        self.remote = remote
        self.tg_client = tg_client or TelegramClient()
        self.polling_client = polling_client or TelegramPollingClient()
        self.state = state or TelegramState()
        self.media_client = media_client or TelegramMediaClient()
        self._startup_alert_sent = False

    def _validate_monitored_chat_access(self) -> None:
        """Best-effort startup validation to avoid silent misconfiguration."""
        monitored_chat_id = str(TelegramConfig.TELEGRAM_MONITORED_CHAT_ID or "").strip()
        if not monitored_chat_id:
            return

        token = self.polling_client.token
        url = f"https://api.telegram.org/bot{token}/getChat"
        try:
            resp = self.polling_client.http.get(url, params={"chat_id": monitored_chat_id}, timeout=15)
            data = resp.json() if resp is not None else {}
            if not isinstance(data, dict) or not data.get("ok"):
                raise RuntimeError("Unexpected getChat response")
            chat = data.get("result") or {}
            LOGGER.info(
                "poller_startup_check ok monitored_chat_id=%s chat_type=%s title=%s",
                monitored_chat_id,
                chat.get("type"),
                chat.get("title") or chat.get("username") or chat.get("first_name") or "",
            )
        except Exception as exc:
            LOGGER.error(
                "poller_startup_check failed monitored_chat_id=%s error=%r",
                monitored_chat_id,
                exc,
            )
            if self._startup_alert_sent:
                return
            self._startup_alert_sent = True
            approval_chat_id = str(TelegramConfig.TELEGRAM_APPROVAL_CHAT_ID or TelegramConfig.TELEGRAM_ALLOWED_CHAT_ID or "").strip()
            if approval_chat_id:
                self.tg_client.send_text(
                    approval_chat_id,
                    (
                        "[alerta] El poller de Telegram esta activo, pero no puede acceder al chat monitorizado.\n"
                        f"chat_id configurado: {monitored_chat_id}\n"
                        "Motivo probable: chat_id incorrecto o bot sin acceso al grupo."
                    ),
                )

    def _validate_required_bot_username(self) -> None:
        """Fail fast when the configured bot identity does not match expected."""
        required = os.getenv("OPENCLAW_TELEGRAM_REQUIRED_BOT_USERNAME", "").strip().lstrip("@").lower()
        if not required:
            return

        token = self.polling_client.token
        if not token:
            raise RuntimeError("Missing Telegram bot token")

        url = f"https://api.telegram.org/bot{token}/getMe"
        resp = self.polling_client.http.get(url, timeout=15)
        data = resp.json() if resp is not None else {}
        username = str(((data or {}).get("result") or {}).get("username") or "").strip().lstrip("@").lower()
        if username != required:
            raise RuntimeError(f"Unexpected Telegram bot username: got '{username}', expected '{required}'")

    def run_once(self, offset: Optional[int] = None) -> int:
        current_offset = offset if offset is not None else self.state.get_last_update_id()
        LOGGER.info(f"[poller] run_once: calling get_updates(offset={current_offset})")
        data = self.polling_client.get_updates(offset=current_offset)
        updates = data.get("result", []) if isinstance(data, dict) else []
        LOGGER.info(f"[poller] run_once: received {len(updates)} updates from Telegram API")
        next_offset = current_offset or 0

        for update in updates:
            update_id = update.get("update_id")
            LOGGER.info(f"[poller] run_once: processing update_id={update_id}")
            if isinstance(update_id, int) and update_id >= next_offset:
                next_offset = update_id + 1
            try:
                LOGGER.info(f"[poller] run_once: calling process_update for update_id={update_id}")
                process_update(
                    update,
                    router=self.router,
                    remote=self.remote,
                    tg_client=self.tg_client,
                    state=self.state,
                    media_client=self.media_client,
                    allowed_chat_id=TelegramConfig.TELEGRAM_ALLOWED_CHAT_ID,
                    min_interval=TelegramConfig.TELEGRAM_RATE_LIMIT_SECONDS,
                )
                LOGGER.info(f"[poller] run_once: process_update COMPLETED for update_id={update_id}")
            except Exception as e:
                LOGGER.error("[poller] Failed to process update %s: %r", update_id, e, exc_info=True)
            if isinstance(next_offset, int) and next_offset > 0:
                self.state.set_last_update_id(next_offset)
        if not updates:
            run_proactive_cycle(self.state, self.tg_client)
        LOGGER.info(f"[poller] run_once: returning next_offset={next_offset}")
        return next_offset

    def run_forever(self, sleep_seconds: int = 2) -> None:
        offset = None
        self._validate_required_bot_username()
        self._validate_monitored_chat_access()
        while True:
            try:
                LOGGER.info(f"run_forever: starting polling cycle with offset={offset}")
                offset = self.run_once(offset)
                LOGGER.info(f"run_forever: cycle completed, new offset={offset}")
            except Exception as exc:
                LOGGER.exception("Telegram polling cycle failed", exc_info=exc)
                time.sleep(sleep_seconds)
                continue
            time.sleep(sleep_seconds)
