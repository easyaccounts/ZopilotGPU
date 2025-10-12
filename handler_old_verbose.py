"""
RunPod Serverless Handler for ZopilotGPU
Wraps FastAPI endpoints for RunPod serverless format
"""
import os
import sys
from pathlib import Path

# CRITICAL: Force flush stdout immediately (RunPod logging)
print("=" * 70, flush=True)
print("🚀 HANDLER.PY STARTING", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print("=" * 70, flush=True)

# Verify /runpod-volume exists (RunPod Serverless Network Volume mount point)
workspace_path = Path("/runpod-volume")
if not workspace_path.exists():
    print("⚠️  WARNING: /runpod-volume directory does not exist!", flush=True)
    print("   Please ensure RunPod Network Volume is properly attached to the endpoint", flush=True)
    print("   ⚠️  CONTINUING - Worker will start but may fail to cache models", flush=True)
    # REMOVED sys.exit(1) for debugging

if not workspace_path.is_dir():
    print("⚠️  WARNING: /runpod-volume exists but is not a directory!", flush=True)
    print("   ⚠️  CONTINUING - Worker will start but may have issues", flush=True)
    # REMOVED sys.exit(1) for debugging

# Verify workspace is writable
try:
    test_file = workspace_path / ".write_test"
    test_file.write_text("test")
    test_file.unlink()
    print(f"✅ /runpod-volume verified and writable", flush=True)
except Exception as e:
    print(f"⚠️  WARNING: /runpod-volume is not writable: {e}", flush=True)
    print("   ⚠️  CONTINUING - Worker will start but cannot cache models", flush=True)
    # REMOVED sys.exit(1) for debugging

# Configure environment variables for model caching BEFORE any imports
# This ensures all ML libraries use persistent storage on /runpod-volume
# IMPORTANT: Models are stored directly in /runpod-volume/huggingface (legacy transformers structure)
os.environ['HF_HOME'] = str(workspace_path / "huggingface")  # HuggingFace home directory
os.environ['TRANSFORMERS_CACHE'] = str(workspace_path / "huggingface")  # Transformers cache (models stored here)
os.environ['HF_HUB_CACHE'] = str(workspace_path / "huggingface")  # Hub cache (same location)
os.environ['TORCH_HOME'] = str(workspace_path / "torch")     # PyTorch models
os.environ['XDG_CACHE_HOME'] = str(workspace_path)           # Generic cache (used by some libs)

# BitsAndBytes 0.45.0 has native CUDA 12.4+ support with auto-detection
# PyTorch 2.6.x comes with CUDA 12.6, which is compatible with BitsAndBytes 0.45.0
# Set BNB_CUDA_VERSION=126 for CUDA 12.6 (PyTorch 2.6.x default)
os.environ['BNB_CUDA_VERSION'] = '126'
print(f"🔧 BitsAndBytes: Set BNB_CUDA_VERSION=126 for CUDA 12.6 (PyTorch 2.6.x, BnB 0.45.0 native support)")

# Verify model cache directories exist
required_cache_dirs = [
    workspace_path / "huggingface",  # HF models stored directly here (legacy transformers structure)
    workspace_path / "torch",  # PyTorch models

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
if not mixtral_model_found:
    print("\n" + "=" * 80)
    print("⚠️  WARNING: Mixtral model not found in cache!")
    print("=" * 80)
    print(f"Expected location: /runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/")
    print("\nThis will cause the model to download (~93GB) on first use,")
    print("which may take 15-30 minutes.")
    print("\n⚠️  CONTINUING - Model will be downloaded on first /prompt request")
    
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
    print("\nTo pre-cache for faster startup:")
    print("1. Copy the ACTUAL CACHE STRUCTURE output above")
    print("2. Update handler.py cache paths to match your actual structure")
    print("3. Or reorganize your network volume to match expected structure:")
    print("   - Ensure models are in: /runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/")
    print("4. Download models locally: python download_models_locally.py")
    print("5. Upload: tar -czf model_cache.tar.gz model_cache/")
    print("6. Extract in volume: tar -xzf model_cache.tar.gz -C /runpod-volume/")
    print("=" * 80)
    # REMOVED: sys.exit(1) - Allow worker to continue and download model on first use
else:
    print(f"✅ Mixtral model found in cache - will use cached version")

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
    print("\n⚠️  WARNING: Missing environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nPlease add these in RunPod endpoint settings under 'Environment Variables'")
    print("⚠️  CONTINUING - Some features may not work without these variables")
    # REMOVED: sys.exit(1) - Allow worker to continue for debugging

# COMPREHENSIVE STARTUP DIAGNOSTICS
print("\n" + "=" * 80)
print("🔍 STARTUP DIAGNOSTICS")
print("=" * 80)

# System info
import platform
import subprocess
print(f"\n🖥️  SYSTEM INFORMATION:")
print(f"   OS: {platform.system()} {platform.release()}")
print(f"   Python: {platform.python_version()}")
print(f"   Platform: {platform.platform()}")

# GPU info via nvidia-smi
print(f"\n🎮 GPU INFORMATION:")
try:
    nvidia_smi = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
        timeout=10
    ).decode().strip()
    print(f"   {nvidia_smi}")
except Exception as e:
    print(f"   ⚠️  Could not get GPU info via nvidia-smi: {e}")

# Check GPU availability and memory
try:
    import torch
    
    # CRITICAL: Verify PyTorch version matches expected version
    # Prevents silent failures from PyTorch upgrades breaking compatibility
    EXPECTED_PYTORCH_MAJOR_MINOR = "2.6"  # ONLY 2.6.x supports RTX 5090 sm_120! (2.7.x removed support)
    actual_major_minor = '.'.join(torch.__version__.split('.')[:2])
    
    if actual_major_minor != "2.6":
        print("=" * 80)
        print("🔴 CRITICAL: PyTorch version mismatch!")
        print("=" * 80)
        print(f"Expected: ONLY {EXPECTED_PYTORCH_MAJOR_MINOR}.x")
        print(f"Actual: {torch.__version__}")
        print("\n🔴 CRITICAL COMPATIBILITY ISSUE:")
        print("- PyTorch 2.6.0-2.6.2: HAS RTX 5090 (sm_120) support ✅")
        print("- PyTorch 2.7.x: REMOVED sm_120 support (only up to sm_90) ❌")
        print("- PyTorch 2.5.1: Only supports up to sm_90 (Hopper) ❌")
        print("\nYour RTX 5090 has sm_120 compute capability!")
        print("Using PyTorch 2.7+ will cause:")
        print("  - WARNING: 'sm_120 is not compatible with current PyTorch'")
        print("  - Model loading will fail or use fallback mode")
        print("  - Severely degraded performance or crashes")
        print("\nPossible causes:")
        print("1. constraints.txt allowed 2.7.x (should be <2.7.0)")
        print("2. pip resolver upgraded to 2.7.x despite constraints")
        print("3. PyTorch index had 2.7.x as default")
        print("\n🔧 FIX: Rebuild Docker image with torch>=2.6.0,<2.7.0")
        print("=" * 80)
        print("⚠️  CONTINUING - But expect GPU compatibility warnings and failures")
        # REMOVED: sys.exit(1) - Allow worker to continue for debugging
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC: PyTorch & CUDA Configuration")
    print("=" * 60)
    print(f"✅ PyTorch Version: {torch.__version__}")
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
        if gpu_memory < 16:
            print(f"⚠️  WARNING: Mixtral 8x7B 4-bit requires ~16-18GB VRAM, you have {gpu_memory:.1f}GB")
            print("   Model loading may fail or run very slowly")
        else:
            print(f"✅ Sufficient VRAM for Mixtral 8x7B 4-bit NF4 (~16-18GB required, {gpu_memory:.1f}GB available)")
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
        
        # Check CUDA setup
        print(f"🔧 BNB_CUDA_VERSION env: {os.environ.get('BNB_CUDA_VERSION', 'NOT SET (will auto-detect)')}")
        
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

# Disk space diagnostics
print("\n" + "=" * 60)
print("💾 DISK SPACE DIAGNOSTICS")
print("=" * 60)
try:
    import shutil
    
    # Check /runpod-volume (network volume)
    if workspace_path.exists():
        total, used, free = shutil.disk_usage(str(workspace_path))
        total_gb = total // (2**30)
        used_gb = used // (2**30)
        free_gb = free // (2**30)
        usage_percent = (used / total) * 100
        print(f"📁 /runpod-volume:")
        print(f"   Total: {total_gb}GB")
        print(f"   Used: {used_gb}GB ({usage_percent:.1f}%)")
        print(f"   Free: {free_gb}GB")
        
        if free_gb < 50:
            print(f"   ⚠️  WARNING: Low disk space (< 50GB free)")
            print(f"      Mixtral model requires ~93GB for download")
    else:
        print(f"   ⚠️  /runpod-volume not accessible")
    
    # Check root filesystem
    total, used, free = shutil.disk_usage("/")
    print(f"📁 / (root):")
    print(f"   Total: {total // (2**30)}GB")
    print(f"   Used: {used // (2**30)}GB")
    print(f"   Free: {free // (2**30)}GB")
    
except Exception as e:
    print(f"⚠️  Disk space check failed: {e}")

print("=" * 80)
print("✅ STARTUP DIAGNOSTICS COMPLETE")
print("=" * 80 + "\n")

print("Attempting to import runpod...", flush=True)
try:
    import runpod  # type: ignore
    print(f"✅ RunPod SDK imported successfully (version: {runpod.__version__ if hasattr(runpod, '__version__') else 'unknown'})", flush=True)
except ImportError as e:
    print(f"❌ Failed to import runpod: {e}", flush=True)
    print(f"   ImportError details: {type(e).__name__}: {str(e)}", flush=True)
    runpod = None  # Will be available in RunPod environment
except Exception as e:
    print(f"❌ Unexpected error importing runpod: {e}", flush=True)
    import traceback
    traceback.print_exc()
    runpod = None

import asyncio
import logging
from typing import Any, Dict

# Import FastAPI app and endpoints
from app.main import prompt_endpoint
from app.main import PromptInput

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GPU Memory management
GPU_MEMORY_THRESHOLD_GB = 4.0  # Minimum free VRAM required to accept request
# LLM-only endpoint - no extraction memory requirements
CLASSIFICATION_MEMORY_ESTIMATE_GB = 22.0  # Mixtral 8x7B 8-bit (reduced from 24.0 to account for system overhead)

# Concurrency control
# LLM-only service: classification endpoint runs on GPU
# Keep concurrency limited to prevent CUDA OOM errors
import asyncio
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
        
        
        # Create mock request object for API verification
        mock_request = MockRequest(api_key=api_key)
        
        # Handle /prompt endpoint
        if endpoint == '/prompt':
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
                    
                    logger.error("="*70)
                    
                    # Return error response (don't raise - RunPod needs a response)
                    return {
                        "success": False,
                        "error": error_msg,
                        "error_type": error_type,
                        "traceback": error_traceback[:2000],
                        "diagnostics": {
                            "bnb_cuda_version": os.environ.get('BNB_CUDA_VERSION', 'NOT SET'),
                            "pytorch_cuda": torch.version.cuda if torch.cuda.is_available() else None,
                            "gpu_available": torch.cuda.is_available(),
                            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                        }
                    }
        
        elif endpoint == '/health':
            # Health check endpoint
            logger.info(f"[RunPod] ❤️  Health check requested")
            
            health_status = {
                "status": "healthy",
                "service": "ZopilotGPU",
                "timestamp": str(Path.cwd()),  # Using Path import for timestamp
                "gpu_available": torch.cuda.is_available(),
                "model_loaded": False,
                "free_memory_gb": 0.0,
                "total_memory_gb": 0.0
            }
            
            # GPU diagnostics
            if torch.cuda.is_available():
                try:
                    torch.cuda.synchronize()
                    device_props = torch.cuda.get_device_properties(0)
                    total_memory = device_props.total_memory
                    allocated_memory = torch.cuda.memory_allocated(0)
                    reserved_memory = torch.cuda.memory_reserved(0)
                    free_memory = total_memory - reserved_memory
                    
                    health_status.update({
                        "total_memory_gb": total_memory / (1024**3),
                        "allocated_memory_gb": allocated_memory / (1024**3),
                        "reserved_memory_gb": reserved_memory / (1024**3),
                        "free_memory_gb": free_memory / (1024**3),
                        "gpu_name": torch.cuda.get_device_name(0),
                        "cuda_version": torch.version.cuda
                    })
                    
                    # Check if model is loaded (imported check)
                    try:
                        from app.llama_utils import model_cache
                        health_status["model_loaded"] = "llm" in model_cache and model_cache["llm"] is not None
                        if health_status["model_loaded"]:
                            logger.info(f"[RunPod] ✅ Model is loaded and ready")
                        else:
                            logger.info(f"[RunPod] ⚠️  Model not yet loaded (will load on first request)")
                    except Exception as e:
                        health_status["model_check_error"] = str(e)
                        logger.warning(f"[RunPod] ⚠️  Could not check model status: {e}")
                        
                except Exception as e:
                    health_status["gpu_error"] = str(e)
                    logger.warning(f"[RunPod] ⚠️  GPU diagnostics failed: {e}")
            
            logger.info(f"[RunPod] ✅ Health check completed: {health_status['status']}")
            return health_status
        
        else:
            # Unknown endpoint
            logger.error(f"[RunPod] ❌ Unknown endpoint: {endpoint}")
            return {
                "success": False,
                "error": f"Unknown endpoint: {endpoint}. Supported: /prompt, /health"
            }
    
    except Exception as e:
        import traceback
        logger.error("="*70)
        logger.error("[RunPod] FATAL ERROR IN HANDLER")
        logger.error("="*70)
        logger.error(f"Error: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()[:2000]
        }


# Start RunPod serverless worker
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("🚀 Starting RunPod Serverless Worker for ZopilotGPU")
    logger.info("=" * 70)
    logger.info(f"✅ Handler function: async_handler")
    logger.info(f"✅ Supported endpoints: /prompt, /health")
    logger.info(f"✅ GPU Memory Threshold: {GPU_MEMORY_THRESHOLD_GB}GB")
    logger.info(f"✅ Model Memory Estimate: {CLASSIFICATION_MEMORY_ESTIMATE_GB}GB")
    logger.info(f"✅ Concurrency: {classification_semaphore._value} concurrent requests")
    logger.info("=" * 70)
    
    if runpod is None:
        logger.error("❌ RunPod SDK not available!")
        logger.error("   Install with: pip install runpod")
        sys.exit(1)
    
    #  Pre-load models before starting RunPod worker
    # In RunPod serverless, FastAPI lifespan never runs (no server started)
    # So we must initialize models here before worker registration
    logger.info("🔧 Pre-loading models (RunPod serverless requires manual initialization)...")
    try:
        from app.llama_utils import get_llama_processor
        logger.info("📥 Loading Mixtral model...")
        get_llama_processor()  # This loads the model into memory
        logger.info("✅ Models pre-loaded successfully")
    except Exception as e:
        logger.error(f"⚠️ Failed to pre-load models: {e}")
        logger.error("   Models will be loaded on first request (slower cold start)")
        import traceback
        logger.error(traceback.format_exc())
    
    try:
        print("=" * 70, flush=True)
        print("🎯 ABOUT TO CALL runpod.serverless.start()", flush=True)
        print(f"Handler function: {async_handler}", flush=True)
        print("=" * 70, flush=True)
        logger.info("🎯 Calling runpod.serverless.start()...")
        runpod.serverless.start({"handler": async_handler})
        logger.info("✅ RunPod serverless started successfully")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}", flush=True)
        logger.error(f"❌ Failed to start RunPod serverless: {e}")
        import traceback
        traceback.print_exc()
        logger.error(traceback.format_exc())
        raise
