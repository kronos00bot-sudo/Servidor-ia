import pytest

from skills.telegram.core import LAST_MESSAGE_AT, build_reply, extract_update_message
from skills.telegram.service import process_update
from skills.telegram.state import TelegramState
from skills.telegram.utils.config import TelegramConfig
from skills.telegram.utils.exceptions import ConfigError, WebhookError
from skills.telegram.webhook.endpoint import create_app


SECRET_HEADER = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_ALLOWED_CHAT_ID", "")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_RATE_LIMIT_SECONDS", 0)
    monkeypatch.setattr(TelegramConfig, "PROJECT_DIR", tmp_path)


class FakeRouter:
    def route_chat(self, prompt):
        return type("Route", (), {"host": "http://local", "model": "fast", "timeout": 1})()

    def route_reasoning(self, prompt, complexity=0):
        return type("Route", (), {"host": "http://local", "model": "reason", "timeout": 1})()

    def route_fallback(self, task_type):
        return type("Route", (), {"host": "http://fallback", "model": "fast", "timeout": 1})()


class FakeRemote:
    def generate(self, *args, **kwargs):
        return {"response": "respuesta de prueba"}


class FakeClient:
    def __init__(self):
        self.calls = []

    def send_text(self, chat_id, text):
        self.calls.append((chat_id, text))
        return {"ok": True, "chat_id": chat_id, "text": text}


def test_extract_update_message_text():
    payload = {
        "message": {
            "message_id": 7,
            "chat": {"id": 12345},
            "from": {"first_name": "Ana"},
            "text": "hola",
        }
    }
    message = extract_update_message(payload)
    assert message["chat_id"] == "12345"
    assert message["type"] == "text"
    assert message["text"] == "hola"


def test_build_reply_text_uses_core():
    reply = build_reply({"type": "text", "text": "hola"}, FakeRouter(), FakeRemote())
    assert reply == "respuesta de prueba"


def test_build_reply_commands():
    assert build_reply({"type": "text", "text": "/start", "command": "start"}, FakeRouter(), FakeRemote()).startswith("Hola")
    assert "/help" in build_reply({"type": "text", "text": "/help", "command": "help"}, FakeRouter(), FakeRemote())


def test_build_reply_summary_uses_state(tmp_path):
    state = TelegramState(state_path=tmp_path / "state.json")
    state.touch_chat("12345", {"text": "hola", "has_media": True}, reply="respuesta")
    reply = build_reply({"type": "text", "text": "/summary", "command": "summary", "chat_id": "12345"}, FakeRouter(), FakeRemote(), state=state)
    assert "Resumen del chat" in reply
    assert "Mensajes procesados: 1" in reply


def test_webhook_flow_text_message(monkeypatch):
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()

    payload = {
        "message": {
            "message_id": 7,
            "chat": {"id": 12345},
            "from": {"first_name": "Ana"},
            "text": "hola",
        }
    }

    resp = client.post("/telegram/webhook", json=payload, headers=SECRET_HEADER)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["reply"] == "respuesta de prueba"
    assert body["outbound"]["ok"] is True
    assert body["outbound"]["chat_id"] == "12345"


def test_process_update_ignores_non_text_media():
    def fake_process_telegram_media(*args, **kwargs):
        return {"ok": False, "error": "skip"}

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr("skills.telegram.service.process_telegram_media", fake_process_telegram_media)
    result = process_update(
        {"message": {"chat": {"id": 12345}, "from": {"first_name": "Ana"}, "photo": [{"file_id": "x"}] }},
        router=FakeRouter(),
        remote=FakeRemote(),
        tg_client=FakeClient(),
        allowed_chat_id="",
        min_interval=0,
    )
    monkeypatch.undo()
    assert result["ok"] is True


def test_process_update_media_enriches_text():
    LAST_MESSAGE_AT.clear()

    def fake_process_telegram_media(*args, **kwargs):
        return {"ok": True, "kind": "photo", "text": "Imagen con una mesa y una ventana", "error": None}

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr("skills.telegram.service.process_telegram_media", fake_process_telegram_media)
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()
    payload = {
        "message": {
            "message_id": 8,
            "chat": {"id": 54321},
            "from": {"first_name": "Ana"},
            "photo": [{"file_id": "x"}],
        }
    }
    resp = client.post("/telegram/webhook", json=payload, headers=SECRET_HEADER)
    monkeypatch.undo()
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["reply"] == "respuesta de prueba"


def test_process_update_media_failure_returns_user_feedback():
    LAST_MESSAGE_AT.clear()

    def fake_process_telegram_media(*args, **kwargs):
        return {"ok": False, "kind": "voice", "text": None, "error": "ffmpeg error"}

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr("skills.telegram.service.process_telegram_media", fake_process_telegram_media)
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()
    payload = {
        "message": {
            "message_id": 9,
            "chat": {"id": 12345},
            "from": {"first_name": "Ana"},
            "voice": {"file_id": "voice_1", "mime_type": "audio/ogg"},
        }
    }
    resp = client.post("/telegram/webhook", json=payload, headers=SECRET_HEADER)
    monkeypatch.undo()
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "fallo el procesamiento multimedia" in body["reply"]


def test_group_message_is_queued_for_approval(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "-777")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")

    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()
    payload = {
        "message": {
            "message_id": 10,
            "chat": {"id": -777, "type": "group", "title": "Equipo"},
            "from": {"id": 111, "first_name": "Luis"},
            "text": "Necesitamos actualizar el reporte",
        }
    }
    resp = client.post("/telegram/webhook", json=payload, headers=SECRET_HEADER)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["queued_for_approval"] is True
    assert body["approval_id"].isdigit()
    assert body["outbound"]["ok"] is True
    assert body["outbound"]["chat_id"] == "12345"


def test_approve_command_sends_english_reply_to_group(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "-777")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")
    tg_client = FakeClient()
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=tg_client, validate_config=False)
    client = app.test_client()

    group_payload = {
        "message": {
            "message_id": 11,
            "chat": {"id": -777, "type": "group", "title": "Equipo"},
            "from": {"id": 111, "first_name": "Luis"},
            "text": "Can you share the delivery estimate?",
        }
    }
    queue_resp = client.post("/telegram/webhook", json=group_payload, headers=SECRET_HEADER)
    assert queue_resp.status_code == 200
    queue_body = queue_resp.get_json()
    approval_id = queue_body["approval_id"]

    approve_payload = {
        "message": {
            "message_id": 12,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "text": f"/approve {approval_id}",
        }
    }
    approve_resp = client.post("/telegram/webhook", json=approve_payload, headers=SECRET_HEADER)
    assert approve_resp.status_code == 200
    approve_body = approve_resp.get_json()
    assert approve_body["ok"] is True
    assert "aprobada" in approve_body["reply"]
    sent_to_group = [call for call in tg_client.calls if call[0] == "-777"]
    assert len(sent_to_group) == 1


def test_spanish_approval_commands_are_accepted(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "-777")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")
    tg_client = FakeClient()
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=tg_client, validate_config=False)
    client = app.test_client()

    group_payload = {
        "message": {
            "message_id": 15,
            "chat": {"id": -777, "type": "group", "title": "Equipo"},
            "from": {"id": 111, "first_name": "Luis"},
            "text": "Can you share the delivery estimate?",
        }
    }
    queue_resp = client.post("/telegram/webhook", json=group_payload, headers=SECRET_HEADER)
    assert queue_resp.status_code == 200
    approval_id = queue_resp.get_json()["approval_id"]

    approve_payload = {
        "message": {
            "message_id": 16,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "text": f"/aprobar {approval_id}",
        }
    }
    approve_resp = client.post("/telegram/webhook", json=approve_payload, headers=SECRET_HEADER)
    assert approve_resp.status_code == 200
    approve_body = approve_resp.get_json()
    assert approve_body["ok"] is True
    assert "aprobada" in approve_body["reply"]


def test_spanish_approval_note_is_translated_to_english(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "-777")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")

    class NoteAwareRemote(FakeRemote):
        def generate(self, *args, **kwargs):
            prompt = kwargs.get("prompt", "")
            if "Translate this Spanish approval note into natural English" in prompt:
                return {"response": "Please keep the delivery estimate updated."}
            return {"response": "respuesta de prueba"}

    tg_client = FakeClient()
    app = create_app(router=FakeRouter(), remote=NoteAwareRemote(), tg_client=tg_client, validate_config=False)
    client = app.test_client()

    group_payload = {
        "message": {
            "message_id": 17,
            "chat": {"id": -777, "type": "group", "title": "Equipo"},
            "from": {"id": 111, "first_name": "Luis"},
            "text": "Can you share the delivery estimate?",
        }
    }
    queue_resp = client.post("/telegram/webhook", json=group_payload, headers=SECRET_HEADER)
    approval_id = queue_resp.get_json()["approval_id"]

    approve_payload = {
        "message": {
            "message_id": 18,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "text": f"/aprobar {approval_id} Por favor mantén actualizado el estimado.",
        }
    }
    approve_resp = client.post("/telegram/webhook", json=approve_payload, headers=SECRET_HEADER)
    assert approve_resp.status_code == 200
    sent_to_group = [call for call in tg_client.calls if call[0] == "-777"]
    assert sent_to_group[-1][1] == "Please keep the delivery estimate updated."


def test_reject_command_closes_pending_without_sending_to_source(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "-777")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")
    tg_client = FakeClient()
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=tg_client, validate_config=False)
    client = app.test_client()

    group_payload = {
        "message": {
            "message_id": 19,
            "chat": {"id": -777, "type": "group", "title": "Equipo"},
            "from": {"id": 111, "first_name": "Luis"},
            "text": "Please send the latest status",
        }
    }
    queue_resp = client.post("/telegram/webhook", json=group_payload, headers=SECRET_HEADER)
    assert queue_resp.status_code == 200
    approval_id = queue_resp.get_json()["approval_id"]

    reject_payload = {
        "message": {
            "message_id": 20,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "text": f"/rechazar {approval_id} No aplica ahora",
        }
    }
    reject_resp = client.post("/telegram/webhook", json=reject_payload, headers=SECRET_HEADER)
    assert reject_resp.status_code == 200
    reject_body = reject_resp.get_json()
    assert reject_body["ok"] is True
    assert "rechazada" in reject_body["reply"]

    sent_to_group = [call for call in tg_client.calls if call[0] == "-777"]
    assert len(sent_to_group) == 0

    reject_again_resp = client.post("/telegram/webhook", json=reject_payload, headers=SECRET_HEADER)
    assert reject_again_resp.status_code == 200
    assert "ya fue rechazada" in reject_again_resp.get_json()["reply"]


def test_cannot_approve_after_reject(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "-777")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")
    tg_client = FakeClient()
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=tg_client, validate_config=False)
    client = app.test_client()

    group_payload = {
        "message": {
            "message_id": 21,
            "chat": {"id": -777, "type": "group", "title": "Equipo"},
            "from": {"id": 111, "first_name": "Luis"},
            "text": "Need your approval",
        }
    }
    queue_resp = client.post("/telegram/webhook", json=group_payload, headers=SECRET_HEADER)
    assert queue_resp.status_code == 200
    approval_id = queue_resp.get_json()["approval_id"]

    reject_payload = {
        "message": {
            "message_id": 22,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "text": f"/rechazar {approval_id} no procede",
        }
    }
    reject_resp = client.post("/telegram/webhook", json=reject_payload, headers=SECRET_HEADER)
    assert reject_resp.status_code == 200
    assert "rechazada" in reject_resp.get_json()["reply"]

    approve_after_reject_payload = {
        "message": {
            "message_id": 23,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "text": f"/aprobar {approval_id}",
        }
    }
    approve_after_reject_resp = client.post("/telegram/webhook", json=approve_after_reject_payload, headers=SECRET_HEADER)
    assert approve_after_reject_resp.status_code == 200
    assert "ya fue rechazada" in approve_after_reject_resp.get_json()["reply"]

    sent_to_group = [call for call in tg_client.calls if call[0] == "-777"]
    assert len(sent_to_group) == 0


def test_group_message_not_monitored_when_config_missing(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_ALLOWED_CHAT_ID", "12345")

    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()
    payload = {
        "message": {
            "message_id": 13,
            "chat": {"id": -888, "type": "supergroup", "title": "Ops"},
            "from": {"id": 222, "first_name": "Marta"},
            "text": "Please provide the latest deployment status",
        }
    }
    resp = client.post("/telegram/webhook", json=payload, headers=SECRET_HEADER)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body.get("ignored") == "Chat not allowed"


def test_private_chat_can_queue_for_approval_when_same_control_chat(monkeypatch):
    LAST_MESSAGE_AT.clear()
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_MONITORED_CHAT_ID", "")
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_APPROVAL_CHAT_ID", "12345")

    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()
    payload = {
        "message": {
            "message_id": 14,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 999, "first_name": "Owner"},
            "voice": {"file_id": "voice_1", "mime_type": "audio/ogg"},
        }
    }

    def fake_process_telegram_media(*args, **kwargs):
        return {"ok": True, "kind": "voice", "text": "hello from audio", "error": None}

    mp = __import__("pytest").MonkeyPatch()
    mp.setattr("skills.telegram.service.process_telegram_media", fake_process_telegram_media)
    resp = client.post("/telegram/webhook", json=payload, headers=SECRET_HEADER)
    mp.undo()
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["queued_for_approval"] is True


def test_webhook_rejects_missing_secret_header():
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()
    resp = client.post("/telegram/webhook", json={"message": {"message_id": 1}})
    assert resp.status_code == 403


def test_create_app_requires_secret_when_validating(monkeypatch):
    monkeypatch.setattr(TelegramConfig, "TELEGRAM_WEBHOOK_SECRET", "")
    with pytest.raises(ConfigError):
        create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=True)


def test_webhook_returns_generic_bad_request(monkeypatch):
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()

    def bad_payload(_raw):
        raise WebhookError("token=123 hidden")

    monkeypatch.setattr("skills.telegram.webhook.endpoint._extract_payload", bad_payload)
    resp = client.post("/telegram/webhook", data=b"{}", headers=SECRET_HEADER)
    assert resp.status_code == 400
    assert resp.get_json() == {"ok": False, "error": "Invalid request"}


def test_webhook_returns_generic_internal_error(monkeypatch):
    app = create_app(router=FakeRouter(), remote=FakeRemote(), tg_client=FakeClient(), validate_config=False)
    client = app.test_client()

    def boom(*args, **kwargs):
        raise RuntimeError("https://api.telegram.org/bot123456:ABCDEF/sendMessage failed")

    monkeypatch.setattr("skills.telegram.webhook.endpoint.process_update", boom)
    resp = client.post("/telegram/webhook", json={"message": {"message_id": 1}}, headers=SECRET_HEADER)
    assert resp.status_code == 500
    assert resp.get_json() == {"ok": False, "error": "Internal server error"}
