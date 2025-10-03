"""
RunPod Serverless Handler for ZopilotGPU
Wraps FastAPI endpoints for RunPod serverless format
"""
import os
import sys

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


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous wrapper for async handler
    Required by RunPod serverless
    """
    try:
        return asyncio.run(async_handler(job))
    except Exception as e:
        logger.error(f"[RunPod] Sync handler error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


# Start RunPod serverless worker
if __name__ == "__main__":
    if runpod is None:
        logger.error("runpod package not installed. Install with: pip install runpod")
        exit(1)
    
    logger.info("Starting RunPod serverless worker for ZopilotGPU...")
    runpod.serverless.start({"handler": handler})
