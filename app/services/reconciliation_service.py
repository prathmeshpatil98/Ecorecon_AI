"""
app/services/reconciliation_service.py
========================================
Deterministic EPR reconciliation engine for EcoRecon AI.

Architecture Position:
  GET /summary route → ReconciliationService → ERPService + DeclarationRepository
                                             → ReconciliationResult (pure Python)
                                             → LLM layer (narrative only)
                                             → SummaryResponse

Responsibilities:
  1. Fetch the stored declaration from the database.
  2. Load the ERP procurement snapshot from the CSV feed.
  3. Execute per-category mismatch analysis — pure arithmetic, no LLM.
  4. Classify each category's severity tier deterministically.
  5. Compute aggregate totals and overall compliance status.
  6. Persist an audit ReconciliationLog entry.
  7. Return a typed ReconciliationResult to the caller (LLM layer or route).

STRICT ENFORCEMENT:
  - ZERO LLM calls in this service.
  - ZERO semantic reasoning.
  - ALL mismatch detection is arithmetic: abs(declared − procured) / declared × 100.
  - The 5% threshold comes from configuration — never hardcoded.
  - This service is the source of truth for compliance analysis.
    The LLM layer reads its output; it NEVER influences its computation.

Design Decisions:
  - ReconciliationService is injected with both its dependencies (repository
    and ERP service) — it can be tested in isolation with mocks.
  - Execution time is measured and stored in the audit log for observability.
  - Edge cases are handled deterministically:
      * declared_kg == 0 → deviation_pct = 0.0 (no EPR obligation)
      * procured_kg == 0 while declared > 0 → MISSING severity, always flagged
      * No ERP data at all → status = NO_ERP_DATA, all categories flagged
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from app.core.config import get_settings
from app.core.exceptions import DeclarationNotFoundError
from app.core.logger import get_logger
from app.database.models import PlasticCategory
from app.repositories.declaration_repository import DeclarationRepository
from app.schemas.erp_schema import ERPProcurementSnapshot
from app.schemas.summary_schema import (
    CategoryReconciliation,
    MismatchSeverity,
    ReconciliationResult,
    ReconciliationStatus,
)
from app.services.erp_service import ERPService

logger = get_logger(__name__)

# Ordered category list — deterministic iteration order across the engine
_ALL_CATEGORIES: tuple[str, ...] = (
    PlasticCategory.RIGID.value,
    PlasticCategory.FLEXIBLE.value,
    PlasticCategory.MULTILAYER.value,
)


class ReconciliationService:
    """
    Deterministic EPR reconciliation engine.

    Compares GreenPack's declared plastic quantities against ERP procurement
    data and produces a fully typed, auditable ReconciliationResult.

    Zero LLM involvement. All math is pure Python floating-point arithmetic
    rounded to 4 decimal places for stable audit-trail storage.

    Args:
        repository:  Injected DeclarationRepository for declaration lookup.
        erp_service: Injected ERPService for procurement snapshot loading.
        threshold_pct: Override the default mismatch threshold. If None,
                       reads from application settings.
    """

    def __init__(
        self,
        repository: DeclarationRepository,
        erp_service: ERPService,
        threshold_pct: Optional[float] = None,
    ) -> None:
        self._repo = repository
        self._erp = erp_service
        settings = get_settings()
        self._threshold_pct = (
            threshold_pct
            if threshold_pct is not None
            else settings.reconciliation_threshold_pct
        )

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    async def reconcile(
        self,
        producer_id: str,
        month: str,
    ) -> ReconciliationResult:
        """
        Execute the full deterministic reconciliation for a producer+month.

        Workflow:
          1. Fetch declaration from DB → fail fast with 404 if missing.
          2. Load ERP procurement snapshot from CSV.
          3. Compute per-category mismatch analysis.
          4. Classify severity for each category.
          5. Aggregate totals and determine overall status.
          6. Persist audit log to the database.
          7. Return typed ReconciliationResult.

        Args:
            producer_id: The registered producer identifier.
            month:       The reporting period in YYYY-MM format.

        Returns:
            A fully populated ``ReconciliationResult`` — the source of truth
            for this reconciliation run.

        Raises:
            DeclarationNotFoundError: If no declaration exists for this
                                      producer+month.
            ERPFeedNotFoundError:     If the ERP feed CSV cannot be read.
            InfrastructureError:      If a database or filesystem error occurs.
        """
        start_ms = time.monotonic()
        normalised_id = producer_id.strip().upper()
        normalised_month = month.strip()

        logger.info(
            "Starting reconciliation",
            extra={
                "producer_id": normalised_id,
                "month": normalised_month,
                "threshold_pct": self._threshold_pct,
            },
        )

        # ── Step 1: Fetch Declaration ─────────────────────────────────
        declaration = await self._repo.get_by_producer_month(
            normalised_id, normalised_month
        )
        if not declaration:
            raise DeclarationNotFoundError(
                producer_id=normalised_id, month=normalised_month
            )

        logger.info(
            "Declaration found",
            extra={
                "record_id": declaration.record_id,
                "total_declared_kg": declaration.total_declared_kg,
            },
        )

        # ── Step 2: Load ERP Snapshot ─────────────────────────────────
        # Synchronous I/O — the CSV read is fast enough for this scale.
        erp_snapshot = self._erp.get_procurement_snapshot(
            producer_id=normalised_id,
            month=normalised_month,
        )

        return await self.compute_reconciliation(
            declaration=declaration,
            erp_snapshot=erp_snapshot,
            start_ms=start_ms
        )

    async def compute_reconciliation(
        self,
        declaration,
        erp_snapshot,
        start_ms: float,
    ) -> ReconciliationResult:
        """
        Execute deterministic reconciliation math and persist audit log.
        Used by the LangGraph orchestration nodes.
        """
        normalised_id = declaration.producer_id.upper()
        normalised_month = declaration.month

        # ── Step 3: Build declared quantities dict ────────────────────
        declared: dict[str, float] = {
            cat.category: cat.declared_quantity_kg
            for cat in declaration.categories
        }
        for category in _ALL_CATEGORIES:
            declared.setdefault(category, 0.0)

        procured: dict[str, float] = erp_snapshot.to_category_dict()

        # ── Step 4: Per-category reconciliation math ──────────────────
        category_results: list[CategoryReconciliation] = []

        for category in _ALL_CATEGORIES:
            result = self._reconcile_category(
                category=category,
                declared_kg=declared.get(category, 0.0),
                procured_kg=procured.get(category, 0.0),
                threshold_pct=self._threshold_pct,
            )
            category_results.append(result)

        # ── Step 5: Aggregate Analysis ────────────────────────────────
        reconciliation_result_partial = self._build_reconciliation_result(
            producer_id=normalised_id,
            month=normalised_month,
            categories=category_results,
            erp_snapshot=erp_snapshot,
            threshold_pct=self._threshold_pct,
            start_ms=start_ms,
        )

        # ── Step 6: Persist Audit Log ─────────────────────────────────
        log_entry = await self._repo.create_reconciliation_log(
            declaration_id=declaration.record_id,
            erp_quantities=procured,
            has_mismatch=reconciliation_result_partial["has_mismatch"],
            mismatch_categories=list(reconciliation_result_partial["flagged_categories"]),
            threshold_pct=self._threshold_pct,
            narrative_summary=None,
            llm_model_used=None,
            execution_ms=reconciliation_result_partial["execution_ms"],
        )

        reconciliation_result = ReconciliationResult(
            record_id=declaration.record_id,
            log_id=log_entry.id,
            **reconciliation_result_partial,
        )

        logger.info(
            "Reconciliation complete",
            extra={
                "producer_id": normalised_id,
                "month": normalised_month,
                "overall_status": reconciliation_result.overall_status.value,
                "has_mismatch": reconciliation_result.has_mismatch,
                "flagged_categories": list(reconciliation_result.flagged_categories),
                "total_declared_kg": reconciliation_result.total_declared_kg,
                "total_procured_kg": reconciliation_result.total_procured_kg,
                "overall_deviation_pct": reconciliation_result.overall_deviation_pct,
                "execution_ms": reconciliation_result.execution_ms,
            },
        )

        return reconciliation_result

    # ─────────────────────────────────────────────
    # Private: Per-Category Math
    # ─────────────────────────────────────────────

    def _reconcile_category(
        self,
        category: str,
        declared_kg: float,
        procured_kg: float,
        threshold_pct: float,
    ) -> CategoryReconciliation:
        """
        Compute the full reconciliation result for a single plastic category.

        Math (all deterministic, zero LLM):
          variance_kg   = declared_kg − procured_kg
          deviation_pct = abs(variance_kg) / declared_kg × 100
                          (0.0 when declared_kg == 0 — no EPR obligation)
          is_flagged    = deviation_pct > threshold_pct
                          (special case: procured == 0 while declared > 0
                           → always flagged regardless of threshold)

        Args:
            category:      Plastic category name.
            declared_kg:   What GreenPack declared to the EPR authority.
            procured_kg:   What the ERP system recorded as procured.
            threshold_pct: Mismatch flag threshold percentage.

        Returns:
            A frozen ``CategoryReconciliation`` instance.
        """
        variance_kg = round(declared_kg - procured_kg, 4)

        # ── Deviation Percentage ──────────────────────────────────────
        if declared_kg == 0.0:
            # No EPR obligation for this category — deviation is meaningless
            deviation_pct = 0.0
        else:
            deviation_pct = round((abs(variance_kg) / declared_kg) * 100, 4)

        # ── Mismatch Flag ─────────────────────────────────────────────
        # Special case: if producer declared quantity but ERP shows zero,
        # it must always be flagged — regardless of threshold value.
        if declared_kg > 0.0 and procured_kg == 0.0:
            is_flagged = True
        else:
            is_flagged = deviation_pct > threshold_pct

        # ── Severity Classification ───────────────────────────────────
        severity = self._classify_severity(
            declared_kg=declared_kg,
            procured_kg=procured_kg,
            deviation_pct=deviation_pct,
            threshold_pct=threshold_pct,
        )

        logger.debug(
            "Category reconciled",
            extra={
                "category": category,
                "declared_kg": declared_kg,
                "procured_kg": procured_kg,
                "variance_kg": variance_kg,
                "deviation_pct": deviation_pct,
                "is_flagged": is_flagged,
                "severity": severity.value,
            },
        )

        return CategoryReconciliation(
            category=category,
            declared_kg=declared_kg,
            procured_kg=procured_kg,
            variance_kg=variance_kg,
            deviation_pct=deviation_pct,
            is_flagged=is_flagged,
            severity=severity,
            threshold_pct=threshold_pct,
        )

    @staticmethod
    def _classify_severity(
        declared_kg: float,
        procured_kg: float,
        deviation_pct: float,
        threshold_pct: float,
    ) -> MismatchSeverity:
        """
        Classify the severity of a category's mismatch deterministically.

        Severity tiers:
          NONE:     no mismatch (deviation <= threshold OR declared == 0)
          MISSING:  declared > 0, procured == 0 (ERP has no record)
          LOW:      threshold < deviation <= 2 × threshold
          MODERATE: 2× threshold < deviation <= 5 × threshold
          HIGH:     deviation > 5 × threshold

        Pure function — no side effects, no I/O.
        """
        if declared_kg == 0.0:
            return MismatchSeverity.NONE

        if procured_kg == 0.0 and declared_kg > 0.0:
            return MismatchSeverity.MISSING

        if deviation_pct <= threshold_pct:
            return MismatchSeverity.NONE
        elif deviation_pct <= threshold_pct * 2:
            return MismatchSeverity.LOW
        elif deviation_pct <= threshold_pct * 5:
            return MismatchSeverity.MODERATE
        else:
            return MismatchSeverity.HIGH

    # ─────────────────────────────────────────────
    # Private: Aggregate Builder
    # ─────────────────────────────────────────────

    @staticmethod
    def _build_reconciliation_result(
        producer_id: str,
        month: str,
        categories: list[CategoryReconciliation],
        erp_snapshot: ERPProcurementSnapshot,
        threshold_pct: float,
        start_ms: float,
    ) -> dict:
        """
        Aggregate all category results into a partial ReconciliationResult dict.

        Pure function — deterministic aggregation, zero I/O.

        Args:
            producer_id:   Registered producer identifier.
            month:         Reporting period.
            categories:    All per-category reconciliation results.
            erp_snapshot:  The ERP snapshot used (for record_count and totals).
            threshold_pct: Threshold used in this run.
            start_ms:      monotonic start time (for execution_ms calculation).

        Returns:
            A dictionary containing partial ``ReconciliationResult`` fields.
        """
        flagged = tuple(c.category for c in categories if c.is_flagged)
        has_mismatch = len(flagged) > 0

        total_declared = round(sum(c.declared_kg for c in categories), 4)
        total_procured = round(sum(c.procured_kg for c in categories), 4)
        total_variance = round(total_declared - total_procured, 4)

        if total_declared == 0.0:
            overall_deviation = 0.0
        else:
            overall_deviation = round(
                (abs(total_variance) / total_declared) * 100, 4
            )

        # Determine overall status
        if erp_snapshot.record_count == 0:
            status = ReconciliationStatus.NO_ERP_DATA
        elif has_mismatch:
            status = ReconciliationStatus.MISMATCHED
        else:
            status = ReconciliationStatus.CLEAN

        execution_ms = int((time.monotonic() - start_ms) * 1000)

        return {
            "producer_id": producer_id,
            "month": month,
            "categories": tuple(sorted(categories, key=lambda c: c.category)),
            "overall_status": status,
            "total_declared_kg": total_declared,
            "total_procured_kg": total_procured,
            "total_variance_kg": total_variance,
            "overall_deviation_pct": overall_deviation,
            "flagged_categories": flagged,
            "has_mismatch": has_mismatch,
            "threshold_pct": threshold_pct,
            "erp_record_count": erp_snapshot.record_count,
            "reconciled_at": datetime.now(timezone.utc),
            "execution_ms": execution_ms,
        }
