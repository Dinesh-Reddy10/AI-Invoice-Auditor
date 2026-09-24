from models.invoice_models import ExtractedInvoice, ValidationResult
from configs.settings import settings

class ValidationService:
    def validate_invoice(self, invoice: ExtractedInvoice) -> ValidationResult:
        missing_fields = []
        calculation_errors = []
        currency_issues = []
        status = "PASS"
        
        # 1. Check required fields
        if not invoice.invoice_number or invoice.invoice_number == "INV-000":
            missing_fields.append("invoice_number")
        if not invoice.invoice_date or invoice.invoice_date == "2000-01-01":
            missing_fields.append("invoice_date")
        if not invoice.vendor_name or invoice.vendor_name == "Unknown Vendor":
            missing_fields.append("vendor_name")
            
        # 2. Check calculations
        calculated_subtotal = 0.0
        for item in invoice.line_items:
            expected_total = item.quantity * item.unit_price
            
            # Allow tolerance
            diff = abs(expected_total - item.line_total)
            if diff > 0.01 and (diff / max(expected_total, 1)) * 100 > settings.tolerance_percent:
                calculation_errors.append(f"Line item {item.item_code} total mismatch: {item.quantity} * {item.unit_price} != {item.line_total}")
                
            calculated_subtotal += item.line_total
            
        diff_sub = abs(calculated_subtotal - invoice.subtotal)
        if diff_sub > 0.01 and (diff_sub / max(calculated_subtotal, 1)) * 100 > settings.tolerance_percent:
            calculation_errors.append(f"Subtotal mismatch: Sum of lines {calculated_subtotal} != {invoice.subtotal}")
            
        expected_total_amount = invoice.subtotal + invoice.tax
        diff_tot = abs(expected_total_amount - invoice.total_amount)
        if diff_tot > 0.01 and (diff_tot / max(expected_total_amount, 1)) * 100 > settings.tolerance_percent:
             calculation_errors.append(f"Total mismatch: Subtotal + Tax ({expected_total_amount}) != {invoice.total_amount}")

        # 3. Currency check
        if invoice.currency not in settings.accepted_currencies:
            currency_issues.append(f"Unsupported currency: {invoice.currency}")
            
        # Determine status
        if missing_fields or calculation_errors:
            status = "FAIL"
        elif currency_issues:
            status = "WARNING"
            
        # Calculate a basic score 
        score = 1.0
        if status == "FAIL":
            score = 0.0
        elif status == "WARNING":
            score = 0.5
            
        return ValidationResult(
            status=status,
            missing_fields=missing_fields,
            calculation_errors=calculation_errors,
            currency_issues=currency_issues,
            overall_score=score
        )
