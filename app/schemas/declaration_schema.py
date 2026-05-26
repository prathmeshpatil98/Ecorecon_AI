"""
app/schemas/declaration_schema.py
===================================
Pydantic v2 request and response schemas for the POST /submit endpoint.

Design Decisions:
  - All validation is deterministic — pure Pydantic field_validators.
    No LLM, no inference, no semantic reasoning.
  - DeclaredQuantities uses a typed model (not a raw dict) so each
    category is schema-enforced, not arbitrarily extensible.
  - Negative quantity rejection happens at the Pydantic layer before
    the request touches the service or repository.
  - YYYY-MM format is enforced via a regex pattern validator — a
    malformed month string never reaches the database.
  - Response schemas mirror the DB model precisely, enabling clean
    serialisation without adapter layers.
  - `model_config = ConfigDict(from_attributes=True)` on response
    models allows direct `.model_validate(orm_instance)` calls.
"""

import re
from datetime import datetime
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_PRODUCER_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,98}[A-Z0-9]$")

VALID_CATEGORIES = frozenset(
    {"rigid_plastic", "flexible_plastic", "multilayer_plastic"}
)

# Positive float type alias — reused across all quantity fields
PositiveKg = Annotated[
    float,
    Field(ge=0.0, description="Declared quantity in kilograms. Must be >= 0."),
]


# ─────────────────────────────────────────────
# Sub-schema: Declared Quantities
# ─────────────────────────────────────────────

class DeclaredQuantitiesKg(BaseModel):
    """
    Per-category plastic quantities declared by the producer.

    Every field is individually typed and bounded — no raw dict, no
    arbitrary keys, no silent data loss. Future categories (e.g. EPS,
    PET) are added here as new typed fields.

    All values must be >= 0. The total must be > 0 (a zero-quantity
    declaration is meaningless and is rejected at model level).
    """

    model_config = ConfigDict(
        extra="forbid",  # Reject unknown categories — no silent pass-through
        str_strip_whitespace=True,
    )

    rigid_plastic: PositiveKg = Field(
        default=0.0,
        description="Rigid plastic declared in kilograms.",
        examples=[12000.0],
    )
    flexible_plastic: PositiveKg = Field(
        default=0.0,
        description="Flexible plastic declared in kilograms.",
        examples=[8500.0],
    )
    multilayer_plastic: PositiveKg = Field(
        default=0.0,
        description="Multilayer plastic declared in kilograms.",
        examples=[3200.0],
    )

    @model_validator(mode="after")
    def total_must_be_positive(self) -> "DeclaredQuantitiesKg":
        """
        Reject submissions where all quantities are zero.

        A declaration with total_kg == 0 indicates a data entry error
        and should not be persisted.
        """
        total = self.rigid_plastic + self.flexible_plastic + self.multilayer_plastic
        if total <= 0.0:
            raise ValueError(
                "Total declared quantity must be greater than 0. "
                "At least one category must have a non-zero value."
            )
        return self

    def to_category_dict(self) -> dict[str, float]:
        """
        Return quantities as a flat dict keyed by category name.

        Used by the repository's ``create()`` method to build
        ``DeclarationCategory`` rows.
        """
        return {
            "rigid_plastic": self.rigid_plastic,
            "flexible_plastic": self.flexible_plastic,
            "multilayer_plastic": self.multilayer_plastic,
        }

    @property
    def total_kg(self) -> float:
        """Computed total across all categories."""
        return self.rigid_plastic + self.flexible_plastic + self.multilayer_plastic


# ─────────────────────────────────────────────
# Request Schema
# ─────────────────────────────────────────────

class DeclarationSubmitRequest(BaseModel):
    """
    Request body for POST /submit.

    Validated deterministically at the HTTP boundary — no business logic,
    no LLM, no external I/O. Pure schema enforcement.

    Example::
        {
            "producer_id": "GREENPACK-001",
            "month": "2026-04",
            "declared_quantities_kg": {
                "rigid_plastic": 12000,
                "flexible_plastic": 8500,
                "multilayer_plastic": 3200
            }
        }
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "producer_id": "GREENPACK-001",
                "month": "2026-04",
                "declared_quantities_kg": {
                    "rigid_plastic": 12000,
                    "flexible_plastic": 8500,
                    "multilayer_plastic": 3200,
                },
            }
        },
    )

    producer_id: str = Field(
        min_length=2,
        max_length=100,
        description=(
            "Unique registered producer identifier. "
            "Must be uppercase alphanumeric with hyphens (e.g. GREENPACK-001)."
        ),
        examples=["GREENPACK-001"],
    )
    month: str = Field(
        description="Reporting period in YYYY-MM format (e.g. 2026-04).",
        examples=["2026-04"],
    )
    declared_quantities_kg: DeclaredQuantitiesKg = Field(
        description="Per-category declared plastic quantities in kilograms.",
    )

    # ── Field Validators ──────────────────────

    @field_validator("producer_id")
    @classmethod
    def validate_producer_id(cls, v: str) -> str:
        """
        Enforce producer ID format: uppercase alphanumeric + hyphens.

        Rejects:
          - lowercase characters
          - leading/trailing hyphens
          - special characters or spaces
        """
        normalised = v.strip().upper()
        if not _PRODUCER_ID_PATTERN.match(normalised):
            raise ValueError(
                f"Invalid producer_id format: '{v}'. "
                "Must be uppercase alphanumeric with hyphens (e.g. GREENPACK-001). "
                "Cannot start or end with a hyphen."
            )
        return normalised

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """
        Enforce YYYY-MM format with valid month range (01–12).

        Rejects:
          - YYYY/MM, MM-YYYY, or free-text months
          - Month 00 or 13+
          - Dates with day components (YYYY-MM-DD)
        """
        stripped = v.strip()
        if not _MONTH_PATTERN.match(stripped):
            raise ValueError(
                f"Invalid month format: '{v}'. "
                "Expected YYYY-MM with a valid month (01–12), e.g. '2026-04'."
            )
        return stripped


# ─────────────────────────────────────────────
# Response Schemas
# ─────────────────────────────────────────────

class CategoryQuantityResponse(BaseModel):
    """Per-category quantity as returned in the API response."""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(description="Plastic category name.")
    declared_quantity_kg: float = Field(description="Declared quantity in kilograms.")


class DeclarationSubmitResponse(BaseModel):
    """
    Response body for a successful POST /submit.

    Returns the full persisted record, including the server-generated
    ``record_id`` and ``submitted_at`` timestamp — enabling idempotency
    checks and audit log correlation by the caller.
    """

    model_config = ConfigDict(from_attributes=True)

    record_id: str = Field(description="UUID4 identifier assigned at submission.")
    producer_id: str = Field(description="Registered producer identifier.")
    month: str = Field(description="Reporting period (YYYY-MM).")
    total_declared_kg: float = Field(description="Sum of all declared category quantities.")
    categories: list[CategoryQuantityResponse] = Field(
        description="Breakdown of declared quantities per plastic category."
    )
    submitted_at: datetime = Field(description="UTC timestamp of submission.")
    revision: int = Field(description="Record revision number (1 for new submissions).")


class DeclarationErrorResponse(BaseModel):
    """Structured error response for failed submission validation."""

    error_code: str = Field(description="Machine-readable error identifier.")
    message: str = Field(description="Human-readable error description.")
    detail: Optional[dict] = Field(
        default=None,
        description="Additional context (field name, value, constraint).",
    )
