"""Job application routes."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body
from starlette import status
import tempfile
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from ..jd.parser import parse_jd
from ..jd.store import save_jd
from ..email.generator import compose_full_email, load_resume_profile, load_jd_data
from ..utils.pdf_utils import validate_pdf_header
from ..mail.sender import send_email
from ..mail.logger import log_application
from ..config import SENDER_EMAIL


class PreparedEmailPayload(BaseModel):
    """Payload for sending a pre-generated email to avoid recompute.
    
    If provided, the send-email endpoint will skip decision + compose
    and use these values directly.
    """

    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    sender: Optional[str] = None
    decision: Optional[dict] = None
from ..v2.agents import analyze_jd, analyze_resume, decide

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

        # Run V2 decision agents
        decision_info = None
        try:
            # Analyze JD using V2 agent
            jd_profile = analyze_jd(jd_data)
            
            # Load resume profile and analyze it
            resume_profile = load_resume_profile()
            if resume_profile:
                resume_intelligence = analyze_resume(resume_profile)
                
                # Get decision from decision agent
                decision = decide(jd_profile, resume_intelligence)
                decision_info = {
                    "decision": decision.decision,
                    "reasons": decision.reasons,
                    "blockers": decision.blockers,
                    "confidence": decision.confidence,
                }
        except Exception as e:
            # Log decision error but don't block apply endpoint
            print(f"Decision agent error: {str(e)}")
            decision_info = None

        # Return parsed JD with decision info (exclude raw_text from response)
        response = {
            "status": "parsed",
            "jd_path": jd_path,
            "company": jd_data.get("company", ""),
            "role": jd_data.get("role", ""),
            "key_skills": jd_data.get("key_skills", []),
            "summary": jd_data.get("summary", ""),
        }
        
        # Add decision info if available
        if decision_info:
            response["decision"] = decision_info
        
        return response

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


@router.post("/prepare-application", status_code=status.HTTP_200_OK)
async def prepare_application(
    jd_file: UploadFile = File(...),
    email: str = Query(None),
    force: bool = Query(False),
):
    """Upload JD, run decision agents, and return email preview (no send).

    Flow:
    1) Parse JD (V1) and persist.
    2) Analyze JD + Resume (V2 agents) → decision.
    3) Generate email (V1) using JD/resume and optional email override.
    4) Return decision + email preview + can_send flag (SKIP blocks unless force).

    Args:
        jd_file: Job description PDF.
        email: Optional recipient override. If absent, JD email is used.
        force: If true, allows send even when decision is SKIP.

    Returns:
        Parsed JD fields, decision info, email preview, and can_send flag.
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

    try:
        # Save JD to temp
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

        # Parse JD (V1) and persist
        jd_data = parse_jd(tmp_path)
        jd_path = save_jd(jd_data)

        # Clean temp
        Path(tmp_path).unlink()

        # Ensure resume is available
        resume_profile = load_resume_profile()
        if not resume_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume not found. Upload resume first via /resume.",
            )

        # Run decision agents (V2)
        decision_info = None
        decision_code = None
        try:
            jd_profile = analyze_jd(jd_data)
            resume_intelligence = analyze_resume(resume_profile)
            decision = decide(jd_profile, resume_intelligence)
            decision_code = decision.decision
            decision_info = {
                "decision": decision.decision,
                "reasons": decision.reasons,
                "blockers": decision.blockers,
                "confidence": decision.confidence,
            }
        except Exception as e:
            # Graceful degradation: allow flow to continue
            print(f"Decision agent error: {str(e)}")
            decision_info = None

        # Compose email preview (V1)
        email_obj = compose_full_email(resume_profile, jd_data, recipient_email=email)

        # Determine if send should be allowed
        can_send = True
        if not force and decision_code == "SKIP":
            can_send = False

        response = {
            "status": "prepared",
            "jd_path": jd_path,
            "company": jd_data.get("company", ""),
            "role": jd_data.get("role", ""),
            "key_skills": jd_data.get("key_skills", []),
            "summary": jd_data.get("summary", ""),
            "decision": decision_info,
            "email": {
                "to": email_obj["to"],
                "from": email_obj["from"],
                "subject": email_obj["subject"],
                "body": email_obj["body"],
            },
            "can_send": can_send,
            "force": force,
        }

        # If SKIP and not forced, add helper message
        if decision_code == "SKIP" and not force:
            response["message"] = "Decision is SKIP. Sending is blocked unless force=true."

        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to prepare application: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare application: {str(e)}",
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
async def send_email_endpoint(
    email: str = Query(None),
    prepared: Optional[PreparedEmailPayload] = Body(None),
):
    """Send email, optionally using a pre-generated payload to avoid recompute.

    If `prepared` is provided (from /prepare-application), we skip running
    decision + compose and send exactly what the user reviewed. Otherwise,
    we follow the existing decision + compose flow.
    """

    try:
        # Load stored data
        resume_profile = load_resume_profile()
        jd_data = load_jd_data()

        decision_info = None
        decision_code = None

        # If prepared payload exists, use it directly to avoid second OpenAI call
        if prepared and prepared.subject and prepared.body:
            recipient = (prepared.to or email or jd_data.get("email", "")).strip()
            if not recipient:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No recipient email found. Provide email query param or prepared.to.",
                )

            sender_email = prepared.sender or SENDER_EMAIL
            if not sender_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sender email not configured.",
                )

            email_obj = {
                "to": recipient,
                "from": sender_email,
                "subject": prepared.subject,
                "body": prepared.body,
            }

            if prepared.decision:
                decision_info = prepared.decision
                decision_code = prepared.decision.get("decision")

            # If decision is SKIP and no override, block
            if decision_code == "SKIP":
                company = jd_data.get("company", "Unknown Company").strip()
                role = jd_data.get("role", "Unknown Role").strip()

                log_application(
                    recipient_email=recipient,
                    company=company,
                    role=role,
                    subject=prepared.subject,
                    status="skipped",
                    notes="Decision: SKIP (prepared payload)",
                )

                return {
                    "status": "skipped",
                    "message": "Application skipped due to decision logic",
                    "company": company,
                    "role": role,
                    "decision": decision_info,
                }

        else:
            # Run decision logic to check if should send
            try:
                jd_profile = analyze_jd(jd_data)

                if resume_profile:
                    resume_intelligence = analyze_resume(resume_profile)

                    decision = decide(jd_profile, resume_intelligence)
                    decision_info = {
                        "decision": decision.decision,
                        "reasons": decision.reasons,
                        "blockers": decision.blockers,
                        "confidence": decision.confidence,
                    }
                    decision_code = decision.decision

                    # If decision is SKIP, return early without sending
                    if decision.decision == "SKIP":
                        company = jd_data.get("company", "Unknown Company").strip()
                        role = jd_data.get("role", "Unknown Role").strip()

                        log_application(
                            recipient_email=email or "unknown",
                            company=company,
                            role=role,
                            subject="",
                            status="skipped",
                            notes=f"Decision: SKIP. Blockers: {', '.join(decision.blockers)}",
                        )

                        return {
                            "status": "skipped",
                            "message": "Application skipped due to decision logic",
                            "company": company,
                            "role": role,
                            "decision": decision_info,
                        }
            except Exception as e:
                # Log decision error but proceed with sending (safe fallback)
                print(f"Decision agent error: {str(e)}")
                # Continue to send email (graceful degradation)

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

        notes = "Email sent successfully with resume attached"
        if decision_info:
            notes += f"; Decision: {decision_info['decision']}"

        log_entry = log_application(
            recipient_email=email_obj["to"],
            company=company,
            role=role,
            subject=email_obj["subject"],
            status="sent",
            notes=notes,
        )

        response = {
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

        # Add decision info if available
        if decision_info:
            response["decision"] = decision_info

        return response

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
