"""
app/graph/nodes/load_erp_feed.py
================================
Graph Node 2: Load ERP Feed
"""

from app.core.logger import get_logger
from app.graph.state import SummaryState
from app.services.erp_service import ERPService

logger = get_logger(__name__)


def get_load_erp_feed_node(erp_service: ERPService):
    """
    Factory returning the load_erp_feed node bound to its dependencies.
    """
    
    async def load_erp_feed(state: SummaryState) -> dict:
        logger.debug("Graph Node: load_erp_feed")
        
        producer_id = state["producer_id"].upper()
        month = state["month"]
        
        # Synchronous parsing for the mock CSV, runs fast enough
        snapshot = erp_service.get_procurement_snapshot(producer_id, month)
        
        logger.info(f"Loaded ERP snapshot with {snapshot.record_count} records")
        
        return {"erp_snapshot": snapshot}
        
    return load_erp_feed
