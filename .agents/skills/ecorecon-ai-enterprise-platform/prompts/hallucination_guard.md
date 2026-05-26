# Hallucination Guard

Evaluate the following generated answer against the retrieved context.

If the answer contains any claims not present in the context, output: HALLUCINATION_DETECTED.
Otherwise, output: GROUNDED.