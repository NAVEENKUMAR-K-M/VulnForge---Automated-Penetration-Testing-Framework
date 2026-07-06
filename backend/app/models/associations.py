"""
Association tables for many-to-many relationships.

Design:
    Association tables use composite primary keys (no surrogate UUID) because
    the pair itself is the identity — there is no useful additional data on
    these join rows beyond the two FKs.

Tables:
    report_scans:          Report ↔ Scan  (a report covers multiple scans)
    report_vulnerabilities: Report ↔ Vulnerability (a report includes curated findings)
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, Index, Table
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base

report_scans = Table(
    "report_scans",
    Base.metadata,
    Column(
        "report_id",
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE", name="fk_report_scans_reports"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "scan_id",
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="RESTRICT", name="fk_report_scans_scans"),
        primary_key=True,
        nullable=False,
    ),
    Index("idx_report_scans_report_id", "report_id"),
    Index("idx_report_scans_scan_id", "scan_id"),
)
"""Association table linking reports to the scans they cover."""


report_vulnerabilities = Table(
    "report_vulnerabilities",
    Base.metadata,
    Column(
        "report_id",
        UUID(as_uuid=True),
        ForeignKey(
            "reports.id",
            ondelete="CASCADE",
            name="fk_report_vulns_reports",
        ),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "vulnerability_id",
        UUID(as_uuid=True),
        ForeignKey(
            "vulnerabilities.id",
            ondelete="CASCADE",
            name="fk_report_vulns_vulns",
        ),
        primary_key=True,
        nullable=False,
    ),
    Index("idx_report_vulns_report_id", "report_id"),
    Index("idx_report_vulns_vuln_id", "vulnerability_id"),
)
"""Association table linking reports to the curated vulnerabilities they contain."""
