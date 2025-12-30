from fastapi import APIRouter, UploadFile, File, HTTPException
from starlette import status

from ..resume.store import save_resume, save_profile
from ..resume.parser import parse_resume

router = APIRouter()


@router.post("/resume", status_code=status.HTTP_200_OK)
async def upload_resume(file: UploadFile = File(...)):
    """Upload resume PDF, store it, and immediately parse it.

    Input: multipart/form-data with field 'file' (PDF)
    Output: Resume stored and parsed, profile saved to resume_profile.json
    """
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing file.",
        )

    # Store resume PDF
    resume_path = await save_resume(file)

    try:
        # Parse resume with OpenAI
        profile = parse_resume()

        # Save profile to JSON
        profile_path = save_profile(profile)

        # Return response with parsed data (exclude raw_text)
        return {
            "message": "Resume uploaded and parsed successfully",
            "resume_path": resume_path,
            "profile_path": profile_path,
            "name": profile.get("name", ""),
            "current_title": profile.get("current_title", ""),
            "summary": profile.get("summary", ""),
            "skills": profile.get("skills", []),
            "experience": profile.get("experience", []),
            "projects": profile.get("projects", []),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse resume: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse resume: {str(e)}",
        )
