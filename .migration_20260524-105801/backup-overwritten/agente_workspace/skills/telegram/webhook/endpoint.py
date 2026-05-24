"""Flask webhook endpoint for Telegram Bot API events."""

from __future__ import annotations

import hmac
import json
from typing import Any, Dict

from flask import Flask, jsonify, request

from skills.telegram.routing.remote_client import RemoteClient
from skills.telegram.routing.task_router import TaskRouter
from skills.telegram.utils.exceptions import WebhookError
from skills.telegram.client import TelegramClient
from skills.telegram.media import TelegramMediaClient
from skills.telegram.service import process_update
from skills.telegram.state import TelegramState
from skills.telegram.utils.config import TelegramConfig
from skills.telegram.utils.exceptions import ConfigError
from skills.telegram.utils.logger import get_logger


LOGGER = get_logger(__name__)


def _verify_secret(secret: str) -> bool:
    expected = TelegramConfig.TELEGRAM_WEBHOOK_SECRET
    if not expected:
        return False
    return hmac.compare_digest(secret or "", expected)


def _extract_payload(raw_body: bytes) -> Dict[str, Any]:
    payload = request.get_json(silent=True)
    if payload is not None:
        return payload

    try:
        return json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise WebhookError(f"Invalid JSON payload: {exc}") from exc


def create_app(
    router: TaskRouter | None = None,
    remote: RemoteClient | None = None,
    tg_client: TelegramClient | None = None,
    validate_config: bool = True,
) -> Flask:
    app = Flask(__name__)

    if validate_config:
        TelegramConfig.validate()
        if not TelegramConfig.TELEGRAM_WEBHOOK_SECRET:
            raise ConfigError("TELEGRAM_WEBHOOK_SECRET es obligatorio para exponer el webhook")
    router = router or TaskRouter(TelegramConfig)
    remote = remote or RemoteClient()
    tg_client = tg_client or TelegramClient()
    state = TelegramState()
    media_client = TelegramMediaClient()

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "channel": "telegram"}), 200

    @app.get(TelegramConfig.webhook_path())
    def verify_webhook():
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not _verify_secret(header_secret):
            return "Forbidden", 403
        return jsonify({"ok": True, "channel": "telegram"}), 200

    @app.post(TelegramConfig.webhook_path())
    def receive_webhook():
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not _verify_secret(header_secret):
            return jsonify({"ok": False, "error": "Forbidden"}), 403

        raw_body = request.get_data() or b""
        try:
            payload = _extract_payload(raw_body)
            result = process_update(
                payload,
                router=router,
                remote=remote,
                tg_client=tg_client,
                state=state,
                media_client=media_client,
                allowed_chat_id=TelegramConfig.TELEGRAM_ALLOWED_CHAT_ID,
                min_interval=TelegramConfig.TELEGRAM_RATE_LIMIT_SECONDS,
            )
            return jsonify(result), 200
        except WebhookError as exc:
            LOGGER.warning("Webhook request rejected: %s", exc)
            return jsonify({"ok": False, "error": "Invalid request"}), 400
        except Exception as exc:
            LOGGER.exception("Webhook processing failed: %r", exc)
            return jsonify({"ok": False, "error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=TelegramConfig.TELEGRAM_WEBHOOK_PORT)
