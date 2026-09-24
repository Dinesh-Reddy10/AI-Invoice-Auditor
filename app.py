import streamlit as st
import os
import json
import time
from workflow.invoice_workflow import InvoiceWorkflow
from rag.rag_service import RAGService
from configs.settings import settings

# Initialize services
@st.cache_resource
def get_services():
    return InvoiceWorkflow(), RAGService()

workflow_service, rag_service = get_services()

st.set_page_config(page_title="AI Invoice Auditor", layout="wide", page_icon="🧾")

st.title("🧾 AI Invoice Auditor")
st.markdown("Automated Invoice Processing & Auditing Pipeline")

# Basic sanity check
if not settings.openrouter_api_key:
    st.warning("⚠️ OpenRouter API Key is missing. Please add it to your `.env` file to enable LLM reasoning and Q&A features. Deterministic processing will still work.")

# Session state
if 'processed_state' not in st.session_state:
    st.session_state.processed_state = None
    
# --- UI Sections ---

with st.sidebar:
    st.header("Upload Invoice")
    uploaded_file = st.file_uploader("Choose a PDF or Image (PNG/JPG)", type=["pdf", "png", "jpg", "jpeg"])
    
    if uploaded_file is not None:
        if st.button("Analyze Invoice"):
            # Save file temporarily
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            with st.spinner("Processing invoice through LangGraph..."):
                start_time = time.time()
                # Run Workflow
                state = workflow_service.run(temp_path)
                
                # Index in FAISS
                if not state.error:
                     rag_service.index_state(state)
                     
                st.session_state.processed_state = state
                st.success(f"Processing complete in {time.time() - start_time:.2f}s!")
                
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

if st.session_state.processed_state:
    state = st.session_state.processed_state
    
    if state.error:
        st.error(f"Workflow Error: {state.error}")
    else:
        # Layout columns
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.header("1. Extraction & Translation")
            inv = state.extracted_invoice
            st.json({
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date,
                "vendor_name": inv.vendor_name,
                "po_number": inv.po_number,
                "currency": inv.currency,
                "subtotal": inv.subtotal,
                "tax": inv.tax,
                "total_amount": inv.total_amount,
                "detected_language": inv.detected_language,
                "was_translated": inv.was_translated,
                "translation_engine": inv.translation_engine
            })
            
            st.subheader("Line Items")
            st.dataframe([item.dict() for item in inv.line_items], use_container_width=True)

        with col2:
            st.header("2. Validation Results")
            val = state.validation_result
            
            if val.status == "PASS":
                st.success("✅ Invoice Data Validation: PASS")
            elif val.status == "WARNING":
                st.warning("⚠️ Invoice Data Validation: WARNING")
            else:
                st.error("❌ Invoice Data Validation: FAIL")
                
            if val.missing_fields: st.write("**Missing Fields:**", ", ".join(val.missing_fields))
            if val.calculation_errors: 
                for err in val.calculation_errors: st.write(f"- {err}")
            if val.currency_issues:
                for issue in val.currency_issues: st.write(f"- {issue}")

            st.header("3. Mock ERP Validation")
            erp = state.erp_validation_result
            if erp.status == "PASS":
                st.success("✅ ERP Validation: PASS")
            elif erp.status == "SKIPPED":
                st.info("ℹ️ ERP Validation: SKIPPED (No PO or API unavailable)")
            else:
                st.error("❌ ERP Validation: FAIL")
                
            if erp.discrepancies:
                st.write("**Discrepancies found:**")
                st.dataframe([d.dict() for d in erp.discrepancies], use_container_width=True)

        st.divider()
        
        # Decision Section
        st.header("4. Final Agentic Decision")
        decision = state.final_decision
        
        if decision.decision == "APPROVE":
            st.success(f"### {decision.decision}")
        elif decision.decision == "MANUAL_REVIEW":
            st.warning(f"### {decision.decision}")
        else:
            st.error(f"### {decision.decision}")
            
        st.info(f"**Reasoning:** {decision.reasoning}")
        
        # Report
        if state.report_path and os.path.exists(state.report_path):
             with open(state.report_path, "r", encoding="utf-8") as f:
                 report_json = f.read()
             st.download_button("Download JSON Report", data=report_json, file_name=os.path.basename(state.report_path), mime="application/json")

        st.divider()
        
        # QA Section
        st.header("5. Invoice Q&A (RAG)")
        st.markdown("Ask questions about this specific invoice and its validation results.")
        
        user_q = st.text_input("Ask a question...")
        if st.button("Ask"):
            if user_q:
                with st.spinner("Searching FAISS and querying LLM..."):
                    answer = rag_service.ask_question(user_q)
                    st.write(f"**Answer:** {answer}")
