"""
RunPod Serverless Handler for ZopilotGPU
Wraps FastAPI endpoints for RunPod serverless format
"""
import os
import sys
from pathlib import Path

# CRITICAL: Ensure /root/.cache symlink points to /workspace for Docstrange
# This must happen BEFORE any model imports
cache_path = Path("/root/.cache")
workspace_path = Path("/workspace")

# Handle /root/.cache symlink - remove if it's a directory or file, create if missing
if cache_path.exists() and not cache_path.is_symlink():
    import shutil
    try:
        cache_type = 'dir' if cache_path.is_dir() else 'file'
        if cache_path.is_dir():
            shutil.rmtree(cache_path, ignore_errors=True)
        else:
            # It's a file, remove it
            cache_path.unlink(missing_ok=True)
        print(f"🗑️  Removed existing /root/.cache (was {cache_type})")
    except Exception as e:
        print(f"⚠️  Warning: Could not remove existing cache: {e}")

if not cache_path.exists():
    try:
        cache_path.symlink_to(workspace_path)
        print(f"✅ Created symlink: /root/.cache -> /workspace")
    except Exception as e:
        print(f"⚠️  Warning: Could not create symlink: {e}")
        # Try creating as directory if symlink fails
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: /root/.cache (fallback)")
        except Exception as e2:
            print(f"❌ CRITICAL: Cannot create cache directory: {e2}")

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


class MockRequest:
    """Mock Request object for API key verification"""
    def __init__(self, api_key: str = None):
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'


async def async_handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle RunPod serverless job
    
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
        
        # Create mock request with API key
        mock_request = MockRequest(api_key=api_key)
        
        if endpoint == '/extract':
            # Handle extraction
            input_data = ExtractionInput(**data)
            result = await extract_endpoint(mock_request, input_data)
            return result.dict()
            
        elif endpoint == '/prompt':
            # Handle prompting
            input_data = PromptInput(**data)
            result = await prompt_endpoint(mock_request, input_data)
            return result.dict()
            
        elif endpoint == '/health':
            # Health check
            return {
                "status": "healthy",
                "service": "ZopilotGPU",
                "model": "Mixtral-8x7B-Instruct-v0.1"
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


# Rename async_handler to handler (RunPod supports async handlers directly)
handler = async_handler


# Start RunPod serverless worker
if __name__ == "__main__":
    if runpod is None:
        logger.error("runpod package not installed. Install with: pip install runpod")
        exit(1)
    
    logger.info("Starting RunPod serverless worker for ZopilotGPU...")
    runpod.serverless.start({"handler": handler})
