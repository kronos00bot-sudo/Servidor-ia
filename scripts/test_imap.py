#!/usr/bin/env python3
import imaplib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"


def load_env_file(path: Path):
    env_vars = {}
    if not path.exists():
        return env_vars
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()
    return env_vars


env_vars = load_env_file(ENV_FILE)


def get_config(key: str, default: str = "") -> str:
    return os.getenv(key, env_vars.get(key, default))

# Configuration
EMAIL_ACCOUNT = get_config("EMAIL_ACCOUNT", "kronos00bot@gmail.com")
EMAIL_PASSWORD = get_config("EMAIL_PASSWORD", get_config("GMAIL_API_KEY", ""))
IMAP_SERVER = get_config("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(get_config("IMAP_PORT", "993"))

if not EMAIL_PASSWORD:
    raise SystemExit("❌ Falta EMAIL_PASSWORD (o GMAIL_API_KEY para compatibilidad)")

print(f"Testing IMAP connection for: {EMAIL_ACCOUNT}")
print("Using password: [hidden]")

try:
    # Conectar a IMAP
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    print("✅ IMAP login successful")
    
    # Seleccionar bandeja
    mail.select('inbox')
    
    # Buscar mensajes recientes
    status, messages = mail.search(None, 'ALL')
    if status == 'OK':
        email_ids = messages[0].split()
        print(f"📧 Total emails in inbox: {len(email_ids)}")
        
        # Mostrar los 3 más recientes
        if email_ids:
            recent_ids = email_ids[-3:]
            recent_ids.reverse()
            for eid in recent_ids:
                status, msg_data = mail.fetch(eid, '(RFC822)')
                if status == 'OK':
                    import email
                    from email.header import decode_header
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    subject = decode_header(email_message['Subject'])[0]
                    subject = subject[0].decode(subject[1] if subject[1] else 'utf-8') if isinstance(subject[0], bytes) else subject[0]
                    from_addr = decode_header(email_message['From'])[0]
                    from_addr = from_addr[0].decode(from_addr[1] if from_addr[1] else 'utf-8') if isinstance(from_addr[0], bytes) else from_addr[0]
                    print(f"  - From: {from_addr}")
                    print(f"    Subject: {subject}")
    
    mail.close()
    mail.logout()
    print("✅ IMAP test completed successfully")
    
except Exception as e:
    print(f"❌ IMAP error: {e}")