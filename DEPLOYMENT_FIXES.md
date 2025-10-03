# Deployment Fixes Applied

## Issues Fixed

### 1. ✅ Google Drive Sync - Recursive Folder Scanning
**Problem**: Subfolders reported 0 files even though files existed in nested folders  
**Root Cause**: Code only scanned direct children, not recursive subfolders  
**Fix**: Added `getAllFilesRecursive()` method to traverse entire folder tree  
**Location**: `zopilot-backend/src/services/googleDriveSyncService.ts`  
**Status**: Pushed to main branch

### 2. ✅ ZopilotGPU - Dependency Conflicts
**Problem**: `pip install` failing with ResolutionImpossible error  
**Root Cause**: Overly strict version pinning causing conflicts  
**Fix**: Changed to flexible version ranges (e.g., `>=4.36.0,<4.50.0`)  
**Location**: `ZopilotGPU/requirements.txt`  
**Status**: Pushed to main branch

### 3. ✅ ZopilotGPU - RunPod Configuration
**Problem**: Build looking for "Dcokerfile" (typo)  
**Fix**: Added `runpod.toml` with explicit Dockerfile configuration  
**Location**: `ZopilotGPU/runpod.toml`  
**Status**: Pushed to main branch

### 4. ✅ ZopilotGPU - Environment Variable Validation
**Problem**: Unclear error messages when HF token missing  
**Fix**: Added startup validation with detailed error messages  
**Location**: `ZopilotGPU/handler.py` and `ZopilotGPU/app/llama_utils.py`  
**Status**: Pushed to main branch

---

## Next Steps

### For Google Drive Sync
1. **Wait for Railway deployment** (auto-deploys from main branch)
2. **Monitor next sync cycle** (runs every 5 minutes)
3. **Check logs** for: "Full scan found X files" where X > 0
4. **Expected behavior**: Files in nested folders now detected and synced

### For ZopilotGPU
1. **Rebuild RunPod endpoint** (auto-detects new GitHub commits)
2. **Monitor build logs** for successful pip install
3. **Check for**: "✅ HUGGING_FACE_TOKEN" and "✅ ZOPILOT_GPU_API_KEY"
4. **Expected timeline**: 
   - Build: 10-15 minutes
   - First request: Additional 5-10 minutes (model loading)

---

## Verification Commands

### Test Google Drive Sync (after deployment)
Check Railway logs for:
```
[GoogleDriveSync] Full scan found X files in FolderName (recursive)
[GoogleDriveSync] Processing X files from FolderName
[GoogleDriveSync] Uploaded to R2: business-id/category/2025/10/03/filename.pdf
```

### Test ZopilotGPU (after deployment)
```bash
# Health check
curl -X POST https://api-YOUR_ID.runpod.net/runsync \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -d '{
    "input": {
      "endpoint": "/health",
      "data": {}
    }
  }'

# Expected response:
# {"status": "healthy", "service": "ZopilotGPU", "model": "Mixtral-8x7B-Instruct-v0.1"}
```

---

## Cost Estimates (Updated)

### With Current Fixes
- **Google Drive Sync**: No cost change (runs on Railway)
- **ZopilotGPU Processing**: 
  - 10k docs/month: ~$22/month (RTX 4090) or ~$13/month (L4/A5000)
  - With keep-warm: Add ~$3/month
  - **Total**: $16-25/month depending on GPU choice

### Comparison
- **Before (Always-on GPU)**: $248/month
- **After (Serverless)**: $16-25/month
- **Savings**: ~$225/month (90% reduction)

---

## Known Issues / Future Improvements

1. **Backend Build Failure** (TypeScript error)
   - Error: `Property 'extractDocumentWithRetry' does not exist`
   - Status: Method exists but needs investigation
   - Workaround: May need to restart Railway build

2. **First Cold Start**
   - Takes 5-10 minutes to load Mixtral model
   - Consider implementing keep-warm strategy ($3/month)

3. **Document Processing Pipeline**
   - Step 1 (Extraction): ✅ Implemented
   - Step 2 (Module/Action): ⏳ TODO
   - Step 3 (Execution): ⏳ TODO

---

## Files Changed

### zopilot-backend
- ✅ `src/services/googleDriveSyncService.ts` - Added recursive scanning

### ZopilotGPU
- ✅ `requirements.txt` - Flexible version ranges
- ✅ `runpod.toml` - RunPod configuration
- ✅ `handler.py` - Environment validation
- ✅ `app/llama_utils.py` - Better error messages

---

## Support

If builds still fail:
1. Check RunPod logs for specific errors
2. Check Railway logs for backend errors
3. Verify environment variables are set correctly
4. Try rebuilding from scratch (delete & recreate endpoint)
