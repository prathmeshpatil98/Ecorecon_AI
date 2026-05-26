"""
tests/integration/test_endpoints.py
===================================
Integration tests for the FastAPI endpoints.
Validates the determinism of the ingestion and reconciliation layers.
"""

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_submit_declaration_success(test_client: AsyncClient, mock_declaration_payload: dict):
    """
    Test that submitting a valid declaration persists correctly.
    """
    response = await test_client.post("/api/v1/submit", json=mock_declaration_payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["producer_id"] == mock_declaration_payload["producer_id"]
    assert data["month"] == mock_declaration_payload["month"]
    assert data["total_declared_kg"] == 1700.0  # 1000 + 500 + 200
    assert "record_id" in data


@pytest.mark.asyncio
async def test_submit_declaration_invalid_date(test_client: AsyncClient, mock_declaration_payload: dict):
    """
    Test that deterministic validation rejects bad date formats.
    """
    payload = mock_declaration_payload.copy()
    payload["month"] = "04-2026"  # Invalid format, expects YYYY-MM
    
    response = await test_client.post("/api/v1/submit", json=payload)
    # FastAPI Pydantic validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_summary_missing_declaration(test_client: AsyncClient):
    """
    Test that requesting a summary for a non-existent declaration returns 404.
    """
    response = await test_client.get("/api/v1/summary/UNKNOWN-PRODUCER/2026-04")
    assert response.status_code == 404
    
    data = response.json()
    assert data["error_code"] == "DECLARATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_summary_success_flow(test_client: AsyncClient, mock_declaration_payload: dict):
    """
    Test the full integration flow: Submit -> Summary.
    Uses GreenPack because the mock ERP CSV has data for GREENPACK-001.
    """
    # 1. Submit
    payload = mock_declaration_payload.copy()
    payload["producer_id"] = "GREENPACK-001"
    payload["month"] = "2026-04"
    
    submit_resp = await test_client.post("/api/v1/submit", json=payload)
    assert submit_resp.status_code == 201

    # 2. Reconcile
    summary_resp = await test_client.get("/api/v1/summary/GREENPACK-001/2026-04")
    assert summary_resp.status_code == 200
    
    data = summary_resp.json()
    assert "reconciliation" in data
    assert "narrative" in data
    assert "record_id" in data
    
    recon = data["reconciliation"]
    # The ERP mock CSV has 12000 rigid, 8500 flexible, 3200 multilayer.
    # Our mock payload has 1000 rigid, 500 flexible, 200 multilayer.
    # This will obviously trigger massive mismatches.
    assert recon["has_mismatch"] is True
    assert recon["overall_status"] == "mismatched"
    assert "rigid_plastic" in recon["flagged_categories"]
