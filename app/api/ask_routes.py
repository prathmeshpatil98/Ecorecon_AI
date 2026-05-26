"""
app/api/ask_routes.py
=====================
HTTP route for POST /ask — Hallucination-safe RAG pipeline for compliance documents.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.logger import get_logger
from app.schemas.rag_schema import AskRequest, AskResponse
from app.services.llm_service import LLMService
from app.rag.vectorstore import VectorStoreManager
from app.services.retrieval_service import RetrievalService

logger = get_logger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────
# Dependency Factories
# ─────────────────────────────────────────────

def get_vector_store_manager() -> VectorStoreManager:
    return VectorStoreManager()

def get_llm_service() -> LLMService:
    return LLMService()

def get_retrieval_service(
    vsm: Annotated[VectorStoreManager, Depends(get_vector_store_manager)],
    llm: Annotated[LLMService, Depends(get_llm_service)]
) -> RetrievalService:
    """Dependency for the enterprise retrieval service."""
    return RetrievalService(vector_store_manager=vsm, llm_service=llm)


# ─────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────

@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a compliance question (Hallucination-safe RAG)",
    description=(
        "**Queries the EPR compliance document corpus.** "
        "\n\n"
        "This endpoint uses LangGraph to orchestrate a hallucination-safe RAG workflow:\n"
        "1. **Retrieval**: Searches ChromaDB for relevant document chunks.\n"
        "2. **Threshold Filter**: Drops any chunks below the similarity threshold.\n"
        "3. **Generation**: Instructs the LLM to answer ONLY using the retrieved context.\n"
        "4. **Deterministic Fallback**: If no chunks pass the threshold, or if the LLM "
        "cannot find the answer, it returns exactly: *'I do not know based on the provided documents.'*\n\n"
        "All returned answers include explicit source citations with similarity scores."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Question processed successfully.",
            "model": AskResponse,
        },
    },
)
async def ask_question(
    payload: AskRequest,
    retrieval_service: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> AskResponse:
    """
    **POST /ask** — Submit a natural language question about EPR compliance.
    """
    logger.info(
        "POST /ask received",
        extra={"question": payload.question},
    )

    answer, is_fallback, citations = await retrieval_service.ask_question(payload.question)
    
    response = AskResponse(
        question=payload.question,
        answer=answer,
        is_fallback=is_fallback,
        citations=citations,
        generated_at=datetime.now(timezone.utc)
    )

    logger.info(
        "POST /ask completed",
        extra={
            "is_fallback": response.is_fallback,
            "citations_count": len(response.citations),
        },
    )

    return response
