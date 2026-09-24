import pytest
from services.validation_service import ValidationService
from models.invoice_models import ExtractedInvoice, LineItem
from configs.settings import settings

@pytest.fixture
def valid_invoice():
    return ExtractedInvoice(
        invoice_number="INV-100",
        invoice_date="2023-11-01",
        vendor_name="Acme Corp",
        currency="USD",
        subtotal=100.0,
        tax=10.0,
        total_amount=110.0,
        line_items=[
            LineItem(item_code="A", description="Item A", quantity=2.0, unit_price=50.0, line_total=100.0)
        ]
    )

def test_validation_pass(valid_invoice):
    service = ValidationService()
    result = service.validate_invoice(valid_invoice)
    assert result.status == "PASS"
    assert len(result.missing_fields) == 0
    assert len(result.calculation_errors) == 0

def test_validation_missing_fields(valid_invoice):
    valid_invoice.invoice_number = ""
    valid_invoice.vendor_name = "Unknown Vendor"
    
    service = ValidationService()
    result = service.validate_invoice(valid_invoice)
    
    assert result.status == "FAIL"
    assert "invoice_number" in result.missing_fields
    assert "vendor_name" in result.missing_fields

def test_validation_calculation_errors(valid_invoice):
    # Mess up line total
    valid_invoice.line_items[0].line_total = 90.0
    
    service = ValidationService()
    result = service.validate_invoice(valid_invoice)
    
    assert result.status == "FAIL"
    assert len(result.calculation_errors) > 0
    assert any("Line item" in e for e in result.calculation_errors)

def test_validation_currency_issue(valid_invoice):
    valid_invoice.currency = "XYZ" # Unsupported
    
    service = ValidationService()
    result = service.validate_invoice(valid_invoice)
    
    assert result.status == "WARNING"
    assert len(result.currency_issues) > 0
