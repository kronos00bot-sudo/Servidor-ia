from skills.whatsapp.core.config import Config
from skills.whatsapp.core.task_router import TaskRouter


def test_route_transcription():
    router = TaskRouter(Config())
    target = router.route_transcription({})
    assert target.key == 'dgx_whisper'
    assert target.timeout == Config.TIMEOUTS['whisper']


def test_route_vision():
    router = TaskRouter(Config())
    target = router.route_vision({})
    assert target.key == 'um890_gemma4'
    assert target.model == Config.VISION_MODEL


def test_route_chat():
    router = TaskRouter(Config())
    target = router.route_chat('Hola')
    assert target.key == 'um890_qwen35'
    assert target.model == Config.FAST_MODEL


def test_route_reasoning():
    router = TaskRouter(Config())
    assert router.route_reasoning('test', complexity=2).key == 'um890_qwen36'
    assert router.route_reasoning('test', complexity=7).key == 'um890_nemotron33'
    assert router.route_reasoning('test', complexity=9).key == 'dgx_nemotron_120b'


def test_route_translation():
    router = TaskRouter(Config())
    target = router.route_translation('hola')
    assert target.key == 'dgx_nemotron_120b'
    assert target.timeout == Config.TIMEOUTS['translation']
