"""
app/schemas/erp_schema.py
==========================
Pydantic v2 schemas for ERP procurement feed data.

Design Decisions:
  - ERPRecord is the atomic unit: one row in the CSV = one typed record.
  - ERPFeedResult is the aggregated output of a full feed parse:
    all records, filtered records, and parse diagnostics.
  - ERPProcurementSnapshot is the category-keyed dict used by the
    reconciliation engine — the authoritative ERP view for one
    producer+month pair.
  - All schemas use strict typing — no raw dicts passed between layers.
  - Pydantic validators catch data quality issues at parse time,
    preventing corrupt records from silently reaching reconciliation math.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.database.models import PlasticCategory

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

VALID_CATEGORIES: frozenset[str] = frozenset(c.value for c in PlasticCategory)

REQUIRED_CSV_COLUMNS: frozenset[str] = frozenset(
    {"producer_id", "month", "category", "procured_kg"}
)


# ─────────────────────────────────────────────
# Schema 1: ERPRecord — one CSV row
# ─────────────────────────────────────────────

class ERPRecord(BaseModel):
    """
    A single validated ERP procurement record.

    Represents one row from the ERP CSV feed after type coercion and
    field-level validation. Invalid rows are never silently swallowed —
    they surface as parse errors in ``ERPFeedResult.parse_errors``.

    Immutable after construction (``frozen=True``) — records are
    never mutated once parsed from the feed.
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    producer_id: str = Field(
        description="Registered producer identifier from the ERP system.",
        examples=["GREENPACK-001"],
    )
    month: str = Field(
        description="Procurement reporting month in YYYY-MM format.",
        examples=["2026-04"],
    )
    category: str = Field(
        description="Plastic category (rigid_plastic / flexible_plastic / multilayer_plastic).",
        examples=["rigid_plastic"],
    )
    procured_kg: float = Field(
        ge=0.0,
        description="Quantity of this plastic category procured, in kilograms.",
        examples=[11800.0],
    )

    @field_validator("producer_id")
    @classmethod
    def normalise_producer_id(cls, v: str) -> str:
        """Strip whitespace and normalise to uppercase."""
        return v.strip().upper()

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """Enforce YYYY-MM format. Reject malformed month strings immediately."""
        import re
        stripped = v.strip()
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", stripped):
            raise ValueError(
                f"ERP record has invalid month format: '{v}'. "
                "Expected YYYY-MM (e.g. 2026-04)."
            )
        return stripped

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Reject unknown plastic categories — ERP feed must align with EPR schema."""
        normalised = v.strip().lower()
        if normalised not in VALID_CATEGORIES:
            raise ValueError(
                f"Unknown plastic category in ERP feed: '{v}'. "
                f"Valid categories: {sorted(VALID_CATEGORIES)}."
            )
        return normalised


# ─────────────────────────────────────────────
# Schema 2: ERPParseError — one failed row
# ─────────────────────────────────────────────

class ERPParseError(BaseModel):
    """
    Structured parse failure for a single ERP CSV row.

    Captured during feed loading so that partial failures do not abort
    the entire ingestion — valid rows still proceed to reconciliation.
    """

    model_config = ConfigDict(frozen=True)

    row_index: int = Field(description="0-based row index in the CSV (excluding header).")
    raw_data: dict = Field(description="The raw unparsed row dict as read from CSV.")
    error_message: str = Field(description="Validation error that caused rejection.")


# ─────────────────────────────────────────────
# Schema 3: ERPFeedResult — full parse output
# ─────────────────────────────────────────────

class ERPFeedResult(BaseModel):
    """
    Aggregated result of parsing the full ERP CSV feed.

    Returned by ``ERPService.load_feed()``. Contains:
      - All successfully validated records.
      - All parse failures (row index + error message).
      - Feed-level diagnostics: total rows, success count, error count.

    The caller (ReconciliationService) uses ``records`` for computation
    and may log or alert on ``parse_errors`` for data quality monitoring.
    """

    model_config = ConfigDict(frozen=True)

    records: tuple[ERPRecord, ...] = Field(
        default_factory=tuple,
        description="All successfully parsed ERP records.",
    )
    parse_errors: tuple[ERPParseError, ...] = Field(
        default_factory=tuple,
        description="Rows that failed validation during parsing.",
    )
    total_rows_read: int = Field(
        description="Total data rows read from the CSV (excluding header).",
    )
    feed_path: str = Field(
        description="Absolute or relative path of the CSV file that was parsed.",
    )
    parsed_at: datetime = Field(
        description="UTC timestamp when the feed was parsed.",
    )

    @property
    def success_count(self) -> int:
        return len(self.records)

    @property
    def error_count(self) -> int:
        return len(self.parse_errors)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def success_rate_pct(self) -> float:
        """Parse success rate as a percentage (0–100)."""
        if self.total_rows_read == 0:
            return 100.0
        return round((self.success_count / self.total_rows_read) * 100, 2)


# ─────────────────────────────────────────────
# Schema 4: ERPProcurementSnapshot — reconciliation input
# ─────────────────────────────────────────────

class ERPProcurementSnapshot(BaseModel):
    """
    Aggregated ERP procurement quantities for a single producer+month.

    This is the authoritative ERP data view consumed by the reconciliation
    engine. Created by ``ERPService.get_procurement_snapshot()``.

    Category quantities are individually typed (not a raw dict) so that
    the reconciliation service can access them without key lookups.

    Missing categories default to 0.0 — if the ERP has no record for a
    category, the procurement is treated as zero (which will trigger a
    mismatch if the declaration is non-zero).
    """

    model_config = ConfigDict(frozen=True)

    producer_id: str = Field(description="Registered producer identifier.")
    month: str = Field(description="Reporting month in YYYY-MM format.")

    rigid_plastic_kg: float = Field(
        default=0.0,
        ge=0.0,
        description="Total rigid plastic procured per ERP data (kg).",
    )
    flexible_plastic_kg: float = Field(
        default=0.0,
        ge=0.0,
        description="Total flexible plastic procured per ERP data (kg).",
    )
    multilayer_plastic_kg: float = Field(
        default=0.0,
        ge=0.0,
        description="Total multilayer plastic procured per ERP data (kg).",
    )
    record_count: int = Field(
        default=0,
        description="Number of ERP records aggregated into this snapshot.",
    )

    @property
    def total_procured_kg(self) -> float:
        """Sum of all category procurements."""
        return (
            self.rigid_plastic_kg
            + self.flexible_plastic_kg
            + self.multilayer_plastic_kg
        )

    def to_category_dict(self) -> dict[str, float]:
        """
        Return procurement quantities keyed by category name.

        Used by the reconciliation engine for category-by-category math.
        """
        return {
            PlasticCategory.RIGID.value: self.rigid_plastic_kg,
            PlasticCategory.FLEXIBLE.value: self.flexible_plastic_kg,
            PlasticCategory.MULTILAYER.value: self.multilayer_plastic_kg,
        }

    @classmethod
    def empty(cls, producer_id: str, month: str) -> "ERPProcurementSnapshot":
        """
        Return a zero-quantity snapshot for a producer+month with no ERP data.

        Used as a safe fallback when the ERP feed has no records for the
        requested producer+month — all categories will flag as mismatched.
        """
        return cls(
            producer_id=producer_id,
            month=month,
            rigid_plastic_kg=0.0,
            flexible_plastic_kg=0.0,
            multilayer_plastic_kg=0.0,
            record_count=0,
        )
