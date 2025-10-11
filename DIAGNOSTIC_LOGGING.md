# Comprehensive Diagnostic Logging System

## Overview

We've implemented extensive diagnostic logging throughout the codebase to capture the complete environment state when errors occur, enabling accurate troubleshooting and fixes on the first attempt.

---

## 1. Startup Diagnostics (handler.py)

### When: Container starts / RunPod worker initializes

### What's Logged:

#### **PyTorch & CUDA Configuration**
```
✅ PyTorch Version: 2.3.1+cu121
✅ PyTorch CUDA Compiled: 12.1
✅ CUDA Available: True
✅ CUDA Version (PyTorch): 12.1
✅ CUDA Runtime Version: 12.4
✅ cuDNN Version: 90100
✅ Number of GPUs: 1
🎮 GPU: NVIDIA GeForce RTX 5090
💾 VRAM Total: 31.4 GB
💾 VRAM Free: 31.3 GB
🔢 Compute Capability: 12.0
📊 Multi-processor count: 170
📊 Max threads per block: 1024
```

**Why:** Captures exact GPU/CUDA configuration to identify compatibility issues

---

#### **BitsAndBytes Configuration**
```
✅ BitsAndBytes version: 0.42.0
📦 BitsAndBytes location: /usr/local/lib/python3.10/dist-packages/bitsandbytes
🔧 BNB_CUDA_VERSION env: 121
✅ CUDA library loaded: libbitsandbytes_cuda121.so
✅ Binary name: libbitsandbytes_cuda121.so
✅ Linear4bit import: OK
✅ quantize_4bit import: OK
```

**Why:** Verifies BitsAndBytes can find correct CUDA libraries before model loading

---

#### **Transformers Integration**
```
✅ Transformers version: 4.45.0
📦 Transformers location: /usr/local/lib/python3.10/dist-packages/transformers
✅ BitsAndBytes integration import: OK
✅ BitsAndBytes backend validation: PASSED
✅ BitsAndBytesConfig import: OK
```

**Why:** Confirms transformers can use BitsAndBytes for quantization

---

#### **System & Container Info**
```
🐍 Python version: 3.10.12
🖥️  Platform: Linux-5.15.0-1057-nvidia-x86_64
🖥️  Machine: x86_64
🖥️  Processor: x86_64

📋 Critical Environment Variables:
   CUDA_HOME: /usr/local/cuda
   CUDA_PATH: /usr/local/cuda
   LD_LIBRARY_PATH: /usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64
   BNB_CUDA_VERSION: 121
   PYTORCH_CUDA_ALLOC_CONF: expandable_segments:True
   HF_HOME: /runpod-volume/huggingface
   TRANSFORMERS_CACHE: /runpod-volume/huggingface
```

**Why:** Captures system configuration and environment variables that affect library behavior

---

## 2. Model Initialization Diagnostics (llama_utils.py)

### When: Mixtral 8x7B model is loaded

### What's Logged:

#### **Pre-Load State**
```
======================================================================
MODEL INITIALIZATION: mistralai/Mixtral-8x7B-Instruct-v0.1
======================================================================
----------------------------------------------------------------------
DIAGNOSTIC: Environment & Dependencies
----------------------------------------------------------------------
PyTorch version: 2.3.1+cu121
CUDA available: True
CUDA version (PyTorch): 12.1
GPU: NVIDIA GeForce RTX 5090
VRAM: 31.4 GB
Compute capability: (12, 0)
BitsAndBytes version: 0.42.0
BNB_CUDA_VERSION env: 121
Transformers version: 4.45.0
----------------------------------------------------------------------
PyTorch memory expansion enabled: expandable_segments=True
GPU cache cleared. Free memory: 31.3 GB
Using Hugging Face token: hf_fbCvJxn...
```

**Why:** Baseline state before model loading to identify what changed

---

#### **Post-Load State**
```
----------------------------------------------------------------------
MODEL LOADING SUMMARY
----------------------------------------------------------------------
✅ Model loaded from cache in 4.8 seconds
✅ All model layers on GPU (no CPU offloading)
   Sample mapping: {'model.embed_tokens': 0, 'model.layers.0': 0}
GPU Memory: 13.45GB allocated, 15.23GB reserved, 16.17GB free
```

**Why:** Confirms successful load and memory usage

---

#### **Error State (if fails)**
```
======================================================================
MODEL INITIALIZATION FAILED
======================================================================
Error Type: RuntimeError
Error Message: CUDA Setup failed despite GPU being available...

Full Traceback:
[complete stack trace]

----------------------------------------------------------------------
BITSANDBYTES FAILURE DIAGNOSTICS
----------------------------------------------------------------------
BNB_CUDA_VERSION: 121
BitsAndBytes version: 0.42.0
BitsAndBytes location: /usr/local/lib/python3.10/dist-packages/bitsandbytes
CUDA_HOME: /usr/local/cuda
CUDA_PATH: /usr/local/cuda
LD_LIBRARY_PATH: /usr/local/nvidia/lib:/usr/local/nvidia/lib64...

Searching for CUDA libraries:
  ✅ Found libcudart in /usr/local/cuda/lib64: ['libcudart.so.12.4.1', 'libcudart.so']
  ✅ Found libcudart in /usr/local/nvidia/lib64: ['libcudart.so.12']

Searching for BNB CUDA libraries in: /usr/local/lib/python3.10/dist-packages/bitsandbytes
  Found 3 .so files:
    - libbitsandbytes_cpu.so
    - libbitsandbytes_cuda121.so
    - libbitsandbytes_cuda124.so

----------------------------------------------------------------------
RECOMMENDED FIXES:
1. Check BNB_CUDA_VERSION environment variable is set correctly
2. Ensure CUDA libraries are in LD_LIBRARY_PATH
3. Verify BitsAndBytes version compatibility with PyTorch
4. Check CUDA runtime version matches PyTorch compilation
----------------------------------------------------------------------
```

**Why:** Complete diagnostic context for BitsAndBytes failures with actionable fix suggestions

---

## 3. Request Failure Diagnostics (handler.py)

### When: Classification request fails

### What's Logged:

#### **BitsAndBytes/CUDA Errors**
```
======================================================================
[RunPod] CLASSIFICATION REQUEST FAILED
======================================================================
❌ Error Type: RuntimeError
❌ Error Message: CUDA Setup failed...
❌ Full Traceback: [complete stack]

----------------------------------------------------------------------
BITSANDBYTES/CUDA DIAGNOSTICS
----------------------------------------------------------------------
BNB_CUDA_VERSION: 121
LD_LIBRARY_PATH: /usr/local/nvidia/lib:/usr/local/nvidia/lib64...
CUDA_HOME: /usr/local/cuda
PyTorch version: 2.3.1+cu121
PyTorch CUDA compiled: 12.1
GPU Available: True
GPU: NVIDIA GeForce RTX 5090
CUDA Runtime (detected): 12.1
Compute Capability: (12, 0)
BitsAndBytes version: 0.42.0
BitsAndBytes path: /usr/local/lib/python3.10/dist-packages/bitsandbytes

----------------------------------------------------------------------
SOLUTION HINTS:
- If 'libbitsandbytes_cudaXXX.so not found': Set BNB_CUDA_VERSION env var
- If 'CUDA libraries not in path': Check LD_LIBRARY_PATH
- If 'PyTorch CUDA mismatch': Verify PyTorch CUDA version matches runtime
----------------------------------------------------------------------
```

**Why:** Context-aware diagnostics with targeted solutions

---

#### **GPU Memory Errors**
```
----------------------------------------------------------------------
GPU MEMORY DIAGNOSTICS
----------------------------------------------------------------------
Total VRAM: 31.36 GB
Allocated: 28.45 GB
Reserved: 29.12 GB
Free: 2.24 GB

----------------------------------------------------------------------
SOLUTION HINTS:
- Model requires ~16-17GB for 4-bit quantization
- Try reducing max_new_tokens in generation
- Check if other processes are using GPU memory
----------------------------------------------------------------------
```

**Why:** Captures exact memory state at failure with suggestions

---

## 4. How to Use These Logs

### **For BitsAndBytes Issues:**

1. **Look for startup diagnostics** → Verify BNB_CUDA_VERSION is set
2. **Check "BitsAndBytes Configuration"** → Confirm correct .so file loaded
3. **Verify "Transformers Integration"** → Ensure integration imports work
4. **Review LD_LIBRARY_PATH** → Confirm CUDA libraries accessible

### **For OOM Issues:**

1. **Check "Post-Load State"** → See baseline memory usage
2. **Look at "GPU MEMORY DIAGNOSTICS"** → See memory at failure
3. **Compare with requirements** → 16-17GB needed for 4-bit Mixtral
4. **Check device map** → Ensure no CPU offloading

### **For Import Errors:**

1. **Check "System & Container Info"** → Verify Python/platform
2. **Review "Environment Variables"** → Confirm paths set correctly
3. **Look at "Full Traceback"** → Identify exact import failure point

---

## 5. What This Enables

### **Before (without diagnostics):**
```
Error: CUDA Setup failed
```
→ No idea what CUDA version, what BitsAndBytes found, what environment variables were set

### **After (with diagnostics):**
```
Error: CUDA Setup failed
BNB_CUDA_VERSION: NOT SET
PyTorch CUDA: 12.1
CUDA Runtime: 12.4 (reports as version 128)
BitsAndBytes looking for: libbitsandbytes_cuda128.so
BitsAndBytes has: libbitsandbytes_cuda121.so
```
→ **Immediate fix:** Set `BNB_CUDA_VERSION=121`

---

## 6. Future Improvements

If issues persist, we can add:

1. **Pre-flight health check endpoint** - Test imports before first request
2. **Periodic memory profiling** - Track memory usage over time
3. **Request telemetry** - Log request patterns to identify contention
4. **Automatic recovery** - Retry with different configs on failure
5. **Structured logging** - JSON logs for automated analysis

---

## Summary

Every critical failure point now has:
- ✅ **Full context capture** (versions, paths, environment)
- ✅ **Diagnostic checks** (library imports, CUDA availability)
- ✅ **Error-specific details** (memory state, library locations)
- ✅ **Actionable solutions** (fix suggestions based on error type)

This ensures that **the next time an error occurs, we have everything needed to apply the correct fix immediately**, without trial-and-error or multiple debugging rounds.
