"""
Reporting Service — aggregates workspace data and generates reports.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.asset import AssetType, DiscoveredAsset
from app.models.report import ReportFormat
from app.models.target import Target
from app.models.vulnerability import Vulnerability, VulnerabilitySeverity
from app.models.workspace import Workspace
from app.services.llm.provider import LLMUnavailableError, get_llm_provider
from app.services.workspace_service import WorkspaceService

logger = get_logger(__name__)

_SUMMARY_SYSTEM = (
    "You are a senior penetration tester writing the executive summary of an "
    "authorized security assessment. Write 2-4 concise paragraphs for a technical "
    "stakeholder: overall risk posture, the most significant findings and the "
    "assets they affect, and high-level remediation themes. Ground every statement "
    "ONLY in the data provided — do not invent findings, severities, or hosts. Do "
    "not include a greeting or sign-off."
)


class ReportingService:
    """Service to handle generating assessment reports."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._workspace_svc = WorkspaceService(db, settings)
        self._llm = get_llm_provider(settings)

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

        # 3. Vulnerabilities — scoped to the workspace via their scan.
        from app.models.scan import Scan

        stmt_vulns = (
            select(Vulnerability)
            .join(Scan, Vulnerability.scan_id == Scan.id)
            .where(Scan.workspace_id == workspace_id)
            .options(selectinload(Vulnerability.references))
        )
        vulns_result = await self._db.execute(stmt_vulns)
        vulnerabilities = list(vulns_result.scalars().all())

        # Order by true severity rank in Python (the DB column is an enum type).
        _rank = {
            VulnerabilitySeverity.CRITICAL: 5,
            VulnerabilitySeverity.HIGH: 4,
            VulnerabilitySeverity.MEDIUM: 3,
            VulnerabilitySeverity.LOW: 2,
            VulnerabilitySeverity.INFO: 1,
        }
        vulnerabilities.sort(key=lambda v: _rank.get(v.severity, 0), reverse=True)

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

    # ── AI Executive Summary ───────────────────────────────────────────────────

    async def _generate_ai_summary(self, data: dict[str, Any]) -> str:
        """Produce an executive summary via the LLM, or a deterministic fallback.

        The summary is grounded strictly in the aggregated findings. If an LLM
        backend isn't available (no CLI configured), a data-derived summary is
        returned instead so reports always have a summary.
        """
        if not self._settings.ai_summary_enabled:
            return ""

        prompt = self._build_summary_prompt(data)
        context = await self._retrieve_rag_context(data)
        if context:
            prompt = f"{prompt}\n\nRelevant reference material (cite by URL where used):\n{context}"

        try:
            text = await self._llm.generate(prompt, system=_SUMMARY_SYSTEM)
            logger.info("report.ai_summary", provider=self._llm.name, chars=len(text))
            return text
        except LLMUnavailableError as exc:
            logger.info("report.ai_summary_fallback", reason=str(exc))
            return self._deterministic_summary(data)
        except Exception:  # noqa: BLE001 - never fail report generation on the summary
            logger.exception("report.ai_summary_error")
            return self._deterministic_summary(data)

    def _build_summary_prompt(self, data: dict[str, Any]) -> str:
        vulns = data["vulnerabilities"]
        lines = [
            f"Workspace: {data['workspace'].name}",
            f"Assets discovered: {len(data['assets'])}",
            f"Vulnerabilities: {len(vulns)} (critical/high: {data['critical_high_count']})",
        ]
        if data.get("technologies"):
            techs = sorted({t["category"] for t in data["technologies"]})
            lines.append("Technology categories: " + ", ".join(techs))
        if data.get("ports"):
            ports = sorted({str(p.get("port")) for p in data["ports"] if p.get("port")})
            lines.append("Open ports: " + ", ".join(ports[:20]))
        if vulns:
            lines.append("\nTop findings (severity-ordered):")
            for v in vulns[:10]:
                host = v.affected_host or "n/a"
                cwe = f" {v.cwe_id}" if v.cwe_id else ""
                lines.append(f"- [{v.severity.value.upper()}]{cwe} {v.title} (host: {host})")
        else:
            lines.append("\nNo vulnerabilities were recorded.")
        return "Assessment findings:\n" + "\n".join(lines)

    async def _retrieve_rag_context(self, data: dict[str, Any]) -> str:
        """Best-effort: pull one related writeup for the top finding, with citation.

        Bounded to a single retrieval (one embedding call) so report generation
        stays fast and resilient to embedder rate limits. Failures are swallowed.
        """
        vulns = data["vulnerabilities"]
        if not vulns:
            return ""
        try:
            from app.services.rag.retrieval_service import RetrievalService

            top = vulns[0]
            query = f"{top.title} {top.cwe_id or ''}".strip()
            result = await RetrievalService(self._db, self._settings).search(query, top_k=2)
            if not result.results:
                return ""
            cites = [
                f"- {r.title} ({r.source_url or 'no url'})"
                for r in result.results
                if r.source_url
            ]
            return "\n".join(cites)
        except Exception:  # noqa: BLE001 - enrichment is optional
            logger.info("report.rag_context_skipped")
            return ""

    def _deterministic_summary(self, data: dict[str, Any]) -> str:
        vulns = data["vulnerabilities"]
        ws = data["workspace"].name
        ch = data["critical_high_count"]
        parts = [
            f"The security assessment of {ws} discovered {len(data['assets'])} asset(s) "
            f"and identified {len(vulns)} vulnerability(ies), of which {ch} are rated "
            f"critical or high severity."
        ]
        if vulns:
            top = vulns[0]
            parts.append(
                f"The most significant finding is \"{top.title}\" "
                f"({top.severity.value.upper()}), affecting {top.affected_host or 'the target'}."
            )
            sev_counts: dict[str, int] = {}
            for v in vulns:
                sev_counts[v.severity.value] = sev_counts.get(v.severity.value, 0) + 1
            breakdown = ", ".join(f"{n} {s}" for s, n in sorted(sev_counts.items()))
            parts.append(f"Severity breakdown: {breakdown}.")
            parts.append(
                "Remediation should prioritize the critical and high-severity issues, "
                "followed by configuration hardening and validation of the remaining findings."
            )
        else:
            parts.append(
                "No vulnerabilities were recorded for this workspace; continue monitoring "
                "as the attack surface evolves."
            )
        return " ".join(parts)

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
        data["ai_summary"] = await self._generate_ai_summary(data)

        if format == ReportFormat.JSON:
            json_payload = {
                "workspace": data["workspace"].name,
                "date": data["date"],
                "executive_summary": data.get("ai_summary", ""),
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
                import pdfkit  # lazy: PDF support is optional (needs pdfkit + wkhtmltopdf)

                pdf_bytes = pdfkit.from_string(html_content, False)
                return pdf_bytes, "application/pdf"
            except Exception as e:
                error_html = f"<html><body><h1>PDF Generation Failed</h1><p>{str(e)}</p><p>Ensure wkhtmltopdf is installed on the server.</p></body></html>"
                return error_html.encode('utf-8'), "application/pdf"
            
        raise ValueError(f"Unsupported report format: {format}")
