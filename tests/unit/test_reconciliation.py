"""
tests/unit/test_reconciliation.py
=================================
Unit tests for deterministic reconciliation math.
Ensures that variances and thresholds are calculated precisely.
"""

import pytest

from app.schemas.erp_schema import ERPProcurementSnapshot, ERPRecord
from app.schemas.summary_schema import ReconciliationStatus
from app.services.reconciliation_service import ReconciliationService


@pytest.fixture
def reconciliation_service():
    # Use a dummy repo and ERP service since we are testing the private math directly
    return ReconciliationService(repository=None, erp_service=None, threshold_pct=5.0)


def test_reconcile_category_exact_match(reconciliation_service):
    """Test math when declared exactly matches procured."""
    result = reconciliation_service._reconcile_category("rigid_plastic", 1000.0, 1000.0, 5.0)
    assert result.declared_kg == 1000.0
    assert result.procured_kg == 1000.0
    assert result.variance_kg == 0.0
    assert result.deviation_pct == 0.0
    assert result.is_flagged is False


def test_reconcile_category_under_threshold(reconciliation_service):
    """Test math when mismatch is under the 5% threshold."""
    result = reconciliation_service._reconcile_category("rigid_plastic", 1000.0, 1040.0, 5.0)
    assert result.variance_kg == -40.0
    assert result.deviation_pct == 4.0
    assert result.is_flagged is False


def test_reconcile_category_over_threshold(reconciliation_service):
    """Test math when mismatch exceeds the 5% threshold."""
    result = reconciliation_service._reconcile_category("flexible_plastic", 1000.0, 1060.0, 5.0)
    assert result.variance_kg == -60.0
    assert result.deviation_pct == 6.0
    assert result.is_flagged is True


def test_reconcile_category_zero_division(reconciliation_service):
    """Test math when procured is zero but declared is positive."""
    result = reconciliation_service._reconcile_category("multilayer_plastic", 500.0, 0.0, 5.0)
    assert result.variance_kg == 500.0
    # Expected behavior for zero division in our logic is 100% mismatch
    assert result.deviation_pct == 100.0
    assert result.is_flagged is True

