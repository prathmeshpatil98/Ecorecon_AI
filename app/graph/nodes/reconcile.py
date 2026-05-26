"""
app/graph/nodes/reconcile.py
============================
Graph Node 3: Deterministic Reconciliation
"""

from app.core.logger import get_logger
from app.graph.state import SummaryState
from app.services.reconciliation_service import ReconciliationService

logger = get_logger(__name__)


def get_reconcile_node(reconciliation_service: ReconciliationService):
    """
    Factory returning the reconcile node bound to its dependencies.
    """
    
    async def reconcile(state: SummaryState) -> dict:
        logger.debug("Graph Node: reconcile")
        
        declaration = state["declaration"]
        erp_snapshot = state["erp_snapshot"]
        start_ms = state["start_ms"]
        
        if not declaration or not erp_snapshot:
            raise ValueError("Missing prerequisite data for reconciliation.")
            
        result = await reconciliation_service.compute_reconciliation(
            declaration=declaration,
            erp_snapshot=erp_snapshot,
            start_ms=start_ms
        )
        
        logger.info("Deterministic reconciliation math complete")
        
        return {"reconciliation": result}
        
    return reconcile
