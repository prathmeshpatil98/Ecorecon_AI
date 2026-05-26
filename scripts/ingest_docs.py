"""
scripts/ingest_docs.py
======================
Standalone script to ingest markdown compliance documents into ChromaDB.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.vectorstore import VectorStoreManager

logger = get_logger(__name__)


async def main():
    settings = get_settings()
    docs_dir = settings.compliance_docs_dir

    logger.info(f"Loading compliance documents from {docs_dir}")

    # Load all markdown files in the directory
    loader = DirectoryLoader(
        docs_dir,
        glob="**/*.md",
        loader_cls=TextLoader,
        show_progress=True,
    )
    docs = loader.load()

    if not docs:
        logger.warning(f"No markdown documents found in {docs_dir}.")
        return

    logger.info(f"Loaded {len(docs)} documents.")

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    chunks = text_splitter.split_documents(docs)

    logger.info(f"Split documents into {len(chunks)} chunks.")

    # Ingest into ChromaDB
    vector_store_manager = VectorStoreManager()
    logger.info(
        f"Adding {len(chunks)} chunks to Chroma collection '{vector_store_manager.collection_name}'..."
    )
    
    # Add documents to the vector store
    await vector_store_manager.add_documents(chunks)
    
    logger.info("Ingestion complete. The /ask endpoint is ready.")


if __name__ == "__main__":
    asyncio.run(main())
