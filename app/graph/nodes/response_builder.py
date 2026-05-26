"""
app/graph/nodes/response_builder.py
===================================
Graph Node 5: Response Builder
"""

from datetime import datetime, timezone

from app.core.logger import get_logger
from app.graph.state import SummaryState
from app.schemas.summary_schema import SummaryResponse

logger = get_logger(__name__)


def get_response_builder_node():
    """
    Factory returning the response_builder node.
    """
    
    async def response_builder(state: SummaryState) -> dict:
        logger.debug("Graph Node: response_builder")
        recon = state["reconciliation"]
        narrative = state["narrative"]
        
        if not recon:
            raise ValueError("Reconciliation result missing from state.")
            
        response = SummaryResponse(
            record_id=recon.record_id,
            log_id=recon.log_id,
            reconciliation=recon,
            narrative=narrative,
            generated_at=datetime.now(timezone.utc),
        )
        
        return {"response": response}
        
    return response_builder
