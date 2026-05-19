"""Shared Telegram event processing for webhook and polling."""

from __future__ import annotations

import concurrent.futures
from typing import Any, Dict

# Tiempo máximo (segundos) para cada llamada LLM en el poller;
# si se supera, se usa cadena vacía y el update sigue sin bloquear el loop.
_LLM_CALL_TIMEOUT = 60
_LLM_TRANSLATION_TIMEOUT = 60

from skills.telegram.routing.remote_client import RemoteClient
from skills.telegram.routing.task_router import TaskRouter
from skills.telegram.utils.logger import get_logger

from .core import build_reply, extract_update_message, is_rate_limited
from .client import TelegramClient
from .media import process_telegram_media
from .proactive import TelegramProactiveEngine
from .state import TelegramState
from .utils.config import TelegramConfig


LOGGER = get_logger(__name__)


def _build_english_fallback_draft(transcript: str) -> str:
    """Build a minimal deterministic English draft when LLM generation is unavailable."""
    text = " ".join((transcript or "").strip().split())
    if not text:
        return "Thanks for your message. Could you share a bit more detail so I can help accurately?"
    snippet = text[:180].rstrip(" .,!?:;")
    return (
        "Thanks for the update. I understand the key point is: "
        f"\"{snippet}\". "
        "Could you confirm the next action you want me to take?"
    )


def _build_english_draft(transcript: str, router: TaskRouter, remote: RemoteClient) -> str:
    text = (transcript or "").strip()
    if not text:
        return ""

    prompt = (
        "You are an assistant replying in a group chat. "
        "Write a concise, natural English response based on this message transcript. "
        "Keep it practical and friendly. Do not mention that this is a draft.\n\n"
        f"Transcript:\n{text}"
    )

    def _call() -> str:
        try:
            route_translation = getattr(router, "route_translation", None)
            if callable(route_translation):
                route = route_translation(text)
            else:
                route = router.route_chat(text)
            raw = remote.generate(
                generate_url=route.host,
                model=route.model,
                prompt=prompt,
                timeout=route.timeout,
            )
        except Exception:
            fallback = router.route_fallback("translation")
            raw = remote.generate(
                generate_url=fallback.host,
                model=fallback.model,
                prompt=prompt,
                timeout=fallback.timeout,
            )
        return (raw.get("response") or "").strip()

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_call)
    try:
        draft = (future.result(timeout=_LLM_CALL_TIMEOUT) or "").strip()
        if draft:
            return draft
        LOGGER.warning("_build_english_draft returned empty response, using local fallback")
        return _build_english_fallback_draft(text)
    except Exception as exc:
        LOGGER.warning("_build_english_draft timeout/error: %r", exc)
        future.cancel()
        return _build_english_fallback_draft(text)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _translate_transcript_to_spanish(transcript: str, router: TaskRouter, remote: RemoteClient) -> str:
    text = (transcript or "").strip()
    if not text:
        return ""
    route_translation = getattr(router, "route_translation", None)
    if callable(route_translation):
        route = route_translation(text)
    else:
        route = router.route_chat(text)
    request_timeout = max(int(getattr(route, "timeout", 0) or 0), _LLM_TRANSLATION_TIMEOUT)

    prompt = (
        "Traduce al espanol de forma fiel y breve. "
        "Devuelve solo la traduccion final sin comentarios adicionales.\n\n"
        f"Texto:\n{text}"
    )

    def _call() -> str:
        raw = remote.generate(
            generate_url=route.host,
            model=route.model,
            prompt=prompt,
            timeout=request_timeout,
        )
        return (raw.get("response") or "").strip()

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_call)
    try:
        return future.result(timeout=request_timeout)
    except Exception as exc:
        LOGGER.warning("_translate_transcript_to_spanish timeout/error: %r", exc)
        future.cancel()
        return ""
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _translate_approval_note_to_english(note: str, router: TaskRouter, remote: RemoteClient) -> str:
    text = (note or "").strip()
    if not text:
        return ""
    route_translation = getattr(router, "route_translation", None)
    if callable(route_translation):
        route = route_translation(text)
    else:
        route = router.route_chat(text)
    request_timeout = max(int(getattr(route, "timeout", 0) or 0), _LLM_TRANSLATION_TIMEOUT)

    prompt = (
        "Translate this Spanish approval note into natural English. "
        "Return only the English text, without extra comments.\n\n"
        f"Texto:\n{text}"
    )

    def _call() -> str:
        raw = remote.generate(
            generate_url=route.host,
            model=route.model,
            prompt=prompt,
            timeout=request_timeout,
        )
        return (raw.get("response") or "").strip()

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_call)
    try:
        return future.result(timeout=request_timeout)
    except Exception as exc:
        LOGGER.warning("_translate_approval_note_to_english timeout/error: %r", exc)
        future.cancel()
        return ""
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _format_pending_for_approval(
    approval_id: str,
    source_chat_name: str,
    sender: str,
    transcript: str,
    transcript_es: str,
    draft_reply: str,
) -> str:
    return (
        "Nueva solicitud para aprobar respuesta\n"
        f"ID: {approval_id}\n"
        f"Chat origen: {source_chat_name}\n"
        f"Remitente: {sender}\n\n"
        "Transcripcion:\n"
        f"{(transcript or 'N/A')[:1200]}\n\n"
        "Traduccion al espanol:\n"
        f"{(transcript_es or 'No disponible.')[:1200]}\n\n"
        "Borrador en ingles:\n"
        f"{(draft_reply or 'No se pudo generar borrador automaticamente.')[:1200]}\n\n"
        "Comandos:\n"
        f"/aprobar {approval_id}\n"
        f"/aprobar {approval_id} <texto_en_ingles_editado>\n"
        f"/rechazar {approval_id} <motivo_opcional>\n"
        "/pendientes"
    )


def _handle_approval_command(
    message: Dict[str, Any],
    state: TelegramState,
    tg_client: TelegramClient,
    router: TaskRouter,
    remote: RemoteClient,
) -> Dict[str, Any] | None:
    command = (message.get("command") or "").lower()
    aliases = {
        "aprobar": "approve",
        "rechazar": "reject",
        "pendientes": "pending",
    }
    command = aliases.get(command, command)
    if command not in {"approve", "reject", "pending"}:
        return None

    chat_id = message.get("chat_id") or ""
    args = (message.get("command_args") or "").strip()

    if command == "pending":
        pending_items = state.list_pending_approvals(limit=10)
        if not pending_items:
            reply = "No hay respuestas pendientes de aprobación."
        else:
            lines = ["Pendientes de aprobación:"]
            for item in pending_items:
                lines.append(
                    f"- ID {item.get('id')}: {item.get('source_chat_name')} | {item.get('sender')}"
                )
            reply = "\n".join(lines)
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": True, "approval": command, "reply": reply, "outbound": outbound}

    parts = args.split(maxsplit=1) if args else []
    approval_id = parts[0] if parts else ""
    note = parts[1].strip() if len(parts) > 1 else ""
    if not approval_id:
        reply = "Debes indicar un ID. Ejemplo: /aprobar 12"
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": True, "approval": command, "reply": reply, "outbound": outbound}

    item = state.get_pending_approval(approval_id)
    if not item:
        reply = f"No existe un pendiente activo con ID {approval_id}."
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": True, "approval": command, "reply": reply, "outbound": outbound}

    status = (item.get("status") or "").strip().lower()
    if status != "pending":
        if status == "rejected":
            reply = f"La solicitud {approval_id} ya fue rechazada."
        elif status == "approved":
            reply = f"La solicitud {approval_id} ya fue aprobada y enviada."
        else:
            reply = f"No existe un pendiente activo con ID {approval_id}."
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": True, "approval": command, "reply": reply, "outbound": outbound}

    if command == "reject":
        state.resolve_pending_approval(approval_id, "rejected", note)
        reply = f"Solicitud {approval_id} rechazada."
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": True, "approval": command, "reply": reply, "outbound": outbound}

    final_reply = (item.get("draft_reply_en") or "").strip()
    if note:
        translated_note = _translate_approval_note_to_english(note, router=router, remote=remote)
        final_reply = translated_note or final_reply
    elif not final_reply:
        transcript = str(item.get("transcript") or "").strip()
        if transcript and "No se pudo transcribir contenido" not in transcript:
            final_reply = _build_english_draft(transcript, router=router, remote=remote)
    if not final_reply:
        reply = "No hay borrador para aprobar. Usa /aprobar <id> <texto_en_ingles>."
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": True, "approval": command, "reply": reply, "outbound": outbound}

    sent = tg_client.send_text(str(item.get("source_chat_id") or ""), final_reply)
    if not sent.get("ok"):
        reply = f"No se pudo enviar al chat origen (ID {approval_id})."
        outbound = tg_client.send_text(chat_id, reply)
        return {"ok": False, "approval": command, "reply": reply, "outbound": outbound, "send_error": sent}

    state.resolve_pending_approval(approval_id, "approved", note)
    reply = f"Solicitud {approval_id} aprobada y enviada al chat origen."
    outbound = tg_client.send_text(chat_id, reply)
    return {"ok": True, "approval": command, "reply": reply, "outbound": outbound, "sent": sent}


def _build_transcript_for_review(message: Dict[str, Any], media_result: Dict[str, Any] | None) -> str:
    text = (message.get("text") or "").strip()
    if text:
        return text
    if media_result and media_result.get("text"):
        return str(media_result.get("text") or "").strip()
    media_kind = (media_result or {}).get("kind") or message.get("raw_type") or "archivo"
    media_error = (media_result or {}).get("error") or "sin detalle"
    return f"[{media_kind}] No se pudo transcribir contenido. error={media_error}"


def process_update(
    payload: Dict[str, Any],
    router: TaskRouter,
    remote: RemoteClient,
    tg_client: TelegramClient,
    state: TelegramState | None = None,
    media_client: Any | None = None,
    allowed_chat_id: str = "",
    min_interval: int = 1,
) -> Dict[str, Any]:
    """Normalize an incoming Telegram update, generate a reply and send it."""
    state = state or TelegramState()
    message = extract_update_message(payload)
    if not message:
        return {"ok": True, "ignored": "No user message in event"}

    chat_id = str(message.get("chat_id") or "")

    approval_chat_id = str(TelegramConfig.TELEGRAM_APPROVAL_CHAT_ID or allowed_chat_id or "")
    monitored_chat_id = str(TelegramConfig.TELEGRAM_MONITORED_CHAT_ID or "")
    chat_type = message.get("chat_type") or ""
    is_group_chat = chat_type in {"group", "supergroup"}
    is_command = bool((message.get("command") or "").strip())
    private_review_mode = (
        not monitored_chat_id
        and bool(approval_chat_id)
        and chat_id == approval_chat_id
        and not is_command
    )
    # Si no hay chat monitorizado explícito, solo activamos revisión privada
    # en el chat de aprobación; no auto-monitorizamos grupos.
    effective_monitored_chat_id = monitored_chat_id or (chat_id if private_review_mode else "")

    if monitored_chat_id and chat_id not in {monitored_chat_id, approval_chat_id}:
        return {"ok": True, "ignored": "Chat not monitored"}
    if not effective_monitored_chat_id and allowed_chat_id:
        allowed_normalized = str(allowed_chat_id)
        if chat_id != allowed_normalized:
            return {"ok": True, "ignored": "Chat not allowed"}

    # No aplicar rate limit a multimedia para no perder rafagas de archivos/importaciones.
    if not message.get("has_media") and is_rate_limited(chat_id, min_interval):
        return {"ok": True, "ignored": "Rate limited"}

    LOGGER.info(f"[process_update] approval_chat_id={approval_chat_id} chat_id={chat_id} is_command={is_command}")
    if approval_chat_id and chat_id == approval_chat_id:
        LOGGER.info(f"[process_update] calling _handle_approval_command for command={message.get('command')}")
        approval_result = _handle_approval_command(message, state=state, tg_client=tg_client, router=router, remote=remote)
        LOGGER.info(f"[process_update] _handle_approval_command returned: {approval_result is not None}")
        if approval_result is not None:
            state.touch_chat(chat_id, message, reply=approval_result.get("reply") or "")
            return approval_result

    media_result = None
    if message.get("has_media"):
        LOGGER.warning(
            "media_start chat_id=%s message_id=%s raw_type=%s",
            chat_id,
            message.get("message_id"),
            message.get("raw_type") or message.get("type"),
        )
        try:
            media_result = process_telegram_media(message, router=router, media_client=media_client)
        except Exception as exc:
            LOGGER.exception("Telegram media processing failed", exc_info=exc)
            media_result = {
                "ok": False,
                "kind": message.get("raw_type") or message.get("type"),
                "text": None,
                "error": str(exc),
            }
        LOGGER.warning(
            "media_done chat_id=%s message_id=%s ok=%s has_text=%s error=%s",
            chat_id,
            message.get("message_id"),
            (media_result or {}).get("ok"),
            bool((media_result or {}).get("text")),
            (media_result or {}).get("error"),
        )

        if media_result.get("text"):
            message = dict(message)
            message["media_result"] = media_result
            message["text"] = media_result.get("text")
            message["type"] = "text"
            message["raw_type"] = media_result.get("kind", message.get("raw_type"))

    # En modo revisión privada solo encolamos mensajes con media (audio/voz/doc).
    # Los textos del propietario en el chat de aprobación son conversación normal o comandos.
    # En grupos monitorizados se encola todo (texto y media).
    has_queueable_content = message.get("has_media") or not private_review_mode
    is_from_monitored_chat = effective_monitored_chat_id and str(effective_monitored_chat_id) == str(chat_id)
    if is_from_monitored_chat and has_queueable_content:
        LOGGER.warning(
            "approval_queue_start chat_id=%s message_id=%s private_review_mode=%s has_media=%s",
            chat_id,
            message.get("message_id"),
            private_review_mode,
            bool(message.get("has_media")),
        )
        transcript = _build_transcript_for_review(message, media_result)
        transcript_es = ""
        draft_reply = ""
        transcription_failed = "No se pudo transcribir contenido" in transcript
        if transcription_failed:
            LOGGER.warning(
                "approval_queue_skip_llm chat_id=%s message_id=%s reason=transcription_failed",
                chat_id,
                message.get("message_id"),
            )
        else:
            transcript_es = _translate_transcript_to_spanish(transcript, router=router, remote=remote)
            if not transcript_es:
                LOGGER.warning(
                    "approval_queue_skip_draft chat_id=%s message_id=%s reason=translation_unavailable",
                    chat_id,
                    message.get("message_id"),
                )
            # El borrador en ingles no debe depender de la traduccion al espanol.
            draft_reply = _build_english_draft(transcript, router=router, remote=remote)
        approval_id = state.create_pending_approval(
            source_chat_id=chat_id,
            source_chat_name=message.get("chat_title") or chat_id,
            sender=message.get("sender") or "unknown",
            transcript=transcript,
            transcript_es=transcript_es,
            draft_reply_en=draft_reply,
            source_message_id=message.get("message_id"),
            media_kind=(message.get("raw_type") or message.get("type") or "text"),
        )
        if approval_chat_id:
            approval_text = _format_pending_for_approval(
                approval_id=approval_id,
                source_chat_name=message.get("chat_title") or chat_id,
                sender=message.get("sender") or "unknown",
                transcript=transcript,
                transcript_es=transcript_es,
                draft_reply=draft_reply,
            )
            outbound = tg_client.send_text(approval_chat_id, approval_text)
        else:
            outbound = {"ok": False, "error": "Missing TELEGRAM_APPROVAL_CHAT_ID"}
        state.touch_chat(chat_id, message, reply=f"pending_approval:{approval_id}")
        LOGGER.warning(
            "approval_queue_done chat_id=%s message_id=%s approval_id=%s outbound_ok=%s",
            chat_id,
            message.get("message_id"),
            approval_id,
            outbound.get("ok") if isinstance(outbound, dict) else None,
        )
        return {
            "ok": True,
            "queued_for_approval": True,
            "approval_id": approval_id,
            "outbound": outbound,
        }
    # Guard: si viene del Chat Origen monitoreado pero no se encoló, no intentes build_reply
    if is_from_monitored_chat:
        return {
            "ok": True,
            "ignored": "Message from monitored chat not queueable (likely a command or media processing)",
        }
    if message.get("has_media") and not (message.get("text") or "").strip():
        media_kind = (media_result or {}).get("kind") or message.get("raw_type") or "archivo"
        media_error = (media_result or {}).get("error")
        if media_error:
            reply = (
                f"Recibi tu {media_kind}, pero fallo el procesamiento multimedia. "
                "Prueba de nuevo o envia texto con contexto."
            )
        else:
            reply = (
                f"Recibi tu {media_kind}, pero no pude extraer contenido util. "
                "Prueba con otro archivo o envia texto."
            )
    else:
        LOGGER.info(f"[process_update] calling build_reply with command={message.get('command')} text_len={len((message.get('text') or ''))}")
        reply = build_reply(message, router, remote, state=state)
        LOGGER.info(f"[process_update] build_reply returned: {len((reply or ''))} chars")

    outbound = tg_client.send_text(chat_id, reply)
    state.touch_chat(chat_id, message, reply=reply)
    return {"ok": True, "message": message, "reply": reply, "outbound": outbound}


def run_proactive_cycle(state: TelegramState, tg_client: TelegramClient) -> list[dict]:
    engine = TelegramProactiveEngine(state=state, tg_client=tg_client)
    return engine.run_once()
