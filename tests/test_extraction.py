import pytest
from services.extraction_service import ExtractionService
from models.invoice_models import LineItem

def test_parse_text_to_invoice():
    service = ExtractionService()
    sample_text = """
    INVOICE NUMBER: INV-2023-001
    Date: 2023-10-25
    Vendor ID: VEND001
    Acme Corp
    PO Number: PO-1001
    
    ItemCode Description Qty UnitPrice Total
    ITEM001 Widget A 10 100.00 1000.00
    ITEM002 Widget B 5 50.00 250.00
    
    Subtotal 1250.00
    Tax 125.00
    Total 1375.00
    USD
    """
    
    invoice = service._parse_text_to_invoice(sample_text)
    
    assert invoice.invoice_number == "INV-2023-001"
    assert invoice.invoice_date == "2023-10-25"
    assert invoice.vendor_id == "VEND001"
    assert invoice.po_number == "PO-1001"
    assert invoice.subtotal == 1250.00
    assert invoice.tax == 125.00
    assert invoice.total_amount == 1375.00
    assert invoice.currency == "USD"
    
    assert len(invoice.line_items) == 2
    assert invoice.line_items[0].item_code == "ITEM001"
    assert invoice.line_items[0].quantity == 10.0
    assert invoice.line_items[0].line_total == 1000.0

def test_parse_empty_text():
    service = ExtractionService()
    invoice = service._parse_text_to_invoice("")
    
    # Check defaults
    assert invoice.invoice_number == "INV-000"
    assert invoice.subtotal == 0.0
    assert len(invoice.line_items) == 0
