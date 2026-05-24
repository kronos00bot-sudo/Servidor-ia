#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/mloco/Escritorio/workspace')
from check_email import EmailManager

def main():
    email_manager = EmailManager()
    if not email_manager.connect_imap() or not email_manager.connect_smtp():
        print("❌ Failed to connect to email servers")
        return False
    
    # Send email
    success = email_manager.send_email(
        to="mcozzolinoes@gmail.com",
        subject="Teste",
        body="Teste"
    )
    
    email_manager.disconnect()
    return success

if __name__ == "__main__":
    if main():
        print("✅ Email sent successfully")
    else:
        print("❌ Failed to send email")
        sys.exit(1)