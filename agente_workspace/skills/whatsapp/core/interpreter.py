"""Conversation interpretation for WhatsApp skill."""

import json
from pathlib import Path

from skills.whatsapp.routing.remote_client import RemoteClient
from skills.whatsapp.utils.config import Config

CONFIG = Config()
REMOTE = RemoteClient()

PROMPT = """Estás analizando una conversación de WhatsApp. A continuación verás la conversación completa, incluyendo transcripciones de audio/video y descripciones de imágenes y documentos.

Tu tarea:
1. Identificar los temas principales discutidos
2. Identificar participantes y sus roles/relación
3. Resumir los puntos clave de la conversación
4. Anotar decisiones, acuerdos y tareas accionables
5. Identificar tono y contexto (negocio, personal, urgencia, casual, etc.)

Importante:
- Responde SIEMPRE en español.
- Si hay transcripciones de audio, inclúyelas en los puntos clave de forma breve.
- Para videos, usa descripciones cortas (1-2 frases por evento relevante).
- Sé completo, pero conciso.

CONVERSACIÓN:
{conversation}"""


def _looks_like_placeholder(text: str) -> bool:
    low = (text or '').lower()
    markers = (
        'necesito que me facilites',
        'por favor, envíame',
        'por favor envíame',
        'necesito que me envíes',
        'facilites el contenido',
        'please provide',
        'please send',
    )
    return any(m in low for m in markers)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _hydrate_message_result(message: dict) -> None:
    """Completa result/procesado desde caché en disco si falta en parsed.json."""
    if message.get('result'):
        return

    msg_id = message.get('id')
    filepath = message.get('filepath')
    mtype = message.get('type')
    if msg_id is None or not filepath:
        return

    stem = Path(filepath).stem
    project = CONFIG.PROJECT_DIR

    candidate_paths = []
    if mtype == 'audio':
        candidate_paths.append(project / 'data' / 'transcriptions' / f"{msg_id:04d}_{stem}.json")
    elif mtype == 'video':
        candidate_paths.append(project / 'data' / 'transcriptions' / f"{msg_id:04d}_{stem}_video.json")
        candidate_paths.append(project / 'data' / 'transcriptions' / f"{msg_id:04d}_{stem}.json")
    elif mtype == 'image':
        candidate_paths.append(project / 'data' / 'descriptions' / f"{msg_id:04d}_{stem}.json")
    elif mtype == 'document':
        candidate_paths.append(project / 'data' / 'documents' / f"{msg_id:04d}_{stem}.json")

    for path in candidate_paths:
        data = _load_json(path)
        if not data:
            continue
        text = (data.get('text') or '').strip()
        if text:
            message['result'] = text
            message['processed'] = True
            return


def _short_video_description(text: str, max_len: int = 220) -> str:
    cleaned = ' '.join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + '...'


def build_conversation_text(messages: list) -> str:
    lines = []
    for m in messages:
        _hydrate_message_result(m)
        if m['type'] == 'omitted':
            continue
        timestamp = f"[{m['date']} {m['time']} ]"
        sender = m['sender']
        if m['type'] == 'text' and m.get('text'):
            lines.append(f"{timestamp} {sender}: {m['text']}")
        elif m.get('result'):
            label = {
                'audio': '🎤 AUDIO',
                'video': '🎥 VIDEO',
                'image': '🖼️ IMAGE',
                'document': '📄 DOCUMENT',
                'contact': '👤 CONTACT',
            }.get(m['type'], m['type'].upper())
            result_text = m['result']
            if m.get('type') == 'video':
                result_text = _short_video_description(result_text)
            lines.append(f"{timestamp} {sender} [{label}]: {result_text}")
        elif m.get('filename'):
            lines.append(f"{timestamp} {sender} [FILE - not processed]: {m['filename']}")
    return '\n'.join(lines)


def _compact_conversation_text(conversation_text: str, max_chars: int = 18000) -> str:
    """Reduce contexto para evitar saturar ventana del modelo remoto."""
    if len(conversation_text) <= max_chars:
        return conversation_text

    lines = conversation_text.splitlines()
    media_lines = [ln for ln in lines if ' [🎤 AUDIO]:' in ln or ' [🎥 VIDEO]:' in ln or ' [🖼️ IMAGE]:' in ln or ' [📄 DOCUMENT]:' in ln]

    head_budget = max_chars // 3
    tail_budget = max_chars // 3
    media_budget = max_chars - head_budget - tail_budget - 200

    head = conversation_text[:head_budget]
    tail = conversation_text[-tail_budget:]

    media_joined = '\n'.join(media_lines)
    if len(media_joined) > media_budget:
        media_joined = media_joined[:media_budget]

    return (
        "[CONTEXTO COMPACTADO POR TAMAÑO]\n"
        f"Tamaño original: {len(conversation_text)} caracteres.\n"
        "\n[INICIO]\n"
        f"{head}\n"
        "\n[EVENTOS DE MEDIA RELEVANTES]\n"
        f"{media_joined}\n"
        "\n[FINAL]\n"
        f"{tail}"
    )


def interpret(messages: list, router) -> dict:
    conversation_text = build_conversation_text(messages)
    llm_conversation = _compact_conversation_text(conversation_text)
    print(f'Sending conversation to DGX for interpretation...')
    route = router.route_reasoning(llm_conversation, complexity=9)
    prompt = PROMPT.format(conversation=llm_conversation)
    try:
        raw = REMOTE.generate(
            generate_url=route.host,
            model=route.model,
            prompt=prompt,
            timeout=route.timeout,
        )
    except Exception:
        fallback = router.route_fallback("reasoning")
        raw = REMOTE.generate(
            generate_url=fallback.host,
            model=fallback.model,
            prompt=prompt,
            timeout=fallback.timeout,
        )

    interpretation = raw.get('response', '').strip()
    if _looks_like_placeholder(interpretation):
        # Reintento con contexto aún más corto para forzar respuesta útil.
        tighter = _compact_conversation_text(conversation_text, max_chars=9000)
        retry_prompt = PROMPT.format(conversation=tighter)
        retry_raw = REMOTE.generate(
            generate_url=route.host,
            model=route.model,
            prompt=retry_prompt,
            timeout=route.timeout,
        )
        retried = retry_raw.get('response', '').strip()
        if retried:
            interpretation = retried

    return {
        'conversation_text': conversation_text,
        'interpretation': interpretation,
        'message_count': len(messages),
    }
