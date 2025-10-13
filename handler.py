"""
RunPod Serverless Handler for ZopilotGPU
Clean implementation for Mixtral 8x7B classification
"""
# CRITICAL: Print before ANY imports to confirm Python starts
print("HANDLER.PY STARTING - BEFORE IMPORTS", flush=True)

import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict

print("HANDLER.PY - IMPORTS COMPLETE", flush=True)

# ============================================
# 1. ENVIRONMENT SETUP
# ============================================
print("=" * 70, flush=True)
print("🚀 ZopilotGPU Handler Starting", flush=True)
print(f"Python: {sys.version.split()[0]}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print("=" * 70, flush=True)

# Configure RunPod network volume for model caching
VOLUME_PATH = Path("/runpod-volume")
os.environ['HF_HOME'] = str(VOLUME_PATH / "huggingface")
os.environ['TRANSFORMERS_CACHE'] = str(VOLUME_PATH / "huggingface")
os.environ['HF_HUB_CACHE'] = str(VOLUME_PATH / "huggingface")
os.environ['TORCH_HOME'] = str(VOLUME_PATH / "torch")
os.environ['XDG_CACHE_HOME'] = str(VOLUME_PATH)
os.environ['BNB_CUDA_VERSION'] = '128'  # CUDA 12.8 for PyTorch 2.8.0+cu128

print(f"✅ Model cache: {VOLUME_PATH / 'huggingface'}", flush=True)
print(f"✅ BNB_CUDA_VERSION: 128 (CUDA 12.8 for sm_120 support)", flush=True)

# Verify volume exists and is writable
if VOLUME_PATH.exists() and VOLUME_PATH.is_dir():
    try:
        (VOLUME_PATH / ".test").write_text("test")
        (VOLUME_PATH / ".test").unlink()
        print(f"✅ Volume verified and writable", flush=True)
    except Exception as e:
        print(f"⚠️  Volume not writable: {e}", flush=True)
else:
    print(f"⚠️  Volume not found: {VOLUME_PATH}", flush=True)

# Verify environment variables
print("\n📋 Environment Check:", flush=True)
required_vars = ['HUGGING_FACE_TOKEN', 'ZOPILOT_GPU_API_KEY']
for var in required_vars:
    value = os.getenv(var)
    if value:
        print(f"  ✅ {var}: {value[:10]}...", flush=True)
    else:
        print(f"  ⚠️  {var}: NOT SET", flush=True)

# ============================================
# 2. IMPORT DEPENDENCIES
# ============================================
print("\n📦 Importing dependencies...", flush=True)

try:
    import torch
    print(f"  ✅ PyTorch {torch.__version__}", flush=True)
    
    # Simple GPU detection
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"  ✅ GPU: {gpu_name} ({gpu_memory:.0f}GB)", flush=True)
        print(f"  ✅ CUDA {torch.version.cuda}", flush=True)
    else:
        print(f"  ⚠️  No GPU detected", flush=True)
        print(f"  ℹ️  CUDA available: {torch.cuda.is_available()}", flush=True)
        print(f"  ℹ️  GPU count: {torch.cuda.device_count()}", flush=True)
        
        # Check for /dev/nvidia* devices
        import glob
        nvidia_devs = glob.glob('/dev/nvidia*')
        if nvidia_devs:
            print(f"  ℹ️  Found {len(nvidia_devs)} /dev/nvidia* devices", flush=True)
        else:
            print(f"  ⚠️  No /dev/nvidia* devices found - GPU not mounted!", flush=True)
        
        # Check NVIDIA_VISIBLE_DEVICES env var
        nvd = os.getenv('NVIDIA_VISIBLE_DEVICES', 'NOT SET')
        print(f"  ℹ️  NVIDIA_VISIBLE_DEVICES: {nvd}", flush=True)
        
except ImportError as e:
    print(f"  ❌ PyTorch import failed: {e}", flush=True)
    sys.exit(1)

try:
    import runpod
    print(f"  ✅ RunPod SDK {getattr(runpod, '__version__', 'unknown')}", flush=True)
except ImportError as e:
    print(f"  ❌ RunPod SDK not installed: {e}", flush=True)
    print(f"     Install with: pip install runpod", flush=True)
    sys.exit(1)

try:
    import asyncio
    from app.main import prompt_endpoint, PromptInput
    print(f"  ✅ FastAPI endpoint imported", flush=True)
except ImportError as e:
    print(f"  ❌ Failed to import FastAPI endpoint: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# 3. MODEL INITIALIZATION
# ============================================
print("\n🔧 Pre-loading Mixtral model from cache...", flush=True)
model_loaded = False

try:
    from app.llama_utils import get_llama_processor
    import time
    start_time = time.time()
    
    # Load model (this will use cached version from /runpod-volume/huggingface)
    get_llama_processor()
    load_time = time.time() - start_time
    
    print(f"✅ Mixtral model loaded in {load_time:.1f}s", flush=True)
    model_loaded = True
    
    # Report GPU memory after loading
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / (1024**3)
        total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"  GPU Memory: {allocated:.1f}GB used / {total:.0f}GB total", flush=True)
        
except Exception as e:
    print(f"⚠️  Model pre-load failed: {e}", flush=True)
    print(f"   Model will be loaded on first request (slower)", flush=True)
    import traceback
    traceback.print_exc()
    model_loaded = False

# ============================================
# 4. CALLBACK HELPER
# ============================================
async def send_callback(job_id: str, callback_url: str, callback_api_key: str, status: str, result: Dict[str, Any] = None, error: str = None):
    """
    Send callback to backend when job completes
    Replaces polling with push-based updates
    """
    try:
        import aiohttp
        
        payload = {
            'job_id': job_id,
            'status': status,
            'api_key': callback_api_key
        }
        
        if result:
            payload['result'] = result
        if error:
            payload['error'] = error
        
        logger.info(f"[Callback] Sending {status} callback for job {job_id} to {callback_url}")
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(callback_url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"[Callback] ✅ Callback successful for job {job_id}")
                else:
                    logger.error(f"[Callback] ❌ Callback failed for job {job_id}: HTTP {response.status}")
                    resp_text = await response.text()
                    logger.error(f"[Callback] Response: {resp_text[:500]}")
    except Exception as e:
        logger.error(f"[Callback] ❌ Failed to send callback for job {job_id}: {e}")
        import traceback
        logger.error(traceback.format_exc()[:1000])

# ============================================
# 5. HANDLER FUNCTION
# ============================================
class MockRequest:
    """Mock Request object for API key verification"""
    def __init__(self, api_key: str = None):
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'

async def async_handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod serverless handler for Mixtral 8x7B prompting.
    
    Expected input:
    {
        "input": {
            "endpoint": "/prompt" or "/health",
            "data": {
                "prompt": "your prompt here",
                "context": {...}  // optional
            },
            "api_key": "your_api_key"  // optional if set in env
        }
    }
    """
    try:
        job_input = job.get('input', {})
        endpoint = job_input.get('endpoint')
        data = job_input.get('data', {})
        api_key = job_input.get('api_key')
        callback_url = job_input.get('callback_url')  # ✅ NEW: Get callback URL
        callback_api_key = job_input.get('callback_api_key')  # ✅ NEW: Get callback auth
        
        logger.info(f"[RunPod] Request: {endpoint}")
        if callback_url:
            logger.info(f"[RunPod] Callback URL: {callback_url}")
        
        # Create mock request for API verification
        mock_request = MockRequest(api_key=api_key)
        
        # Handle /prompt endpoint
        if endpoint == '/prompt':
            logger.info(f"[RunPod] Processing prompt ({len(data.get('prompt', ''))} chars)")
            
            try:
                # Validate and create input
                input_data = PromptInput(**data)
                
                # Call prompt endpoint
                result = await prompt_endpoint(mock_request, input_data)
                
                # Convert result to dict
                if hasattr(result, 'body'):
                    import json
                    result_dict = json.loads(result.body.decode('utf-8'))
                elif isinstance(result, dict):
                    result_dict = result
                elif hasattr(result, 'dict'):
                    result_dict = result.dict()
                else:
                    result_dict = {"success": True, "output": str(result)}
                
                # ✅ NEW: If callback URL provided, send callback
                if callback_url:
                    await send_callback(
                        job_id=job.get('id'),
                        callback_url=callback_url,
                        callback_api_key=callback_api_key,
                        status='COMPLETED',
                        result=result_dict
                    )
                
                return result_dict
                    
            except Exception as e:
                logger.error(f"[RunPod] Prompt failed: {e}")
                import traceback
                error_result = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()[:2000]
                }
                
                # ✅ NEW: If callback URL provided, send error callback
                if callback_url:
                    await send_callback(
                        job_id=job.get('id'),
                        callback_url=callback_url,
                        callback_api_key=callback_api_key,
                        status='FAILED',
                        error=str(e)
                    )
                
                return error_result
        
        # Handle /health endpoint
        elif endpoint == '/health':
            logger.info(f"[RunPod] Health check")
            
            health = {
                "status": "healthy",
                "service": "ZopilotGPU",
                "model_loaded": model_loaded,
                "gpu_available": torch.cuda.is_available()
            }
            
            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_memory
                allocated = torch.cuda.memory_allocated(0)
                health.update({
                    "gpu_name": torch.cuda.get_device_name(0),
                    "gpu_memory_total_gb": round(total / (1024**3), 1),
                    "gpu_memory_used_gb": round(allocated / (1024**3), 1),
                    "gpu_memory_free_gb": round((total - allocated) / (1024**3), 1)
                })
            
            return health
        
        # Unknown endpoint
        else:
            logger.error(f"[RunPod] Unknown endpoint: {endpoint}")
            return {
                "success": False,
                "error": f"Unknown endpoint: {endpoint}",
                "supported_endpoints": ["/prompt", "/health"]
            }
    
    except Exception as e:
        logger.error(f"[RunPod] Handler error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()[:2000]
        }

# ============================================
# 5. START RUNPOD WORKER
# ============================================
if __name__ == "__main__":
    print("\n" + "=" * 70, flush=True)
    print("🚀 Starting RunPod Serverless Worker", flush=True)
    print("=" * 70, flush=True)
    print(f"  Handler: async_handler", flush=True)
    print(f"  Endpoints: /prompt, /health", flush=True)
    print(f"  Model: Mixtral-8x7B-Instruct-v0.1", flush=True)
    print(f"  Cached: {model_loaded}", flush=True)
    print("=" * 70, flush=True)
    
    try:
        logger.info("Starting RunPod worker...")
        runpod.serverless.start({"handler": async_handler})
        logger.info("RunPod worker registered successfully")
    except Exception as e:
        logger.error(f"Failed to start RunPod worker: {e}")
        import traceback
        traceback.print_exc()
        raise
