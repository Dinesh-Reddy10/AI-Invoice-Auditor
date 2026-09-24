import requests
from models.invoice_models import ExtractedInvoice, ERPValidationResult, Discrepancy
from configs.settings import settings

class ERPService:
    def validate_against_erp(self, invoice: ExtractedInvoice) -> ERPValidationResult:
        discrepancies = []
        status = "PASS"
        
        if not invoice.po_number:
            return ERPValidationResult(status="SKIPPED", discrepancies=[Discrepancy(type="missing_data", field="po_number")])
            
        try:
            # Fetch PO Data
            po_response = requests.get(f"{settings.erp_api_base_url}/po/{invoice.po_number}")
            if po_response.status_code != 200:
                return ERPValidationResult(status="FAIL", discrepancies=[Discrepancy(type="po_not_found", field="po_number", invoice_value=invoice.po_number)])
                
            po_data = po_response.json()
            
            # Fetch Vendor Data
            vendor_response = requests.get(f"{settings.erp_api_base_url}/vendor/{po_data['vendor_id']}")
            vendor_data = vendor_response.json() if vendor_response.status_code == 200 else {}
            
            # Compare Vendor Name (Fuzzy/basic check)
            if invoice.vendor_id and invoice.vendor_id != po_data['vendor_id']:
                 discrepancies.append(Discrepancy(type="vendor_mismatch", field="vendor_id", invoice_value=invoice.vendor_id, erp_value=po_data['vendor_id']))
                 
            # Compare Currency
            if invoice.currency != po_data['currency']:
                discrepancies.append(Discrepancy(type="currency_mismatch", field="currency", invoice_value=invoice.currency, erp_value=po_data['currency']))
                
            # Compare Total Amount
            erp_total = po_data['total_amount']
            diff = abs(invoice.total_amount - erp_total)
            if diff > 0.01 and (diff / max(erp_total, 1)) * 100 > settings.tolerance_percent:
                discrepancies.append(Discrepancy(type="total_mismatch", field="total_amount", invoice_value=invoice.total_amount, erp_value=erp_total))
                
            # Compare Line Items
            erp_items = {item['item_code']: item for item in po_data['items']}
            for invoice_item in invoice.line_items:
                if not invoice_item.item_code:
                    continue
                    
                if invoice_item.item_code not in erp_items:
                    discrepancies.append(Discrepancy(type="item_not_in_po", field="item_code", item_code=invoice_item.item_code))
                    continue
                    
                erp_item = erp_items[invoice_item.item_code]
                
                # Qty Match
                if invoice_item.quantity != erp_item['quantity']:
                     discrepancies.append(Discrepancy(type="quantity_mismatch", field="quantity", item_code=invoice_item.item_code, invoice_value=invoice_item.quantity, erp_value=erp_item['quantity']))
                     
                # Price Match
                if invoice_item.unit_price != erp_item['unit_price']:
                     p_diff = abs(invoice_item.unit_price - erp_item['unit_price'])
                     if p_diff > 0.01 and (p_diff / max(erp_item['unit_price'], 1)) * 100 > settings.tolerance_percent:
                         discrepancies.append(Discrepancy(type="price_mismatch", field="unit_price", item_code=invoice_item.item_code, invoice_value=invoice_item.unit_price, erp_value=erp_item['unit_price']))

            if discrepancies:
                status = "FAIL"
                
        except requests.exceptions.RequestException as e:
            return ERPValidationResult(status="SKIPPED", discrepancies=[Discrepancy(type="api_error", field="erp_connection", invoice_value=str(e))])

        return ERPValidationResult(status=status, discrepancies=discrepancies)
