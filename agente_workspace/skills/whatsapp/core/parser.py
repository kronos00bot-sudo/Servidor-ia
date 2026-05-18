"""Parse WhatsApp exported chat text into structured messages."""

import re
import json
from pathlib import Path
from .config import Config

CONFIG = Config()

PATTERN_MSG = re.compile(
    r'^(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+-\s+(.+)$'
)
PATTERN_FILE = re.compile(
    r'^\u200e?(.+?)\s*\((?:file attached|archivo adjunto)\)$|^<attached:\s*(.+?)>$',
    re.IGNORECASE,
)

EXT_AUDIO = {'.opus', '.ogg', '.m4a', '.mp3', '.aac', '.wav'}
EXT_VIDEO = {'.mp4', '.mov', '.3gp', '.avi', '.mkv', '.webm'}
EXT_IMAGE = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
EXT_DOC = {'.pdf', '.docx', '.xlsx', '.xls', '.txt', '.csv', '.pptx'}
EXT_CONTACT = {'.vcf'}


def classify_file(filename: str):
    ext = Path(filename).suffix.lower()
    if ext in EXT_AUDIO:
        return 'audio'
    if ext in EXT_VIDEO:
        return 'video'
    if ext in EXT_IMAGE:
        return 'image'
    if ext in EXT_DOC:
        return 'document'
    if ext in EXT_CONTACT:
        return 'contact'
    return 'unknown'


def classify_message(text: str):
    omitted = {
        '<Media omitted>', 'image omitted', 'video omitted', 'audio omitted',
        'sticker omitted', 'document omitted', 'This message was deleted', 'You deleted this message',
        '<Multimedia omitido>', 'Multimedia omitido',
    }
    clean_text = text.replace('\u200e', '').strip()
    if clean_text in omitted:
        return 'omitted', None
    m = PATTERN_FILE.match(clean_text)
    if m:
        filename = m.group(1) or m.group(2)
        return classify_file(filename), filename.strip().replace('\u200e', '')
    for word in clean_text.split():
        word = word.strip('.,;:')
        ext = Path(word).suffix.lower()
        if ext in EXT_AUDIO | EXT_VIDEO | EXT_IMAGE | EXT_DOC | EXT_CONTACT:
            return classify_file(word), word
    return 'text', None


def _subdir(msg_type: str) -> str:
    return {
        'audio': 'audios_raw',
        'video': 'videos_raw',
        'image': 'images_raw',
        'document': 'documents_raw',
        'contact': 'contacts_raw',
    }.get(msg_type, '')


def parse_chat(chat_file: Path):
    messages = []
    current = None
    with open(chat_file, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            m = PATTERN_MSG.match(line)
            if m:
                if current:
                    messages.append(current)
                date_str, time_str, payload = m.groups()

                # Format: "Sender: message" or system event without sender.
                sender = None
                text = payload
                if ': ' in payload:
                    sender, text = payload.split(': ', 1)

                sender = (sender or 'system').replace('\u200e', '').strip()
                msg_type, filename = classify_message(text)
                current = {
                    'id': len(messages),
                    'date': date_str.strip(),
                    'time': time_str.strip(),
                    'sender': sender,
                    'type': msg_type,
                    'text': text.replace('\u200e', '').strip() if msg_type == 'text' else None,
                    'filename': filename,
                    'filepath': str(CONFIG.PROJECT_DIR / 'media' / 'input' / _subdir(msg_type) / filename) if filename else None,
                    'processed': False,
                    'result': None,
                }
            else:
                if current and current['type'] == 'text' and current['text']:
                    current['text'] += '\n' + line
    if current:
        messages.append(current)
    return messages


def save_parsed(messages: list, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def load_parsed(parsed_path: Path) -> list:
    """Carga parsed.json existente para reanudar sin re-parsear."""
    with open(parsed_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def summary(messages: list):
    from collections import Counter
    types = Counter(m['type'] for m in messages)
    total_label = "TOTAL"
    print('\nResumen del chat:')
    for t, n in types.most_common():
        print(f'  {t:12s}: {n}')
    print(f'  {total_label:12s}: {len(messages)}')
