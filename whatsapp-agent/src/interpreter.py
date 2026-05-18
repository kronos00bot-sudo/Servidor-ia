#!/usr/bin/env python3
"""
interpreter.py — Ensambla la conversación completa y pide contexto al DGX
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_DIR    = Path(os.getenv("PROJECT_DIR"))
DGX_OLLAMA_URL = os.getenv("DGX_OLLAMA_URL", "http://100.64.129.87:11434")
DGX_LLM_MODEL = os.getenv("DGX_LLM_MODEL", "nemotron-3-super:120b")
CONV_DIR       = PROJECT_DIR / "data" / "conversations"

PROMPT = """You are analyzing a WhatsApp conversation. Below is the full conversation with all messages, including transcriptions of audio/video and descriptions of images and documents.

Your task:
1. Identify the main topics discussed
2. Identify the participants and their roles/relationship
3. Summarize the key points of the conversation
4. Note any important decisions, agreements or action items
5. Identify the tone and context (business, personal, urgent, casual, etc.)

Be thorough but concise. Answer in English.

CONVERSATION:
{conversation}"""


def build_conversation_text(messages: list) -> str:
    lines = []
    for m in messages:
        if m["type"] == "omitted":
            continue
        timestamp = f"[{m['date']} {m['time']}]"
        sender    = m["sender"]

        if m["type"] == "text" and m.get("text"):
            lines.append(f"{timestamp} {sender}: {m['text']}")
        elif m.get("result"):
            type_label = {
                "audio":    "🎤 AUDIO",
                "video":    "🎥 VIDEO",
                "image":    "🖼️ IMAGE",
                "document": "📄 DOCUMENT",
                "contact":  "👤 CONTACT",
            }.get(m["type"], m["type"].upper())
            lines.append(f"{timestamp} {sender} [{type_label}]: {m['result']}")
        elif m.get("filename"):
            lines.append(f"{timestamp} {sender} [FILE - not processed]: {m['filename']}")

    return "\n".join(lines)


def interpret(messages: list) -> dict:
    result_path = CONV_DIR / "interpreted.json"

    conversation_text = build_conversation_text(messages)

    print(f"\nEnviando conversación al DGX para interpretación...")
    print(f"  Mensajes: {len(messages)} | Chars: {len(conversation_text)}")

    prompt = PROMPT.format(conversation=conversation_text)

    resp = requests.post(
        f"{DGX_OLLAMA_URL}/api/generate",
        json={"model": DGX_LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=300
    )
    resp.raise_for_status()
    interpretation = resp.json().get("response", "").strip()

    result = {
        "conversation_text": conversation_text,
        "interpretation":    interpretation,
        "message_count":     len(messages),
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  OK: {interpretation[:100]}...")
    return result


if __name__ == "__main__":
    parsed_path = CONV_DIR / "parsed.json"
    if not parsed_path.exists():
        print("Ejecuta primero parser.py y los processors")
        import sys; sys.exit(1)

    with open(parsed_path, encoding="utf-8") as f:
        messages = json.load(f)

    result = interpret(messages)
    print("\nInterpretación completada.")
    print("\n" + "="*60)
    print(result["interpretation"])
