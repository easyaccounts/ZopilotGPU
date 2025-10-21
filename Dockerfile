# Production Dockerfile for ZopilotGPU with Mixtral 8x7B
# Optimized for Cloud GPU deployment (RunPod, Vast.ai, Lambda Labs)
# CUDA 12.9.0 required for RTX 5090 Blackwell (sm_120) support
FROM nvidia/cuda:12.9.0-devel-ubuntu22.04 AS base

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

# CRITICAL: Install PyTorch 2.8.0 STABLE with CUDA 12.8 for RTX 5090 (sm_120) support
# RTX 5090 has compute capability sm_120 (Blackwell architecture)
# PyTorch 2.8.0 CUDA 12.8 build includes sm_120 + sm_100 support (Blackwell)
# PyTorch 2.8.0 CUDA 12.6 does NOT have sm_120 (only up to sm_90)
# Using cu128 index (cu129 wheels not available, cu128 has sm_120 support)
# Compatible with BitsAndBytes 0.48.0 (verified stable release)
RUN pip install --no-cache-dir \
    "torch==2.8.0" "torchvision==0.23.0" \
    --index-url https://download.pytorch.org/whl/cu128

# Install remaining Python dependencies from requirements.txt with constraints
# constraints.txt locks PyTorch 2.8.0, BitsAndBytes 0.48.0, and other critical packages
# NumPy 2.x enforced by constraints (required by PyTorch 2.8+)
# BitsAndBytes 0.48.0 is compatible with PyTorch 2.8.0 stable (verified)
RUN pip install --no-cache-dir --ignore-installed blinker \
    --constraint constraints.txt \
    -r requirements.txt

# NOTE: Triton downgrade NO LONGER NEEDED
# PyTorch 2.8.0 + BitsAndBytes 0.48.0 use compatible Triton versions
# BitsAndBytes 0.48.0 works with modern Triton (no triton.ops dependency)

# CRITICAL: Verify correct versions installed (fail fast if wrong binaries)
RUN echo "============================================================" && \
    echo "VERIFICATION: Checking PyTorch 2.8.0 + CUDA 12.9 Installation" && \
    echo "============================================================" && \
    python -c "import torch; \
        print(f'✅ PyTorch Version: {torch.__version__}'); \
        print(f'   CUDA Runtime: {torch.version.cuda}'); \
        print(f'   cuDNN Version: {torch.backends.cudnn.version()}'); \
        print(f'   Note: PyTorch 2.8.0 stable with sm_120 support for RTX 5090'); \
        major_minor = '.'.join(torch.__version__.split('.')[:2]); \
        assert major_minor == '2.8', \
        f'🔴 WRONG PyTorch version {torch.__version__}! Need 2.8.0 for RTX 5090 sm_120 support'" && \
    echo "============================================================"

# CRITICAL: Verify CUDA 12.8+ for sm_120 support
# PyTorch 2.8.0 with CUDA 12.8 or 12.9 includes sm_120 (RTX 5090 Blackwell)
# PyTorch 2.8.0 with CUDA 12.6 does NOT include sm_120
RUN echo "VERIFICATION: Checking CUDA 12.8+ Version (Required for sm_120)" && \
    python -c "import torch; \
        print(f'✅ CUDA Version: {torch.version.cuda}'); \
        cuda_major_minor = '.'.join(torch.version.cuda.split('.')[:2]); \
        print(f'   CUDA Major.Minor: {cuda_major_minor}'); \
        assert cuda_major_minor in ['12.8', '12.9'], \
        f'🔴 WRONG CUDA version: {torch.version.cuda} (need 12.8 or 12.9 for sm_120 support)'" && \
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

RUN echo "VERIFICATION: Checking Triton Version (PyTorch Dependency)" && \
    python -c "import triton; \
        print(f'✅ Triton Version: {triton.__version__}'); \
        print(f'   Note: BitsAndBytes 0.48.0 compatible with modern Triton')" && \
    echo "============================================================"

RUN echo "VERIFICATION: Checking BitsAndBytes 0.48.0 Package (NOT importing - requires GPU)" && \
    python -c "import pkg_resources; \
        bnb_version = pkg_resources.get_distribution('bitsandbytes').version; \
        print(f'✅ BitsAndBytes Package Installed: {bnb_version}'); \
        assert bnb_version == '0.48.0', \
        f'🔴 WRONG BitsAndBytes version {bnb_version}! Need 0.48.0 for PyTorch 2.8 compatibility'; \
        print(f'   Note: Import verification will happen at runtime when GPU is available')" && \
    echo "============================================================"

RUN echo "✅ All dependency versions verified!" && \
    echo "   PyTorch: 2.8.0 stable (RTX 5090 sm_120 support via CUDA 12.8)" && \
    echo "   CUDA: 12.8 (sm_120 + sm_100 Blackwell support)" && \
    echo "   BitsAndBytes: 0.48.0 (verified compatible with PyTorch 2.8.0)" && \
    echo "   Triton: Compatible version (no manual downgrade needed)" && \
    echo "============================================================"

# Copy application code
COPY app/ ./app/
COPY schemas/ ./schemas/
COPY *.py ./
COPY start.sh ./

# Create necessary directories
RUN mkdir -p /app/models /app/temp /app/logs

# Verify schemas are present (228 action-specific schemas for Outlines)
RUN echo "============================================================" && \
    echo "VERIFICATION: Checking Outlines Schemas" && \
    echo "============================================================" && \
    python -c "from pathlib import Path; \
        schemas_dir = Path('/app/schemas'); \
        stage1 = list(schemas_dir.glob('stage_1/*.json')); \
        stage2_5 = list(schemas_dir.glob('stage_2_5/*.json')); \
        stage4_generic = list(schemas_dir.glob('stage_4/*.json')); \
        stage4_qb = list(schemas_dir.glob('stage_4/actions/quickbooks/*.json')); \
        stage4_zoho = list(schemas_dir.glob('stage_4/actions/zohobooks/*.json')); \
        print(f'✅ Stage 1 schemas: {len(stage1)}'); \
        print(f'✅ Stage 2.5 schemas: {len(stage2_5)}'); \
        print(f'✅ Stage 4 generic schemas: {len(stage4_generic)}'); \
        print(f'✅ Stage 4 QuickBooks action schemas: {len(stage4_qb)}'); \
        print(f'✅ Stage 4 Zoho Books action schemas: {len(stage4_zoho)}'); \
        total_action_schemas = len(stage4_qb) + len(stage4_zoho); \
        print(f'✅ Total action-specific schemas: {total_action_schemas}'); \
        assert len(stage1) >= 1, 'Missing Stage 1 schema!'; \
        assert len(stage2_5) >= 1, 'Missing Stage 2.5 schema!'; \
        assert len(stage4_generic) >= 1, 'Missing Stage 4 generic schema!'; \
        assert len(stage4_qb) >= 144, f'Missing QuickBooks schemas! Found {len(stage4_qb)}, need 144'; \
        assert len(stage4_zoho) >= 84, f'Missing Zoho Books schemas! Found {len(stage4_zoho)}, need 84'; \
        print(f'✅ All schemas verified! Ready for Outlines integration')" && \
    echo "============================================================"

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

# Health check (allow time for model loading on first start)
HEALTHCHECK --interval=60s --timeout=30s --start-period=180s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port (configurable via environment)
EXPOSE 8000

# Default command for RunPod Serverless
# Use handler.py for serverless, start.sh for direct deployment
# -u flag: unbuffered output (CRITICAL for real-time logs in RunPod dashboard)
CMD ["python", "-u", "handler.py"]