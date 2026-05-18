"""Translation and final reporting for WhatsApp skill."""

import json
import re
from skills.whatsapp.routing.remote_client import RemoteClient
from skills.whatsapp.utils.config import Config

CONFIG = Config()
REMOTE = RemoteClient()

PROMPT_TRANSLATE = """Eres un traductor profesional. Traduce la siguiente conversación de WhatsApp al español.

Reglas:
- Mantén el formato original: [date time] Sender: message
- Conserva nombres propios tal como están
- Mantén timestamps exactamente iguales
- Traduce de forma natural (no literal) respetando tono y registro
- Conserva etiquetas entre corchetes (AUDIO/VIDEO/IMAGE/DOCUMENT)
- Si un texto ya está en español, déjalo tal cual
- NO omitas líneas, aunque sean cortas o repetitivas
- Si el contenido viene de audio transcrito o descripción visual, también debe quedar en español

CONVERSACIÓN A TRADUCIR:
{conversation}"""

PROMPT_FINAL = """Con base en el análisis y en la traducción al español de esta conversación de WhatsApp, crea un informe final claro en español con esta estructura:

# Resumen de la Conversación

## Participantes
[List participants]

## Temas Principales
[Main topics discussed]

## Puntos Clave
[Key points, decisions, agreements]

## Tono y Contexto
[Tone and context]

## Conversación Traducida
[Full translated conversation]

ANÁLISIS:
{interpretation}

CONVERSACIÓN TRADUCIDA:
{translated}"""


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


def _compact_text(text: str, max_chars: int = 18000) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-(max_chars // 2) :]
    return (
        "[CONTENIDO COMPACTADO POR TAMAÑO]\n"
        f"Tamaño original: {len(text)} caracteres.\n"
        "\n[INICIO]\n"
        f"{head}\n"
        "\n[FINAL]\n"
        f"{tail}"
    )


def _compact_conversation_with_media(conversation_text: str, max_chars: int = 26000) -> str:
    """Compacta conversación preservando eventos multimedia relevantes."""
    if len(conversation_text) <= max_chars:
        return conversation_text

    lines = conversation_text.splitlines()
    media_lines = [
        ln
        for ln in lines
        if ('[🎤 AUDIO]:' in ln or '[🎥 VIDEO]:' in ln or '[🖼️ IMAGE]:' in ln or '[📄 DOCUMENT]:' in ln)
    ]

    head_budget = max_chars // 3
    tail_budget = max_chars // 3
    media_budget = max_chars - head_budget - tail_budget - 200

    head = conversation_text[:head_budget]
    tail = conversation_text[-tail_budget:]
    media_joined = '\n'.join(media_lines)
    if len(media_joined) > media_budget:
        media_joined = media_joined[:media_budget]

    return (
        "[CONVERSACIÓN COMPACTADA POR TAMAÑO]\n"
        f"Tamaño original: {len(conversation_text)} caracteres.\n"
        "\n[INICIO]\n"
        f"{head}\n"
        "\n[EVENTOS MULTIMEDIA]\n"
        f"{media_joined}\n"
        "\n[FINAL]\n"
        f"{tail}"
    )


def _fallback_report(interpretation: str, translated: str) -> str:
    return (
        "# Resumen de la Conversación\n\n"
        "## Participantes\n"
        "Identificados a partir del chat exportado (ver líneas de conversación).\n\n"
        "## Temas Principales\n"
        f"{interpretation}\n\n"
        "## Puntos Clave\n"
        "Se incluyen acuerdos, acciones y eventos multimedia relevantes en la traducción.\n\n"
        "## Tono y Contexto\n"
        "Conversación operativa con coordinación de tareas y seguimiento.\n\n"
        "## Conversación Traducida\n"
        f"{translated}"
    )


def _extract_media_lines(conversation_text: str) -> list[str]:
    media_markers = ('[🎤 AUDIO]:', '[🎥 VIDEO]:', '[🖼️ IMAGE]:', '[📄 DOCUMENT]:')
    return [ln for ln in conversation_text.splitlines() if any(m in ln for m in media_markers)]


def _strip_media_lines(text: str) -> str:
    media_markers = ('[🎤 AUDIO]:', '[🎥 VIDEO]:', '[🖼️ IMAGE]:', '[📄 DOCUMENT]:')
    kept = [ln for ln in text.splitlines() if not any(m in ln for m in media_markers)]
    return '\n'.join(kept)


def _parse_json_object(raw_text: str) -> dict | None:
    text = (raw_text or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.startswith('json'):
            text = text[4:].strip()
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def _translate_text_to_spanish(content: str, router) -> str:
    if not content.strip():
        return content

    prompt = (
        "Traduce al español el siguiente texto. "
        "No agregues explicaciones, solo devuelve la traducción.\n\n"
        f"TEXTO:\n{content}"
    )
    route = router.route_translation(content)
    try:
        raw = REMOTE.generate(route.host, route.model, prompt, timeout=route.timeout)
    except Exception:
        fallback = router.route_fallback("translation")
        raw = REMOTE.generate(fallback.host, fallback.model, prompt, timeout=fallback.timeout)

    translated = (raw.get('response') or '').strip()
    return translated or content


def _translate_media_lines_to_spanish(media_lines: list[str], router, chunk_size: int = 10) -> list[str]:
    if not media_lines:
        return media_lines

    translated_lines: list[str] = []
    for i in range(0, len(media_lines), chunk_size):
        chunk = media_lines[i:i + chunk_size]
        payload = []
        for ln in chunk:
            if ':' in ln:
                prefix, content = ln.split(':', 1)
                payload.append({'prefix': prefix + ':', 'content': content.strip()})
            else:
                payload.append({'prefix': ln, 'content': ''})

        prompt = (
            "Traduce al español el campo content de cada elemento sin cambiar el prefijo. "
            "Mantén nombres propios, números y montos. "
            "Devuelve SOLO JSON válido con la forma exacta {\"items\":[{\"prefix\":\"...\",\"content\":\"...\"}]}.\n\n"
            f"INPUT:\n{json.dumps({'items': payload}, ensure_ascii=False)}"
        )

        joined = '\n'.join(chunk)
        route = router.route_translation(joined)
        try:
            raw = REMOTE.generate(route.host, route.model, prompt, timeout=route.timeout)
        except Exception:
            fallback = router.route_fallback("translation")
            raw = REMOTE.generate(fallback.host, fallback.model, prompt, timeout=fallback.timeout)

        parsed = _parse_json_object(raw.get('response', ''))
        items = (parsed or {}).get('items') if isinstance(parsed, dict) else None

        if not isinstance(items, list) or len(items) != len(payload):
            for row in payload:
                content_es = _translate_text_to_spanish(row['content'], router)
                translated_lines.append(f"{row['prefix']} {content_es}".rstrip())
            continue

        rebuilt = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                rebuilt.append(chunk[idx])
                continue
            prefix = str(item.get('prefix', payload[idx]['prefix'])).strip()
            content = str(item.get('content', payload[idx]['content'])).strip()
            rebuilt.append(f"{prefix} {content}".rstrip())
        translated_lines.extend(rebuilt)

    return translated_lines


def _cleanup_stale_not_processed_lines(translated: str, conversation_text: str) -> str:
    """Quita líneas [FILE - not processed] obsoletas si ya existe resultado multimedia."""
    truly_unprocessed = set()
    for ln in conversation_text.splitlines():
        if '[FILE - not processed]:' not in ln:
            continue
        parts = ln.split(':', 1)
        if len(parts) == 2:
            truly_unprocessed.add(parts[1].strip())

    cleaned = []
    for ln in translated.splitlines():
        if '[FILE - not processed]:' not in ln:
            cleaned.append(ln)
            continue

        match = re.search(r"\[FILE - not processed\]:\s*(.+)$", ln)
        filename = match.group(1).strip() if match else ''
        if filename and filename in truly_unprocessed:
            cleaned.append(ln)

    return '\n'.join(cleaned)


def _ensure_media_in_translation(translated: str, conversation_text: str, router) -> str:
    media_lines = _extract_media_lines(conversation_text)
    if not media_lines:
        return _cleanup_stale_not_processed_lines(translated, conversation_text)

    translated = _cleanup_stale_not_processed_lines(translated, conversation_text)
    translated = _strip_media_lines(translated)

    media_lines_es = _translate_media_lines_to_spanish(media_lines, router)

    media_block = "\n".join(media_lines_es)
    return (
        f"{translated}\n\n"
        "[EVENTOS MULTIMEDIA EN ESPAÑOL]\n"
        f"{media_block}"
    )


def translate_conversation(conversation_text: str, router) -> str:
    llm_conversation = _compact_conversation_with_media(conversation_text)
    prompt = PROMPT_TRANSLATE.format(conversation=llm_conversation)
    route = router.route_translation(llm_conversation)
    try:
        raw = REMOTE.generate(route.host, route.model, prompt, timeout=route.timeout)
    except Exception:
        fallback = router.route_fallback("translation")
        raw = REMOTE.generate(fallback.host, fallback.model, prompt, timeout=fallback.timeout)
    response = raw.get('response', '').strip()
    if _looks_like_placeholder(response):
        tighter = _compact_conversation_with_media(conversation_text, max_chars=12000)
        retry_prompt = PROMPT_TRANSLATE.format(conversation=tighter)
        retry_raw = REMOTE.generate(route.host, route.model, retry_prompt, timeout=route.timeout)
        retried = retry_raw.get('response', '').strip()
        if retried:
            response = retried
    return response


def generate_final_report(interpretation: str, translated: str, router) -> str:
    interpretation_short = _compact_text(interpretation, max_chars=12000)
    translated_short = _compact_text(translated, max_chars=18000)
    prompt = PROMPT_FINAL.format(interpretation=interpretation_short, translated=translated_short)
    route = router.route_translation(translated_short)
    try:
        raw = REMOTE.generate(route.host, route.model, prompt, timeout=route.timeout)
    except Exception:
        fallback = router.route_fallback("translation")
        raw = REMOTE.generate(fallback.host, fallback.model, prompt, timeout=fallback.timeout)
    report = raw.get('response', '').strip()
    if _looks_like_placeholder(report):
        report = _fallback_report(interpretation, translated)
    return report


def translate(interpreted: dict, router) -> dict:
    translated = translate_conversation(interpreted['conversation_text'], router)
    translated = _ensure_media_in_translation(translated, interpreted['conversation_text'], router)
    final_report = generate_final_report(interpreted['interpretation'], translated, router)

    output_dir = CONFIG.PROJECT_DIR / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / 'conversation_es.md'
    md_path.write_text(final_report, encoding='utf-8')

    result = {
        'translated_conversation': translated,
        'interpretation': interpreted['interpretation'],
        'final_report': final_report,
    }
    json_path = output_dir / 'conversation_es.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'  Saved: {md_path}')
    print(f'  Saved: {json_path}')
    return result
