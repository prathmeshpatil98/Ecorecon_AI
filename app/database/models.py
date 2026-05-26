"""
app/database/models.py
=======================
SQLAlchemy ORM models for EcoRecon AI — production enterprise schema.

Schema Design Rationale:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  PlasticDeclaration  (one per producer+month submission)            │
  │   └── DeclarationCategory  (one row per plastic type, normalized)  │
  │   └── ReconciliationLog    (one row per /summary run, audit trail)  │
  └─────────────────────────────────────────────────────────────────────┘

  - PlasticDeclaration is the authoritative immutable record of what
    GreenPack declared for a given month. It is NEVER mutated post-creation.
  - DeclarationCategory normalizes plastic quantities into individual rows
    (rigid / flexible / multilayer), enabling category-level querying,
    reporting, and future extensibility without schema migrations.
  - ReconciliationLog is append-only — every /summary call creates a new
    log entry. This preserves a full, queryable audit trail of every
    reconciliation run and its LLM-generated narrative.
  - All timestamps are timezone-aware UTC — no naive datetimes anywhere.
  - All primary keys are UUID4 strings — globally unique, portable.
  - No JSON blobs. Every field is individually typed and queryable.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


# ─────────────────────────────────────────────
# Domain Enums
# ─────────────────────────────────────────────

class PlasticCategory(str, Enum):
    """
    Canonical set of plastic categories recognized by the EPR framework.

    Using a string enum ensures that category values stored in SQLite are
    human-readable and stable across migrations.
    """
    RIGID = "rigid_plastic"
    FLEXIBLE = "flexible_plastic"
    MULTILAYER = "multilayer_plastic"


class ReconciliationStatus(str, Enum):
    """
    Lifecycle status of a reconciliation run.

    - PENDING:  Scheduled but not yet executed.
    - COMPLETED: Deterministic analysis and LLM narrative both finished.
    - FAILED:   An infrastructure error prevented completion.
    """
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _new_uuid() -> str:
    """Generate a collision-resistant UUID4 string primary key."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Return the current moment as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Model 1: PlasticDeclaration
# ─────────────────────────────────────────────

class PlasticDeclaration(Base):
    """
    Header record for a monthly EPR plastic declaration.

    Represents the submission event: who declared, for which month, when,
    and what the combined total declared weight was. Detailed per-category
    quantities live in the child ``DeclarationCategory`` rows.

    Immutability contract:
        Once created, this record MUST NOT be updated. Any amendment workflow
        must create a new PlasticDeclaration with an incremented ``revision``
        counter (reserved for future scope; currently defaults to 1).

    Indexes:
        - (producer_id, month) UNIQUE — prevents duplicate submissions.
        - producer_id — for producer-scoped queries.
        - month — for month-scoped reporting.
    """

    __tablename__ = "plastic_declarations"
    __table_args__ = (
        UniqueConstraint(
            "producer_id",
            "month",
            name="uq_declaration_producer_month",
        ),
        {"comment": "Monthly EPR plastic declarations submitted by GreenPack producers."},
    )

    # ── Primary Key ────────────────────────────
    record_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
        comment="UUID4 identifier generated at submission time.",
    )

    # ── Business Identifiers ───────────────────
    producer_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Registered GreenPack producer identifier (e.g. GREENPACK-001).",
    )
    month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        index=True,
        comment="Reporting period in YYYY-MM format (e.g. 2026-04).",
    )

    # ── Derived Aggregate ──────────────────────
    total_declared_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Sum of all declared category quantities. Computed deterministically at submission.",
    )

    # ── Versioning / Audit ─────────────────────
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Monotonically increasing version counter. Reserved for amendment workflows.",
    )
    submitted_by: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Identity of the submitter (user ID / service account). Populated by auth layer.",
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="UTC timestamp of initial submission.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="UTC row creation timestamp.",
    )

    # ── Relationships ──────────────────────────
    categories: Mapped[list["DeclarationCategory"]] = relationship(
        "DeclarationCategory",
        back_populates="declaration",
        cascade="all, delete-orphan",
        lazy="selectin",  # Always load categories with the declaration
        order_by="DeclarationCategory.category",
    )
    reconciliation_logs: Mapped[list["ReconciliationLog"]] = relationship(
        "ReconciliationLog",
        back_populates="declaration",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<PlasticDeclaration record_id={self.record_id!r} "
            f"producer={self.producer_id!r} month={self.month!r} "
            f"total_kg={self.total_declared_kg}>"
        )

    def to_audit_dict(self) -> dict:
        """
        Return a serialisable snapshot of this declaration for audit logging.
        Does NOT include relationships — call explicitly when needed.
        """
        return {
            "record_id": self.record_id,
            "producer_id": self.producer_id,
            "month": self.month,
            "total_declared_kg": self.total_declared_kg,
            "revision": self.revision,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


# ─────────────────────────────────────────────
# Model 2: DeclarationCategory
# ─────────────────────────────────────────────

class DeclarationCategory(Base):
    """
    Normalized per-category quantity row for a PlasticDeclaration.

    One row per plastic category per declaration. This normalized design:
      - Allows adding new categories (e.g. EPS, PET) without schema changes.
      - Makes category-level reporting and aggregation SQL-native.
      - Enables direct ERP feed comparison at the category grain.

    Constraints:
        - (declaration_id, category) UNIQUE — one row per category per declaration.
    """

    __tablename__ = "declaration_categories"
    __table_args__ = (
        UniqueConstraint(
            "declaration_id",
            "category",
            name="uq_category_declaration_type",
        ),
        {"comment": "Normalized per-category plastic quantities for each declaration."},
    )

    # ── Primary Key ────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    # ── Foreign Key ────────────────────────────
    declaration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plastic_declarations.record_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent declaration this category row belongs to.",
    )

    # ── Category Data ──────────────────────────
    category: Mapped[str] = mapped_column(
        SAEnum(PlasticCategory, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        comment="Plastic category type (rigid_plastic / flexible_plastic / multilayer_plastic).",
    )
    declared_quantity_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Declared quantity in kilograms. Must be >= 0 (validated before persistence).",
    )

    # ── Audit ──────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    # ── Relationships ──────────────────────────
    declaration: Mapped["PlasticDeclaration"] = relationship(
        "PlasticDeclaration",
        back_populates="categories",
    )

    def __repr__(self) -> str:
        return (
            f"<DeclarationCategory id={self.id!r} "
            f"category={self.category!r} qty_kg={self.declared_quantity_kg}>"
        )


# ─────────────────────────────────────────────
# Model 3: ReconciliationLog
# ─────────────────────────────────────────────

class ReconciliationLog(Base):
    """
    Append-only audit record for each ERP reconciliation run.

    Created by GET /summary/{producer_id}/{month}. Captures:
      - A snapshot of ERP quantities at the time of reconciliation.
      - The deterministic mismatch analysis result (pure Python, no LLM).
      - The LLM-generated narrative summary (augmentation layer only).
      - Execution metadata for observability.

    Immutability contract:
        Records are never updated. Each /summary call produces a new log row,
        preserving the complete history of reconciliation attempts.
    """

    __tablename__ = "reconciliation_logs"
    __table_args__ = {
        "comment": "Audit trail of all ERP reconciliation runs against plastic declarations."
    }

    # ── Primary Key ────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    # ── Foreign Key ────────────────────────────
    declaration_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plastic_declarations.record_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The declaration this reconciliation run was performed against.",
    )

    # ── ERP Snapshot (point-in-time) ───────────
    erp_rigid_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="ERP-reported rigid plastic procurement (kg) at time of reconciliation.",
    )
    erp_flexible_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="ERP-reported flexible plastic procurement (kg).",
    )
    erp_multilayer_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="ERP-reported multilayer plastic procurement (kg).",
    )

    # ── Deterministic Analysis ─────────────────
    status: Mapped[str] = mapped_column(
        SAEnum(ReconciliationStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ReconciliationStatus.PENDING,
        comment="Lifecycle status of this reconciliation run.",
    )
    has_mismatch: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if any category exceeded the configured variance threshold (default 5%).",
    )
    mismatch_categories: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated list of flagged categories (e.g. 'flexible_plastic,multilayer_plastic').",
    )
    threshold_used_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
        comment="Mismatch threshold percentage used in this run (from config, not hardcoded).",
    )

    # ── AI Augmentation Layer ──────────────────
    narrative_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM-generated narrative. Populated AFTER deterministic analysis. NEVER affects logic.",
    )
    llm_model_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Model identifier used for narrative generation (e.g. llama3-70b-8192).",
    )

    # ── Audit & Observability ──────────────────
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="UTC timestamp when this reconciliation run completed.",
    )
    execution_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total reconciliation execution time in milliseconds.",
    )

    # ── Relationships ──────────────────────────
    declaration: Mapped["PlasticDeclaration"] = relationship(
        "PlasticDeclaration",
        back_populates="reconciliation_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<ReconciliationLog id={self.id!r} "
            f"declaration_id={self.declaration_id!r} "
            f"status={self.status!r} has_mismatch={self.has_mismatch}>"
        )
