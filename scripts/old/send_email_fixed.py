#!/usr/bin/env python3
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
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

# Configuration - Fix: Account should be kronos00bot@gmail.com, password is the API key
EMAIL_ACCOUNT = get_config("EMAIL_ACCOUNT", "kronos00bot@gmail.com")
EMAIL_PASSWORD = get_config("EMAIL_PASSWORD", get_config("GMAIL_API_KEY", ""))
IMAP_SERVER = get_config("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = get_config("SMTP_SERVER", "smtp.gmail.com")
IMAP_PORT = int(get_config("IMAP_PORT", "993"))
SMTP_PORT = int(get_config("SMTP_PORT", "587"))

if not EMAIL_PASSWORD:
    raise SystemExit("❌ Falta EMAIL_PASSWORD (o GMAIL_API_KEY para compatibilidad)")

def decodificar_header(header_value):
    """Decodificar cabeceras de correo."""
    if header_value is None:
        return ""
    
    decoded_parts = decode_header(header_value)
    decoded_text = ""
    
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            if charset:
                decoded_text += part.decode(charset, errors='replace')
            else:
                decoded_text += part.decode('utf-8', errors='replace')
        else:
            decoded_text += part
    
    return decoded_text

def enviar_email_teste():
    """Enviar un email de teste a mcozzolinoes@gmail.com"""
    try:
        # Conectar a SMTP
        smtp_conn = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        smtp_conn.starttls()
        smtp_conn.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        
        print("✅ Conexión SMTP establecida")
        print(f"   Autenticado como: {EMAIL_ACCOUNT}")
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = "mcozzolinoes@gmail.com"
        msg['Subject'] = "Teste"
        
        # Cuerpo del mensaje
        body = "Teste"
        msg.attach(MIMEText(body, 'plain'))
        
        # Enviar email
        text = msg.as_string()
        smtp_conn.sendmail(EMAIL_ACCOUNT, "mcozzolinoes@gmail.com", text)
        smtp_conn.quit()
        
        print("✅ Email enviado exitosamente a mcozzolinoes@gmail.com")
        print(f"   De: {EMAIL_ACCOUNT}")
        print(f"   Para: mcozzolinoes@gmail.com")
        print(f"   Asunto: Teste")
        print(f"   Cuerpo: Teste")
        return True
        
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
        return False

if __name__ == '__main__':
    enviar_email_teste()