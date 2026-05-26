"""
app/services/erp_service.py
=============================
Deterministic ERP procurement feed ingestion service.

Architecture Position:
  ReconciliationService → ERPService → pandas CSV loader → ERPFeedResult

Responsibilities:
  1. Load and parse the ERP procurement CSV from the configured path.
  2. Validate every row via Pydantic — corrupt rows are captured, not raised.
  3. Filter records by producer_id and month for the reconciliation engine.
  4. Aggregate filtered records into a typed ERPProcurementSnapshot.
  5. Emit structured diagnostics (parse rate, error count, row counts).

Design Decisions:
  - Uses pandas for CSV loading — handles encoding edge cases, large files,
    and malformed rows far more reliably than the stdlib csv module.
  - Row-level validation is Pydantic-driven — type errors, invalid months,
    and unknown categories are captured as ERPParseError instances so that
    partial failures do not abort the reconciliation of valid data.
  - The service is stateless — it reads the feed path from settings at
    runtime. The path can be overridden per-call for testing.
  - Zero LLM calls. Zero database writes. Pure deterministic I/O and math.
  - ``get_procurement_snapshot()`` is the primary public API surface.
    The caller (ReconciliationService) never needs to touch raw records.

STRICT RULES ENFORCED:
  - No LLM usage.
  - No hallucinated procurement logic.
  - No business rule decisions — this service only reads and parses.
  - Reconciliation math belongs to ReconciliationService, not here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.exceptions import ERPFeedNotFoundError, InfrastructureError
from app.core.logger import get_logger
from app.database.models import PlasticCategory
from app.schemas.erp_schema import (
    ERPFeedResult,
    ERPParseError,
    ERPProcurementSnapshot,
    ERPRecord,
    REQUIRED_CSV_COLUMNS,
)

logger = get_logger(__name__)

# Category name → snapshot field name mapping (deterministic, not config-driven)
_CATEGORY_TO_FIELD: dict[str, str] = {
    PlasticCategory.RIGID.value: "rigid_plastic_kg",
    PlasticCategory.FLEXIBLE.value: "flexible_plastic_kg",
    PlasticCategory.MULTILAYER.value: "multilayer_plastic_kg",
}


class ERPService:
    """
    Deterministic ERP procurement feed ingestion service.

    Loads, validates, filters, and aggregates the ERP CSV procurement feed.
    Used exclusively by the ReconciliationService — never called directly
    from routes.

    Args:
        feed_path: Path to the ERP CSV file. Defaults to the value from
                   application settings (``erp_feed_path``).
    """

    def __init__(self, feed_path: Optional[str | Path] = None) -> None:
        settings = get_settings()
        self._feed_path = Path(feed_path or settings.erp_feed_path).resolve()

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    def load_feed(self) -> ERPFeedResult:
        """
        Load and validate the full ERP procurement CSV feed.

        Reads the CSV from the configured path, validates every row via
        Pydantic, and returns an ``ERPFeedResult`` containing:
          - All valid ``ERPRecord`` instances.
          - All ``ERPParseError`` instances for corrupt/invalid rows.
          - Parse diagnostics (total rows, success rate, path, timestamp).

        Returns:
            ``ERPFeedResult`` — never raises on row-level errors.

        Raises:
            ERPFeedNotFoundError:  If the CSV file does not exist.
            InfrastructureError:   If the file cannot be read (permissions,
                                   encoding failures, empty file).
        """
        self._assert_feed_exists()

        logger.info(
            "Loading ERP feed",
            extra={"path": str(self._feed_path)},
        )

        raw_df = self._read_csv()
        self._assert_required_columns(raw_df)

        records: list[ERPRecord] = []
        errors: list[ERPParseError] = []

        for idx, row in enumerate(raw_df.to_dict(orient="records")):
            try:
                record = ERPRecord.model_validate(row)
                records.append(record)
            except (ValidationError, ValueError, TypeError) as exc:
                errors.append(
                    ERPParseError(
                        row_index=idx,
                        raw_data=row,
                        error_message=str(exc),
                    )
                )

        result = ERPFeedResult(
            records=tuple(records),
            parse_errors=tuple(errors),
            total_rows_read=len(raw_df),
            feed_path=str(self._feed_path),
            parsed_at=datetime.now(timezone.utc),
        )

        logger.info(
            "ERP feed loaded",
            extra={
                "total_rows": result.total_rows_read,
                "valid_records": result.success_count,
                "parse_errors": result.error_count,
                "success_rate_pct": result.success_rate_pct,
                "path": str(self._feed_path),
            },
        )

        if result.has_errors:
            logger.warning(
                "ERP feed parse errors detected — check feed data quality",
                extra={
                    "error_count": result.error_count,
                    "first_error": result.parse_errors[0].error_message
                    if result.parse_errors
                    else None,
                },
            )

        return result

    def get_procurement_snapshot(
        self,
        producer_id: str,
        month: str,
        feed_result: Optional[ERPFeedResult] = None,
    ) -> ERPProcurementSnapshot:
        """
        Return the aggregated ERP procurement snapshot for a producer+month.

        This is the primary method consumed by ReconciliationService.
        It:
          1. Loads the feed (or uses a pre-loaded ``ERPFeedResult``).
          2. Filters records by ``producer_id`` and ``month``.
          3. Aggregates per-category quantities (sum across matching rows).
          4. Returns a typed ``ERPProcurementSnapshot``.

        If no matching records exist, returns an empty snapshot with all
        quantities at 0.0 — this safely triggers mismatch detection.

        Args:
            producer_id:  The producer to filter by (e.g. "GREENPACK-001").
            month:        The reporting month to filter by (e.g. "2026-04").
            feed_result:  Optional pre-loaded feed result. If provided, the
                          CSV is not re-read (useful for batch processing).

        Returns:
            A typed ``ERPProcurementSnapshot`` for the given producer+month.

        Raises:
            ERPFeedNotFoundError:  If the feed file does not exist.
            InfrastructureError:   If the feed cannot be read.
        """
        normalised_producer = producer_id.strip().upper()
        normalised_month = month.strip()

        feed = feed_result or self.load_feed()

        # Filter records deterministically — pure Python, no LLM
        matching: list[ERPRecord] = [
            r for r in feed.records
            if r.producer_id == normalised_producer and r.month == normalised_month
        ]

        if not matching:
            logger.warning(
                "No ERP records found for producer+month — returning empty snapshot",
                extra={"producer_id": normalised_producer, "month": normalised_month},
            )
            return ERPProcurementSnapshot.empty(normalised_producer, normalised_month)

        # Aggregate by category — sum across multiple rows for same category
        # (handles ERP systems that emit multiple rows per category per month)
        category_totals: dict[str, float] = {
            PlasticCategory.RIGID.value: 0.0,
            PlasticCategory.FLEXIBLE.value: 0.0,
            PlasticCategory.MULTILAYER.value: 0.0,
        }

        for record in matching:
            if record.category in category_totals:
                category_totals[record.category] += record.procured_kg

        snapshot = ERPProcurementSnapshot(
            producer_id=normalised_producer,
            month=normalised_month,
            rigid_plastic_kg=category_totals[PlasticCategory.RIGID.value],
            flexible_plastic_kg=category_totals[PlasticCategory.FLEXIBLE.value],
            multilayer_plastic_kg=category_totals[PlasticCategory.MULTILAYER.value],
            record_count=len(matching),
        )

        logger.info(
            "ERP procurement snapshot built",
            extra={
                "producer_id": normalised_producer,
                "month": normalised_month,
                "record_count": snapshot.record_count,
                "total_procured_kg": snapshot.total_procured_kg,
                "rigid_kg": snapshot.rigid_plastic_kg,
                "flexible_kg": snapshot.flexible_plastic_kg,
                "multilayer_kg": snapshot.multilayer_plastic_kg,
            },
        )

        return snapshot

    def list_available_months(
        self,
        producer_id: str,
        feed_result: Optional[ERPFeedResult] = None,
    ) -> list[str]:
        """
        Return sorted list of months that have ERP data for a given producer.

        Utility method for observability and reporting — not used in the
        reconciliation path.

        Returns:
            Sorted list of YYYY-MM strings (oldest first).
        """
        normalised = producer_id.strip().upper()
        feed = feed_result or self.load_feed()

        months = sorted(
            {r.month for r in feed.records if r.producer_id == normalised}
        )
        return months

    def list_available_producers(
        self,
        feed_result: Optional[ERPFeedResult] = None,
    ) -> list[str]:
        """
        Return sorted list of all producer IDs present in the feed.

        Utility method — not used in the reconciliation path.

        Returns:
            Sorted list of producer ID strings.
        """
        feed = feed_result or self.load_feed()
        return sorted({r.producer_id for r in feed.records})

    # ─────────────────────────────────────────────
    # Private Helpers
    # ─────────────────────────────────────────────

    def _assert_feed_exists(self) -> None:
        """
        Raise ERPFeedNotFoundError if the configured CSV path does not exist.

        Checked before any pandas I/O to surface a clean, typed error
        rather than a raw FileNotFoundError.
        """
        if not self._feed_path.exists():
            raise ERPFeedNotFoundError(path=str(self._feed_path))

    def _read_csv(self) -> pd.DataFrame:
        """
        Load the ERP CSV into a pandas DataFrame.

        Enforces:
          - UTF-8 encoding (with latin-1 fallback for legacy ERP exports).
          - All columns read as strings initially — Pydantic handles coercion.
          - Empty files raise InfrastructureError.
          - Whitespace stripped from column names.

        Returns:
            A raw pandas DataFrame with string-typed columns.

        Raises:
            InfrastructureError: If the file is unreadable or empty.
        """
        try:
            df = pd.read_csv(
                self._feed_path,
                dtype=str,                 # Read all as strings — Pydantic coerces
                encoding="utf-8",
                on_bad_lines="warn",       # Log bad lines, don't abort
                skip_blank_lines=True,
            )
        except UnicodeDecodeError:
            logger.warning(
                "UTF-8 decode failed for ERP feed — retrying with latin-1",
                extra={"path": str(self._feed_path)},
            )
            try:
                df = pd.read_csv(
                    self._feed_path,
                    dtype=str,
                    encoding="latin-1",
                    on_bad_lines="warn",
                    skip_blank_lines=True,
                )
            except Exception as exc:
                raise InfrastructureError(
                    message=f"Failed to read ERP feed after latin-1 retry: {exc}",
                ) from exc
        except Exception as exc:
            raise InfrastructureError(
                message=f"Failed to read ERP feed: {exc}",
            ) from exc

        if df.empty:
            raise InfrastructureError(
                message=f"ERP feed at '{self._feed_path}' is empty.",
            )

        # Normalise column names — strip whitespace, lowercase
        df.columns = [c.strip().lower() for c in df.columns]

        # Strip whitespace from all string cells
        df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

        return df

    def _assert_required_columns(self, df: pd.DataFrame) -> None:
        """
        Raise InfrastructureError if the CSV is missing required columns.

        Validates the feed schema before processing any rows — fail-fast
        on structural incompatibility.
        """
        present = set(df.columns)
        missing = REQUIRED_CSV_COLUMNS - present
        if missing:
            raise InfrastructureError(
                message=(
                    f"ERP feed is missing required columns: {sorted(missing)}. "
                    f"Present columns: {sorted(present)}."
                ),
            )
