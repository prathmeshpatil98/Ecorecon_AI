"""
app/api/summary_routes.py
=========================
HTTP route for GET /summary — ERP compliance reconciliation and narrative.

Architecture Responsibilities:
  - Expose the GET endpoint.
  - Wire up dependency injection (DB session → Repository + ERP Service → Orchestrator).
  - Call the LangGraph orchestrator and return the final SummaryResponse.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.core.exceptions import DeclarationNotFoundError, ERPFeedNotFoundError
from app.core.logger import get_logger
from app.database.db import DBSession
from app.graph.summary_graph import SummaryOrchestrator
from app.repositories.declaration_repository import DeclarationRepository
from app.schemas.declaration_schema import DeclarationErrorResponse
from app.schemas.summary_schema import SummaryResponse
from app.services.erp_service import ERPService
from app.services.reconciliation_service import ReconciliationService
from app.services.llm_service import LLMService

logger = get_logger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────
# Dependency Factories
# ─────────────────────────────────────────────

def get_erp_service() -> ERPService:
    """Dependency for ERP ingestion service."""
    return ERPService()


def get_declaration_repository(db: DBSession) -> DeclarationRepository:
    """Dependency for DB operations."""
    return DeclarationRepository(session=db)


def get_reconciliation_service(
    repository: Annotated[DeclarationRepository, Depends(get_declaration_repository)],
    erp_service: Annotated[ERPService, Depends(get_erp_service)],
) -> ReconciliationService:
    """Dependency for the deterministic reconciliation engine."""
    return ReconciliationService(repository=repository, erp_service=erp_service)


def get_llm_service() -> LLMService:
    """Dependency for the enterprise LLM narrative service."""
    return LLMService()

def get_summary_orchestrator(
    reconciliation_service: Annotated[ReconciliationService, Depends(get_reconciliation_service)],
    erp_service: Annotated[ERPService, Depends(get_erp_service)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
) -> SummaryOrchestrator:
    """Dependency for the LangGraph orchestrator."""
    return SummaryOrchestrator(
        reconciliation_service=reconciliation_service, 
        erp_service=erp_service,
        llm_service=llm_service
    )


# ─────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────

@router.get(
    "/summary/{producer_id}/{month}",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get reconciliation summary and narrative",
    description=(
        "**Reconciles declared plastic quantities against ERP procurement data.** "
        "\n\n"
        "This endpoint uses LangGraph to orchestrate a two-step workflow:\n"
        "1. **Deterministic Math:** Pure Python reconciliation logic computes variances "
        "and flags >5% deviations. Results are stored in an audit table.\n"
        "2. **AI Narrative:** The deterministic results are passed to Groq (LLM) "
        "to generate a professional plain-English summary of the compliance status.\n\n"
        "If the LLM is unavailable, the endpoint degrades gracefully and still returns "
        "the full deterministic analysis with a fallback narrative string."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Reconciliation successful. Returns math and narrative.",
            "model": SummaryResponse,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Declaration or ERP feed not found.",
            "model": DeclarationErrorResponse,
        },
    },
)
async def get_summary(
    producer_id: Annotated[
        str,
        Path(
            description="Registered producer identifier.",
            examples=["GREENPACK-001"]
        )
    ],
    month: Annotated[
        str,
        Path(
            description="Reporting month in YYYY-MM format.",
            examples=["2026-04"]
        )
    ],
    orchestrator: Annotated[SummaryOrchestrator, Depends(get_summary_orchestrator)],
) -> SummaryResponse:
    """
    **GET /summary** — Retrieve the deterministic reconciliation and AI narrative.

    Args:
        producer_id: Path parameter.
        month:       Path parameter.
        orchestrator: Injected LangGraph orchestrator.

    Returns:
        The SummaryResponse combining the deterministic ReconciliationResult
        and the AI-generated narrative string.
    """
    logger.info(
        "GET /summary requested",
        extra={"producer_id": producer_id, "month": month},
    )

    # The orchestrator manages the strict boundary between math and LLM
    response = await orchestrator.execute(
        producer_id=producer_id,
        month=month,
    )

    logger.info(
        "GET /summary completed",
        extra={
            "producer_id": producer_id,
            "month": month,
            "has_mismatch": response.reconciliation.has_mismatch,
            "flagged_categories": list(response.reconciliation.flagged_categories),
        },
    )

    return response
