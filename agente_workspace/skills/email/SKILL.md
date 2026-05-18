# Email Skill for OpenClaw

Provides Gmail/IMAP/SMTP email capabilities for reading, sending, and managing emails.

## Configuration

Requires Gmail App Password (enable 2-factor authentication first):

1. Go to [Google Account](https://myaccount.google.com/)
2. Security → 2-Step Verification (must be enabled)
3. App passwords → Generate new → Select "Mail" and device
4. Use the 16-character password generated

## Dependencies

- Python 3.6+
- imaplib (standard library)
- smtplib (standard library)
- email (standard library)

## Usage

### Via CLI (Interactive)

```bash
python3 -m skills.email.email_bot --interactive
```

### Via Python API

```python
from skills.email.email_bot import EmailBot

bot = EmailBot()
if bot.authenticate_imap("YOUR_APP_PASSWORD") and bot.authenticate_smtp():
    # Read unread emails
    emails = bot.read_emails(limit=10)
    
    for email in emails:
        print(f"From: {email['from']}")
        print(f"Subject: {email['subject']}")
        
    # Send email
    bot.send_email(
        to="recipient@example.com",
        subject="Test from OpenClaw Email Skill",
        body="This email was sent via the OpenClaw email skill."
    )
    
    bot.disconnect()
```

## Available Functions

### EmailBot Class

#### Authentication
- `authenticate_imap(password)` - Authenticate to IMAP server
- `authenticate_smtp(password=None)` - Authenticate to SMTP server (uses IMAP password if not provided)

### Email Operations
- `read_emails(folder="INBOX", limit=10, unseen_only=True)` - Read emails from folder
- `send_email(to, subject, body, cc=None, bcc=None, attachments=None)` - Send email
- `download_attachments(email_id, download_dir="./attachments")` - Download attachments from email
- `mark_as_read(email_id)` - Mark email as read
- `delete_email(email_id)` - Mark email for deletion
- `expunge()` - Permanently delete marked emails

### Connection Management
- `disconnect()` - Close IMAP and SMTP connections

## Examples

### Check for urgent emails
```python
bot = EmailBot()
if bot.authenticate_imap(app_pass) and bot.authenticate_smtp():
    urgent = bot.read_emails(folder="INBOX", limit=5, unseen_only=True)
    for email in urgent:
        if "urgent" in email['subject'].lower() or "important" in email['subject'].lower():
            print(f"URGENT: {email['subject']} from {email['from']}")
    bot.disconnect()
```

### Send report with attachment
```python
bot = EmailBot()
bot.authenticate_imap(app_pass)
bot.authenticate_smtp()

bot.send_email(
    to="team@example.com",
    subject="Daily Report",
    body="Please find attached the daily report.",
    attachments=["./reports/daily.pdf"]
)

bot.disconnect()
```

## Security Notes

- App passwords are required for Gmail (regular passwords won't work with 2FA)
- Credentials are used only during the session and not stored
- Always call `disconnect()` when finished
- Consider using environment variables for passwords in production

## Error Handling

All methods return boolean success status or appropriate data structures.
Errors are logged via Python's logging module.

## Implementation Details

- Uses IMAP over SSL (port 993)
- Uses SMTP with STARTTLS (port 587)
- Handles MIME multipart messages for attachments
- Properly decodes email headers (UTF-8, etc.)
- Supports both plain text and HTML emails (text extraction)

## Related Skills

- None specific, but can be combined with:
  - `memory` for storing email history
  - `cron` for scheduled email checking
  - `sessions_spawn` for background email processing

---
*Skill created for OpenClaw workspace. Integrates with native Python email libraries.*