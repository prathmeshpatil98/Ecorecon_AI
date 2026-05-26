"""
app/api/submit_routes.py
=========================
HTTP route for POST /submit — EPR plastic declaration ingestion.

Architecture Responsibilities (this file only):
  - Parse and validate the request body (delegated to Pydantic).
  - Wire up dependency injection (DB session → Repository → Service).
  - Call the service and return the typed response.
  - Declare OpenAPI metadata (tags, summary, responses).

Architecture Non-Responsibilities (strictly enforced):
  - Zero business logic — no validation rules, no duplicate checks.
  - Zero LLM calls — this endpoint is purely deterministic.
  - Zero direct database access — all via the injected service.
  - Zero reconciliation logic — that belongs to summary_routes.py.

Dependency Injection Chain:
  get_db() → AsyncSession
    → DeclarationRepository(session)
      → DeclarationService(repository)
        → route handler
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import DuplicateDeclarationError
from app.core.logger import get_logger
from app.database.db import DBSession
from app.repositories.declaration_repository import DeclarationRepository
from app.schemas.declaration_schema import (
    DeclarationErrorResponse,
    DeclarationSubmitRequest,
    DeclarationSubmitResponse,
)
from app.services.declaration_service import DeclarationService

logger = get_logger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────
# Dependency Factories
# ─────────────────────────────────────────────

def get_declaration_repository(db: DBSession) -> DeclarationRepository:
    """
    FastAPI dependency that constructs a DeclarationRepository.

    The async session (``db``) is injected by the ``get_db`` dependency
    defined in ``app/database/db.py``. The repository receives the session
    and uses it for all queries within the request lifecycle.
    """
    return DeclarationRepository(session=db)


def get_declaration_service(
    repository: Annotated[DeclarationRepository, Depends(get_declaration_repository)],
) -> DeclarationService:
    """
    FastAPI dependency that constructs a DeclarationService.

    The repository is injected by FastAPI's dependency resolution.
    The service is stateless — a new instance per request is safe and cheap.
    """
    return DeclarationService(repository=repository)


# ─────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────

@router.post(
    "/submit",
    response_model=DeclarationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit monthly plastic declaration",
    description=(
        "**Deterministic ingestion endpoint.** "
        "Accepts GreenPack's monthly EPR plastic declaration, validates it, "
        "and persists it to the compliance database. "
        "No LLM or AI involvement — validation is purely deterministic. "
        "\n\n"
        "**Validation rules enforced:**\n"
        "- `producer_id`: Uppercase alphanumeric with hyphens (e.g. `GREENPACK-001`).\n"
        "- `month`: Must match `YYYY-MM` format with a valid month (01–12).\n"
        "- All quantities: Must be `>= 0`. Total must be `> 0`.\n"
        "- Duplicate submissions (same `producer_id` + `month`) are rejected with `409`.\n"
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Declaration successfully ingested and persisted.",
            "model": DeclarationSubmitResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "A declaration for this producer and month already exists.",
            "model": DeclarationErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Request body failed deterministic validation.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database infrastructure error.",
            "model": DeclarationErrorResponse,
        },
    },
)
async def submit_declaration(
    request: Request,
    payload: DeclarationSubmitRequest,
    service: Annotated[DeclarationService, Depends(get_declaration_service)],
) -> DeclarationSubmitResponse:
    """
    **POST /submit** — Ingest a monthly EPR plastic declaration.

    Validates the payload deterministically (Pydantic v2), checks for
    duplicate submissions, and persists the record to SQLite.

    **This endpoint never calls an LLM.** Validation and persistence
    are deterministic operations — the correctness of compliance data
    must not depend on probabilistic AI inference.

    Args:
        request: The raw FastAPI Request (used for caller identity extraction).
        payload: Validated request body (Pydantic v2 schema).
        service: Injected DeclarationService (via FastAPI DI).

    Returns:
        The persisted declaration record with UUID, timestamp, and
        per-category quantity breakdown.
    """
    # Extract caller identity if available (from auth middleware, future scope)
    # For now, fall back to the client IP as a lightweight audit marker.
    submitted_by = request.headers.get("X-User-ID") or str(request.client.host)

    logger.info(
        "POST /submit received",
        extra={
            "producer_id": payload.producer_id,
            "month": payload.month,
            "client": submitted_by,
        },
    )

    # Delegate entirely to the service — no business logic in this route
    response = await service.submit(
        request=payload,
        submitted_by=submitted_by,
    )

    logger.info(
        "POST /submit completed",
        extra={
            "record_id": response.record_id,
            "producer_id": response.producer_id,
            "month": response.month,
        },
    )

    return response
