"""Telegram long-polling runner for local/sandbox usage."""

from __future__ import annotations

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
