"""Tests para core/parser.py — formato de export WhatsApp en español."""

import json
import tempfile
from pathlib import Path

from skills.whatsapp.core.parser import parse_chat, load_parsed, save_parsed, classify_message


# ── Fixtures de líneas reales del export español ─────────────────────────────

CHAT_SAMPLE = """\
20/06/24, 9:05 - Mariana: Hola buenos días!
21/06/24, 10:30 - Kashmir: Buenos días, ya revisé la unidad.
22/06/24, 11:00 - Mariana: Kashmir - PTT-20240622-WA0001.opus (archivo adjunto)
22/06/24, 11:05 - Kashmir: 📷 Kashmir - IMG-20240622-WA0002.jpg (archivo adjunto)
22/06/24, 11:10 - Mariana: <Multimedia omitido>
22/06/24, 11:15 - Kashmir: Kashmir - DOC-20240622-WA0003.pdf (archivo adjunto)
22/06/24, 11:20 - Mariana: Mensaje en
varias líneas
continúa aquí.
22/06/24, 11:25 - Sistema: Los mensajes y llamadas están cifrados.
"""


def _write_chat(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


# ── Tests de parseo ────────────────────────────────────────────────────────────

def test_parse_text_messages():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    texts = [m for m in msgs if m["type"] == "text"]
    assert any(m["sender"] == "Mariana" and "Hola" in m["text"] for m in texts)
    assert any(m["sender"] == "Kashmir" and "revisé" in m["text"] for m in texts)


def test_parse_audio_message():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    audios = [m for m in msgs if m["type"] == "audio"]
    assert len(audios) == 1
    assert audios[0]["filename"].endswith(".opus")
    assert audios[0]["sender"] == "Mariana"


def test_parse_image_message():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    images = [m for m in msgs if m["type"] == "image"]
    assert len(images) == 1
    assert images[0]["filename"].endswith(".jpg")


def test_parse_document_message():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    docs = [m for m in msgs if m["type"] == "document"]
    assert len(docs) == 1
    assert docs[0]["filename"].endswith(".pdf")


def test_parse_omitted():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    omitted = [m for m in msgs if m["type"] == "omitted"]
    assert len(omitted) == 1


def test_parse_multiline_message():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    multiline = [m for m in msgs if "varias líneas" in (m.get("text") or "")]
    assert len(multiline) == 1
    assert "continúa aquí" in multiline[0]["text"]


def test_parse_system_message_no_sender():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    # Los mensajes de sistema no deben aparecer como mensajes de texto normales
    # o deben tener sender vacío / None
    system_msgs = [m for m in msgs if "cifrados" in (m.get("text") or "")]
    if system_msgs:
        assert system_msgs[0]["sender"] in (None, "", "Sistema")


def test_parse_ids_sequential():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    ids = [m["id"] for m in msgs]
    assert ids == list(range(len(msgs)))


def test_parse_date_time_fields():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    for m in msgs:
        assert "date" in m
        assert "time" in m


# ── Tests de classify_message ─────────────────────────────────────────────────

def test_classify_opus():
    t, f = classify_message("Kashmir - PTT-20240622-WA0001.opus (archivo adjunto)")
    assert t == "audio"
    assert f is not None and f.endswith(".opus")


def test_classify_jpg():
    t, f = classify_message("Kashmir - IMG-20240622-WA0002.jpg (archivo adjunto)")
    assert t == "image"


def test_classify_pdf():
    t, f = classify_message("Kashmir - DOC-20240622-WA0003.pdf (archivo adjunto)")
    assert t == "document"


def test_classify_omitted_es():
    t, _ = classify_message("<Multimedia omitido>")
    assert t == "omitted"


def test_classify_omitted_en():
    t, _ = classify_message("<Media omitted>")
    assert t == "omitted"


def test_classify_plain_text():
    t, f = classify_message("Hola, ¿cómo estás?")
    assert t == "text"
    assert f is None


# ── Tests de save/load parsed ─────────────────────────────────────────────────

def test_save_load_roundtrip():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "data" / "conversations" / "parsed.json"
        save_parsed(msgs, out)
        assert out.exists()
        loaded = load_parsed(out)
        assert len(loaded) == len(msgs)
        assert loaded[0]["id"] == msgs[0]["id"]
        assert loaded[0]["type"] == msgs[0]["type"]


def test_load_preserves_processed_field():
    path = _write_chat(CHAT_SAMPLE)
    msgs = parse_chat(path)
    msgs[0]["processed"] = True
    msgs[0]["result"] = "transcripción de prueba"

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "parsed.json"
        save_parsed(msgs, out)
        loaded = load_parsed(out)
        assert loaded[0].get("processed") is True
        assert loaded[0].get("result") == "transcripción de prueba"
