"""
app/graph/nodes/fetch_declaration.py
====================================
Graph Node 1: Fetch Declaration
"""

from app.core.exceptions import DeclarationNotFoundError
from app.core.logger import get_logger
from app.graph.state import SummaryState
from app.repositories.declaration_repository import DeclarationRepository

logger = get_logger(__name__)


def get_fetch_declaration_node(repository: DeclarationRepository):
    """
    Factory returning the fetch_declaration node bound to its dependencies.
    """
    
    async def fetch_declaration(state: SummaryState) -> dict:
        logger.debug("Graph Node: fetch_declaration")
        
        producer_id = state["producer_id"].upper()
        month = state["month"]
        
        declaration = await repository.get_by_producer_month(producer_id, month)
        if not declaration:
            raise DeclarationNotFoundError(producer_id=producer_id, month=month)
            
        logger.info(f"Fetched declaration {declaration.record_id}")
            
        return {"declaration": declaration}
        
    return fetch_declaration
