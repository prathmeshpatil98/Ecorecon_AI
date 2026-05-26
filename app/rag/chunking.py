"""
app/rag/chunking.py
===================
Advanced contextual chunking for compliance documents.
"""

import hashlib
import os
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logger import get_logger

logger = get_logger(__name__)


class ComplianceDocumentChunker:
    """
    Advanced chunker for compliance documents that preserves context
    and injects structured metadata into each chunk.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Using RecursiveCharacterTextSplitter for semantic boundary preservation
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    def process_document(self, file_path: str, content: str, category: str = "general") -> List[Document]:
        """
        Chunks the document text and enriches each chunk with required metadata.
        
        Args:
            file_path: The origin file path of the document.
            content: The raw text content of the document.
            category: The document category (e.g., 'epr_rules', 'plastic_waste').
            
        Returns:
            List of LangChain Document objects with contextual metadata.
        """
        filename = os.path.basename(file_path)
        logger.debug(f"Chunking document: {filename} with size={self.chunk_size}, overlap={self.chunk_overlap}")

        raw_chunks = self.text_splitter.split_text(content)
        documents = []

        for idx, chunk_text in enumerate(raw_chunks):
            # Attempt to extract a naive regulation section from the chunk
            # In a real enterprise system, this might use NLP or regex to find exact section headers
            first_line = chunk_text.split('\n')[0][:50].strip()
            regulation_section = first_line if len(first_line) > 5 else "Unknown Section"
            
            # Generate deterministic chunk ID
            chunk_hash = hashlib.sha256(f"{filename}_{idx}_{chunk_text}".encode()).hexdigest()[:12]
            
            # Preserve strict metadata hierarchy
            metadata = {
                "source_document": filename,
                "regulation_section": regulation_section,
                "chunk_id": f"{filename}_{idx}_{chunk_hash}",
                "document_category": category,
            }
            
            documents.append(
                Document(
                    page_content=chunk_text,
                    metadata=metadata
                )
            )

        logger.info(f"Processed '{filename}' into {len(documents)} contextual chunks.")
        return documents
