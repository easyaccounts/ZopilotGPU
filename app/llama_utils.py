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
            logger.info("Note: Mixtral 8x7B requires ~24GB VRAM with 8-bit quantization")
            
            # Enable PyTorch memory expansion to reduce fragmentation
            # Prevents "CUDA out of memory" errors during generation
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
            
            # Clear GPU cache before loading (critical for 24GB VRAM)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info(f"GPU cache cleared before model loading")
            
            # Verify token exists
            hf_token = os.getenv("HUGGING_FACE_TOKEN")
            if not hf_token:
                raise ValueError(
                    "HUGGING_FACE_TOKEN environment variable not set. "
                    "Please add it to your RunPod endpoint environment variables."
                )
            
            logger.info(f"Using Hugging Face token: {hf_token[:10]}...")
            
            # Configure 8-bit quantization for best quality/VRAM balance
            # 8-bit provides 98-99% of FP16 quality while fitting in 24GB VRAM
            # CRITICAL: CPU offload DISABLED to prevent meta tensor errors and disk offloading
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_threshold=6.0,  # Threshold for outlier detection
                llm_int8_has_fp16_weight=False,  # Use 8-bit weights
                llm_int8_enable_fp32_cpu_offload=False  # ✅ DISABLED: Prevents CPU/disk offloading
            )
            
            # Load tokenizer
            logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                token=hf_token,
                trust_remote_code=True
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("Tokenizer loaded successfully")
            
            # Load model with quantization
            logger.info("Loading model from cache...")
            logger.info("⏱️  Cached: ~5 seconds | First download: ~15-30 minutes")
            model_load_start = __import__('time').time()
            
            # CRITICAL: Load model with 8-bit quantization
            # RTX 4090 has 24GB VRAM total (23.5GB available after overhead)
            # Mixtral 8x7B 8-bit will use ~18-20GB for weights + 2-4GB for activations
            # 
            # CRITICAL CONSTRAINTS:
            # 1. Model CANNOT be offloaded to CPU (causes meta tensor errors)
            # 2. Must reserve memory buffer for activations/KV cache
            # 3. Need to prevent OOM during generation
            #
            # Strategy:
            # - Set max_memory to reserve 2-3GB buffer (use 21GB of 24GB)
            # - Use device_map={"": 0} to force FULL placement on GPU 0
            # - Keep llm_int8_enable_fp32_cpu_offload=False (no CPU fallback)
            # - Model will either fit entirely on GPU or fail fast (no partial offload)
            
            logger.info("Loading Mixtral 8x7B with 8-bit quantization...")
            logger.info("Expected memory: ~18-20GB for weights, ~3GB buffer for activations")
            logger.info("Memory limit: 21GB on GPU 0 (reserving 3GB buffer)")
            
            # Configure memory: reserve 3GB buffer from 24GB total
            max_memory_config = {
                0: "21GB",  # Use 21GB of 24GB, leaving 3GB buffer
            }
            # Note: Intentionally NOT setting "cpu": "0GB" to avoid device_map conflict
            # device_map={"": 0} will force GPU-only placement
            
            # Load model with FORCED GPU-only placement (no auto fallback to CPU)
            # Flash Attention 2 disabled for faster builds
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=quantization_config,
                device_map={"": 0},  # Force ALL layers on GPU 0 (no CPU offload)
                max_memory=max_memory_config,
                torch_dtype=torch.float16,
                token=hf_token,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                # attn_implementation="flash_attention_2"  # Requires flash-attn package
            )
            
            # Report actual load time
            model_load_time = __import__('time').time() - model_load_start
            if model_load_time < 30:
                logger.info(f"✅ Model loaded from cache in {model_load_time:.1f} seconds")
            else:
                logger.info(f"✅ Model loaded in {model_load_time:.1f} seconds (downloaded from HuggingFace)")
            
            # CRITICAL: Verify no CPU offloading (check for meta device)
            if hasattr(self.model, 'hf_device_map'):
                device_map = self.model.hf_device_map
                cpu_layers = [k for k, v in device_map.items() 
                             if 'cpu' in str(v).lower() or 'meta' in str(v).lower()]

                if cpu_layers:
                    logger.error(f"❌ CRITICAL: {len(cpu_layers)} layers on CPU/meta device!")
                    logger.error(f"   First few: {cpu_layers[:5]}")
                    raise RuntimeError(
                        f"Model has {len(cpu_layers)} layers on CPU/meta device. "
                        f"This will cause 'Cannot copy out of meta tensor' errors during generation. "
                        f"Increase GPU memory allocation or use smaller model."
                    )
                else:
                    logger.info(f"✅ All model layers on GPU (no CPU offloading)")
            
            # Report GPU memory usage after loading
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                reserved = torch.cuda.memory_reserved(0) / (1024**3)
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                free = total - reserved
                logger.info(f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved, {free:.2f}GB free")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to load model: {error_msg}")
            
            # Provide helpful error messages
            if "access" in error_msg.lower() or "permission" in error_msg.lower():
                logger.error(
                    "⚠️  Permission Error: Please ensure:\n"
                    "1. You've accepted the Mixtral license at:\n"
                    "   https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1\n"
                    "2. Your token has read access\n"
                    "3. You're using the correct token in HUGGING_FACE_TOKEN env var"
                )
            
            raise RuntimeError(
                f"Unable to access model '{self.model_name}'. "
                f"Please ensure the model exists and you have permission to access it. "
                f"For private models, make sure the HuggingFace token is properly configured. "
                f"Original error: {error_msg}"
            )
    
    def generate_journal_entry(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a structured journal entry in JSON format."""
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model not initialized")
        
        try:
            logger.info("🎯 Starting generation...")
            gen_start = __import__('time').time()
            
            # Build the system prompt for structured JSON output
            system_message = self._build_system_prompt(context, prompt)
            logger.info(f"📝 Prompt built: {len(system_message)} chars")
            
            # Format for Mixtral-Instruct (uses [INST] tags)
            formatted_prompt = f"<s>[INST] {system_message}\n\nGenerate the journal entry in the specified JSON format. [/INST]"
            
            # Tokenize and generate
            logger.info("🔢 Tokenizing input...")
            inputs = self.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=2048)
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            input_tokens = len(inputs["input_ids"][0])
            logger.info(f"   Input tokens: {input_tokens}")
            
            logger.info("🚀 Generating response (max 1024 tokens)...")
            gen_only_start = __import__('time').time()
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
            gen_time = __import__('time').time() - gen_only_start
            output_tokens = len(outputs[0]) - input_tokens
            tokens_per_sec = output_tokens / gen_time if gen_time > 0 else 0
            logger.info(f"✅ Generated {output_tokens} tokens in {gen_time:.1f}s ({tokens_per_sec:.1f} tok/s)")
            
            # Decode response
            logger.info("📖 Decoding response...")
            response = self.tokenizer.decode(outputs[0][len(inputs["input_ids"][0]):], skip_special_tokens=True)
            logger.info(f"   Response length: {len(response)} chars")
            
            # CRITICAL: Clear KV cache after generation to prevent memory leak
            # KV cache can grow to 4-8GB and stays in VRAM if not cleared
            if hasattr(self.model, 'past_key_values'):
                self.model.past_key_values = None
            torch.cuda.empty_cache()
            torch.cuda.synchronize()  # Ensure cleanup completes before continuing
            
            # Report memory after cleanup
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                reserved = torch.cuda.memory_reserved(0) / (1024**3)
                logger.info(f"🧹 KV cache cleared: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
            
            # Parse JSON from response
            logger.info("🔍 Parsing JSON response...")
            result = self._parse_journal_response(response)
            
            total_time = __import__('time').time() - gen_start
            logger.info(f"🎉 Generation complete in {total_time:.1f}s total")
            return result
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Generation failed: {str(e)}")
            logger.error(f"🔍 Traceback:\n{traceback.format_exc()}")
            
            # CRITICAL: Clean up KV cache even on error to prevent memory leaks
            if hasattr(self.model, 'past_key_values'):
                self.model.past_key_values = None
            torch.cuda.empty_cache()
            logger.info("🧹 KV cache cleared after error")
            
            # CRITICAL: Don't return fallback - raise exception so backend knows generation failed
            # Returning fallback causes silent failures where backend gets empty/incorrect data
            raise RuntimeError(f"Mixtral generation failed: {str(e)}") from e
    
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