"""Resume storage utilities."""

from fastapi import UploadFile, HTTPException
from starlette import status
import json
from pathlib import Path

from ..config import RESUME_PATH, MAX_RESUME_SIZE_BYTES, MAX_RESUME_SIZE_MB, STORAGE_DIR
from ..utils.pdf_utils import validate_pdf_header


async def save_resume(file: UploadFile) -> str:
    """Validate and store the uploaded resume PDF.
    
    Performs these checks:
    - File extension is .pdf
    - PDF magic header is valid
    - File is not empty
    - File does not exceed size limit (default 10MB)
    
    Overwrites any existing resume.pdf.
    
    Args:
        file: Uploaded PDF file
        
    Returns:
        Path to saved resume file
        
    Raises:
        HTTPException: If validation fails or storage error occurs
    """
    filename = (file.filename or "").lower().strip()

    if not filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only .pdf is allowed.",
        )

    # Content-Type is advisory; we'll validate PDF header instead
    total_bytes = 0
    header_checked = False

    try:
        with RESUME_PATH.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # Read in 1MB chunks
                if not chunk:
                    break
                    
                total_bytes += len(chunk)
                
                # Check size limit
                if total_bytes > MAX_RESUME_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Resume too large. Max {MAX_RESUME_SIZE_MB}MB.",
                    )
                
                # Check PDF header on first chunk
                if not header_checked:
                    if not validate_pdf_header(chunk):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid PDF header.",
                        )
                    header_checked = True
                
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file.",
            )

    except HTTPException:
        # Re-raise controlled errors
        # Ensure partial writes don't leave corrupt files
        if RESUME_PATH.exists():
            try:
                RESUME_PATH.unlink()
            except Exception:
                pass
        raise
    except Exception:
        # Any unexpected failure
        if RESUME_PATH.exists():
            try:
                RESUME_PATH.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store resume.",
        )

    return str(RESUME_PATH)


def save_profile(profile_data: dict) -> str:
    """Save parsed resume profile to JSON file.
    
    Persists the parsed resume data (name, title, skills, experience, projects)
    to storage/resume_profile.json for later use in email generation.

    Args:
        profile_data: Dict containing parsed resume fields
        
    Returns:
        Path to the saved profile JSON file
        
    Raises:
        HTTPException on write failure
    """
    profile_path = STORAGE_DIR / "resume_profile.json"

    try:
        with profile_path.open("w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save resume profile: {e}",
        )

    return str(profile_path)
