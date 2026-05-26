"""
app/graph/state.py
==================
Shared state definition for the EcoRecon LangGraph orchestrator.
"""

from typing import Optional, TypedDict

from app.database.models import PlasticDeclaration
from app.schemas.erp_schema import ERPProcurementSnapshot
from app.schemas.summary_schema import ReconciliationResult, SummaryResponse


class SummaryState(TypedDict):
    """
    State for the EcoRecon Summary generation graph.
    
    This enforces strict type boundaries between nodes, ensuring that 
    each node only has access to the data it requires or populates.
    """
    producer_id: str
    month: str
    start_ms: float
    
    # ── Populated by: fetch_declaration ──
    declaration: Optional[PlasticDeclaration]
    
    # ── Populated by: load_erp_feed ──
    erp_snapshot: Optional[ERPProcurementSnapshot]
    
    # ── Populated by: reconcile ──
    reconciliation: Optional[ReconciliationResult]
    
    # ── Populated by: generate_summary ──
    narrative: Optional[str]
    
    # ── Populated by: response_builder ──
    response: Optional[SummaryResponse]
