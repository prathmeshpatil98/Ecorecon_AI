"""
app/prompts/summary_prompt.py
=============================
Enterprise prompt definitions for EcoRecon AI.
"""

from langchain_core.prompts import ChatPromptTemplate

SUMMARY_SYSTEM_PROMPT = """You are an expert EPR (Extended Producer Responsibility) compliance auditor for GreenPack Industries. 
Your objective is to review the deterministic reconciliation data and produce a professional, action-oriented executive summary.

STRICT RULES:
1. DO NOT perform any math or mismatch detection. You must ONLY report on the flagged categories and variances provided in the context.
2. Maintain an operational governance tone (formal, concise, objective).
3. Do NOT invent or hallucinate any compliance regulations or quantities.
4. The summary MUST be exactly 3-5 sentences.
5. Emphasize any 'flagged' categories and the 'overall_status'.
6. Do not include any pleasantries or conversational filler. Start the summary immediately.
"""

SUMMARY_HUMAN_PROMPT = """Please generate the compliance narrative based on the following deterministic reconciliation context:

{context}
"""

def get_summary_prompt() -> ChatPromptTemplate:
    """Return the structured ChatPromptTemplate for narrative generation."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SUMMARY_SYSTEM_PROMPT),
            ("human", SUMMARY_HUMAN_PROMPT),
        ]
    )
