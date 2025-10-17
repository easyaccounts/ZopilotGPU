# Critical Bugs Fixed - Production Classification Failure

## Date: 2025-01-29

## Summary
Fixed THREE critical bugs causing 100% classification failure in production:
- Two GPU bugs causing malformed JSON output
- One backend bug causing database query errors

---

## Bug #1: JSON Repair Removing Outer Brace
**File:** `ZopilotGPU/app/classification.py`  
**Lines:** 458-559 (repair_json function)  
**Severity:** CRITICAL

### Problem
The JSON repair function had logic conflict:
1. Issue #2 added outer wrapper: `{}` → `{{}}`
2. Issue #7 removed leading `{`: `{{` → `{` (thinking it was a duplicate)
3. Result: Removed the `{` we just added, back to invalid JSON

### Root Cause
Issue #7 (`json_str.startswith('{{')`) would trigger EVERY time Issue #2 added a wrapper.

### Fix Applied
```python
# Track if we added outer wrapper to skip Issue #7
needs_outer_wrapper = not json_str.startswith('{')
if needs_outer_wrapper:
    json_str = '{\n' + json_str

# FIXED: Skip Issue #7 if we added wrapper (prevents removing what we just added)
if not needs_outer_wrapper and json_str.count('{') > json_str.count('}'):
    if json_str.startswith('{{'):
        json_str = json_str[1:]  # Remove leading {
```

### Impact
- Prevents JSON repair from destroying its own fixes
- Allows proper handling of LLM output missing outer braces

---

## Bug #2: Decoder Stripping Forced Opening Brace (PRIMARY BUG)
**File:** `ZopilotGPU/app/classification.py`  
**Lines:** 160-176 (Stage 1), 348-366 (Stage 2)  
**Severity:** CRITICAL

### Problem
The prompt engineering forced JSON output by ending with `[/INST]{`, but the decoder excluded this forced character:
```python
# Prompt forces: [/INST]{
# Model generates: "accounting_relevance": {...}
# Full output: [/INST]{"accounting_relevance": {...}

# But decoder does this:
decoded_output = processor.tokenizer.decode(outputs[0][input_tokens:], skip_special_tokens=True)
# Result: "accounting_relevance": {...}  (missing opening {)
```

### Root Cause
`outputs[0][input_tokens:]` slices AFTER the prompt tokens, excluding the forced `{` character.

### Discovery
User asked: **"instead of repair are we already enforcing in the prompt for a json output?"**

This question revealed the root cause - we WERE enforcing in the prompt, but the decoder was stripping it.

### Fix Applied (Stage 1)
```python
# Line 160-176
# FIX: Prompt ends with [/INST]{ but decoder excludes prompt tokens
# The tokenizer.decode() with outputs[0][input_tokens:] skips the forced {
# We need to restore it since the model was trained to continue from there
decoded_output = processor.tokenizer.decode(
    outputs[0][input_tokens:], 
    skip_special_tokens=True
)

# Restore the { that was forced in the prompt but excluded from decoding
response_text = "{" + decoded_output
```

### Fix Applied (Stage 2)
```python
# Line 348-366 (identical fix for field mapping)
decoded_output = processor.tokenizer.decode(
    outputs[0][input_tokens:], 
    skip_special_tokens=True
)

# Restore the { that was forced in the prompt but excluded from decoding
response_text = "{" + decoded_output
```

### Impact
- PRIMARY FIX for classification failures
- Simpler solution than complex JSON repair logic
- Decoder output now matches prompt engineering intent
- JSON repair becomes backup safety net

---

## Bug #3: Backend Query Using Non-Existent Column
**File:** `zopilot-backend/src/routes/system.ts`  
**Lines:** 99-101  
**Severity:** HIGH

### Problem
Query was using non-existent `status` column:
```sql
SELECT
  COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
  COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing,
  COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
FROM documents
WHERE business_id = $1
```

### Database Error
```
ERROR: column "status" does not exist at character 39
STATEMENT: SELECT COUNT(CASE WHEN status = 'pending'...)
```

### Schema Reality
Documents table has:
- ✅ `processing_status` VARCHAR(50) - Status: uploaded, extracted, classified, etc.
- ✅ `sync_status` VARCHAR(50) - Status: pending, preview_required, synced, failed
- ❌ `status` - DOES NOT EXIST (legacy_status is deprecated)

### Fix Applied
```typescript
// Get document processing status
const { rows: documentRows } = await pool.query(`
  SELECT
    COUNT(CASE WHEN processing_status IN ('uploaded', 'extracted') THEN 1 END) as pending,
    COUNT(CASE WHEN processing_status IN ('classified', 'under_review', 'ready_for_review') THEN 1 END) as processing,
    COUNT(CASE WHEN processing_status = 'posted' THEN 1 END) as completed
  FROM documents
  WHERE business_id = $1
`, [businessId]);
```

### Status Mapping
- **pending** → processing_status IN ('uploaded', 'extracted')
- **processing** → processing_status IN ('classified', 'under_review', 'ready_for_review')
- **completed** → processing_status = 'posted'

### Impact
- Fixes dashboard/statistics endpoint failures
- Query now matches current schema
- Proper status categorization

---

## Deployment Steps

### 1. Build GPU Docker Image
```bash
cd D:\Desktop\Zopilot\ZopilotGPU
docker build -t zopilotgpu:decoder-fix .
```

### 2. Deploy to RunPod
Update endpoint: `zfr55q0syj8ymg`

### 3. Backend Changes
Backend fix already applied to `system.ts` - no deployment needed if using hot reload.

### 4. Test Classification
Upload test document to verify:
- ✅ Stage 1 classification succeeds
- ✅ Stage 2 field mapping succeeds  
- ✅ No JSON parsing errors
- ✅ Database logging works
- ✅ Dashboard statistics load correctly

---

## Verification Logs

### Before Fix (Production Logs)
```
ERROR: JSON parsing failed: Extra data: line 2 column 31 (char 32)
ERROR: column "status" does not exist at character 39
```

### After Fix (Expected)
```
INFO: Stage 1 classification successful
INFO: Stage 2 field mapping successful
INFO: Document classified as [type]
INFO: Dashboard statistics loaded
```

---

## Related Documents
- `ROOT_CAUSE_ANALYSIS.md` - Detailed analysis of decoder bug
- `complete-schema.sql` - Database schema reference
- Production logs from RunPod and backend

## Credits
Issue discovered through systematic log analysis and user's insightful question about prompt enforcement.
