"""
app/repositories/declaration_repository.py
============================================
Repository pattern implementation for PlasticDeclaration persistence.

Architecture:
  - BaseRepository[T]: Generic, reusable async repository base.
  - DeclarationRepository: Concrete declaration-specific queries.

Design Decisions:
  - Repositories are PURE DATA ACCESS OBJECTS. They contain zero business
    logic, zero validation, and zero LLM calls.
  - Every method is typed end-to-end using SQLAlchemy 2.x Mapped types
    and Python generics — no `Any` shortcuts.
  - Sessions are injected (not created here) — the repository is
    stateless and reusable across request contexts.
  - All SELECT queries use explicit `select()` with `where()` clauses —
    no ORM-level lazy loading that can trigger N+1 issues.
  - `get_by_producer_month()` is the most-called method (by /submit
    duplicate check and /summary fetch) — it has a covering index via
    the UniqueConstraint defined in the model.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Generic, Optional, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.core.logger import get_logger
from app.database.models import (
    DeclarationCategory,
    PlasticCategory,
    PlasticDeclaration,
    ReconciliationLog,
    ReconciliationStatus,
)

logger = get_logger(__name__)

# Generic type variable — bound to SQLAlchemy ORM Base subclasses
ModelT = TypeVar("ModelT")


# ─────────────────────────────────────────────
# Generic Base Repository
# ─────────────────────────────────────────────

class BaseRepository(ABC, Generic[ModelT]):
    """
    Abstract generic repository providing common async CRUD operations.

    Subclasses must declare ``model_class`` and may override any method
    to add model-specific behaviour.

    Args:
        session: An injected async SQLAlchemy session. The repository
                 does not own or manage the session lifecycle.
    """

    @property
    @abstractmethod
    def model_class(self) -> type[ModelT]:
        """Return the SQLAlchemy model class this repository manages."""
        ...

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, record_id: str) -> Optional[ModelT]:
        """
        Fetch a single record by its primary key.

        Returns:
            The model instance if found, else ``None``.
        """
        result = await self._session.get(self.model_class, record_id)
        return result

    async def get_all(self) -> Sequence[ModelT]:
        """
        Fetch all records for this model (use with caution on large tables).

        Returns:
            A sequence of all model instances.
        """
        stmt = select(self.model_class)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, instance: ModelT) -> ModelT:
        """
        Persist a new model instance to the database.

        The session is not committed here — commit is managed by the
        calling service or the ``get_db`` dependency.

        Returns:
            The added instance (with server defaults populated after flush).
        """
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Remove a model instance from the database."""
        await self._session.delete(instance)
        await self._session.flush()


# ─────────────────────────────────────────────
# Declaration Repository
# ─────────────────────────────────────────────

class DeclarationRepository(BaseRepository[PlasticDeclaration]):
    """
    Data access layer for PlasticDeclaration and its child models.

    Exposes purpose-built async query methods used by the service layer.
    All queries are explicit, indexed, and return typed results.

    Responsibilities:
      - Create declarations with normalized category rows.
      - Check for duplicate submissions (producer + month uniqueness).
      - Retrieve declarations for /summary reconciliation.
      - Append reconciliation log entries.

    Non-responsibilities (enforced):
      - No validation logic.
      - No LLM calls.
      - No business rules.
      - No session lifecycle management.
    """

    @property
    def model_class(self) -> type[PlasticDeclaration]:
        return PlasticDeclaration

    # ── Queries ───────────────────────────────

    async def get_by_id(self, record_id: str) -> Optional[PlasticDeclaration]:
        """
        Fetch a declaration by its UUID record_id.

        Uses ``session.get()`` (primary key lookup — fastest path).
        Categories are loaded via ``selectin`` eager loading.
        """
        return await self._session.get(PlasticDeclaration, record_id)

    async def get_by_producer_month(
        self,
        producer_id: str,
        month: str,
    ) -> Optional[PlasticDeclaration]:
        """
        Fetch the declaration for a specific producer and reporting month.

        This is the primary lookup used by:
          - POST /submit (duplicate check)
          - GET /summary (declaration retrieval)

        Hits the ``uq_declaration_producer_month`` covering index.

        Args:
            producer_id: e.g. "GREENPACK-001"
            month:       e.g. "2026-04"

        Returns:
            The matching ``PlasticDeclaration`` or ``None`` if not found.
        """
        stmt = (
            select(PlasticDeclaration)
            .where(
                PlasticDeclaration.producer_id == producer_id,
                PlasticDeclaration.month == month,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists(self, producer_id: str, month: str) -> bool:
        """
        Check if a declaration already exists for the given producer+month.

        Used for duplicate submission guard in the service layer.
        Does NOT raise — returns a plain bool. Raising is the service's job.

        Returns:
            ``True`` if a declaration exists, ``False`` otherwise.
        """
        record = await self.get_by_producer_month(producer_id, month)
        return record is not None

    async def list_by_producer(
        self,
        producer_id: str,
        limit: int = 50,
    ) -> Sequence[PlasticDeclaration]:
        """
        Fetch recent declarations for a given producer, ordered newest first.

        Args:
            producer_id: The producer to filter by.
            limit:       Maximum number of records to return (default 50).

        Returns:
            A sequence of ``PlasticDeclaration`` instances.
        """
        stmt = (
            select(PlasticDeclaration)
            .where(PlasticDeclaration.producer_id == producer_id)
            .order_by(PlasticDeclaration.submitted_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Write Operations ──────────────────────

    async def create(
        self,
        producer_id: str,
        month: str,
        quantities: dict[str, float],
        submitted_by: Optional[str] = None,
    ) -> PlasticDeclaration:
        """
        Persist a new declaration with its normalized category rows.

        Atomically creates:
          1. The parent ``PlasticDeclaration`` header.
          2. One ``DeclarationCategory`` row per plastic type.

        Args:
            producer_id:  Registered producer identifier.
            month:        Reporting period in YYYY-MM format.
            quantities:   Dict mapping category name → declared kg.
                          e.g. {"rigid_plastic": 12000, "flexible_plastic": 8500}
            submitted_by: Optional identity of the caller (auth context).

        Returns:
            The persisted ``PlasticDeclaration`` with categories eagerly loaded.

        Raises:
            DatabaseError: If the ORM flush fails for any infrastructure reason.
        """
        total_kg = sum(quantities.values())

        declaration = PlasticDeclaration(
            record_id=str(uuid.uuid4()),
            producer_id=producer_id,
            month=month,
            total_declared_kg=total_kg,
            submitted_by=submitted_by,
            submitted_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(declaration)

        # Create one DeclarationCategory row per provided quantity
        for category_name, qty_kg in quantities.items():
            category_row = DeclarationCategory(
                id=str(uuid.uuid4()),
                declaration_id=declaration.record_id,
                category=category_name,
                declared_quantity_kg=qty_kg,
                created_at=datetime.now(timezone.utc),
            )
            self._session.add(category_row)

        try:
            await self._session.flush()
            await self._session.refresh(declaration)
        except Exception as exc:
            logger.exception(
                "Failed to persist declaration for producer=%s month=%s",
                producer_id,
                month,
            )
            raise DatabaseError(
                message="Failed to persist declaration.",
                detail={"producer_id": producer_id, "month": month},
            ) from exc

        logger.info(
            "Declaration persisted",
            extra={
                "record_id": declaration.record_id,
                "producer_id": producer_id,
                "month": month,
                "total_kg": total_kg,
                "categories": list(quantities.keys()),
            },
        )
        return declaration

    # ── Reconciliation Log ────────────────────

    async def create_reconciliation_log(
        self,
        declaration_id: str,
        erp_quantities: dict[str, float],
        has_mismatch: bool,
        mismatch_categories: list[str],
        threshold_pct: float,
        narrative_summary: Optional[str] = None,
        llm_model_used: Optional[str] = None,
        execution_ms: Optional[int] = None,
    ) -> ReconciliationLog:
        """
        Append a new reconciliation audit log entry.

        Called by the service layer after deterministic reconciliation math
        completes and (optionally) after the LLM narrative is generated.

        Args:
            declaration_id:      Parent declaration's record_id.
            erp_quantities:      Snapshot of ERP procurement data used.
            has_mismatch:        Whether any category exceeded the threshold.
            mismatch_categories: List of category names that failed the check.
            threshold_pct:       The variance threshold used in this run.
            narrative_summary:   LLM-generated text (may be None on LLM failure).
            llm_model_used:      Model identifier for observability.
            execution_ms:        Total run time in milliseconds.

        Returns:
            The persisted ``ReconciliationLog`` instance.

        Raises:
            DatabaseError: If the ORM flush fails.
        """
        log_entry = ReconciliationLog(
            id=str(uuid.uuid4()),
            declaration_id=declaration_id,
            erp_rigid_kg=erp_quantities.get(PlasticCategory.RIGID.value),
            erp_flexible_kg=erp_quantities.get(PlasticCategory.FLEXIBLE.value),
            erp_multilayer_kg=erp_quantities.get(PlasticCategory.MULTILAYER.value),
            status=ReconciliationStatus.COMPLETED,
            has_mismatch=has_mismatch,
            mismatch_categories=",".join(mismatch_categories) if mismatch_categories else None,
            threshold_used_pct=threshold_pct,
            narrative_summary=narrative_summary,
            llm_model_used=llm_model_used,
            reconciled_at=datetime.now(timezone.utc),
            execution_ms=execution_ms,
        )
        self._session.add(log_entry)

        try:
            await self._session.flush()
            await self._session.refresh(log_entry)
        except Exception as exc:
            logger.exception(
                "Failed to persist reconciliation log for declaration_id=%s",
                declaration_id,
            )
            raise DatabaseError(
                message="Failed to persist reconciliation log.",
                detail={"declaration_id": declaration_id},
            ) from exc

        logger.info(
            "Reconciliation log persisted",
            extra={
                "log_id": log_entry.id,
                "declaration_id": declaration_id,
                "has_mismatch": has_mismatch,
                "mismatch_categories": mismatch_categories,
                "execution_ms": execution_ms,
            },
        )
        return log_entry

    async def get_latest_reconciliation_log(
        self,
        declaration_id: str,
    ) -> Optional[ReconciliationLog]:
        """
        Fetch the most recent reconciliation log for a given declaration.

        Used by GET /summary to return the latest reconciliation result
        if the service opts to cache instead of re-running.

        Returns:
            The most recent ``ReconciliationLog`` or ``None``.
        """
        stmt = (
            select(ReconciliationLog)
            .where(ReconciliationLog.declaration_id == declaration_id)
            .order_by(ReconciliationLog.reconciled_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_categories_for_declaration(
        self,
        declaration_id: str,
    ) -> Sequence[DeclarationCategory]:
        """
        Fetch all category rows for a given declaration.

        Ordered alphabetically by category name for consistent output.

        Returns:
            A sequence of ``DeclarationCategory`` rows.
        """
        stmt = (
            select(DeclarationCategory)
            .where(DeclarationCategory.declaration_id == declaration_id)
            .order_by(DeclarationCategory.category)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
