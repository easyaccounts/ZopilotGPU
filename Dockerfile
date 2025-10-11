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

# Copy requirements first for better caching
COPY requirements.txt .

# Install build dependencies first (required for package compilation)
RUN pip install --no-cache-dir packaging wheel setuptools

# CRITICAL FIX: Install NumPy 1.26+ FIRST to prevent all compatibility issues
# NumPy 2.x breaks scipy, docstrange, and many scientific libraries
# Must be installed BEFORE torch/torchvision to avoid dependency conflicts
# Using 1.26+ to match requirements.txt (prevents upgrade during pip install -r)
RUN pip install --no-cache-dir "numpy>=1.26.0,<2.0.0"

# Install scipy with NumPy 1.x (required by docstrange)
# scipy 1.11.x-1.12.x are NumPy 1.x compatible (1.13.0+ requires NumPy 2.x)
# Must happen BEFORE docstrange is installed
RUN pip install --no-cache-dir "scipy>=1.11.0,<1.13.0"

# Install PyTorch 2.5.1 with CUDA 12.4 support BEFORE requirements.txt (RTX 5090 Blackwell native)
# PyTorch 2.5.1 has native RTX 5090 Blackwell optimizations (5-10% faster inference)
# Using cu124 wheel for native CUDA 12.4 support (no forward compatibility layer needed)
# Still compatible with NumPy 1.x (docstrange requirement)
RUN pip install --no-cache-dir \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

# Create constraints file to prevent PyTorch upgrades during requirements.txt install
RUN echo "torch==2.5.1" > /tmp/constraints.txt && \
    echo "torchvision==0.20.1" >> /tmp/constraints.txt && \
    echo "torchaudio==2.5.1" >> /tmp/constraints.txt

# Install remaining Python dependencies AFTER PyTorch
# accelerate is constrained to <1.0.0 in requirements.txt (NumPy 1.x compatible)
# scipy and numpy already installed above, so they won't be upgraded
# Use --constraint to prevent PyTorch upgrades from dependencies
# BitsAndBytes 0.45.0 has native CUDA 12.4 support - no BNB_CUDA_VERSION override needed!
RUN pip install --no-cache-dir --ignore-installed blinker \
    --constraint /tmp/constraints.txt \
    -r requirements.txt

# CRITICAL: Verify correct versions installed (fail fast if wrong binaries)
RUN python -c "import torch; print(f'✅ PyTorch: {torch.__version__}'); assert '2.5.1' in torch.__version__, f'Wrong PyTorch: {torch.__version__}'"
RUN python -c "import torch; print(f'✅ CUDA: {torch.version.cuda}'); assert torch.version.cuda == '12.4', f'Wrong CUDA: {torch.version.cuda}'"
RUN python -c "import numpy as np; print(f'✅ NumPy: {np.__version__}'); assert np.__version__.startswith('1.26'), f'Wrong NumPy: {np.__version__}'"
RUN python -c "import bitsandbytes as bnb; print(f'✅ BitsAndBytes: {bnb.__version__}'); assert bnb.__version__ == '0.45.0', f'Wrong BnB: {bnb.__version__}'"
RUN python -c "import scipy; print(f'✅ SciPy: {scipy.__version__}')"
RUN python -c "import transformers; print(f'✅ Transformers: {transformers.__version__}')"
RUN python -c "print('✅ All dependency versions verified!')"

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
#   - Mount a persistent volume to /workspace (where models download)
#   - First worker downloads models once (~123GB: 93GB Mixtral FP16 + 30GB Docstrange, 30-45 min)
#   - Models are quantized to 8-bit at load time (~24GB VRAM)
#   - All subsequent workers share the same volume (instant startup)
#   - RunPod: Create Network Volume (120GB+), mount to /workspace
#   - Cost: ~$0.15/GB/month = ~$18/month for 120GB
#
# APPROACH 2: Bake into Image (for reference, not recommended)
#   - Uncomment the RUN commands below to pre-download during build
#   - Makes image ~123GB (very slow push/pull, expensive storage)
#   - Any code change requires rebuilding entire image
#
# APPROACH 3: MIN_WORKERS=1
#   - Keep 1 worker always warm with models in memory
#   - First download happens once on deployment
#   - Models stay in container filesystem until restart
#   - Cost: ~$7-12/day GPU cost

# Uncomment to bake models into image (NOT RECOMMENDED):
# RUN python -c "from app.docstrange_utils import get_docstrange_processor; \
#     print('📦 Downloading Docstrange (~30GB)...'); \
#     get_docstrange_processor(); \
#     print('✅ Docstrange ready!')"
#
# ARG HUGGING_FACE_TOKEN
# RUN if [ -n "$HUGGING_FACE_TOKEN" ]; then \
#         python -c "from app.llama_utils import get_llama_processor; \
#         print('📦 Downloading Mixtral FP16 (~93GB, will be 8-bit quantized at load)...'); \
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
# Docstrange uses XDG_CACHE_HOME (stores models in XDG_CACHE_HOME/docstrange)
ENV XDG_CACHE_HOME=/runpod-volume

# GPU-specific environment variables for Mixtral 8x7B
# Mixtral 8x7B: 4-bit NF4 ~12GB weights + 3-5GB activations = ~16-17GB total
# Compatible with RTX 4090 (24GB), RTX 5090 (32GB), A40 (48GB)
ENV CUDA_VISIBLE_DEVICES=0
# GPU memory allocation settings optimized for 4-bit quantization with expandable segments
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512,expandable_segments:True
ENV CUDA_LAUNCH_BLOCKING=0

# Health check (allow time for model loading on first start)
HEALTHCHECK --interval=60s --timeout=30s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port (configurable via environment)
EXPOSE 8000

# Default command for RunPod Serverless
# Use handler.py for serverless, start.sh for direct deployment
CMD ["python", "handler.py"]