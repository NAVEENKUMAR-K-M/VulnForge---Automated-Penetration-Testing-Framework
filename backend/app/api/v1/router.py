"""
API v1 router — aggregates all v1 endpoint routers.

Adding a new feature domain = adding one ``router.include_router()`` line.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, workspaces, targets, scope, scan_profiles

router = APIRouter(prefix="/v1")

router.include_router(auth.router)
router.include_router(workspaces.router)
router.include_router(targets.router)
router.include_router(scope.router)
router.include_router(scan_profiles.router)
# router.include_router(scans.router)
# router.include_router(vulnerabilities.router)
# router.include_router(reports.router)
# router.include_router(plugins.router)
