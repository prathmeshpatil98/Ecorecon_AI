"""
app/rag/ingest.py
=================
Pipeline orchestrator for advanced RAG document ingestion.
"""

import glob
import os

from app.core.logger import get_logger
from app.rag.chunking import ComplianceDocumentChunker
from app.rag.vectorstore import VectorStoreManager

logger = get_logger(__name__)


class DocumentIngestionPipeline:
    """
    Orchestrates the ingestion of compliance markdown documents into the
    ChromaDB vector store with contextual chunking and metadata tracking.
    """

    def __init__(self, docs_dir: str = "data/compliance_docs"):
        self.docs_dir = docs_dir
        self.chunker = ComplianceDocumentChunker(chunk_size=500, chunk_overlap=50)
        self.vector_store_manager = VectorStoreManager()

    async def run(self):
        """
        Execute the end-to-end ingestion pipeline.
        """
        logger.info(f"Starting advanced ingestion pipeline from directory: {self.docs_dir}")
        
        if not os.path.exists(self.docs_dir):
            logger.error(f"Documents directory not found: {self.docs_dir}")
            return

        md_files = glob.glob(os.path.join(self.docs_dir, "**/*.md"), recursive=True)
        if not md_files:
            logger.warning(f"No markdown documents found in {self.docs_dir}.")
            return

        logger.info(f"Found {len(md_files)} document(s) to ingest.")

        all_chunks = []
        for file_path in md_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Derive a naive category based on the filename or parent dir
                # For this implementation, we just use a default category
                category = "epr_compliance"
                
                chunks = self.chunker.process_document(
                    file_path=file_path,
                    content=content,
                    category=category
                )
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Failed to process document {file_path}: {e}")

        if all_chunks:
            logger.info(f"Pipeline generated a total of {len(all_chunks)} enriched chunks.")
            await self.vector_store_manager.add_documents(all_chunks)
            logger.info("Advanced ingestion pipeline completed successfully.")
        else:
            logger.warning("Pipeline completed but generated 0 chunks.")


# ─────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    
    async def main():
        pipeline = DocumentIngestionPipeline()
        await pipeline.run()

    asyncio.run(main())
