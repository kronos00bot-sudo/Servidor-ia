#!/usr/bin/env python3
"""
Script mejorado para operaciones completas de Gmail:
Leer, escribir/enviar, descargar adjuntos y gestionar conexiones
Creado por: Mejorado por Nex (basado en el original de Kronos)
Usuario: Manoel
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import decode_header
import os
import getpass
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración desde .env
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT", "kronos00bot@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") or os.getenv("GMAIL_API_KEY")  # Soporta ambos formats
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

class EmailManager:
    def __init__(self):
        self.imap_conn = None
        self.smtp_conn = None
        self.email_account = EMAIL_ACCOUNT
        self.email_password = EMAIL_PASSWORD
        
    def connect_imap(self) -> bool:
        """Conectar y autenticar con IMAP"""
        try:
            self.imap_conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            self.imap_conn.login(self.email_account, self.email_password)
            print("✅ Conexión IMAP establecida")
            return True
        except Exception as e:
            print(f"❌ Error conectando IMAP: {e}")
            return False
    
    def connect_smtp(self) -> bool:
        """Conectar y autenticar con SMTP"""
        try:
            self.smtp_conn = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            self.smtp_conn.starttls()
            self.smtp_conn.login(self.email_account, self.email_password)
            print("✅ Conexión SMTP establecida")
            return True
        except Exception as e:
            print(f"❌ Error conectando SMTP: {e}")
            return False
    
    def read_emails(self, folder: str = "INBOX", limit: int = 10, 
                   unseen_only: bool = True, mark_as_read: bool = False) -> List[Dict[str, Any]]:
        """
        Leer emails de la carpeta especificada
        
        Args:
            folder: Carpeta de correo (INBOX, Spam, etc.)
            limit: Número máximo de emails a leer
            unseen_only: Si es True, solo lee no leídos
            mark_as_read: Si es True, marca como leído después de leer
            
        Returns:
            Lista de diccionarios con la información de los emails
        """
        if not self.imap_conn:
            if not self.connect_imap():
                return []
                
        try:
            self.imap_conn.select(folder)
            
            search_criteria = "UNSEEN" if unseen_only else "ALL"
            status, messages = self.imap_conn.search(None, search_criteria)
            
            if status != "OK":
                print("❌ Error al buscar correos")
                return []
                
            email_ids = messages[0].split()
            if not email_ids:
                print("📭 No hay correos que coincidan con los criterios")
                return []
                
            # Tomar los más recientes primero
            email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
            email_ids.reverse()
            
            emails = []
            for email_id in email_ids:
                status, msg_data = self.imap_conn.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                    
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Parsear email
                parsed_email = {
                    'id': email_id.decode(),
                    'subject': self._decode_header(email_message['Subject']),
                    'from': self._decode_header(email_message['From']),
                    'to': self._decode_header(email_message['To']),
                    'date': email_message['Date'],
                    'body': self._get_body(email_message),
                    'attachments': self._get_attachments_info(email_message)
                }
                emails.append(parsed_email)
                
                # Marcar como leído si se solicita
                if mark_as_read:
                    self.imap_conn.store(email_id, '+FLAGS', '\\Seen')
                    
            print(f"📧 Leídos {len(emails)} correos de {folder}")
            return emails
            
        except Exception as e:
            print(f"❌ Error leyendo correos: {e}")
            return []
    
    def send_email(self, to: str, subject: str, body: str, 
                   cc: str = None, bcc: str = None,
                   attachments: List[str] = None) -> bool:
        """
        Enviar un email
        
        Args:
            to: Destinatario principal
            subject: Asunto del email
            body: Cuerpo del email (texto plano)
            cc: CC (opcional)
            bcc: BCC (opcional)
            attachments: Lista de rutas de archivos para adjuntar (opcional)
            
        Returns:
            True si se envió exitosamente, False en caso contrario
        """
        if not self.smtp_conn:
            if not self.connect_smtp():
                return False
                
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_account
            msg['To'] = to
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = cc
            if bcc:
                msg['Bcc'] = bcc
                
            # Añadir cuerpo
            msg.attach(MIMEText(body, 'plain'))
            
            # Añadir adjuntos si los hay
            if attachments:
                for file_path in attachments:
                    if os.path.isfile(file_path):
                        part = MIMEBase('application', 'octet-stream')
                        with open(file_path, "rb") as file:
                            part.set_payload(file.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(file_path)}'
                        )
                        msg.attach(part)
                    else:
                        print(f"⚠️  Archivo no encontrado para adjuntar: {file_path}")
            
            # Preparar lista de destinatarios
            recipients = [to]
            if cc:
                recipients.append(cc)
            if bcc:
                recipients.append(bcc)
                
            # Enviar email
            text = msg.as_string()
            self.smtp_conn.sendmail(self.email_account, recipients, text)
            print(f"✅ Email enviado exitosamente a {to}")
            return True
            
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
            return False
    
    def download_attachments(self, email_id: str, 
                           download_dir: str = "./descargas") -> List[str]:
        """
        Descargar adjuntos de un email específico
        
        Args:
            email_id: ID del email del cual descargar adjuntos
            download_dir: Directorio donde guardar los adjuntos
            
        Returns:
            Lista de rutas de los archivos descargados
        """
        if not self.imap_conn:
            if not self.connect_imap():
                return []
                
        try:
            os.makedirs(download_dir, exist_ok=True)
            status, msg_data = self.imap_conn.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                print(f"❌ No se pudo obtener el email {email_id}")
                return []
                
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            downloaded_files = []
            for part in email_message.walk():
                # Saltar partes multipart (son contenedores)
                if part.get_content_maintype() == 'multipart':
                    continue
                    
                # Verificar si es un adjunto
                content_disposition = part.get("Content-Disposition")
                if content_disposition is None:
                    continue
                    
                filename = part.get_filename()
                if filename:
                    filename = self._decode_header(filename)
                    # Evitar nombres de archivo peligrosos
                    filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
                    if not filename:
                        filename = f"adjunto_{len(downloaded_files)}"
                        
                    filepath = os.path.join(download_dir, filename)
                    
                    # Evitar sobrescribir archivos
                    counter = 1
                    original_filepath = filepath
                    while os.path.exists(filepath):
                        name, ext = os.path.splitext(original_filepath)
                        filepath = f"{name}_{counter}{ext}"
                        counter += 1
                    
                    # Guardar el adjunto
                    with open(filepath, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    
                    downloaded_files.append(filepath)
                    print(f"📥 Adjunto descargado: {filename}")
            
            if not downloaded_files:
                print("📭 No se encontraron adjuntos en este email")
                
            return downloaded_files
            
        except Exception as e:
            print(f"❌ Error descargando adjuntos: {e}")
            return []
    
    def mark_as_read(self, email_id: str) -> bool:
        """Marcar un email como leído"""
        if not self.imap_conn:
            if not self.connect_imap():
                return False
                
        try:
            self.imap_conn.store(email_id, '+FLAGS', '\\Seen')
            print(f"📧 Email {email_id} marcado como leído")
            return True
        except Exception as e:
            print(f"❌ Error marcando como leído: {e}")
            return False
    
    def mark_as_unread(self, email_id: str) -> bool:
        """Marcar un email como no leído"""
        if not self.imap_conn:
            if not self.connect_imap():
                return False
                
        try:
            self.imap_conn.store(email_id, '-FLAGS', '\\Seen')
            print(f"📧 Email {email_id} marcado como no leído")
            return True
        except Exception as e:
            print(f"❌ Error marcando como no leído: {e}")
            return False
    
    def delete_email(self, email_id: str) -> bool:
        """Marcar un email para eliminación (se expunge después)"""
        if not self.imap_conn:
            if not self.connect_imap():
                return False
                
        try:
            self.imap_conn.store(email_id, '+FLAGS', '\\Deleted')
            print(f"🗑️  Email {email_id} marcado para eliminación")
            return True
        except Exception as e:
            print(f"❌ Error marcando para eliminación: {e}")
            return False
    
    def expunge(self) -> bool:
        """Eliminar permanentemente los emails marcados para eliminación"""
        if not self.imap_conn:
            if not self.connect_imap():
                return False
                
        try:
            self.imap_conn.expunge()
            print("🗑️  Correos eliminados permanentemente")
            return True
        except Exception as e:
            print(f"❌ Error expunging: {e}")
            return False
    
    def disconnect(self):
        """Cerrar todas las conexiones"""
        try:
            if self.imap_conn:
                self.imap_conn.close()
                self.imap_conn.logout()
                print("🔌 Conexión IMAP cerrada")
        except Exception as e:
            print(f"⚠️  Error cerrando IMAP: {e}")
        
        try:
            if self.smtp_conn:
                self.smtp_conn.quit()
                print("🔌 Conexión SMTP cerrada")
        except Exception as e:
            print(f"⚠️  Error cerrando SMTP: {e}")
    
    # Métodos auxiliares privados
    def _decode_header(self, header) -> str:
        """Decodificar un header de email de forma segura"""
        if header is None:
            return ""
        try:
            decoded_parts = decode_header(header)
            decoded_text = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_text += part.decode(encoding, errors='replace')
                    else:
                        decoded_text += part.decode('utf-8', errors='replace')
                else:
                    decoded_text += part
            return decoded_text
        except Exception:
            return str(header) if header else ""
    
    def _get_body(self, email_message) -> str:
        """Extraer el cuerpo de texto plano de un email"""
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Buscar la parte de texto plano que no sea adjunto
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        break
                    except:
                        continue
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='replace')
            except:
                body = str(email_message.get_payload())
        return body
    
    def _get_attachments_info(self, email_message) -> List[Dict[str, str]]:
        """Obtener información de los adjuntos sin descargarlos"""
        attachments = []
        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
                
            filename = part.get_filename()
            if filename:
                filename = self._decode_header(filename)
                attachments.append({
                    'filename': filename,
                    'content_type': part.get_content_type(),
                    'size': len(part.get_payload(decode=True) or b'')
                })
        return attachments

def menu_interactivo():
    """Menú interactivo para operaciones de email"""
    email_manager = EmailManager()
    
    print("=" * 60)
    print("📧 GESTOR DE EMAIL GMAIL - KRONOS00BOT")
    print("=" * 60)
    print("Credenciales cargadas desde .env")
    print(f"Cuenta: {EMAIL_ACCOUNT}")
    print("-" * 60)
    
    # Conectar automáticamente al iniciar
    if not email_manager.connect_imap() or not email_manager.connect_smtp():
        print("❌ No se pudo establecer conexión. Verifique sus credenciales.")
        return
    
    while True:
        print("\n📋 MENÚ DE OPERACIONES:")
        print("1️⃣  Leer correos no leídos")
        print("2️⃣  Leer todos los correos (últimos N)")
        print("3️⃣  Enviar un email")
        print("4️⃣  Descargar adjuntos de un email")
        print("5️⃣  Marcar email como leído")
        print("6️⃣  Marcar email como no leído")
        print("7️⃣  Eliminar email")
        print("8️⃣  Ver bandeja de entrada")
        print("9️⃣  Ver carpeta de spam")
        print("🔟 Salir")
        print("-" * 40)
        
        try:
            opcion = input("Seleccione una opción (1-10): ").strip()
            
            if opcion == "1":
                limit = input("¿Cuántos correos leer? (default 5): ").strip()
                limit = int(limit) if limit.isdigit() else 5
                emails = email_manager.read_emails(limit=limit, unseen_only=True, mark_as_read=False)
                _mostrar_emails(emails)
                
            elif opcion == "2":
                limit = input("¿