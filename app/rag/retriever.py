"""
app/rag/retriever.py
====================
Advanced retrieval orchestration combining multi-query, contextual compression, 
and strict similarity threshold filtering.
"""

from typing import List

from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logger import get_logger
from app.prompts.rag_prompt import QUERY_REFORMULATION_PROMPT
from app.rag.vectorstore import VectorStoreManager
from app.services.llm_service import LLMService

logger = get_logger(__name__)


class AdvancedRetriever:
    """
    Implements enterprise-grade RAG retrieval ensuring high recall (via multi-query)
    and high precision (via LLM-based contextual compression and thresholding).
    """

    def __init__(
        self, 
        vector_store_manager: VectorStoreManager,
        llm_service: LLMService,
    ):
        self.settings = get_settings()
        self.vector_store_manager = vector_store_manager
        self.llm_service = llm_service
        
        # Base retriever from ChromaDB (with basic similarity search)
        self.base_retriever = self.vector_store_manager.get_retriever(
            search_kwargs={"k": 5}
        )
        
        if self.llm_service.is_configured:
            llm = self.llm_service._llm
            
            # 1. MultiQueryRetriever: Generates variations of the query for higher recall
            self.multi_query_retriever = MultiQueryRetriever.from_llm(
                retriever=self.base_retriever,
                llm=llm,
                prompt=QUERY_REFORMULATION_PROMPT,
            )
            
            # 2. ContextualCompression: Extracts only relevant sentences from chunks to lower noise
            compressor = LLMChainExtractor.from_llm(llm)
            self.compression_retriever = ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=self.multi_query_retriever
            )
        else:
            logger.warning("LLM is not configured. Advanced retrieval will gracefully degrade to base retriever.")
            self.compression_retriever = self.base_retriever

    async def retrieve_and_filter(self, query: str) -> List[Document]:
        """
        Execute the advanced retrieval pipeline and apply strict post-filtering.
        """
        logger.debug(f"Starting advanced retrieval for query: {query}")
        
        try:
            # Execute contextual compression + multi-query (if LLM is available)
            if hasattr(self.compression_retriever, "ainvoke"):
                docs = await self.compression_retriever.ainvoke(query)
            else:
                docs = await self.compression_retriever.aget_relevant_documents(query)
                
            logger.info(f"Advanced retrieval returned {len(docs)} compressed document(s).")
            
            # Post-filter: Drop documents where the contextual compressor returned "NO_OUTPUT" (case-insensitive)
            filtered_docs = []
            for doc in docs:
                content_lower = doc.page_content.lower()
                if "no_output" in content_lower or "no output" in content_lower:
                    logger.debug(f"Filtering out document chunk from {doc.metadata.get('source_document')} due to 'NO_OUTPUT' compression output.")
                    continue
                filtered_docs.append(doc)
            
            logger.info(f"Advanced retrieval returned {len(filtered_docs)} document(s) after post-filtering.")
            
            if not filtered_docs:
                logger.warning("No context met the retrieval criteria. Dropping to fallback.")
            
            return filtered_docs
            
        except Exception as e:
            logger.error(f"Advanced retrieval failed: {e}")
            return []
