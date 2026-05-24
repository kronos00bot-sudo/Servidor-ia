#!/usr/bin/env python3
"""Telegram skill entrypoint for OpenClaw."""

from pathlib import Path

from skills.telegram.media import TelegramMediaClient
from skills.telegram.poller import TelegramPoller
from skills.telegram.proactive import TelegramProactiveEngine
from skills.telegram.state import TelegramState
from skills.telegram.utils.config import TelegramConfig
from skills.telegram.webhook.endpoint import create_app
from skills.telegram.client import TelegramClient
from skills.telegram.routing.remote_client import RemoteClient
from skills.telegram.routing.task_router import TaskRouter
from skills.telegram.utils.logger import setup_logging, get_logger

CONFIG = TelegramConfig
setup_logging(CONFIG.PROJECT_DIR / "logs")
logger = get_logger(__name__)


class TelegramSkill:
    """Telegram skill entrypoint over the OpenClaw Telegram stack."""

    def __init__(self, config: TelegramConfig = CONFIG):
        self.config = config
        self.router = TaskRouter(config)
        self.remote = RemoteClient()
        self.tg_client = TelegramClient()
        self.state = TelegramState()
        self.media_client = TelegramMediaClient()

    def create_app(self):
        return create_app(router=self.router, remote=self.remote)

    def run_server(self, host: str = "0.0.0.0", port: int | None = None):
        app = self.create_app()
        app.run(host=host, port=port or self.config.TELEGRAM_WEBHOOK_PORT)

    def run_polling(self, sleep_seconds: int = 2):
        poller = TelegramPoller(self.router, self.remote, state=self.state, media_client=self.media_client)
        poller.run_forever(sleep_seconds=sleep_seconds)

    def run_proactive_once(self):
        engine = TelegramProactiveEngine(state=self.state, tg_client=self.tg_client)
        return engine.run_once()

    def run_cli(self):
        import argparse

        parser = argparse.ArgumentParser(description="Telegram Skill adapter")
        parser.add_argument("--serve", action="store_true", help="Start Telegram webhook server")
        parser.add_argument("--poll", action="store_true", help="Run Telegram long polling loop")
        parser.add_argument("--proactive-once", action="store_true", help="Send one proactive cycle and exit")
        parser.add_argument("--host", default="0.0.0.0", help="Webhook host")
        parser.add_argument("--port", type=int, default=self.config.TELEGRAM_WEBHOOK_PORT, help="Webhook port")
        parser.add_argument("--sleep", type=int, default=2, help="Polling sleep seconds")
        args = parser.parse_args()

        if args.serve:
            logger.info("Starting Telegram webhook server")
            self.run_server(host=args.host, port=args.port)
        elif args.poll:
            logger.info("Starting Telegram long polling")
            self.run_polling(sleep_seconds=args.sleep)
        elif args.proactive_once:
            logger.info("Running one proactive Telegram cycle")
            self.run_proactive_once()
        else:
            parser.print_help()


if __name__ == "__main__":
    TelegramSkill().run_cli()
