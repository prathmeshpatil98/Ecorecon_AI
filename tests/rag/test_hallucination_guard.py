"""
tests/rag/test_hallucination_guard.py
=====================================
Unit tests for the HallucinationGuard service.
Validates strict fallback and anti-fabrication behavior.
"""

import pytest

from app.services.hallucination_guard import HallucinationGuard


def test_guard_low_confidence():
    """Test that empty retrieval triggers a guard failure."""
    is_valid = HallucinationGuard.validate_retrieval_confidence([])
    assert is_valid is False


def test_guard_valid_grounded_answer():
    """Test that an answer containing valid matching citations passes."""
    answer = "The variance threshold is 5% [pwm_rules.md - Section 2]."
    expected_citations = [
        {"source": "pwm_rules.md", "section": "Section 2", "text_snippet": "..."}
    ]
    
    validated = HallucinationGuard.validate_grounded_answer(answer, expected_citations)
    assert validated == answer


def test_guard_fabricated_citation():
    """Test that an answer fabricating an unknown citation is aggressively rejected."""
    answer = "The variance threshold is 10% [fake_law.pdf - Article 9]."
    expected_citations = [
        {"source": "pwm_rules.md", "section": "Section 2", "text_snippet": "..."}
    ]
    
    validated = HallucinationGuard.validate_grounded_answer(answer, expected_citations)
    assert validated == HallucinationGuard.FALLBACK_ANSWER


def test_guard_no_citations():
    """Test that an answer without explicit brackets is rejected."""
    answer = "The variance threshold is 5% according to the rules."
    expected_citations = [
        {"source": "pwm_rules.md", "section": "Section 2", "text_snippet": "..."}
    ]
    
    validated = HallucinationGuard.validate_grounded_answer(answer, expected_citations)
    assert validated == HallucinationGuard.FALLBACK_ANSWER


def test_guard_graceful_refusal():
    """Test that the LLM explicitly admitting ignorance passes through to fallback."""
    answer = "I do not know based on the provided documents because the document is missing."
    expected_citations = []
    
    validated = HallucinationGuard.validate_grounded_answer(answer, expected_citations)
    assert validated == HallucinationGuard.FALLBACK_ANSWER
