# GPU Memory-Aware Dynamic Concurrency

## Problem

**Single GPU (RTX 4090 = 24GB VRAM) with Multiple Workers:**
- DocStrange: Uses CPU (cpu=True), minimal GPU usage
- Mixtral 8x7B: Uses GPU, requires ~24GB VRAM
- Multiple simultaneous Mixtral requests → OOM crash

**Network Volume helps with disk caching, NOT GPU memory:**
- ✅ Models load from cache quickly (no re-download)
- ❌ Each worker still loads models into its own GPU memory
- ❌ GPU memory is NOT shared between workers

## Solution: 3-Layer Concurrency Control

### **Layer 1: RunPod Configuration (runpod.toml)**

```toml
[handler]
max_concurrency = 4  # Maximum concurrent requests
timeout = 300  # Cold start timeout
execution_timeout = 120  # Warm request timeout
gpu_memory_per_request = "6GB"  # Reserve memory per request
```

**How it works:**
- RunPod tracks GPU memory usage across all workers
- If `gpu_memory_per_request × active_workers > total_GPU_memory`:
  - New requests are QUEUED (not rejected)
  - Workers start when memory becomes available
- This prevents OOM crashes at the infrastructure level

### **Layer 2: Runtime Memory Check (handler.py)**

```python
def check_gpu_memory_available(required_gb: float) -> bool:
    torch.cuda.empty_cache()  # Clear cache
    free_memory_gb = (total - reserved) / (1024**3)
    return free_memory_gb >= required_gb
```

**Before processing each request:**
1. Check current GPU memory
2. If insufficient → Return retry signal
3. If sufficient → Process request

**Benefits:**
- Prevents accepting requests when GPU is full
- Returns graceful error (not crash)
- Client can retry automatically

### **Layer 3: Application Semaphores**

```python
extraction_semaphore = asyncio.Semaphore(4)  # Max 4 concurrent extractions
classification_semaphore = asyncio.Semaphore(1)  # Max 1 classification

async with extraction_semaphore:
    # Process extraction
```

**How it works:**
- **Extraction endpoint:** Max 4 concurrent (DocStrange is CPU-bound)
- **Classification endpoint:** Max 1 concurrent (Mixtral is GPU-bound)
- Requests queue at application level if limit reached

## How Multiple Workers Work Now

### **Scenario 1: 4 Extraction Requests (DocStrange)**

```
Request 1 → Worker 1: DocStrange (CPU) → 2GB RAM, ~0GB VRAM
Request 2 → Worker 2: DocStrange (CPU) → 2GB RAM, ~0GB VRAM
Request 3 → Worker 3: DocStrange (CPU) → 2GB RAM, ~0GB VRAM
Request 4 → Worker 4: DocStrange (CPU) → 2GB RAM, ~0GB VRAM

Total VRAM used: ~0-2GB (minimal)
Status: ✅ All process concurrently
```

**Why it works:**
- DocStrange with `cpu=True` uses CPU inference
- Minimal GPU memory usage
- Bottleneck is CPU cores, not GPU

### **Scenario 2: 2 Classification Requests (Mixtral)**

```
Request 1 → Worker 1: Mixtral (GPU) → 24GB VRAM
Request 2 → QUEUED (classification_semaphore blocks)

Worker 1 finishes → Releases GPU memory → Cleans up
Request 2 → Worker 1: Mixtral (GPU) → 24GB VRAM

Status: ✅ Sequential processing (no OOM)
```

**Why it works:**
- `classification_semaphore = 1` prevents concurrent Mixtral loads
- Only 1 Mixtral instance in GPU memory at a time
- Subsequent requests wait their turn

### **Scenario 3: Mixed Workload**

```
Request 1 (extract) → Worker 1: DocStrange → ~0GB VRAM
Request 2 (extract) → Worker 2: DocStrange → ~0GB VRAM
Request 3 (classify) → Worker 3: Mixtral → 24GB VRAM (semaphore locked)
Request 4 (extract) → Worker 4: DocStrange → ~0GB VRAM
Request 5 (classify) → QUEUED (waiting for Worker 3 to finish)

Total VRAM: 24GB / 24GB (almost full but safe)
Status: ✅ Extractions continue, classification queued
```

**Why it works:**
- Extractions and classification use different semaphores
- Extractions don't block on classification
- Classification blocks other classifications (not extractions)

## Network Volume Role

```
WITHOUT Network Volume:
├── Worker starts
├── Downloads models (40-55 minutes)
├── Loads into GPU memory
└── If worker restarts → RE-DOWNLOAD

WITH Network Volume:
├── First worker downloads once (40-55 minutes)
├── Models cached at /runpod-volume
├── Subsequent workers read from cache (30-60 seconds)
└── Loads into GPU memory (fast, but still uses VRAM per worker)
```

**Network Volume helps:**
- ✅ Fast worker startup (read from cache)
- ✅ Avoid repeated downloads
- ✅ Shared across all workers

**Network Volume does NOT:**
- ❌ Share GPU memory between workers
- ❌ Allow multiple Mixtral instances on single GPU
- ❌ Reduce GPU memory usage

## Configuration Recommendations

### **Current Setup: 1× RTX 4090 (24GB VRAM)**

**For extraction-only (no classification):**
```toml
[handler]
max_concurrency = 4-8  # CPU-bound (DocStrange)
gpu_memory_per_request = "2GB"  # Conservative
```

**For extraction + classification:**
```toml
[handler]
max_concurrency = 4  # Mixed workload
gpu_memory_per_request = "6GB"  # Average (some extract, some classify)
```

**For classification-heavy:**
```toml
[handler]
max_concurrency = 1  # GPU-bound (Mixtral)
gpu_memory_per_request = "24GB"  # Full GPU per request
```

### **Future: 4× RTX 4090 (96GB VRAM total)**

```toml
[handler]
max_concurrency = 16  # 4 extractions per GPU
gpu_memory_per_request = "6GB"

# Or for classification:
max_concurrency = 4  # 1 classification per GPU
gpu_memory_per_request = "24GB"
```

## Monitoring

### **Check GPU Memory Usage**

Call `/health` endpoint:
```json
{
  "status": "healthy",
  "gpu_name": "NVIDIA GeForce RTX 4090",
  "total_vram_gb": 23.5,
  "free_vram_gb": 18.3,
  "allocated_vram_gb": 5.2,
  "reserved_vram_gb": 5.2
}
```

### **Check Concurrent Requests**

Look for logs:
```
[RunPod] Extraction started (concurrent: 3/4)
[RunPod] Classification started (GPU locked)
```

### **Check for Memory Exhaustion**

Response indicates retry needed:
```json
{
  "success": false,
  "error": "GPU memory exhausted, retry shortly",
  "error_type": "InsufficientGPUMemory",
  "retry_after": 10
}
```

## Cost Implications

### **Serverless (Current)**

**Cost:** $0.00031/second = $1.116/hour
- Only pay when processing
- Workers shut down after idle timeout
- Network Volume: $0.15/GB/month (~$18/month for 120GB)

**Best for:**
- <10 requests/hour
- Unpredictable load
- Cost optimization

### **Always-On (Future)**

**Cost:** $0.60/hour = $432/month
- Worker always warm (no cold start)
- Faster response times
- Network Volume: included

**Best for:**
- 10+ requests/hour
- Predictable load
- Speed optimization

## Summary

✅ **Multiple workers CAN work** with proper concurrency control
✅ **DocStrange (CPU)** can run 4+ concurrent
✅ **Mixtral (GPU)** limited to 1 concurrent per GPU
✅ **Network Volume** speeds up worker startup (not GPU memory)
✅ **3-layer control** prevents OOM crashes
✅ **Dynamic queuing** handles bursts gracefully

The key insight: **Disk cache ≠ GPU memory**. Network Volume helps with the former, semaphores help with the latter.
