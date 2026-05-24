from pathlib import Path

from skills.telegram.state import TelegramState


def test_state_touch_and_persist(tmp_path: Path):
    state_path = tmp_path / "telegram_state.json"
    state = TelegramState(state_path=state_path)
    state.touch_chat("123", {"text": "hola", "has_media": True}, reply="respuesta")

    assert state_path.exists()
    assert state.get_chat_summary("123")["message_count"] == 1
    assert state.get_chat_summary("123")["media_count"] == 1
    assert state.get_chat_summary("123")["last_reply"] == "respuesta"

    state.set_last_update_id(42)
    reloaded = TelegramState(state_path=state_path)
    assert reloaded.get_last_update_id() == 42
