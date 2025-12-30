"""Resume Intelligence Agent.

Extracts structured understanding of a resume.
Does NOT know anything about the job description.
"""

import json
from typing import Any, Dict

import openai

from ...utils.openai_utils import ensure_api_key_set
from ..schemas import ResumeIntelligence
from ..prompts import RESUME_INTELLIGENCE_SYSTEM_PROMPT


def analyze_resume(resume_profile: Dict[str, Any]) -> ResumeIntelligence:
    """Analyze resume and extract structured intelligence.
    
    Args:
        resume_profile: Resume dict with keys: name, current_title, summary, skills, 
                        experience, projects, raw_text
        
    Returns:
        ResumeIntelligence with structured understanding
        
    Raises:
        ValueError: If analysis fails
    """
    ensure_api_key_set()
    
    raw_text = resume_profile.get("raw_text", "") or ""
    if not raw_text.strip():
        raise ValueError("Resume text is empty; cannot analyze")
    
    user_prompt = f"""Analyze this resume and extract structured intelligence about the candidate:

{raw_text}

Return JSON only."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": RESUME_INTELLIGENCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=500,
        )
        
        response_text = response["choices"][0]["message"]["content"].strip()
        parsed = json.loads(response_text)

        # Prefer deterministic years from pre-parsed resume if available
        resume_years = int(resume_profile.get("total_experience_years", 0) or 0)
        llm_years = int(parsed.get("experience_years", 0) or 0)
        experience_years = resume_years if resume_years > 0 else llm_years
        
        # Construct ResumeIntelligence
        intelligence = ResumeIntelligence(
            name=parsed.get("name", "").strip(),
            current_role=parsed.get("current_role", "").strip(),
            seniority_level=parsed.get("seniority_level", "unknown").strip(),
            tech_skills=parsed.get("tech_skills", []) or [],
            domain_focus=parsed.get("domain_focus", "").strip(),
            experience_years=experience_years,
            recent_highlights=parsed.get("recent_highlights", []) or [],
            raw_text=raw_text,
        )
        
        return intelligence
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Resume analysis returned invalid JSON: {e}")
    except Exception as e:
        raise ValueError(f"Resume analysis failed: {e}")
