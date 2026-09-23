"""ORM model registry — importing this package registers all tables."""
from app.models.user import User  # noqa: F401
from app.models.document import AuditLog, Document, ProcessingLog, ProcessingStatus  # noqa: F401
from app.models.profile import (  # noqa: F401
    Candidate,
    CandidateNote,
    CandidateSkill,
    CandidateStatus,
    CandidateTag,
    Certification,
    Education,
    Experience,
    Project,
    Skill,
    SkillAlias,
)
from app.models.matching import Job, SkillMatchResult  # noqa: F401
from app.models.ops import AppSetting, Webhook, WebhookDelivery  # noqa: F401
