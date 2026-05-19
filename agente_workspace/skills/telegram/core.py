"""Telegram message normalization and reply building."""

import time
import threading
from typing import Any, Dict

from skills.telegram.routing.remote_client import RemoteClient
from skills.telegram.routing.task_router import TaskRouter

LAST_MESSAGE_AT: dict[str, float] = {}


def _call_generate_with_timeout(remote: RemoteClient, generate_url: str, model: str, prompt: str, timeout: int) -> Dict[str, Any]:
    """Call remote.generate with thread-based timeout wrapper."""
    result = {"response": "", "error": None}
    error_holder = {}
    
    def call_it():
        try:
            response = remote.generate(
                generate_url=generate_url,
                model=model,
                prompt=prompt,
                timeout=timeout,
            )
            result.update(response or {})
        except Exception as e:
            error_holder["exc"] = e
    
    thread = threading.Thread(target=call_it, daemon=False)
    thread.start()
    thread.join(timeout=timeout + 10)  # Extra 10s buffer
    
    if thread.is_alive():
        # Thread is still running - the underlying call timed out or is hung
        return {"response": "", "error": f"Timeout after {timeout}s calling {generate_url}"}
    
    if error_holder.get("exc"):
        return {"response": "", "error": str(error_holder["exc"])}
    
    return result



def extract_update_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a Telegram update into the shared internal message shape."""
    try:
        update = payload.get("message") or payload.get("edited_message") or payload.get("channel_post")
        if not update:
            return {}

        sender = update.get("from", {})
        if sender.get("is_bot"):
            return {}

        chat = update.get("chat") or {}
        chat_id = chat.get("id")
        chat_type = chat.get("type") or "unknown"
        chat_title = chat.get("title") or chat.get("username") or str(chat_id or "")
        sender_id = sender.get("id")
        sender_name = sender.get("username") or sender.get("first_name") or str(chat_id or "")

        text = update.get("text") or update.get("caption") or ""
        file_id = ""
        file_name = ""
        mime_type = ""
        command = ""
        command_args = ""
        if text.startswith("/") and not any(update.get(key) for key in ("voice", "audio", "photo", "document", "video")):
            parts = text.split(maxsplit=1)
            command = parts[0].split("@", 1)[0][1:]
            command_args = parts[1].strip() if len(parts) > 1 else ""
        media_type = None
        if update.get("voice"):
            media_type = "voice"
            file_id = update.get("voice", {}).get("file_id", "")
            file_name = update.get("voice", {}).get("file_name", "")
            mime_type = update.get("voice", {}).get("mime_type", "")
        elif update.get("audio"):
            media_type = "audio"
            file_id = update.get("audio", {}).get("file_id", "")
            file_name = update.get("audio", {}).get("file_name", "")
            mime_type = update.get("audio", {}).get("mime_type", "")
        elif update.get("photo"):
            media_type = "photo"
            photo_items = update.get("photo") or []
            if photo_items:
                file_id = photo_items[-1].get("file_id", "")
        elif update.get("document"):
            media_type = "document"
            document = update.get("document") or {}
            file_id = document.get("file_id", "")
            file_name = document.get("file_name", "")
            mime_type = document.get("mime_type", "")
        elif update.get("video"):
            media_type = "video"
            video = update.get("video") or {}
            file_id = video.get("file_id", "")
            file_name = video.get("file_name", "")
            mime_type = video.get("mime_type", "")

        return {
            "chat_id": str(chat_id) if chat_id is not None else "",
            "chat_type": chat_type,
            "chat_title": chat_title,
            "sender_id": str(sender_id) if sender_id is not None else "",
            "sender": sender_name,
            "type": media_type or ("text" if text else "unknown"),
            "text": text,
            "command": command,
            "command_args": command_args,
            "message_id": update.get("message_id"),
            "raw_type": media_type or "text",
            "has_media": media_type is not None,
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
        }
    except Exception:
        return {}


def is_rate_limited(chat_id: str, min_seconds: int = 1) -> bool:
    if not chat_id:
        return False
    now = time.time()
    last = LAST_MESSAGE_AT.get(chat_id)
    LAST_MESSAGE_AT[chat_id] = now
    if last is None:
        return False
    return (now - last) < min_seconds


def build_reply(message: Dict[str, Any], router: TaskRouter, remote: RemoteClient, state: Any | None = None) -> str:
    """Build a text reply using the UM890/DGX core used by Telegram."""
    from skills.telegram.utils.logger import get_logger
    LOGGER = get_logger(__name__)
    
    command = (message.get("command") or "").lower()
    LOGGER.info(f"[build_reply] START command={command}")
    if command == "start":
        LOGGER.info(f"[build_reply] matched START command")
        return (
            "Hola. Estoy listo para ayudarte por Telegram. "
            "Puedes escribirme texto o comandos como /help."
        )
    if command == "help":
        LOGGER.info(f"[build_reply] matched HELP command")
        return (
            "Comandos disponibles:\n"
            "/start - iniciar\n"
            "/help - ver ayuda\n"
            "/status - estado básico del bot\n"
            "/summary - resumen del chat"
        )
    if command == "status":
        LOGGER.info(f"[build_reply] matched STATUS command")
        return "Bot activo. El core UM890/DGX está disponible para procesar mensajes."
    if command == "summary":
        LOGGER.info(f"[build_reply] matched SUMMARY command")
        if state is not None and message.get("chat_id"):
            chat_summary = getattr(state, "get_chat_summary", lambda _chat_id: {}) (message["chat_id"])
            if chat_summary:
                return (
                    "Resumen del chat:\n"
                    f"- Mensajes procesados: {int(chat_summary.get('message_count') or 0)}\n"
                    f"- Multimedia procesada: {int(chat_summary.get('media_count') or 0)}\n"
                    f"- Ultimo mensaje: {(chat_summary.get('last_message') or 'N/A')[:180]}"
                )
        return "Resumen del chat no disponible todavia."

    if message.get("type") != "text" or not (message.get("text") or "").strip():
        LOGGER.info(f"[build_reply] not text type, returning generic media response")
        media_type = message.get("raw_type") or message.get("type") or "mensaje"
        return (
            f"Recibí tu {media_type}. En esta primera fase priorizo texto y comandos; "
            "multimedia proactiva se activará después."
        )

    user_text = message["text"].strip()
    LOGGER.info(f"[build_reply] processing text, len={len(user_text)}")
    prompt = (
        "Eres el asistente OpenClaw en UM890. Responde en español, breve y accionable. "
        "Si detectas una tarea, sugiere el siguiente paso concreto.\n"
        f"Mensaje del usuario: {user_text}"
    )

    complexity = 3 if len(user_text) < 280 else 9
    LOGGER.info(f"[build_reply] routing with complexity={complexity}")
    route = router.route_chat(user_text) if complexity <= 5 else router.route_reasoning(user_text, complexity)
    LOGGER.info(f"[build_reply] route resolved: host={route.host} model={route.model} timeout={route.timeout}")

    try:
        LOGGER.info(f"[build_reply] calling remote.generate with timeout={route.timeout}")
        raw = _call_generate_with_timeout(remote, route.host, route.model, prompt, route.timeout)
        if raw.get("error"):
            LOGGER.warning(f"[build_reply] remote.generate error: {raw.get('error')}")
            raise Exception(raw.get("error"))
        LOGGER.info(f"[build_reply] remote.generate completed, response_len={len((raw or {}).get('response', ''))}")
    except Exception as e:
        LOGGER.warning(f"[build_reply] remote.generate failed ({type(e).__name__}), using fallback")
        try:
            fallback = router.route_fallback("chat")
            raw = _call_generate_with_timeout(remote, fallback.host, fallback.model, prompt, fallback.timeout)
            if raw.get("error"):
                LOGGER.warning(f"[build_reply] fallback also failed: {raw.get('error')}")
                raw = {"response": "Mensaje recibido. Estoy listo para ayudarte."}
        except Exception as fb_err:
            LOGGER.error(f"[build_reply] fallback exception: {fb_err}")
            raw = {"response": "Mensaje recibido. Estoy listo para ayudarte."}

    response = (raw.get("response") or "").strip()
    return response or "Mensaje recibido. Estoy listo para ayudarte."
