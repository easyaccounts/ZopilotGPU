import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import aiofiles
from pathlib import Path
import torch  # For CUDA OOM error handling

from app.llama_utils import generate_with_llama, get_llama_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models

class PromptInput(BaseModel):
    prompt: str = Field(..., description="Natural language instruction for Mixtral")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context data")
    
class PromptResponse(BaseModel):
    success: bool
    output: str
    metadata: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str
    models_loaded: Dict[str, bool]
    gpu_available: bool
    memory_info: Optional[Dict[str, Any]] = None

# Retry prevention: Track recent extraction requests to avoid duplicate processing
recent_extractions = {}  # {document_id: timestamp}
EXTRACTION_DEDUP_WINDOW = 60  # seconds

# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    logger.info("Starting EasyAccountsGPU Service...")
    
    try:
        # Initialize models in background
        await initialize_models()
        logger.info("Models initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize models: {str(e)}")
        raise
    finally:
        logger.info("Shutting down EasyAccountsGPU Service...")

async def initialize_models():
    """Initialize models in background."""
    def init_llama():
        try:
            get_llama_processor()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Llama: {str(e)}")
            return False
    
    
    # Initialize in background
    loop = asyncio.get_event_loop()
    await asyncio.gather(
        loop.run_in_executor(None, init_llama),
        return_exceptions=True
    )

# Create FastAPI app
app = FastAPI(
    title="ZopilotGPU API",
    description="LLM prompting with Mixtral 8x7B on RTX 5090",
    version="2.0.0",
    lifespan=lifespan
)

# Security: Get allowed origins from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
if ALLOWED_ORIGINS != "*":
    # Parse comma-separated origins
    allowed_origins_list = [origin.strip() for origin in ALLOWED_ORIGINS.split(",")]
else:
    allowed_origins_list = ["*"]

logger.info(f"CORS configured with origins: {allowed_origins_list}")

# CORS middleware with environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Authentication
API_KEY = os.getenv("ZOPILOT_GPU_API_KEY")
if API_KEY:
    logger.info("API key authentication enabled")
else:
    logger.warning("⚠️  No API key set - service is OPEN! Set ZOPILOT_GPU_API_KEY for production")

async def verify_api_key(request: Request):
    """Verify API key from request headers."""
    if not API_KEY:
        return True  # No auth required if API_KEY not set
    
    auth_header = request.headers.get("Authorization")
    api_key_header = request.headers.get("X-API-Key")
    
    # Support both Authorization: Bearer <key> and X-API-Key: <key>
    if auth_header and auth_header.startswith("Bearer "):
        provided_key = auth_header[7:]
    elif api_key_header:
        provided_key = api_key_header
    else:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide via 'Authorization: Bearer <key>' or 'X-API-Key: <key>'"
        )
    
    if provided_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return True

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

@app.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint for RunPod monitoring."""
    # Health check optionally uses API key (allows monitoring without auth)
    skip_auth = os.getenv("HEALTH_CHECK_PUBLIC", "true").lower() == "true"
    if not skip_auth:
        await verify_api_key(request)
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        
        memory_info = None
        if gpu_available:
            memory_info = {
                "total": torch.cuda.get_device_properties(0).total_memory,
                "allocated": torch.cuda.memory_allocated(0),
                "cached": torch.cuda.memory_reserved(0)
            }
        
        # Test model availability
        models_loaded = {
            "llama": False,
            "docstrange": False
        }
        
        try:
            get_llama_processor()
            models_loaded["llama"] = True
        except:
            pass
        
        # Docstrange removed - LLM-only endpoint
        models_loaded["docstrange"] = False
        return HealthResponse(
            status="healthy",
            models_loaded=models_loaded,
            gpu_available=gpu_available,
            memory_info=memory_info
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/warmup")
async def warmup_endpoint(request: Request):
    """
    Pre-download and cache all models to network volume.
    Call this once after deployment to avoid cold start on first real request.
    
    Usage: curl -X POST https://your-endpoint/warmup -H "X-API-Key: your-key"
    """
    await verify_api_key(request)
    
    try:
        import time
        from pathlib import Path
        
        logger.info("🔥 Warmup requested - pre-caching models...")
        start_time = time.time()
        results = {}
        
        # Check if models already cached
        volume_path = Path("/workspace")
        mixtral_cached = (volume_path / "huggingface" / "hub").exists()
        
        if mixtral_cached:
            logger.info("✅ Models already cached - skipping download")
            return {
                "status": "already_cached",
                "message": "Models already exist in cache",
                "volume_path": str(volume_path)
            }
        
        # Docstrange removed - LLM-only endpoint
        results["docstrange"] = {"status": "not_applicable"}
        
        # Download Mixtral
        if not mixtral_cached:
            logger.info("📦 Downloading Mixtral 8x7B model (this may take 15-25 min)...")
            mix_start = time.time()
            get_llama_processor()
            results["mixtral"] = {
                "status": "downloaded",
                "time_seconds": time.time() - mix_start
            }
        else:
            results["mixtral"] = {"status": "already_cached"}
        
        total_time = time.time() - start_time
        logger.info(f"✅ Warmup complete in {total_time/60:.1f} minutes")
        
        return {
            "status": "success",
            "message": "Models cached successfully",
            "total_time_seconds": total_time,
            "models": results
        }
        
    except Exception as e:
        logger.error(f"❌ Warmup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Warmup failed: {str(e)}")

# ============================================
# ENDPOINT 1: DOCUMENT EXTRACTION
# ============================================
@app.post("/prompt")
async def prompt_endpoint(request: Request, data: PromptInput):
    """
    Send prompt to Mixtral 8x7B and get AI-generated output.
    
    Takes natural language prompt (with optional context data) and returns
    Mixtral's structured response (typically a journal entry dict).
    
    Response format: {"success": bool, "output": dict|str, "metadata": {...}}
    No Pydantic validation to allow dynamic response structure from Mixtral.
    
    Requires API key authentication.
    """
    await verify_api_key(request)
    
    try:
        prompt_start = asyncio.get_event_loop().time()
        logger.info(f"[PROMPT] 📨 Received classification request")
        logger.info(f"[PROMPT] 📝 Prompt length: {len(data.prompt)} chars")
        logger.info(f"[PROMPT] 🎯 Sending to Mixtral: {data.prompt[:100]}...")
        
        # Generate with Mixtral (runs in thread pool to avoid blocking)
        logger.info(f"[PROMPT] 🔄 Running generation in thread pool...")
        output = await asyncio.get_event_loop().run_in_executor(
            None, generate_with_llama, data.prompt, data.context
        )
        
        prompt_time = asyncio.get_event_loop().time() - prompt_start
        logger.info(f"[PROMPT] ⏱️  Total prompt processing time: {prompt_time:.1f}s")
        
        # Preserve output structure (dict or string)
        # generate_with_llama returns dict (journal entry), keep it as-is
        response_data = {
            "success": True,
            "output": output,  # Keep dict structure (don't stringify)
            "metadata": {
                "generated_at": get_timestamp(),
                "prompt_length": len(data.prompt),
                "context_provided": data.context is not None,
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "output_type": type(output).__name__,
                "processing_time_seconds": round(prompt_time, 2)
            }
        }
        
        logger.info(f"[PROMPT] ✅ Success! Output type: {type(output).__name__}, response size: {len(str(output))} chars")
        
        # Return plain JSON (no Pydantic validation) to preserve dynamic structure
        return JSONResponse(content=response_data)
        
    except RuntimeError as e:
        # Model initialization errors
        error_msg = str(e)
        logger.error(f"[PROMPT] Model error: {error_msg}")
        if "not initialized" in error_msg.lower():
            raise HTTPException(status_code=503, detail="Model not loaded. Service starting up.")
        raise HTTPException(status_code=500, detail=f"Model error: {error_msg}")
        
    except torch.cuda.OutOfMemoryError:
        # VRAM exhausted
        logger.error(f"[PROMPT] CUDA OOM - VRAM exhausted")
        torch.cuda.empty_cache()
        raise HTTPException(status_code=507, detail="GPU memory exhausted. Try again in a moment.")
        
    except Exception as e:
        # Other errors
        logger.error(f"[PROMPT] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prompt generation failed: {str(e)}")

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_timestamp() -> str:
    """Get current timestamp."""
    from datetime import datetime
    return datetime.now().isoformat()

if __name__ == "__main__":
    import uvicorn
    
    # Configure for production
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # Disable reload in production
        workers=1,     # Single worker for GPU memory management
        timeout_keep_alive=30,
        access_log=True
    )