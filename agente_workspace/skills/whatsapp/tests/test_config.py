from skills.whatsapp.utils.config import Config


def test_config_machine_type_valid():
    assert Config.MACHINE_TYPE in {"um890", "dgx"}


def test_config_timeouts_present():
    required = {"whisper", "vision", "chat", "reasoning", "translation", "document"}
    assert required.issubset(set(Config.TIMEOUTS.keys()))
