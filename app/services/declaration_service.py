"""
app/services/declaration_service.py
=====================================
Business logic layer for EPR plastic declaration submissions.

Architecture Position:
  HTTP Route → DeclarationService → DeclarationRepository → SQLite

Design Decisions:
  - This service owns ALL business rules for the submission workflow.
    The route delegates entirely — it only calls `submit()` and returns.
  - Duplicate detection, quantity aggregation, and audit log creation
    live here — not in the route, not in the repository.
  - Zero LLM involvement. Every operation is deterministic Python.
  - The service receives an injected repository — testable in isolation
    with a mock repository and no database required.
  - Structured logging with contextual fields enables log aggregation
    and distributed tracing without additional instrumentation.
  - All domain errors are raised as typed exceptions from
    `app/core/exceptions.py` — the route's exception handler translates
    them to structured JSON responses.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import DuplicateDeclarationError, DatabaseError
from app.core.logger import get_logger
from app.database.models import DeclarationCategory, PlasticDeclaration
from app.repositories.declaration_repository import DeclarationRepository
from app.schemas.declaration_schema import (
    CategoryQuantityResponse,
    DeclarationSubmitRequest,
    DeclarationSubmitResponse,
)

logger = get_logger(__name__)


class DeclarationService:
    """
    Orchestrates the EPR plastic declaration submission workflow.

    Responsibilities:
      1. Duplicate submission guard (producer + month uniqueness).
      2. Delegates persistence to the repository (single create call).
      3. Constructs the typed API response from the persisted ORM record.
      4. Emits structured audit log entries at submission and on failure.

    Non-responsibilities (strictly enforced):
      - No HTTP concerns (status codes, headers, request parsing).
      - No LLM calls — zero AI involvement.
      - No direct database access — all via DeclarationRepository.
      - No reconciliation logic — that belongs to ReconciliationService.

    Args:
        repository: An injected DeclarationRepository instance.
    """

    def __init__(self, repository: DeclarationRepository) -> None:
        self._repo = repository

    async def submit(
        self,
        request: DeclarationSubmitRequest,
        submitted_by: Optional[str] = None,
    ) -> DeclarationSubmitResponse:
        """
        Process and persist a monthly plastic declaration.

        Workflow:
          1. Check for an existing declaration for the same producer+month.
             → Raise DuplicateDeclarationError if one already exists.
          2. Persist the declaration and its category rows via the repository.
          3. Build and return a typed response DTO.

        Args:
            request:      Validated Pydantic request body.
            submitted_by: Optional caller identity for audit tracking.

        Returns:
            A ``DeclarationSubmitResponse`` populated from the persisted record.

        Raises:
            DuplicateDeclarationError: If a declaration already exists for
                                       this producer+month combination.
            DatabaseError:             If persistence fails at infrastructure level.
        """
        producer_id = request.producer_id
        month = request.month

        logger.info(
            "Processing declaration submission",
            extra={
                "producer_id": producer_id,
                "month": month,
                "total_kg": request.declared_quantities_kg.total_kg,
                "submitted_by": submitted_by,
            },
        )

        # ── Step 1: Duplicate Guard ───────────────────────────────────
        # Deterministic uniqueness check — no LLM, no fuzzy logic.
        # The repository query hits the covering UNIQUE index on (producer_id, month).
        already_exists = await self._repo.exists(producer_id, month)
        if already_exists:
            logger.warning(
                "Duplicate declaration submission rejected",
                extra={"producer_id": producer_id, "month": month},
            )
            raise DuplicateDeclarationError(producer_id=producer_id, month=month)

        # ── Step 2: Persist ───────────────────────────────────────────
        # The repository atomically creates the PlasticDeclaration header
        # and all DeclarationCategory child rows in a single flush.
        declaration = await self._repo.create(
            producer_id=producer_id,
            month=month,
            quantities=request.declared_quantities_kg.to_category_dict(),
            submitted_by=submitted_by,
        )

        logger.info(
            "Declaration submission accepted",
            extra={
                "record_id": declaration.record_id,
                "producer_id": producer_id,
                "month": month,
                "total_declared_kg": declaration.total_declared_kg,
                "category_count": len(declaration.categories),
            },
        )

        # ── Step 3: Build Response ────────────────────────────────────
        return self._build_response(declaration)

    def _build_response(
        self, declaration: PlasticDeclaration
    ) -> DeclarationSubmitResponse:
        """
        Construct the API response DTO from a persisted ORM model instance.

        This is a pure data mapping function — no I/O, no validation,
        no business logic. Kept private as it is an internal concern.

        Args:
            declaration: The newly persisted ``PlasticDeclaration`` ORM instance.

        Returns:
            A fully populated ``DeclarationSubmitResponse``.
        """
        categories = [
            CategoryQuantityResponse(
                category=cat.category,
                declared_quantity_kg=cat.declared_quantity_kg,
            )
            for cat in sorted(declaration.categories, key=lambda c: c.category)
        ]

        return DeclarationSubmitResponse(
            record_id=declaration.record_id,
            producer_id=declaration.producer_id,
            month=declaration.month,
            total_declared_kg=declaration.total_declared_kg,
            categories=categories,
            submitted_at=declaration.submitted_at or datetime.now(timezone.utc),
            revision=declaration.revision,
        )
