"""
frontend/utils/api_client.py
=============================
Enterprise HTTP API client wrapping connections to the FastAPI backend.
"""

import requests
from typing import Dict, Any, Tuple, Optional

class APIClient:
    """
    Client for interacting with the EcoRecon FastAPI backend service.
    Handles network safety, exceptions, and validation message mapping.
    """

    def __init__(self, base_url: Optional[str] = None):
        import os
        if base_url is None:
            base_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000/api/v1")
        self.base_url = base_url

    def check_connection(self) -> bool:
        """Verify if the backend FastAPI service is reachable."""
        try:
            # Check OpenAPI docs endpoint (base server URL)
            health_url = self.base_url.replace("/api/v1", "/docs")
            resp = requests.get(health_url, timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def submit_declaration(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        POST /submit
        Submits monthly declaration data.
        Returns: Tuple of (status_code, json_response)
        """
        url = f"{self.base_url}/submit"
        try:
            resp = requests.post(url, json=payload, timeout=8.0)
            return resp.status_code, resp.json()
        except requests.exceptions.Timeout:
            return 504, {"message": "Request timed out. The database may be locked."}
        except Exception as e:
            return 500, {"message": f"Connection error: {str(e)}"}

    def get_reconciliation_summary(self, producer_id: str, month: str) -> Tuple[int, Dict[str, Any]]:
        """
        GET /summary/{producer_id}/{month}
        Executes deterministic reconciliation math and returns summaries.
        Returns: Tuple of (status_code, json_response)
        """
        url = f"{self.base_url}/summary/{producer_id}/{month}"
        try:
            resp = requests.get(url, timeout=12.0)
            return resp.status_code, resp.json()
        except requests.exceptions.Timeout:
            return 504, {"message": "Reconciliation engine execution timed out."}
        except Exception as e:
            return 500, {"message": f"Connection error: {str(e)}"}

    def ask_policy_question(self, question: str) -> Tuple[int, Dict[str, Any]]:
        """
        POST /ask
        Queries RAG policy indexes and checks hallucination-safety.
        Returns: Tuple of (status_code, json_response)
        """
        url = f"{self.base_url}/ask"
        try:
            resp = requests.post(url, json={"question": question}, timeout=15.0)
            return resp.status_code, resp.json()
        except requests.exceptions.Timeout:
            return 504, {"message": "Vector index semantic retrieval timed out."}
        except Exception as e:
            return 500, {"message": f"Connection error: {str(e)}"}
