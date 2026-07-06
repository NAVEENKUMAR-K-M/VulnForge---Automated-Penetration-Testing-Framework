"""Initial schema — all VulnForge tables, enums, indexes, triggers, and partitions.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-06 00:00:00.000000 UTC
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Create the full VulnForge schema."""

    # ── PostgreSQL Extensions ────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── updated_at Trigger Function ──────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # ── Enum Types ───────────────────────────────────────────────────────────
    user_role_enum = postgresql.ENUM(
        "admin", "analyst", "viewer", name="user_role_enum", create_type=False
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    target_type_enum = postgresql.ENUM(
        "host", "network", "url", "domain",
        name="target_type_enum", create_type=False
    )
    target_type_enum.create(op.get_bind(), checkfirst=True)

    scan_status_enum = postgresql.ENUM(
        "pending", "running", "paused", "completed", "failed", "cancelled",
        name="scan_status_enum", create_type=False
    )
    scan_status_enum.create(op.get_bind(), checkfirst=True)

    scan_type_enum = postgresql.ENUM(
        "reconnaissance", "vulnerability", "exploitation", "full",
        name="scan_type_enum", create_type=False
    )
    scan_type_enum.create(op.get_bind(), checkfirst=True)

    priority_enum = postgresql.ENUM(
        "low", "medium", "high", "critical",
        name="priority_enum", create_type=False
    )
    priority_enum.create(op.get_bind(), checkfirst=True)

    plugin_phase_enum = postgresql.ENUM(
        "reconnaissance", "vulnerability_scanning", "exploitation", "post_exploitation",
        name="plugin_phase_enum", create_type=False
    )
    plugin_phase_enum.create(op.get_bind(), checkfirst=True)

    plugin_exec_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed", "skipped", "timed_out",
        name="plugin_exec_status_enum", create_type=False
    )
    plugin_exec_status_enum.create(op.get_bind(), checkfirst=True)

    vuln_severity_enum = postgresql.ENUM(
        "info", "low", "medium", "high", "critical",
        name="vuln_severity_enum", create_type=False
    )
    vuln_severity_enum.create(op.get_bind(), checkfirst=True)

    vuln_status_enum = postgresql.ENUM(
        "open", "confirmed", "false_positive", "mitigated", "resolved",
        name="vuln_status_enum", create_type=False
    )
    vuln_status_enum.create(op.get_bind(), checkfirst=True)

    ref_type_enum = postgresql.ENUM(
        "cve", "cwe", "url", "advisory", "exploit_db",
        name="ref_type_enum", create_type=False
    )
    ref_type_enum.create(op.get_bind(), checkfirst=True)

    report_type_enum = postgresql.ENUM(
        "executive_summary", "technical", "compliance",
        name="report_type_enum", create_type=False
    )
    report_type_enum.create(op.get_bind(), checkfirst=True)

    report_format_enum = postgresql.ENUM(
        "html", "pdf", "json",
        name="report_format_enum", create_type=False
    )
    report_format_enum.create(op.get_bind(), checkfirst=True)

    report_status_enum = postgresql.ENUM(
        "pending", "generating", "completed", "failed",
        name="report_status_enum", create_type=False
    )
    report_status_enum.create(op.get_bind(), checkfirst=True)

    audit_outcome_enum = postgresql.ENUM(
        "success", "failure",
        name="audit_outcome_enum", create_type=False
    )
    audit_outcome_enum.create(op.get_bind(), checkfirst=True)

    # ── Table: users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("role", sa.Enum("admin", "analyst", "viewer", name="user_role_enum"), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("char_length(username) >= 3", name="ck_users_username_len"),
        sa.CheckConstraint("failed_login_attempts >= 0", name="ck_users_attempts"),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_role", "users", ["role"])
    op.create_index("idx_users_active", "users", ["is_active"])
    op.execute("CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: user_sessions ─────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_user_sessions_token"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_sessions_users", ondelete="CASCADE"),
    )
    op.create_index("idx_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("idx_user_sessions_token", "user_sessions", ["refresh_token_hash"])
    op.execute("""
        CREATE INDEX idx_user_sessions_active ON user_sessions (user_id, expires_at)
        WHERE is_revoked = FALSE
    """)
    op.execute("CREATE TRIGGER trg_user_sessions_updated_at BEFORE UPDATE ON user_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: targets ───────────────────────────────────────────────────────
    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_type", sa.Enum("host", "network", "url", "domain", name="target_type_enum"), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("scope_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_targets_users", ondelete="RESTRICT"),
        sa.CheckConstraint("char_length(trim(value)) > 0", name="ck_targets_value_nonempty"),
    )
    op.create_index("idx_targets_type", "targets", ["target_type"])
    op.create_index("idx_targets_active", "targets", ["is_active"])
    op.create_index("idx_targets_created_by", "targets", ["created_by_id"])
    op.create_index("idx_targets_value", "targets", ["value"])
    op.execute("CREATE TRIGGER trg_targets_updated_at BEFORE UPDATE ON targets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: target_tags ───────────────────────────────────────────────────
    op.create_table(
        "target_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_id", "tag", name="uq_target_tags_pair"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], name="fk_target_tags_targets", ondelete="CASCADE"),
        sa.CheckConstraint("char_length(trim(tag)) > 0", name="ck_target_tags_nonempty"),
    )
    op.create_index("idx_target_tags_target_id", "target_tags", ["target_id"])
    op.create_index("idx_target_tags_tag", "target_tags", ["tag"])

    # ── Table: plugins ───────────────────────────────────────────────────────
    op.create_table(
        "plugins",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("phase", sa.Enum("reconnaissance", "vulnerability_scanning", "exploitation", "post_exploitation", name="plugin_phase_enum"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("module_path", sa.String(500), nullable=False),
        sa.Column("default_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("plugin_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_plugins_name"),
    )
    op.create_index("idx_plugins_phase", "plugins", ["phase"])
    op.create_index("idx_plugins_enabled", "plugins", ["is_enabled"])
    op.create_index("idx_plugins_name", "plugins", ["name"])
    op.execute("CREATE TRIGGER trg_plugins_updated_at BEFORE UPDATE ON plugins FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: scans ─────────────────────────────────────────────────────────
    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("pending", "running", "paused", "completed", "failed", "cancelled", name="scan_status_enum"), nullable=False, server_default="pending"),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scan_type", sa.Enum("reconnaissance", "vulnerability", "exploitation", "full", name="scan_type_enum"), nullable=False),
        sa.Column("priority", sa.Enum("low", "medium", "high", "critical", name="priority_enum"), nullable=False, server_default="medium"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("configuration", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], name="fk_scans_targets", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_scans_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], name="fk_scans_assigned_to", ondelete="SET NULL"),
        sa.CheckConstraint("completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at", name="ck_scans_completed_after_started"),
    )
    op.create_index("idx_scans_status", "scans", ["status"])
    op.create_index("idx_scans_target_id", "scans", ["target_id"])
    op.create_index("idx_scans_created_by", "scans", ["created_by_id"])
    op.create_index("idx_scans_type", "scans", ["scan_type"])
    op.create_index("idx_scans_priority", "scans", ["priority"])
    op.execute("CREATE INDEX idx_scans_celery_task ON scans (celery_task_id) WHERE celery_task_id IS NOT NULL")
    op.execute("CREATE INDEX idx_scans_scheduled ON scans (scheduled_at) WHERE scheduled_at IS NOT NULL")
    op.execute("CREATE TRIGGER trg_scans_updated_at BEFORE UPDATE ON scans FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: scan_plugin_executions ────────────────────────────────────────
    op.create_table(
        "scan_plugin_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "skipped", "timed_out", name="plugin_exec_status_enum"), nullable=False, server_default="pending"),
        sa.Column("configuration", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.SmallInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_spe_scans", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], name="fk_spe_plugins", ondelete="RESTRICT"),
    )
    op.create_index("idx_spe_scan_id", "scan_plugin_executions", ["scan_id"])
    op.create_index("idx_spe_plugin_id", "scan_plugin_executions", ["plugin_id"])
    op.create_index("idx_spe_status", "scan_plugin_executions", ["status"])
    op.execute("CREATE TRIGGER trg_spe_updated_at BEFORE UPDATE ON scan_plugin_executions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: vulnerabilities ───────────────────────────────────────────────
    op.create_table(
        "vulnerabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.Enum("info", "low", "medium", "high", "critical", name="vuln_severity_enum"), nullable=False),
        sa.Column("cvss_score", sa.Numeric(4, 1), nullable=True),
        sa.Column("cvss_vector", sa.String(100), nullable=True),
        sa.Column("cve_id", sa.String(20), nullable=True),
        sa.Column("cwe_id", sa.String(20), nullable=True),
        sa.Column("status", sa.Enum("open", "confirmed", "false_positive", "mitigated", "resolved", name="vuln_status_enum"), nullable=False, server_default="open"),
        sa.Column("affected_host", sa.String(255), nullable=True),
        sa.Column("affected_port", sa.Integer(), nullable=True),
        sa.Column("affected_service", sa.String(100), nullable=True),
        sa.Column("affected_path", sa.Text(), nullable=True),
        sa.Column("proof_of_concept", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_vulns_scans", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plugin_execution_id"], ["scan_plugin_executions.id"], name="fk_vulns_spe", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], name="fk_vulns_targets", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], name="fk_vulns_verifier", ondelete="SET NULL"),
        sa.CheckConstraint("cvss_score IS NULL OR (cvss_score >= 0.0 AND cvss_score <= 10.0)", name="ck_vulns_cvss_range"),
        sa.CheckConstraint("affected_port IS NULL OR (affected_port >= 1 AND affected_port <= 65535)", name="ck_vulns_port_range"),
        sa.CheckConstraint("(verified_by_id IS NULL AND verified_at IS NULL) OR (verified_by_id IS NOT NULL AND verified_at IS NOT NULL)", name="ck_vulns_verified_consistency"),
    )
    op.create_index("idx_vulns_scan_id", "vulnerabilities", ["scan_id"])
    op.create_index("idx_vulns_target_id", "vulnerabilities", ["target_id"])
    op.create_index("idx_vulns_severity", "vulnerabilities", ["severity"])
    op.create_index("idx_vulns_status", "vulnerabilities", ["status"])
    op.execute("CREATE INDEX idx_vulns_open_high ON vulnerabilities (severity, status) WHERE status = 'open'")
    op.execute("CREATE INDEX idx_vulns_cve ON vulnerabilities (cve_id) WHERE cve_id IS NOT NULL")
    op.execute("CREATE TRIGGER trg_vulns_updated_at BEFORE UPDATE ON vulnerabilities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: vulnerability_references ──────────────────────────────────────
    op.create_table(
        "vulnerability_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_type", sa.Enum("cve", "cwe", "url", "advisory", "exploit_db", name="ref_type_enum"), nullable=False),
        sa.Column("reference_value", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vulnerability_id", "reference_type", "reference_value", name="uq_vuln_refs_pair"),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"], name="fk_vuln_refs_vulns", ondelete="CASCADE"),
    )
    op.create_index("idx_vuln_refs_vuln_id", "vulnerability_references", ["vulnerability_id"])
    op.create_index("idx_vuln_refs_type", "vulnerability_references", ["reference_type"])

    # ── Table: vulnerability_notes ────────────────────────────────────────────
    op.create_table(
        "vulnerability_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"], name="fk_vuln_notes_vulns", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_vuln_notes_users", ondelete="RESTRICT"),
        sa.CheckConstraint("char_length(trim(content)) > 0", name="ck_vuln_notes_content"),
    )
    op.create_index("idx_vuln_notes_vuln_id", "vulnerability_notes", ["vulnerability_id"])
    op.create_index("idx_vuln_notes_author_id", "vulnerability_notes", ["author_id"])
    op.execute("CREATE TRIGGER trg_vuln_notes_updated_at BEFORE UPDATE ON vulnerability_notes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: reports ────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("report_type", sa.Enum("executive_summary", "technical", "compliance", name="report_type_enum"), nullable=False),
        sa.Column("format", sa.Enum("html", "pdf", "json", name="report_format_enum"), nullable=False),
        sa.Column("status", sa.Enum("pending", "generating", "completed", "failed", name="report_status_enum"), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("generated_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["generated_by_id"], ["users.id"], name="fk_reports_users", ondelete="RESTRICT"),
        sa.CheckConstraint("file_size_bytes IS NULL OR file_size_bytes > 0", name="ck_reports_file_size"),
    )
    op.create_index("idx_reports_generated_by", "reports", ["generated_by_id"])
    op.create_index("idx_reports_status", "reports", ["status"])
    op.create_index("idx_reports_type", "reports", ["report_type"])
    op.execute("CREATE TRIGGER trg_reports_updated_at BEFORE UPDATE ON reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    # ── Table: report_scans (M:M join) ────────────────────────────────────────
    op.create_table(
        "report_scans",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "scan_id"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name="fk_report_scans_reports", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_report_scans_scans", ondelete="RESTRICT"),
    )
    op.create_index("idx_report_scans_report_id", "report_scans", ["report_id"])
    op.create_index("idx_report_scans_scan_id", "report_scans", ["scan_id"])

    # ── Table: report_vulnerabilities (M:M join) ──────────────────────────────
    op.create_table(
        "report_vulnerabilities",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "vulnerability_id"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name="fk_report_vulns_reports", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"], name="fk_report_vulns_vulns", ondelete="CASCADE"),
    )
    op.create_index("idx_report_vulns_report_id", "report_vulnerabilities", ["report_id"])
    op.create_index("idx_report_vulns_vuln_id", "report_vulnerabilities", ["vulnerability_id"])

    # ── Table: audit_logs (partitioned by RANGE on created_at) ───────────────
    op.execute("""
        CREATE TABLE audit_logs (
            id            UUID NOT NULL DEFAULT gen_random_uuid(),
            actor_id      UUID REFERENCES users(id) ON DELETE SET NULL,
            actor_ip      INET,
            action        VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id   UUID,
            details       JSONB,
            outcome       audit_outcome_enum NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        ) PARTITION BY RANGE (created_at)
    """)
    # Initial quarterly partitions
    op.execute("""
        CREATE TABLE audit_logs_2026_q3
        PARTITION OF audit_logs
        FOR VALUES FROM ('2026-07-01') TO ('2026-10-01')
    """)
    op.execute("""
        CREATE TABLE audit_logs_2026_q4
        PARTITION OF audit_logs
        FOR VALUES FROM ('2026-10-01') TO ('2027-01-01')
    """)
    op.execute("""
        CREATE TABLE audit_logs_2027_q1
        PARTITION OF audit_logs
        FOR VALUES FROM ('2027-01-01') TO ('2027-04-01')
    """)
    op.execute("CREATE INDEX idx_audit_actor_id ON audit_logs (actor_id)")
    op.execute("CREATE INDEX idx_audit_action ON audit_logs (action)")
    op.execute("CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id)")
    op.execute("CREATE INDEX idx_audit_created_at ON audit_logs (created_at DESC)")
    op.execute("CREATE INDEX idx_audit_outcome ON audit_logs (outcome)")


def downgrade() -> None:
    """Drop the full VulnForge schema in reverse dependency order."""

    # Drop tables (partitioned table drops all partitions automatically)
    for table in [
        "report_vulnerabilities",
        "report_scans",
        "reports",
        "vulnerability_notes",
        "vulnerability_references",
        "vulnerabilities",
        "scan_plugin_executions",
        "scans",
        "plugins",
        "target_tags",
        "targets",
        "user_sessions",
        "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")

    # Drop enum types
    for enum_name in [
        "user_role_enum", "target_type_enum", "scan_status_enum",
        "scan_type_enum", "priority_enum", "plugin_phase_enum",
        "plugin_exec_status_enum", "vuln_severity_enum", "vuln_status_enum",
        "ref_type_enum", "report_type_enum", "report_format_enum",
        "report_status_enum", "audit_outcome_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")
