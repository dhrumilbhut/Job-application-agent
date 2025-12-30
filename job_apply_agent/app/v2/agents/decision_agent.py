"""Decision Agent.

Makes APPLY/REVIEW/SKIP decision based on JD profile and resume intelligence.
Outputs structured decision with reasons, blockers, and confidence.
"""

import json
from typing import Any, Dict

import openai

from ...utils.openai_utils import ensure_api_key_set
from ..schemas import JDProfile, ResumeIntelligence, Decision


SYSTEM_PROMPT = """You are making a hiring decision for a candidate based on JD requirements and resume intelligence.

Your task:
- Compare JD requirements with candidate capabilities
- Output a structured decision: APPLY, REVIEW, or SKIP
- Provide clear reasons and blockers
- Be conservative: only APPLY on strong match

Decision logic:
- APPLY: Strong match on seniority level, domain, and key skills. Candidate clearly has what the JD asks for.
- REVIEW: Partial match, unclear fit, or any ambiguity. User should manually review.
- SKIP: Explicit blockers such as: overqualified (seniority mismatch), completely wrong domain, or missing critical requirements.

Return a JSON object:
{
  "decision": "APPLY | REVIEW | SKIP",
  "reasons": ["reason1", "reason2", ...],
  "blockers": ["blocker1", "blocker2", ...],
  "confidence": "low | medium | high"
}

Rules:
- reasons: positive signals supporting the decision (max 3)
- blockers: issues or concerns (empty if no blockers)
- confidence: low if uncertain, medium if reasonable match, high if clear decision
- Be explicit and avoid vague language
- If domain mismatch, include it in blockers
- If seniority too far off, include it in blockers
- Return valid JSON only
"""


def decide(jd_profile: JDProfile, resume_intelligence: ResumeIntelligence) -> Decision:
    """Make APPLY/REVIEW/SKIP decision.
    
    Args:
        jd_profile: Structured JD understanding
        resume_intelligence: Structured resume understanding
        
    Returns:
        Decision with decision code, reasons, blockers, confidence
        
    Raises:
        ValueError: If decision fails
    """
    ensure_api_key_set()
    
    user_prompt = f"""Make a hiring decision for this candidate.

JD Requirements:
- Company: {jd_profile.company}
- Role: {jd_profile.role}
- Seniority: {jd_profile.seniority_level}
- Domain: {jd_profile.domain}
- Tech Stack: {', '.join(jd_profile.tech_stack) if jd_profile.tech_stack else 'Not specified'}
- Key Requirements: {', '.join(jd_profile.key_requirements) if jd_profile.key_requirements else 'Not specified'}

Candidate Profile:
- Name: {resume_intelligence.name}
- Current Role: {resume_intelligence.current_role}
- Seniority: {resume_intelligence.seniority_level}
- Domain: {resume_intelligence.domain_focus}
- Experience Years: {resume_intelligence.experience_years}
- Tech Skills: {', '.join(resume_intelligence.tech_skills) if resume_intelligence.tech_skills else 'Not specified'}
- Recent Highlights: {'; '.join(resume_intelligence.recent_highlights) if resume_intelligence.recent_highlights else 'Not specified'}

Make a decision: APPLY (strong match), REVIEW (unclear/partial match), or SKIP (blockers exist).

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
        
        # Validate decision code
        decision_code = parsed.get("decision", "").strip().upper()
        if decision_code not in ("APPLY", "REVIEW", "SKIP"):
            decision_code = "REVIEW"  # Default to REVIEW if invalid
        
        # Construct Decision
        decision = Decision(
            decision=decision_code,
            reasons=parsed.get("reasons", []) or [],
            blockers=parsed.get("blockers", []) or [],
            confidence=parsed.get("confidence", "medium").strip().lower(),
        )
        
        # Validate confidence
        if decision.confidence not in ("low", "medium", "high"):
            decision.confidence = "medium"
        
        return decision
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Decision analysis returned invalid JSON: {e}")
    except Exception as e:
        raise ValueError(f"Decision analysis failed: {e}")
