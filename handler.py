"""
RunPod Serverless Handler for ZopilotGPU
Wraps FastAPI endpoints for RunPod serverless format
"""
print("=" * 80)
print("🚀 HANDLER.PY STARTING...")
print("=" * 80)
import sys
print(f"✅ sys imported - Python {sys.version}")

import os
print(f"✅ os imported")

from pathlib import Path
print(f"✅ pathlib imported")

# Verify /runpod-volume exists (RunPod Serverless Network Volume mount point)
workspace_path = Path("/runpod-volume")
if not workspace_path.exists():
    print("❌ CRITICAL: /runpod-volume directory does not exist!")
    print("   Please ensure RunPod Network Volume is properly attached to the endpoint")
    sys.exit(1)

if not workspace_path.is_dir():
    print("❌ CRITICAL: /runpod-volume exists but is not a directory!")
    sys.exit(1)

# Verify workspace is writable
try:
    test_file = workspace_path / ".write_test"
    test_file.write_text("test")
    test_file.unlink()
    print(f"✅ /runpod-volume verified and writable")
except Exception as e:
    print(f"❌ CRITICAL: /runpod-volume is not writable: {e}")
    sys.exit(1)

# Configure environment variables for model caching BEFORE any imports
# This ensures all ML libraries use persistent storage on /runpod-volume
# IMPORTANT: Models are stored directly in /runpod-volume/huggingface (legacy transformers structure)
os.environ['HF_HOME'] = str(workspace_path / "huggingface")  # HuggingFace home directory
os.environ['TRANSFORMERS_CACHE'] = str(workspace_path / "huggingface")  # Transformers cache (models stored here)
os.environ['HF_HUB_CACHE'] = str(workspace_path / "huggingface")  # Hub cache (same location)
os.environ['TORCH_HOME'] = str(workspace_path / "torch")     # PyTorch models
os.environ['XDG_CACHE_HOME'] = str(workspace_path)           # Generic cache (used by some libs)

# BitsAndBytes 0.45.0 has native CUDA 12.4 support - no override needed!
# Previous versions (0.42.0) required BNB_CUDA_VERSION=121 workaround
# Now BitsAndBytes auto-detects CUDA 12.4 correctly and uses native binaries
print(f"🔧 BitsAndBytes 0.45.0: Native CUDA 12.4 support (no override needed)")

# CRITICAL: EasyOCR cache configuration
# EasyOCR downloads models to MODULE_PATH/model by default (ephemeral!)
# We need to redirect it to persistent storage using EASYOCR_MODULE_PATH
easyocr_cache = workspace_path / "easyocr"
easyocr_cache.mkdir(parents=True, exist_ok=True)
os.environ['EASYOCR_MODULE_PATH'] = str(easyocr_cache)
print(f"📦 EasyOCR cache: {easyocr_cache}")

# Verify model cache directories exist
required_cache_dirs = [
    workspace_path / "huggingface",  # HF models stored directly here (legacy transformers structure)
    workspace_path / "docstrange" / "models",  # DocStrange models in /models subfolder
    workspace_path / "torch",  # PyTorch models
    easyocr_cache  # EasyOCR models
]

# Track if we found the Mixtral model
mixtral_model_found = False

for cache_dir in required_cache_dirs:
    if cache_dir.exists():
        print(f"✅ Found cache: {cache_dir}")
        # Check if it's the huggingface directory and list model contents
        if cache_dir.name == "huggingface":
            try:
                # Check for models in the cache directory (models stored directly here)
                models = list(cache_dir.glob("models--*"))
                if models:
                    print(f"   📦 Cached models: {len(models)} found")
                    for model in models[:3]:  # Show first 3
                        print(f"      - {model.name}")
                        # Check if Mixtral model exists
                        if "mistralai--Mixtral-8x7B-Instruct-v0.1" in model.name or "Mixtral" in model.name:
                            mixtral_model_found = True
                    if len(models) > 3:
                        print(f"      ... and {len(models) - 3} more")
                else:
                    print(f"   ⚠️  Huggingface directory exists but no models cached yet")
            except Exception as e:
                print(f"   Could not list models: {e}")
    else:
        print(f"⚠️  Cache directory does not exist (will be created): {cache_dir}")
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            print(f"   Created: {cache_dir}")
        except Exception as e:
            print(f"   Warning: Could not create {cache_dir}: {e}")

# CRITICAL: Stop execution if Mixtral model not found in cache
# Models MUST be pre-cached to network volume - downloads not allowed in production
if not mixtral_model_found:
    print("\n" + "=" * 80)
    print("❌ CRITICAL ERROR: Mixtral model not found in cache!")
    print("=" * 80)
    print(f"Expected location: /runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/")
    print("\n⚠️  Models MUST be pre-cached on network volume before deployment.")
    print("⚠️  Automatic downloads are disabled to prevent wasting GPU credits.")
    print("\n📋 To fix:")
    print("   1. Run: python download_models_locally.py (on local machine)")
    print("   2. Upload model_cache/ to RunPod network volume")
    print("   3. Ensure models are at /runpod-volume/huggingface/")
    
    # Print detailed cache structure for debugging
    print("\n" + "-" * 80)
    print("📁 ACTUAL CACHE STRUCTURE (for debugging):")
    print("-" * 80)
    
    try:
        hf_cache = workspace_path / "huggingface"
        if hf_cache.exists():
            print(f"\n/runpod-volume/huggingface/ contents:")
            for item in sorted(hf_cache.iterdir())[:20]:  # Show first 20 items
                if item.is_dir():
                    # Count files in subdirectory
                    try:
                        file_count = len(list(item.iterdir()))
                        print(f"  📁 {item.name}/ ({file_count} items)")
                        # If it looks like a model directory, show one level deeper
                        if item.name.startswith("models--"):
                            for subitem in sorted(item.iterdir())[:5]:
                                if subitem.is_dir():
                                    subfile_count = len(list(subitem.iterdir()))
                                    print(f"     📁 {subitem.name}/ ({subfile_count} items)")
                                else:
                                    size_mb = subitem.stat().st_size / (1024**2)
                                    print(f"     📄 {subitem.name} ({size_mb:.1f}MB)")
                    except Exception as e:
                        print(f"  📁 {item.name}/ (cannot read: {e})")
                else:
                    size_mb = item.stat().st_size / (1024**2)
                    print(f"  📄 {item.name} ({size_mb:.1f}MB)")
        else:
            print(f"  ⚠️  Directory does not exist: {hf_cache}")
        
        # Check alternative locations
        print(f"\nChecking alternative locations:")
        alt_locations = [
            workspace_path / "huggingface" / "hub",
            workspace_path / "huggingface" / "models",
            workspace_path / "model_cache" / "huggingface",
        ]
        for alt_path in alt_locations:
            if alt_path.exists():
                print(f"  ✅ Found: {alt_path}")
                try:
                    items = list(alt_path.iterdir())[:5]
                    for item in items:
                        print(f"     - {item.name}")
                except Exception as e:
                    print(f"     (cannot read: {e})")
            else:
                print(f"  ❌ Not found: {alt_path}")
                
    except Exception as e:
        print(f"  ⚠️  Error reading cache structure: {e}")
    
    print("-" * 80)
    print("\n❌ STOPPING: Models must be pre-cached, downloads not allowed in production")
    print("=" * 80)
    sys.exit(1)  # EXIT - do NOT allow download
else:
    print(f"✅ Mixtral model found in cache - will use cached version")

# Create symlink for DocStrange (it ignores XDG_CACHE_HOME and uses ~/.cache)
# This ensures DocStrange finds the cached models at /runpod-volume/docstrange
root_cache = Path("/root/.cache")
root_cache.mkdir(parents=True, exist_ok=True)

docstrange_symlink = root_cache / "docstrange"
docstrange_cache = workspace_path / "docstrange"

if not docstrange_symlink.exists():
    try:
        docstrange_symlink.symlink_to(docstrange_cache)
        print(f"✅ Created symlink: {docstrange_symlink} -> {docstrange_cache}")
    except Exception as e:
        print(f"⚠️  Could not create DocStrange symlink: {e}")
elif docstrange_symlink.is_symlink():
    print(f"✅ DocStrange symlink exists: {docstrange_symlink} -> {docstrange_symlink.readlink()}")
else:
    print(f"⚠️  {docstrange_symlink} exists but is not a symlink")

# CRITICAL: Create symlink for EasyOCR too (it uses ~/.EasyOCR/ by default)
# This is a backup in case EASYOCR_MODULE_PATH doesn't work
easyocr_symlink = Path("/root/.EasyOCR")
if not easyocr_symlink.exists():
    try:
        easyocr_symlink.symlink_to(easyocr_cache)
        print(f"✅ Created symlink: {easyocr_symlink} -> {easyocr_cache}")
    except Exception as e:
        print(f"⚠️  Could not create EasyOCR symlink: {e}")
elif easyocr_symlink.is_symlink():
    print(f"✅ EasyOCR symlink exists: {easyocr_symlink} -> {easyocr_symlink.readlink()}")
else:
    print(f"⚠️  {easyocr_symlink} exists but is not a symlink")

# Verify critical environment variables BEFORE any imports
REQUIRED_ENV_VARS = {
    'HUGGING_FACE_TOKEN': 'Hugging Face API token',
    'ZOPILOT_GPU_API_KEY': 'ZopilotGPU API key',
}

print("=" * 60)
print("RunPod Serverless Handler - Environment Check")
print("=" * 60)

missing_vars = []
for var, description in REQUIRED_ENV_VARS.items():
    value = os.getenv(var)
    if value:
        # Show first 10 chars of token for verification
        masked = f"{value[:10]}..." if len(value) > 10 else value
        print(f"✅ {var}: {masked}")
    else:
        print(f"❌ {var}: MISSING")
        missing_vars.append(f"{var} ({description})")

if missing_vars:
    print("\n⚠️  CRITICAL: Missing environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nPlease add these in RunPod endpoint settings under 'Environment Variables'")
    sys.exit(1)

# Check GPU availability and memory
print("🔄 Attempting to import torch...")
try:
    import torch
    print(f"✅ torch imported successfully: {torch.__version__}")
    
    # CRITICAL: Verify PyTorch version matches expected version
    # Prevents silent failures from PyTorch upgrades breaking BitsAndBytes compatibility
    EXPECTED_PYTORCH_VERSION = "2.5.1"
    if not torch.__version__.startswith(EXPECTED_PYTORCH_VERSION):
        print("=" * 80)
        print("❌ CRITICAL: PyTorch version mismatch!")
        print("=" * 80)
        print(f"Expected: {EXPECTED_PYTORCH_VERSION}")
        print(f"Actual: {torch.__version__}")
        print("\nThis will cause BitsAndBytes compatibility issues:")
        print("- PyTorch 2.5.1 is compatible with BitsAndBytes 0.45.0")
        print("- PyTorch 2.6+ requires NumPy 2.x (incompatible with docstrange)")
        print("- Version mismatch may cause quantization failures")
        print("\nPossible causes:")
        print("1. requirements.txt dependencies upgraded PyTorch")
        print("2. constraints file not applied correctly")
        print("3. pip resolver chose newer version")
        print("\nFix: Rebuild Docker image with correct constraints")
        print("=" * 80)
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC: PyTorch & CUDA Configuration")
    print("=" * 60)
    print(f"✅ PyTorch Version: {torch.__version__} (matches expected {EXPECTED_PYTORCH_VERSION})")
    print(f"✅ Native RTX 5090 Support: CUDA 12.4 cu124 binaries")
    print(f"PyTorch CUDA Compiled: {torch.version.cuda}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA Version (PyTorch): {torch.version.cuda}")
        print(f"CUDA Runtime Version: {torch.version.cuda}")
        print(f"cuDNN Version: {torch.backends.cudnn.version()}")
        print(f"Number of GPUs: {torch.cuda.device_count()}")
        
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
        compute_capability = torch.cuda.get_device_capability(0)
        
        print(f"🎮 GPU: {gpu_name}")
        print(f"💾 VRAM Total: {gpu_memory:.1f} GB")
        print(f"💾 VRAM Free: {(torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / (1024**3):.1f} GB")
        print(f"🔢 Compute Capability: {compute_capability[0]}.{compute_capability[1]}")
        
        # Check CUDA device properties (defensive - some attributes may not exist in all PyTorch versions)
        props = torch.cuda.get_device_properties(0)
        print(f"📊 Multi-processor count: {props.multi_processor_count}")
        # max_threads_per_block doesn't exist in PyTorch 2.8+, use safe access
        if hasattr(props, 'max_threads_per_block'):
            print(f"📊 Max threads per block: {props.max_threads_per_block}")
        
        # Warn if insufficient memory for Mixtral 8x7B with 4-bit NF4 quantization
        if gpu_memory < 20:
            print(f"⚠️  WARNING: Mixtral 8x7B 4-bit requires ~16-17GB VRAM, you have {gpu_memory:.1f}GB")
            print("   Model loading may fail or run very slowly")
        else:
            print(f"✅ Sufficient VRAM for Mixtral 8x7B 4-bit NF4 (~16-17GB required)")
    else:
        print("⚠️  No GPU detected - will fall back to CPU (very slow)")
    
    # BitsAndBytes diagnostics
    print("\n" + "=" * 60)
    print("DIAGNOSTIC: BitsAndBytes Configuration")
    print("=" * 60)
    try:
        import bitsandbytes as bnb
        print(f"✅ BitsAndBytes version: {bnb.__version__}")
        print(f"📦 BitsAndBytes location: {bnb.__file__}")
        
        # Check CUDA setup (BnB 0.45.0 auto-detects CUDA 12.4 correctly)
        print(f"🔧 BNB_CUDA_VERSION env: {os.environ.get('BNB_CUDA_VERSION', 'NOT SET (auto-detect enabled)')}")
        print(f"✅ BitsAndBytes 0.45.0: Native CUDA 12.4 support")
        
        # Try to get CUDA setup info
        try:
            from bitsandbytes.cuda_setup.main import CUDASetup
            setup = CUDASetup.get_instance()
            if hasattr(setup, 'lib'):
                print(f"✅ CUDA library loaded: {setup.lib}")
            if hasattr(setup, 'binary_name'):
                print(f"✅ Binary name: {setup.binary_name}")
        except Exception as e:
            print(f"⚠️  Could not get CUDA setup details: {e}")
        
        # Test import of critical BitsAndBytes functions
        try:
            from bitsandbytes.nn import Linear4bit
            print(f"✅ Linear4bit import: OK")
        except ImportError as e:
            print(f"❌ Linear4bit import FAILED: {e}")
        
        try:
            from bitsandbytes.functional import quantize_4bit
            print(f"✅ quantize_4bit import: OK")
        except ImportError as e:
            print(f"❌ quantize_4bit import FAILED: {e}")
            
    except ImportError as e:
        print(f"❌ BitsAndBytes import FAILED: {e}")
        print("   This will cause model loading to fail!")
    
    # Transformers diagnostics
    print("\n" + "=" * 60)
    print("DIAGNOSTIC: Transformers Configuration")
    print("=" * 60)
    try:
        import transformers
        print(f"✅ Transformers version: {transformers.__version__}")
        print(f"📦 Transformers location: {transformers.__file__}")
        
        # Test BitsAndBytes integration
        try:
            from transformers.integrations import validate_bnb_backend_availability
            print(f"✅ BitsAndBytes integration import: OK")
            # Try to validate (may fail, but we want to see the error)
            try:
                validate_bnb_backend_availability()
                print(f"✅ BitsAndBytes backend validation: PASSED")
            except Exception as e:
                print(f"⚠️  BitsAndBytes backend validation: {e}")
        except ImportError as e:
            print(f"❌ BitsAndBytes integration import FAILED: {e}")
            print("   This will cause quantized model loading to fail!")
            
        # Test BitsAndBytesConfig
        try:
            from transformers import BitsAndBytesConfig
            print(f"✅ BitsAndBytesConfig import: OK")
        except ImportError as e:
            print(f"❌ BitsAndBytesConfig import FAILED: {e}")
            
    except ImportError as e:
        print(f"❌ Transformers import FAILED: {e}")
    
    # System & Container diagnostics
    print("\n" + "=" * 60)
    print("DIAGNOSTIC: System & Container Info")
    print("=" * 60)
    import platform
    import sys
    print(f"🐍 Python version: {sys.version}")
    print(f"🖥️  Platform: {platform.platform()}")
    print(f"🖥️  Machine: {platform.machine()}")
    print(f"🖥️  Processor: {platform.processor()}")
    
    # Check critical environment variables
    print("\n📋 Critical Environment Variables:")
    critical_envs = [
        'CUDA_HOME', 'CUDA_PATH', 'LD_LIBRARY_PATH', 
        'BNB_CUDA_VERSION', 'PYTORCH_CUDA_ALLOC_CONF',
        'HF_HOME', 'TRANSFORMERS_CACHE'
    ]
    for env in critical_envs:
        value = os.environ.get(env)
        if value:
            # Truncate long paths
            display_value = value if len(value) < 80 else value[:77] + "..."
            print(f"   {env}: {display_value}")
        else:
            print(f"   {env}: NOT SET")
    
    print("=" * 60)
        
    # Check BitsAndBytes configuration
    print("\n" + "-" * 60)
    print("DIAGNOSTIC: BitsAndBytes Configuration")
    print("-" * 60)
    print(f"BNB_CUDA_VERSION override: {os.environ.get('BNB_CUDA_VERSION', 'NOT SET')}")
    
    try:
        import bitsandbytes as bnb
        print(f"BitsAndBytes Version: {bnb.__version__}")
        print(f"BitsAndBytes Location: {bnb.__file__}")
        
        # Try to check if CUDA is properly detected by BitsAndBytes
        try:
            from bitsandbytes.cuda_setup.main import get_cuda_lib_handle, get_compute_capabilities
            print("✅ BitsAndBytes CUDA setup module accessible")
        except ImportError as e:
            print(f"⚠️  BitsAndBytes CUDA setup import failed: {e}")
            
    except ImportError as e:
        print(f"⚠️  BitsAndBytes not yet imported: {e}")
    
except ImportError as e:
    print(f"⚠️  PyTorch not available for GPU check: {e}")

print("=" * 60)

print("🔄 Attempting to import runpod...")
try:
    import runpod  # type: ignore
    print(f"✅ runpod imported")
except ImportError:
    runpod = None  # Will be available in RunPod environment
    print(f"⚠️  runpod not available (will be provided by RunPod runtime)")

print("🔄 Importing Python standard libraries...")
import asyncio
import logging
from typing import Any, Dict
print("✅ Standard libraries imported")

# Import FastAPI app and endpoints
print("🔄 Attempting to import app.main (FastAPI endpoints)...")
try:
    from app.main import extract_endpoint, prompt_endpoint
    from app.main import ExtractionInput, PromptInput
    print("✅ FastAPI app imported successfully")
except Exception as app_import_error:
    print(f"❌ CRITICAL: Failed to import app.main: {app_import_error}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GPU Memory management
GPU_MEMORY_THRESHOLD_GB = 4.0  # Minimum free VRAM required to accept request
EXTRACTION_MEMORY_ESTIMATE_GB = 2.5  # DocStrange + buffers (CPU mode)
CLASSIFICATION_MEMORY_ESTIMATE_GB = 22.0  # Mixtral 8x7B 8-bit (reduced from 24.0 to account for system overhead)

# Concurrency control
# Since DocStrange uses CPU (cpu=True), we can have multiple extraction workers
# But Mixtral uses GPU, so only 1 classification at a time
import asyncio
extraction_semaphore = asyncio.Semaphore(4)  # Max 4 concurrent extractions (CPU-bound)
classification_semaphore = asyncio.Semaphore(1)  # Max 1 classification (GPU-bound)


def check_gpu_memory_available(required_gb: float = GPU_MEMORY_THRESHOLD_GB) -> bool:
    """
    Check if sufficient GPU memory is available for processing.
    Returns True if enough memory, False otherwise.
    """
    try:
        if not torch.cuda.is_available():
            # No GPU, assume CPU processing (always available)
            return True
        
        torch.cuda.empty_cache()  # Clear cache first
        torch.cuda.synchronize()  # Ensure all operations complete
        
        total_memory = torch.cuda.get_device_properties(0).total_memory
        allocated_memory = torch.cuda.memory_allocated(0)
        reserved_memory = torch.cuda.memory_reserved(0)
        
        # Use reserved memory (more accurate than allocated)
        free_memory_gb = (total_memory - reserved_memory) / (1024**3)
        
        logger.info(f"GPU Memory: {free_memory_gb:.2f}GB free / {total_memory/(1024**3):.2f}GB total")
        
        return free_memory_gb >= required_gb
        
    except Exception as e:
        logger.warning(f"Could not check GPU memory: {e}, assuming available")
        return True  # Fail open (allow request)


class MockRequest:
    """Mock Request object for API key verification"""
    def __init__(self, api_key: str = None):
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'


async def async_handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle RunPod serverless job with GPU memory checking.
    
    Expected input format:
    {
        "input": {
            "endpoint": "/extract" or "/prompt",
            "data": {...endpoint-specific data...},
            "api_key": "your_api_key" (optional if set in env)
        }
    }
    """
    try:
        job_input = job.get('input', {})
        
        endpoint = job_input.get('endpoint')
        data = job_input.get('data', {})
        api_key = job_input.get('api_key')
        
        logger.info(f"[RunPod] 📨 Processing endpoint: {endpoint}")
        logger.info(f"[RunPod] 📦 Payload size: {len(str(data))} bytes")
        
        # Check GPU memory before processing (for GPU endpoints)
        if endpoint in ['/extract', '/prompt']:
            # Determine memory requirement based on endpoint
            if endpoint == '/extract':
                required_memory = EXTRACTION_MEMORY_ESTIMATE_GB
                operation = "extraction"
            else:  # /prompt
                required_memory = CLASSIFICATION_MEMORY_ESTIMATE_GB
                operation = "classification"
            
            # Check if enough memory available
            if not check_gpu_memory_available(required_memory):
                logger.warning(f"[RunPod] Insufficient GPU memory for {operation}, returning retry signal")
                return {
                    "success": False,
                    "error": "GPU memory exhausted, retry shortly",
                    "error_type": "InsufficientGPUMemory",
                    "retry_after": 10  # Suggest retry after 10 seconds
                }
        
        # Create mock request with API key
        mock_request = MockRequest(api_key=api_key)
        
        if endpoint == '/extract':
            # Handle extraction with semaphore (limit concurrent extractions)
            async with extraction_semaphore:
                logger.info(f"[RunPod] Extraction started (concurrent: {4 - extraction_semaphore._value}/{4})")
                input_data = ExtractionInput(**data)
                result = await extract_endpoint(mock_request, input_data)
                
                # Handle JSONResponse (extract content from response body)
                if hasattr(result, 'body'):
                    import json
                    # JSONResponse stores content as bytes in body attribute
                    return json.loads(result.body.decode('utf-8'))
                # Handle dict response (backward compatibility)
                elif isinstance(result, dict):
                    return result
                # Handle Pydantic model response
                elif hasattr(result, 'dict'):
                    return result.dict()
                else:
                    raise ValueError(f"Unexpected result type: {type(result)}")
            
        elif endpoint == '/prompt':
            # Handle prompting with semaphore (limit to 1 concurrent classification)
            async with classification_semaphore:
                logger.info(f"[RunPod] 🎯 Classification started (GPU locked)")
                
                try:
                    input_data = PromptInput(**data)
                    logger.info(f"[RunPod] 📝 Prompt length: {len(input_data.prompt)} chars")
                    
                    result = await prompt_endpoint(mock_request, input_data)
                    logger.info(f"[RunPod] ✅ Classification completed successfully")
                    
                    # Handle JSONResponse (extract content from response body)
                    if hasattr(result, 'body'):
                        import json
                        # JSONResponse stores content as bytes in body attribute
                        return json.loads(result.body.decode('utf-8'))
                    # Handle dict response (backward compatibility)
                    elif isinstance(result, dict):
                        return result
                    # Handle Pydantic model response
                    elif hasattr(result, 'dict'):
                        return result.dict()
                    else:
                        raise ValueError(f"Unexpected result type: {type(result)}")
                        
                except Exception as prompt_error:
                    import traceback
                    error_msg = str(prompt_error)
                    error_type = type(prompt_error).__name__
                    error_traceback = traceback.format_exc()
                    
                    logger.error("="*70)
                    logger.error("[RunPod] CLASSIFICATION REQUEST FAILED")
                    logger.error("="*70)
                    logger.error(f"❌ Error Type: {error_type}")
                    logger.error(f"❌ Error Message: {error_msg}")
                    logger.error(f"\n❌ Full Traceback:\n{error_traceback}")
                    
                    # Add context-specific diagnostics
                    if "bitsandbytes" in error_msg.lower() or "cuda setup" in error_msg.lower():
                        logger.error("-"*70)
                        logger.error("BITSANDBYTES/CUDA DIAGNOSTICS")
                        logger.error("-"*70)
                        logger.error(f"BNB_CUDA_VERSION: {os.environ.get('BNB_CUDA_VERSION', 'NOT SET')}")
                        logger.error(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', 'NOT SET')[:200]}")
                        logger.error(f"CUDA_HOME: {os.environ.get('CUDA_HOME', 'NOT SET')}")
                        logger.error(f"PyTorch version: {torch.__version__}")
                        logger.error(f"PyTorch CUDA compiled: {torch.version.cuda if hasattr(torch.version, 'cuda') else 'N/A'}")
                        logger.error(f"GPU Available: {torch.cuda.is_available()}")
                        if torch.cuda.is_available():
                            logger.error(f"GPU: {torch.cuda.get_device_name(0)}")
                            logger.error(f"CUDA Runtime (detected): {torch.version.cuda}")
                            logger.error(f"Compute Capability: {torch.cuda.get_device_capability(0)}")
                        
                        # Try to check BitsAndBytes state
                        try:
                            import bitsandbytes as bnb
                            logger.error(f"BitsAndBytes version: {bnb.__version__}")
                            logger.error(f"BitsAndBytes path: {bnb.__file__}")
                        except Exception as bnb_err:
                            logger.error(f"Cannot import BitsAndBytes: {bnb_err}")
                        
                        logger.error("-"*70)
                        logger.error("SOLUTION HINTS:")
                        logger.error("- If 'libbitsandbytes_cudaXXX.so not found': Set BNB_CUDA_VERSION env var")
                        logger.error("- If 'CUDA libraries not in path': Check LD_LIBRARY_PATH")
                        logger.error("- If 'PyTorch CUDA mismatch': Verify PyTorch CUDA version matches runtime")
                        logger.error("-"*70)
                    
                    elif "out of memory" in error_msg.lower() or "oom" in error_msg.lower():
                        logger.error("-"*70)
                        logger.error("GPU MEMORY DIAGNOSTICS")
                        logger.error("-"*70)
                        if torch.cuda.is_available():
                            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                            allocated = torch.cuda.memory_allocated(0) / (1024**3)
                            reserved = torch.cuda.memory_reserved(0) / (1024**3)
                            free = total - reserved
                            logger.error(f"Total VRAM: {total:.2f} GB")
                            logger.error(f"Allocated: {allocated:.2f} GB")
                            logger.error(f"Reserved: {reserved:.2f} GB")
                            logger.error(f"Free: {free:.2f} GB")
                        logger.error("-"*70)
                        logger.error("SOLUTION HINTS:")
                        logger.error("- Model requires ~16-17GB for 4-bit quantization")
                        logger.error("- Try reducing max_new_tokens in generation")
                        logger.error("- Check if other processes are using GPU memory")
                        logger.error("-"*70)
                    
                    elif "out of memory" in error_msg.lower():
                        logger.error("-"*70)
                        logger.error("GPU MEMORY DIAGNOSTICS")
                        logger.error("-"*70)
                        if torch.cuda.is_available():
                            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                            allocated = torch.cuda.memory_allocated(0) / (1024**3)
                            reserved = torch.cuda.memory_reserved(0) / (1024**3)
                            logger.error(f"Total: {total:.2f}GB | Allocated: {allocated:.2f}GB | Reserved: {reserved:.2f}GB")
                        logger.error("💡 Suggestion: Reduce batch size or use smaller model")
                        logger.error("-"*70)
                    
                    logger.error(f"\n🔍 Full Traceback:\n{error_traceback}")
                    logger.error("="*70)
                    
                    # Return error response (don't raise - RunPod needs a response)
                    return {
                        "success": False,
                        "error": error_msg,
                        "error_type": error_type,
                        "traceback": error_traceback[:2000],  # Increased limit for debugging
                        "diagnostics": {
                            "bnb_cuda_version": os.environ.get('BNB_CUDA_VERSION', 'NOT SET'),
                            "pytorch_cuda": torch.version.cuda if torch.cuda.is_available() else None,
                            "gpu_available": torch.cuda.is_available(),
                            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                        }
                    }
            
        elif endpoint == '/health':
            # Health check with GPU memory info
            gpu_info = {}
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                reserved = torch.cuda.memory_reserved(0) / (1024**3)
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                free = total - reserved
                gpu_info = {
                    "gpu_available": True,
                    "gpu_name": torch.cuda.get_device_name(0),
                    "total_vram_gb": round(total, 2),
                    "free_vram_gb": round(free, 2),
                    "allocated_vram_gb": round(allocated, 2),
                    "reserved_vram_gb": round(reserved, 2)
                }
            
            return {
                "status": "healthy",
                "service": "ZopilotGPU",
                "model": "Mixtral-8x7B-Instruct-v0.1",
                **gpu_info
            }
            
        else:
            return {
                "success": False,
                "error": f"Unknown endpoint: {endpoint}. Valid: /extract, /prompt, /health"
            }
            
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[RunPod] ❌ Handler error: {str(e)}")
        logger.error(f"[RunPod] 🔍 Traceback:\n{error_traceback}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": error_traceback[:1000]
        }
    finally:
        # Always cleanup GPU memory after request
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception as cleanup_error:
            logger.warning(f"GPU cleanup error: {cleanup_error}")


# Rename async_handler to handler (RunPod supports async handlers directly)
handler = async_handler


# Start RunPod serverless worker
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🎯 STARTING RUNPOD SERVERLESS WORKER")
    print("=" * 80)
    
    if runpod is None:
        logger.error("runpod package not installed. Install with: pip install runpod")
        print("❌ runpod package not available!")
        exit(1)
    
    logger.info("Starting RunPod serverless worker for ZopilotGPU...")
    print("✅ Calling runpod.serverless.start()...")
    try:
        runpod.serverless.start({"handler": handler})
        print("✅ RunPod serverless worker started successfully!")
    except Exception as start_error:
        print(f"❌ Failed to start RunPod worker: {start_error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
