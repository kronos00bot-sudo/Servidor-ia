"""Main WhatsApp processing pipeline orchestrator."""

import json
from datetime import datetime
from pathlib import Path

from skills.whatsapp.core.parser import parse_chat, save_parsed, summary
from skills.whatsapp.core.transcriber import transcribe_messages
from skills.whatsapp.core.image_processor import process_images
from skills.whatsapp.core.video_processor import process_videos
from skills.whatsapp.core.document_processor import process_documents
from skills.whatsapp.core.interpreter import interpret
from skills.whatsapp.core.translator import translate
from skills.whatsapp.routing.task_router import TaskRouter
from skills.whatsapp.utils.config import Config
from skills.whatsapp.utils.logger import get_logger


def run_pipeline(config: Config, chat_file: Path = None, skip_llm: bool = False) -> dict:
    """Execute the complete media and LLM pipeline for a WhatsApp export."""
    logger = get_logger(__name__)
    start = datetime.now()

    router = TaskRouter(config)
    chat_file = chat_file or config.PROJECT_DIR / "media" / "input" / "_chat.txt"

    if not chat_file.exists():
        raise FileNotFoundError(f"Chat file not found: {chat_file}")

    messages = parse_chat(chat_file)
    summary(messages)

    parsed_path = config.PROJECT_DIR / "data" / "conversations" / "parsed.json"
    save_parsed(messages, parsed_path)

    logger.info("[2/6] Transcribing audio and video")
    messages = transcribe_messages(messages, router)

    logger.info("[3/6] Processing images")
    messages = process_images(messages, router)

    logger.info("[4/6] Processing videos")
    messages = process_videos(messages, router)

    logger.info("[5/6] Processing documents")
    messages = process_documents(messages, router)

    parsed_path.parent.mkdir(parents=True, exist_ok=True)
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    if skip_llm:
        elapsed = datetime.now() - start
        logger.info(f"Pipeline completed in {elapsed} (skip_llm)")
        return {"messages": messages, "interpreted": None, "translated": None}

    logger.info("[6/6] Interpreting and translating")
    interpreted = interpret(messages, router)
    translated = translate(interpreted, router)

    elapsed = datetime.now() - start
    logger.info(f"Pipeline completed in {elapsed}")
    return {
        "messages": messages,
        "interpreted": interpreted,
        "translated": translated,
    }
