---
name: hallucination-safe-rag
description: |
  Use this skill to enforce strict anti-hallucination protocols, citation validation, and deterministic fallbacks in AI-generated responses.
---

# Hallucination-Safe RAG Skill

## 1. Zero-Hallucination Imperative

For legal compliance platforms, hallucinating rules, circulars, or citation sections can result in direct regulatory violations. Under no circumstance may the system:
1.  **Fabricate regulations**: Every claim must be grounded in verified ingested regulatory context.
2.  **Fabricate citations**: Every chunk cited must exist in the retrieved vector context.
3.  **Extrapolate meaning**: Do not assume, project, or speculate on compliance obligations if the context is silent.

If a plain-English question cannot be fully answered with the retrieved context, the system must trigger a deterministic fallback and return the exact string:

> **"I do not know based on the provided documents."**

---

## 2. Multi-Tier Defense-in-Depth RAG Security Architecture

The RAG pipeline implements a 4-tier security boundary to isolate, filter, and police all generated response outputs before they return to the compliance officer.

```
   ┌──────────────────────────────────────────────────────────┐
   │                  User Question Ingest                    │
   └────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
   ┌──────────────────────────────────────────────────────────┐
   │       Vector Search (ChromaDB + nomic-embed-text)        │
   └────────────────────────────┬─────────────────────────────┘
                                │ Chunks + Cosine Similarity Scores
                                ▼
   ┌──────────────────────────────────────────────────────────┐
   │            Similarity Threshold Filtering                │
   │   Is Max Score >= 0.45?                                  │
   │   - [NO]  ──► [Hard Stop] Return: "I do not know..."     │
   │   - [YES] ──► Keep Only Chunks >= 0.45                   │
   └────────────────────────────┬─────────────────────────────┘
                                │ Filtered Chunks (high confidence)
                                ▼
   ┌──────────────────────────────────────────────────────────┐
   │                Grounded Context Prompt                   │
   │   - Inject ONLY filtered chunks                          │
   │   - Instruct Groq (meta-llama/llama-4-scout)             │
   │   - Enforce JSON format with Source, Section, ChunkText   │
   └────────────────────────────┬─────────────────────────────┘
                                │ Generated Raw Response
                                ▼
   ┌──────────────────────────────────────────────────────────┐
   │              Citation Grounding Validator                │
   │   Are all citations present in the retrieved set?        │
   │   - [NO]  ──► Prune fabricated citation/Raise error       │
   │   - [YES] ──► Assemble final schema Response             │
   └────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
   ┌──────────────────────────────────────────────────────────┐
   │                     Summary Response                     │
   └──────────────────────────────────────────────────────────┘
```

---

## 3. Strict Prompt Calibration (System Prompts)

To enforce strict contextual alignment, prompt engineering must explicitly restrict Groq's generation window. **Never use open-ended chat prompts.**

### Authorized System Prompt Pattern for `/ask`

```
You are an expert Extended Producer Responsibility (EPR) compliance audit engine for GreenPack Industries.
Your sole task is to answer the compliance officer's question using ONLY the verified regulatory context blocks provided below.

=== RULES OF ENGAGEMENT ===
1. If the answer cannot be directly derived from the verified context below, return exactly: "I do not know based on the provided documents."
2. You must never extrapolate, assume, or suggest information. If a detail is missing, treat it as unknown.
3. Every claim you make MUST be directly associated with a citation.
4. Your response must be formatted as a structured JSON object containing:
   - "answer": A clear, natural language summary of the compliance rule.
   - "citations": An array of citation objects, each containing:
     - "source": Filename of the source document.
     - "section": Title/Heading of the section.
     - "chunk_text": The exact snippet from the context that supports the answer.
     - "similarity_score": The matching confidence score of the chunk.

=== VERIFIED REGULATORY CONTEXT ===
{context_blocks}

=== QUESTION ===
{question}
```

---

## 4. Citation Validation Schema (Pydantic v2)

API responses map citations cleanly to make source provenance transparent to the auditor. 

### Grounding Citation Models

```python
from typing import List, Optional
from pydantic import BaseModel, Field

class Citation(BaseModel):
    """
    Structured citation representing the exact source location of verified context.
    """
    source: str = Field(..., description="The name of the source regulation document (e.g. CPCB_Notification.pdf).")
    section: str = Field(..., description="The specific heading or chapter (e.g. Section 4(b) - Targets).")
    chunk_text: str = Field(..., description="The precise textual snippet extracted from the chunk.")
    similarity_score: float = Field(..., description="Cosine similarity score calculated by ChromaDB (must be >= 0.45).")

class AskResponse(BaseModel):
    """
    Response schema for POST /ask compliance questions.
    """
    question: str = Field(..., description="The compliance officer's original question.")
    answer: str = Field(..., description="The grounded natural language response.")
    citations: List[Citation] = Field(default_factory=list, description="List of source citations verifying the answer.")
    is_fallback: bool = Field(
        ...,
        description="True if the search failed to meet confidence thresholds and returned the fallback string."
    )
```

---

## 5. Retrieval Guardrail Implementation

Below is the concrete logical block executed within `RetrievalService` to guarantee that low-confidence matching blocks do not reach the LLM:

```python
async def query_compliance_docs(question: str, settings, vector_db) -> AskResponse:
    # 1. Fetch nearest chunks (top_k)
    results = vector_db.similarity_search_with_relevance_scores(question, k=settings.rag_top_k)
    
    # 2. Extract and filter by threshold (e.g. 0.45)
    filtered_results = [
        (doc, score) for doc, score in results 
        if score >= settings.rag_similarity_threshold
    ]
    
    # 3. Check for fallback trigger
    if not filtered_results:
        return AskResponse(
            question=question,
            answer="I do not know based on the provided documents.",
            citations=[],
            is_fallback=True
        )
        
    # 4. Map valid citations
    citations = [
        Citation(
            source=doc.metadata.get("source", "Unknown Document"),
            section=doc.metadata.get("section", "Unknown Section"),
            chunk_text=doc.page_content,
            similarity_score=float(score)
        )
        for doc, score in filtered_results
    ]
    
    # Proceed to trigger Groq LLM with citations...
```
