"""
Reporting Service — aggregates workspace data and generates reports.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

import pdfkit
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.asset import AssetType, DiscoveredAsset
from app.models.report import ReportFormat
from app.models.target import Target
from app.models.vulnerability import Vulnerability, VulnerabilitySeverity
from app.models.workspace import Workspace
from app.services.workspace_service import WorkspaceService


class ReportingService:
    """Service to handle generating assessment reports."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._workspace_svc = WorkspaceService(db, settings)

        # Setup Jinja2 templates
        template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../templates/reports"))
        self._jinja_env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
        if 'tojson' not in self._jinja_env.filters:
            self._jinja_env.filters['tojson'] = json.dumps

    async def _gather_workspace_data(self, workspace_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate all relevant data for a workspace."""
        
        # 1. Workspace info
        stmt_ws = select(Workspace).where(Workspace.id == workspace_id)
        ws_result = await self._db.execute(stmt_ws)
        workspace = ws_result.scalar_one_or_none()
        if not workspace:
            raise ValueError("Workspace not found")

        # 2. Assets
        stmt_assets = select(DiscoveredAsset).where(
            DiscoveredAsset.workspace_id == workspace_id,
            DiscoveredAsset.is_active == True
        )
        assets_result = await self._db.execute(stmt_assets)
        assets = list(assets_result.scalars().all())

        # 3. Vulnerabilities
        stmt_vulns = (
            select(Vulnerability)
            .join(Target, Vulnerability.target_id == Target.id)
            .where(Target.workspace_id == workspace_id)
            .options(selectinload(Vulnerability.references))
            .order_by(Vulnerability.severity.desc())
        )
        vulns_result = await self._db.execute(stmt_vulns)
        vulnerabilities = list(vulns_result.scalars().all())

        # Derived metrics
        critical_high_count = sum(
            1 for v in vulnerabilities 
            if v.severity in (VulnerabilitySeverity.CRITICAL, VulnerabilitySeverity.HIGH)
        )

        ports = []
        technologies = []
        screenshots = []

        for asset in assets:
            meta = asset.metadata_dict
            if not meta:
                continue
                
            if "open_ports" in meta and isinstance(meta["open_ports"], list):
                for p in meta["open_ports"]:
                    ports.append({
                        "host": asset.value,
                        "port": p.get("port"),
                        "service": p.get("service"),
                        "version": p.get("version", ""),
                        "os": meta.get("os_matches", [""])[0] if "os_matches" in meta and meta["os_matches"] else ""
                    })

            if "structured_tech" in meta:
                tech_data = meta["structured_tech"]
                for category, items in tech_data.items():
                    if items:
                        technologies.append({
                            "asset": asset.value,
                            "category": category,
                            "items": items
                        })

            if "screenshot_path" in meta:
                screenshots.append({
                    "asset": asset.value,
                    "path": meta["screenshot_path"]
                })

        return {
            "workspace": workspace,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "assets": assets,
            "vulnerabilities": vulnerabilities,
            "critical_high_count": critical_high_count,
            "ports": ports,
            "technologies": technologies,
            "screenshots": screenshots,
        }

    async def generate_report_sync(
        self, 
        workspace_id: uuid.UUID, 
        format: ReportFormat
    ) -> tuple[str | bytes, str]:
        """
        Generate the report data synchronously.
        Returns a tuple of (content, content_type).
        """
        data = await self._gather_workspace_data(workspace_id)

        if format == ReportFormat.JSON:
            json_payload = {
                "workspace": data["workspace"].name,
                "date": data["date"],
                "stats": {
                    "total_assets": len(data["assets"]),
                    "total_vulnerabilities": len(data["vulnerabilities"]),
                    "critical_high_findings": data["critical_high_count"],
                },
                "vulnerabilities": [
                    {
                        "title": v.title,
                        "severity": v.severity.value,
                        "cve_id": v.cve_id,
                        "host": v.affected_host,
                    } for v in data["vulnerabilities"]
                ]
            }
            return json.dumps(json_payload, indent=2), "application/json"

        elif format == ReportFormat.MARKDOWN:
            template = self._jinja_env.get_template("report.md.j2")
            rendered = template.render(**data)
            return rendered, "text/markdown"

        elif format == ReportFormat.HTML:
            template = self._jinja_env.get_template("report.html.j2")
            rendered = template.render(**data)
            return rendered, "text/html"

        elif format == ReportFormat.PDF:
            template = self._jinja_env.get_template("report.html.j2")
            html_content = template.render(**data)
            try:
                pdf_bytes = pdfkit.from_string(html_content, False)
                return pdf_bytes, "application/pdf"
            except Exception as e:
                error_html = f"<html><body><h1>PDF Generation Failed</h1><p>{str(e)}</p><p>Ensure wkhtmltopdf is installed on the server.</p></body></html>"
                return error_html.encode('utf-8'), "application/pdf"
            
        raise ValueError(f"Unsupported report format: {format}")
