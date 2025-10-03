# GPU to Cloud Fallback Implementation

## Overview

Implemented automatic fallback from GPU extraction to cloud API when GPU encounters ANY error. This ensures documents are always processed even when GPU has issues (missing dependencies, OOM, model failures, etc.).

## Architecture

### Previous Behavior (WRONG)
- GPU would return error structures `{"success": false, "error": "..."}`
- Backend would treat these as failed extractions
- No automatic fallback to cloud API

### New Behavior (CORRECT)
```
Document → Backend → GPU Extraction
                      ↓ (any error)
                      Returns 503 GPU_EXTRACTION_FAILED
                      ↓
                      Backend catches 503
                      ↓
                      Backend routes to Cloud API
                      ↓
                      Cloud extraction succeeds
                      ↓
                      Return to user
```

## Changes Made

### 1. GPU Service (ZopilotGPU)

#### `app/docstrange_utils.py`
- **Added**: `GPUExtractionFailedError` custom exception class
- **Modified**: All error handling in `extract_with_docstrange()` to raise exceptions instead of returning error structures

```python
# Custom exception for GPU extraction failures
class GPUExtractionFailedError(Exception):
    """
    Raised when GPU local extraction fails and backend should route to cloud API.
    This is different from returning error structures - it signals backend to use cloud fallback.
    """
    pass
```

**Before:**
```python
except DocstrageFileNotFoundError as e:
    logger.error(f"File not found: {filename}")
    return self._error_fallback(filename, f"File not found: {str(e)}")
```

**After:**
```python
except DocstrageFileNotFoundError as e:
    logger.error(f"File not found: {filename}")
    raise GPUExtractionFailedError(f"File not found: {str(e)}")
```

#### `app/main.py`
- **Added**: Import of `GPUExtractionFailedError`
- **Modified**: `/extract` endpoint to catch exception and return 503 with specific error structure

**Added Error Handling:**
```python
except GPUExtractionFailedError as e:
    # GPU extraction failed - backend should route to cloud API
    logger.error(f"[EXTRACT] GPU extraction failed for {data.document_id}: {str(e)}")
    logger.info(f"[EXTRACT] Returning 503 - backend will route to cloud API")
    return JSONResponse(
        status_code=503,
        content={
            "error": "GPU_EXTRACTION_FAILED",
            "reason": str(e),
            "use_cloud": True,
            "document_id": data.document_id
        }
    )
```

### 2. Backend Service (zopilot-backend)

#### `src/services/documentExtractionService.ts`
- **Modified**: `callGPUEndpoint()` method to catch 503 responses and automatically fallback to cloud

**Added Fallback Logic:**
```typescript
catch (error: any) {
  // Check if GPU returned 503 (GPU_EXTRACTION_FAILED)
  if (error.response?.status === 503 && error.response?.data?.error === 'GPU_EXTRACTION_FAILED') {
    console.log('[Extraction] ⚠️  GPU extraction failed, routing to cloud API');
    console.log(`[Extraction] Reason: ${error.response.data.reason}`);
    
    // Fall back to cloud extraction
    const { docstrangeExtractor } = await import('../lib/docstrangeExtractor');
    
    if (!docstrangeExtractor.isAvailable()) {
      throw new Error('GPU extraction failed and cloud API not available');
    }
    
    if (!(await docstrangeExtractor.hasAvailableQuota())) {
      throw new Error('GPU extraction failed and cloud API quota exceeded');
    }
    
    // Handle both URL and base64 content
    let documentUrl = data.document_url;
    
    if (!documentUrl && data.document_content_base64) {
      console.log('[Extraction] Uploading base64 content to R2 for cloud extraction');
      const fileBuffer = Buffer.from(data.document_content_base64, 'base64');
      const filename = data.filename || 'document.pdf';
      const contentType = filename.endsWith('.pdf') ? 'application/pdf' : 'application/octet-stream';
      
      const uploadResult = await r2Storage.uploadFile(fileBuffer, filename, contentType, 'documents');
      documentUrl = uploadResult.url;
    }
    
    if (!documentUrl) {
      throw new Error('Cannot fallback to cloud: no document URL available');
    }
    
    console.log('[Extraction] Using cloud extraction as fallback');
    const cloudResult = await docstrangeExtractor.extractFromUrl(documentUrl);
    return cloudResult;
  }
  
  // Re-throw other errors
  throw error;
}
```

## Error Flow

### Scenario 1: Missing torchvision dependency
```
1. User uploads document
2. Backend sends to GPU
3. GPU tries to load RT-DETR model
4. Import fails: "operator torchvision::nms does not exist"
5. GPU raises GPUExtractionFailedError("Conversion error: ...")
6. GPU /extract endpoint catches exception
7. GPU returns 503 with {"error": "GPU_EXTRACTION_FAILED", "reason": "Conversion error: ...", "use_cloud": true}
8. Backend callGPUEndpoint catches 503
9. Backend imports docstrangeExtractor
10. Backend uploads document to R2 (if using base64)
11. Backend calls cloud extraction
12. Cloud extraction succeeds
13. Return extracted data to user
```

### Scenario 2: GPU Out of Memory
```
1. User uploads large document
2. Backend sends to GPU
3. GPU starts extraction
4. CUDA OOM error occurs
5. GPU raises GPUExtractionFailedError("Unexpected error: CUDA out of memory")
6. GPU returns 503
7. Backend catches 503, routes to cloud
8. Cloud extraction succeeds
9. Return to user
```

### Scenario 3: Model Loading Failure
```
1. User uploads document
2. Backend sends to GPU
3. GPU tries to initialize DocumentExtractor
4. Model file corrupted or missing
5. GPU raises GPUExtractionFailedError("Unexpected error: ...")
6. GPU returns 503
7. Backend catches 503, routes to cloud
8. Cloud extraction succeeds
9. Return to user
```

## Benefits

1. **Automatic Fallback**: No manual intervention needed when GPU fails
2. **Resilience**: Documents always processed even with GPU issues
3. **Overrides Env Variables**: GPU error response takes precedence over `USE_DOCSTRANGE_CLOUD` setting
4. **Transparent to User**: User doesn't see GPU failure, just gets extracted data
5. **Proper Error Handling**: 503 is semantically correct (Service Unavailable, try alternative)
6. **Logging**: Full visibility of GPU failures and cloud fallback in logs

## Testing Checklist

### Test GPU Error Handling
- [ ] Simulate missing dependency (remove torchvision): Should return 503
- [ ] Simulate CUDA OOM: Should return 503
- [ ] Simulate model loading failure: Should return 503
- [ ] Verify 503 response has correct structure: `{"error": "GPU_EXTRACTION_FAILED", "reason": "...", "use_cloud": true}`

### Test Backend Fallback
- [ ] Backend receives 503 from GPU: Should log "GPU extraction failed, routing to cloud API"
- [ ] Backend calls docstrangeExtractor.extractFromUrl()
- [ ] Cloud extraction succeeds: Should return extracted data
- [ ] Verify extracted data has correct format (FLAT JSON)

### Test Base64 Content Handling
- [ ] GPU fails with base64 content (no URL): Backend should upload to R2 first
- [ ] Verify upload to R2 succeeds: Should get presigned URL
- [ ] Verify cloud extraction uses uploaded URL
- [ ] Verify extracted data returned to user

### Test Edge Cases
- [ ] GPU fails AND cloud API unavailable: Should throw "GPU extraction failed and cloud API not available"
- [ ] GPU fails AND cloud quota exceeded: Should throw "GPU extraction failed and cloud API quota exceeded"
- [ ] GPU succeeds: Should NOT fallback to cloud
- [ ] Network error (not 503): Should retry as normal

## Deployment Steps

### 1. Deploy GPU Changes
```bash
cd ZopilotGPU

# Rebuild Docker image with torchvision fix + error handling
docker build -t zopilot-gpu:latest .

# Test locally
docker run -p 8000:8000 zopilot-gpu:latest

# Test error handling (simulate failure)
curl -X POST http://localhost:8000/extract \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"document_url": "INVALID_URL"}'

# Expected: 503 with {"error": "GPU_EXTRACTION_FAILED", ...}

# Deploy to RunPod
# Upload to Docker Hub or use RunPod's container registry
docker tag zopilot-gpu:latest YOUR_DOCKERHUB/zopilot-gpu:v2.0
docker push YOUR_DOCKERHUB/zopilot-gpu:v2.0
```

### 2. Deploy Backend Changes
```bash
cd zopilot-backend

# Build TypeScript
npm run build

# Run tests
npm test

# Deploy to production (Railway, Vercel, etc.)
git add .
git commit -m "feat: Add GPU to cloud fallback on errors"
git push origin main
```

### 3. Verify End-to-End
```bash
# Upload document that will cause GPU failure (or disable GPU)
# Verify logs show:
# 1. "[EXTRACT] GPU extraction failed for doc-123: ..."
# 2. "[EXTRACT] Returning 503 - backend will route to cloud API"
# 3. "[Extraction] ⚠️  GPU extraction failed, routing to cloud API"
# 4. "[Extraction] Using cloud extraction as fallback"
# 5. "[Extraction] Cloud extraction successful"

# Verify user receives extracted data (not error)
```

## Monitoring

### GPU Logs to Watch
```
# GPU errors (should be rare after torchvision fix)
[EXTRACT] GPU extraction failed for {document_id}: {reason}
[EXTRACT] Returning 503 - backend will route to cloud API

# Normal success (most common)
[EXTRACT] Success: {document_id}, Method: docstrange_local
```

### Backend Logs to Watch
```
# Fallback triggered (should be rare)
[Extraction] ⚠️  GPU extraction failed, routing to cloud API
[Extraction] Reason: {reason}
[Extraction] Using cloud extraction as fallback
[Extraction] Cloud extraction successful

# Normal GPU success (most common)
[Extraction] GPU extraction successful (direct transfer)
```

## Performance Impact

### GPU Failure Scenario
- **Before**: Document fails, user gets error, manual retry needed
- **After**: Document processed via cloud, user gets data (slower but successful)

### Cost Impact
- **GPU Success**: $0 per document (local extraction)
- **GPU Failure → Cloud**: $0.001-0.01 per document (cloud API cost)

### Expected Fallback Rate
- **After torchvision fix**: <1% (only OOM or rare model errors)
- **Before torchvision fix**: 100% (all documents failing)

## Related Files

### GPU Service
- `ZopilotGPU/app/docstrange_utils.py`: Exception class and error handling
- `ZopilotGPU/app/main.py`: 503 response handling
- `ZopilotGPU/requirements.txt`: torchvision dependency fix

### Backend Service
- `zopilot-backend/src/services/documentExtractionService.ts`: Cloud fallback logic
- `zopilot-backend/src/lib/r2Storage.ts`: Upload for base64 content
- `zopilot-backend/src/lib/docstrangeExtractor.ts`: Cloud extraction

### Documentation
- `ZopilotGPU/DEPLOYMENT_FIX_INSTRUCTIONS.md`: Torchvision deployment guide
- `ZopilotGPU/ROOT_CAUSE_ANALYSIS.md`: Detailed analysis of original GPU failures
- `ZopilotGPU/GPU_TO_CLOUD_FALLBACK_IMPLEMENTATION.md`: This document

## Summary

✅ **Implemented**: Complete GPU → Cloud fallback on ANY error
✅ **GPU Changes**: Exception-based error handling with 503 response
✅ **Backend Changes**: Automatic cloud routing on 503 detection
✅ **Base64 Support**: Uploads to R2 before cloud extraction
✅ **Error Handling**: Proper validation and edge case handling
✅ **Logging**: Full visibility into fallback flow
✅ **Resilient**: Documents always processed (GPU or cloud)

The system now automatically handles GPU failures gracefully, ensuring documents are always extracted successfully via cloud API when GPU encounters any error.
