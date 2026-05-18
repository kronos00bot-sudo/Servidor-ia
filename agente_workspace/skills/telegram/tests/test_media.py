from pathlib import Path

from skills.telegram.media import TelegramMediaClient


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
