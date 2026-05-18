#!/usr/bin/env python3
"""
parser.py — Lee y parsea el chat exportado de WhatsApp (_chat.txt)
Clasifica cada mensaje por tipo: texto, audio, video, imagen, pdf, doc, contacto
"""

import re
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROJECT_DIR = Path(os.getenv("PROJECT_DIR", "/home/mloco/Escritorio/Servidor-ia/whatsapp-agent"))
INPUT_DIR   = PROJECT_DIR / "media" / "input"

PATTERN_MSG  = re.compile(
    r'^\[(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s+([^:]+):\s+(.+)$'
)
PATTERN_FILE = re.compile(r'^(.+?)\s*\(file attached\)$|^<attached:\s*(.+?)>$', re.IGNORECASE)

EXT_AUDIO   = {'.opus', '.ogg', '.m4a', '.mp3', '.aac', '.wav'}
EXT_VIDEO   = {'.mp4', '.mov', '.3gp', '.avi', '.mkv', '.webm'}
EXT_IMAGE   = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
EXT_DOC     = {'.pdf', '.docx', '.xlsx', '.xls', '.txt', '.csv', '.pptx'}
EXT_CONTACT = {'.vcf'}

def classify_file(filename):
    ext = Path(filename).suffix.lower()
    if ext in EXT_AUDIO:   return "audio"
    if ext in EXT_VIDEO:   return "video"
    if ext in EXT_IMAGE:   return "image"
    if ext in EXT_DOC:     return "document"
    if ext in EXT_CONTACT: return "contact"
    return "unknown"

def classify_message(text):
    omitted = {"<Media omitted>", "image omitted", "video omitted",
               "audio omitted", "sticker omitted", "document omitted",
               "This message was deleted", "You deleted this message"}
    if text.strip() in omitted:
        return "omitted", None
    m = PATTERN_FILE.match(text.strip())
    if m:
        filename = m.group(1) or m.group(2)
        return classify_file(filename), filename.strip()
    for word in text.split():
        word = word.strip(".,;:")
        ext = Path(word).suffix.lower()
        if ext in EXT_AUDIO | EXT_VIDEO | EXT_IMAGE | EXT_DOC | EXT_CONTACT:
            return classify_file(word), word
    return "text", None

def _subdir(msg_type):
    return {
        "audio":    "audios_raw",
        "video":    "videos_raw",
        "image":    "images_raw",
        "document": "documents_raw",
        "contact":  "contacts_raw",
    }.get(msg_type, "")

def parse_chat(chat_file):
    messages = []
    current = None
    with open(chat_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = PATTERN_MSG.match(line)
            if m:
                if current:
                    messages.append(current)
                date_str, time_str, sender, text = m.groups()
                msg_type, filename = classify_message(text)
                current = {
                    "id":       len(messages),
                    "date":     date_str.strip(),
                    "time":     time_str.strip(),
                    "sender":   sender.strip(),
                    "type":     msg_type,
                    "text":     text.strip() if msg_type == "text" else None,
                    "filename": filename,
                    "filepath": str(INPUT_DIR / _subdir(msg_type) / filename) if filename else None,
                    "processed": False,
                    "result":   None,
                }
            else:
                if current and current["type"] == "text" and current["text"]:
                    current["text"] += "\n" + line
    if current:
        messages.append(current)
    return messages

def save_parsed(messages, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    print(f"Guardados {len(messages)} mensajes en {output_path}")

def summary(messages):
    from collections import Counter
    types = Counter(m["type"] for m in messages)
    print("\nResumen del chat:")
    for t, n in types.most_common():
        print(f"  {t:12s}: {n}")
    print(f"  {'TOTAL':12s}: {len(messages)}")

if __name__ == "__main__":
    import sys
    chat_file = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_DIR / "_chat.txt"
    if not chat_file.exists():
        print(f"No encontrado: {chat_file}")
        sys.exit(1)
    messages = parse_chat(chat_file)
    summary(messages)
    out = PROJECT_DIR / "data" / "conversations" / "parsed.json"
    save_parsed(messages, out)
