import os
import langdetect
from transformers import MarianMTModel, MarianTokenizer
from litellm import completion
from models.invoice_models import ExtractedInvoice
from configs.settings import settings

class TranslationService:
    def __init__(self):
        # Supported languages and their MarianMT model names (Helsinki-NLP)
        self.supported_languages = {
            "hi": "Helsinki-NLP/opus-mt-hi-en",
            "te": "Helsinki-NLP/opus-mt-te-en",
            "ta": "Helsinki-NLP/opus-mt-ta-en", # Note: ta-en might need fallback depending on availability, but exists in opus-mt
            "kn": "Helsinki-NLP/opus-mt-kn-en"  # Note: kn-en might not exist directly, will rely on fallback if it fails
        }
        self.models = {}
        self.tokenizers = {}

    def _get_model_and_tokenizer(self, lang_code: str):
        if lang_code not in self.supported_languages:
            return None, None
            
        model_name = self.supported_languages[lang_code]
        
        if lang_code not in self.models:
            try:
                self.tokenizers[lang_code] = MarianTokenizer.from_pretrained(model_name)
                self.models[lang_code] = MarianMTModel.from_pretrained(model_name)
            except Exception as e:
                print(f"Failed to load MarianMT model for {lang_code}: {e}")
                return None, None
                
        return self.models[lang_code], self.tokenizers[lang_code]

    def _translate_text_marian(self, text: str, lang_code: str) -> str:
        model, tokenizer = self._get_model_and_tokenizer(lang_code)
        if not model or not tokenizer:
            return text
            
        inputs = tokenizer(text, return_tensors="pt", padding=True)
        translated = model.generate(**inputs)
        translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)
        return translated_text

    def _translate_text_llm(self, text: str, lang_code: str) -> str:
        if not settings.openrouter_api_key:
            return text
            
        try:
            response = completion(
                model=settings.openrouter_model if settings.openrouter_model.startswith("openrouter/") else f"openrouter/{settings.openrouter_model}",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate the following text to English. Return ONLY the English translation, no extra text."},
                    {"role": "user", "content": f"Text ({lang_code}): {text}"}
                ],
                api_key=settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM translation failed: {e}")
            return text

    def translate_invoice(self, raw_text: str, invoice: ExtractedInvoice) -> ExtractedInvoice:
        """User explicitly requested to disable all translation features and keep it English only."""
        invoice.detected_language = "en"
        invoice.was_translated = False
        invoice.translation_engine = None
        return invoice


