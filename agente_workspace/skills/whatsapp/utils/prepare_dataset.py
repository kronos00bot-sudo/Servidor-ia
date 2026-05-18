"""Prepare a WhatsApp export folder into the skill input structure.

This helper is intended for OpenClaw runtime on UM890.
It creates symlinks (or copies) from a source chat folder into:

PROJECT_DIR/media/input/
  - _chat.txt
  - audios_raw/
  - videos_raw/
  - images_raw/
  - documents_raw/
  - contacts_raw/
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from skills.whatsapp.utils.config import Config


AUDIO_EXT = {".opus", ".ogg", ".m4a", ".mp3", ".aac", ".wav"}
VIDEO_EXT = {".mp4", ".mov", ".3gp", ".avi", ".mkv", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
DOC_EXT = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".csv", ".pptx"}
CONTACT_EXT = {".vcf"}


def _bucket_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in AUDIO_EXT:
        return "audios_raw"
    if ext in VIDEO_EXT:
        return "videos_raw"
    if ext in IMAGE_EXT:
        return "images_raw"
    if ext in DOC_EXT:
        return "documents_raw"
    if ext in CONTACT_EXT:
        return "contacts_raw"
    return None


def _ensure_dirs(base: Path) -> None:
    (base / "audios_raw").mkdir(parents=True, exist_ok=True)
    (base / "videos_raw").mkdir(parents=True, exist_ok=True)
    (base / "images_raw").mkdir(parents=True, exist_ok=True)
    (base / "documents_raw").mkdir(parents=True, exist_ok=True)
    (base / "contacts_raw").mkdir(parents=True, exist_ok=True)


def _link_or_copy(src: Path, dst: Path, copy: bool = False) -> None:
    if dst.exists() or dst.is_symlink():
        return
    if copy:
        shutil.copy2(src, dst)
    else:
        dst.symlink_to(src)


def prepare(source_dir: Path, chat_file: Path, copy: bool = False) -> dict:
    media_input = Config.PROJECT_DIR / "media" / "input"
    _ensure_dirs(media_input)

    chat_target = media_input / "_chat.txt"
    if chat_target.exists() or chat_target.is_symlink():
        chat_target.unlink()
    _link_or_copy(chat_file, chat_target, copy=copy)

    linked = 0
    skipped = 0
    for file_path in source_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.name == chat_file.name:
            continue
        bucket = _bucket_for(file_path)
        if not bucket:
            skipped += 1
            continue
        dst = media_input / bucket / file_path.name
        _link_or_copy(file_path, dst, copy=copy)
        linked += 1

    return {
        "project_dir": str(Config.PROJECT_DIR),
        "source_dir": str(source_dir),
        "chat": str(chat_target),
        "prepared": linked,
        "skipped": skipped,
        "mode": "copy" if copy else "symlink",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare WhatsApp dataset for the skill")
    parser.add_argument("--source", type=Path, required=True, help="Folder with exported chat and media files")
    parser.add_argument(
        "--chat-file",
        type=Path,
        required=True,
        help="Path to exported WhatsApp text file",
    )
    parser.add_argument("--copy", action="store_true", help="Copy files instead of symlink")
    args = parser.parse_args()

    result = prepare(args.source, args.chat_file, copy=args.copy)
    print("Dataset prepared:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
