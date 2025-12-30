from pathlib import Path
import os
from dotenv import load_dotenv

# Project root is the folder containing 'job_apply_agent' and 'storage'
ROOT_DIR = Path(__file__).resolve().parents[2]

# Load .env file — try job_apply_agent root first, then workspace root
JOB_APPLY_AGENT_DIR = Path(__file__).resolve().parents[1]
env_paths = [
    JOB_APPLY_AGENT_DIR / ".env",  # job_apply_agent/.env
    ROOT_DIR / ".env",              # workspace root/.env
]
for env_file in env_paths:
    if env_file.exists():
        load_dotenv(env_file)
        break

STORAGE_DIR = ROOT_DIR / "storage"
JDS_DIR = STORAGE_DIR / "jds"
RESUME_PATH = STORAGE_DIR / "resume.pdf"
RESUME_PROFILE_PATH = STORAGE_DIR / "resume_profile.json"
JD_DATA_PATH = STORAGE_DIR / "current_jd.json"  # pointer to latest JD
APPLICATIONS_LOG_PATH = STORAGE_DIR / "applications.log"

# Size limit in MB (default: 10MB). Can be overridden via env var.
MAX_RESUME_SIZE_MB = int(os.getenv("JAA_MAX_RESUME_SIZE_MB", "10"))
MAX_RESUME_SIZE_BYTES = MAX_RESUME_SIZE_MB * 1024 * 1024

# Sender email address for outgoing emails. Must be set in .env
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
if not SENDER_EMAIL:
    raise ValueError(
        "SENDER_EMAIL not configured. Please set SENDER_EMAIL in your .env file."
    )

# SMTP Configuration for email sending (Phase 5)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))  # Default to TLS port
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

# Validate SMTP config only if email sending will be used
def validate_smtp_config():
    """Validate that all SMTP settings are configured."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        raise ValueError(
            "SMTP not fully configured. Please set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env"
        )

# Ensure storage directories exist (safe, idempotent)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
JDS_DIR.mkdir(parents=True, exist_ok=True)
