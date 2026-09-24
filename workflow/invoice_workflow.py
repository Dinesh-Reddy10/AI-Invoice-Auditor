import json
import os
from datetime import datetime
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from litellm import completion

from models.invoice_models import WorkflowState, FinalDecision
from services.extraction_service import ExtractionService
from services.validation_service import ValidationService
from services.erp_service import ERPService
from configs.settings import settings

class InvoiceWorkflow:
    def __init__(self):
        self.extraction_service = ExtractionService()
        self.validation_service = ValidationService()
        self.erp_service = ERPService()
        
        # Build LangGraph
        workflow = StateGraph(WorkflowState)
        
        workflow.add_node("extract", self.extract_node)
        workflow.add_node("validate", self.validate_node)
        workflow.add_node("erp_validate", self.erp_validate_node)
        workflow.add_node("agentic_decision", self.agentic_decision_node)
        workflow.add_node("report", self.report_node)
        
        workflow.set_entry_point("extract")
        
        workflow.add_edge("extract", "validate")
        workflow.add_edge("validate", "erp_validate")
        workflow.add_edge("erp_validate", "agentic_decision")
        workflow.add_edge("agentic_decision", "report")
        workflow.add_edge("report", END)
        
        self.app = workflow.compile()

    def extract_node(self, state: WorkflowState) -> Dict[str, Any]:
        try:
            raw_text, invoice = self.extraction_service.extract_from_file(state.file_path)
            return {"raw_text": raw_text, "extracted_invoice": invoice}
        except Exception as e:
            return {"error": f"Extraction failed: {str(e)}"}

    def validate_node(self, state: WorkflowState) -> Dict[str, Any]:
        if state.error or not state.extracted_invoice: return {}
        try:
            val_result = self.validation_service.validate_invoice(state.extracted_invoice)
            return {"validation_result": val_result}
        except Exception as e:
            return {"error": f"Validation failed: {str(e)}"}

    def erp_validate_node(self, state: WorkflowState) -> Dict[str, Any]:
        if state.error or not state.extracted_invoice: return {}
        try:
            erp_result = self.erp_service.validate_against_erp(state.extracted_invoice)
            return {"erp_validation_result": erp_result}
        except Exception as e:
            return {"error": f"ERP Validation failed: {str(e)}"}

    def agentic_decision_node(self, state: WorkflowState) -> Dict[str, Any]:
        if state.error: return {}
        
        # Base deterministic decision logic
        decision = "MANUAL_REVIEW"
        val_status = state.validation_result.status if state.validation_result else "FAIL"
        erp_status = state.erp_validation_result.status if state.erp_validation_result else "FAIL"
        
        if val_status == "PASS" and erp_status == "PASS":
            decision = "APPROVE"
        elif val_status == "FAIL" or erp_status == "FAIL":
            decision = "REJECT"
            
        # Use LLM to generate human-readable reasoning based on the deterministic results
        reasoning = f"Determined automatically. Validation: {val_status}. ERP: {erp_status}."
        
        if settings.openrouter_api_key:
            prompt = f"""You are a senior invoice auditor. Based on the following deterministic rules, explain why this invoice is marked as {decision}. Do not contradict the {decision} decision.
            
            Invoice Validation Status: {val_status}
            Missing Fields: {state.validation_result.missing_fields if state.validation_result else []}
            Calculation Errors: {state.validation_result.calculation_errors if state.validation_result else []}
            
            ERP Validation Status: {erp_status}
            Discrepancies: {[d.dict() for d in state.erp_validation_result.discrepancies] if state.erp_validation_result else []}
            
            Write a 2-3 sentence professional explanation."""
            
            try:
                response = completion(
                    model=settings.openrouter_model if settings.openrouter_model.startswith("openrouter/") else f"openrouter/{settings.openrouter_model}",
                    messages=[{"role": "user", "content": prompt}],
                    api_key=settings.openrouter_api_key,
                    base_url="https://openrouter.ai/api/v1",
                    temperature=0.1
                )
                reasoning = response.choices[0].message.content.strip()
            except Exception as e:
                pass # Fallback to deterministic reasoning
                
        return {"final_decision": FinalDecision(decision=decision, reasoning=reasoning)}

    def report_node(self, state: WorkflowState) -> Dict[str, Any]:
        if state.error: return {}
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "invoice": state.extracted_invoice.dict() if state.extracted_invoice else None,
            "validation": state.validation_result.dict() if state.validation_result else None,
            "erp_validation": state.erp_validation_result.dict() if state.erp_validation_result else None,
            "decision": state.final_decision.dict() if state.final_decision else None
        }
        
        os.makedirs("reports", exist_ok=True)
        filename = f"reports/validation_report_{state.extracted_invoice.invoice_number if state.extracted_invoice else 'error'}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=4)
            
        return {"report_path": filename}

    def run(self, file_path: str) -> WorkflowState:
        initial_state = WorkflowState(file_path=file_path)
        result = self.app.invoke(initial_state.dict())
        return WorkflowState(**result)
