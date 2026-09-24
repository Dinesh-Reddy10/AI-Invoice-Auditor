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
                model=f"openrouter/{settings.openrouter_model}",
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
        """Detects language and translates vendor_name and line item descriptions."""
        
        # 1. Detect Language
        try:
            lang_code = langdetect.detect(raw_text)
        except langdetect.lang_detect_exception.LangDetectException:
            lang_code = "en"
            
        invoice.detected_language = lang_code
        
        # If English or unsupported (not in our specific Indic list and not english), just return
        # Actually, if it's not English, let's try to translate it if it's in our supported list
        if lang_code == "en":
            invoice.was_translated = False
            return invoice
            
        if lang_code not in self.supported_languages:
            # Unsupported language, we won't translate but we note it
            invoice.was_translated = False
            invoice.translation_engine = "UNSUPPORTED"
            return invoice
            
        # 2. Translate fields
        engine_used = "MarianMT"
        try:
            # Try MarianMT first
            translated_vendor = self._translate_text_marian(invoice.vendor_name, lang_code)
            
            # If MarianMT failed to load, it returns the original text. Let's fallback if they are identical and it's not English text
            if translated_vendor == invoice.vendor_name:
                 engine_used = "LLM Fallback"
                 translated_vendor = self._translate_text_llm(invoice.vendor_name, lang_code)
                 
            invoice.vendor_name = translated_vendor
            
            for item in invoice.line_items:
                if engine_used == "MarianMT":
                    t_desc = self._translate_text_marian(item.description, lang_code)
                    if t_desc == item.description:
                        t_desc = self._translate_text_llm(item.description, lang_code)
                        engine_used = "LLM Fallback"
                    item.description = t_desc
                else:
                    item.description = self._translate_text_llm(item.description, lang_code)

            invoice.was_translated = True
            invoice.translation_engine = engine_used
            invoice.translation_confidence = 0.85 if engine_used == "MarianMT" else 0.95
            
        except Exception as e:
            print(f"Translation process failed: {e}")
            invoice.was_translated = False
            
        return invoice
