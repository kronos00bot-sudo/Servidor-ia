#!/usr/bin/env python3
"""
transcriber.py — Transcribe audios y extrae audio de videos
Envia al DGX whisper-server para STT
"""

import os
import json
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_DIR      = Path(os.getenv("PROJECT_DIR"))
DGX_WHISPER_URL  = os.getenv("DGX_WHISPER_URL")
AUDIO_SAMPLE_RATE = os.getenv("AUDIO_SAMPLE_RATE", "16000")
FFMPEG_BIN       = os.getenv("FFMPEG_BIN", "ffmpeg")
PROCESSED_DIR    = PROJECT_DIR / "media" / "processed" / "audio_wav"
TRANSCR_DIR      = PROJECT_DIR / "data" / "transcriptions"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
TRANSCR_DIR.mkdir(parents=True, exist_ok=True)


def convert_to_wav(input_path: Path) -> Path:
    """Convierte cualquier audio/video a WAV mono 16kHz usando ffmpeg."""
    out_path = PROCESSED_DIR / (input_path.stem + ".wav")
    if out_path.exists():
        return out_path
    cmd = [
        FFMPEG_BIN, "-y", "-i", str(input_path),
        "-ac", "1",                     # mono
        "-ar", AUDIO_SAMPLE_RATE,       # 16000 Hz
        "-sample_fmt", "s16",
        str(out_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr[-300:]}")
    return out_path


def transcribe_wav(wav_path: Path) -> dict:
    """Envía WAV al DGX whisper-server y devuelve resultado."""
    with open(wav_path, "rb") as f:
        resp = requests.post(
            DGX_WHISPER_URL,
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"response_format": "json", "language": "auto"},
            timeout=120
        )
    resp.raise_for_status()
    return resp.json()


def transcribe_file(filepath: str, msg_id: int) -> dict:
    """Flujo completo: convierte + transcribe + guarda JSON."""
    input_path = Path(filepath)
    if not input_path.exists():
        return {"id": msg_id, "error": f"Archivo no encontrado: {filepath}", "text": None}

    result_path = TRANSCR_DIR / f"{msg_id:04d}_{input_path.stem}.json"
    if result_path.exists():
        with open(result_path) as f:
            return json.load(f)

    try:
        print(f"  Convirtiendo: {input_path.name}")
        wav_path = convert_to_wav(input_path)

        print(f"  Transcribiendo en DGX: {wav_path.name}")
        raw = transcribe_wav(wav_path)

        result = {
            "id":       msg_id,
            "original": str(filepath),
            "text":     raw.get("text", "").strip(),
            "language": raw.get("language", "unknown"),
            "error":    None
        }
    except Exception as e:
        result = {
            "id":       msg_id,
            "original": str(filepath),
            "text":     None,
            "language": None,
            "error":    str(e)
        }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def transcribe_messages(messages: list) -> list:
    """Procesa todos los mensajes de tipo audio o video."""
    results = []
    to_process = [m for m in messages if m["type"] in ("audio", "video") and m.get("filepath")]

    if not to_process:
        print("No hay audios o videos para transcribir.")
        return messages

    print(f"\nTranscribiendo {len(to_process)} archivos en el DGX...")
    for msg in to_process:
        print(f"[{msg['id']:03d}] {msg['sender']} — {msg['filename']}")
        result = transcribe_file(msg["filepath"], msg["id"])
        msg["result"]   = result.get("text")
        msg["processed"] = True
        if result.get("error"):
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {result['text'][:80]}...")
        results.append(result)

    return messages


if __name__ == "__main__":
    import sys
    parsed_path = PROJECT_DIR / "data" / "conversations" / "parsed.json"
    if not parsed_path.exists():
        print("Ejecuta primero parser.py")
        sys.exit(1)

    with open(parsed_path, encoding="utf-8") as f:
        messages = json.load(f)

    messages = transcribe_messages(messages)

    # Guardar mensajes actualizados
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    print("\nTranscripcion completada.")
