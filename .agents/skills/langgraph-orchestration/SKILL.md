---
name: langgraph-orchestration
description: |
  Use this skill to orchestrate LLM workflows using LangGraph. Ensures strict graph state management via TypedDict and isolates LLM calls from deterministic business logic.
---

# LangGraph Orchestration Skill

## 1. Principles of Stateful Graph Orchestration

LangGraph coordinates stateful, sequential operations across multi-node pipelines. In EcoRecon AI, the graph is utilized exclusively to manage the state machine and execute the narrative generation loop. 
*   **Decoupled State**: State management is cleanly decoupled from data layer storage.
*   **Separation of Concerns**: Deterministic steps (loading data, computing variance, and identifying severity) must run in isolated Python nodes before triggering any generative models.
*   **State Immutability**: All nodes receive the current state, compute a delta, and return a dictionary that updates the state using Pydantic schemas or standard Python types.

---

## 2. Strong Typing with State Dict (`TypedDict`)

To ensure compile-time and runtime safety, the entire pipeline is tracked within a strongly-typed graph state dictionary.

### Concrete State Class Schema Definition

Here is the exact state architecture representing the workflow inputs, intermediate calculations, and final Groq-generated narratives:

```python
from typing import Dict, List, Optional, TypedDict
from datetime import datetime
from pydantic import BaseModel

class CategoryData(BaseModel):
    category: str
    declared_kg: float
    procured_kg: float
    variance_kg: float
    deviation_pct: float
    is_flagged: bool
    severity: str

class DeterministicReconOutput(BaseModel):
    producer_id: str
    month: str
    record_id: str
    log_id: str
    categories: List[CategoryData]
    overall_status: str
    total_declared_kg: float
    total_procured_kg: float
    total_variance_kg: float
    overall_deviation_pct: float
    flagged_categories: List[str]
    has_mismatch: bool
    threshold_pct: float
    erp_record_count: int
    reconciled_at: datetime
    execution_ms: int

class ReconciliationGraphState(TypedDict):
    """
    Standard state tracking for a single reconciliation run.
    """
    # -- Initial Inputs
    producer_id: str
    month: str
    record_id: str
    log_id: str
    
    # -- Loaded Domain Data
    declared_quantities: Dict[str, float]
    erp_records: List[Dict[str, any]]
    
    # -- Intermediate Deterministic Results
    reconciliation_result: Optional[DeterministicReconOutput]
    
    # -- AI Output Narrative (Augmentation Only)
    llm_summary: Optional[str]
    
    # -- Trace Metadata
    error_message: Optional[str]
    is_success: bool
```

---

## 3. Sequential Directed Acyclic Graph (DAG) Transition Mappings

The workflow must execute in a strictly linear, acyclic sequence to ensure auditability and deterministic fallbacks. **Conditional routing to the LLM node must be bypassed if inputs are invalid.**

```
   ┌───────────────────────────────────────────────────────────┐
   │                       START NODE                          │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │                load_declaration_node                      │
   │      - Load raw declaration from SQLite DB                │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │                     load_erp_node                         │
   │      - Read monthly ERP csv procurement records            │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │                  reconcile_math_node                      │
   │      - Compute variance & flags dynamically               │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │               generate_narrative_node                     │
   │      - Invoke Groq (meta-llama/llama-4-scout)             │
   │      - Synthesize 3-5 sentence action narrative          │
   └─────────────────────────────┬─────────────────────────────┘
                                 │
                                 ▼
   ┌───────────────────────────────────────────────────────────┐
   │                        END NODE                           │
   └───────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Code Blueprint

Here is the exact structural standard for defining the graph workflow using LangGraph:

```python
from langgraph.graph import StateGraph, END
from app.services.reconciliation_service import ReconciliationService
from app.services.llm_service import LLMService

class ReconciliationWorkflow:
    def __init__(self):
        # 1. Initialize nodes and state graph
        workflow = StateGraph(ReconciliationGraphState)
        
        # 2. Define nodes
        workflow.add_node("load_declaration", self.load_declaration_node)
        workflow.add_node("load_erp", self.load_erp_node)
        workflow.add_node("reconcile_math", self.reconcile_math_node)
        workflow.add_node("generate_narrative", self.generate_narrative_node)
        
        # 3. Define execution path edges
        workflow.set_entry_point("load_declaration")
        workflow.add_edge("load_declaration", "load_erp")
        workflow.add_edge("load_erp", "reconcile_math")
        workflow.add_edge("reconcile_math", "generate_narrative")
        workflow.add_edge("generate_narrative", END)
        
        self.app = workflow.compile()

    async def load_declaration_node(self, state: ReconciliationGraphState) -> dict:
        # Load logic here...
        return {"declared_quantities": {...}}

    async def load_erp_node(self, state: ReconciliationGraphState) -> dict:
        # Load CSV logic here...
        return {"erp_records": [...]}

    async def reconcile_math_node(self, state: ReconciliationGraphState) -> dict:
        # Compute pure Python calculations here...
        result = ReconciliationService.reconcile(
            state["declared_quantities"], 
            state["erp_records"]
        )
        return {"reconciliation_result": result}

    async def generate_narrative_node(self, state: ReconciliationGraphState) -> dict:
        # Generate summary using Groq LLM
        summary = await LLMService().generate_compliance_summary(
            state["reconciliation_result"].to_llm_context()
        )
        return {"llm_summary": summary, "is_success": True}
```
