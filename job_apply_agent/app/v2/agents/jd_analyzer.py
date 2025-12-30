"""JD Analysis Agent.

Extracts structured understanding of a job description.
Does NOT know anything about the resume.
"""

import json
from typing import Any, Dict

import openai

from ...utils.openai_utils import ensure_api_key_set
from ..schemas import JDProfile


SYSTEM_PROMPT = """You are analyzing a job description to extract structured requirements and context.

Your task:
- Extract company, role, key technical requirements, seniority level, tech stack, and problem domain
- Do NOT know anything about the candidate
- Do NOT make assumptions about how well a candidate fits
- Focus only on what the JD explicitly asks for
- Be conservative: only include skills/requirements mentioned in the JD

Return a JSON object with these fields:
{
  "company": "company name or empty string",
  "role": "job title or empty string",
  "key_requirements": ["requirement1", "requirement2", ...],
  "seniority_level": "junior | mid | senior | unknown",
  "tech_stack": ["tech1", "tech2", ...],
  "domain": "backend | frontend | fullstack | data | devops | ml | other"
}

Rules:
- If company/role is missing from JD, use empty string
- key_requirements: extract 3-5 most critical skills/experiences
- seniority_level: infer from language ("senior engineer", "5+ years", etc.) or "unknown"
- tech_stack: list of explicit technologies/frameworks/languages mentioned
- domain: best guess based on role and tech stack
- Use empty arrays for missing skills
- Return valid JSON only
"""


def analyze_jd(jd_data: Dict[str, Any]) -> JDProfile:
    """Analyze JD and extract structured profile.
    
    Args:
        jd_data: JD dict with keys: company, role, summary, key_skills, raw_text
        
    Returns:
        JDProfile with structured understanding
        
    Raises:
        ValueError: If analysis fails
    """
    ensure_api_key_set()
    
    raw_text = jd_data.get("raw_text", "") or ""
    if not raw_text.strip():
        raise ValueError("JD text is empty; cannot analyze")
    
    user_prompt = f"""Analyze this job description and extract structured requirements:

{raw_text}

Return JSON only."""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=500,
        )
        
        response_text = response["choices"][0]["message"]["content"].strip()
        parsed = json.loads(response_text)
        
        # Construct JDProfile
        profile = JDProfile(
            company=parsed.get("company", "").strip(),
            role=parsed.get("role", "").strip(),
            key_requirements=parsed.get("key_requirements", []) or [],
            seniority_level=parsed.get("seniority_level", "unknown").strip(),
            tech_stack=parsed.get("tech_stack", []) or [],
            domain=parsed.get("domain", "").strip(),
            raw_text=raw_text,
        )
        
        return profile
        
    except json.JSONDecodeError as e:
        raise ValueError(f"JD analysis returned invalid JSON: {e}")
    except Exception as e:
        raise ValueError(f"JD analysis failed: {e}")
