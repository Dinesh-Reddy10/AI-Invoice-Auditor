import pytest
import os
from unittest.mock import patch, MagicMock
from workflow.invoice_workflow import InvoiceWorkflow
from models.invoice_models import ExtractedInvoice, LineItem, ERPValidationResult, ValidationResult

@patch('services.extraction_service.ExtractionService.extract_from_file')
@patch('services.translation_service.TranslationService.translate_invoice')
@patch('services.erp_service.ERPService.validate_against_erp')
def test_workflow_end_to_end(mock_erp, mock_translate, mock_extract):
    # Setup Mocks
    mock_extract.return_value = (
        "raw text", 
        ExtractedInvoice(
            invoice_number="INV-100",
            invoice_date="2023-01-01",
            vendor_name="Test Vendor",
            po_number="PO-1001",
            currency="USD",
            subtotal=100.0,
            tax=0.0,
            total_amount=100.0,
            line_items=[LineItem(item_code="ITEM1", description="Desc", quantity=10, unit_price=10.0, line_total=100.0)]
        )
    )
    
    # Translate just returns the invoice as is
    mock_translate.side_effect = lambda text, inv: inv
    
    # ERP returns PASS
    mock_erp.return_value = ERPValidationResult(status="PASS", discrepancies=[])

    workflow = InvoiceWorkflow()
    
    # Run
    state = workflow.run("dummy.pdf")
    
    assert state.error is None
    assert state.validation_result.status == "PASS"
    assert state.erp_validation_result.status == "PASS"
    assert state.final_decision.decision == "APPROVE"
    assert os.path.exists(state.report_path)
    
    # cleanup report
    if os.path.exists(state.report_path):
        os.remove(state.report_path)

@patch('services.extraction_service.ExtractionService.extract_from_file')
@patch('services.erp_service.ERPService.validate_against_erp')
def test_workflow_rejection(mock_erp, mock_extract):
    # Setup Mocks with bad calculation
    mock_extract.return_value = (
        "raw text", 
        ExtractedInvoice(
            invoice_number="INV-100",
            invoice_date="2023-01-01",
            vendor_name="Test Vendor",
            po_number="PO-1001",
            currency="USD",
            subtotal=100.0,
            tax=0.0,
            total_amount=999.0, # Bad total
            line_items=[LineItem(item_code="ITEM1", description="Desc", quantity=10, unit_price=10.0, line_total=100.0)]
        )
    )
    
    mock_erp.return_value = ERPValidationResult(status="PASS", discrepancies=[])

    workflow = InvoiceWorkflow()
    state = workflow.run("dummy.pdf")
    
    assert state.error is None
    assert state.validation_result.status == "FAIL"
    assert state.final_decision.decision == "REJECT"
    
    if os.path.exists(state.report_path):
        os.remove(state.report_path)
