# Build Fix for RTX 4090 Deployment

## Issue Encountered

**Build Error:**
```
ModuleNotFoundError: No module named 'packaging'
error: subprocess-exited-with-error (flash-attn)
```

## Root Cause

1. **Flash Attention compilation** requires `packaging` module during `setup.py` execution
2. **Dependency order matters**: PyTorch must be installed before packages that depend on it
3. **Flash Attention takes 10-15 minutes** to compile CUDA kernels for RTX 4090

## Solutions Applied

### 1. Install Build Dependencies First
```dockerfile
# Install build dependencies BEFORE requirements.txt
RUN pip install --no-cache-dir packaging wheel setuptools
```

### 2. Install PyTorch Before Other Dependencies
```dockerfile
# PyTorch MUST come before packages that depend on it (transformers, flash-attn, etc.)
RUN pip install torch==2.2.1 torchvision==0.17.1 torchaudio==2.2.1 --index-url https://download.pytorch.org/whl/cu121
```

### 3. Install Flash Attention Separately with Fallback
```dockerfile
# Flash Attention compiled separately with graceful failure
RUN pip install flash-attn>=2.5.0 --no-build-isolation || \
    echo "⚠️  Flash Attention installation failed, will use standard attention"
```

### 4. Install Remaining Requirements
```dockerfile
# Now safe to install requirements.txt
RUN pip install --no-cache-dir --ignore-installed blinker -r requirements.txt
```

### 5. Reinstall BitsAndBytes for RTX 4090
```dockerfile
# Ensure BitsAndBytes compiled with CUDA 12.1 for Ada Lovelace
RUN pip uninstall -y bitsandbytes && \
    pip install bitsandbytes>=0.42.0 --no-cache-dir
```

## Build Order (Critical)

```
1. System dependencies (ninja-build, etc.)
2. Upgrade pip
3. Build dependencies (packaging, wheel, setuptools)
4. PyTorch with CUDA 12.1
5. Flash Attention (optional, may fail gracefully)
6. Application requirements.txt
7. BitsAndBytes rebuild
8. Application code
```

## Expected Build Time

| Component | Time | Notes |
|-----------|------|-------|
| System packages | 1-2 min | apt-get install |
| PyTorch | 3-5 min | Pre-built wheels |
| Flash Attention | 10-15 min | **Compiles CUDA kernels** |
| Requirements.txt | 5-8 min | Transformers, etc. |
| BitsAndBytes rebuild | 1-2 min | Quick reinstall |
| **Total** | **20-30 min** | First build only |

## Verification After Build

Check logs for these success indicators:

### ✅ Success
```
✅ Successfully installed flash-attn-2.8.3
✅ Successfully installed bitsandbytes-0.42.0
✅ Successfully installed torch-2.2.1
```

### ⚠️ Acceptable Warning
```
⚠️  Flash Attention installation failed, will use standard attention
```
This is OK - model will work but 2-3x slower.

### ❌ Critical Failure
```
ERROR: Failed to build bitsandbytes
ERROR: No module named 'torch'
```
These indicate real problems.

## RTX 4090 Specific Optimizations

### Compute Capability 8.9 (Ada Lovelace)
- **PyTorch**: 2.2.1+ required
- **BitsAndBytes**: 0.42.0+ required
- **CUDA**: 12.1+ required
- **Flash Attention**: 2.5.0+ recommended

### VRAM Management (24GB)
```dockerfile
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512,expandable_segments:True
ENV CUDA_LAUNCH_BLOCKING=0
```

### Expected Performance
| Metric | With Flash Attention | Without |
|--------|---------------------|---------|
| Model Load | 2-3 min | 2-3 min |
| Inference | 20-30 sec | 45-60 sec |
| VRAM Usage | ~22 GB | ~23 GB |

## Troubleshooting

### Build Hangs at Flash Attention
**Normal** - Flash Attention compiles CUDA kernels for 10-15 minutes. Look for:
```
Building wheel for flash-attn (setup.py) ...
```

### Out of Memory During Build
Increase Docker build memory:
```bash
docker build --memory=16g --memory-swap=32g -t image-name .
```

### BitsAndBytes CUDA Error
```
RuntimeError: CUDA error: no kernel image is available
```
**Solution:** Upgrade to BitsAndBytes 0.42.0+ and PyTorch 2.2.1+

## Testing After Deployment

### 1. Check GPU Detection
```python
import torch
print(torch.cuda.is_available())  # Should be True
print(torch.cuda.get_device_name(0))  # Should show "RTX 4090"
```

### 2. Check Flash Attention
Look in startup logs for:
```
✅ Model loaded with Flash Attention 2 (optimized for RTX 4090)
```

### 3. Check Memory Usage
```python
import torch
print(torch.cuda.memory_allocated(0) / 1024**3)  # Should be ~22GB after model load
```

## Quick Rebuild Command

```bash
cd D:\Desktop\Zopilot\ZopilotGPU
docker build -t your-dockerhub-username/zopilot-gpu:rtx4090-fixed .
docker push your-dockerhub-username/zopilot-gpu:rtx4090-fixed
```

## RunPod Deployment Settings

After successful build:

```yaml
Container Image: your-dockerhub-username/zopilot-gpu:rtx4090-fixed
GPU Type: RTX 4090 (24GB)
Container Disk: 30 GB
Execution Timeout: 900 seconds
Max Workers: 5
Min Workers: 0

Environment Variables:
  HUGGING_FACE_TOKEN: hf_xxx...
  ZOPILOT_GPU_API_KEY: xxx...
  PYTORCH_CUDA_ALLOC_CONF: max_split_size_mb:512,expandable_segments:True
```

## Next Steps After This Fix

1. ✅ Build should complete successfully
2. ✅ Flash Attention may or may not compile (both OK)
3. ✅ Push to Docker Hub
4. ✅ Deploy to RunPod with RTX 4090
5. ✅ Test with sample document
6. ✅ Verify Flash Attention in logs

---

**Last Updated:** October 3, 2025
**Fix Version:** v2.0-rtx4090-optimized
