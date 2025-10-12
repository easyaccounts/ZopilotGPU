# Quick Testing Guide - Backend-GPU Alignment

## Pre-Deployment Checklist

- [x] Code changes complete
- [x] No syntax errors
- [ ] Git commit and tag created
- [ ] Docker image built
- [ ] Local testing passed
- [ ] RunPod deployed
- [ ] Backend integration verified

---

## Test 1: Parameter Passing (5 min)

### Objective
Verify GPU receives and uses backend-provided parameters.

### Backend Request
```typescript
await callGPUEndpoint('/prompt', {
  prompt: "Analyze this invoice: ABC Corp, $1000 total",
  max_tokens: 5000,
  temperature: 0.3,
  context: { stage: 'action_selection' }
});
```

### Expected GPU Logs
```
⚙️  Generation config: max_tokens=5000, temp=0.3, max_input=29491
⚙️  [Stage 1] Generation config: max_new_tokens=5000, temp=0.3, max_input=29491
🚀 [Stage 1] Generating classification response (max 5000 tokens)...
```

### ✅ Pass Criteria
- GPU logs show max_new_tokens=5000 (not 2500)
- GPU logs show temp=0.3 (not 0.1)

---

## Test 2: Large Document (15 min)

### Objective
Process invoice with 50+ line items (~10k token prompt).

### Setup
Create invoice JSON with 50 line items, each with description, quantity, price.

### Backend Request
```typescript
const largeExtractedData = {
  parties: [...],
  line_items: [/* 50 items */],
  // ... total ~8k tokens
};

const prompt = buildActionSelectionPrompt(largeExtractedData, businessProfile);
// Prompt should be ~10k tokens

await callGPUEndpoint('/prompt', {
  prompt,
  max_tokens: 3000,
  temperature: 0.1,
  context: { stage: 'action_selection' }
});
```

### Expected GPU Logs
```
🔢 [Stage 1] Tokenizing prompt...
   Input tokens: 9847  // Should be ~10k, NOT capped at 4096
```

### ✅ Pass Criteria
- Input tokens > 8000 (not truncated to 4096)
- Response includes analysis of all line items
- No warnings about truncation

---

## Test 3: Stage 2 Parameter Fix (10 min)

### Objective
Verify Stage 2 uses 3000 tokens and 0.05 temperature (not old 2000/0.1).

### Backend Request
```typescript
await callGPUEndpoint('/prompt', {
  prompt: buildFieldMappingPrompt(...),
  max_tokens: 3000,      // Backend default for Stage 2
  temperature: 0.05,     // Backend default for Stage 2
  context: {
    stage: 'field_mapping',
    action: 'createInvoice',
    entity: 'Invoice'
  }
});
```

### Expected GPU Logs
```
⚙️  [Stage 2] Generation config: max_new_tokens=3000, temp=0.05, max_input=29491
🚀 [Stage 2] Generating field mappings (max 3000 tokens)...
```

### ✅ Pass Criteria
- GPU uses max_new_tokens=3000 (not 2000)
- GPU uses temperature=0.05 (not 0.1)
- Response may be longer than previous 2000 token limit

---

## Test 4: Maximum Context (20 min)

### Objective
Test 32k token support (near maximum Mixtral capacity).

### Setup
Create very large prompt (~28k tokens):
- Business profile: 500 tokens
- Extracted data with 200 line items: 20k tokens
- Action registry: 2k tokens
- Instructions: 5k tokens
Total: ~28k tokens

### Backend Request
```typescript
await callGPUEndpoint('/prompt', {
  prompt: veryLargePrompt,  // ~28k tokens
  max_tokens: 4000,
  temperature: 0.1,
  max_input_length: 29000,
  context: { stage: 'action_selection' }
});
```

### Expected GPU Logs
```
   Input tokens: 28567  // Should accept large input
✅ [Stage 1] Generated XXXX tokens in XXs (XX tok/s)
```

### ✅ Pass Criteria
- Input tokens > 25000 (not truncated)
- No OOM errors
- VRAM usage < 30GB
- Generation completes successfully

---

## Test 5: Response Format Validation (5 min)

### Objective
Ensure response structure unchanged (no regression).

### Stage 1 Response Check
```typescript
assert(response.semantic_analysis !== undefined);
assert(response.suggested_actions !== undefined);
assert(response.overall_confidence !== undefined);

const primaryActions = response.suggested_actions.filter(a => a.action_type === 'PRIMARY');
assert(primaryActions.length === 1, 'Must have exactly 1 PRIMARY action');
```

### Stage 2 Response Check
```typescript
assert(response.field_mappings !== undefined);
assert(response.lookups_required !== undefined);
assert(response.validation !== undefined);

// All validation fields mandatory
assert(response.validation.total_amount_matches !== undefined);
assert(response.validation.calculated_total !== undefined);
assert(response.validation.all_charges_included !== undefined);
assert(Array.isArray(response.validation.charges_found));
assert(Array.isArray(response.validation.warnings));
```

### ✅ Pass Criteria
- All required fields present
- No fields changed from undefined to null
- Backend parser accepts responses without errors

---

## Test 6: End-to-End Integration (15 min)

### Objective
Complete flow from frontend upload to database.

### Steps
1. Upload test invoice via frontend
2. Document processes through OCR
3. Backend sends to GPU for classification
4. GPU returns Stage 1 result
5. Backend sends Stage 2 requests (parallel)
6. GPU returns field mappings
7. Backend resolves lookups
8. Backend validates business rules
9. Actions ready for execution

### Check Points
- [ ] No parse errors in backend logs
- [ ] GPU logs show correct generation configs
- [ ] Stage 1 completes successfully
- [ ] Stage 2 completes for all actions
- [ ] Lookups resolve correctly
- [ ] Validation passes
- [ ] Actions ready for user review

### ✅ Pass Criteria
- Complete flow without errors
- Actions have all required fields
- UI shows actions correctly

---

## Performance Baseline

### Current Metrics (from workingLLM tag)
- Model load: 252s (first time only)
- Stage 1 generation: ~45s @ 17.4 tok/s (2500 tokens)
- Stage 2 generation: ~35s @ 17 tok/s (2000 tokens)
- VRAM: 22.8GB allocated, 8.5GB free

### Expected After Changes
- Model load: 252s (unchanged)
- Stage 1: ~45s @ 17.4 tok/s (2500 tokens, unchanged)
- Stage 2: ~50s @ 17 tok/s (**3000 tokens**, 50% increase)
- VRAM: 22-24GB (slight increase due to longer output)

### Alert Thresholds
- ⚠️  Generation speed < 15 tok/s (investigate)
- ⚠️  VRAM usage > 28GB (potential OOM risk)
- ⚠️  Stage 2 time > 70s (too slow)
- 🚨 Any OOM errors (critical)

---

## Debugging Tips

### If Parameters Not Respected

1. **Check backend request**:
   ```typescript
   console.log('GPU Request:', { prompt, max_tokens, temperature, context });
   ```

2. **Check GPU logs** for generation config:
   ```
   grep "Generation config" runpod_logs.txt
   ```

3. **Verify PromptInput parsing**:
   - Check handler.py receives all fields
   - Check Pydantic doesn't drop fields

### If Token Truncation Occurs

1. **Check input tokens**:
   ```
   grep "Input tokens:" runpod_logs.txt
   ```

2. **Verify max_input_length**:
   - Should default to 29491
   - Backend can override

3. **Check for warnings**:
   ```
   grep "exceeds 32k limit" runpod_logs.txt
   ```

### If Response Parsing Fails

1. **Check response format**:
   - Stage 1: must have semantic_analysis, suggested_actions
   - Stage 2: must have field_mappings, lookups_required, validation

2. **Check validation logs**:
   ```
   grep "Validation" runpod_logs.txt
   ```

3. **Check auto-fix logic**:
   - _validate_stage1_response() fixes missing PRIMARY
   - _validate_stage2_response() adds default validation fields

---

## Rollback Procedure

### If Critical Issues Found

1. **Stop current deployment**:
   ```powershell
   # In RunPod console, stop current pod
   ```

2. **Revert code**:
   ```powershell
   cd d:\Desktop\Zopilot\ZopilotGPU
   git checkout workingLLM
   ```

3. **Rebuild and deploy**:
   ```powershell
   docker build -t zopilotgpu:rollback .
   # Deploy rollback image to RunPod
   ```

4. **Verify rollback**:
   - Check GPU logs for old hardcoded values
   - Test document processing
   - Confirm stable operation

---

## Success Metrics

### Must Pass
- ✅ GPU accepts custom max_tokens (Test 1)
- ✅ GPU processes 10k+ token prompts (Test 2)
- ✅ Stage 2 uses 3000 tokens, 0.05 temp (Test 3)
- ✅ Response formats unchanged (Test 5)
- ✅ End-to-end flow works (Test 6)

### Should Pass
- ✅ GPU handles 32k token context (Test 4)
- ✅ Performance within thresholds
- ✅ No memory leaks over time
- ✅ Concurrent requests work (3 parallel Stage 2)

### Nice to Have
- ✅ Improved Stage 2 accuracy (lower temp)
- ✅ Fewer truncated responses
- ✅ Better handling of large documents

---

## Contact

**Implementation**: `IMPLEMENTATION_COMPLETE.md`  
**Alignment Plan**: `BACKEND_GPU_ALIGNMENT_PLAN.md`  
**Classification Flow**: `CLASSIFICATION_FLOW_COMPLETE.md`  

**Git Tags**:
- `workingLLM`: Stable state before alignment
- `backend-aligned-v1`: Current implementation (to be created)

**Key Changes**:
- PromptInput: Added max_tokens, temperature, etc.
- classify_stage1/2: Accept generation_config
- Token limits: 4096 → 29491 input, 32768 max
- Stage 2: 2000 → 3000 output, 0.1 → 0.05 temp
