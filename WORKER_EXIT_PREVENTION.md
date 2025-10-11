# 🔧 WORKER EXIT PREVENTION - DEBUGGING IMPROVEMENTS

**Date**: October 11, 2025  
**Issue**: Workers exiting abruptly on `/prompt` requests, preventing error log visibility  
**Solution**: Converted critical `sys.exit()` calls to warnings

---

## 🎯 PROBLEM

Workers were terminating during startup due to aggressive validation checks:
- ❌ Missing Mixtral model in cache → `sys.exit(1)`
- ❌ Missing environment variables → `sys.exit(1)`  
- ❌ PyTorch version mismatch → `sys.exit(1)`

This prevented you from seeing actual runtime errors when sending requests to `/prompt`.

---

## ✅ CHANGES MADE

### **1. Mixtral Model Cache Check** (Line ~167)

**Before:**
```python
if not mixtral_model_found:
    print("❌ CRITICAL ERROR: Mixtral model not found in cache!")
    print("🛑 STOPPING EXECUTION to prevent unnecessary downloads")
    sys.exit(1)  # ❌ KILLS WORKER
```

**After:**
```python
if not mixtral_model_found:
    print("⚠️  WARNING: Mixtral model not found in cache!")
    print("⚠️  CONTINUING - Model will be downloaded on first /prompt request")
    # REMOVED: sys.exit(1) - Allow worker to continue and download model on first use
else:
    print(f"✅ Mixtral model found in cache - will use cached version")
```

**Impact**: Worker now continues even if model isn't cached. Model will download on first use (15-30 min first request).

---

### **2. Environment Variables Check** (Line ~230)

**Before:**
```python
if missing_vars:
    print("⚠️  CRITICAL: Missing environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    sys.exit(1)  # ❌ KILLS WORKER
```

**After:**
```python
if missing_vars:
    print("⚠️  WARNING: Missing environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("⚠️  CONTINUING - Some features may not work without these variables")
    # REMOVED: sys.exit(1) - Allow worker to continue for debugging
```

**Impact**: Worker continues without env vars. You'll see the actual error when trying to use HuggingFace token, etc.

---

### **3. PyTorch Version Check** (Line ~255)

**Before:**
```python
if not torch.__version__.startswith(EXPECTED_PYTORCH_VERSION):
    print("❌ CRITICAL: PyTorch version mismatch!")
    print("Expected: 2.5.1")
    print(f"Actual: {torch.__version__}")
    sys.exit(1)  # ❌ KILLS WORKER
```

**After:**
```python
if not torch.__version__.startswith(EXPECTED_PYTORCH_VERSION):
    print("⚠️  WARNING: PyTorch version mismatch!")
    print("Expected: 2.5.1")
    print(f"Actual: {torch.__version__}")
    print("⚠️  CONTINUING - Will attempt to use installed version")
    # REMOVED: sys.exit(1) - Allow worker to continue for debugging
```

**Impact**: Worker continues with wrong PyTorch version. You'll see the actual BitsAndBytes error if incompatible.

---

## 📊 REMAINING sys.exit() CALLS (Still Valid)

These `sys.exit()` calls are **KEPT** because they represent truly critical startup failures:

### **1. Volume Not Found** (Line ~14)
```python
if not workspace_path.exists():
    print("❌ CRITICAL: /runpod-volume directory does not exist!")
    sys.exit(1)  # ✅ VALID - Cannot function without volume
```
**Reason**: Cannot operate without persistent storage. This is a deployment configuration error.

### **2. Volume Not Writable** (Line ~28)
```python
except Exception as e:
    print(f"❌ CRITICAL: /runpod-volume is not writable: {e}")
    sys.exit(1)  # ✅ VALID - Cannot save models/cache
```
**Reason**: Cannot cache models if volume is read-only. This is a permissions error.

### **3. Volume Not a Directory** (Line ~18)
```python
if not workspace_path.is_dir():
    print("❌ CRITICAL: /runpod-volume exists but is not a directory!")
    sys.exit(1)  # ✅ VALID - Corrupted mount
```
**Reason**: Indicates corrupted mount point. This is a system error.

### **4. RunPod Package Missing** (Line ~736)
```python
if runpod is None:
    logger.error("runpod package not installed")
    exit(1)  # ✅ VALID - Cannot run without RunPod SDK
```
**Reason**: This is the main entry point. If RunPod SDK missing, worker cannot start.

---

## 🎯 EXPECTED BEHAVIOR NOW

### **Scenario 1: Missing Model Cache**
- ✅ Worker starts successfully
- ⚠️  Warning logged about missing cache
- ⏳ First `/prompt` request triggers model download (15-30 min)
- ✅ Subsequent requests use cached model

### **Scenario 2: Missing Environment Variables**
- ✅ Worker starts successfully
- ⚠️  Warning logged about missing vars
- ❌ First `/prompt` request fails with clear error:
  ```
  ValueError: HUGGING_FACE_TOKEN environment variable not set
  ```
- ✅ **YOU CAN NOW SEE THIS ERROR IN LOGS!**

### **Scenario 3: Wrong PyTorch Version**
- ✅ Worker starts successfully
- ⚠️  Warning logged about version mismatch
- ❌ First `/prompt` request fails with clear error:
  ```
  ImportError: BitsAndBytes 0.45.0 requires PyTorch 2.5.1, found 2.3.1
  ```
- ✅ **YOU CAN NOW SEE THIS ERROR IN LOGS!**

---

## 🐛 DEBUGGING WORKFLOW

### **Step 1: Deploy Changes**
```bash
cd D:\Desktop\Zopilot\ZopilotGPU
git add handler.py
git commit -m "Remove aggressive sys.exit() calls for better debugging"
git push
```

### **Step 2: Rebuild & Deploy**
- Rebuild Docker image
- Deploy to RunPod
- Check startup logs for warnings

### **Step 3: Send Test Request**
```bash
# Send a test /prompt request
curl -X POST https://your-endpoint/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test", "context": null}'
```

### **Step 4: Check Worker Logs**
Now you should see:
- ✅ Full error traceback (not just "worker exited")
- ✅ Context-specific diagnostics (BitsAndBytes, OOM, etc.)
- ✅ Solution hints for common issues
- ✅ All environment variables and versions

---

## 🎬 WHAT YOU'LL SEE IN LOGS

### **Before (Worker Exits):**
```
❌ CRITICAL: Missing environment variables:
   - HUGGING_FACE_TOKEN (Hugging Face API token)
[Worker exited with code 1]
```

### **After (Full Error Visible):**
```
⚠️  WARNING: Missing environment variables:
   - HUGGING_FACE_TOKEN (Hugging Face API token)
⚠️  CONTINUING - Some features may not work without these variables

[RunPod] 🎯 Classification started (GPU locked)
[RunPod] 📝 Prompt length: 100 chars

======================================================================
[RunPod] CLASSIFICATION REQUEST FAILED
======================================================================
❌ Error Type: ValueError
❌ Error Message: HUGGING_FACE_TOKEN environment variable not set

❌ Full Traceback:
Traceback (most recent call last):
  File "/app/app/llama_utils.py", line 75, in _initialize_model
    if not hf_token:
        raise ValueError(
            "HUGGING_FACE_TOKEN environment variable not set. "
            "Please add it to your RunPod endpoint environment variables."
        )
ValueError: HUGGING_FACE_TOKEN environment variable not set
======================================================================
```

---

## 📋 TESTING CHECKLIST

After deployment, verify:

- [ ] Worker starts successfully (no immediate exit)
- [ ] Startup logs show warnings (not critical errors)
- [ ] `/prompt` request shows full error traceback
- [ ] Error includes context-specific diagnostics
- [ ] Solution hints are displayed
- [ ] Worker doesn't exit after error (stays alive for next request)

---

## 🚨 IMPORTANT NOTES

1. **Model Download on First Request**: If model isn't cached, first `/prompt` request will take 15-30 minutes. Subsequent requests will be fast.

2. **Environment Variables**: You still need to set these for production:
   - `HUGGING_FACE_TOKEN`
   - `ZOPILOT_GPU_API_KEY`

3. **PyTorch Version**: Ideally should be 2.5.1+cu124. Worker will attempt to use wrong version but may fail with clear error.

4. **Volume Mount**: Worker still exits immediately if `/runpod-volume` isn't mounted. This is correct behavior.

---

## 🎯 NEXT STEPS

1. **Deploy these changes**
2. **Send a test `/prompt` request**
3. **Check logs for full error details**
4. **Share the full error traceback** if you need help debugging

Now you'll be able to see exactly what's causing the worker to fail! 🎉
