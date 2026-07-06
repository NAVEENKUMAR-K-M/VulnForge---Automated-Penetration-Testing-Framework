"""
VulnForge FastAPI application factory.

Design:
    ``create_app()`` is a factory function rather than a module-level
    ``app`` variable.  This enables:
        - Test isolation: each test can get a fresh app instance
        - Multiple app variants (e.g., reduced-scope apps for workers)
        - Clean separation from application startup side effects

    The module-level ``app`` is created once for production/dev uvicorn.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import VulnForgeError
from app.lifespan import lifespan


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Returns:
        FastAPI: The fully configured application instance.
    """
    settings = get_settings()

    application = FastAPI(
        title="VulnForge API",
        description=(
            "**VulnForge** — Automated Penetration Testing Framework.\n\n"
            "All endpoints require authentication via JWT Bearer tokens "
            "unless explicitly marked as public.\n\n"
            "Obtain tokens via `POST /api/v1/auth/login`."
        ),
        version=settings.app_version,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ─────────────────────────────────────────────────────
    @application.exception_handler(VulnForgeError)
    async def vulnforge_exception_handler(
        request: Request,
        exc: VulnForgeError,
    ) -> JSONResponse:
        """Convert domain exceptions to standardised JSON error responses.

        Args:
            request: The incoming FastAPI request.
            exc:     The raised VulnForgeError subclass.

        Returns:
            JSONResponse: Standardised error envelope.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "request_id": request.headers.get("X-Request-ID"),
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Catch-all handler for unexpected errors.

        Logs the full traceback but returns a generic 500 response to the
        client — no internal details are leaked.

        Args:
            request: The incoming FastAPI request.
            exc:     The unhandled exception.

        Returns:
            JSONResponse: Generic 500 error response.
        """
        from app.core.logging import get_logger
        get_logger(__name__).exception(
            "unhandled_exception",
            path=str(request.url),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please try again later.",
                "request_id": request.headers.get("X-Request-ID"),
            },
        )

    # ── Routes ─────────────────────────────────────────────────────────────────
    from app.api.v1.router import router as v1_router
    application.include_router(v1_router, prefix=settings.api_prefix)

    # Health check — no auth required
    @application.get(
        "/health",
        tags=["health"],
        summary="API health check",
        include_in_schema=True,
    )
    async def health_check() -> dict:
        """Return API health status.

        Returns:
            dict: Health status with version info.
        """
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    return application


# ── Production application instance ──────────────────────────────────────────
app = create_app()
