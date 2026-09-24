import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM Settings
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "google/gemma-3-4b-it")
    
    # Mock ERP
    erp_api_base_url: str = os.getenv("ERP_API_BASE_URL", "http://localhost:8000")
    
    # Validation Rules
    tolerance_percent: float = 5.0 # 5% tolerance for calculations
    accepted_currencies: list[str] = ["USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD"]

    # RAG Settings
    faiss_index_path: str = "faiss_index"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
