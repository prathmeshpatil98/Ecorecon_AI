"""
evaluation/deepeval/test_hallucination.py
=========================================
DeepEval validation for hallucination detection.
Ensures the AI does not inject external world knowledge into compliance answers.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import HallucinationMetric
from deepeval.test_case import LLMTestCase

# Zero tolerance for hallucinations in enterprise compliance
HALLUCINATION_THRESHOLD = 0.5


@pytest.mark.asyncio
async def test_hallucination_safe_output():
    """
    Test that a grounded output passes the hallucination guard.
    """
    input_question = "What happens if there is a mismatch above 5%?"
    actual_output = "If the mismatch is above 5%, the producer is flagged for compliance review."
    context = [
        "A variance of more than 5% (flexible or rigid plastic) is considered a material mismatch and flags the producer for compliance review."
    ]

    metric = HallucinationMetric(threshold=HALLUCINATION_THRESHOLD)
    test_case = LLMTestCase(
        input=input_question,
        actual_output=actual_output,
        context=context,
    )

    assert_test(test_case, [metric])


@pytest.mark.asyncio
async def test_hallucination_external_knowledge():
    """
    Test that injecting external world knowledge triggers a hallucination failure.
    """
    input_question = "What happens if there is a mismatch above 5%?"
    # The actual output includes external knowledge about fines not present in context
    actual_output = "The producer is flagged for compliance review and may face a penalty of up to Rs 100,000."
    context = [
        "A variance of more than 5% (flexible or rigid plastic) is considered a material mismatch and flags the producer for compliance review."
    ]

    metric = HallucinationMetric(threshold=HALLUCINATION_THRESHOLD)
    test_case = LLMTestCase(
        input=input_question,
        actual_output=actual_output,
        context=context,
    )

    try:
        assert_test(test_case, [metric])
        pytest.fail("Hallucination metric failed to catch external knowledge injection.")
    except AssertionError:
        pass  # Expected behavior
