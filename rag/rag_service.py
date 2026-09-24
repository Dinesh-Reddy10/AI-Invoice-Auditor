import json
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from litellm import completion
# For basic local embeddings instead of relying on external API for embeddings if preferred, 
# but using a simple huggingface local embedding is better for a solo project to avoid extra costs.
from langchain_community.embeddings import HuggingFaceEmbeddings
from models.invoice_models import WorkflowState
from configs.settings import settings

class RAGService:
    def __init__(self):
        # Use a lightweight local embedding model to avoid needing another API key
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vectorstore = None

    def index_state(self, state: WorkflowState):
        """Indexes the invoice data into FAISS."""
        docs = []
        
        # 1. Extracted Invoice
        if state.extracted_invoice:
             invoice_text = f"INVOICE DATA:\nNumber: {state.extracted_invoice.invoice_number}\n"
             invoice_text += f"Date: {state.extracted_invoice.invoice_date}\n"
             invoice_text += f"Vendor: {state.extracted_invoice.vendor_name}\n"
             invoice_text += f"Total: {state.extracted_invoice.total_amount} {state.extracted_invoice.currency}\n"
             invoice_text += "Items:\n"
             for item in state.extracted_invoice.line_items:
                 invoice_text += f"- {item.description} (Qty: {item.quantity}, Price: {item.unit_price}, Total: {item.line_total})\n"
             docs.append(Document(page_content=invoice_text, metadata={"source": "extraction"}))
             
             if state.extracted_invoice.was_translated:
                 docs.append(Document(page_content=f"TRANSLATION INFO:\nLanguage: {state.extracted_invoice.detected_language}\nEngine: {state.extracted_invoice.translation_engine}", metadata={"source": "translation"}))

        # 2. Validation Result
        if state.validation_result:
             val_text = f"INVOICE VALIDATION:\nStatus: {state.validation_result.status}\n"
             if state.validation_result.missing_fields:
                  val_text += f"Missing: {', '.join(state.validation_result.missing_fields)}\n"
             if state.validation_result.calculation_errors:
                  val_text += f"Errors: {'; '.join(state.validation_result.calculation_errors)}\n"
             docs.append(Document(page_content=val_text, metadata={"source": "validation"}))
             
        # 3. ERP Result
        if state.erp_validation_result:
             erp_text = f"ERP VALIDATION:\nStatus: {state.erp_validation_result.status}\n"
             for d in state.erp_validation_result.discrepancies:
                 erp_text += f"Discrepancy: {d.type} on {d.field} (Invoice: {d.invoice_value} vs ERP: {d.erp_value})\n"
             docs.append(Document(page_content=erp_text, metadata={"source": "erp"}))
             
        # 4. Final Decision
        if state.final_decision:
             dec_text = f"FINAL DECISION:\n{state.final_decision.decision}\nReasoning: {state.final_decision.reasoning}"
             docs.append(Document(page_content=dec_text, metadata={"source": "decision"}))
             
        if not docs:
             return
             
        self.vectorstore = FAISS.from_documents(docs, self.embeddings)

    def ask_question(self, query: str) -> str:
        if not self.vectorstore:
            return "No invoice data has been indexed yet. Please process an invoice first."
            
        if not settings.openrouter_api_key:
            return "OpenRouter API Key is missing. Cannot perform Q&A."
            
        # Retrieve relevant chunks
        docs = self.vectorstore.similarity_search(query, k=3)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        prompt = f"""You are an AI assistant answering questions about an invoice auditing process.
Use the following pieces of retrieved context to answer the question. 
If you don't know the answer, just say that you don't know based on the context.

Context:
{context}

Question: {query}
Answer:"""

        try:
            response = completion(
                model=settings.openrouter_model if settings.openrouter_model.startswith("openrouter/") else f"openrouter/{settings.openrouter_model}",
                messages=[{"role": "user", "content": prompt}],
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error querying LLM: {str(e)}"
