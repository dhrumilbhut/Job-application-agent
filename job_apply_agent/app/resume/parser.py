"""Resume PDF parser using OpenAI."""

import os
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
  "projects": ["project1 description", "project2 description", ...] (array)
}

Rules:
- Extract ONLY information explicitly in the resume
- Do NOT invent or hallucinate skills, experience, or projects
- Use empty string "" for missing name/title/summary
- Use empty array [] for missing skills/experience/projects
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
    }
    parsed = fill_defaults(parsed, defaults)

    # Include raw text for reference
    parsed["raw_text"] = raw_text

    return parsed
