"""
app/graph/nodes/generate_summary.py
===================================
Graph Node 4: Narrative Summary Generation
"""

from app.core.logger import get_logger
from app.graph.state import SummaryState
from app.services.llm_service import LLMService

logger = get_logger(__name__)


def get_generate_summary_node(llm_service: LLMService):
    """
    Factory returning the generate_summary node bound to its dependencies.
    """
    
    async def generate_summary(state: SummaryState) -> dict:
        logger.debug("Graph Node: generate_summary")
        recon = state["reconciliation"]
        if not recon:
            raise ValueError("Reconciliation result missing from state.")

        # Bridge the deterministic result into a context dict
        context = recon.to_llm_context()
        
        # Generate the narrative via the enterprise LLM service
        narrative = await llm_service.generate_compliance_summary(context)
        
        return {"narrative": narrative}

    return generate_summary
