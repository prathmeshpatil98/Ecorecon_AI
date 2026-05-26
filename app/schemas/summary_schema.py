"""
app/schemas/summary_schema.py
==============================
Pydantic v2 schemas for the reconciliation engine and GET /summary response.

Schema Hierarchy:
  ┌──────────────────────────────────────────────────────────────────────┐
  │  CategoryReconciliation      (one per plastic category)              │
  │   ↓ aggregated into                                                  │
  │  ReconciliationResult        (full deterministic analysis output)    │
  │   ↓ consumed by LLM layer, then wrapped into                         │
  │  SummaryResponse             (final GET /summary API response)       │
  └──────────────────────────────────────────────────────────────────────┘

Design Decisions:
  - CategoryReconciliation is frozen and immutable — each category's math
    result is computed once and never re-evaluated.
  - ReconciliationResult carries the complete audit package: all category
    results, overall mismatch status, threshold used, and timing metadata.
  - SummaryResponse separates the deterministic result (reconciliation)
    from the LLM narrative — making it structurally impossible to confuse
    the two sources of information.
  - MismatchSeverity is a deterministic enum classification of how far
    the declared vs. procured deviation falls from the threshold.
  - All float fields are rounded to 4 decimal places to avoid floating-
    point representation noise in API responses and audit logs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class MismatchSeverity(str, Enum):
    """
    Deterministic severity classification for a category-level mismatch.

    Computed purely from the deviation percentage — no LLM involvement.

    Severity tiers (relative to declared quantity):
      NONE:     deviation <= threshold (no mismatch)
      LOW:      threshold < deviation <= 2x threshold
      MODERATE: 2x threshold < deviation <= 5x threshold
      HIGH:     deviation > 5x threshold
      MISSING:  ERP has zero procurement for a declared category
    """
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    MISSING = "missing"


class ReconciliationStatus(str, Enum):
    """Overall status of the reconciliation run."""
    CLEAN = "clean"            # All categories within threshold
    MISMATCHED = "mismatched"  # One or more categories exceed threshold
    NO_ERP_DATA = "no_erp_data"  # ERP snapshot had zero records


# ─────────────────────────────────────────────
# Schema 1: CategoryReconciliation
# ─────────────────────────────────────────────

class CategoryReconciliation(BaseModel):
    """
    Deterministic reconciliation result for a single plastic category.

    Contains:
      - declared_kg:       what GreenPack declared to the EPR authority
      - procured_kg:       what the ERP system shows as procured
      - variance_kg:       absolute difference (declared − procured)
      - deviation_pct:     percentage deviation relative to declared quantity
      - is_flagged:        True if deviation_pct > threshold
      - severity:          Deterministic tier classification
      - threshold_pct:     The threshold used in this comparison

    Immutable after construction. Every field is computed before storage —
    no lazy evaluation, no LLM involvement.
    """

    model_config = ConfigDict(frozen=True)

    category: str = Field(
        description="Plastic category name (rigid_plastic / flexible_plastic / multilayer_plastic).",
    )
    declared_kg: float = Field(
        description="Declared quantity for this category in kilograms.",
    )
    procured_kg: float = Field(
        description="ERP-reported procured quantity for this category in kilograms.",
    )
    variance_kg: float = Field(
        description=(
            "Absolute difference: declared_kg − procured_kg. "
            "Positive = over-declared. Negative = under-declared."
        ),
    )
    deviation_pct: float = Field(
        description=(
            "Percentage deviation of declared vs. procured relative to declared quantity. "
            "Formula: abs(declared − procured) / declared × 100. "
            "0.0 when declared_kg == 0 (no EPR obligation for this category)."
        ),
    )
    is_flagged: bool = Field(
        description="True if deviation_pct exceeds the configured mismatch threshold.",
    )
    severity: MismatchSeverity = Field(
        description="Deterministic severity tier for this category's deviation.",
    )
    threshold_pct: float = Field(
        description="The mismatch threshold percentage used in this calculation.",
    )

    @property
    def is_over_declared(self) -> bool:
        """True if declared_kg > procured_kg (over-declaration risk)."""
        return self.variance_kg > 0

    @property
    def is_under_declared(self) -> bool:
        """True if declared_kg < procured_kg (under-declaration risk)."""
        return self.variance_kg < 0


# ─────────────────────────────────────────────
# Schema 2: ReconciliationResult
# ─────────────────────────────────────────────

class ReconciliationResult(BaseModel):
    """
    Complete deterministic reconciliation output for one producer+month.

    This is the authoritative output of ReconciliationService.reconcile().
    It is:
      - Passed to the LLM layer as the sole input for narrative generation.
      - Stored verbatim in the ReconciliationLog audit table.
      - Returned as the structured part of the GET /summary response.

    The LLM NEVER modifies this object — it only reads it to generate text.

    Fields:
      producer_id:        Identifies whose declaration was reconciled.
      month:              The reporting period.
      categories:         Per-category reconciliation results (one per type).
      overall_status:     Clean / Mismatched / No ERP Data.
      total_declared_kg:  Aggregate declared quantity across all categories.
      total_procured_kg:  Aggregate ERP procurement across all categories.
      flagged_categories: Names of categories that exceeded the threshold.
      has_mismatch:       Convenience boolean (True if any category is flagged).
      threshold_pct:      Threshold used in this run (from config, not hardcoded).
      reconciled_at:      UTC timestamp of computation.
      execution_ms:       Wall-clock time for the reconciliation in milliseconds.
    """

    model_config = ConfigDict(frozen=True)

    # ── Identity ──────────────────────────────
    producer_id: str = Field(description="Registered producer identifier.")
    month: str = Field(description="Reporting month in YYYY-MM format.")
    record_id: str = Field(description="UUID of the originating PlasticDeclaration.")
    log_id: str = Field(description="UUID of the ReconciliationLog audit entry.")

    # ── Category Results ──────────────────────
    categories: tuple[CategoryReconciliation, ...] = Field(
        description="Per-category reconciliation results, ordered alphabetically.",
    )

    # ── Aggregate Analysis ────────────────────
    overall_status: ReconciliationStatus = Field(
        description="Deterministic overall compliance status for this reporting period.",
    )
    total_declared_kg: float = Field(
        description="Sum of all declared category quantities (kg).",
    )
    total_procured_kg: float = Field(
        description="Sum of all ERP procured category quantities (kg).",
    )
    total_variance_kg: float = Field(
        description="total_declared_kg − total_procured_kg.",
    )
    overall_deviation_pct: float = Field(
        description=(
            "Overall percentage deviation: abs(total_declared − total_procured) "
            "/ total_declared × 100. 0.0 if total_declared == 0."
        ),
    )
    flagged_categories: tuple[str, ...] = Field(
        description="Tuple of category names that exceeded the mismatch threshold.",
    )
    has_mismatch: bool = Field(
        description="True if one or more categories are flagged.",
    )

    # ── Audit Metadata ────────────────────────
    threshold_pct: float = Field(
        description="Mismatch threshold percentage used in this run.",
    )
    erp_record_count: int = Field(
        description="Number of ERP records that contributed to this reconciliation.",
    )
    reconciled_at: datetime = Field(
        description="UTC timestamp when reconciliation was computed.",
    )
    execution_ms: int = Field(
        description="Wall-clock execution time of the reconciliation in milliseconds.",
    )

    # ── Convenience Accessors ─────────────────

    def get_category(self, name: str) -> Optional[CategoryReconciliation]:
        """Return the reconciliation result for a specific category by name."""
        for cat in self.categories:
            if cat.category == name:
                return cat
        return None

    @property
    def flagged_count(self) -> int:
        """Number of categories that exceeded the mismatch threshold."""
        return len(self.flagged_categories)

    @property
    def highest_severity(self) -> MismatchSeverity:
        """
        Return the most severe mismatch severity across all categories.

        Used by the LLM prompt to calibrate narrative urgency.
        """
        severity_order = [
            MismatchSeverity.NONE,
            MismatchSeverity.LOW,
            MismatchSeverity.MODERATE,
            MismatchSeverity.HIGH,
            MismatchSeverity.MISSING,
        ]
        current_max = MismatchSeverity.NONE
        for cat in self.categories:
            if severity_order.index(cat.severity) > severity_order.index(current_max):
                current_max = cat.severity
        return current_max

    def to_llm_context(self) -> dict:
        """
        Serialise the reconciliation result into a structured context dict
        for the LLM narrative prompt.

        The LLM reads this dict to understand the reconciliation outcome.
        It NEVER modifies it. This enforces the deterministic-first boundary.
        """
        return {
            "producer_id": self.producer_id,
            "month": self.month,
            "overall_status": self.overall_status.value,
            "has_mismatch": self.has_mismatch,
            "flagged_categories": list(self.flagged_categories),
            "highest_severity": self.highest_severity.value,
            "total_declared_kg": self.total_declared_kg,
            "total_procured_kg": self.total_procured_kg,
            "total_variance_kg": self.total_variance_kg,
            "overall_deviation_pct": self.overall_deviation_pct,
            "threshold_pct": self.threshold_pct,
            "categories": [
                {
                    "category": c.category,
                    "declared_kg": c.declared_kg,
                    "procured_kg": c.procured_kg,
                    "variance_kg": c.variance_kg,
                    "deviation_pct": c.deviation_pct,
                    "is_flagged": c.is_flagged,
                    "severity": c.severity.value,
                    "direction": "over_declared" if c.is_over_declared else
                                 "under_declared" if c.is_under_declared else "exact",
                }
                for c in self.categories
            ],
        }


# ─────────────────────────────────────────────
# Schema 3: SummaryResponse — GET /summary API output
# ─────────────────────────────────────────────

class SummaryResponse(BaseModel):
    """
    API response body for GET /summary/{producer_id}/{month}.

    Structurally separates the deterministic reconciliation result from
    the LLM-generated narrative — making provenance transparent to callers.

    The ``reconciliation`` field is always populated from pure Python math.
    The ``narrative`` field is populated by the Groq LLM based on the
    reconciliation result — it is informational only and carries no
    compliance authority.

    Fields:
      record_id:       UUID of the originating PlasticDeclaration.
      reconciliation:  The full deterministic analysis (source of truth).
      narrative:       LLM-generated plain-English summary (augmentation only).
      log_id:          UUID of the ReconciliationLog audit record.
      generated_at:    UTC timestamp of the full response generation.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str = Field(
        description="UUID of the PlasticDeclaration this summary is based on.",
    )
    log_id: str = Field(
        description="UUID of the ReconciliationLog audit entry created for this run.",
    )
    reconciliation: ReconciliationResult = Field(
        description=(
            "**Deterministic reconciliation analysis.** "
            "This is the authoritative compliance data. "
            "Computed by pure Python — no LLM involvement."
        ),
    )
    narrative: Optional[str] = Field(
        default=None,
        description=(
            "**AI-generated narrative summary.** "
            "Generated by the Groq LLM from the reconciliation result above. "
            "Informational only — does not carry compliance authority."
        ),
    )
    generated_at: datetime = Field(
        description="UTC timestamp when this full summary response was assembled.",
    )
