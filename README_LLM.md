# ZopilotGPU

**LLM Classification Service** - Mixtral 8x7B inference endpoint for Zopilot

## Purpose

This is a specialized service that handles **document classification only** using Mixtral 8x7B.
It runs on **RTX 5090 GPU** with PyTorch 2.6+ + NumPy 2.x for sm_120 compute capability support.

## Architecture

```
Backend → ZopilotOCR (/extract) → Text Extraction
       → ZopilotGPU (/prompt) → LLM Classification (THIS SERVICE)
```

## Key Changes from Original ZopilotGPU

- ✅ **KEEPS**: `/prompt` endpoint, Mixtral 8x7B, transformers, BitsAndBytes
- ❌ **REMOVES**: `/extract` endpoint, DocStrange, EasyOCR, all OCR dependencies

## Dependencies

- **PyTorch 2.6+ + CUDA 12.4** (for RTX 5090 sm_120 support)
- **NumPy 2.x** (required by PyTorch 2.6+)
- **Mixtral 8x7B-Instruct-v0.1** (LLM model)
- **BitsAndBytes 0.45.0** (4-bit quantization)
- **transformers 4.49.0+** (HuggingFace)

## GPU Requirements

- **RTX 5090 (32GB)** - Blackwell architecture with sm_120 compute capability
- Requires PyTorch 2.6+ for native sm_120 support

## Deployment

```bash
# Build Docker image with PyTorch 2.6+
docker build -t zopilot-gpu-llm:latest .

# Deploy to RunPod Serverless
# Target: RTX 5090 GPU ONLY
# Network Volume: Attach /runpod-volume for Mixtral model cache (~93GB)
```

## API Endpoint

**POST /prompt**

Request:
```json
{
  "prompt": "Extract invoice_number, vendor_name, total_amount from:\n\n[DOCUMENT TEXT]",
  "context": {}
}
```

Response:
```json
{
  "success": true,
  "output": "{\n  \"invoice_number\": \"INV-001\",\n  \"vendor_name\": \"Acme Corp\",\n  \"total_amount\": 1234.56\n}",
  "metadata": {
    "model": "Mixtral-8x7B-Instruct-v0.1",
    "generation_time": 0.85
  }
}
```

## Environment Variables

- `ZOPILOT_GPU_API_KEY` - API key for authentication
- `HUGGING_FACE_TOKEN` - HuggingFace token (for Mixtral model downloads)

## Model Caching

Mixtral 8x7B model (~93GB) is cached on RunPod Network Volume at:
- `/runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/`

First deployment will download model (15-30 minutes), subsequent starts use cache.

## Memory Requirements

- **Mixtral 8x7B 4-bit quantization**: ~16-17GB VRAM
- **Context processing**: ~2-4GB VRAM
- **Total recommended**: RTX 5090 32GB

## Related Repos

- **ZopilotOCR**: Document extraction service (RTX 4090, DocStrange)
- **zopilot-backend**: Orchestrates both OCR and LLM endpoints

## Upgrade Notes

**Why PyTorch 2.6+ and NumPy 2.x?**

- RTX 5090 has compute capability **sm_120** (Blackwell architecture)
- PyTorch 2.5.1 only supports up to **sm_90** (Hopper)
- PyTorch 2.6+ added native **sm_120** support
- PyTorch 2.6+ requires **NumPy 2.x**
- This is why we split OCR (NumPy 1.x) and LLM (NumPy 2.x) into separate services

## Performance

- **Cold start**: 15-30 seconds (model loading from cache)
- **Warm inference**: 0.5-2 seconds per request
- **Throughput**: ~1-2 requests/second (depends on prompt length)
