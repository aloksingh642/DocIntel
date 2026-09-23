"""Prompt templates for LLM-based providers.

The strict safety rules (Section 45) are encoded here: never invent data,
return null for unavailable scalars, empty arrays for unavailable lists,
valid JSON only, validated downstream against Pydantic schemas.
"""

CLASSIFICATION_PROMPT = """You are a document classification engine.

Classify the DOCUMENT TEXT into exactly one of:
resume, invoice, contract, purchase_order, certificate, other.

Respond with ONLY valid JSON matching exactly:
{{"document_type": "<type>", "confidence": <float between 0 and 1>}}

Rules:
- confidence must reflect genuine certainty; unsure means a LOW score.
- Do not add any keys. Do not add prose.

DOCUMENT TEXT:
\"\"\"
{text}
\"\"\"
"""

RESUME_EXTRACTION_PROMPT = """You are a resume information-extraction engine.

Extract ONLY information explicitly present in the DOCUMENT TEXT.

STRICT RULES:
1. Never invent candidate information.
2. Never infer a skill unless the document supports it.
3. Never invent employment history, education, dates, or certifications.
4. Use null for unavailable scalar fields.
5. Use empty arrays for unavailable lists.
6. Return ONLY valid JSON conforming to the schema below. No prose.
7. Normalize obvious formatting variants (e.g. "React.js" -> "React").

SCHEMA:
{{
  "candidate": {{
    "name": str|null, "email": str|null, "phone": str|null,
    "location": str|null, "linkedin": str|null, "github": str|null,
    "portfolio": str|null, "professional_summary": str|null
  }},
  "skills": [str],
  "experiences": [{{"company": str|null, "job_title": str|null,
    "start_date": str|null, "end_date": str|null, "description": str|null}}],
  "education": [{{"institution": str|null, "degree": str|null,
    "field": str|null, "start_year": int|null, "end_year": int|null}}],
  "certifications": [{{"name": str, "issuer": str|null, "issue_date": str|null}}],
  "projects": [{{"name": str, "description": str|null, "technologies": [str]}}],
  "languages": [{{"language": str, "proficiency": str|null}}],
  "total_experience_years": float|null,
  "confidence": float
}}

DOCUMENT TEXT:
\"\"\"
{text}
\"\"\"
"""
