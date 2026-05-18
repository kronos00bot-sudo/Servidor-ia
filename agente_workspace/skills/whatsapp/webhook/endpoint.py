"""Flask webhook endpoint for WhatsApp Business events."""

import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict

from flask import Flask, jsonify, request

from skills.whatsapp.routing.remote_client import RemoteClient
from skills.whatsapp.routing.task_router import TaskRouter
from skills.whatsapp.utils.config import Config
from skills.whatsapp.utils.exceptions import WebhookError
from skills.whatsapp.webhook.client import WhatsAppClient


LAST_MESSAGE_AT = {}


def _verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    signature = signature.replace("sha256=", "")
    return hmac.compare_digest(expected, signature)


def _extract_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        messages = value.get("messages", [])
        if not messages:
            return {}
        message = messages[0]
        return {
            "from": message.get("from"),
            "type": message.get("type"),
            "text": message.get("text", {}).get("body"),
        }
    except Exception as exc:
        raise WebhookError(f"Invalid webhook payload: {exc}") from exc


def _is_rate_limited(sender: str, min_seconds: int = 1) -> bool:
    if not sender:
        return False
    now = time.time()
    last = LAST_MESSAGE_AT.get(sender)
    LAST_MESSAGE_AT[sender] = now
    if last is None:
        return False
    return (now - last) < min_seconds


def _build_reply(message: Dict[str, Any], router: TaskRouter, remote: RemoteClient) -> str:
    if message.get("type") != "text" or not (message.get("text") or "").strip():
        return "Recibi tu mensaje. Ahora mismo proceso texto; multimedia estara disponible en la siguiente fase."

    user_text = message["text"].strip()
    prompt = (
        "Eres el asistente OpenClaw en UM890. Responde en espanol, breve y accionable.\n"
        f"Mensaje del usuario: {user_text}"
    )

    complexity = 3 if len(user_text) < 280 else 9
    route = router.route_chat(user_text) if complexity <= 5 else router.route_reasoning(user_text, complexity)

    try:
        raw = remote.generate(
            generate_url=route.host,
            model=route.model,
            prompt=prompt,
            timeout=route.timeout,
        )
    except Exception:
        fallback = router.route_fallback("chat")
        raw = remote.generate(
            generate_url=fallback.host,
            model=fallback.model,
            prompt=prompt,
            timeout=fallback.timeout,
        )

    response = (raw.get("response") or "").strip()
    return response or "Mensaje recibido. Estoy listo para ayudarte."


def create_app(router: TaskRouter = None, remote: RemoteClient = None, wa_client: WhatsAppClient = None) -> Flask:
    app = Flask(__name__)

    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "")
    router = router or TaskRouter(Config)
    remote = remote or RemoteClient()
    wa_client = wa_client or WhatsAppClient()
    min_interval = int(os.getenv("WHATSAPP_RATE_LIMIT_SECONDS", "1"))

    @app.get("/webhook")
    def verify_webhook():
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            return challenge, 200
        return "Forbidden", 403

    @app.post("/webhook")
    def receive_webhook():
        raw_body = request.get_data() or b""
        signature = request.headers.get("X-Hub-Signature-256", "")

        if app_secret and not _verify_signature(raw_body, signature, app_secret):
            return jsonify({"ok": False, "error": "Invalid signature"}), 401

        payload = request.get_json(silent=True)
        if payload is None:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception:
                return jsonify({"ok": False, "error": "Invalid JSON"}), 400

        try:
            message = _extract_message(payload)
            if not message:
                return jsonify({"ok": True, "ignored": "No user message in event"}), 200

            sender = message.get("from")
            if _is_rate_limited(sender, min_interval):
                return jsonify({"ok": True, "ignored": "Rate limited"}), 200

            reply = _build_reply(message, router, remote)
            outbound = wa_client.send_text(sender, reply) if sender else {"ok": False, "error": "Missing sender"}

            return jsonify({"ok": True, "message": message, "reply": reply, "outbound": outbound}), 200
        except WebhookError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("WHATSAPP_WEBHOOK_PORT", "8000")))
