"""Application logging for sent emails."""

import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from ..config import APPLICATIONS_LOG_PATH


def log_application(
    recipient_email: str,
    company: str,
    role: str,
    subject: str,
    status: str = "sent",
    notes: str = "",
) -> Dict[str, Any]:
    """Log a sent application to the applications log.
    
    Each log entry contains:
    - timestamp: When the email was sent
    - recipient_email: Email address
    - company: Company name
    - role: Job title
    - subject: Email subject
    - status: "sent", "failed", or other status
    - notes: Any additional notes or error messages
    
    Args:
        recipient_email: Recipient email address
        company: Company name
        role: Job role/title
        subject: Email subject line
        status: Sending status (default: "sent")
        notes: Optional notes or error message
        
    Returns:
        Dict with log entry details
        
    Raises:
        ValueError: If log writing fails
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "recipient_email": recipient_email,
        "company": company,
        "role": role,
        "subject": subject,
        "status": status,
        "notes": notes,
    }
    
    try:
        # Read existing logs if file exists
        logs = []
        if APPLICATIONS_LOG_PATH.exists():
            with APPLICATIONS_LOG_PATH.open("r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    # Each line is a JSON log entry
                    for line in content.split("\n"):
                        if line.strip():
                            logs.append(json.loads(line))
        
        # Append new entry
        logs.append(log_entry)
        
        # Write updated logs (JSONL format: one JSON object per line)
        with APPLICATIONS_LOG_PATH.open("w", encoding="utf-8") as f:
            for log in logs:
                f.write(json.dumps(log) + "\n")
        
        return log_entry
    
    except Exception as e:
        raise ValueError(f"Failed to write application log: {str(e)}")


def get_application_history() -> list:
    """Get all logged applications.
    
    Returns:
        List of log entries (dicts)
    """
    if not APPLICATIONS_LOG_PATH.exists():
        return []
    
    logs = []
    try:
        with APPLICATIONS_LOG_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
    except Exception:
        return []
    
    return logs
