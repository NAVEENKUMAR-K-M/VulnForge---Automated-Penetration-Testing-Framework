"""
Scan Pydantic schemas — request/response structures for scan orchestration.

A Scan is created against a single Target.  The operator either selects a
ScanProfile (whose enabled plugins are resolved at creation time) or relies on
the ``scan_type`` to pick enabled plugins by PTES phase.  The resolved plugin
set is persisted on ``Scan.configuration["resolved_plugins"]`` and executed by
the Celery ``run_scan`` task.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.scan import Priority, ScanStatus, ScanType
from app.models.scan_plugin_execution import PluginExecutionStatus
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class ScanCreate(VulnForgeBaseModel):
    """Request body for creating (and dispatching) a scan."""

    name: str = Field(min_length=1, max_length=300, description="Human-readable scan label.")
    target_id: uuid.UUID = Field(description="The target to assess. Must be in workspace scope.")
    scan_type: ScanType = Field(
        default=ScanType.RECONNAISSANCE,
        description="PTES phase(s) to run when no profile is supplied.",
    )
    profile_id: uuid.UUID | None = Field(
        default=None,
        description="Optional scan profile. Its enabled plugins are resolved at creation.",
    )
    priority: Priority | None = Field(default=None, description="Queue priority override.")
    description: str | None = Field(default=None, description="Optional scan context.")
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Scan-level configuration overrides applied to all plugins.",
    )


class PluginExecutionResponse(TimestampedResponse):
    """A single plugin's execution record within a scan."""

    scan_id: uuid.UUID
    plugin_id: uuid.UUID
    status: PluginExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    exit_code: int | None
    error_message: str | None


class ScanResponse(TimestampedResponse):
    """Full scan detail."""

    name: str
    description: str | None
    status: ScanStatus
    target_id: uuid.UUID
    workspace_id: uuid.UUID | None
    scan_type: ScanType
    priority: Priority
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    celery_task_id: str | None


class ScanSummary(VulnForgeBaseModel):
    """Compact scan row for list views."""

    id: uuid.UUID
    name: str
    status: ScanStatus
    scan_type: ScanType
    target_id: uuid.UUID
    workspace_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
