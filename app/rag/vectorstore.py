"""
app/rag/vectorstore.py
======================
Manages the ChromaDB vector storage and Ollama embeddings integration.
"""

from typing import List

from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class VectorStoreManager:
    """
    Manages the ChromaDB vector store and handles document embedding
    via the Nomic embeddings model running on Ollama.
    """

    def __init__(self, collection_name: str = "ecorecon_compliance"):
        self.settings = get_settings()
        self.collection_name = collection_name
        
        # Initialize Ollama embeddings with the specified Nomic model
        self.embeddings = OllamaEmbeddings(
            model=self.settings.ollama_embed_model,
            base_url=self.settings.ollama_base_url,
        )
        
        # Initialize Chroma vector store
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.settings.chroma_persist_dir,
        )
        logger.info(f"Initialized ChromaDB vector store for collection '{self.collection_name}'")

    async def add_documents(self, documents: List[Document]) -> None:
        """
        Embed and store a list of LangChain documents into ChromaDB.
        """
        if not documents:
            logger.warning("No documents provided for insertion.")
            return

        logger.info(f"Adding {len(documents)} document chunks to vector store...")
        await self.vector_store.aadd_documents(documents)
        logger.info("Successfully added documents to vector store.")

    def get_retriever(self, search_kwargs: dict = None):
        """
        Get a LangChain retriever interface for the vector store.
        """
        kwargs = search_kwargs or {"k": 4}
        return self.vector_store.as_retriever(search_kwargs=kwargs)
