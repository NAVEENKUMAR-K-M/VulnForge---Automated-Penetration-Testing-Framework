import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target import Target
from app.models.user import User
from app.models.web import HttpMethod, TransactionSource
from app.models.workspace import Workspace
from app.repositories.web import EndpointRepository, TransactionRepository
from app.schemas.web import (
    EndpointParameter,
    HttpEndpointCreate,
    HttpTransactionCreate,
)


async def _seed(db_session: AsyncSession, user: User) -> tuple[uuid.UUID, uuid.UUID]:
    workspace = Workspace(id=uuid.uuid4(), name="WS", owner_id=user.id)
    target = Target(
        id=uuid.uuid4(), name="t", value="example.com",
        target_type="domain", created_by_id=user.id,
    )
    db_session.add_all([workspace, target])
    await db_session.flush()
    return workspace.id, target.id


@pytest.mark.asyncio
async def test_ingest_endpoints_dedupes_and_merges(
    db_session: AsyncSession, test_user: User
) -> None:
    ws_id, target_id = await _seed(db_session, test_user)
    repo = EndpointRepository(db_session)

    await repo.ingest_endpoints(ws_id, target_id, None, [
        HttpEndpointCreate(
            method=HttpMethod.GET, url="https://example.com/login",
            source_tool="crawler", status_code=200,
            parameters=[EndpointParameter(name="next")],
        ),
    ])
    # Same (method, url) from another tool with richer params → merge, not duplicate.
    await repo.ingest_endpoints(ws_id, target_id, None, [
        HttpEndpointCreate(
            method=HttpMethod.GET, url="https://example.com/login",
            source_tool="zap",
            parameters=[EndpointParameter(name="next"), EndpointParameter(name="redirect")],
        ),
        HttpEndpointCreate(
            method=HttpMethod.POST, url="https://example.com/login",
            source_tool="crawler",
        ),
    ])

    rows, total = await repo.list_endpoints(ws_id)
    assert total == 2  # GET+POST /login are distinct; the GET was deduped
    get_row = next(r for r in rows if r.method == HttpMethod.GET)
    assert set(get_row.source_tools) == {"crawler", "zap"}
    assert {p["name"] for p in get_row.parameters} == {"next", "redirect"}
    assert get_row.status_code == 200  # preserved from the first report


@pytest.mark.asyncio
async def test_add_transactions_links_endpoint(
    db_session: AsyncSession, test_user: User
) -> None:
    ws_id, target_id = await _seed(db_session, test_user)
    endpoints = EndpointRepository(db_session)
    await endpoints.ingest_endpoints(ws_id, target_id, None, [
        HttpEndpointCreate(method=HttpMethod.GET, url="https://example.com/api", source_tool="crawler"),
    ])

    txs = TransactionRepository(db_session)
    n = await txs.add_transactions(ws_id, None, [
        HttpTransactionCreate(
            source=TransactionSource.DAST, method=HttpMethod.GET,
            url="https://example.com/api?q=1", endpoint_url="https://example.com/api",
            status_code=200, response_body="ok",
        ),
    ])
    assert n == 1

    rows, total = await txs.list_transactions(ws_id)
    assert total == 1
    assert rows[0].endpoint_id is not None  # resolved to the known endpoint
    assert rows[0].source == TransactionSource.DAST
