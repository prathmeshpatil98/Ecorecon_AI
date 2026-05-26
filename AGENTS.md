# AI Architecture & Governance

EcoRecon AI is designed under a **Deterministic-First AI Engineering** paradigm. In enterprise compliance, auditability and mathematical correctness are non-negotiable. 

## 1. Deterministic-First Engineering
We strictly isolate business logic from Generative AI.
- **Math is Math**: Reconciliation (`app/services/reconciliation_service.py`) calculates mismatch percentages and threshold violations using pure Python. 
- **LLMs are Narrators**: The Large Language Model (Groq) is only allowed to observe the deterministic outputs and generate plain-English operational summaries. The LangGraph state machine enforces this strict boundary.

## 2. Hallucination-Safe RAG
Our Advanced Retrieval system goes beyond naive semantic search:
- **Query Reformulation**: `MultiQueryRetriever` rewrites the user's question to maximize recall.
- **Contextual Compression**: `ContextualCompressionRetriever` forces the LLM to extract only the sentences explicitly answering the prompt, minimizing noise before the final generation phase.
- **HallucinationGuard Middleware**: The `app/services/hallucination_guard.py` intercepts the final output. If the LLM fabricated a citation, ignored the context, or triggered a low-confidence retrieval, the Guard immediately aborts the response and triggers a deterministic fallback: *"I do not know based on the provided documents."*

## 3. Evaluation-Driven AI Engineering
We treat AI outputs as unit-testable code.
Using **DeepEval**, we run continuous CI/CD evaluations (`evaluation/deepeval/`):
- **Faithfulness**: Mathematically verifying that 100% of the generated claims exist in the retrieved context.
- **Answer Relevancy**: Penalizing evasive or tangential LLM responses.
- **Context Precision**: Verifying the ChromaDB/Ollama embedding pipeline surfaces the most critical chunks at rank 1.

## 4. LangGraph Orchestration
Rather than using unpredictable "Autonomous Agents", EcoRecon AI utilizes LangGraph to build strict, acyclic workflows. Nodes execute in a predetermined, auditable sequence:
`Fetch Declaration -> Load ERP -> Reconcile (Math) -> Generate Summary (AI) -> Build Response`.
This guarantees that compliance reports are generated consistently every single time.
