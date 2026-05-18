#!/usr/bin/env python3
"""
image_processor.py — Describe imágenes usando gemma4-es (visión) en el UM890
"""

import os
import json
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

PROJECT_DIR      = Path(os.getenv("PROJECT_DIR"))
LOCAL_OLLAMA_URL = os.getenv("LOCAL_OLLAMA_URL", "http://127.0.0.1:11434")
VISION_MODEL     = os.getenv("VISION_MODEL", "gemma4-es")
DESCR_DIR        = PROJECT_DIR / "data" / "descriptions"

DESCR_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

PROMPT = """You are analyzing an image from a WhatsApp conversation.
Describe what you see in detail: people, objects, text, context, emotions, setting.
Be concise but complete. Answer in English."""


def encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def describe_image(image_path: Path, msg_id: int) -> dict:
    result_path = DESCR_DIR / f"{msg_id:04d}_{image_path.stem}.json"
    if result_path.exists():
        with open(result_path) as f:
            return json.load(f)

    if image_path.suffix.lower() not in SUPPORTED:
        return {"id": msg_id, "text": None, "error": f"Formato no soportado: {image_path.suffix}"}

    try:
        print(f"  Describiendo imagen: {image_path.name}")
        image_data = encode_image(image_path)

        resp = requests.post(
            f"{LOCAL_OLLAMA_URL}/api/generate",
            json={
                "model": VISION_MODEL,
                "prompt": PROMPT,
                "images": [image_data],
                "stream": False
            },
            timeout=120
        )
        resp.raise_for_status()
        description = resp.json().get("response", "").strip()

        result = {
            "id":       msg_id,
            "original": str(image_path),
            "text":     description,
            "error":    None
        }
    except Exception as e:
        result = {
            "id":       msg_id,
            "original": str(image_path),
            "text":     None,
            "error":    str(e)
        }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def process_images(messages: list) -> list:
    to_process = [m for m in messages if m["type"] == "image" and m.get("filepath")]

    if not to_process:
        print("No hay imágenes para procesar.")
        return messages

    print(f"\nDescribiendo {len(to_process)} imágenes con {VISION_MODEL}...")
    for msg in to_process:
        print(f"[{msg['id']:03d}] {msg['sender']} — {msg['filename']}")
        result = describe_image(Path(msg["filepath"]), msg["id"])
        msg["result"]    = result.get("text")
        msg["processed"] = True
        if result.get("error"):
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {result['text'][:80]}...")

    return messages


if __name__ == "__main__":
    import sys
    parsed_path = PROJECT_DIR / "data" / "conversations" / "parsed.json"
    if not parsed_path.exists():
        print("Ejecuta primero parser.py")
        sys.exit(1)

    with open(parsed_path, encoding="utf-8") as f:
        messages = json.load(f)

    messages = process_images(messages)

    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    print("\nProcesamiento de imágenes completado.")
