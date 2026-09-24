import pytest
from services.translation_service import TranslationService
from models.invoice_models import ExtractedInvoice, LineItem

@pytest.fixture
def mock_invoice():
    return ExtractedInvoice(
        invoice_number="123",
        invoice_date="2023-01-01",
        vendor_name="एकमे कॉर्प", # Acme Corp in Hindi
        currency="USD",
        subtotal=100.0,
        tax=0.0,
        total_amount=100.0,
        line_items=[
            LineItem(item_code="ITM1", description="कंप्यूटर", quantity=1, unit_price=100.0, line_total=100.0)
        ]
    )

def test_translation_english_skipped(mock_invoice):
    service = TranslationService()
    mock_invoice.vendor_name = "Acme Corp"
    
    # Force language detect to English by passing english text
    result = service.translate_invoice("This is an english invoice", mock_invoice)
    
    assert result.detected_language == "en"
    assert result.was_translated == False
    assert result.vendor_name == "Acme Corp"

def test_translation_unsupported_language(mock_invoice, monkeypatch):
    service = TranslationService()
    
    # Mock langdetect to return 'fr' (French), which is not in our specific supported list (hi, te, ta, kn)
    monkeypatch.setattr("langdetect.detect", lambda text: "fr")
    
    result = service.translate_invoice("Bonjour le monde", mock_invoice)
    
    assert result.detected_language == "fr"
    assert result.was_translated == False
    assert result.translation_engine == "UNSUPPORTED"
