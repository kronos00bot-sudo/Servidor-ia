#!/usr/bin/env python3
"""
pipeline.py — Orquestador principal del WhatsApp Agent
Ejecuta el flujo completo: parse -> process -> interpret -> translate
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_DIR = Path(os.getenv("PROJECT_DIR"))

# Logging
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# Importar módulos
sys.path.insert(0, str(Path(__file__).parent))
from parser import parse_chat, save_parsed, summary
from transcriber import transcribe_messages
from processors.image_processor import process_images
from processors.video_processor import process_videos
from processors.pdf_processor import process_documents
from interpreter import interpret
from translator import translate


def run(chat_file: Path = None, skip_llm: bool = False):
    start = datetime.now()
    log.info("=" * 60)
    log.info("WhatsApp Agent — Iniciando pipeline")
    log.info("=" * 60)

    # 1. PARSE
    chat_file = chat_file or PROJECT_DIR / "media" / "input" / "_chat.txt"
    if not chat_file.exists():
        log.error(f"Chat no encontrado: {chat_file}")
        sys.exit(1)

    log.info(f"[1/6] Parseando: {chat_file.name}")
    messages = parse_chat(chat_file)
    summary(messages)
    parsed_path = PROJECT_DIR / "data" / "conversations" / "parsed.json"
    save_parsed(messages, parsed_path)

    # 2. AUDIO/VIDEO — STT en DGX
    log.info("[2/6] Transcribiendo audios y videos en DGX whisper-server...")
    messages = transcribe_messages(messages)

    # 3. IMÁGENES — visión en UM890
    log.info("[3/6] Describiendo imágenes con gemma4-es (UM890)...")
    messages = process_images(messages)

    # 4. VIDEOS — frames en UM890
    log.info("[4/6] Procesando frames de video con gemma4-es (UM890)...")
    messages = process_videos(messages)

    # 5. DOCUMENTOS — extracción + resumen en DGX
    log.info("[5/6] Procesando documentos con DGX...")
    messages = process_documents(messages)

    # Guardar estado intermedio
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    if skip_llm:
        log.info("--skip-llm: omitiendo interpretación y traducción")
        log.info(f"Pipeline completado en {datetime.now() - start}")
        return

    # 6. INTERPRETAR + TRADUCIR en DGX
    log.info("[6/6] Interpretando y traduciendo con DGX nemotron-3-super:120b...")
    interpreted = interpret(messages)
    result = translate(interpreted)

    elapsed = datetime.now() - start
    log.info("=" * 60)
    log.info(f"Pipeline completado en {elapsed}")
    log.info(f"Output: {PROJECT_DIR}/output/conversation_es.md")
    log.info("=" * 60)

    print(chr(10) + "=" * 60)
    print(result["final_report"][:800])
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WhatsApp Agent Pipeline")
    parser.add_argument("--chat", type=Path, help="Ruta al _chat.txt (opcional)")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Solo procesar media, sin interpretar ni traducir")
    args = parser.parse_args()
    run(chat_file=args.chat, skip_llm=args.skip_llm)
