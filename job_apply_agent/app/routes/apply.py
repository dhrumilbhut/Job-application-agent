"""Job application routes."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from starlette import status
import tempfile
from pathlib import Path

from ..jd.parser import parse_jd
from ..jd.store import save_jd
from ..email.generator import compose_full_email, load_resume_profile, load_jd_data
from ..utils.pdf_utils import validate_pdf_header
from ..mail.sender import send_email
from ..mail.logger import log_application

router = APIRouter()


@router.post("/apply", status_code=status.HTTP_200_OK)
async def apply_to_job(jd_file: UploadFile = File(...)):
    """Submit a job description and prepare application.
    
    Accepts a job description PDF, parses it to extract company, role, and
    required skills, then saves it for email generation.
    
    Input: multipart/form-data with field 'jd_file' (PDF)
    Output: Parsed JD saved to storage/current_jd.json
    
    Args:
        jd_file: Job description PDF file
        
    Returns:
        JSON with parsed JD fields: company, role, key_skills, summary
        
    Raises:
        400: Invalid file type, invalid PDF, or parsing error
        500: Storage or API failure
    """
    if jd_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing jd_file.",
        )

    filename = (jd_file.filename or "").lower().strip()
    if not filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only .pdf is allowed.",
        )

    # Save JD to temporary location for parsing
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            content = await jd_file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Validate PDF header
        with open(tmp_path, "rb") as f:
            header = f.read(4)
            if not validate_pdf_header(header):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid PDF header.",
                )

        # Parse JD with OpenAI
        jd_data = parse_jd(tmp_path)

        # Save JD data to persistent storage
        jd_path = save_jd(jd_data)

        # Clean up temp file
        Path(tmp_path).unlink()

        # Return parsed JD (exclude raw_text from response)
        return {
            "status": "parsed",
            "jd_path": jd_path,
            "company": jd_data.get("company", ""),
            "role": jd_data.get("role", ""),
            "key_skills": jd_data.get("key_skills", []),
            "summary": jd_data.get("summary", ""),
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse JD: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse JD: {str(e)}",
        )


@router.get("/generate-email", status_code=status.HTTP_200_OK)
async def generate_email_endpoint(email: str = Query(None)):
    """Generate a cold application email using stored resume and JD data.
    
    Uses the most recently parsed resume (from POST /resume) and job description
    (from POST /apply) to generate a tailored, concise cold email.
    
    If the job description contains a contact email, it will be used automatically.
    Otherwise, you must provide the recipient email as a query parameter.
    
    Requirements:
    - Must have uploaded resume via POST /resume first
    - Must have submitted JD via POST /apply first
    - Must have email in JD OR provide ?email=hiring@company.com query parameter
    
    Query Parameters:
        email (optional): Recipient email address. Required if JD has no email field.
    
    Returns:
        JSON with email fields: subject, body, from, to
        
    Raises:
        400: Resume or JD data not found, or no email available
        500: Email generation failure
    """
    try:
        # Load stored data
        resume_profile = load_resume_profile()
        jd_data = load_jd_data()
        
        # Compose email (pass recipient_email if provided)
        email_obj = compose_full_email(resume_profile, jd_data, recipient_email=email)
        
        return {
            "status": "generated",
            "subject": email_obj["subject"],
            "body": email_obj["body"],
            "from": email_obj["from"],
            "to": email_obj["to"],
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate email: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate email: {str(e)}",
        )


@router.post("/send-email", status_code=status.HTTP_200_OK)
async def send_email_endpoint(email: str = Query(None)):
    """Generate and send a cold application email with resume attachment.
    
    Combines email generation with actual sending via SMTP. Attaches the
    stored resume PDF and logs the application to applications.log.
    
    Requirements:
    - Must have uploaded resume via POST /resume first
    - Must have submitted JD via POST /apply first
    - Must have valid SMTP configuration in .env
    - Must have email in JD OR provide ?email=hiring@company.com query parameter
    
    Query Parameters:
        email (optional): Recipient email address. Required if JD has no email field.
    
    Returns:
        JSON with sending status and application log entry
        
    Raises:
        400: Resume or JD data not found, no email, or invalid SMTP config
        500: Email sending or logging failure
    """
    try:
        # Load stored data
        resume_profile = load_resume_profile()
        jd_data = load_jd_data()
        
        # Compose complete email
        email_obj = compose_full_email(resume_profile, jd_data, recipient_email=email)
        
        # Send email with resume attachment
        send_result = send_email(
            recipient_email=email_obj["to"],
            subject=email_obj["subject"],
            body=email_obj["body"],
            sender_email=email_obj["from"],
            attach_resume=True,
        )
        
        # Log the application
        company = jd_data.get("company", "Unknown Company").strip()
        role = jd_data.get("role", "Unknown Role").strip()
        
        log_entry = log_application(
            recipient_email=email_obj["to"],
            company=company,
            role=role,
            subject=email_obj["subject"],
            status="sent",
            notes="Email sent successfully with resume attached",
        )
        
        return {
            "status": "sent",
            "message": send_result["message"],
            "email": {
                "to": email_obj["to"],
                "from": email_obj["from"],
                "subject": email_obj["subject"],
            },
            "company": company,
            "role": role,
            "logged_at": log_entry["timestamp"],
        }
        
    except FileNotFoundError as e:
        # Log failed attempt even when JD is missing
        try:
            log_application(
                recipient_email=email or "unknown",
                company="Unknown Company",
                role="Unknown Role",
                subject="",
                status="failed",
                notes=str(e),
            )
        finally:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    except ValueError as e:
        # Try to log failed attempt
        try:
            jd_data = load_jd_data()
            company = jd_data.get("company", "Unknown Company").strip()
            role = jd_data.get("role", "Unknown Role").strip()
            log_application(
                recipient_email=email or "unknown",
                company=company,
                role=role,
                subject="",
                status="failed",
                notes=str(e),
            )
        except Exception:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to send email: {str(e)}",
        )
    except Exception as e:
        try:
            log_application(
                recipient_email=email or "unknown",
                company="Unknown Company",
                role="Unknown Role",
                subject="",
                status="failed",
                notes=str(e),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}",
        )


@router.get("/applications", status_code=status.HTTP_200_OK)
async def get_applications_history():
    """Get history of all sent applications.
    
    Returns a list of all logged applications in chronological order.
    
    Returns:
        JSON with array of application log entries, each containing:
        - timestamp: When the email was sent
        - recipient_email: Email address
        - company: Company name
        - role: Job role
        - subject: Email subject
        - status: "sent", "failed", etc.
        - notes: Any additional notes or error messages
    """
    try:
        from ..mail.logger import get_application_history
        
        history = get_application_history()
        
        return {
            "status": "success",
            "total_applications": len(history),
            "applications": history,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve application history: {str(e)}",
        )
