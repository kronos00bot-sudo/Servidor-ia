"""Tests para core/image_processor.py — visión local y fallback DGX."""

import json
import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from skills.whatsapp.core.image_processor import describe_image, process_images


def _fake_router(local_key="um890_gemma4", fallback_key="dgx_gemma4_26b"):
    router = MagicMock()
    local_route = MagicMock()
    local_route.key = local_key
    local_route.host = "http://127.0.0.1:11434/api/generate"
    local_route.model = "gemma4-es:latest"
    local_route.timeout = 10

    fallback_route = MagicMock()
    fallback_route.key = fallback_key
    fallback_route.host = "http://100.64.129.87:11434/api/generate"
    fallback_route.model = "gemma4:26b"
    fallback_route.timeout = 10

    router.route_vision.return_value = local_route
    router.route_fallback.return_value = fallback_route
    return router


def _tiny_jpg(path: Path) -> Path:
    """Crea un JPEG mínimo válido en la ruta dada."""
    # JPEG SOI + EOI mínimo
    path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xD9]))
    return path


# ── describe_image: happy path local ─────────────────────────────────────────

def test_describe_image_ok_local(tmp_path):
    img = _tiny_jpg(tmp_path / "test.jpg")
    router = _fake_router()

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        mock_remote.generate.return_value = {"response": "A small room with white walls."}
        result = describe_image(img, 1, router=router)

    assert result["text"] == "A small room with white walls."
    assert result["error"] is None
    assert result["route"] == "um890_gemma4"
    # Solo se llamó una vez (no fallback)
    mock_remote.generate.assert_called_once()


# ── describe_image: fallback a DGX cuando local falla ────────────────────────

def test_describe_image_fallback_to_dgx(tmp_path):
    img = _tiny_jpg(tmp_path / "test.jpg")
    router = _fake_router()

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        # Primera llamada (local) lanza timeout, segunda (DGX) tiene éxito
        mock_remote.generate.side_effect = [
            TimeoutError("local timeout"),
            {"response": "A bedroom with two beds."},
        ]
        result = describe_image(img, 2, router=router)

    assert result["text"] == "A bedroom with two beds."
    assert result["error"] is None
    assert result["route"] == "dgx_gemma4_26b"
    assert mock_remote.generate.call_count == 2
    router.route_fallback.assert_called_once_with("vision")


def test_describe_image_empty_local_output_fallback_to_dgx(tmp_path):
    img = _tiny_jpg(tmp_path / "test.jpg")
    router = _fake_router()

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        # Primera llamada responde vacío; debe activar fallback y tomar salida DGX.
        mock_remote.generate.side_effect = [
            {"response": "   "},
            {"response": "DGX fallback description."},
        ]
        result = describe_image(img, 22, router=router)

    assert result["text"] == "DGX fallback description."
    assert result["error"] is None
    assert result["route"] == "dgx_gemma4_26b"
    assert mock_remote.generate.call_count == 2
    router.route_fallback.assert_called_once_with("vision")


# ── describe_image: ambos fallan → error registrado ──────────────────────────

def test_describe_image_both_fail(tmp_path):
    img = _tiny_jpg(tmp_path / "test.jpg")
    router = _fake_router()

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        mock_remote.generate.side_effect = Exception("red error")
        result = describe_image(img, 3, router=router)

    assert result["text"] is None
    assert result["error"] is not None


# ── describe_image: caché exitoso evita re-llamada ───────────────────────────

def test_describe_image_uses_cache(tmp_path):
    img = _tiny_jpg(tmp_path / "test.jpg")
    router = _fake_router()

    cached = {"id": 4, "text": "Cached description.", "error": None, "route": "um890_gemma4"}
    cache_file = tmp_path / "0004_test.json"
    cache_file.write_text(json.dumps(cached), encoding="utf-8")

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        result = describe_image(img, 4, router=router)

    assert result["text"] == "Cached description."
    mock_remote.generate.assert_not_called()


# ── describe_image: caché con error NO bloquea reintento ─────────────────────

def test_describe_image_error_cache_retried(tmp_path):
    img = _tiny_jpg(tmp_path / "test.jpg")
    router = _fake_router()

    bad_cache = {"id": 5, "text": None, "error": "previous timeout", "route": None}
    cache_file = tmp_path / "0005_test.json"
    cache_file.write_text(json.dumps(bad_cache), encoding="utf-8")

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        mock_remote.generate.return_value = {"response": "Retry succeeded."}
        result = describe_image(img, 5, router=router)

    assert result["text"] == "Retry succeeded."
    mock_remote.generate.assert_called_once()


# ── describe_image: formato no soportado ─────────────────────────────────────

def test_describe_image_unsupported_format(tmp_path):
    img = tmp_path / "file.bmp_not_real.xyz"
    img.write_bytes(b"fake")
    router = _fake_router()

    with patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        result = describe_image(img, 6, router=router)

    assert result["text"] is None
    assert "Unsupported" in result["error"]


# ── process_images: integración con lista de mensajes ────────────────────────

def test_process_images_marks_processed(tmp_path):
    img = _tiny_jpg(tmp_path / "photo.jpg")
    router = _fake_router()

    messages = [
        {"id": 10, "type": "image", "sender": "Alice", "filename": "photo.jpg",
         "filepath": str(img), "processed": False, "result": None},
        {"id": 11, "type": "text", "sender": "Alice", "text": "hola",
         "processed": False, "result": None},
    ]

    with patch("skills.whatsapp.core.image_processor.REMOTE") as mock_remote, \
         patch("skills.whatsapp.core.image_processor.DESCR_DIR", tmp_path):
        mock_remote.generate.return_value = {"response": "A photo of a room."}
        result = process_images(messages, router)

    img_msg = next(m for m in result if m["id"] == 10)
    txt_msg = next(m for m in result if m["id"] == 11)
    assert img_msg["processed"] is True
    assert img_msg["result"] == "A photo of a room."
    assert not txt_msg.get("processed")  # texto no se toca
