#!/usr/bin/env python3
"""
translator.py — Traduce la conversación completa al español
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
TARGET_LANG    = os.getenv("TARGET_LANG", "es")
CONV_DIR       = PROJECT_DIR / "data" / "conversations"
OUTPUT_DIR     = PROJECT_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TRANSLATE = """You are a professional translator. Translate the following WhatsApp conversation to Spanish.

Rules:
- Keep the original format: [date time] Sender: message
- Preserve names as they are (do not translate names)
- Keep timestamps exactly as they appear
- Translate naturally, not literally — preserve the tone and register
- For audio/image/video/document labels keep them in brackets
- If text is already in Spanish, keep it as is

CONVERSATION TO TRANSLATE:
{conversation}"""

PROMPT_FINAL = """Based on this WhatsApp conversation analysis and its Spanish translation, create a clean final report in Spanish with this structure:

# Resumen de la Conversación

## Participantes
[List participants]

## Temas Principales
[Main topics discussed]

## Puntos Clave
[Key points, decisions, agreements]

## Tono y Contexto
[Tone and context]

## Conversación Traducida
[Full translated conversation]

ANALYSIS:
{interpretation}

TRANSLATED CONVERSATION:
{translated}"""


def translate_conversation(conversation_text: str) -> str:
    print(f"  Traduciendo conversación ({len(conversation_text)} chars)...")
    prompt = PROMPT_TRANSLATE.format(conversation=conversation_text)
    resp = requests.post(
        f"{DGX_OLLAMA_URL}/api/generate",
        json={"model": DGX_LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=300
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def generate_final_report(interpretation: str, translated: str) -> str:
    print(f"  Generando reporte final...")
    prompt = PROMPT_FINAL.format(interpretation=interpretation, translated=translated)
    resp = requests.post(
        f"{DGX_OLLAMA_URL}/api/generate",
        json={"model": DGX_LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=300
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def translate(interpreted: dict) -> dict:
    print(f"\nTraduciendo con DGX nemotron-3-super:120b...")

    translated = translate_conversation(interpreted["conversation_text"])
    final_report = generate_final_report(interpreted["interpretation"], translated)

    # Guardar MD
    md_path = OUTPUT_DIR / "conversation_es.md"
    md_path.write_text(final_report, encoding="utf-8")

    # Guardar JSON
    result = {
        "translated_conversation": translated,
        "interpretation":          interpreted["interpretation"],
        "final_report":            final_report,
    }
    json_path = OUTPUT_DIR / "conversation_es.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Guardado: {md_path}")
    print(f"  Guardado: {json_path}")
    return result


if __name__ == "__main__":
    interpreted_path = CONV_DIR / "interpreted.json"
    if not interpreted_path.exists():
        print("Ejecuta primero interpreter.py")
        import sys; sys.exit(1)

    with open(interpreted_path, encoding="utf-8") as f:
        interpreted = json.load(f)

    result = translate(interpreted)
    print("\nTraducción completada.")
    print("\n" + "="*60)
    print(result["final_report"][:500] + "...")
