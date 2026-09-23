"""v2: ATS workflow, runtime settings, webhooks, weighted matching

Adds candidate pipeline status, notes & tags; nice-to-have job skills;
tiered match columns; app_settings, webhooks and webhook_deliveries tables.

Revision ID: a02c1f9d7b3a
Revises: 49dc0d5359c4
Create Date: 2026-09-16 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a02c1f9d7b3a"
down_revision = "49dc0d5359c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- jobs: nice-to-have skill tier ----------------------------------
    op.add_column(
        "jobs",
        sa.Column("nice_to_have_skills", sa.JSON(), nullable=False, server_default="[]"),
    )

    # ---- skill_match_results: tiered match detail -----------------------
    op.add_column(
        "skill_match_results",
        sa.Column("matched_nice", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "skill_match_results",
        sa.Column("missing_nice", sa.JSON(), nullable=False, server_default="[]"),
    )

    # ---- candidates: ATS pipeline status --------------------------------
    op.add_column(
        "candidates",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
    )
    op.create_index("ix_candidates_status", "candidates", ["status"])

    # ---- candidate notes -------------------------------------------------
    op.create_table(
        "candidate_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidate_notes_id", "candidate_notes", ["id"])
    op.create_index("ix_candidate_notes_candidate_id", "candidate_notes", ["candidate_id"])
    op.create_index("ix_candidate_notes_created_at", "candidate_notes", ["created_at"])

    # ---- candidate tags (composite PK) -----------------------------------
    op.create_table(
        "candidate_tags",
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tag", sa.String(length=64), primary_key=True),
    )

    # ---- runtime settings ------------------------------------------------
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ---- webhooks --------------------------------------------------------
    op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False, server_default="document.processed"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("secret", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhooks_id", "webhooks", ["id"])
    op.create_index("ix_webhooks_event", "webhooks", ["event"])
    op.create_index("ix_webhooks_active", "webhooks", ["active"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "webhook_id",
            sa.Integer(),
            sa.ForeignKey("webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Integer()),
        sa.Column("status_code", sa.Integer()),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text()),
        sa.Column("payload", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_deliveries_id", "webhook_deliveries", ["id"])
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])
    op.create_index("ix_webhook_deliveries_success", "webhook_deliveries", ["success"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_success", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_id", "webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhooks_active", "webhooks")
    op.drop_index("ix_webhooks_event", "webhooks")
    op.drop_index("ix_webhooks_id", "webhooks")
    op.drop_table("webhooks")
    op.drop_table("app_settings")
    op.drop_table("candidate_tags")
    op.drop_index("ix_candidate_notes_created_at", "candidate_notes")
    op.drop_index("ix_candidate_notes_candidate_id", "candidate_notes")
    op.drop_index("ix_candidate_notes_id", "candidate_notes")
    op.drop_table("candidate_notes")
    op.drop_index("ix_candidates_status", "candidates")
    op.drop_column("candidates", "status")
    op.drop_column("skill_match_results", "missing_nice")
    op.drop_column("skill_match_results", "matched_nice")
    op.drop_column("jobs", "nice_to_have_skills")
