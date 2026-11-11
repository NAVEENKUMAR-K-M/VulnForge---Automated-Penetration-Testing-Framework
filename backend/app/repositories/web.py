"""
Repositories for the web attack surface: endpoints and captured transactions.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.web import HttpEndpoint, HttpMethod, HttpTransaction
from app.repositories.base import BaseRepository
from app.schemas.web import HttpEndpointCreate, HttpTransactionCreate

# Cap stored bodies so a huge response can't bloat a row.
_MAX_BODY = 200_000


def _clip(value: str | None) -> str | None:
    if value is None:
        return None
    return value if len(value) <= _MAX_BODY else value[:_MAX_BODY] + "\n…[truncated]"


class EndpointRepository(BaseRepository[HttpEndpoint, dict, dict]):
    """Data access + dedupe upsert for discovered HTTP endpoints."""

    model = HttpEndpoint

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def ingest_endpoints(
        self,
        workspace_id: uuid.UUID,
        target_id: uuid.UUID,
        scan_id: uuid.UUID | None,
        endpoints: list[HttpEndpointCreate],
    ) -> int:
        """Upsert endpoints, deduplicating on (workspace, method, url).

        On conflict: merge source_tools (distinct), take the richer parameter
        set, merge metadata, fill in status/content-type, and OR requires_auth.
        """
        if not endpoints:
            return 0

        values = []
        for e in endpoints:
            values.append({
                "workspace_id": workspace_id,
                "target_id": target_id,
                "scan_id": scan_id,
                "method": e.method,
                "url": e.url,
                "status_code": e.status_code,
                "content_type": e.content_type,
                "parameters": [p.model_dump(mode="json") for p in e.parameters],
                "source_tools": [e.source_tool],
                "metadata": e.metadata,
                "requires_auth": e.requires_auth,
            })

        stmt = insert(HttpEndpoint).values(values)

        merge_tools = func.coalesce(
            select(func.jsonb_agg(func.distinct(text("elem"))))
            .select_from(func.jsonb_array_elements(
                HttpEndpoint.source_tools.op("||")(stmt.excluded.source_tools)
            ).alias("elem")).scalar_subquery(),
            stmt.excluded.source_tools,
        )
        # Prefer the newly-reported parameter set when it is non-empty.
        keep_params = func.coalesce(
            func.nullif(stmt.excluded.parameters, text("'[]'::jsonb")),
            HttpEndpoint.parameters,
        )

        update_stmt = stmt.on_conflict_do_update(
            constraint="uq_http_endpoints_workspace_method_url",
            set_={
                "source_tools": merge_tools,
                "parameters": keep_params,
                "metadata": HttpEndpoint.metadata_dict.op("||")(stmt.excluded.metadata),
                "status_code": func.coalesce(stmt.excluded.status_code, HttpEndpoint.status_code),
                "content_type": func.coalesce(stmt.excluded.content_type, HttpEndpoint.content_type),
                "requires_auth": HttpEndpoint.requires_auth.op("OR")(stmt.excluded.requires_auth),
                "is_active": text("TRUE"),
                "updated_at": func.now(),
            },
        )

        await self._session.execute(update_stmt)
        await self._session.flush()
        return len(endpoints)

    async def list_endpoints(
        self,
        workspace_id: uuid.UUID,
        target_id: uuid.UUID | None = None,
        method: HttpMethod | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[HttpEndpoint], int]:
        """Paginated list of active endpoints for a workspace."""
        conditions: list[Any] = [
            HttpEndpoint.workspace_id == workspace_id,
            HttpEndpoint.is_active.is_(True),
        ]
        if target_id:
            conditions.append(HttpEndpoint.target_id == target_id)
        if method:
            conditions.append(HttpEndpoint.method == method)
        if search:
            conditions.append(HttpEndpoint.url.ilike(f"%{search}%"))

        count_stmt = select(func.count(HttpEndpoint.id)).where(and_(*conditions))
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(HttpEndpoint)
            .where(and_(*conditions))
            .order_by(HttpEndpoint.url, HttpEndpoint.method)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total


class TransactionRepository(BaseRepository[HttpTransaction, dict, dict]):
    """Append-only capture of request/response evidence."""

    model = HttpTransaction

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def add_transactions(
        self,
        workspace_id: uuid.UUID,
        scan_id: uuid.UUID | None,
        transactions: list[HttpTransactionCreate],
        vulnerability_id: uuid.UUID | None = None,
    ) -> int:
        """Persist captured transactions, linking each to a known endpoint by URL."""
        if not transactions:
            return 0

        # Resolve endpoint_url → endpoint_id for this workspace in one query.
        wanted = {t.endpoint_url for t in transactions if t.endpoint_url}
        url_to_id: dict[str, uuid.UUID] = {}
        if wanted:
            rows = await self._session.execute(
                select(HttpEndpoint.url, HttpEndpoint.id).where(
                    HttpEndpoint.workspace_id == workspace_id,
                    HttpEndpoint.url.in_(wanted),
                )
            )
            for url, eid in rows.all():
                url_to_id.setdefault(url, eid)

        rows_to_add = []
        for t in transactions:
            endpoint_id = url_to_id.get(t.endpoint_url) if t.endpoint_url else None
            rows_to_add.append(
                HttpTransaction(
                    workspace_id=workspace_id,
                    scan_id=scan_id,
                    endpoint_id=endpoint_id,
                    vulnerability_id=vulnerability_id,
                    source=t.source,
                    method=t.method,
                    url=t.url,
                    request_headers=t.request_headers,
                    request_body=_clip(t.request_body),
                    status_code=t.status_code,
                    response_headers=t.response_headers,
                    response_body=_clip(t.response_body),
                    duration_ms=t.duration_ms,
                    notes=t.notes,
                )
            )
        self._session.add_all(rows_to_add)
        await self._session.flush()
        return len(rows_to_add)

    async def list_transactions(
        self,
        workspace_id: uuid.UUID,
        endpoint_id: uuid.UUID | None = None,
        vulnerability_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[HttpTransaction], int]:
        """Paginated list of captured transactions for a workspace."""
        conditions: list[Any] = [HttpTransaction.workspace_id == workspace_id]
        if endpoint_id:
            conditions.append(HttpTransaction.endpoint_id == endpoint_id)
        if vulnerability_id:
            conditions.append(HttpTransaction.vulnerability_id == vulnerability_id)

        count_stmt = select(func.count(HttpTransaction.id)).where(and_(*conditions))
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(HttpTransaction)
            .where(and_(*conditions))
            .order_by(HttpTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total
