"""
Scope API router — HTTP endpoints for workspace scope management.

Scope rules are nested under workspaces:
    /workspaces/{workspace_id}/scope/...

Endpoints:
    GET    /workspaces/{id}/scope                       Scope overview
    GET    /workspaces/{id}/scope/rules                 List rules
    POST   /workspaces/{id}/scope/rules                 Create rule
    POST   /workspaces/{id}/scope/rules/import          Bulk import rules
    POST   /workspaces/{id}/scope/check                 Ad-hoc scope check
    GET    /workspaces/{id}/scope/rules/{rule_id}       Get rule
    PATCH  /workspaces/{id}/scope/rules/{rule_id}       Update rule
    DELETE /workspaces/{id}/scope/rules/{rule_id}       Delete rule
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import (
    CurrentUserDep,
    DatabaseDep,
    SettingsDep,
    get_client_ip,
)
from app.core.constants import API_SCOPE_TAG
from app.models.scope import ScopeDisposition, ScopeRuleType
from app.schemas.scope import (
    BulkScopeImport,
    ScopeCheckRequest,
    ScopeCheckResponse,
    ScopeRuleCreate,
    ScopeRuleResponse,
    ScopeRuleUpdate,
    WorkspaceScopeOverview,
)
from app.services.scope_service import ScopeService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/scope",
    tags=[API_SCOPE_TAG],
)


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_scope_service(db: DatabaseDep, settings: SettingsDep) -> ScopeService:
    """Construct and return a ScopeService for the current request."""
    return ScopeService(db=db, settings=settings)


ScopeServiceDep = Annotated[ScopeService, Depends(get_scope_service)]


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=WorkspaceScopeOverview,
    status_code=status.HTTP_200_OK,
    summary="Get workspace scope overview",
    description=(
        "Return a summary of the workspace's scope configuration: "
        "count of active/inactive rules, allow vs. exclude breakdown, "
        "and per-type distribution. "
        "If `has_scope_defined` is False, no scans can be run against this workspace."
    ),
)
async def get_scope_overview(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> WorkspaceScopeOverview:
    return await svc.get_overview(workspace_id=workspace_id, current_user=current_user)


# ── Rules CRUD ────────────────────────────────────────────────────────────────

@router.get(
    "/rules",
    response_model=list[ScopeRuleResponse],
    status_code=status.HTTP_200_OK,
    summary="List scope rules",
    description=(
        "Return scope rules for the workspace. "
        "Optionally filter by disposition (allow/exclude) or rule type."
    ),
)
async def list_scope_rules(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
    active_only: bool = Query(True, description="Exclude inactive rules."),
    disposition: ScopeDisposition | None = Query(None, description="Filter by disposition."),
    rule_type: ScopeRuleType | None = Query(None, description="Filter by rule type."),
) -> list[ScopeRuleResponse]:
    return await svc.list_rules(
        workspace_id=workspace_id,
        current_user=current_user,
        active_only=active_only,
        disposition=disposition,
        rule_type=rule_type,
    )


@router.post(
    "/rules",
    response_model=ScopeRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scope rule",
    description=(
        "Add a new scope rule to the workspace. "
        "The `value` is validated against `rule_type` at the API layer. "
        "Requires workspace **OWNER** role.\n\n"
        "**Rule Type Semantics:**\n"
        "- **domain**: Exact FQDN match only — `example.com` does NOT match subdomains\n"
        "- **subdomain**: Matches all subdomains — `example.com` matches `api.example.com`\n"
        "- **cidr**: IPv4/IPv6 network range — `10.0.0.0/24` matches all hosts in that range\n"
        "- **wildcard**: Glob pattern — `*.dev.example.com` matches one level of subdomains\n"
        "- **host**: Single IP exact match — `192.168.1.100`\n\n"
        "**Disposition:**\n"
        "- **allow**: Target matching this rule is in scope\n"
        "- **exclude**: Target matching this rule is out of scope (exclude overrides allow)"
    ),
)
async def create_scope_rule(
    request: Request,
    workspace_id: uuid.UUID,
    data: ScopeRuleCreate,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> ScopeRuleResponse:
    ip = get_client_ip(request)
    return await svc.create_rule(
        workspace_id=workspace_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.post(
    "/rules/import",
    response_model=list[ScopeRuleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import scope rules",
    description=(
        "Import multiple scope rules in a single request (max 100). "
        "Duplicate rules (same type+disposition+value) are silently skipped. "
        "Set `replace_existing=true` to clear all existing rules first. "
        "Requires workspace **OWNER** role."
    ),
)
async def bulk_import_scope_rules(
    request: Request,
    workspace_id: uuid.UUID,
    data: BulkScopeImport,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> list[ScopeRuleResponse]:
    ip = get_client_ip(request)
    return await svc.bulk_import(
        workspace_id=workspace_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.get(
    "/rules/{rule_id}",
    response_model=ScopeRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a scope rule",
)
async def get_scope_rule(
    workspace_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> ScopeRuleResponse:
    return await svc.get_rule(
        workspace_id=workspace_id,
        rule_id=rule_id,
        current_user=current_user,
    )


@router.patch(
    "/rules/{rule_id}",
    response_model=ScopeRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a scope rule",
    description=(
        "Update a scope rule's description, active status, or disposition. "
        "The `value` and `rule_type` cannot be changed — delete and recreate for that. "
        "Requires workspace **OWNER** role."
    ),
)
async def update_scope_rule(
    request: Request,
    workspace_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: ScopeRuleUpdate,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> ScopeRuleResponse:
    ip = get_client_ip(request)
    return await svc.update_rule(
        workspace_id=workspace_id,
        rule_id=rule_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scope rule",
    description=(
        "Permanently delete a scope rule. "
        "Use PATCH with `is_active=false` to temporarily disable without deleting. "
        "Requires workspace **OWNER** role."
    ),
)
async def delete_scope_rule(
    request: Request,
    workspace_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> Response:
    ip = get_client_ip(request)
    await svc.delete_rule(
        workspace_id=workspace_id,
        rule_id=rule_id,
        current_user=current_user,
        ip_address=ip,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Scope Check ───────────────────────────────────────────────────────────────

@router.post(
    "/check",
    response_model=ScopeCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check if a target is in scope",
    description=(
        "Test whether a target value would be permitted by the workspace's scope rules. "
        "This is the same check that runs before every scan. "
        "Use this to validate your scope configuration interactively.\n\n"
        "**Verdicts:**\n"
        "- **permitted**: Target matches an ALLOW rule and no EXCLUDE rule\n"
        "- **denied**: Target matches an EXCLUDE rule, or no ALLOW rule matches\n"
        "- **no_scope_defined**: No active rules exist — all scans are blocked\n\n"
        "This endpoint does NOT trigger a scan."
    ),
)
async def check_scope(
    workspace_id: uuid.UUID,
    request_body: ScopeCheckRequest,
    current_user: CurrentUserDep,
    svc: ScopeServiceDep,
) -> ScopeCheckResponse:
    return await svc.check_scope(
        workspace_id=workspace_id,
        request=request_body,
        current_user=current_user,
    )
