# Production Dockerfile for ZopilotGPU with Mixtral 8x7B
# Optimized for Cloud GPU deployment (RunPod, Vast.ai, Lambda Labs)
# CUDA 12.4.1 required for RTX 5090 (Blackwell) support
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHON_VERSION=3.10
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    git \
    wget \
    curl \
    build-essential \
    software-properties-common \
    ninja-build \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python
RUN ln -s /usr/bin/python${PYTHON_VERSION} /usr/bin/python

# Upgrade pip
RUN python -m pip install --upgrade pip

# Set working directory
WORKDIR /app

# Copy requirements and constraints files first for better caching
COPY requirements.txt constraints.txt ./

# Install build dependencies first (required for package compilation)
RUN pip install --no-cache-dir packaging wheel setuptools

# CRITICAL: Install PyTorch 2.6.x ONLY (NOT 2.7.x!) with CUDA 12.4 for RTX 5090 (sm_120) support
# PyTorch 2.6.0-2.6.2 has native Blackwell architecture support (sm_120 compute capability)
# PyTorch 2.7.x REMOVED sm_120 support (only supports up to sm_90)
# PyTorch 2.5.1 only supports up to sm_90 (Hopper) - will crash on RTX 5090
# PyTorch 2.6+ requires NumPy 2.x (will be constrained by constraints.txt)
# Using cu124 wheel for native CUDA 12.4 support
# MUST stay on 2.6.x for RTX 5090 compatibility
RUN pip install --no-cache-dir \
    "torch>=2.6.0,<2.7.0" "torchvision>=0.21.0,<0.22.0" \
    --index-url https://download.pytorch.org/whl/cu124

# NOTE: PyTorch 2.6.0 installs Triton 3.2.0 as a dependency (which doesn't have triton.ops)
# We'll downgrade Triton AFTER installing requirements.txt

# Install remaining Python dependencies from requirements.txt with constraints
# constraints.txt prevents pip from upgrading PyTorch, NumPy, and other critical packages
# NumPy 2.x enforced by constraints (required by PyTorch 2.6+)
# BitsAndBytes 0.45.0 locked to prevent version drift
RUN pip install --no-cache-dir --ignore-installed blinker \
    --constraint constraints.txt \
    -r requirements.txt

# CRITICAL: Downgrade Triton to 2.x AFTER all other packages
# BitsAndBytes 0.45.0 requires triton.ops module which was removed in Triton 3.x
# PyTorch 2.6.0 pins triton==3.2.0, but we need 2.x for BitsAndBytes
# This downgrade won't break PyTorch (Triton is only used for kernel optimizations)
RUN pip install --no-cache-dir --force-reinstall "triton==2.3.1"

# CRITICAL: Verify correct versions installed (fail fast if wrong binaries)
RUN echo "============================================================" && \
    echo "VERIFICATION: Checking PyTorch Installation" && \
    echo "============================================================" && \
    python -c "import torch; \
        print(f'✅ PyTorch Version: {torch.__version__}'); \
        print(f'   CUDA Runtime: {torch.version.cuda}'); \
        print(f'   cuDNN Version: {torch.backends.cudnn.version()}'); \
        print(f'   Build: {torch.__config__.show()}' if hasattr(torch.__config__, 'show') else ''); \
        major_minor = '.'.join(torch.__version__.split('.')[:2]); \
        assert major_minor == '2.6', \
        f'🔴 WRONG PyTorch version {torch.__version__}! MUST be 2.6.x for RTX 5090 sm_120 support. PyTorch 2.7+ removed sm_120!'" && \
    echo "============================================================"

# FIXED: PyTorch 2.6.x comes with CUDA 12.6, not 12.4! Accept 12.4, 12.5, or 12.6
RUN echo "VERIFICATION: Checking CUDA Version" && \
    python -c "import torch; \
        print(f'✅ CUDA Version: {torch.version.cuda}'); \
        cuda_major_minor = '.'.join(torch.version.cuda.split('.')[:2]); \
        print(f'   CUDA Major.Minor: {cuda_major_minor}'); \
        assert cuda_major_minor in ['12.4', '12.5', '12.6'], \
        f'Wrong CUDA version: {torch.version.cuda} (need 12.4-12.6)'" && \
    echo "============================================================"

RUN echo "VERIFICATION: Checking NumPy Version" && \
    python -c "import numpy as np; \
        print(f'✅ NumPy Version: {np.__version__}'); \
        assert np.__version__.startswith('2.'), \
        f'Wrong NumPy (need 2.x for PyTorch 2.6+): {np.__version__}'" && \
    echo "============================================================"

# REMOVED: BitsAndBytes import check - requires GPU at import time (not available during Docker build)
# BitsAndBytes will be validated at runtime in handler.py when GPU is available
RUN echo "VERIFICATION: Checking Transformers Version" && \
    python -c "import transformers; \
        print(f'✅ Transformers Version: {transformers.__version__}')" && \
    echo "============================================================"

RUN echo "VERIFICATION: Checking Triton Version (Required by BitsAndBytes)" && \
    python -c "import triton; \
        print(f'✅ Triton Version: {triton.__version__}'); \
        major_minor = '.'.join(triton.__version__.split('.')[:2]); \
        assert major_minor.startswith('2.'), \
        f'🔴 WRONG Triton version {triton.__version__}! MUST be 2.x for BitsAndBytes 0.45.0 (triton.ops removed in 3.x)'; \
        import triton.ops; \
        print(f'✅ triton.ops module available (required by BitsAndBytes 0.45.0)')" && \
    echo "============================================================"

RUN echo "VERIFICATION: Checking BitsAndBytes Package (NOT importing - requires GPU)" && \
    python -c "import pkg_resources; \
        bnb_version = pkg_resources.get_distribution('bitsandbytes').version; \
        print(f'✅ BitsAndBytes Package Installed: {bnb_version}'); \
        print(f'   Note: Import verification will happen at runtime when GPU is available')" && \
    echo "============================================================"

RUN echo "✅ All dependency versions verified!" && \
    echo "   PyTorch: 2.6.x (RTX 5090 sm_120 support)" && \
    echo "   Triton: 2.x (triton.ops available for BitsAndBytes)" && \
    echo "   BitsAndBytes: 0.45.0 (import will be verified at runtime)" && \
    echo "============================================================"

# Copy application code
COPY app/ ./app/
COPY *.py ./
COPY start.sh ./

# Create necessary directories
RUN mkdir -p /app/models /app/temp /app/logs

# NOTE: Models are NOT baked into image for efficiency
# Instead, use one of these approaches:
#
# APPROACH 1 (RECOMMENDED): Persistent Network Volume
#   - Mount a persistent volume to /runpod-volume (where models download)
#   - First worker downloads Mixtral once (~93GB FP16, quantized to 4-bit at load time)
#   - Model download takes 15-30 min depending on network speed
#   - All subsequent workers share the same volume (instant startup)
#   - RunPod: Create Network Volume (100GB+), mount to /runpod-volume
#   - Cost: ~$0.15/GB/month = ~$15/month for 100GB
#
# APPROACH 2: Bake into Image (for reference, not recommended)
#   - Uncomment the RUN commands below to pre-download during build
#   - Makes image ~93GB (very slow push/pull, expensive storage)
#   - Any code change requires rebuilding entire image
#
# APPROACH 3: MIN_WORKERS=1
#   - Keep 1 worker always warm with models in memory
#   - First download happens once on deployment
#   - Models stay in container filesystem until restart
#   - Cost: ~$0.70-1.20/hr for RTX 5090

# Uncomment to bake Mixtral into image (NOT RECOMMENDED):
# ARG HUGGING_FACE_TOKEN
# RUN if [ -n "$HUGGING_FACE_TOKEN" ]; then \
#         python -c "from app.llama_utils import get_llama_processor; \
#         print('📦 Downloading Mixtral FP16 (~93GB, will be 4-bit quantized at load)...'); \
#         get_llama_processor(); \
#         print('✅ Mixtral ready!')"; \
#     fi

# Make start script executable
RUN chmod +x /app/start.sh

# Set permissions
RUN chmod -R 755 /app

# NOTE: Do NOT create /workspace or symlink here!
# /workspace is mounted by RunPod at runtime
# Symlink is created in handler.py after volume mount

# Environment variables for production
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Model cache paths - RunPod Serverless mounts network volumes at /runpod-volume
# Models are stored at Network Volume root (mounted as /runpod-volume in serverless)
# HuggingFace stores models directly in HF_HOME (no /hub subdirectory)
# Structure: HF_HOME/models--<org>--<model>/snapshots/<commit>/
ENV HF_HOME=/runpod-volume/huggingface
ENV TRANSFORMERS_CACHE=/runpod-volume/huggingface
ENV TORCH_HOME=/runpod-volume/torch
ENV XDG_CACHE_HOME=/runpod-volume

# GPU-specific environment variables for Mixtral 8x7B
# Mixtral 8x7B: 4-bit NF4 ~12GB weights + 4-6GB activations = ~16-18GB total VRAM
# RTX 5090 (32GB) has plenty of headroom for generation
ENV CUDA_VISIBLE_DEVICES=0
# GPU memory allocation settings optimized for 4-bit quantization with expandable segments
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512,expandable_segments:True
ENV CUDA_LAUNCH_BLOCKING=0
# RunPod serverless mode flag (disables FastAPI lifespan, models loaded on-demand)
ENV RUNPOD_SERVERLESS=true

# Health check (allow time for model loading on first start)
HEALTHCHECK --interval=60s --timeout=30s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port (configurable via environment)
EXPOSE 8000

# Default command for RunPod Serverless
# Use handler.py for serverless, start.sh for direct deployment
# -u flag: unbuffered output (CRITICAL for real-time logs in RunPod dashboard)
CMD ["python", "-u", "handler.py"]