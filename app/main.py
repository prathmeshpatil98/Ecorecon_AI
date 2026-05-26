"""
app/main.py
============
EcoRecon AI — FastAPI application entrypoint.

Responsibilities:
  - Construct and configure the FastAPI application instance.
  - Register all domain exception handlers (no stack trace leakage).
  - Mount API routers under versioned prefixes.
  - Manage database lifecycle via asynccontextmanager lifespan.
  - Expose /health for container readiness probes.

This module contains ZERO business logic. It is purely wiring.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from app.api import submit_routes, summary_routes, ask_routes

from app.core.config import get_settings
from app.core.exceptions import EcoReconError
from app.core.logger import get_logger
from app.database.db import close_db, init_db

logger = get_logger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────
# Lifespan — startup / shutdown
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle events.

    Startup:
      - Initialise SQLite tables (idempotent).
      - Log platform boot summary.

    Shutdown:
      - Dispose database connection pool cleanly.
    """
    logger.info(
        "EcoRecon AI starting up",
        extra={
            "version": settings.app_version,
            "env": settings.app_env,
            "db": settings.database_url,
        },
    )

    await init_db()
    logger.info("Database initialised.")

    yield  # ← Application runs here

    logger.info("EcoRecon AI shutting down — disposing resources.")
    await close_db()


# ─────────────────────────────────────────────
# Application Factory
# ─────────────────────────────────────────────

def create_application() -> FastAPI:
    """
    Construct and return the configured FastAPI application.

    Separating application creation from module-level instantiation allows
    test fixtures to create isolated instances without side effects.
    """
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        description=settings.app_description,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Exception Handlers ---
    _register_exception_handlers(app)

    # --- Routers ---
    _register_routers(app)

    # --- Infrastructure Routes ---
    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        """Redirect incoming root requests directly to /docs."""
        return RedirectResponse(url="/docs")

    @app.get("/health", tags=["Infrastructure"], summary="Container readiness probe")
    async def health_check() -> dict[str, str]:
        """
        Lightweight readiness probe for Docker / Kubernetes health checks.

        Returns 200 OK when the application is up and the database layer
        has been initialised. Does NOT perform a live DB query to keep it fast.
        """
        return {
            "status": "ok",
            "service": settings.app_title,
            "version": settings.app_version,
            "env": settings.app_env,
        }

    return app


# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────

def _register_exception_handlers(app: FastAPI) -> None:
    """
    Map domain exceptions to structured JSON HTTP responses.

    No stack traces are exposed to API consumers. Full tracebacks are
    captured by the logger for internal observability.
    """

    @app.exception_handler(EcoReconError)
    async def ecorecon_error_handler(
        request: Request, exc: EcoReconError
    ) -> JSONResponse:
        logger.warning(
            "Domain error: %s — %s",
            exc.error_code,
            exc.message,
            extra={"path": str(request.url), "detail": exc.detail},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url,
        )
        content: dict[str, Any] = {
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please contact support.",
        }
        if settings.app_debug:
            content["debug"] = str(exc)
        return JSONResponse(status_code=500, content=content)


# ─────────────────────────────────────────────
# Router Registration
# ─────────────────────────────────────────────

def _register_routers(app: FastAPI) -> None:
    """
    Mount all API routers.

    Routers are imported here (not at module top-level) to avoid circular
    imports during application initialisation.
    """

    app.include_router(submit_routes.router, prefix="/api/v1", tags=["Ingestion"])
    app.include_router(summary_routes.router, prefix="/api/v1", tags=["Reconciliation"])
    app.include_router(ask_routes.router, prefix="/api/v1", tags=["Intelligence"])


# ─────────────────────────────────────────────
# Health Endpoint (Module Level Reference)
# ─────────────────────────────────────────────

# Build the app instance at module level (used by uvicorn when run in non-factory mode)
app = create_application()
