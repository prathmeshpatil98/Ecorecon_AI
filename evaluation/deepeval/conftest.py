"""
evaluation/deepeval/conftest.py
===============================
DeepEval configuration using Ollama instead of OpenAI.
"""

import os
from langchain_ollama import ChatOllama
from deepeval.models import DeepEvalBaseLLM


class OllamaLLM(DeepEvalBaseLLM):
    """
    Custom DeepEval LLM wrapper for Ollama.
    Allows DeepEval metrics to use local Ollama models instead of OpenAI.
    """

    def __init__(self, model_name: str = "gpt-oss:20b-cloud", base_url: str = "http://localhost:11434"):
        """
        Args:
            model_name: Ollama model identifier (e.g., 'mistral', 'neural-chat')
            base_url: Ollama API base URL
        """
        self.model_name = model_name
        self.ollama_client = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
        )

    def load_model(self):
        """Load the Ollama model."""
        return self.ollama_client

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using Ollama.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
        """
        try:
            # Try known client interfaces in order of likelihood
            if hasattr(self.ollama_client, "invoke"):
                resp = self.ollama_client.invoke(prompt)
            elif hasattr(self.ollama_client, "generate"):
                resp = self.ollama_client.generate(prompt)
            else:
                # Fallback: call the client if it's callable
                resp = self.ollama_client(prompt)

            # Some clients return objects with a `content` or `text` attribute
            if hasattr(resp, "content"):
                out = resp.content
            elif hasattr(resp, "text"):
                out = resp.text
            else:
                out = resp

            return str(out).strip()
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {e}")

    async def a_generate(self, prompt: str, **kwargs) -> str:
        """
        Async generate text using Ollama.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
        """
        # Ollama doesn't have native async, so we'll use sync in executor
        loop = __import__('asyncio').get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.generate, 
            prompt
        )

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model_name
