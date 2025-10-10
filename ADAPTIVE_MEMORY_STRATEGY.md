# Adaptive GPU Memory Allocation Strategy

**Date:** October 10, 2025  
**Status:** Production Ready  

---

## 🎯 Problem Statement

**The Challenge:**
- RTX 4090 has 24GB VRAM (23.5GB usable)
- Mixtral 8x7B 8-bit needs 18-22GB for weights (varies by implementation)
- Generation needs 2-4GB for activations (varies by prompt length)
- **Static allocation fails** when requirements don't match expectations

---

## ✅ Adaptive Solution

### Multi-Tier Memory Strategy

Instead of a single fixed allocation, we try multiple configurations in order of preference:

```python
# Attempt 1: Conservative (Recommended)
{
    "model": "20GB",           # Model weights
    "activations": "3.5GB",    # Buffer for generation
    "strategy": "Safe for all workloads"
}

# Attempt 2: Aggressive (Fallback)
{
    "model": "21GB",           # Model weights
    "activations": "2.5GB",    # Minimal buffer
    "strategy": "For smaller prompts"
}
```

### How It Works

**Step 1:** Try loading with 20GB
- If successful → Use this (best balance)
- If fails → Clear GPU cache, try next

**Step 2:** Try loading with 21GB
- If successful → Use this (tighter fit)
- If fails → Raise clear error

**Step 3:** All attempts failed
- Stop execution immediately
- Return detailed error to backend
- Prevents silent failures

---

## 🔍 Safety Checks

### Check #1: Verify No CPU Offloading

After model loads, we check the device map:

```python
if hasattr(self.model, 'hf_device_map'):
    device_map = self.model.hf_device_map
    cpu_layers = [k for k, v in device_map.items() if 'cpu' in str(v) or 'meta' in str(v)]
    
    if cpu_layers:
        raise RuntimeError(
            f"Model has {len(cpu_layers)} layers on CPU/meta device. "
            "This will cause 'Cannot copy out of meta tensor' errors."
        )
```

**Why This Matters:**
- CPU offloading causes silent corruption
- Meta tensors crash during generation
- Better to fail loading than fail generation

### Check #2: Report Memory Usage

After successful load:

```python
allocated = torch.cuda.memory_allocated(0) / (1024**3)
reserved = torch.cuda.memory_reserved(0) / (1024**3)
free = total - reserved

logger.info(f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved, {free:.2f}GB free")
```

**Expected Output:**
```
Attempt 1: Loading with 20GB for model (3.5GB buffer for activations)
✅ Model loaded successfully with 20GB allocation
✅ All model layers on GPU (no CPU offloading)
📊 GPU Memory: 19.2GB allocated, 19.8GB reserved, 3.7GB free
```

---

## 📊 Decision Matrix

### When Each Configuration Succeeds

| Config | Model Weights | Activations | Use Case |
|--------|--------------|-------------|----------|
| **20GB** | ~18-19GB | ~3.5-4GB | Long prompts, complex documents |
| **21GB** | ~19-20GB | ~2.5-3GB | Short prompts, simple classifications |

### What If Both Fail?

If model truly needs >21GB for weights, we have **3 options**:

#### Option A: Reduce Model Size
```python
# Use 4-bit quantization instead of 8-bit
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,  # Was: load_in_8bit=True
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)
```
- **Pros:** Fits in ~10-12GB, leaves plenty of activation space
- **Cons:** ~5-10% quality reduction

#### Option B: Use Smaller Model
```python
self.model_name = "mistralai/Mistral-7B-Instruct-v0.2"  # Single expert
```
- **Pros:** Fits in ~7-8GB, very fast
- **Cons:** Lower reasoning capability for complex accounting

#### Option C: Upgrade GPU
- **A100 40GB:** Plenty of room for Mixtral 8x7B 8-bit
- **A100 80GB:** Can run full precision
- **H100:** Even faster inference

---

## 🧪 Testing Strategy

### Test Case 1: Normal Document (Success)
```
Expected: Loads with 20GB config
Expected Memory: 19-20GB allocated, 3-4GB free
Expected Generation: 30-40 tok/s
```

### Test Case 2: Long Document (Edge Case)
```
Expected: Loads with 20GB config
Expected Memory: 19-20GB allocated, 3-4GB free
Activation Needs: 3-4GB (fits in buffer)
Expected Generation: 25-35 tok/s (slightly slower due to KV cache)
```

### Test Case 3: Multiple Concurrent (Stress Test)
```
Expected: First request loads model
Expected: Subsequent requests queue (semaphore blocks)
Expected Memory: Stable at 19-20GB (no memory leaks)
```

---

## 🔧 Monitoring & Alerts

### Key Metrics to Watch

**Success Indicators:**
- ✅ `"Model loaded successfully with 20GB allocation"`
- ✅ `"All model layers on GPU (no CPU offloading)"`
- ✅ `"Generated X tokens in Ys (30-40 tok/s)"`

**Warning Signs:**
- ⚠️  `"Attempt 1 failed, trying next configuration"`
- ⚠️  `"GPU Memory: X.XGB allocated, <2GB free"`
- ⚠️  `"Generated X tokens in Ys (<20 tok/s)"` (slow)

**Critical Errors:**
- ❌ `"Failed to load Mixtral model after 2 attempts"`
- ❌ `"Model has X layers on CPU/meta device"`
- ❌ `"CUDA out of memory during generation"`

### Recommended Actions

| Alert | Severity | Action |
|-------|----------|--------|
| Model loads with 21GB | LOW | Monitor activation usage, consider 4-bit if issues |
| Generation <20 tok/s | MEDIUM | Check for CPU offloading, verify GPU utilization |
| Both attempts fail | CRITICAL | Switch to 4-bit quantization or smaller model |
| CPU layers detected | CRITICAL | Memory config too tight, increase allocation |

---

## 📈 Performance Expectations

### With 20GB Configuration (Recommended)

**Pros:**
- ✅ 3.5GB buffer for activations (generous)
- ✅ Handles long prompts (2048+ tokens)
- ✅ Stable memory usage
- ✅ Consistent performance

**Cons:**
- ⚠️  If model >20GB, falls back to 21GB
- ⚠️  Slightly more conservative than necessary

### With 21GB Configuration (Fallback)

**Pros:**
- ✅ Accommodates slightly larger model variants
- ✅ Still leaves 2.5GB for activations

**Cons:**
- ⚠️  Tighter margin for error
- ⚠️  May struggle with very long prompts
- ⚠️  Less buffer for memory fragmentation

---

## 🚀 Deployment Checklist

Before deploying:

- [ ] Verify PyTorch version supports `expandable_segments:True`
- [ ] Confirm RTX 4090 GPU in RunPod endpoint
- [ ] Test with sample document
- [ ] Monitor first 10 classifications
- [ ] Check memory usage stays stable
- [ ] Verify no CPU offloading warnings

After deployment:

- [ ] First request takes 60-70s (model loading)
- [ ] Subsequent requests take 12-15s (warm)
- [ ] GPU memory stable at ~19-20GB allocated
- [ ] Free memory stays above 2GB
- [ ] Generation speed 30-40 tok/s

---

## 💡 Summary

**The Strategy:**
1. Try conservative (20GB) first → Best for most cases
2. Fall back to aggressive (21GB) if needed → Handles edge cases
3. Fail fast with clear error → No silent failures
4. Verify no CPU offloading → Catch issues early
5. Report memory usage → Enable monitoring

**The Result:**
- Automatic adaptation to model size variations
- Safety checks prevent silent failures
- Clear errors enable quick debugging
- Production-ready with monitoring

This approach gives us **robustness** without sacrificing **performance**! 🎯
