"""Audio transcription helpers for Telegram skill."""

import json
import os
import signal
import subprocess
from pathlib import Path

from skills.telegram.routing.remote_client import RemoteClient
from skills.telegram.utils.http_client import HttpClient
from skills.telegram.utils.config import TelegramConfig

# Para transcripción preferimos fallo rápido; reintentos largos bloquean polling.
REMOTE = RemoteClient(http_client=HttpClient(retries=1))

PROCESSED_DIR = TelegramConfig.PROJECT_DIR / "media" / "processed" / "audio_wav"
TRANSCR_DIR = TelegramConfig.PROJECT_DIR / "data" / "transcriptions"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
TRANSCR_DIR.mkdir(parents=True, exist_ok=True)


def _ffprobe_bin() -> str:
    ffmpeg_path = Path(TelegramConfig.FFMPEG_BIN)
    if ffmpeg_path.name.lower() == "ffmpeg":
        return str(ffmpeg_path.with_name("ffprobe"))
    return "ffprobe"


def _audio_duration_seconds(wav_path: Path) -> float:
    cmd = [
        _ffprobe_bin(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(wav_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return 0.0
    
    if result.returncode != 0:
        return 0.0
    try:
        return float((result.stdout or "").strip() or 0.0)
    except Exception:
        return 0.0


def _resolve_whisper_timeout(wav_path: Path, base_timeout: int) -> int:
    duration = _audio_duration_seconds(wav_path)
    if duration <= 0:
        return max(60, int(base_timeout))

    # En DGX, Whisper puede tardar ~4-5x la duracion del audio.
    # Para audio de 60s -> ~300s. Usamos 5x + 60s de margen.
    adaptive = int((duration * 5.0) + 60)
    return max(60, int(base_timeout), adaptive)


def convert_to_wav(input_path: Path) -> Path:
    """Convert audio file to WAV and enforce hard timeout safely."""
    out_path = PROCESSED_DIR / (input_path.stem + ".wav")
    if out_path.exists():
        return out_path

    cmd = [
        TelegramConfig.FFMPEG_BIN,
        "-y",
        "-loglevel",
        "quiet",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        str(TelegramConfig.AUDIO_SAMPLE_RATE),
        "-sample_fmt",
        "s16",
        str(out_path),
    ]

    timeout_seconds = 30
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            returncode = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Matar todo el grupo evita procesos hijo/zombies colgados.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
            raise RuntimeError(f"ffmpeg timeout converting {input_path.name} (>{timeout_seconds}s)")

        result = subprocess.CompletedProcess(cmd, returncode)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed with returncode {result.returncode}")
        return out_path
    except Exception as e:
        raise RuntimeError(f"ffmpeg error: {str(e)}")


def transcribe_wav(wav_path: Path) -> dict:
    timeout = _resolve_whisper_timeout(wav_path, TelegramConfig.TIMEOUTS["whisper"])
    with open(wav_path, "rb") as f:
        return REMOTE.transcribe(
            whisper_url=TelegramConfig.DGX_WHISPER_URL,
            file_handle=f,
            timeout=timeout,
        )


def transcribe_file(filepath: str, msg_id: int) -> dict:
    input_path = Path(filepath)
    if not input_path.exists():
        return {"id": msg_id, "error": f"File not found: {filepath}", "text": None}

    result_path = TRANSCR_DIR / f"{msg_id:04d}_{input_path.stem}.json"
    if result_path.exists():
        with open(result_path, encoding="utf-8") as f:
            return json.load(f)

    try:
        wav_path = convert_to_wav(input_path)
        raw = transcribe_wav(wav_path)
        result = {
            "id": msg_id,
            "original": str(filepath),
            "text": (raw.get("text") or "").strip(),
            "language": raw.get("language", "unknown"),
            "error": None,
        }
    except Exception as exc:
        result = {
            "id": msg_id,
            "original": str(filepath),
            "text": None,
            "language": None,
            "error": str(exc),
        }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result
