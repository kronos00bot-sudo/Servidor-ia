#!/usr/bin/env python3
"""
Procesa el dataset grande por lotes y por tipo de media.
Uso:
  python -m skills.whatsapp.utils.batch_run --type audio
  python -m skills.whatsapp.utils.batch_run --type image
  python -m skills.whatsapp.utils.batch_run --type document
  python -m skills.whatsapp.utils.batch_run --type all
Para reanudar sin re-parsear (reutiliza parsed.json existente):
  python -m skills.whatsapp.utils.batch_run --type audio --resume"""

import argparse
import time
from pathlib import Path

from skills.whatsapp.core.parser import parse_chat, load_parsed, save_parsed, summary
from skills.whatsapp.core.transcriber import transcribe_messages
from skills.whatsapp.core.image_processor import process_images
from skills.whatsapp.core.video_processor import process_videos
from skills.whatsapp.core.document_processor import process_documents
from skills.whatsapp.core.interpreter import interpret
from skills.whatsapp.core.translator import translate
from skills.whatsapp.routing.task_router import TaskRouter
from skills.whatsapp.utils.config import Config
from skills.whatsapp.utils.logger import setup_logging, get_logger


def print_batch_summary(label: str, messages: list, elapsed: float, media_types: tuple[str, ...]) -> None:
    tasks = [m for m in messages if m.get("type") in media_types and m.get("processed")]
    ok = [m for m in tasks if m.get("result")]
    err = [m for m in tasks if not m.get("result")]
    print(f"\n[{label}] {len(tasks)} procesados en {elapsed:.1f}s  |  OK={len(ok)}  ERROR={len(err)}")
    for m in err:
        print(f"  FAIL [{m['id']:03d}] {m['filename']}")


def run(media_type: str, config: Config, chat_file: Path, verbose: bool = True, resume: bool = False) -> None:
    setup_logging(config.PROJECT_DIR / "logs")
    logger = get_logger(__name__)

    parsed_path = config.PROJECT_DIR / "data" / "conversations" / "parsed.json"

    if resume and parsed_path.exists():
        logger.info("Reanudando desde parsed.json existente")
        messages = load_parsed(parsed_path)
        if not messages:
            logger.warning("parsed.json está vacío; reparseando desde _chat.txt")
            messages = parse_chat(chat_file)
            if verbose:
                summary(messages)
            save_parsed(messages, parsed_path)
            print(f"parsed.json vacío detectado: se reparsó el chat ({len(messages)} mensajes).")
        else:
            already = sum(1 for m in messages if m.get("processed"))
            print(f"Reanudando: {len(messages)} mensajes cargados, {already} ya procesados.")
    else:
        messages = parse_chat(chat_file)
        if verbose:
            summary(messages)
        save_parsed(messages, parsed_path)

    router = TaskRouter(config)

    if media_type in ("audio", "all", "media"):
        t0 = time.time()
        logger.info("Batch: audio")
        messages = transcribe_messages(messages, router)
        print_batch_summary("AUDIO", messages, time.time() - t0, ("audio", "video"))
        save_parsed(messages, parsed_path)

    if media_type in ("image", "all", "media"):
        t0 = time.time()
        logger.info("Batch: image")
        messages = process_images(messages, router)
        print_batch_summary("IMAGE", messages, time.time() - t0, ("image",))
        save_parsed(messages, parsed_path)

    if media_type in ("video", "all", "media"):
        t0 = time.time()
        logger.info("Batch: video")
        messages = process_videos(messages, router)
        print_batch_summary("VIDEO", messages, time.time() - t0, ("video",))
        save_parsed(messages, parsed_path)

    if media_type in ("document", "all", "media"):
        t0 = time.time()
        logger.info("Batch: document")
        messages = process_documents(messages, router)
        print_batch_summary("DOCUMENT", messages, time.time() - t0, ("document",))
        save_parsed(messages, parsed_path)

    if media_type in ("llm", "all"):
        t0 = time.time()
        logger.info("Batch: LLM interpret+translate")
        print("\nInterpretando conversación vía DGX...")
        interpreted = interpret(messages, router)
        print("Traduciendo y generando reporte final...")
        translate(interpreted, router)
        print_batch_summary("LLM", messages, time.time() - t0, ("audio", "video", "image", "document"))

    # Summary of unprocessed
    if media_type != "llm":
        remaining = [m for m in messages if not m.get("processed") and m["type"] not in ("text", "omitted")]
        if remaining:
            print(f"\nPendientes sin procesar: {len(remaining)}")
            for m in remaining[:10]:
                print(f"  [{m['id']:03d}] {m['type']:10s} {m.get('filename','')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch media processing for WhatsApp skill")
    parser.add_argument(
        "--type",
        choices=["audio", "image", "video", "document", "media", "llm", "all"],
        default="all",
        help=(
            "Tipo de media a procesar. "
            "'media' = audio+image+video+document sin LLM. "
            "'llm' = solo interpret+translate sobre parsed.json existente. "
            "'all' = todo."
        ),
    )
    parser.add_argument("--chat", type=Path, default=None, help="Ruta a _chat.txt")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reanudar cargando parsed.json existente en lugar de re-parsear",
    )
    args = parser.parse_args()

    config = Config()
    chat_file = args.chat or config.PROJECT_DIR / "media" / "input" / "_chat.txt"
    run(args.type, config, chat_file, resume=args.resume)


if __name__ == "__main__":
    main()
