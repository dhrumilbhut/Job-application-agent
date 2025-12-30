"""V2 agent data schemas.

Defines shared data structures for decision agents.
Ensures clear contracts between JD analysis, resume intelligence, and decision logic.
"""

from typing import List, Literal

from pydantic import BaseModel, Field


class JDProfile(BaseModel):
    """Structured understanding of a job description.
    
    Extracted by JD Analysis Agent.
    Does not contain resume information.
    """

    company: str = Field(default="", description="Company name")
    role: str = Field(default="", description="Job title / role")
    key_requirements: List[str] = Field(
        default_factory=list,
        description="Core technical/domain requirements extracted from JD"
    )
    seniority_level: str = Field(
        default="",
        description="junior | mid | senior (inferred from JD language)"
    )
    tech_stack: List[str] = Field(
        default_factory=list,
        description="Technologies, languages, frameworks mentioned"
    )
    domain: str = Field(
        default="",
        description="Problem domain: backend | frontend | fullstack | data | devops | etc."
    )
    raw_text: str = Field(
        default="",
        description="Full JD text for reference"
    )


class ResumeIntelligence(BaseModel):
    """Structured understanding of a resume.
    
    Extracted by Resume Intelligence Agent.
    Does not contain JD information.
    """

    name: str = Field(default="", description="Candidate name")
    current_role: str = Field(default="", description="Current job title")
    seniority_level: str = Field(
        default="",
        description="junior | mid | senior (inferred from resume)"
    )
    tech_skills: List[str] = Field(
        default_factory=list,
        description="Technical skills mentioned in resume"
    )
    domain_focus: str = Field(
        default="",
        description="Primary domain of expertise: backend | frontend | fullstack | data | devops | etc."
    )
    experience_years: int = Field(
        default=0,
        description="Total years of professional experience (estimated)"
    )
    recent_highlights: List[str] = Field(
        default_factory=list,
        description="Recent projects, achievements, or responsibilities"
    )
    raw_text: str = Field(
        default="",
        description="Full resume text for reference"
    )


class Decision(BaseModel):
    """Decision output from Decision Agent.
    
    Includes decision code, reasoning, blockers, and confidence.
    """

    decision: Literal["APPLY", "REVIEW", "SKIP"] = Field(
        description="APPLY: send email immediately. REVIEW: user should review. SKIP: do not apply."
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Positive signals and rationale for the decision"
    )
    blockers: List[str] = Field(
        default_factory=list,
        description="Issues, mismatches, or concerns"
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description="Confidence level in the decision"
    )
