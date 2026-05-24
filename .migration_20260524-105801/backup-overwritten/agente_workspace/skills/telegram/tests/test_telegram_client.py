from skills.telegram.client import TelegramClient
from skills.telegram.utils.http_client import HttpClient


class FakeResponse:
    def json(self):
        return {"ok": True, "result": {"message_id": 1}}


class FakeHttp:
    def __init__(self):
        self.last = None

    def post(self, url, json=None, timeout=None, **kwargs):
        self.last = {"url": url, "json": json, "timeout": timeout, "kwargs": kwargs}
        return FakeResponse()


def test_telegram_client_send_text_payload(monkeypatch):
    client = TelegramClient(token="bot-token", http_client=FakeHttp())
    result = client.send_text("12345", "hola")
    assert result["ok"] is True
    assert client.http.last["url"] == "https://api.telegram.org/botbot-token/sendMessage"
    assert client.http.last["json"]["chat_id"] == "12345"
    assert client.http.last["json"]["text"] == "hola"


def test_telegram_client_missing_token():
    client = TelegramClient(token="")
    result = client.send_text("12345", "hola")
    assert result["ok"] is False


def test_http_client_sanitize_url_redacts_bot_token():
    url = "https://api.telegram.org/bot123456:ABCDEF/sendMessage?x=1"
    assert HttpClient.sanitize_url(url) == "https://api.telegram.org/bot<redacted>/sendMessage"
