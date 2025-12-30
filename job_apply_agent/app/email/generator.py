"""Email generation for cold job applications."""

import json
import re
from typing import Any, Dict, List, Tuple

import openai

from ..config import JD_DATA_PATH, RESUME_PROFILE_PATH, SENDER_EMAIL
from ..utils.openai_utils import ensure_api_key_set


def load_resume_profile() -> Dict[str, Any]:
    """Load the parsed resume profile from storage.
    
    Returns:
        Dict with resume data (name, current_title, summary, skills, experience, projects, raw_text)
        
    Raises:
        FileNotFoundError: If resume profile not found
        ValueError: If profile is invalid JSON
    """
    if not RESUME_PROFILE_PATH.exists():
        raise FileNotFoundError(
            "Resume profile not found. Please upload and parse a resume first via POST /resume."
        )
    
    with RESUME_PROFILE_PATH.open("r", encoding="utf-8") as f:
        profile = json.load(f)
    
    return profile


def _strip_list(items: List[str]) -> List[str]:
    return [item.strip() for item in items or [] if str(item).strip()]


def load_jd_data() -> Dict[str, Any]:
    """Load the current job description data from storage.
    
    Returns:
        Dict with JD data (company, role, key_skills, summary, raw_text)
        
    Raises:
        FileNotFoundError: If JD data not found
        ValueError: If data is invalid JSON
    """
    if not JD_DATA_PATH.exists():
        raise FileNotFoundError(
            "Job description not found. Please submit a JD via POST /apply first."
        )
    
    with JD_DATA_PATH.open("r", encoding="utf-8") as f:
        jd_data = json.load(f)
    
    return jd_data


def normalize_jd(jd_data: Dict[str, Any]) -> Dict[str, Any]:
    """Provide predictable, non-invented defaults when JD fields are empty."""
    jd_copy = dict(jd_data)
    jd_copy["company"] = jd_copy.get("company", "").strip()
    jd_copy["role"] = jd_copy.get("role", "").strip()
    jd_copy["summary"] = jd_copy.get("summary", "").strip()
    jd_copy["email"] = jd_copy.get("email", "").strip()
    jd_copy["key_skills"] = _strip_list(jd_copy.get("key_skills", []))
    return jd_copy


SYSTEM_PROMPT = """You are writing a cold application email for a startup or fast-moving engineering team.

Rules you must follow:
- Write like a human engineer, not a resume or LinkedIn summary.
- Be concise, direct, and concrete.
- Avoid abstract phrases such as:
    "solid background", "hands-on experience", "extensive experience",
    "proven track record", "passionate about", "dynamic environment".
- Make at most 2–3 claims total.
- Each claim must be backed by a concrete example or action.
- Prefer verbs over adjectives.
- Do NOT list skills.
- Do NOT invent experience.
- Use ONLY provided resume information.
- If information is missing, omit it.
- Keep the email under 120 words.
- Do NOT flatter the company or ask for meetings.
- Do NOT include a name, signature, or placeholder for a name.
- End the email body with a closing sentence only; the system will append the sender name separately.
- Use 2-3 short paragraphs (max 2 sentences each) that read like a human explaining relevance, not selling themselves.
- Prefer concrete actions over abstract phrases; avoid resume-style wording (e.g., "solid background", "hands-on experience", "full software lifecycle").
- Group related ideas; avoid listing many concepts.
- Final line must be: "Resume attached. Happy to share more details if useful." (with a trailing period).
"""


HUMANIZATION_RULES = """Humanization rules:
- One claim -> one concrete example tied to resume evidence.
- Allow mild imperfection; avoid over-polished symmetry.
- Close softly: "Resume attached. Happy to share more details if useful."""


BANNED_PHRASES = {
    "solid background",
    "hands-on experience",
    "extensive experience",
    "proven track record",
    "passionate about",
    "dynamic environment",
    "full software lifecycle",
    "aligns well",
    "enhancing user experience",
    "saas environment",
    "i am excited",
    "thrilled",
    "dear hiring manager",
    "to whom it may concern",
}


def _sanitize_banned(text: str) -> str:
    cleaned = text
    for phrase in BANNED_PHRASES:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    # Collapse double spaces/newlines that may result
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

GENERIC_TEMPLATES = {
    "i am writing to apply",
    "i'm writing to apply",
    "please find my resume attached",
    "my resume is attached for your review",
    "thank you for your time and consideration",
    "i believe i am a great fit",
    "with x years of experience",
}

ADJECTIVES = {
    "innovative",
    "dynamic",
    "motivated",
    "driven",
    "dedicated",
    "hardworking",
    "detail-oriented",
    "collaborative",
    "strategic",
    "proactive",
    "fast-paced",
}

VERBS = {
    "built",
    "shipped",
    "designed",
    "implemented",
    "led",
    "owned",
    "delivered",
    "debugged",
    "refactored",
    "scaled",
    "optimized",
    "deployed",
    "maintained",
    "improved",
    "integrated",
    "tested",
    "reviewed",
    "applied",
    "integrating",
    "experimented",
}

RESUME_SUMMARY_MARKERS = {
    "professional summary",
    "summary",
    "experience includes",
    "years of experience",
    "proven track record",
}


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _adjective_heavy(text: str) -> bool:
    words = [w.strip(".,!?:;()[]{}\"'\n\r").lower() for w in re.split(r"\s+", text) if w]
    adj = sum(1 for w in words if w in ADJECTIVES or w.endswith("ive"))
    verbs = sum(1 for w in words if w in VERBS)
    return adj > max(verbs, 1) + 2


def _contains_banned_phrase(text: str) -> Tuple[bool, str]:
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            return True, phrase
    return False, ""


def _contains_bullets(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith(('-', '*', '•')):
            return True
    return False


def _reads_generic_template(text: str) -> Tuple[bool, str]:
    lower = text.lower()
    for phrase in GENERIC_TEMPLATES:
        if phrase in lower:
            return True, phrase
    return False, ""


def _resume_corpus(profile: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("summary", "current_title", "name"):
        val = profile.get(key, "")
        if val:
            parts.append(str(val))
    for key in ("skills", "experience", "projects"):
        for item in profile.get(key, []) or []:
            parts.append(str(item))
    return " \n".join(parts).lower()


def _count_claims(body: str) -> int:
    # Heuristic: each sentence-like chunk with a verb counts as a claim
    chunks = re.split(r"[.!?]+\s*", body)
    claims = 0
    for chunk in chunks:
        words = [w.lower() for w in re.findall(r"[a-zA-Z']+", chunk)]
        if not words:
            continue
        if any(w in VERBS for w in words):
            claims += 1
    return claims


def _noun_heavy(body: str) -> bool:
    words = [w.lower() for w in re.findall(r"[a-zA-Z']+", body)]
    if not words:
        return False
    verbs = sum(1 for w in words if w in VERBS)
    nouns = sum(1 for w in words if w.endswith(("ion", "ment", "ness", "ity", "ence", "ance", "ism")))
    return nouns > verbs * 2 + 2


def _looks_like_resume_summary(body: str) -> bool:
    lower = body.lower()
    if any(marker in lower for marker in RESUME_SUMMARY_MARKERS):
        return True
    # If first line lists multiple commas with no verbs, treat as summary-like
    first_line = body.splitlines()[0] if body.splitlines() else ""
    verb_present = any(v in first_line.lower().split() for v in VERBS)
    comma_count = first_line.count(",")
    return comma_count >= 2 and not verb_present


def _paragraphs_ok(body: str) -> bool:
    # Simplified: ensure total sentences are reasonable (<= 6). Do not hard-fail on layout.
    sentences = [s for s in re.split(r"[.!?]+\s*", body) if s.strip()]
    return 0 < len(sentences) <= 6


def _mentions_unbacked_jd_skills(email_text: str, resume_profile: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[bool, str]:
    email_lower = email_text.lower()
    resume_blob = _resume_corpus(resume_profile)
    for skill in jd_data.get("key_skills", []) or []:
        s = str(skill).strip().lower()
        if not s:
            continue
        if s in email_lower and s not in resume_blob:
            return True, skill
    return False, ""


def _repeats_jd_language(email_text: str, jd_summary: str) -> bool:
    jd_summary = jd_summary or ""
    if not jd_summary.strip():
        return False
    email_words = {w for w in re.findall(r"[a-zA-Z]{4,}", email_text.lower())}
    jd_words = {w for w in re.findall(r"[a-zA-Z]{4,}", jd_summary.lower())}
    if not jd_words:
        return False
    overlap = len(email_words & jd_words) / max(len(jd_words), 1)
    return overlap > 0.6


def _build_context(resume_profile: Dict[str, Any], jd_data: Dict[str, Any]) -> str:
    company = jd_data.get("company", "") or ""
    role = jd_data.get("role", "") or ""
    jd_summary_raw = (jd_data.get("summary", "") or "").strip()

    # Limit JD summary to max 3 short lines to avoid copy/paste tone
    jd_sentences = re.split(r"(?<=[.!?])\s+", jd_summary_raw)
    jd_summary = " ".join(jd_sentences[:3]).strip()

    # Resume summary: single line
    resume_summary = (resume_profile.get("summary", "") or resume_profile.get("current_title", "") or "").strip()

    # Up to 2 highlights total
    highlights: List[str] = []
    for block in (resume_profile.get("experience", []) or []):
        if len(highlights) >= 2:
            break
        if str(block).strip():
            highlights.append(str(block).strip())
    if len(highlights) < 2:
        for block in (resume_profile.get("projects", []) or []):
            if len(highlights) >= 2:
                break
            if str(block).strip():
                highlights.append(str(block).strip())

    highlights = highlights[:2]

    # Keep format even if empty to avoid the model guessing
    highlights_section = "\n".join(f"- {line}" if line else "- " for line in (highlights or [""]))

    context = f"""Company Name: {company}
Role Title: {role}

JD Summary:
{jd_summary}

Resume Summary:
{resume_summary}

Relevant Resume Highlights:
{highlights_section}
"""
    return context


def _build_user_prompt(context: str) -> str:
    examples = """
Example 1:
I’m reaching out regarding this role. My background is in backend engineering, and my recent work has focused on building LLM-powered prototypes and systems.

At Zuru Tech, I designed scalable APIs and integrated AI capabilities into production applications, including RAG-based services. This work prepared me for deploying Generative AI features in real systems.

Resume attached. Happy to share more details if useful.

Example 2:
I’m applying for this role. My background is in backend engineering, and my recent work has focused on applying LLMs in real systems rather than demos.

I’ve built RAG-based services and worked on backend APIs that integrate AI capabilities into production applications. At Zuru Tech, this involved designing scalable services used by real users.

Resume attached. Happy to share more details if useful.

Example 3:
I’m reaching out regarding this role. I primarily work on backend systems, with recent projects centered on integrating LLM-based features into APIs.

I’ve built RAG prototypes and backend pipelines using Python and FastAPI, and previously worked as a Software Engineer at Zuru Tech focusing on backend development.

Resume attached. Happy to share more details if useful.

Example 4:
I’m applying for this role. Most of my experience is in backend engineering, and my recent work has involved building and integrating LLM-powered features into production services.

At Zuru Tech, I worked on designing scalable APIs, and more recently I’ve built RAG-based systems as part of applied AI projects.

Resume attached. Happy to share more details if useful.
"""

    return f"""{context}

Behavioral Constraints:
- Never invent or embellish.
- Skip any detail that is missing or unclear.
- Prefer silence over guessing.

Content Selection Rules:
- Only use resume data provided in the context.
- Do not copy JD language verbatim; summarize neutrally if needed.
- If company is missing, do not mention it. If role is missing, say "this role".
- Make only 2-3 claims total, each backed by an action/example.

Style Rules:
- Startup-direct tone; concise and human.
- One claim -> one concrete example from resume.
- Paragraphs 1-2 lines each; total 80-120 words.
- No bullet points or skill lists.

Humanization:
{HUMANIZATION_RULES}

Output Format (strict):
Subject: Application – <Role or "This Role">

Email body:
<email content only>

Rules:
- Greeting optional
- If company name is missing, do not mention it
- If role title is missing, say "this role"
- Keep under 120 words
- Max 2 sentences per paragraph
- Final line: "Resume attached. Happy to share more details if useful." (include period)
- Do NOT include any name, signature, or placeholder for a name
- Match the tone and structure of the provided examples (short opener about role + 1-2 concrete work sentences + closing line)

Style Examples (imitate closely):
{examples}
"""


def _parse_generated_email(text: str) -> Tuple[str, str, str]:
    subject = ""
    body_lines: List[str] = []
    mode: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()

        if lower.startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            mode = None
            continue

        if lower.startswith("email body:"):
            mode = "body"
            continue

        if mode == "body":
            body_lines.append(raw_line)

    body = "\n".join(body_lines).strip()

    # Fallback: if markers were missing and body is empty, treat text as body but
    # filter out subject marker lines to avoid leaking subject into body.
    if not body and text.strip():
        filtered: List[str] = []
        for raw_line in text.splitlines():
            lower_line = raw_line.strip().lower()
            if lower_line.startswith("subject:"):
                continue
            if lower_line.startswith("email body:"):
                continue
            filtered.append(raw_line)
        body = "\n".join(filtered).strip()

    return subject, body, ""


def _validate_email_output(subject: str, body: str, signature: str, resume_profile: Dict[str, Any], jd_data: Dict[str, Any]) -> Tuple[bool, str]:
    full_text = f"{subject}\n{body}\n{signature}"

    wc = _word_count(body)
    if wc > 120:
        return False, "Word count exceeds 120"

    claims = _count_claims(body)
    if claims > 3:
        return False, "Too many claims"

    banned, phrase = _contains_banned_phrase(full_text)
    if banned:
        return False, f"Contains banned phrase: {phrase}"

    generic, phrase = _reads_generic_template(full_text)
    if generic:
        return False, f"Generic template language detected: {phrase}"

    if _adjective_heavy(full_text):
        return False, "Too many adjectives vs verbs"

    if _noun_heavy(body):
        return False, "Too noun-heavy vs verbs"

    if _looks_like_resume_summary(body):
        return False, "Reads like a resume summary"

    if _repeats_jd_language(full_text, jd_data.get("summary", "")):
        return False, "Repeats JD language too closely"

    unbacked, skill = _mentions_unbacked_jd_skills(full_text, resume_profile, jd_data)
    if unbacked:
        return False, f"Mentions skill not in resume: {skill}"

    if _contains_bullets(body):
        return False, "Contains bullet points"

    # Placeholder/signature leakage guard
    lower_body = body.lower()
    if "<name" in lower_body or "signature:" in lower_body:
        return False, "Contains placeholder or signature markers"

    # Require closing line
    closing = "resume attached. happy to share more details if useful."
    if closing not in lower_body:
        return False, "Missing required closing line"

    if not _paragraphs_ok(body):
        return False, "Paragraph structure not in expected 2-3 short paragraphs"

    if not body:
        return False, "Empty email body"

    return True, ""


def generate_email(resume_profile: Dict[str, Any], jd_data: Dict[str, Any]) -> Dict[str, str]:
    """Generate a cold, startup-style application email with validation and retries."""

    ensure_api_key_set()

    context = _build_context(resume_profile, jd_data)
    user_prompt = _build_user_prompt(context)

    attempts = 0
    last_error = ""

    while attempts < 3:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=500,
            )

            raw_output = response["choices"][0]["message"]["content"].strip()
            subject, body, _ = _parse_generated_email(raw_output)

            # Sanitize banned phrases before validation
            subject = _sanitize_banned(subject)
            body = _sanitize_banned(body)

            # Validate pre-signature append
            valid, reason = _validate_email_output(subject, body, "", resume_profile, jd_data)
            if valid:
                return {"subject": subject, "body": body, "signature": ""}

            last_error = reason
            attempts += 1
        except Exception as e:
            last_error = str(e)
            attempts += 1

    raise ValueError(f"Failed to generate email after validation: {last_error}")


def compose_full_email(resume_profile: Dict[str, Any], jd_data: Dict[str, Any], recipient_email: str = None) -> Dict[str, str]:
    """Compose a complete email with salutation, body, and closing.
    
    Args:
        resume_profile: Parsed resume data
        jd_data: Parsed JD data
        recipient_email: Optional email address. If not provided, uses email from JD data.
                         If JD has no email and recipient_email is None, raises ValueError.
        
    Returns:
        Dict with keys:
            - subject: Email subject line
            - body: Email body (generated)
            - to: Recipient email address
            - from: Sender email
            
    Raises:
        ValueError: If no email found in JD and recipient_email not provided
    """
    jd_data = normalize_jd(jd_data)
    company = jd_data.get("company", "").strip()
    role = jd_data.get("role", "").strip()
    
    # Determine recipient email
    to_email = (recipient_email or jd_data.get("email", "")).strip()
    
    if not to_email:
        raise ValueError(
            "No recipient email found. Please provide email as query parameter: ?email=hiring@company.com"
        )
    
    # Generate email content with validation/regeneration
    generated = generate_email(resume_profile, jd_data)

    # Subject: prefer model output; fallback follows required pattern
    subject = generated.get("subject", "").strip()
    if not subject:
        if role:
            subject = f"Application – {role}"
        else:
            subject = "Application – This Role"

    body = generated.get("body", "").strip()

    # Append deterministic signature using resume name (or empty if missing)
    sender_name = (resume_profile.get("name", "") or "").strip()
    if sender_name:
        body = f"{body}\n\nThanks,\n{sender_name}"

    email = {
        "subject": subject,
        "body": body,
        "from": SENDER_EMAIL,
        "to": to_email,
    }

    return email
