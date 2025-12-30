"""Email sender module using SMTP."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, Any

from ..config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_USE_TLS,
    RESUME_PATH,
    validate_smtp_config,
)


def send_email(
    recipient_email: str,
    subject: str,
    body: str,
    sender_email: str,
    attach_resume: bool = True,
) -> Dict[str, Any]:
    """Send an email with optional resume attachment via SMTP.
    
    Args:
        recipient_email: Email address to send to
        subject: Email subject line
        body: Email body (plain text)
        sender_email: Sender email address
        attach_resume: If True, attach the stored resume PDF
        
    Returns:
        Dict with keys:
            - status: "sent" if successful
            - message: Success/error message
            - recipient: Recipient email
            - subject: Email subject
            
    Raises:
        ValueError: If SMTP config invalid or email sending fails
    """
    # Validate SMTP configuration
    try:
        validate_smtp_config()
    except ValueError as e:
        raise ValueError(f"SMTP configuration error: {str(e)}")
    
    # Validate inputs
    if not recipient_email or "@" not in recipient_email:
        raise ValueError(f"Invalid recipient email: {recipient_email}")
    
    if not subject or not body:
        raise ValueError("Subject and body cannot be empty")
    
    try:
        # Create email message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = subject
        
        # Add body
        message.attach(MIMEText(body, "plain"))
        
        # Attach resume if requested and exists
        if attach_resume and RESUME_PATH.exists():
            try:
                with open(RESUME_PATH, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {RESUME_PATH.name}",
                    )
                    message.attach(part)
            except Exception as e:
                raise ValueError(f"Failed to attach resume: {str(e)}")
        
        # Send email via SMTP
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls()
            
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        
        return {
            "status": "sent",
            "message": f"Email sent successfully to {recipient_email}",
            "recipient": recipient_email,
            "subject": subject,
        }
    
    except smtplib.SMTPAuthenticationError as e:
        raise ValueError(f"SMTP authentication failed: {str(e)}")
    except smtplib.SMTPException as e:
        raise ValueError(f"SMTP error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to send email: {str(e)}")
