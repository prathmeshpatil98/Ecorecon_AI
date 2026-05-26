"""
evaluation/deepeval/test_relevancy.py
=====================================
DeepEval validation for Answer Relevancy.
Ensures the LLM output directly answers the user's question without unnecessary tangents.
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from evaluation.deepeval.conftest import OllamaLLM
RELEVANCY_THRESHOLD = 0.7


@pytest.mark.asyncio
async def test_answer_relevancy_high():
    """
    Test that a concise, direct answer scores high in relevancy.
    """
    input_question = "What is the threshold for rigid plastic?"
    actual_output = "The variance threshold for rigid plastic is 5%."
    retrieval_context = [
        "A variance of more than 5% (flexible or rigid plastic) is considered a material mismatch."
    ]

    ollama_llm = OllamaLLM(model_name="gpt-oss:20b-cloud")
    metric = AnswerRelevancyMetric(threshold=RELEVANCY_THRESHOLD, model=ollama_llm)
    test_case = LLMTestCase(
        input=input_question,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
    )

    assert_test(test_case, [metric])


@pytest.mark.asyncio
async def test_answer_relevancy_evasive():
    """
    Test that an evasive or highly tangential answer fails the relevancy check.
    """
    input_question = "What is the threshold for rigid plastic?"
    actual_output = "Plastic waste management is very important for the environment and producers must recycle."
    retrieval_context = [
        "A variance of more than 5% (flexible or rigid plastic) is considered a material mismatch."
    ]

    ollama_llm = OllamaLLM(model_name="gpt-oss:20b-cloud")
    metric = AnswerRelevancyMetric(threshold=RELEVANCY_THRESHOLD, model=ollama_llm)
    test_case = LLMTestCase(
        input=input_question,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
    )

    try:
        assert_test(test_case, [metric])
        pytest.fail("Relevancy metric failed to catch an evasive answer.")
    except AssertionError:
        pass
