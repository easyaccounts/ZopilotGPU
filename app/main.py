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

from app.docstrange_utils import extract_with_docstrange, get_docstrange_processor
from app.llama_utils import generate_with_llama, get_llama_processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models
class ExtractionInput(BaseModel):
    document_url: str = Field(..., description="Pre-signed URL to download document from R2 storage")
    document_id: Optional[str] = Field(None, description="Document ID for tracking")
    document_type: Optional[str] = Field(None, description="Type of document (invoice, receipt, bill, etc.)")

class ExtractionResponse(BaseModel):
    success: bool
    document_id: Optional[str]
    extraction_method: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]

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
    
    def init_docstrange():
        try:
            get_docstrange_processor()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Docstrange: {str(e)}")
            return False
    
    # Initialize in background
    loop = asyncio.get_event_loop()
    await asyncio.gather(
        loop.run_in_executor(None, init_llama),
        loop.run_in_executor(None, init_docstrange),
        return_exceptions=True
    )

# Create FastAPI app
app = FastAPI(
    title="ZopilotGPU API",
    description="Document extraction with Docstrange and AI prompting with Mixtral 8x7B",
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
        
        try:
            get_docstrange_processor()
            models_loaded["docstrange"] = True
        except:
            pass
        
        return HealthResponse(
            status="healthy",
            models_loaded=models_loaded,
            gpu_available=gpu_available,
            memory_info=memory_info
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# ============================================
# ENDPOINT 1: DOCUMENT EXTRACTION
# ============================================
@app.post("/extract", response_model=ExtractionResponse)
async def extract_endpoint(request: Request, data: ExtractionInput):
    """
    Extract structured data from document using Docstrange.
    
    Downloads document from pre-signed URL, processes with Docstrange OCR,
    and returns structured JSON data (invoice fields, receipt data, etc.).
    
    Requires API key authentication.
    """
    await verify_api_key(request)
    
    try:
        logger.info(f"[EXTRACT] Document ID: {data.document_id}, URL: {data.document_url[:100]}...")
        
        # Download file from pre-signed URL
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(data.document_url)
            response.raise_for_status()
            file_content = response.content
            file_size = len(file_content)
        
        # Validate file size (25MB limit)
        max_size = 25 * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(status_code=413, detail="File too large (max 25MB)")
        
        filename = data.document_type or "document.pdf"
        logger.info(f"[EXTRACT] Processing: {filename} ({file_size} bytes)")
        
        # Extract with Docstrange
        extracted_data = await asyncio.get_event_loop().run_in_executor(
            None, extract_with_docstrange, file_content, filename
        )
        
        # Add document_id to response
        extracted_data['document_id'] = data.document_id
        
        return ExtractionResponse(**extracted_data)
        
    except httpx.HTTPError as e:
        logger.error(f"[EXTRACT] Download failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to download document: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[EXTRACT] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

# ============================================
# ENDPOINT 2: MIXTRAL PROMPTING
# ============================================
@app.post("/prompt", response_model=PromptResponse)
async def prompt_endpoint(request: Request, data: PromptInput):
    """
    Send prompt to Mixtral 8x7B and get AI-generated output.
    
    Takes natural language prompt (with optional context data) and returns
    Mixtral's response. Use for journal entries, categorization, analysis, etc.
    
    Requires API key authentication.
    """
    await verify_api_key(request)
    
    try:
        logger.info(f"[PROMPT] Sending to Mixtral: {data.prompt[:100]}...")
        
        # Generate with Mixtral
        output = await asyncio.get_event_loop().run_in_executor(
            None, generate_with_llama, data.prompt, data.context
        )
        
        response_data = {
            "success": True,
            "output": output if isinstance(output, str) else str(output),
            "metadata": {
                "generated_at": get_timestamp(),
                "prompt_length": len(data.prompt),
                "context_provided": data.context is not None,
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1"
            }
        }
        
        return PromptResponse(**response_data)
        
    except Exception as e:
        logger.error(f"[PROMPT] Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prompt failed: {str(e)}")

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