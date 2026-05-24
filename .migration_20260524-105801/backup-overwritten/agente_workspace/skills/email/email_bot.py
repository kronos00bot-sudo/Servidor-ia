#!/usr/bin/env python3
"""
Email Bot for Kronos00bot@gmail.com
Handles: reading, writing, sending, downloading attachments, and clean disconnect
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import getpass
from typing import List, Optional, Dict, Any
import logging

# Configuration
EMAIL_ADDRESS = "Kronos00bot@gmail.com"
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
IMAP_PORT = 993
SMTP_PORT = 587

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmailBot:
    def __init__(self, email_address: str = EMAIL_ADDRESS):
        self.email_address = email_address
        self.imap_conn = None
        self.smtp_conn = None
        self.password = None
        
    def authenticate_imap(self, password: str) -> bool:
        """Authenticate with IMAP server"""
        try:
            self.imap_conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            self.imap_conn.login(self.email_address, password)
            self.password = password
            logger.info("IMAP authentication successful")
            return True
        except Exception as e:
            logger.error(f"IMAP authentication failed: {e}")
            return False
    
    def authenticate_smtp(self, password: str = None) -> bool:
        """Authenticate with SMTP server"""
        if password is None:
            password = self.password
            
        try:
            self.smtp_conn = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            self.smtp_conn.starttls()
            self.smtp_conn.login(self.email_address, password)
            logger.info("SMTP authentication successful")
            return True
        except Exception as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
    
    def read_emails(self, folder: str = "INBOX", limit: int = 10, 
                   unseen_only: bool = True) -> List[Dict[str, Any]]:
        """
        Read emails from specified folder
        
        Args:
            folder: Mailbox folder to read from
            limit: Maximum number of emails to fetch
            unseen_only: Only fetch unread emails
            
        Returns:
            List of email dictionaries
        """
        if not self.imap_conn:
            logger.error("IMAP not authenticated")
            return []
            
        try:
            self.imap_conn.select(folder)
            
            search_criteria = "UNSEEN" if unseen_only else "ALL"
            status, messages = self.imap_conn.search(None, search_criteria)
            
            if status != "OK":
                logger.error("Failed to search emails")
                return []
                
            email_ids = messages[0].split()
            # Get the most recent emails first
            email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
            email_ids.reverse()  # Most recent first
            
            emails = []
            for email_id in email_ids:
                status, msg_data = self.imap_conn.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                    
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Parse email
                parsed_email = {
                    'id': email_id.decode(),
                    'subject': self._decode_header(email_message['Subject']),
                    'from': self._decode_header(email_message['From']),
                    'to': self._decode_header(email_message['To']),
                    'date': email_message['Date'],
                    'body': self._get_body(email_message),
                    'attachments': self._get_attachments(email_message)
                }
                emails.append(parsed_email)
                
            logger.info(f"Read {len(emails)} emails from {folder}")
            return emails
            
        except Exception as e:
            logger.error(f"Error reading emails: {e}")
            return []
    
    def send_email(self, to: str, subject: str, body: str, 
                   cc: str = None, bcc: str = None,
                   attachments: List[str] = None) -> bool:
        """
        Send an email
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            cc: CC recipient (optional)
            bcc: BCC recipient (optional)
            attachments: List of file paths to attach (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.smtp_conn:
            logger.error("SMTP not authenticated")
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = cc
            if bcc:
                msg['Bcc'] = bcc
                
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
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
                        logger.warning(f"Attachment file not found: {file_path}")
            
            # Send email
            recipients = [to]
            if cc:
                recipients.append(cc)
            if bcc:
                recipients.append(bcc)
                
            text = msg.as_string()
            self.smtp_conn.sendmail(self.email_address, recipients, text)
            logger.info(f"Email sent to {to}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def download_attachments(self, email_id: str, 
                           download_dir: str = "./attachments") -> List[str]:
        """
        Download attachments from a specific email
        
        Args:
            email_id: Email ID to process
            download_dir: Directory to save attachments
            
        Returns:
            List of downloaded file paths
        """
        if not self.imap_conn:
            logger.error("IMAP not authenticated")
            return []
            
        try:
            os.makedirs(download_dir, exist_ok=True)
            status, msg_data = self.imap_conn.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                logger.error(f"Failed to fetch email {email_id}")
                return []
                
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            downloaded_files = []
            for part in email_message.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                    
                filename = part.get_filename()
                if filename:
                    filename = self._decode_header(filename)
                    filepath = os.path.join(download_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    
                    downloaded_files.append(filepath)
                    logger.info(f"Downloaded attachment: {filename}")
            
            return downloaded_files
            
        except Exception as e:
            logger.error(f"Error downloading attachments: {e}")
            return []
    
    def mark_as_read(self, email_id: str) -> bool:
        """Mark an email as read"""
        if not self.imap_conn:
            logger.error("IMAP not authenticated")
            return False
            
        try:
            self.imap_conn.store(email_id, '+FLAGS', '\\Seen')
            logger.info(f"Marked email {email_id} as read")
            return True
        except Exception as e:
            logger.error(f"Error marking email as read: {e}")
            return False
    
    def delete_email(self, email_id: str) -> bool:
        """Mark an email for deletion"""
        if not self.imap_conn:
            logger.error("IMAP not authenticated")
            return False
            
        try:
            self.imap_conn.store(email_id, '+FLAGS', '\\Deleted')
            logger.info(f"Marked email {email_id} for deletion")
            return True
        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False
    
    def expunge(self) -> bool:
        """Permanently remove deleted emails"""
        if not self.imap_conn:
            logger.error("IMAP not authenticated")
            return False
            
        try:
            self.imap_conn.expunge()
            logger.info("Expunged deleted emails")
            return True
        except Exception as e:
            logger.error(f"Error expunging: {e}")
            return False
    
    def disconnect(self):
        """Close all connections"""
        try:
            if self.imap_conn:
                self.imap_conn.close()
                self.imap_conn.logout()
                logger.info("IMAP disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting IMAP: {e}")
        
        try:
            if self.smtp_conn:
                self.smtp_conn.quit()
                logger.info("SMTP disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting SMTP: {e}")
    
    # Helper methods
    def _decode_header(self, header) -> str:
        """Decode email header"""
        if header is None:
            return ""
        try:
            decoded_parts = email.header.decode_header(header)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += part
            return decoded_string
        except Exception:
            return str(header) if header else ""
    
    def _get_body(self, email_message) -> str:
        """Extract body from email"""
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8')
                        break
                    except:
                        continue
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8')
            except:
                body = str(email_message.get_payload())
        return body
    
    def _get_attachments(self, email_message) -> List[Dict[str, str]]:
        """Get attachment information"""
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

def interactive_mode():
    """Interactive command-line interface"""
    bot = EmailBot()
    
    print("=== Email Bot for Kronos00bot@gmail.com ===")
    print("Choose an option:")
    print("1. Authenticate")
    print("2. Read emails")
    print("3. Send email")
    print("4. Download attachments from email")
    print("5. Mark email as read")
    print("6. Delete email")
    print("7. Disconnect")
    print("8. Exit")
    
    while True:
        try:
            choice = input("\nEnter choice (1-8): ").strip()
            
            if choice == "1":
                password = getpass.getpass("Enter app password: ")
                if bot.authenticate_imap(password) and bot.authenticate_smtp(password):
                    print("✅ Authentication successful")
                else:
                    print("❌ Authentication failed")
                    
            elif choice == "2":
                if not bot.imap_conn:
                    print("❌ Please authenticate first")
                    continue
                folder = input("Folder (default INBOX): ").strip() or "INBOX"
                limit = input("Limit (default 10): ").strip()
                limit = int(limit) if limit.isdigit() else 10
                unseen = input("Unseen only? (y/N): ").strip().lower() == 'y'
                
                emails = bot.read_emails(folder=folder, limit=limit, unseen_only=unseen)
                print(f"\n📧 Found {len(emails)} emails:")
                for i, email in enumerate(emails, 1):
                    print(f"{i}. From: {email['from']}")
                    print(f"   Subject: {email['subject']}")
                    print(f"   Date: {email['date']}")
                    print(f"   ID: {email['id']}")
                    if email['attachments']:
                        print(f"   📎 Attachments: {[a['filename'] for a in email['attachments']]}")
                    print()
                    
            elif choice == "3":
                if not bot.smtp_conn:
                    print("❌ Please authenticate first")
                    continue
                to = input("To: ").strip()
                subject = input("Subject: ").strip()
                body = input("Body: ").strip()
                cc = input("CC (optional): ").strip() or None
                bcc = input("BCC (optional): ").strip() or None
                
                attach_input = input("Attachment paths (comma-separated, optional): ").strip()
                attachments = [p.strip() for p in attach_input.split(",")] if attach_input else None
                
                if bot.send_email(to, subject, body, cc, bcc, attachments):
                    print("✅ Email sent successfully")
                else:
                    print("❌ Failed to send email")
                    
            elif choice == "4":
                if not bot.imap_conn:
                    print("❌ Please authenticate first")
                    continue
                email_id = input("Email ID: ").strip()
                download_dir = input("Download directory (default ./attachments): ").strip() or "./attachments"
                
                files = bot.download_attachments(email_id, download_dir)
                if files:
                    print(f"✅ Downloaded {len(files)} attachments:")
                    for f in files:
                        print(f"   - {f}")
                else:
                    print("❌ No attachments downloaded")
                    
            elif choice == "5":
                if not bot.imap_conn:
                    print("❌ Please authenticate first")
                    continue
                email_id = input("Email ID to mark as read: ").strip()
                if bot.mark_as_read(email_id):
                    print("✅ Email marked as read")
                else:
                    print("❌ Failed to mark email as read")
                    
            elif choice == "6":
                if not bot.imap_conn:
                    print("❌ Please authenticate first")
                    continue
                email_id = input("Email ID to delete: ").strip()
                if bot.delete_email(email_id):
                    print("✅ Email marked for deletion (use expunge to permanently remove)")
                else:
                    print("❌ Failed to mark email for deletion")
                    
            elif choice == "7":
                bot.disconnect()
                print("👋 Disconnected")
                
            elif choice == "8":
                bot.disconnect()
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice")
                
        except KeyboardInterrupt:
            bot.disconnect()
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Check if running interactively or with arguments
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        print("Email Bot for Kronos00bot@gmail.com")
        print("Run with --interactive for command-line interface")
        print("Or import and use the EmailBot class in your code")