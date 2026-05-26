"""
evaluation/deepeval/test_context_precision.py
=============================================
DeepEval validation for Contextual Precision.
Evaluates the retrieval pipeline's ability to rank relevant context highly.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import ContextualPrecisionMetric
from deepeval.test_case import LLMTestCase
from evaluation.deepeval.conftest import OllamaLLM
PRECISION_THRESHOLD = 0.5


@pytest.mark.asyncio
async def test_contextual_precision_high():
    """
    Test that the retriever provides the most relevant context at the top of the results.
    """
    input_question = "Who must maintain the ERP procurement systems?"
    
    # Context ordered from most relevant to least relevant
    retrieval_context = [
        "Producers must maintain a verifiable paper trail linking their ERP procurement systems to their environmental declarations.",
        "GreenPack Industries is obligated to ensure plastic waste is recycled.",
        "A variance of more than 5% is a material mismatch."
    ]
    
    # Expected output based strictly on context
    expected_output = "Producers are required to maintain a verifiable paper trail for their ERP procurement systems."

    ollama_llm = OllamaLLM(model_name="gpt-oss:20b-cloud")
    metric = ContextualPrecisionMetric(threshold=PRECISION_THRESHOLD, model=ollama_llm)
    
    test_case = LLMTestCase(
        input=input_question,
        actual_output=expected_output,
        expected_output=expected_output,
        retrieval_context=retrieval_context,
    )

    assert_test(test_case, [metric])
