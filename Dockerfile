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

# Install Python dependencies
# Use --ignore-installed for system packages that can't be uninstalled
RUN pip install --no-cache-dir --ignore-installed blinker -r requirements.txt

# Rebuild BitsAndBytes with CUDA 12.1 support for RTX 4090
# This ensures proper Ada Lovelace (compute capability 8.9) support
RUN pip uninstall -y bitsandbytes && \
    pip install bitsandbytes>=0.42.0 --no-cache-dir

# Install PyTorch with CUDA 12.1 support for Mixtral 8x7B
# Updated to 2.2.0+ for better RTX 4090 (Ada Lovelace) support
RUN pip install torch==2.2.1 torchvision==0.17.1 torchaudio==2.2.1 --index-url https://download.pytorch.org/whl/cu121

# Install Flash Attention 2 for RTX 4090 optimization (optional but recommended)
# This provides 2-3x faster inference on Ada Lovelace architecture
RUN pip install flash-attn>=2.5.0 --no-build-isolation || \
    echo "⚠️  Flash Attention installation failed, will use standard attention"

# Copy application code
COPY app/ ./app/
COPY *.py ./
COPY start.sh ./

# Create necessary directories
RUN mkdir -p /app/models /app/temp /app/logs

# Make start script executable
RUN chmod +x /app/start.sh

# Set permissions
RUN chmod -R 755 /app

# Environment variables for production
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/app/models
ENV HF_HOME=/app/models
ENV TORCH_HOME=/app/models

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