"""
evaluation/deepeval/test_faithfulness.py
========================================
DeepEval validation for answer faithfulness.
Ensures the RAG pipeline output strictly derives from the provided context.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

# We set a very strict threshold for compliance intelligence
FAITHFULNESS_THRESHOLD = 1.0


@pytest.mark.asyncio
async def test_faithfulness_valid_answer():
    """
    Test that a highly accurate, grounded response passes faithfulness evaluation.
    """
    input_question = "What is the variance threshold for flexible plastic?"
    actual_output = "The variance threshold for flexible plastic is 5% [pwm_rules.md - Section 2]."
    retrieval_context = [
        "A variance of more than 5% (flexible or rigid plastic) is considered a material mismatch and flags the producer for compliance review."
    ]

    metric = FaithfulnessMetric(threshold=FAITHFULNESS_THRESHOLD)
    test_case = LLMTestCase(
        input=input_question,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
    )
    
    assert_test(test_case, [metric])


@pytest.mark.asyncio
async def test_faithfulness_detects_fabrication():
    """
    Test that the metric catches when the LLM hallucinates an answer
    not present in the retrieved context.
    
    Note: In a real CI environment we use try/except around assert_test
    to verify that the metric properly FAILS this case.
    """
    input_question = "What is the variance threshold for flexible plastic?"
    # The actual output invents a 10% threshold
    actual_output = "The variance threshold for flexible plastic is 10%."
    retrieval_context = [
        "A variance of more than 5% (flexible or rigid plastic) is considered a material mismatch."
    ]

    metric = FaithfulnessMetric(threshold=FAITHFULNESS_THRESHOLD)
    test_case = LLMTestCase(
        input=input_question,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
    )
    
    # We expect this to fail
    try:
        assert_test(test_case, [metric])
        pytest.fail("Faithfulness metric failed to catch a hallucinated threshold.")
    except AssertionError:
        pass  # Expected behavior
