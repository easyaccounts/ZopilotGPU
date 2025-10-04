# GPU Document Extraction Cache Directory Fix

## Issue Summary
**Error:** `[Errno 17] File exists: '/root/.cache'`  
**Location:** DocStrange initialization in `app/docstrange_utils.py`  
**Impact:** Document extraction fails completely on GPU service

## Root Cause
The error occurs when `/root/.cache` exists as a **file** instead of a directory. The DocStrange library (and other ML libraries) try to create cache directories but fail when the path already exists as a file.

### Why This Happens
1. RunPod serverless workers may have `/root/.cache` created as a file by some process
2. The symlink creation in `handler.py` only checked `is_symlink()` but didn't handle the case where it's a regular file
3. `shutil.rmtree()` only works on directories, causing `[Errno 17]` on files
4. DocStrange then fails to initialize because it cannot create cache directories

## Error Flow
```
handler.py startup
  → Attempts to create /root/.cache symlink
  → Finds /root/.cache exists as FILE
  → Tries shutil.rmtree() on FILE
  → Fails with [Errno 17] File exists
  → Symlink not created
  
app/docstrange_utils.py initialization
  → DocumentExtractor tries to create /root/.cache/docstrange
  → Fails because /root/.cache is a file
  → Raises [Errno 17] File exists: '/root/.cache'
  → Extraction fails
```

## Fixes Applied

### 1. handler.py - Improved Symlink Creation (Lines 9-33)
**Before:**
```python
if cache_path.exists() and not cache_path.is_symlink():
    import shutil
    shutil.rmtree(cache_path, ignore_errors=True)  # ❌ Fails on files
```

**After:**
```python
if cache_path.exists() and not cache_path.is_symlink():
    import shutil
    try:
        cache_type = 'dir' if cache_path.is_dir() else 'file'
        if cache_path.is_dir():
            shutil.rmtree(cache_path, ignore_errors=True)
        else:
            # It's a file, remove it properly
            cache_path.unlink(missing_ok=True)  # ✅ Handles files
        print(f"🗑️  Removed existing /root/.cache (was {cache_type})")
    except Exception as e:
        print(f"⚠️  Warning: Could not remove existing cache: {e}")

if not cache_path.exists():
    try:
        cache_path.symlink_to(workspace_path)
        print(f"✅ Created symlink: /root/.cache -> /workspace")
    except Exception as e:
        print(f"⚠️  Warning: Could not create symlink: {e}")
        # Try creating as directory if symlink fails (fallback)
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: /root/.cache (fallback)")
        except Exception as e2:
            print(f"❌ CRITICAL: Cannot create cache directory: {e2}")
```

**Changes:**
- ✅ Check if path is a file vs directory before removal
- ✅ Use `unlink()` for files instead of `rmtree()`
- ✅ Add fallback to create directory if symlink fails
- ✅ Better error messages for debugging

### 2. app/docstrange_utils.py - Defensive Cache Initialization (Lines 32-71)
**Added new method:**
```python
def _ensure_cache_directory(self):
    """Ensure cache directories exist and are writable."""
    cache_dirs = [
        os.path.expanduser("~/.cache"),
        os.path.expanduser("~/.cache/docstrange"),
        os.path.expanduser("~/.cache/huggingface"),
    ]
    
    for cache_dir in cache_dirs:
        cache_path = os.path.abspath(cache_dir)
        try:
            # If it exists as a file, remove it
            if os.path.exists(cache_path) and not os.path.isdir(cache_path):
                logger.warning(f"Removing {cache_path} (was a file, need directory)")
                os.remove(cache_path)
            
            # Create directory if it doesn't exist
            os.makedirs(cache_path, exist_ok=True)
            
            # Test write permissions
            test_file = os.path.join(cache_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            logger.info(f"✅ Cache directory ready: {cache_path}")
        except Exception as e:
            logger.error(f"❌ Cannot create/access cache directory {cache_path}: {e}")
            # Try to continue anyway - may work with different cache location
            pass
```

**Called before DocumentExtractor initialization:**
```python
def __init__(self):
    try:
        # CRITICAL: Ensure cache directory exists and is writable before initialization
        self._ensure_cache_directory()  # ✅ Added
        
        self.extractor = DocumentExtractor(...)
```

**Benefits:**
- ✅ Proactively checks and fixes cache directories
- ✅ Removes file-type cache paths before DocStrange tries to use them
- ✅ Tests write permissions to catch issues early
- ✅ Graceful degradation if cache setup fails
- ✅ Clear logging for debugging

## Testing Recommendations

### 1. Simulate the Error
```bash
# Create /root/.cache as a file to reproduce the issue
docker exec -it <container> touch /root/.cache

# Try to start the service - should now handle it gracefully
docker restart <container>
```

### 2. Verify Fix
```bash
# Check logs for successful cache setup
docker logs <container> | grep "Cache directory ready"
docker logs <container> | grep "Created symlink"

# Try document extraction
curl -X POST http://localhost:8000/extract \
  -H "X-API-Key: your-key" \
  -F "file=@test-invoice.pdf"
```

### 3. Edge Cases to Test
- `/root/.cache` exists as a file → Should be removed and recreated
- `/root/.cache` exists as a directory → Should be removed and symlinked
- `/root/.cache` is already a symlink → Should be left alone
- `/root/.cache` doesn't exist → Should create symlink
- Symlink creation fails → Should fall back to directory creation
- Cache write permissions fail → Should log error but continue

## Deployment Steps

1. **Update handler.py**
   - Improved symlink/cache handling at startup
   - Better error messages

2. **Update app/docstrange_utils.py**
   - Added `_ensure_cache_directory()` method
   - Call before DocumentExtractor initialization

3. **Rebuild Docker image**
   ```bash
   docker build -t zopilot-gpu:latest .
   ```

4. **Deploy to RunPod**
   - Push updated image
   - Existing workers will fail with old error
   - New workers should handle cache issues gracefully

5. **Monitor logs**
   - Look for "Cache directory ready" messages
   - Verify no more "[Errno 17]" errors
   - Check extraction success rate

## Prevention

### Environment Setup
Ensure RunPod template includes:
```dockerfile
# Ensure cache directories exist as directories, not files
RUN mkdir -p /root/.cache /workspace && \
    ln -sf /workspace /root/.cache
```

### Worker Initialization
The `handler.py` now handles cache setup automatically:
- Checks for file/directory conflicts
- Creates symlink to network volume
- Falls back to directory creation if needed

## Related Issues

### Similar Cache Problems
This fix also prevents similar issues with:
- `/root/.cache/huggingface` - Used by transformers
- `/root/.cache/torch` - Used by PyTorch
- `/root/.cache/docstrange` - Used by DocStrange

### Other ML Libraries
The same pattern can affect:
- `torchvision` - Vision models cache
- `transformers` - NLP models cache
- `sentence-transformers` - Embedding models cache

## Success Metrics

**Before Fix:**
- ❌ Document extraction fails: `[Errno 17] File exists: '/root/.cache'`
- ❌ 100% failure rate when cache is misconfigured
- ❌ No graceful degradation

**After Fix:**
- ✅ Cache path conflicts automatically resolved
- ✅ Clear logging of cache setup status
- ✅ Fallback to directory if symlink fails
- ✅ Extraction continues even if cache setup has issues

## Additional Notes

### Why Symlink to /workspace?
- Network volume mounted at `/workspace` persists between worker restarts
- Prevents re-downloading 6GB+ models on each worker spawn
- Shared cache across all workers
- Much faster startup (seconds vs minutes)

### Why File vs Directory Matters
- ML libraries use `os.makedirs()` which fails if path exists as non-directory
- Python's `shutil.rmtree()` only works on directories
- Need `os.remove()` or `Path.unlink()` for files
- Symlinks need special handling (`is_symlink()` check)

### Cache Directory Structure
```
/root/.cache/          (symlink → /workspace)
├── docstrange/
│   ├── models/
│   │   ├── layout/         (159 MB)
│   │   ├── tableformer/    (333 MB)
│   │   └── Nanonets-OCR/   (5.98 GB)
│   └── temp/
├── huggingface/
│   ├── hub/
│   │   └── mixtral-8x7b/   (46+ GB)
│   └── transformers/
└── torch/
```

## Rollback Plan
If issues occur after deployment:
1. Revert to previous image
2. Manually clean `/root/.cache` on workers
3. Check logs for specific errors
4. File issue with details

## Credits
- **Issue Identified:** GPU logs analysis showing `[Errno 17]` errors
- **Root Cause:** `/root/.cache` existing as file instead of directory
- **Fix Applied:** Two-layer defense (handler.py + docstrange_utils.py)
- **Testing:** Verify with various cache path states
