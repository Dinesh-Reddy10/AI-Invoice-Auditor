from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    item_code: Optional[str] = Field(None, description="Unique identifier for the item")
    description: str = Field(..., description="Description of the item")
    quantity: float = Field(..., description="Quantity of the item")
    unit_price: float = Field(..., description="Price per unit")
    line_total: float = Field(..., description="Total price for this line (quantity * unit_price)")


class ExtractedInvoice(BaseModel):
    invoice_number: str = Field(..., description="Unique invoice identifier")
    invoice_date: str = Field(..., description="Date of the invoice")
    vendor_id: Optional[str] = Field(None, description="Vendor ID if available")
    vendor_name: str = Field(..., description="Name of the vendor")
    po_number: Optional[str] = Field(None, description="Purchase Order number")
    currency: str = Field(..., description="Currency code (e.g., USD, INR)")
    subtotal: float = Field(..., description="Total before tax")
    tax: float = Field(..., description="Tax amount")
    total_amount: float = Field(..., description="Final total amount including tax")
    line_items: List[LineItem] = Field(default_factory=list, description="List of items in the invoice")

    # Translation metadata
    translation_confidence: Optional[float] = None


class ValidationResult(BaseModel):
    status: Literal["PASS", "WARNING", "FAIL"]
    missing_fields: List[str] = Field(default_factory=list)
    calculation_errors: List[str] = Field(default_factory=list)
    currency_issues: List[str] = Field(default_factory=list)
    overall_score: float = 1.0


class Discrepancy(BaseModel):
    type: str
    field: str
    item_code: Optional[str] = None
    invoice_value: str | float | None = None
    erp_value: str | float | None = None


class ERPValidationResult(BaseModel):
    status: Literal["PASS", "WARNING", "FAIL", "SKIPPED"]
    discrepancies: List[Discrepancy] = Field(default_factory=list)


class FinalDecision(BaseModel):
    decision: Literal["APPROVE", "MANUAL_REVIEW", "REJECT"]
    reasoning: str


# LangGraph State
class WorkflowState(BaseModel):
    file_path: str
    raw_text: str = ""
    extracted_invoice: Optional[ExtractedInvoice] = None
    validation_result: Optional[ValidationResult] = None
    erp_validation_result: Optional[ERPValidationResult] = None
    final_decision: Optional[FinalDecision] = None
    report_path: Optional[str] = None
    error: Optional[str] = None
