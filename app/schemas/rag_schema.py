"""
app/schemas/rag_schema.py
=========================
Pydantic v2 schemas for the /ask (RAG) endpoint.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    """Request payload for the /ask endpoint."""
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        min_length=5,
        max_length=500,
        description="The compliance question to ask.",
        examples=["What is the mismatch threshold for flexible plastic?"]
    )


class Citation(BaseModel):
    """Citation of a specific document chunk used in the response."""
    model_config = ConfigDict(frozen=True)

    source: str = Field(description="Filename of the source document.")
    chunk_text: str = Field(description="The exact text snippet retrieved.")
    similarity_score: float = Field(description="Cosine similarity score of the retrieval.")


class AskResponse(BaseModel):
    """API response for the /ask endpoint."""
    model_config = ConfigDict(frozen=True)

    question: str = Field(description="The original question.")
    answer: str = Field(description="The LLM-generated answer or the deterministic fallback.")
    citations: tuple[Citation, ...] = Field(
        default_factory=tuple,
        description="List of document citations used to generate the answer."
    )
    is_fallback: bool = Field(
        description="True if the deterministic 'I do not know' fallback was triggered."
    )
    generated_at: datetime = Field(description="UTC timestamp of the response.")
