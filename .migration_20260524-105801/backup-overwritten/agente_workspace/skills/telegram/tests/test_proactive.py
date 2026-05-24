from datetime import datetime, timedelta, timezone

from skills.telegram.proactive import TelegramProactiveEngine
from skills.telegram.state import TelegramState


class FakeClient:
    def __init__(self):
        self.calls = []

    def send_text(self, chat_id, text):
        self.calls.append((chat_id, text))
        return {"ok": True, "chat_id": chat_id, "text": text}


def test_summary_message_contains_counts(tmp_path):
    state = TelegramState(state_path=tmp_path / "state.json")
    state.touch_chat("123", {"text": "hola", "has_media": True}, reply="respuesta")
    engine = TelegramProactiveEngine(state=state, tg_client=FakeClient())
    message = engine.build_summary_message("123", state.get_chat_summary("123"))
    assert "Mensajes procesados: 1" in message
    assert "Elementos multimedia: 1" in message


def test_proactive_cycle_sends_summary_for_inactive_chat(tmp_path):
    state = TelegramState(state_path=tmp_path / "state.json")
    state.touch_chat("123", {"text": "hola", "has_media": False}, reply="respuesta")
    state.data["chats"]["123"]["last_seen"] = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    state.save()
    client = FakeClient()
    engine = TelegramProactiveEngine(state=state, tg_client=client)
    sent = engine.run_once()
    assert len(sent) == 1
    assert client.calls[0][0] == "123"
