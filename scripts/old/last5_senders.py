#!/usr/bin/env python3
"""
Script rápido para mostrar los remetentes de los últimos 5 emails
"""

import imaplib
import email
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

# Configuración
EMAIL_ACCOUNT = get_config("EMAIL_ACCOUNT", "kronos00bot@gmail.com")
EMAIL_PASSWORD = get_config("EMAIL_PASSWORD", get_config("GMAIL_API_KEY", ""))
IMAP_SERVER = get_config("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(get_config("IMAP_PORT", "993"))

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

def obtener_remitentes_ultimos_5():
    """Obtener los remitentes de los últimos 5 correos."""
    try:
        # Conectarse al servidor IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        
        print("✅ Conexión exitosa con Gmail.")
        
        # Seleccionar la bandeja de entrada
        mail.select('inbox')
        
        # Buscar todos los mensajes
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("❌ Error al buscar mensajes.")
            return
        
        # Obtener IDs de mensajes
        email_ids = messages[0].split()
        
        if not email_ids:
            print("📭 No hay mensajes en la bandeja de entrada.")
            return
        
        # Ordenar por fecha (los más recientes primero) y tomar los últimos 5
        email_ids = email_ids[-5:]
        email_ids.reverse()
        
        print(f"\n📬 Remitentes de los últimos {len(email_ids)} mensajes:\n")
        print("=" * 60)
        
        remitentes = []
        for email_id in email_ids:
            # Obtener el mensaje por ID
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
            
            # Crear objeto de email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extraer remitente
            remitente = decodificar_header(msg['From'])
            remitentes.append(remitente)
        
        # Mostrar resultados
        for i, remitente in enumerate(remitentes, 1):
            print(f"{i}. {remitente}")
        
        print("=" * 60)
        
        # Cerrar conexión
        mail.close()
        mail.logout()
        
        print("\n✅ Operación completada.")
    
    except imaplib.IMAP4.error as e:
        print(f"❌ Error de autenticación: {e}")
        print("⚠️  Verifica tu correo y contraseña/API key.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    obtener_remitentes_ultimos_5()