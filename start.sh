#!/bin/bash
set -e

# ZopilotGPU Production Deployment Script
# Supports RunPod, Vast.ai, Lambda Labs, and other cloud GPU providers

echo "🚀 Starting ZopilotGPU with Mixtral 8x7B..."

# Initialize models (downloads to network volume if not cached)
echo "🔧 Checking model cache..."
python /app/init_models.py
if [ $? -ne 0 ]; then
    echo "⚠️  Model initialization had issues, but continuing..."
fi

# Detect cloud provider
if [[ -n "${RUNPOD_POD_ID}" ]]; then
    echo "✅ Detected RunPod environment: ${RUNPOD_POD_ID}"
    CLOUD_PROVIDER="RunPod"
elif [[ -n "${VAST_CONTAINERLABEL}" ]]; then
    echo "✅ Detected Vast.ai environment"
    CLOUD_PROVIDER="Vast.ai"
elif [[ -n "${LAMBDA_TASK_ID}" ]]; then
    echo "✅ Detected Lambda Labs environment"
    CLOUD_PROVIDER="Lambda Labs"
else
    echo "⚠️  Unknown cloud environment, continuing with generic configuration..."
    CLOUD_PROVIDER="Generic"
fi

# Check CUDA availability and GPU specs
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Information:"
    nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader,nounits
    
    # Check if GPU has enough VRAM for Mixtral 8x7B (24GB required)
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n1)
    if [[ $VRAM -lt 22000 ]]; then
        echo "⚠️  WARNING: GPU has ${VRAM}MB VRAM. Mixtral 8x7B requires ~24GB with 4-bit quantization."
        echo "⚠️  Service may fail or run slowly. Consider using RTX 4090, A5000, or higher."
    else
        echo "✅ GPU has sufficient VRAM (${VRAM}MB) for Mixtral 8x7B"
    fi
else
    echo "❌ ERROR: No NVIDIA GPU detected. This service requires a CUDA-capable GPU."
    exit 1
fi

# Verify required environment variables
echo "🔍 Verifying configuration..."

if [[ -z "${HUGGING_FACE_TOKEN}" ]]; then
    echo "❌ ERROR: HUGGING_FACE_TOKEN is required"
    echo "   Get token from: https://huggingface.co/settings/tokens"
    echo "   Accept Mixtral license: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1"
    exit 1
fi

if [[ -z "${ZOPILOT_GPU_API_KEY}" ]]; then
    echo "⚠️  WARNING: ZOPILOT_GPU_API_KEY not set. API will be unprotected!"
    echo "   For production, generate a secure key: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
fi

if [[ "${ALLOWED_ORIGINS}" == "*" ]]; then
    echo "⚠️  WARNING: CORS set to allow all origins (*). Not recommended for production."
fi

# Set environment variables
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1
export TRANSFORMERS_CACHE=${TRANSFORMERS_CACHE:-/app/models}
export HF_HOME=${HF_HOME:-/app/models}
export TORCH_HOME=${TORCH_HOME:-/app/models}
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}

# Create necessary directories
mkdir -p ${TRANSFORMERS_CACHE} /app/temp /app/logs

# Set model cache permissions
chmod -R 755 ${TRANSFORMERS_CACHE}

# Pre-load models if requested (speeds up first request)
if [[ "${PRELOAD_MODELS}" == "true" ]]; then
    echo "📥 Pre-loading Mixtral 8x7B model..."
    echo "   This will download ~47GB and may take 10-30 minutes on first run..."
    
    python -c "
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch
import os

model_name = 'mistralai/Mixtral-8x7B-Instruct-v0.1'
token = os.getenv('HUGGING_FACE_TOKEN')

print('🔄 Loading tokenizer...')
tokenizer = AutoTokenizer.from_pretrained(model_name, token=token)
print('✅ Tokenizer loaded')

print('🔄 Loading Mixtral 8x7B model with 4-bit quantization...')
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type='nf4'
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=quantization_config,
    device_map='auto',
    token=token,
    trust_remote_code=True
)
print('✅ Model loaded successfully')
print(f'   Model memory footprint: ~{model.get_memory_footprint() / 1024**3:.2f} GB')
" || {
    echo "❌ Model pre-loading failed. Service will load on first request."
}
fi

# Log configuration summary
echo ""
echo "📋 Configuration Summary:"
echo "   Cloud Provider: ${CLOUD_PROVIDER}"
echo "   Port: ${PORT:-8000}"
echo "   Log Level: ${LOG_LEVEL:-INFO}"
echo "   Debug Mode: ${DEBUG:-false}"
echo "   Model Cache: ${TRANSFORMERS_CACHE}"
echo "   API Key Protected: $([ -n "${ZOPILOT_GPU_API_KEY}" ] && echo 'Yes' || echo 'No')"
echo "   CORS Origins: ${ALLOWED_ORIGINS}"
echo "   Health Check Public: ${HEALTH_CHECK_PUBLIC:-true}"
echo ""

# Start the application
echo "🎯 Starting ZopilotGPU service..."
echo "   Model: Mixtral 8x7B Instruct v0.1 (4-bit quantized)"
echo "   Endpoints: /extract, /generate, /process"
echo ""

exec uvicorn app.main:app \
    --host ${HOST:-0.0.0.0} \
    --port ${PORT:-8000} \
    --workers 1 \
    --timeout-keep-alive 60 \
    --log-level ${LOG_LEVEL:-info} \
    $([ "${DEBUG}" == "true" ] && echo "--reload" || echo "")