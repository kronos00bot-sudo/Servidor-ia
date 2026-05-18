#!/usr/bin/env python3
import os, json, base64, subprocess, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

PROJECT_DIR       = Path(os.getenv("PROJECT_DIR"))
DGX_WHISPER_URL   = os.getenv("DGX_WHISPER_URL")
LOCAL_OLLAMA_URL  = os.getenv("LOCAL_OLLAMA_URL", "http://127.0.0.1:11434")
VISION_MODEL      = os.getenv("VISION_MODEL", "gemma4-es")
FFMPEG_BIN        = os.getenv("FFMPEG_BIN", "ffmpeg")
AUDIO_SAMPLE_RATE = os.getenv("AUDIO_SAMPLE_RATE", "16000")
FRAME_INTERVAL    = int(os.getenv("VIDEO_FRAME_INTERVAL", "30"))

AUDIO_DIR   = PROJECT_DIR / "media" / "processed" / "audio_wav"
FRAMES_DIR  = PROJECT_DIR / "media" / "processed" / "video_frames"
TRANSCR_DIR = PROJECT_DIR / "data" / "transcriptions"
for d in [AUDIO_DIR, FRAMES_DIR, TRANSCR_DIR]:
    d.mkdir(parents=True, exist_ok=True)

PROMPT_FRAME = "Describe this video frame from a WhatsApp conversation. What do you see? People, objects, text, context, action? Be concise. Answer in English."

def extract_audio(video_path):
    wav_path = AUDIO_DIR / (video_path.stem + "_video.wav")
    if wav_path.exists():
        return wav_path
    cmd = [FFMPEG_BIN, "-y", "-i", str(video_path),
           "-ac", "1", "-ar", AUDIO_SAMPLE_RATE, "-sample_fmt", "s16", str(wav_path)]
    subprocess.run(cmd, capture_output=True, check=True)
    return wav_path

def extract_frames(video_path, msg_id):
    frame_dir = FRAMES_DIR / (str(msg_id).zfill(4) + "_" + video_path.stem)
    frame_dir.mkdir(exist_ok=True)
    pattern = str(frame_dir / "frame_%04d.jpg")
    cmd = [FFMPEG_BIN, "-y", "-i", str(video_path),
           "-vf", "fps=1/" + str(FRAME_INTERVAL), "-q:v", "3", pattern]
    subprocess.run(cmd, capture_output=True)
    return sorted(frame_dir.glob("*.jpg"))

def transcribe_wav(wav_path):
    with open(wav_path, "rb") as f:
        resp = requests.post(
            DGX_WHISPER_URL,
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"response_format": "json", "language": "auto"},
            timeout=120
        )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()

def describe_frame(frame_path):
    with open(frame_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    resp = requests.post(
        LOCAL_OLLAMA_URL + "/api/generate",
        json={"model": VISION_MODEL, "prompt": PROMPT_FRAME, "images": [image_data], "stream": False},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()

def process_video(filepath, msg_id):
    video_path = Path(filepath)
    result_path = TRANSCR_DIR / (str(msg_id).zfill(4) + "_" + video_path.stem + "_video.json")
    if result_path.exists():
        with open(result_path) as f:
            return json.load(f)
    if not video_path.exists():
        return {"id": msg_id, "text": None, "error": "Archivo no encontrado: " + filepath}
    try:
        print("  Extrayendo audio del video...")
        wav_path = extract_audio(video_path)
        print("  Transcribiendo audio en DGX...")
        transcript = transcribe_wav(wav_path)
        print("  Extrayendo frames (cada " + str(FRAME_INTERVAL) + "s)...")
        frames = extract_frames(video_path, msg_id)
        frame_descriptions = []
        for frame in frames[:5]:
            print("  Describiendo frame: " + frame.name)
            desc = describe_frame(frame)
            frame_descriptions.append({"frame": frame.name, "description": desc})
        result = {
            "id": msg_id,
            "original": str(filepath),
            "transcript": transcript,
            "frame_descriptions": frame_descriptions,
            "text": "[Audio]: " + transcript + " [Visual]: " + "; ".join(d["description"] for d in frame_descriptions),
            "error": None
        }
    except Exception as e:
        result = {"id": msg_id, "original": str(filepath), "text": None, "error": str(e)}
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result

def process_videos(messages):
    to_process = [m for m in messages if m["type"] == "video" and m.get("filepath")]
    if not to_process:
        print("No hay videos para procesar.")
        return messages
    print("Procesando " + str(len(to_process)) + " videos...")
    for msg in to_process:
        print("[" + str(msg["id"]).zfill(3) + "] " + msg["sender"] + " - " + msg["filename"])
        result = process_video(msg["filepath"], msg["id"])
        msg["result"] = result.get("text")
        msg["processed"] = True
        if result.get("error"):
            print("  ERROR: " + result["error"])
        else:
            print("  OK: " + result["text"][:80] + "...")
    return messages

if __name__ == "__main__":
    import sys
    parsed_path = PROJECT_DIR / "data" / "conversations" / "parsed.json"
    if not parsed_path.exists():
        print("Ejecuta primero parser.py")
        sys.exit(1)
    with open(parsed_path, encoding="utf-8") as f:
        messages = json.load(f)
    messages = process_videos(messages)
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    print("Procesamiento de videos completado.")
