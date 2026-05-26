"""
app/core/config.py
==================
Centralised, typed configuration management for EcoRecon AI.

All settings are sourced from environment variables (via .env) using
Pydantic-Settings. This is the single source of truth for every tuneable
parameter in the platform — no magic strings scattered across the codebase.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    EcoRecon AI platform configuration.

    Priority order (highest → lowest):
      1. Environment variables
      2. .env file
      3. Field defaults defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment. Controls behaviour of certain guards.",
    )
    app_debug: bool = Field(default=False)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_title: str = "EcoRecon AI"
    app_version: str = "1.0.0"
    app_description: str = (
        "Deterministic-first EPR compliance and reconciliation platform "
        "for GreenPack Industries."
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="sqlite:///./ecorecon.db",
        description="SQLAlchemy-compatible database URL.",
    )

    # ------------------------------------------------------------------
    # Groq LLM
    # ------------------------------------------------------------------
    groq_api_key: str = Field(
        description="Groq API key — REQUIRED in .env for /summary and /ask endpoints.",
    )
    groq_model: str = Field(
        description="Groq model identifier — REQUIRED in .env file.",
    )
    groq_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    groq_max_tokens: int = Field(default=1024, ge=64)

    # ------------------------------------------------------------------
    # Ollama Embeddings
    # ------------------------------------------------------------------
    ollama_base_url: str = Field(
        description="Ollama base URL — REQUIRED in .env file.",
    )
    ollama_embed_model: str = Field(
        description="Ollama embedding model identifier — REQUIRED in .env file.",
    )

    # ------------------------------------------------------------------
    # ChromaDB
    # ------------------------------------------------------------------
    chroma_persist_dir: str = Field(default="./data/chroma_db")
    chroma_collection_name: str = Field(default="epr_compliance_docs")

    # ------------------------------------------------------------------
    # RAG Pipeline
    # ------------------------------------------------------------------
    rag_similarity_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum cosine similarity for a retrieved chunk to be used in generation. "
            "Chunks below this threshold trigger the deterministic fallback response."
        ),
    )
    rag_top_k: int = Field(default=5, ge=1)
    rag_chunk_size: int = Field(
        ge=50,
        description="RAG chunk size — REQUIRED in .env file.",
    )
    rag_chunk_overlap: int = Field(
        ge=0,
        description="RAG chunk overlap — REQUIRED in .env file.",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )

    # ------------------------------------------------------------------
    # ERP Data
    # ------------------------------------------------------------------
    erp_feed_path: str = Field(
        default="./data/erp/mock_erp_feed.csv",
        description="Path to the mock ERP procurement CSV feed.",
    )
    reconciliation_threshold_pct: float = Field(
        default=5.0,
        ge=0.0,
        description="Percentage deviation above which a category is flagged as mismatched.",
    )

    # ------------------------------------------------------------------
    # Compliance Docs
    # ------------------------------------------------------------------
    compliance_docs_dir: str = Field(
        default="./data/compliance_docs",
        description="Directory containing EPR compliance markdown documents for ingestion.",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def sqlalchemy_echo(self) -> bool:
        """Enable SQLAlchemy query logging only in non-production environments."""
        return not self.is_production and self.app_debug


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached singleton Settings instance.

    Usage (FastAPI dependency injection):
        from app.core.config import get_settings, Settings
        from fastapi import Depends

        def my_route(settings: Settings = Depends(get_settings)):
            ...
    """
    return Settings()
