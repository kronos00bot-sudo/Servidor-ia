import importlib
import json


def _reload_config_module():
    module = importlib.import_module("skills.telegram.utils.config")
    return importlib.reload(module)


def test_config_loads_token_and_owner_from_openclaw_json(tmp_path, monkeypatch):
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    config_path = openclaw_dir / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {"telegram": {"botToken": "token-json"}},
                "commands": {"ownerAllowFrom": ["telegram:123456"]},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPENCLAW_CONFIG_PATH", raising=False)
    monkeypatch.delenv("OPENCLAW_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("OPENCLAW_TELEGRAM_OWNER_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_ID", raising=False)

    cfg = _reload_config_module()
    assert cfg.TelegramConfig.TELEGRAM_BOT_TOKEN == "token-json"
    assert cfg.TelegramConfig.TELEGRAM_ALLOWED_CHAT_ID == "123456"


def test_env_variables_override_openclaw_json(tmp_path, monkeypatch):
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()
    config_path = openclaw_dir / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {"telegram": {"botToken": "token-json"}},
                "commands": {"ownerAllowFrom": ["telegram:123456"]},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENCLAW_TELEGRAM_BOT_TOKEN", "token-env")
    monkeypatch.setenv("OPENCLAW_TELEGRAM_OWNER_ID", "999999")

    cfg = _reload_config_module()
    assert cfg.TelegramConfig.TELEGRAM_BOT_TOKEN == "token-env"
    assert cfg.TelegramConfig.TELEGRAM_ALLOWED_CHAT_ID == "999999"
