"""
AgentRun and AgentAction ORM models — the orchestrator agent's audit trail.

An ``AgentRun`` is one autonomous assessment of a single in-scope target. The
agent plans a sequence of tool invocations; each becomes an ``AgentAction``.
Passive/recon actions are auto-approved and execute autonomously; active/
intrusive actions are PROPOSED and require explicit human approval before they
run. Every action records the scope verdict and outcome, so an operator can
always reconstruct exactly what the agent did and why.

Findings are anchored to a backing ``Scan`` (``AgentRun.scan_id``) so assets and
vulnerabilities the agent discovers flow through the existing scan/asset/report
pipeline unchanged.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.target import Target
    from app.models.user import User
    from app.models.workspace import Workspace


class AgentRunStatus(str, enum.Enum):
    """Lifecycle of an agent run."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionTier(str, enum.Enum):
    """Intrusiveness tier that governs autonomy.

    PASSIVE actions (recon) execute autonomously. ACTIVE actions (vuln scanning,
    exploitation) are proposed and require human approval.
    """

    PASSIVE = "passive"
    ACTIVE = "active"


class AgentActionState(str, enum.Enum):
    """Lifecycle of a single planned action."""

    PROPOSED = "proposed"       # planned ACTIVE action awaiting human approval
    APPROVED = "approved"       # ready to execute (auto for passive, human for active)
    REJECTED = "rejected"       # human declined
    EXECUTED = "executed"       # ran successfully
    FAILED = "failed"           # ran but failed (incl. scope denial)
    SKIPPED = "skipped"         # not run (e.g., tool unavailable)


class AgentRun(TimestampedBase):
    """ORM model for the ``agent_runs`` table."""

    __tablename__ = "agent_runs"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, values_callable=lambda obj: [e.value for e in obj], name="agent_run_status_enum"),
        nullable=False,
        default=AgentRunStatus.PENDING,
        server_default=AgentRunStatus.PENDING.value,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_agent_runs_workspace"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="RESTRICT", name="fk_agent_runs_target"),
        nullable=False,
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL", name="fk_agent_runs_scan"),
        nullable=True,
        doc="Backing scan that anchors findings discovered by this run.",
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_agent_runs_created_by"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    actions: Mapped[list[AgentAction]] = relationship(
        "AgentAction",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AgentAction.step_index",
    )
    target: Mapped[Target] = relationship("Target", lazy="select")
    scan: Mapped[Scan | None] = relationship("Scan", lazy="select")
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="select")
    created_by: Mapped[User] = relationship("User", lazy="select")


class AgentAction(TimestampedBase):
    """ORM model for the ``agent_actions`` table — one planned tool invocation."""

    __tablename__ = "agent_actions"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE", name="fk_agent_actions_run"),
        nullable=False,
        index=True,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="The value this action runs against — re-checked against scope at execution.",
    )
    tier: Mapped[ActionTier] = mapped_column(
        Enum(ActionTier, values_callable=lambda obj: [e.value for e in obj], name="agent_action_tier_enum"),
        nullable=False,
    )
    state: Mapped[AgentActionState] = mapped_column(
        Enum(AgentActionState, values_callable=lambda obj: [e.value for e in obj], name="agent_action_state_enum"),
        nullable=False,
        default=AgentActionState.PROPOSED,
        server_default=AgentActionState.PROPOSED.value,
        index=True,
    )
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    rationale: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Why the agent chose this action."
    )
    scope_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_ref: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[AgentRun] = relationship("AgentRun", back_populates="actions", lazy="select")
