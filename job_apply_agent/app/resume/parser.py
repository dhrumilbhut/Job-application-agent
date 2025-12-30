"""Resume PDF parser using OpenAI."""

import os
import re
from datetime import datetime
from typing import Dict, Any

from ..config import RESUME_PATH
from ..utils.pdf_utils import extract_text_from_pdf
from ..utils.openai_utils import call_openai_for_json, fill_defaults


def parse_resume(pdf_path: str = None) -> Dict[str, Any]:
    """Parse resume from PDF and extract structured information.
    
    Reads a PDF resume file, extracts text, and uses OpenAI to parse it
    into structured fields: name, current_title, summary, skills, experience, projects.
    
    Args:
        pdf_path: Path to resume PDF (defaults to stored resume path)
        
    Returns:
        Dict with keys:
            - name: Full name (string)
            - current_title: Current job title (string)
            - summary: Professional summary (string)
            - skills: List of skills (array)
            - experience: List of past roles (array)
            - projects: List of projects (array)
            - raw_text: Full text extracted from PDF
            
    Raises:
        ValueError: If PDF not found, cannot be read, or OpenAI call fails
    """
    # Use provided path or default to configured resume path
    target_path = pdf_path or str(RESUME_PATH)

    # Check file exists
    if not os.path.exists(target_path):
        raise ValueError(f"Resume file not found: {target_path}")

    # Extract text from PDF
    raw_text = extract_text_from_pdf(target_path)
    
    if not raw_text or not raw_text.strip():
        raise ValueError("Resume PDF is empty")

    # Define what we want OpenAI to extract
    system_prompt = """\
You are a resume parser. Extract structured information from the resume text.

Return ONLY a valid JSON object with these exact fields:
{
    "name": "full name (string or empty)",
    "current_title": "current job title (string or empty)",
    "summary": "brief professional summary (string or empty)",
    "skills": ["skill1", "skill2", ...] (array of strings),
    "experience": ["job1 at company1", "job2 at company2", ...] (array),
    "projects": ["project1 description", "project2 description", ...] (array),
    "earliest_experience_start_year": "YYYY or empty string",
    "total_experience_years": "integer number of years or 0"
}

Rules:
- Extract ONLY information explicitly in the resume
- Do NOT invent or hallucinate skills, experience, or projects
- Use empty string "" for missing name/title/summary
- Use empty array [] for missing skills/experience/projects
- For earliest_experience_start_year, return "" if no dates are present
- For total_experience_years, return 0 if dates are not present or cannot be inferred
- Return valid JSON only, no other text
"""

    user_prompt = f"Parse this resume:\n\n{raw_text}"

    # Call OpenAI to parse resume
    parsed = call_openai_for_json(system_prompt, user_prompt, max_tokens=1500)

    # Ensure all expected fields are present
    defaults = {
        "name": "",
        "current_title": "",
        "summary": "",
        "skills": [],
        "experience": [],
        "projects": [],
        "earliest_experience_start_year": "",
        "total_experience_years": 0,
    }
    parsed = fill_defaults(parsed, defaults)

    # Post-compute experience duration; prioritize years in the Experience section over Education
    try:
        text_lower = raw_text.lower()

        def extract_years(blob: str):
            return [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", blob)]

        # Try to isolate experience block between "experience" and "education" headings
        exp_start = None
        for marker in ["work experience", "experience"]:
            idx = text_lower.find(marker)
            if idx != -1:
                exp_start = idx
                break

        edu_idx = text_lower.find("education")

        if exp_start is not None:
            exp_block = raw_text[exp_start: edu_idx if edu_idx != -1 else None]
            years = extract_years(exp_block)
        else:
            years = extract_years(raw_text)

        earliest_year = min(years) if years else None
        if earliest_year:
            parsed["earliest_experience_start_year"] = str(earliest_year)
            current_year = datetime.utcnow().year
            total_years = max(0, current_year - earliest_year)
            parsed["total_experience_years"] = total_years
    except Exception:
        # If anything fails, keep the LLM values / defaults
        pass

    # Include raw text for reference
    parsed["raw_text"] = raw_text

    return parsed
