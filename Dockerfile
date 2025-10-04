# Production Dockerfile for ZopilotGPU with Mixtral 8x7B
# Optimized for Cloud GPU deployment (RunPod, Vast.ai, Lambda Labs)
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 AS base

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

# Install PyTorch with CUDA 12.1 support FIRST (required by many packages)
# Updated to 2.2.0+ for better RTX 4090 (Ada Lovelace) support
RUN pip install torch==2.2.1 torchvision==0.17.1 torchaudio==2.2.1 --index-url https://download.pytorch.org/whl/cu121

# Install Python dependencies
# Use --ignore-installed for system packages that can't be uninstalled
RUN pip install --no-cache-dir --ignore-installed blinker -r requirements.txt

# Rebuild BitsAndBytes with CUDA 12.1 support for RTX 4090
# This ensures proper Ada Lovelace (compute capability 8.9) support
RUN pip uninstall -y bitsandbytes && \
    pip install bitsandbytes>=0.42.0 --no-cache-dir

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
#   - Mount a persistent volume to /root/.cache (where models download)
#   - First worker downloads models once (~53GB, 20-30 min)
#   - All subsequent workers share the same volume (instant startup)
#   - RunPod: Create Network Volume, mount to /root/.cache
#   - Cost: ~$0.10/GB/month = ~$5/month for 53GB
#
# APPROACH 2: Bake into Image (for reference, not recommended)
#   - Uncomment the RUN commands below to pre-download during build
#   - Makes image ~53GB (slow push/pull, expensive storage)
#   - Any code change requires rebuilding entire image
#
# APPROACH 3: MIN_WORKERS=1
#   - Keep 1 worker always warm with models in memory
#   - First download happens once on deployment
#   - Models stay in container filesystem until restart
#   - Cost: ~$7-12/day GPU cost

# Uncomment to bake models into image (NOT RECOMMENDED):
# RUN python -c "from app.docstrange_utils import get_docstrange_processor; \
#     print('📦 Downloading Docstrange (~6GB)...'); \
#     get_docstrange_processor(); \
#     print('✅ Docstrange ready!')"
#
# ARG HUGGING_FACE_TOKEN
# RUN if [ -n "$HUGGING_FACE_TOKEN" ]; then \
#         python -c "from app.llama_utils import get_llama_processor; \
#         print('📦 Downloading Mixtral (~47GB)...'); \
#         get_llama_processor(); \
#         print('✅ Mixtral ready!')"; \
#     fi

# Make start script executable
RUN chmod +x /app/start.sh

# Set permissions
RUN chmod -R 755 /app

# Environment variables for production
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Model cache paths - RunPod network volumes mount at /workspace
ENV TRANSFORMERS_CACHE=/workspace/transformers
ENV HF_HOME=/workspace/huggingface
ENV TORCH_HOME=/workspace/torch
# Docstrange uses XDG_CACHE_HOME
ENV XDG_CACHE_HOME=/workspace

# GPU-specific environment variables for Mixtral 8x7B
# Mixtral 8x7B requires ~24GB VRAM with 4-bit quantization
ENV CUDA_VISIBLE_DEVICES=0
# RTX 4090 optimized memory allocation settings
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