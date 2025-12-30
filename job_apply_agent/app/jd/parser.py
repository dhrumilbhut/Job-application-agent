"""Job Description PDF parser using OpenAI."""

import os
from typing import Dict, Any

from ..utils.pdf_utils import extract_text_from_pdf
from ..utils.openai_utils import call_openai_for_json, fill_defaults


def parse_jd(pdf_path: str) -> Dict[str, Any]:
    """Parse job description from PDF and extract structured information.
    
    Reads a JD PDF file, extracts text, and uses OpenAI to parse it
    into structured fields: company, role, key_skills, summary.
    
    Args:
        pdf_path: Path to JD PDF
        
    Returns:
        Dict with keys:
            - company: Company name (string)
            - role: Job title/role (string)
            - key_skills: List of required skills (array)
            - summary: Brief job summary (string)
            - email: Contact email if found (string, may be empty)
            - raw_text: Full text extracted from PDF
            
    Raises:
        ValueError: If PDF not found, cannot be read, or OpenAI call fails
    """
    # Check file exists
    if not os.path.exists(pdf_path):
        raise ValueError(f"JD file not found: {pdf_path}")

    # Extract text from PDF
    raw_text = extract_text_from_pdf(pdf_path)
    
    if not raw_text or not raw_text.strip():
        raise ValueError("Job description PDF is empty")

    # Define what we want OpenAI to extract
    system_prompt = """\
You are a job description parser. Extract structured information from the JD text.

Return ONLY a valid JSON object with these exact fields:
{
  "company": "company name (string or empty)",
  "role": "job title/role (string or empty)",
  "key_skills": ["skill1", "skill2", ...] (array of strings),
  "summary": "detailed job requirements summary (string or empty)",
  "email": "contact email address if found (string or empty)"
}

Rules:
- Extract ONLY information explicitly in the JD
- Do NOT invent or hallucinate skills, requirements, or benefits
- key_skills should be technical and domain-specific skills mentioned in the JD
- summary: Create a DETAILED, MULTI-POINT summary that includes:
  * Main job focus and responsibilities
  * Required technical skills and experience
  * Nice-to-have qualifications
  * Key team interactions and work environment
  * Any specialized areas (e.g., AI/ML for developer roles)
  * Summary should be 150-250 words, structured with bullet points or numbered items
- email: Look for hiring/recruiter/HR contact email in the JD (e.g., careers@, hiring@, hr@, recruiter email)
- Use empty string "" for missing company/role/summary/email
- Use empty array [] for missing key_skills
- Return valid JSON only, no other text
"""

    user_prompt = f"Parse this job description:\n\n{raw_text}"

    # Call OpenAI to parse JD
    parsed = call_openai_for_json(system_prompt, user_prompt, max_tokens=1000)

    # Ensure all expected fields are present
    defaults = {
        "company": "",
        "role": "",
        "key_skills": [],
        "summary": "",
        "email": "",
    }
    parsed = fill_defaults(parsed, defaults)

    # Include raw text for reference
    parsed["raw_text"] = raw_text

    return parsed
