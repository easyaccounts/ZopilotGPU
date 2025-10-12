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
            logger.info("="*70)
            logger.info(f"MODEL INITIALIZATION: {self.model_name}")
            logger.info("="*70)
            logger.info(f"Loading {self.model_name} (MoE architecture)...")
            logger.info("Note: Mixtral 8x7B 4-bit NF4: ~12GB weights + 3-5GB activations = ~16-17GB total")
            logger.info("Compatible with: RTX 4090 (24GB), RTX 5090 (32GB), A40 (48GB)")
            
            # Log diagnostic information
            logger.info("-"*70)
            logger.info("DIAGNOSTIC: Environment & Dependencies")
            logger.info("-"*70)
            logger.info(f"PyTorch version: {torch.__version__}")
            logger.info(f"CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                logger.info(f"CUDA version (PyTorch): {torch.version.cuda}")
                logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
                logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
                logger.info(f"Compute capability: {torch.cuda.get_device_capability(0)}")
            
            # Log BitsAndBytes configuration
            import bitsandbytes as bnb
            logger.info(f"BitsAndBytes version: {bnb.__version__}")
            logger.info(f"BNB_CUDA_VERSION env: {os.environ.get('BNB_CUDA_VERSION', 'NOT SET')}")
            
            # Log transformers version
            import transformers
            logger.info(f"Transformers version: {transformers.__version__}")
            logger.info("-"*70)
            
            # Enable PyTorch memory expansion to reduce fragmentation
            # Prevents "CUDA out of memory" errors during generation
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
            logger.info("PyTorch memory expansion enabled: expandable_segments=True")
            
            # Clear GPU cache before loading
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                free_memory = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
                logger.info(f"GPU cache cleared. Free memory: {free_memory / (1024**3):.1f} GB")
            
            # Verify token exists
            hf_token = os.getenv("HUGGING_FACE_TOKEN")
            if not hf_token:
                raise ValueError(
                    "HUGGING_FACE_TOKEN environment variable not set. "
                    "Please add it to your RunPod endpoint environment variables."
                )
            
            logger.info(f"Using Hugging Face token: {hf_token[:10]}...")
            
            # Configure 4-bit NF4 quantization (QLoRA standard)
            # NF4 provides 95-97% of FP16 quality while using only ~10-12GB VRAM
            # Benefits:
            # - 2x less memory than 8-bit (10-12GB vs 22-24GB)
            # - 30% faster inference (less memory bandwidth)
            # - Leaves 12GB free for activations/KV cache/future features
            # - No OOM issues during loading
            # Quality: Excellent for classification/instruction-following tasks
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,  # Use 4-bit quantization
                bnb_4bit_compute_dtype=torch.float16,  # Compute in FP16 for quality
                bnb_4bit_quant_type="nf4",  # NormalFloat4 (optimal for LLM weights)
                bnb_4bit_use_double_quant=True,  # Nested quantization (saves more memory)
            )
            
            # Load tokenizer
            logger.info("Loading tokenizer...")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    token=hf_token,
                    trust_remote_code=True
                )
                
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                
                logger.info("Tokenizer loaded successfully")
            except Exception as tokenizer_error:
                logger.error(f"❌ Failed to load tokenizer: {tokenizer_error}")
                import traceback
                logger.error(f"Tokenizer traceback:\n{traceback.format_exc()}")
                raise
            
            # Load model with quantization
            logger.info("Loading model from cache...")
            logger.info("⏱️  Cached: ~5 seconds | First download: ~15-30 minutes")
            model_load_start = __import__('time').time()
            
            # Load model with 4-bit NF4 quantization
            # Memory breakdown:
            #   - 4-bit NF4 weights: ~12GB
            #   - Activations during inference: ~3-5GB
            #   - Total peak usage: ~16-17GB
            # 
            # GPU Compatibility:
            #   - RTX 4090 (24GB): 7-8GB free headroom ✅
            #   - RTX 5090 (32GB): 15-16GB free headroom ✅
            #   - A40 (48GB): 31-32GB free headroom ✅
            #
            # Benefits of 4-bit NF4:
            # 1. Fits on 24GB+ GPUs with plenty of headroom
            # 2. 2x faster than 8-bit (less memory bandwidth)
            # 3. Quality: 95-97% of FP16 (excellent for classification)
            # 4. No CPU offloading needed
            #
            # Strategy:
            # - Use device_map={"": 0} to place all layers on GPU 0
            # - No max_memory constraint needed
            # - Model loads in 1-2 minutes from cache
            
            logger.info("Loading Mixtral 8x7B with 4-bit NF4 quantization...")
            logger.info("Expected memory: ~12GB weights + ~3-5GB activations = ~16-17GB total")
            logger.info("Quality: 95-97% of FP16 (optimal for classification/instruction-following)")
            
            # Load model with simple GPU placement (no memory constraints needed!)
            # 4-bit quantization fits comfortably in available VRAM
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=quantization_config,
                device_map={"": 0},  # Place all layers on GPU 0
                torch_dtype=torch.float16,
                token=hf_token,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                # attn_implementation="flash_attention_2"  # Requires flash-attn package
            )
            
            # Report actual load time
            model_load_time = __import__('time').time() - model_load_start
            logger.info("-"*70)
            logger.info("MODEL LOADING SUMMARY")
            logger.info("-"*70)
            if model_load_time < 30:
                logger.info(f"✅ Model loaded from cache in {model_load_time:.1f} seconds")
            else:
                logger.info(f"✅ Model loaded in {model_load_time:.1f} seconds (downloaded from HuggingFace)")
            
            # CRITICAL: Verify no CPU offloading (check for meta device)
            if hasattr(self.model, 'hf_device_map'):
                device_map = self.model.hf_device_map
                logger.info(f"Device map: {len(device_map)} layers mapped")
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
                    # Show sample of device mapping
                    sample_mapping = dict(list(device_map.items())[:3])
                    logger.info(f"   Sample mapping: {sample_mapping}")
            
            # Report GPU memory usage after loading
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                reserved = torch.cuda.memory_reserved(0) / (1024**3)
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                free = total - reserved
                logger.info(f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved, {free:.2f}GB free")
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_traceback = traceback.format_exc()
            
            logger.error("="*70)
            logger.error("MODEL INITIALIZATION FAILED")
            logger.error("="*70)
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {error_msg}")
            logger.error(f"\nFull Traceback:\n{error_traceback}")
            
            # Detailed BitsAndBytes diagnostics
            if "bitsandbytes" in error_msg.lower() or "bnb" in error_msg.lower():
                logger.error("-"*70)
                logger.error("BITSANDBYTES FAILURE DIAGNOSTICS")
                logger.error("-"*70)
                
                # Check BNB environment variable
                bnb_cuda_ver = os.environ.get('BNB_CUDA_VERSION', 'NOT SET')
                logger.error(f"BNB_CUDA_VERSION: {bnb_cuda_ver}")
                
                # Try to import and get version
                try:
                    import bitsandbytes as bnb
                    logger.error(f"BitsAndBytes version: {bnb.__version__}")
                    logger.error(f"BitsAndBytes location: {bnb.__file__}")
                except ImportError as import_err:
                    logger.error(f"Cannot import BitsAndBytes: {import_err}")
                
                # Check CUDA libraries
                cuda_home = os.environ.get('CUDA_HOME', 'NOT SET')
                cuda_path = os.environ.get('CUDA_PATH', 'NOT SET')
                ld_library_path = os.environ.get('LD_LIBRARY_PATH', 'NOT SET')
                
                logger.error(f"CUDA_HOME: {cuda_home}")
                logger.error(f"CUDA_PATH: {cuda_path}")
                logger.error(f"LD_LIBRARY_PATH: {ld_library_path[:200] if ld_library_path != 'NOT SET' else 'NOT SET'}")
                
                # Check for CUDA libraries
                import glob
                logger.error("\nSearching for CUDA libraries:")
                cuda_search_paths = [
                    '/usr/local/cuda/lib64',
                    '/usr/local/nvidia/lib64',
                    '/usr/lib/x86_64-linux-gnu'
                ]
                for search_path in cuda_search_paths:
                    try:
                        libcudart = glob.glob(f"{search_path}/libcudart.so*")
                        if libcudart:
                            logger.error(f"  ✅ Found libcudart in {search_path}: {libcudart[:2]}")
                        else:
                            logger.error(f"  ❌ No libcudart found in {search_path}")
                    except Exception:
                        pass
                
                # Check for BitsAndBytes CUDA libraries
                try:
                    import bitsandbytes as bnb
                    bnb_path = os.path.dirname(bnb.__file__)
                    logger.error(f"\nSearching for BNB CUDA libraries in: {bnb_path}")
                    bnb_libs = glob.glob(f"{bnb_path}/**/*.so", recursive=True)
                    if bnb_libs:
                        logger.error(f"  Found {len(bnb_libs)} .so files:")
                        for lib in bnb_libs[:5]:  # Show first 5
                            logger.error(f"    - {os.path.basename(lib)}")
                    else:
                        logger.error(f"  ❌ No .so files found in BNB directory")
                except Exception as search_err:
                    logger.error(f"  Error searching BNB libraries: {search_err}")
                
                logger.error("-"*70)
                logger.error("RECOMMENDED FIXES:")
                logger.error("1. Check BNB_CUDA_VERSION environment variable is set correctly")
                logger.error("2. Ensure CUDA libraries are in LD_LIBRARY_PATH")
                logger.error("3. Verify BitsAndBytes version compatibility with PyTorch")
                logger.error("4. Check CUDA runtime version matches PyTorch compilation")
                logger.error("-"*70)
                logger.error(f"BNB_CUDA_VERSION env var: {os.environ.get('BNB_CUDA_VERSION', 'NOT SET')}")
                
                try:
                    import bitsandbytes as bnb
                    logger.error(f"BitsAndBytes version: {bnb.__version__}")
                    logger.error(f"BitsAndBytes location: {bnb.__file__}")
                except Exception as bnb_err:
                    logger.error(f"Cannot import BitsAndBytes: {bnb_err}")
                
                try:
                    logger.error(f"PyTorch CUDA version: {torch.version.cuda}")
                    logger.error(f"CUDA available: {torch.cuda.is_available()}")
                    if torch.cuda.is_available():
                        logger.error(f"CUDA runtime version: {torch.version.cuda}")
                        logger.error(f"Compute capability: {torch.cuda.get_device_capability(0)}")
                except Exception as cuda_err:
                    logger.error(f"Cannot check CUDA: {cuda_err}")
                
                logger.error("\n⚠️  BitsAndBytes CUDA Setup Failed!")
                logger.error("Possible fixes:")
                logger.error("1. Set BNB_CUDA_VERSION=121 environment variable")
                logger.error("2. Verify CUDA runtime matches PyTorch (12.1)")
                logger.error("3. Check LD_LIBRARY_PATH includes CUDA libraries")
                logger.error("4. Run: python -m bitsandbytes (for detailed diagnostics)")
                logger.error("-"*70)
            
            # CUDA OOM diagnostics
            elif "out of memory" in error_msg.lower() or "oom" in error_msg.lower():
                logger.error("-"*70)
                logger.error("CUDA OUT OF MEMORY DIAGNOSTICS")
                logger.error("-"*70)
                if torch.cuda.is_available():
                    total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    allocated = torch.cuda.memory_allocated(0) / (1024**3)
                    reserved = torch.cuda.memory_reserved(0) / (1024**3)
                    logger.error(f"Total VRAM: {total:.2f} GB")
                    logger.error(f"Allocated: {allocated:.2f} GB")
                    logger.error(f"Reserved: {reserved:.2f} GB")
                    logger.error(f"Free: {total - reserved:.2f} GB")
                logger.error("⚠️  Mixtral 8x7B 4-bit requires ~16-17GB VRAM")
                logger.error("Possible fixes:")
                logger.error("1. Use GPU with ≥20GB VRAM (RTX 4090, RTX 5090, A40)")
                logger.error("2. Reduce max_length or batch_size")
                logger.error("3. Use smaller model (Mistral 7B needs ~4-5GB)")
                logger.error("-"*70)
            
            # Permission/access errors
            elif "access" in error_msg.lower() or "permission" in error_msg.lower():
                logger.error("-"*70)
                logger.error("MODEL ACCESS / PERMISSION ERROR")
                logger.error("-"*70)
                logger.error("⚠️  Please ensure:")
                logger.error("1. You've accepted the Mixtral license at:")
                logger.error("   https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1")
                logger.error("2. Your HF token has read access")
                logger.error("3. HUGGING_FACE_TOKEN env var is set correctly")
                logger.error(f"4. Current token (masked): {os.environ.get('HUGGING_FACE_TOKEN', 'NOT SET')[:10]}...")
                logger.error("-"*70)
            
            # Log full traceback for unknown errors
            logger.error("\nFull Traceback:")
            logger.error(error_traceback)
            logger.error("="*70)
            
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