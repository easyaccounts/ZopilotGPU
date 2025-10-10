"""
RunPod Serverless Handler for ZopilotGPU
Wraps FastAPI endpoints for RunPod serverless format
"""
import os
import sys
from pathlib import Path

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
if not mixtral_model_found:
    print("\n" + "=" * 80)
    print("❌ CRITICAL ERROR: Mixtral model not found in cache!")
    print("=" * 80)
    print(f"Expected location: /runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/")
    print("\nThis will cause the model to download (~93GB) on every cold start,")
    print("wasting GPU credits and causing 15-30 minute delays.")
    print("\n🛑 STOPPING EXECUTION to prevent unnecessary downloads and costs.")
    
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
    print("\nTo fix:")
    print("1. Copy the ACTUAL CACHE STRUCTURE output above")
    print("2. Update handler.py cache paths to match your actual structure")
    print("3. Or reorganize your network volume to match expected structure:")
    print("   - Ensure models are in: /runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/")
    print("4. Download models locally: python download_models_locally.py")
    print("5. Upload: tar -czf model_cache.tar.gz model_cache/")
    print("6. Extract in volume: tar -xzf model_cache.tar.gz -C /runpod-volume/")
    print("=" * 80)
    sys.exit(1)

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
try:
    import torch
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
        print(f"🎮 GPU: {gpu_name}")
        print(f"💾 VRAM: {gpu_memory:.1f} GB")
        
        # Warn if insufficient memory for Mixtral 8x7B
        if gpu_memory < 22:
            print(f"⚠️  WARNING: Mixtral 8x7B requires ~24GB VRAM, you have {gpu_memory:.1f}GB")
            print("   Model loading may fail or run very slowly")
    else:
        print("⚠️  No GPU detected - will fall back to CPU (very slow)")
except ImportError:
    print("⚠️  PyTorch not available for GPU check")

print("=" * 60)

try:
    import runpod  # type: ignore
except ImportError:
    runpod = None  # Will be available in RunPod environment

import asyncio
import logging
from typing import Any, Dict

# Import FastAPI app and endpoints
from app.main import extract_endpoint, prompt_endpoint
from app.main import ExtractionInput, PromptInput

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
        
        logger.info(f"[RunPod] Processing endpoint: {endpoint}")
        
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
                logger.info(f"[RunPod] Classification started (GPU locked)")
                input_data = PromptInput(**data)
                result = await prompt_endpoint(mock_request, input_data)
                
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
        logger.error(f"[RunPod] Handler error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
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
    if runpod is None:
        logger.error("runpod package not installed. Install with: pip install runpod")
        exit(1)
    
    logger.info("Starting RunPod serverless worker for ZopilotGPU...")
    runpod.serverless.start({"handler": handler})
