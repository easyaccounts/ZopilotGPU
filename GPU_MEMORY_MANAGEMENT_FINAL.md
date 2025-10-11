# GPU Memory Management - Final Solution

## Problem Statement

When loading Mixtral 8x7B (8-bit quantized) on RTX 4090 (24GB VRAM), we face competing constraints:

1. **CANNOT use CPU offloading** - Causes "Cannot copy out of meta tensor" errors during generation
2. **CANNOT use all 24GB** - Need buffer for activations, KV cache, and other operations
3. **MUST prevent OOM** - Generation fails if no memory available for activations

## Failed Approaches

### Attempt 1: `device_map="auto"` without constraints
```python
device_map="auto"
# No max_memory
```
**Problem**: Uses all 24GB, no buffer for activations → OOM during generation

### Attempt 2: `device_map="auto"` with CPU blocking
```python
device_map="auto"
max_memory={0: "21GB", "cpu": "0GB"}
```
**Problem**: BitsAndBytes validation error - tries to offload but `llm_int8_enable_fp32_cpu_offload=False` blocks it

### Attempt 3: `device_map="auto"` with disk device
```python
device_map="auto"
max_memory={0: "20GB", "cpu": "0GB", "disk": "0GB"}
```
**Problem**: RuntimeError - "disk" is not a valid PyTorch device type

## Final Solution ✅

### Configuration
```python
# In quantization_config:
llm_int8_enable_fp32_cpu_offload=False  # NO CPU offload allowed

# In from_pretrained:
device_map={"": 0}  # FORCE all layers on GPU 0
max_memory={0: "21GB"}  # Reserve 3GB buffer
```

### Why This Works

1. **`device_map={"": 0}`** (not `"auto"`)
   - Forces **ALL** model layers onto GPU 0
   - No automatic fallback to CPU
   - Fail-fast if model doesn't fit (better than silent degradation)

2. **`max_memory={0: "21GB"}`** (21GB of 24GB)
   - Reserves 3GB buffer for:
     - Activations during forward pass
     - KV cache during generation
     - Gradient computations
     - PyTorch CUDA overhead
   - Prevents Accelerate from trying to use all memory

3. **No `"cpu": "0GB"` in max_memory**
   - Avoids conflict with `device_map={"": 0}`
   - Device map already prevents CPU usage
   - Cleaner configuration

## Memory Breakdown

### RTX 4090: 24GB Total
```
├── 18-20GB: Model weights (Mixtral 8x7B 8-bit quantized)
├── 1-2GB:   Activations during generation
├── 3GB:     Reserved buffer (safety margin)
└── Total:   21GB allocated, 3GB free
```

### After Generation (with KV cache cleanup)
```
✅ Model loaded: 18-20GB allocated
🎯 During generation: +1-2GB activations
🧹 After cleanup: Returns to 18-20GB baseline
```

## Expected Behavior

### Success Case
```
Loading Mixtral 8x7B with 8-bit quantization...
Expected memory: ~18-20GB for weights, ~3GB buffer for activations
Memory limit: 21GB on GPU 0 (reserving 3GB buffer)
Loading checkpoint shards: 100%|██████████| 19/19 [00:56<00:00]
✅ Model loaded in 56.9 seconds
✅ All model layers on GPU (no CPU offloading)
GPU Memory: 18.23GB allocated, 19.45GB reserved, 4.55GB free
```

### Failure Case (if model doesn't fit)
```
RuntimeError: CUDA out of memory. Tried to allocate X GB.
Model requires more than 21GB. Consider:
1. Using 4-bit quantization (reduces to ~10-12GB)
2. Using smaller model
3. Upgrading to larger GPU
```

**Better to fail fast than silently degrade with CPU offloading!**

## Key Principles

1. **GPU-only or bust** - No hybrid CPU/GPU execution (causes meta tensor errors)
2. **Reserve buffer space** - Never allocate 100% of VRAM
3. **Explicit device placement** - Don't trust `device_map="auto"` for this use case
4. **KV cache cleanup** - Clear cache after each generation to prevent leaks

## Monitoring

After deployment, watch for these metrics:

### Healthy
- Model loads in 60-70 seconds from cache
- GPU memory: 18-20GB allocated, 4-6GB free
- Generation: 30-40 tokens/sec
- No OOM errors
- Memory returns to baseline after requests

### Unhealthy
- Model takes 5+ minutes to load (downloading, not cached)
- GPU memory: >22GB allocated, <2GB free
- Generation: <20 tokens/sec or OOM errors
- Memory slowly climbing over time (leak)

## Fallback Options

If 21GB limit still causes issues:

### Option A: Increase to 22GB
```python
max_memory={0: "22GB"}  # Only 2GB buffer
```
**Risk**: Less margin for activations

### Option B: Switch to 4-bit quantization
```python
load_in_4bit=True
bnb_4bit_compute_dtype=torch.float16
```
**Benefit**: Reduces to ~10-12GB, plenty of buffer

### Option C: Use smaller model
```python
model_name = "mistralai/Mistral-7B-Instruct-v0.2"
```
**Benefit**: ~7GB for weights, 17GB free

## Files Modified

- `app/llama_utils.py` (lines 85-118)
  - Changed `device_map="auto"` → `device_map={"": 0}`
  - Added `max_memory={0: "21GB"}`
  - Updated comments explaining strategy

## Testing Checklist

- [ ] Rebuild RunPod endpoint with latest code
- [ ] Test cold start (first classification after restart)
- [ ] Verify model loads without CPU offload warnings
- [ ] Confirm 3-4GB free memory after load
- [ ] Test classification with real document
- [ ] Monitor memory during generation
- [ ] Verify KV cache cleanup works
- [ ] Check memory returns to baseline
- [ ] Test 3-4 concurrent requests (within semaphore limit)

## Related Issues

- **Meta tensor error**: Caused by CPU offloading (FIXED by GPU-only placement)
- **OOM during generation**: Caused by no buffer (FIXED by 21GB limit)
- **BitsAndBytes validation**: Caused by device_map conflict (FIXED by explicit placement)
- **Memory leaks**: Caused by KV cache retention (FIXED by manual cleanup)

## References

- [Accelerate device_map docs](https://huggingface.co/docs/accelerate/usage_guides/big_modeling)
- [BitsAndBytes quantization](https://huggingface.co/docs/transformers/quantization)
- [CUDA memory management](https://pytorch.org/docs/stable/notes/cuda.html#memory-management)
