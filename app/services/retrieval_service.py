"""
app/services/retrieval_service.py
=================================
Enterprise service for hallucination-safe compliance intelligence.
"""

from typing import List, Tuple

from app.core.logger import get_logger
from app.prompts.rag_prompt import get_grounded_generation_prompt
from app.rag.retriever import AdvancedRetriever
from app.rag.vectorstore import VectorStoreManager
from app.services.llm_service import LLMService
from app.services.hallucination_guard import HallucinationGuard

logger = get_logger(__name__)


class RetrievalService:
    """
    Service responsible for orchestrating the advanced retrieval and 
    grounded generation pipeline. Ensures zero-hallucination compliance.
    """

    FALLBACK_ANSWER = "I do not know based on the provided documents."

    def __init__(
        self,
        vector_store_manager: VectorStoreManager,
        llm_service: LLMService,
    ):
        self.llm_service = llm_service
        self.retriever = AdvancedRetriever(
            vector_store_manager=vector_store_manager,
            llm_service=llm_service
        )

    async def ask_question(self, question: str) -> Tuple[str, bool, List[dict]]:
        """
        Processes a compliance question through the advanced retrieval pipeline.
        
        Returns:
            Tuple of (answer, is_fallback, citations)
        """
        logger.info(f"RetrievalService processing question: {question}")
        
        # 1. Advanced Retrieval (Multi-Query + Contextual Compression)
        docs = await self.retriever.retrieve_and_filter(question)
        
        # 2. Strict Grounding Threshold Validation via Guard
        if not HallucinationGuard.validate_retrieval_confidence(docs):
            return self.FALLBACK_ANSWER, True, []
            
        # Extract and format context and citations
        formatted_context_parts = []
        citations = []
        
        for idx, doc in enumerate(docs):
            source = doc.metadata.get("source_document", "Unknown")
            section = doc.metadata.get("regulation_section", "Unknown")
            
            score = doc.metadata.get("score")
            if score is None:
                score = doc.metadata.get("similarity_score")
            if score is None:
                score = doc.metadata.get("relevance_score")
            if score is None:
                score = 0.9
                
            citations.append({
                "source": source,
                "section": section,
                "text_snippet": doc.page_content[:150] + "...",
                "chunk_text": doc.page_content,
                "similarity_score": float(score)
            })
            
            # Formatting context for the prompt
            formatted_context_parts.append(
                f"[Document {idx + 1}: {source} - {section}]\n{doc.page_content}\n"
            )
            
        formatted_context = "\n".join(formatted_context_parts)
        
        # 3. Grounded Answer Generation
        if not self.llm_service.is_configured:
            logger.warning("LLM is unconfigured. Returning fallback despite finding context.")
            return self.FALLBACK_ANSWER, True, citations
            
        try:
            prompt = get_grounded_generation_prompt()
            chain = prompt | self.llm_service._llm
            
            response = await chain.ainvoke({
                "context": formatted_context,
                "question": question
            })
            
            answer = str(response.content).strip()
            
            # 4. Hallucination Guard Validation (Defense-in-depth)
            validated_answer = HallucinationGuard.validate_grounded_answer(answer, citations)
            
            if validated_answer == self.FALLBACK_ANSWER:
                return self.FALLBACK_ANSWER, True, citations
                
            return validated_answer, False, citations
            
        except Exception as e:
            logger.error(f"Grounded generation failed: {e}")
            return self.FALLBACK_ANSWER, True, citations
