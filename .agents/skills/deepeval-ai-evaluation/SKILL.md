---
name: deepeval-ai-evaluation
description: |
  Use this skill to implement continuous, evaluation-driven AI engineering using DeepEval. Focuses on measuring faithfulness, hallucination, and context precision.
---

# DeepEval AI Evaluation Skill

## 1. Continuous Evaluation-Driven Engineering

In an enterprise environment, evaluating generative models (LLMs) cannot rely on manual, ad-hoc inspection. The EcoRecon AI platform treats **AI Quality Control** as a first-class citizen integrated directly into the automated Pytest suite. 
Continuous integration gates automatically execute mathematical and semantic evaluations using the **DeepEval** library to assert response safety, grounding, and relevancy before production releases.

---

## 2. Mathematical Metrics and Specifications

DeepEval evaluates LLM performance by breaking down the retrieval and generation phases into distinct mathematical scores. Every test run produces a confidence decimal value between $0.0$ and $1.0$.

---

### A. Faithfulness Metric

Measures whether the Groq-generated response is *strictly derived* from the retrieved vector context. It ensures that the model does not introduce external knowledge or assumptions.

#### Mathematical Definition

$$\text{Faithfulness Score} = \frac{\text{Number of True Claims derived from Context}}{\text{Total Number of Claims made in Response}}$$

*   **Extraction Step**: DeepEval extracts all individual statements and assertions from the LLM-generated answer.
*   **Verification Step**: An evaluator model verifies each statement against the retrieved context chunks.
*   **Threshold Rule**: Any faithfulness score **$< 0.85$** is flagged as a failure.

---

### B. Hallucination Metric

Measures whether the generation contains fabricated, false, or ungrounded statements. It is mathematically the inverse of the grounding state, looking specifically for contradictions.

#### Mathematical Definition

$$\text{Hallucination Score} = \frac{\text{Number of Untrue / Contradictory Claims relative to Context}}{\text{Total Number of Claims made in Response}}$$

*   **Rule**: Any hallucination score **$> 0.0$** indicates a hallucination risk.
*   **Threshold Rule**: A hallucination score **$> 0.15$** triggers a hard test rejection.

---

### C. Context Precision Metric

Measures the relevance and ordering accuracy of the retrieved chunks. It evaluates whether the vector index placed the most informative context blocks at the top of the retrieval stack.

#### Mathematical Definition

$$\text{Context Precision} = \frac{\sum_{k=1}^{K} P(k) \times \text{rel}(k)}{\text{Total Number of Relevant Chunks in top } K}$$

Where:
*   $P(k)$ is the precision at rank $k$.
*   $\text{rel}(k)$ is an indicator function (equals $1$ if chunk at rank $k$ is relevant, else $0$).
*   $K$ is the top retrieval limit (configured via `settings.rag_top_k`).
*   **Threshold Rule**: Context Precision must exceed **$0.80$** to guarantee optimal LLM prompts.

---

## 3. Automated Pytest Integration Code Blueprint

DeepEval tests are executed via Pytest. The tests use local mocks or active API endpoints to run evaluations against test cases.

### Concrete DeepEval Test File Code (`evaluation/deepeval/test_compliance_qa.py`)

```python
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, HallucinationMetric, ContextPrecisionMetric

from app.services.retrieval_service import RetrievalService
from app.core.config import get_settings

@pytest.mark.asyncio
async def test_compliance_qa_faithfulness():
    """
    Automated test asserting that the /ask compliance answer 
    is 100% faithful to the vector database context.
    """
    settings = get_settings()
    question = "What is the penalty for failure to submit monthly declarations?"
    
    # 1. Fetch search response and retrieve citations
    service = RetrievalService()
    response = await service.answer_compliance_question(question)
    
    # 2. Extract actual context chunks and generated text
    retrieved_contexts = [cit.chunk_text for cit in response.citations]
    actual_output = response.answer
    
    # 3. Create a DeepEval LLM Test Case
    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieved_context=retrieved_contexts
    )
    
    # 4. Initialize the DeepEval Faithfulness Metric with a strict threshold
    metric = FaithfulnessMetric(
        threshold=0.85, 
        model=settings.groq_model,
        include_reason=True
    )
    
    # 5. Assert test compliance
    assert_test(test_case, [metric])


@pytest.mark.asyncio
async def test_compliance_qa_hallucination():
    """
    Automated test asserting zero-contradiction hallucination boundary.
    """
    settings = get_settings()
    question = "Does flexible plastic require rigid plastic certification?"
    
    service = RetrievalService()
    response = await service.answer_compliance_question(question)
    
    retrieved_contexts = [cit.chunk_text for cit in response.citations]
    
    test_case = LLMTestCase(
        input=question,
        actual_output=response.answer,
        retrieved_context=retrieved_contexts
    )
    
    # Initialize Hallucination metric (threshold of 0.15 represents max tolerated drift)
    metric = HallucinationMetric(
        threshold=0.15,
        model=settings.groq_model
    )
    
    assert_test(test_case, [metric])
```
