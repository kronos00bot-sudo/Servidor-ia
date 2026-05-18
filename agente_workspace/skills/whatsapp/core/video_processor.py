"""Video processing for WhatsApp skill."""

import json
import base64
import subprocess
from pathlib import Path
from skills.whatsapp.routing.remote_client import RemoteClient
from skills.whatsapp.utils.config import Config

CONFIG = Config()
REMOTE = RemoteClient()
AUDIO_DIR = CONFIG.PROJECT_DIR / 'media' / 'processed' / 'audio_wav'
FRAMES_DIR = CONFIG.PROJECT_DIR / 'media' / 'processed' / 'video_frames'
TRANSCR_DIR = CONFIG.PROJECT_DIR / 'data' / 'transcriptions'
for d in [AUDIO_DIR, FRAMES_DIR, TRANSCR_DIR]:
    d.mkdir(parents=True, exist_ok=True)

PROMPT_FRAME = "Describe brevemente este frame de video de una conversación de WhatsApp. Menciona solo lo más relevante (personas, objetos, texto visible y acción). Máximo 1-2 frases. Responde en español."


def extract_audio(video_path: Path) -> Path:
    wav_path = AUDIO_DIR / (video_path.stem + '_video.wav')
    if wav_path.exists():
        return wav_path
    cmd = [
        CONFIG.FFMPEG_BIN, '-y', '-i', str(video_path),
        '-ac', '1', '-ar', str(CONFIG.AUDIO_SAMPLE_RATE), '-sample_fmt', 's16',
        str(wav_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return wav_path


def extract_frames(video_path: Path, msg_id: int):
    frame_dir = FRAMES_DIR / f"{msg_id:04d}_{video_path.stem}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(frame_dir / 'frame_%04d.jpg')
    cmd = [
        CONFIG.FFMPEG_BIN, '-y', '-i', str(video_path),
        '-vf', f'fps=1/{CONFIG.VIDEO_FRAME_INTERVAL}', '-q:v', '3', pattern
    ]
    subprocess.run(cmd, capture_output=True)
    return sorted(frame_dir.glob('*.jpg'))


def transcribe_wav(wav_path: Path, router, message: dict) -> str:
    route = router.route_transcription(message)
    with open(wav_path, 'rb') as f:
        raw = REMOTE.transcribe(route.host, f, timeout=route.timeout)
    return raw.get('text', '').strip()


def describe_frame(frame_path: Path, router, message: dict) -> str:
    with open(frame_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    route = router.route_vision(message)
    raw = REMOTE.generate(
        route.host,
        route.model,
        PROMPT_FRAME,
        timeout=route.timeout,
        images=[image_data],
    )
    return raw.get('response', '').strip()


def process_video(filepath: str, msg_id: int, router, message: dict) -> dict:
    video_path = Path(filepath)
    result_path = TRANSCR_DIR / f"{msg_id:04d}_{video_path.stem}_video.json"
    if result_path.exists():
        with open(result_path, encoding='utf-8') as f:
            return json.load(f)
    if not video_path.exists():
        return {'id': msg_id, 'text': None, 'error': f'File not found: {filepath}'}
    try:
        wav_path = extract_audio(video_path)
        transcript = transcribe_wav(wav_path, router, message)
        frames = extract_frames(video_path, msg_id)
        frame_descriptions = []
        for frame in frames[:5]:
            desc = describe_frame(frame, router, message)
            frame_descriptions.append({'frame': frame.name, 'description': desc})
        text = '[Audio]: ' + transcript
        if frame_descriptions:
            text += ' [Visual]: ' + '; '.join(d['description'] for d in frame_descriptions)
        result = {
            'id': msg_id,
            'original': str(filepath),
            'transcript': transcript,
            'frame_descriptions': frame_descriptions,
            'text': text,
            'error': None
        }
    except Exception as e:
        result = {'id': msg_id, 'original': str(filepath), 'text': None, 'error': str(e)}
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def process_videos(messages: list, router) -> list:
    tasks = [m for m in messages if m['type'] == 'video' and m.get('filepath')]
    if not tasks:
        print('No videos to process.')
        return messages

    print(f'Processing {len(tasks)} videos...')
    for msg in tasks:
        print(f"[{msg['id']:03d}] {msg['sender']} - {msg['filename']}")
        result = process_video(msg['filepath'], msg['id'], router, msg)
        msg['result'] = result.get('text')
        msg['processed'] = True
        if result.get('error'):
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {msg['result'][:80]}...")
    return messages
