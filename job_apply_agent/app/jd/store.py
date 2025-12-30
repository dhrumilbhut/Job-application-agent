from fastapi import HTTPException
from starlette import status
import json
from datetime import datetime
from pathlib import Path

from ..config import JD_DATA_PATH, JDS_DIR


def _timestamped_jd_path() -> Path:
    """Return a unique JD path to avoid overwriting previous submissions."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return JDS_DIR / f"jd-{ts}.json"


def save_jd(jd_data: dict) -> str:
    """Save parsed JD to disk with history and latest pointer.

    Writes a timestamped copy under storage/jds/ and refreshes
    storage/current_jd.json as the "latest" pointer. This prevents
    state corruption when multiple JDs are submitted back-to-back.

    Args:
        jd_data: Dict with keys: company, role, key_skills, summary, raw_text

    Returns:
        Path to the saved JD JSON file (timestamped copy)

    Raises:
        HTTPException on write failure
    """
    jd_history_path = _timestamped_jd_path()

    try:
        # Write immutable, timestamped copy
        with jd_history_path.open("w", encoding="utf-8") as f:
            json.dump(jd_data, f, indent=2, ensure_ascii=False)

        # Refresh the latest pointer
        with JD_DATA_PATH.open("w", encoding="utf-8") as f:
            json.dump(jd_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save JD data: {e}",
        )

    return str(jd_history_path)
