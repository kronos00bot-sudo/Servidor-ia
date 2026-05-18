"""Transcribe audio and video using DGX whisper-server."""

import json
import subprocess
from pathlib import Path
from skills.whatsapp.routing.remote_client import RemoteClient
from skills.whatsapp.utils.http_client import HttpClient
from skills.whatsapp.utils.config import Config

CONFIG = Config()
# Para transcripción preferimos fallo rápido; los reintentos largos bloquean
# el poller de Telegram cuando Whisper remoto no está disponible.
REMOTE = RemoteClient(http_client=HttpClient(retries=1))

PROCESSED_DIR = CONFIG.PROJECT_DIR / 'media' / 'processed' / 'audio_wav'
TRANSCR_DIR = CONFIG.PROJECT_DIR / 'data' / 'transcriptions'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
TRANSCR_DIR.mkdir(parents=True, exist_ok=True)


def _ffprobe_bin() -> str:
    ffmpeg_path = Path(CONFIG.FFMPEG_BIN)
    name = ffmpeg_path.name.lower()
    if name == 'ffmpeg':
        return str(ffmpeg_path.with_name('ffprobe'))
    return 'ffprobe'


def _audio_duration_seconds(wav_path: Path) -> float:
    cmd = [
        _ffprobe_bin(),
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    try:
        return float((result.stdout or '').strip() or 0.0)
    except Exception:
        return 0.0


def _resolve_whisper_timeout(wav_path: Path, base_timeout: int) -> int:
    duration = _audio_duration_seconds(wav_path)
    if duration <= 0:
        return max(30, int(base_timeout))

    # Presupuesto de tiempo proporcional a la duración del audio.
    # Ejemplo: audio de 60s -> ~129s.
    # En DGX hemos observado transcripciones de ~60s tardando ~108s.
    adaptive = int((duration * 1.8) + 20)
    return max(30, int(base_timeout), adaptive)


def convert_to_wav(input_path: Path) -> Path:
    out_path = PROCESSED_DIR / (input_path.stem + '.wav')
    if out_path.exists():
        return out_path
    cmd = [
        CONFIG.FFMPEG_BIN, '-y', '-i', str(input_path),
        '-ac', '1',
        '-ar', str(CONFIG.AUDIO_SAMPLE_RATE),
        '-sample_fmt', 's16',
        str(out_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg error: {result.stderr[-300:]}')
    return out_path


def transcribe_wav(wav_path: Path) -> dict:
    timeout = _resolve_whisper_timeout(wav_path, CONFIG.TIMEOUTS['whisper'])
    with open(wav_path, 'rb') as f:
        return REMOTE.transcribe(
            whisper_url=CONFIG.DGX_WHISPER_URL,
            file_handle=f,
            timeout=timeout,
        )


def transcribe_file(filepath: str, msg_id: int) -> dict:
    input_path = Path(filepath)
    if not input_path.exists():
        return {"id": msg_id, "error": f"File not found: {filepath}", "text": None}

    result_path = TRANSCR_DIR / f"{msg_id:04d}_{input_path.stem}.json"
    if result_path.exists():
        with open(result_path, encoding='utf-8') as f:
            return json.load(f)

    try:
        wav_path = convert_to_wav(input_path)
        raw = transcribe_wav(wav_path)
        result = {
            'id': msg_id,
            'original': str(filepath),
            'text': raw.get('text', '').strip(),
            'language': raw.get('language', 'unknown'),
            'error': None
        }
    except Exception as e:
        result = {
            'id': msg_id,
            'original': str(filepath),
            'text': None,
            'language': None,
            'error': str(e)
        }

    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def transcribe_messages(messages: list, router) -> list:
    tasks = [m for m in messages if m['type'] in ('audio', 'video') and m.get('filepath')]
    if not tasks:
        print('No audio or video files to transcribe.')
        return messages

    print(f'\nTranscribing {len(tasks)} audio/video files via DGX whisper...')
    for msg in tasks:
        print(f"[{msg['id']:03d}] {msg['sender']} - {msg['filename']}")
        route = router.route_transcription(msg)
        try:
            wav_path = convert_to_wav(Path(msg['filepath']))
            timeout = _resolve_whisper_timeout(wav_path, route.timeout)
            with open(wav_path, 'rb') as f:
                raw = REMOTE.transcribe(route.host, f, timeout=timeout)
            result = {
                'id': msg['id'],
                'original': str(msg['filepath']),
                'text': raw.get('text', '').strip(),
                'language': raw.get('language', 'unknown'),
                'error': None,
            }
        except Exception as primary_error:
            fallback = router.route_fallback("transcription")
            result = {
                'id': msg['id'],
                'original': str(msg['filepath']),
                'text': None,
                'language': None,
                'error': f"{primary_error} | fallback={fallback.key}",
            }

        result_path = TRANSCR_DIR / f"{msg['id']:04d}_{Path(msg['filepath']).stem}.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        msg['result'] = result.get('text')
        msg['processed'] = True
        if result.get('error'):
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {result['text'][:80]}...")
    return messages
