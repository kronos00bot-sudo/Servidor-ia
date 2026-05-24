from pathlib import Path

from skills.telegram.media import TelegramMediaClient, process_telegram_media


class FakeResponse:
    def __init__(self, payload=None, content=b"data"):
        self._payload = payload or {"ok": True, "result": {"file_path": "tmp/file.bin"}}
        self.content = content

    def json(self):
        return self._payload


class FakeHttp:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if "getFile" in url:
            return FakeResponse({"ok": True, "result": {"file_path": "media/file.mp3"}})
        return FakeResponse(content=b"binary")


def test_download_attachment_creates_file(tmp_path: Path):
    client = TelegramMediaClient(token="bot-token", http_client=FakeHttp())
    client.download_root = tmp_path
    result = client.download_attachment(
        {"raw_type": "audio", "file_id": "abc", "file_name": "note.mp3"},
        chat_id="123",
        msg_id=7,
    )
    assert result["ok"] is True
    assert Path(result["saved_path"]).exists()


def test_download_attachment_missing_file_id():
    client = TelegramMediaClient(token="bot-token", http_client=FakeHttp())
    result = client.download_attachment({"raw_type": "audio"}, chat_id="123", msg_id=7)
    assert result["ok"] is False


def test_process_telegram_media_video_uses_transcription(monkeypatch, tmp_path: Path):
    sample_video = tmp_path / "sample.mp4"
    sample_video.write_bytes(b"video")

    class FakeMediaClient:
        def download_attachment(self, message, chat_id, msg_id):
            return {
                "ok": True,
                "kind": "video",
                "saved_path": str(sample_video),
            }

    def fake_process_video_media(saved_path: Path, msg_id: int, router):
        assert str(saved_path).endswith("sample.mp4")
        assert msg_id == 42
        return {"id": msg_id, "text": "Transcripcion de audio:\ntexto\n\nResumen visual:\n- escena", "error": None}

    monkeypatch.setattr("skills.telegram.media._process_video_media", fake_process_video_media)
    result = process_telegram_media(
        {"chat_id": "123", "message_id": 42, "raw_type": "video", "file_id": "v1"},
        router=None,
        media_client=FakeMediaClient(),
    )

    assert result["ok"] is True
    assert result["kind"] == "video"
    assert "Resumen visual" in (result["text"] or "")
    assert result["error"] is None


def test_process_video_media_combines_audio_and_visual(monkeypatch, tmp_path: Path):
    sample_video = tmp_path / "clip.mp4"
    sample_video.write_bytes(b"video")

    def fake_transcribe_file(filepath: str, msg_id: int):
        return {"id": msg_id, "text": "audio text", "error": None}

    def fake_build_video_visual_summary(video_path: Path, router, remote, msg_id: int):
        return "- persona hablando\n- oficina"

    monkeypatch.setattr("skills.telegram.media.transcribe_file", fake_transcribe_file)
    monkeypatch.setattr("skills.telegram.media._build_video_visual_summary", fake_build_video_visual_summary)

    class DummyRouter:
        pass

    from skills.telegram.media import _process_video_media

    result = _process_video_media(sample_video, 55, router=DummyRouter())
    assert result["error"] is None
    assert "Transcripcion de audio" in (result["text"] or "")
    assert "Resumen visual" in (result["text"] or "")


def test_process_telegram_media_document_extracts_text(tmp_path: Path):
    sample_doc = tmp_path / "sample.pdf"
    sample_doc.write_text("hola documento", encoding="utf-8")

    class FakeMediaClient:
        def download_attachment(self, message, chat_id, msg_id):
            return {
                "ok": True,
                "kind": "document",
                "saved_path": str(sample_doc),
            }

    result = process_telegram_media(
        {
            "chat_id": "123",
            "message_id": 99,
            "raw_type": "document",
            "file_id": "d1",
            "file_name": "sample.txt",
            "mime_type": "text/plain",
        },
        router=None,
        media_client=FakeMediaClient(),
    )

    assert result["ok"] is True
    assert result["kind"] == "document"
    assert "hola documento" in (result["text"] or "")
    assert result["error"] is None


def test_process_telegram_media_document_fallback_summary(tmp_path: Path):
    sample_doc = tmp_path / "sample.bin"
    sample_doc.write_bytes(b"\x00\x01\x02\x03")

    class FakeMediaClient:
        def download_attachment(self, message, chat_id, msg_id):
            return {
                "ok": True,
                "kind": "document",
                "saved_path": str(sample_doc),
            }

    result = process_telegram_media(
        {
            "chat_id": "123",
            "message_id": 100,
            "raw_type": "document",
            "file_id": "d2",
            "file_name": "sample.bin",
            "mime_type": "application/octet-stream",
        },
        router=None,
        media_client=FakeMediaClient(),
    )

    assert result["ok"] is True
    assert result["kind"] == "document"
    assert "Se recibio un documento" in (result["text"] or "")
    assert result["error"] is None
