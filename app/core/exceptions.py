"""
app/core/exceptions.py
=======================
Domain-level exception hierarchy for EcoRecon AI.

Design decisions:
  - Every domain error descends from a single ``EcoReconError`` base class so
    callers can catch the full family with one except clause.
  - Each exception carries a machine-readable ``error_code`` alongside the
    human-readable message — essential for audit logs and client error handling.
  - FastAPI exception handlers (registered in app/main.py) translate these into
    structured JSON responses without leaking stack traces.
  - No generic ``Exception`` re-raises anywhere in the platform — every failure
    path must be explicit and attributable.
"""

from typing import Any, Optional


# ─────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────

class EcoReconError(Exception):
    """
    Root exception for all EcoRecon AI domain errors.

    Attributes:
        message:    Human-readable description of the error.
        error_code: Machine-readable identifier (e.g. ``DECLARATION_NOT_FOUND``).
        detail:     Optional arbitrary payload for additional context.
        status_code: Suggested HTTP status code for API responses.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        detail: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.error_code
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict for API error responses."""
        payload: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


# ─────────────────────────────────────────────
# Validation Errors (400)
# ─────────────────────────────────────────────

class ValidationError(EcoReconError):
    """Raised when deterministic input validation fails."""
    status_code = 400
    error_code = "VALIDATION_ERROR"


class InvalidMonthFormatError(ValidationError):
    """Raised when the month field does not match YYYY-MM."""
    error_code = "INVALID_MONTH_FORMAT"

    def __init__(self, month: str) -> None:
        super().__init__(
            message=f"Invalid month format: '{month}'. Expected YYYY-MM (e.g. 2026-04).",
            detail={"provided_month": month, "expected_format": "YYYY-MM"},
        )


class NegativeQuantityError(ValidationError):
    """Raised when any declared plastic quantity is negative."""
    error_code = "NEGATIVE_QUANTITY"

    def __init__(self, category: str, value: float) -> None:
        super().__init__(
            message=f"Declared quantity for '{category}' must be ≥ 0. Got: {value}.",
            detail={"category": category, "value": value},
        )


# ─────────────────────────────────────────────
# Not Found Errors (404)
# ─────────────────────────────────────────────

class NotFoundError(EcoReconError):
    """Raised when a requested resource does not exist."""
    status_code = 404
    error_code = "NOT_FOUND"


class DeclarationNotFoundError(NotFoundError):
    """Raised when a declaration record cannot be located."""
    error_code = "DECLARATION_NOT_FOUND"

    def __init__(self, producer_id: str, month: str) -> None:
        super().__init__(
            message=(
                f"No declaration found for producer '{producer_id}' "
                f"and month '{month}'."
            ),
            detail={"producer_id": producer_id, "month": month},
        )


class ERPFeedNotFoundError(NotFoundError):
    """Raised when the ERP CSV feed cannot be located or read."""
    error_code = "ERP_FEED_NOT_FOUND"

    def __init__(self, path: str) -> None:
        super().__init__(
            message=f"ERP feed not found at path: '{path}'.",
            detail={"path": path},
        )


# ─────────────────────────────────────────────
# Conflict Errors (409)
# ─────────────────────────────────────────────

class ConflictError(EcoReconError):
    """Raised when an operation conflicts with existing state."""
    status_code = 409
    error_code = "CONFLICT"


class DuplicateDeclarationError(ConflictError):
    """Raised when a declaration already exists for the given producer+month."""
    error_code = "DUPLICATE_DECLARATION"

    def __init__(self, producer_id: str, month: str) -> None:
        super().__init__(
            message=(
                f"Declaration for producer '{producer_id}' and month '{month}' "
                f"already exists."
            ),
            detail={"producer_id": producer_id, "month": month},
        )


# ─────────────────────────────────────────────
# AI / RAG Errors (502)
# ─────────────────────────────────────────────

class AIServiceError(EcoReconError):
    """Raised when an upstream AI service call fails."""
    status_code = 502
    error_code = "AI_SERVICE_ERROR"


class LLMUnavailableError(AIServiceError):
    """Raised when the Groq LLM cannot be reached."""
    error_code = "LLM_UNAVAILABLE"


class EmbeddingServiceError(AIServiceError):
    """Raised when the Ollama embedding service fails."""
    error_code = "EMBEDDING_SERVICE_ERROR"


class RAGRetrievalError(AIServiceError):
    """Raised when ChromaDB retrieval fails unexpectedly."""
    error_code = "RAG_RETRIEVAL_ERROR"


# ─────────────────────────────────────────────
# Infrastructure Errors (503)
# ─────────────────────────────────────────────

class InfrastructureError(EcoReconError):
    """Raised when a platform dependency (DB, file system) is unavailable."""
    status_code = 503
    error_code = "INFRASTRUCTURE_ERROR"


class DatabaseError(InfrastructureError):
    """Raised when a database operation fails at the infrastructure level."""
    error_code = "DATABASE_ERROR"
