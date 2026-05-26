"""
app/services/hallucination_guard.py
===================================
Aggressive hallucination prevention layer for EcoRecon AI RAG.
"""

import re
from typing import List

from app.core.logger import get_logger

logger = get_logger(__name__)


class HallucinationGuard:
    """
    Enterprise guard service that validates LLM-generated answers against
    retrieved context to aggressively prevent unsupported generation and
    external knowledge leakage.
    """

    FALLBACK_ANSWER = "I do not know based on the provided documents."

    @classmethod
    def validate_retrieval_confidence(cls, docs: List) -> bool:
        """
        Check if the retrieval stage found sufficient context.
        """
        if not docs:
            logger.warning("Guard check failed: Retrieval confidence too low (0 documents).")
            return False
        return True

    @classmethod
    def validate_grounded_answer(cls, answer: str, expected_citations: List[dict]) -> str:
        """
        Validates the generated answer to ensure it is grounded and contains citations.
        Returns the original answer if valid, or the strict fallback if validation fails.
        """
        # 1. Did the LLM explicitly state it doesn't know?
        lower_answer = answer.lower()
        if "i do not know" in lower_answer or cls.FALLBACK_ANSWER.lower() in lower_answer:
            logger.info("Guard: LLM gracefully refused. Treating as fallback.")
            return cls.FALLBACK_ANSWER

        # 2. Citation existence validation
        # The prompt instructed the LLM to use [source_document - regulation_section] format.
        # We aggressively check if there are ANY brackets indicating a citation.
        citation_matches = re.findall(r"\[.*?\]", answer)
        if not citation_matches:
            logger.warning("Guard check failed: Answer generated without explicit inline citations.")
            return cls.FALLBACK_ANSWER

        # 3. Citation hallucination validation
        # Ensure the citations generated actually match the documents we provided in the context.
        provided_sources = {c["source"] for c in expected_citations}
        provided_sections = {c["section"] for c in expected_citations}
        
        valid_citation_found = False
        for match in citation_matches:
            match_clean = match.strip("[]")
            
            # Check if any part of the matched citation maps to our provided metadata
            source_valid = any(src in match_clean for src in provided_sources)
            section_valid = any(sec in match_clean for sec in provided_sections)
            
            if source_valid or section_valid:
                valid_citation_found = True
                break
                
        if not valid_citation_found:
            logger.warning(
                f"Guard check failed: LLM fabricated citations not in context. "
                f"Extracted: {citation_matches}, Expected Sources: {provided_sources}"
            )
            return cls.FALLBACK_ANSWER

        # Passed all guardrails
        logger.info("Guard: Answer passed hallucination prevention checks.")
        return answer
