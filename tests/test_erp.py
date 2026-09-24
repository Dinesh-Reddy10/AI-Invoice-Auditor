import pytest
from unittest.mock import patch, MagicMock
from services.erp_service import ERPService
from models.invoice_models import ExtractedInvoice, LineItem

@pytest.fixture
def mock_invoice():
    return ExtractedInvoice(
        invoice_number="INV-100",
        invoice_date="2023-11-01",
        vendor_name="Acme Corp",
        vendor_id="VEND001",
        po_number="PO-1001",
        currency="USD",
        subtotal=100.0,
        tax=0.0,
        total_amount=100.0,
        line_items=[
            LineItem(item_code="ITEM001", description="Widget", quantity=10, unit_price=10.0, line_total=100.0)
        ]
    )

@patch('requests.get')
def test_erp_validation_pass(mock_get, mock_invoice):
    # Mock PO response
    mock_po_response = MagicMock()
    mock_po_response.status_code = 200
    mock_po_response.json.return_value = {
        "po_number": "PO-1001",
        "vendor_id": "VEND001",
        "currency": "USD",
        "total_amount": 100.0,
        "items": [
            {"item_code": "ITEM001", "quantity": 10, "unit_price": 10.0}
        ]
    }
    
    # Mock Vendor response
    mock_vendor_response = MagicMock()
    mock_vendor_response.status_code = 200
    mock_vendor_response.json.return_value = {
        "vendor_id": "VEND001",
        "name": "Acme Corp"
    }

    # Sequence of returns for requests.get
    mock_get.side_effect = [mock_po_response, mock_vendor_response]

    service = ERPService()
    result = service.validate_against_erp(mock_invoice)

    assert result.status == "PASS"
    assert len(result.discrepancies) == 0

@patch('requests.get')
def test_erp_validation_price_mismatch(mock_get, mock_invoice):
    # Invoice has price 10.0, let's make ERP price 8.0
    mock_po_response = MagicMock()
    mock_po_response.status_code = 200
    mock_po_response.json.return_value = {
        "po_number": "PO-1001",
        "vendor_id": "VEND001",
        "currency": "USD",
        "total_amount": 80.0,
        "items": [
            {"item_code": "ITEM001", "quantity": 10, "unit_price": 8.0} # Mismatch
        ]
    }
    
    mock_vendor_response = MagicMock()
    mock_vendor_response.status_code = 200
    mock_vendor_response.json.return_value = {"vendor_id": "VEND001", "name": "Acme Corp"}

    mock_get.side_effect = [mock_po_response, mock_vendor_response]

    service = ERPService()
    result = service.validate_against_erp(mock_invoice)

    assert result.status == "FAIL"
    
    types = [d.type for d in result.discrepancies]
    assert "price_mismatch" in types
    assert "total_mismatch" in types
