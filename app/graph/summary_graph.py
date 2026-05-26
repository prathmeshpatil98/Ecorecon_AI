"""
app/graph/summary_graph.py
==========================
LangGraph orchestration for the GET /summary endpoint.

Modular Node Architecture:
  START -> fetch_declaration -> load_erp_feed -> reconcile -> generate_summary -> build_response -> END
"""

import time
from langgraph.graph import END, START, StateGraph

from app.core.logger import get_logger
from app.graph.state import SummaryState
from app.graph.nodes.fetch_declaration import get_fetch_declaration_node
from app.graph.nodes.load_erp_feed import get_load_erp_feed_node
from app.graph.nodes.reconcile import get_reconcile_node
from app.graph.nodes.generate_summary import get_generate_summary_node
from app.graph.nodes.response_builder import get_response_builder_node
from app.schemas.summary_schema import SummaryResponse
from app.services.erp_service import ERPService
from app.services.reconciliation_service import ReconciliationService
from app.services.llm_service import LLMService

logger = get_logger(__name__)


class SummaryOrchestrator:
    """
    Stateful orchestrator for the EPR summary generation workflow.
    Uses LangGraph to enforce the sequence of modular, deterministic nodes.
    """

    def __init__(self, reconciliation_service: ReconciliationService, erp_service: ERPService, llm_service: LLMService):
        self._reconciliation_service = reconciliation_service
        self._erp_service = erp_service
        self._llm_service = llm_service
        # repository is accessed through reconciliation_service._repo for the node factory
        repository = reconciliation_service._repo
        
        # Initialize graph builder
        workflow = StateGraph(SummaryState)
        
        # Add modular nodes using their factories
        workflow.add_node("fetch_declaration", get_fetch_declaration_node(repository))
        workflow.add_node("load_erp_feed", get_load_erp_feed_node(erp_service))
        workflow.add_node("reconcile", get_reconcile_node(reconciliation_service))
        workflow.add_node("generate_summary", get_generate_summary_node(llm_service))
        workflow.add_node("build_response", get_response_builder_node())
        
        # Define strict acyclic execution path
        workflow.add_edge(START, "fetch_declaration")
        workflow.add_edge("fetch_declaration", "load_erp_feed")
        workflow.add_edge("load_erp_feed", "reconcile")
        workflow.add_edge("reconcile", "generate_summary")
        workflow.add_edge("generate_summary", "build_response")
        workflow.add_edge("build_response", END)
        
        self.graph = workflow.compile()

    async def execute(self, producer_id: str, month: str) -> SummaryResponse:
        """
        Execute the modular summary workflow.
        """
        logger.info(
            "Starting SummaryGraph execution (Modular)",
            extra={"producer_id": producer_id, "month": month}
        )
        
        initial_state: SummaryState = {
            "producer_id": producer_id,
            "month": month,
            "start_ms": time.monotonic(),
            "declaration": None,
            "erp_snapshot": None,
            "reconciliation": None,
            "narrative": None,
            "response": None,
        }
        
        final_state = await self.graph.ainvoke(initial_state)
        
        if not final_state.get("response"):
            raise RuntimeError("SummaryGraph finished without producing a response.")
            
        return final_state["response"]
