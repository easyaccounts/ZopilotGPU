import os
import json
import logging
from typing import Dict, Any, Optional, List
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JournalEntry(BaseModel):
    """Structured journal entry format."""
    date: str
    description: str
    account_debits: List[Dict[str, Any]]
    account_credits: List[Dict[str, Any]]
    total_debit: float
    total_credit: float
    reference: Optional[str] = None
    notes: Optional[str] = None

class LlamaProcessor:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        # Upgraded to Mixtral 8x7B for better accounting reasoning and complex logic
        self.model_name = "mistralai/Mixtral-8x7B-Instruct-v0.1"
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Mixtral 8x7B model with GPU optimization and quantization."""
        try:
            logger.info(f"Loading {self.model_name} (MoE architecture)...")
            logger.info("Note: Mixtral 8x7B requires ~24GB VRAM with 4-bit quantization")
            
            # Configure quantization for efficient GPU usage (critical for MoE models)
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16
            )
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                token=os.getenv("HUGGING_FACE_TOKEN"),
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with quantization
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=quantization_config,
                device_map="auto",
                torch_dtype=torch.float16,
                token=os.getenv("HUGGING_FACE_TOKEN"),
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise RuntimeError(f"Model initialization failed: {str(e)}")
    
    def generate_journal_entry(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a structured journal entry in JSON format."""
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not initialized")
        
        try:
            # Build the system prompt for structured JSON output
            system_message = self._build_system_prompt(context, prompt)
            
            # Format for Mixtral-Instruct (uses [INST] tags)
            formatted_prompt = f"<s>[INST] {system_message}\n\nGenerate the journal entry in the specified JSON format. [/INST]"
            
            # Tokenize and generate
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=2048)
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1024,  # Increased for complex accounting entries
                    temperature=0.3,  # Lower temperature for more deterministic output
                    do_sample=True,
                    top_p=0.95,  # Slightly higher for Mixtral
                    top_k=50,  # Add top-k sampling for better quality
                    repetition_penalty=1.1,  # Prevent repetition
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)
            
            # Parse JSON from response
            return self._parse_journal_response(response)
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}")
            return self._fallback_journal_entry(context, str(e))
    
    def _build_system_prompt(self, context: Optional[Dict[str, Any]], user_prompt: str) -> str:
        """Build system prompt for structured journal entry generation."""
        context_str = ""
        if context:
            context_str = f"\nExtracted Document Data:\n{json.dumps(context, indent=2)}\n"
        
        return f"""You are an expert accounting assistant. Your task is to generate structured journal entries in JSON format based on extracted document data.
{context_str}
User Request: {user_prompt}

Generate a journal entry in this exact JSON structure:
{{
  "date": "YYYY-MM-DD",
  "description": "Clear description of the transaction",
  "account_debits": [
    {{"account": "Account Name", "amount": 0.00, "description": "Debit description"}}
  ],
  "account_credits": [
    {{"account": "Account Name", "amount": 0.00, "description": "Credit description"}}
  ],
  "total_debit": 0.00,
  "total_credit": 0.00,
  "reference": "Document reference if available",
  "notes": "Additional notes or observations"
}}

Ensure debits equal credits and follow standard accounting principles. Only respond with valid JSON."""
    
    def _parse_journal_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from model response with fallback handling."""
        try:
            # Find JSON content
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[start:end]
            parsed = json.loads(json_str)
            
            # Validate structure
            required_fields = ['date', 'description', 'account_debits', 'account_credits', 'total_debit', 'total_credit']
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            return parsed
            
        except Exception as e:
            logger.warning(f"Failed to parse JSON response: {str(e)}")
            return self._fallback_journal_entry(None, f"Parse error: {str(e)}")
    
    def _fallback_journal_entry(self, context: Optional[Dict[str, Any]], error_msg: str) -> Dict[str, Any]:
        """Generate a fallback journal entry when parsing fails."""
        from datetime import datetime
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": "Document processing - manual review required",
            "account_debits": [{"account": "Miscellaneous", "amount": 0.00, "description": "Requires manual entry"}],
            "account_credits": [{"account": "Accounts Payable", "amount": 0.00, "description": "Requires manual entry"}],
            "total_debit": 0.00,
            "total_credit": 0.00,
            "reference": "System Generated",
            "notes": f"Processing error: {error_msg}. Original context: {json.dumps(context) if context else 'None'}"
        }

# Global instance
_llama_processor = None

def get_llama_processor() -> LlamaProcessor:
    """Get or create global Llama processor instance."""
    global _llama_processor
    if _llama_processor is None:
        _llama_processor = LlamaProcessor()
    return _llama_processor

def generate_with_llama(prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate structured journal entry using Mixtral 8x7B Instruct."""
    processor = get_llama_processor()
    return processor.generate_journal_entry(prompt, context)