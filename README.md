# ZopilotGPU - AI Document Processing Service

A production-ready FastAPI service that combines **Mixtral 8x7B Instruct** (Mixture of Experts) and **Docstrange (NanoNets)** to extract structured data from accounting documents and generate journal entries with superior reasoning capabilities.

> **🚀 Production Ready:** Secured with API key authentication, environment-based CORS, comprehensive monitoring, and cloud GPU deployment support!

## ✨ Features

### Document Processing
- **Intelligent Extraction**: OCR + structured data extraction using Docstrange with NanoNets fallback
- **Multiple Formats**: PDF, PNG, JPG, JPEG support
- **Pre-signed URLs**: Process documents directly from cloud storage (Cloudflare R2)

### AI-Powered Generation
- **Mixtral 8x7B**: Mixture of Experts architecture for superior accounting reasoning
- **15-20% Better Accuracy**: Outperforms Llama 3.1 8B on complex accounting transactions
- **Structured Output**: JSON-formatted journal entries with proper debits/credits

### Production Security
- **API Key Authentication**: Dual header support (Authorization Bearer / X-API-Key)
- **Environment-based CORS**: Configurable origin whitelist
- **Optional Public Health Check**: For monitoring services

### Performance
- **GPU Optimized**: 4-bit quantization (BitsAndBytes) for efficient VRAM usage (~24GB)
- **Fast Processing**: 3-8 seconds for extraction, 8-15 seconds for extraction + generation
- **Model Caching**: Persistent volume support for 47GB model cache

### Cloud Deployment
- **Multi-Provider**: RunPod, Vast.ai, Lambda Labs support
- **Docker Ready**: Production Dockerfile with CUDA 12.1
- **Auto-Detection**: Recognizes cloud provider environment

---

## 🚀 Quick Start

### Prerequisites

**GPU Requirements:**
- NVIDIA GPU with ≥24GB VRAM (RTX 4090, A5000, A6000, A100)
- CUDA 12.1+ installed
- nvidia-docker runtime (for Docker deployment)

**Accounts Required:**
1. **Hugging Face** - Get token: https://huggingface.co/settings/tokens
   - Accept Mixtral license: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1
2. **NanoNets** (Optional) - Free tier: https://app.nanonets.com/#/keys

### Installation

**Option 1: Local Development**
```bash
# Clone repository
git clone https://github.com/yourusername/ZopilotGPU.git
cd ZopilotGPU

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.development .env
nano .env  # Update HUGGING_FACE_TOKEN and other values

# Start service
chmod +x start.sh
./start.sh
```

**Option 2: Docker**
```bash
# Copy environment file
cp .env.production .env
nano .env  # Update values

# Build and run
docker-compose up --build

# Or manually
docker build -t zopilot-gpu .
docker run --gpus all -p 8000:8000 --env-file .env zopilot-gpu
```

**Option 3: Cloud GPU (Recommended)**
See [CLOUD_DEPLOYMENT_GUIDE.md](CLOUD_DEPLOYMENT_GUIDE.md) for detailed instructions on:
- RunPod deployment (~$0.34-0.69/hr)
- Vast.ai deployment (~$0.25-0.40/hr)
- Lambda Labs deployment (~$1.10/hr)

### First Time Setup

1. **Generate API Key**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Add to `.env`:
   ```bash
   ZOPILOT_GPU_API_KEY=<generated-key>
   ```

2. **Configure CORS**
   ```bash
   # Add your backend domain
   ALLOWED_ORIGINS=https://api.yourdomain.com,https://app.yourdomain.com
   ```

3. **Start Service**
   ```bash
   ./start.sh
   ```
   First start will download Mixtral model (~47GB, 15-30 minutes)

4. **Verify Health**
   ```bash
   curl http://localhost:8000/health
   ```

---

## 📋 API Endpoints

### Authentication
All endpoints (except health check when `HEALTH_CHECK_PUBLIC=true`) require API key authentication:
```bash
# Option 1: Authorization Bearer
Authorization: Bearer your_api_key_here

# Option 2: X-API-Key header
X-API-Key: your_api_key_here
```

---

### `GET /health`
Health check endpoint for monitoring (optionally public).

**Authentication**: Optional (controlled by `HEALTH_CHECK_PUBLIC` env var)

**Response:**
```json
{
  "status": "healthy",
  "model": "Mixtral-8x7B-Instruct-v0.1",
  "gpu_available": true,
  "vram_total": "24GB",
  "vram_used": "23GB"
}
```

---

### `POST /extract`
Extract structured data from document via pre-signed URL.

**Authentication**: Required (API key)

**Request Body:**
```json
{
  "document_url": "https://your-storage.com/document.pdf",
  "document_id": "doc-123-456"
}
```

**Response:**
```json
{
  "success": true,
  "document_id": "doc-123-456",
  "extraction_method": "docstrange_local",
  "data": {
    "invoice_number": "INV-2024-001",
    "date": "2024-03-15",
    "total": 1500.00,
    "vendor": "ACME Corp",
    "line_items": [...]
  },
  "metadata": {
    "processed_at": "2024-03-15T10:30:00Z",
    "confidence_score": 0.95,
    "processing_time_ms": 3421
  }
}
```

---

### `POST /generate`
Generate accounting journal entry from extracted data using Mixtral 8x7B.

**Authentication**: Required (API key)

**Request Body:**
```json
{
  "extracted_data": {
    "invoice_number": "INV-2024-001",
    "date": "2024-03-15",
    "total": 1500.00,
    "vendor": "ACME Corp"
  },
  "document_id": "doc-123-456",
  "document_type": "invoice"
}
```

**Response:**
```json
{
  "success": true,
  "document_id": "doc-123-456",
  "generation": {
    "journal_entry": {
      "date": "2024-03-15",
      "description": "Invoice from ACME Corp",
      "lines": [
        {"account": "Accounts Payable", "debit": 0, "credit": 1500.00},
        {"account": "Expenses", "debit": 1500.00, "credit": 0}
      ]
    }
  },
  "metadata": {
    "generated_at": "2024-03-15T10:30:05Z",
    "model": "Mixtral-8x7B-Instruct-v0.1",
    "processing_time_ms": 4823
  }
}
```

---

### `POST /process`
Complete pipeline: Extract + Generate in single request.

**Authentication**: Required (API key)

**Request Body:**
```json
{
  "prompt": "Generate journal entry for this invoice",
  "context": {...extracted_data...}
}
```

**Response:**
```json
{
  "success": true,
  "journal_entry": {
    "date": "2025-09-24",
    "description": "Office supplies purchase",
    "account_debits": [
      {"account": "Office Supplies", "amount": 150.00, "description": "Office supplies"}
    ],
    "account_credits": [
      {"account": "Accounts Payable", "amount": 150.00, "description": "Vendor payment due"}
    ],
    "total_debit": 150.00,
    "total_credit": 150.00,
    "reference": "INV-2025-001",
    "notes": "..."
  }
}
```

### `POST /process`
Combined endpoint: extract + generate in one call.

**Request:** Multipart form with file and optional prompt
**Response:** Combined extraction and generation results

## 🛠 Local Development

### Prerequisites
- Python 3.10+
- CUDA-compatible GPU (recommended: 16GB+ VRAM)
- Hugging Face account with Llama access
- NanoNets API account (optional, for fallback)

### Setup
```bash
# Clone and setup
git clone <repo>
cd EasyAccountsGPU

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run locally
uvicorn app.main:app --reload --port 8000
```

### Environment Variables
```bash
# Required
HUGGING_FACE_TOKEN=hf_your_token_here

# Optional (for NanoNets fallback)
NANONETS_API_KEY=your_nanonets_key
NANONETS_MODEL_ID=your_model_id

# Server config
HOST=0.0.0.0
PORT=8000
```

## 🚢 RunPod Deployment

### Method 1: Docker Deployment

1. **Build and Push Docker Image**
```bash
# Build
docker build -t your-username/easyaccountsgpu:latest .

# Push to registry
docker push your-username/easyaccountsgpu:latest
```

2. **Deploy on RunPod**
- Go to RunPod Console
- Create new Pod
- Use custom image: `your-username/easyaccountsgpu:latest`
- Set environment variables:
  ```
  HUGGING_FACE_TOKEN=hf_your_token_here
  NANONETS_API_KEY=your_key_here
  NANONETS_MODEL_ID=your_model_id_here
  ```
- Choose GPU: RTX A6000 or better
- Set ports: 8000 (HTTP)
- Volume: 20GB for model caching

### Method 2: Using runpod.json

```bash
# Use the provided configuration
curl -X POST "https://api.runpod.io/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -d @runpod.json
```

### Method 3: Manual Setup

1. Create RunPod instance with:
   - GPU: RTX A6000 or RTX 4090
   - Container: `nvidia/cuda:11.8-devel-ubuntu20.04`
   - Volume: 20GB+

2. Install on RunPod:
```bash
# Install system dependencies
apt-get update && apt-get install -y python3.10 python3-pip git

# Clone repo
git clone <your-repo>
cd EasyAccountsGPU

# Install Python dependencies
pip install -r requirements.txt

# Set environment variables
export HUGGING_FACE_TOKEN=hf_your_token_here
export NANONETS_API_KEY=your_key_here

# Run
chmod +x start.sh
./start.sh
```

## 🧪 Testing

### Test Document Extraction
```python
import requests

# Upload a document
with open("invoice.pdf", "rb") as f:
    response = requests.post(
        "http://your-runpod-url:8000/extract",
        files={"file": ("invoice.pdf", f, "application/pdf")}
    )
print(response.json())
```

### Test Journal Generation
```python
import requests

data = {
    "prompt": "Create journal entry for this invoice",
    "context": {"amount": 150.00, "vendor": "Office Depot"}
}

response = requests.post(
    "http://your-runpod-url:8000/generate",
    json=data
)
print(response.json())
```

### Test Combined Processing
```python
import requests

# Process document end-to-end
with open("invoice.pdf", "rb") as f:
    response = requests.post(
        "http://your-runpod-url:8000/process",
        files={"file": ("invoice.pdf", f, "application/pdf")},
        data={"prompt": "Generate journal entry for this invoice"}
    )
print(response.json())
```

## 📊 Performance

- **Model**: Meta-Llama-3.1-8B-Instruct with 4-bit quantization
- **Memory**: ~8-10GB VRAM usage
- **Speed**: ~2-5 seconds per journal entry generation
- **Extraction**: ~1-3 seconds per document (depending on size)

## 🔧 Configuration

### GPU Memory Optimization
```python
# Automatic in code - uses 4-bit quantization
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16
)
```

### Model Caching
Models are automatically cached in:
- Local: `~/.cache/huggingface/`
- RunPod: `/runpod-volume/models/`

## 📝 License

MIT License - see LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **CUDA Out of Memory**
   - Reduce batch size or use smaller GPU
   - Ensure 4-bit quantization is enabled

2. **Hugging Face Authentication**
   - Get token from https://huggingface.co/settings/tokens
   - Ensure you have Llama-3.1 access approved

3. **Model Download Fails**
   - Check internet connection
   - Verify Hugging Face token permissions

4. **RunPod Connection Issues**
   - Check port 8000 is exposed
   - Verify health endpoint: `/health`

### Logs
```bash
# Check application logs
docker logs <container_id>

# RunPod logs
tail -f /var/log/runpod.log
```