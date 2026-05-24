#!/usr/bin/env python3
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import os
import time
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

def verificar_email_enviado():
    """Verificar si el email de teste aparece en los recientes"""
    try:
        # Conectar a IMAP para revisar bandeja de entrada (por si el destinatario lo recibió y está en la misma cuenta)
        # O mejor, revisar la carpeta de "Enviados"
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        
        print("✅ Conexión IMAP establecida para verificación")
        
        # Intentar revisar la carpeta de "Enviados" (puede variar según el servidor)
        sent_folders = ['[Gmail]/Sent Mail', 'Sent', 'Sent Items']
        selected = False
        
        for folder in sent_folders:
            try:
                mail.select(folder)
                selected = True
                print(f"📁 Revisando carpeta: {folder}")
                break
            except:
                continue
        
        if not selected:
            # Si no encontramos la carpeta de enviados, revisamos INBOX como fallback
            mail.select('inbox')
            print("📁 Revisando carpeta: INBOX (fallback)")
        
        # Buscar todos los mensajes
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("❌ Error al buscar mensajes.")
            return False
        
        # Obtener IDs de mensajes
        email_ids = messages[0].split()
        
        if not email_ids:
            print("📭 No hay mensajes.")
            return False
        
        # Tomar los últimos 10 mensajes para buscar nuestro email de teste
        email_ids = email_ids[-10:]
        email_ids.reverse()  # Más recientes primero
        
        print(f"\n🔍 Verificando los últimos {len(email_ids)} mensajes...")
        
        encontrado = False
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
            
            # Crear objeto de email
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extraer información
            remitente = decodificar_header(email_message['From'])
            asunto = decodificar_header(email_message['Subject'])
            fecha = email_message['Date']
            
            # Buscar nuestro email de teste
            if "teste" in asunto.lower() and "kronos00bot@gmail.com" in remitente.lower():
                print(f"✅ EMAIL DE TESTE ENCONTRADO:")
                print(f"   De: {remitente}")
                print(f"   Para: {decodificar_header(email_message['To'])}")
                print(f"   Asunto: {asunto}")
                print(f"   Fecha: {fecha}")
                
                # Obtener el cuerpo
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                            break
                else:
                    body = email_message.get_payload(decode=True).decode('utf-8', errors='replace')
                
                print(f"   Cuerpo: {body.strip()}")
                encontrado = True
                break
        
        if not encontrado:
            print("ℹ️  No se encontró el email de teste en los últimos 10 mensajes.")
            print("   Esto puede ser normal si:")
            print("   - El email aún no ha llegado (latencia de red)")
            print("   - Fue filtrado a otra carpeta (Spam, Promociones, etc.)")
            print("   - La búsqueda no incluyó suficientes mensajes")
        
        mail.close()
        mail.logout()
        return encontrado
        
    except Exception as e:
        print(f"❌ Error durante la verificación: {e}")
        return False

if __name__ == '__main__':
    print("🔍 Verificando envío de email de teste...")
    verificar_email_enviado()