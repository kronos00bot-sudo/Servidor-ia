"""Centralized logging setup with rotation."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """Configure root logging once with file rotation and stdout."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "whatsapp_skill.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    )

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger by module name."""
    return logging.getLogger(name)
