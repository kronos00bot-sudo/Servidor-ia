#!/usr/bin/env python3
"""WhatsApp Skill entrypoint."""

from pathlib import Path
from skills.whatsapp.core.pipeline import run_pipeline
from skills.whatsapp.routing.task_router import TaskRouter
from skills.whatsapp.utils.config import Config
from skills.whatsapp.utils.logger import setup_logging, get_logger

CONFIG = Config()
setup_logging(CONFIG.PROJECT_DIR / "logs")
logger = get_logger(__name__)


class WhatsAppSkill:
    def __init__(self, config: Config = CONFIG):
        self.config = config
        self.router = TaskRouter(config)

    def run(self, chat_file: Path = None, skip_llm: bool = False):
        logger.info("Starting WhatsApp Skill pipeline")
        return run_pipeline(self.config, chat_file=chat_file, skip_llm=skip_llm)

    def run_cli(self):
        import argparse
        parser = argparse.ArgumentParser(description="WhatsApp Skill pipeline")
        parser.add_argument("--chat", type=Path, help="Path to _chat.txt (optional)")
        parser.add_argument("--skip-llm", action="store_true", help="Only process media, skip LLM")
        args = parser.parse_args()
        self.run(chat_file=args.chat, skip_llm=args.skip_llm)


if __name__ == "__main__":
    WhatsAppSkill().run_cli()
