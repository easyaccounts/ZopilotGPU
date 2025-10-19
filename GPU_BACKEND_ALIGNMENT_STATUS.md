# GPU-Backend Alignment Analysis
## Date: October 18, 2025

## Executive Summary

✅ **Overall Status**: GPU and Backend are **mostly aligned** but missing support for 1 new stage.

The backend has evolved with 6 new sub-stages (0.5, 1.5, 2, 3, 4, 5), but **only 3 of these require GPU inference**:
- Stage 1: Action Selection (✅ GPU has `action_selection`)
- Stage 2: Action Schema Analysis (❌ GPU missing `action_schema_analysis` route)
- Stage 4: Field Mapping (✅ GPU has `field_mapping_batch`)

**Required Action**: Add GPU support for `action_schema_analysis` stage.

---

## Backend Classification Flow (Enhanced v3.1)

### Stage 0: Duplicate Detection
**Location**: Backend only  
**Implementation**: Database query  
**GPU Required**: ❌ No

### Stage 0.5: Math Validation
**Location**: Backend only (line 355-500)  
**Implementation**: JavaScript math validation  
**GPU Required**: ❌ No  
**Purpose**: Validate subtotal + tax = total, block on errors

### Stage 1: Semantic Analysis + Action Selection
**Location**: Backend calls GPU (line 1016)  
**GPU Stage**: `action_selection` ✅  
**GPU Function**: `classify_stage1()` in `app/classification.py`  
**Status**: ✅ **ALIGNED**

**Backend Call**:
```typescript
await this.callGPUEndpoint('/prompt', {
  prompt: buildActionSelectionPrompt(...),
  max_tokens: 2500,
  temperature: 0.1,
  context: {
    stage: 'action_selection',
    business: businessProfile.registered_name,
    software: businessProfile.accounting_software
  }
});
```

**GPU Handler**:
```python
if stage == 'action_selection':
    from app.classification import classify_stage1
    output = classify_stage1(data.prompt, data.context, generation_config)
```

### Stage 1.5: Feasibility Check
**Location**: Backend only (line 501-611)  
**Implementation**: Backend validation logic  
**GPU Required**: ❌ No  
**Purpose**: Check if business can execute action (inventory tracking, thresholds, etc.)

### Stage 2: Action Schema Analysis
**Location**: Backend calls GPU (line 7111)  
**GPU Stage**: `action_schema_analysis` ❌ **MISSING**  
**Status**: ❌ **NOT ALIGNED** - Backend calls new stage, GPU doesn't recognize it

**Backend Call**:
```typescript
const response = await this.callGPUEndpoint('/prompt', {
  prompt,  // Analyzes action schema to determine required entities
  max_tokens: 2000,
  temperature: 0.05,
  context: { 
    stage: 'action_schema_analysis',  // ❌ GPU doesn't handle this
    action: action.action,
    document_id: semanticAnalysis.document_id
  }
});
```

**Current GPU Behavior**:
Falls through to legacy `generate_with_llama()` handler because `action_schema_analysis` is not in the routing logic. This will work but is not optimized.

**Expected Output**:
```json
{
  "entities_required": [
    {
      "entity_type": "Customer",
      "field_name": "customer_id",
      "is_required": true,
      "can_create": true,
      "fallback_strategy": "Use 'Cash Customer' placeholder"
    }
  ],
  "api_dependencies": ["customers", "items"],
  "validation_requirements": ["customer_id must be valid UUID"],
  "reasoning": "Invoice requires customer reference..."
}
```

### Stage 3: Entity Resolution
**Location**: Backend only (line 661-752)  
**Implementation**: Backend API service calls  
**GPU Required**: ❌ No  
**Purpose**: Fetch/create customers, vendors, items from accounting software APIs

### Stage 4: Field Mapping
**Location**: Backend calls GPU (line 1216)  
**GPU Stage**: `field_mapping_batch` ✅  
**GPU Function**: `classify_stage2()` in `app/classification.py`  
**Status**: ✅ **ALIGNED**

**Backend Call**:
```typescript
const response = await this.callGPUEndpoint('/prompt', {
  prompt: batchPrompt,  // Now includes resolved entity IDs
  max_tokens: 4000,
  temperature: 0.05,
  context: {
    stage: 'field_mapping_batch',
    action_count: actionsToProcess.length,
    actions: actionsToProcess.map(a => a.action)
  }
});
```

**GPU Handler**:
```python
elif stage == 'field_mapping' or stage == 'field_mapping_batch':
    from app.classification import classify_stage2
    output = classify_stage2(data.prompt, data.context, generation_config)
```

### Stage 5: Schema Validation
**Location**: Backend only (line 806-900)  
**Implementation**: Backend validates against APISchemaLoader  
**GPU Required**: ❌ No  
**Purpose**: Validate field mappings against actual API schemas, trigger rollback if needed

---

## Alignment Issues

### ❌ Issue 1: Missing `action_schema_analysis` Stage

**Problem**: Backend Stage 2 (Action Schema Analysis) calls GPU with `stage: 'action_schema_analysis'`, but GPU doesn't have a dedicated handler for this stage.

**Current Behavior**: 
- GPU falls through to legacy handler `generate_with_llama()`
- Will still work but not optimized for this specific task
- May not return expected JSON structure consistently

**Impact**: 
- Medium severity
- Stage will work but may have suboptimal performance
- No structured parsing/validation

**Fix Required in**: `ZopilotGPU/app/main.py` and `ZopilotGPU/app/classification.py`

---

## Recommended Changes

### 1. Add `action_schema_analysis` Stage to GPU

**File**: `ZopilotGPU/app/main.py` (lines 310-330)

**Current Code**:
```python
if stage == 'action_selection':
    # Stage 1
    output = classify_stage1(...)
elif stage == 'field_mapping' or stage == 'field_mapping_batch':
    # Stage 2
    output = classify_stage2(...)
else:
    # Legacy
    output = generate_with_llama(...)
```

**Proposed Code**:
```python
if stage == 'action_selection':
    # Stage 1: Action Selection
    output = classify_stage1(...)
elif stage == 'action_schema_analysis':
    # Stage 2: Action Schema Analysis (NEW)
    from app.classification import classify_stage2_schema
    output = classify_stage2_schema(data.prompt, data.context, generation_config)
elif stage == 'field_mapping' or stage == 'field_mapping_batch':
    # Stage 4: Field Mapping
    output = classify_stage2(...)
else:
    # Legacy
    output = generate_with_llama(...)
```

### 2. Add `classify_stage2_schema()` Function

**File**: `ZopilotGPU/app/classification.py` (new function)

**Purpose**: Analyze action schema and determine required entities

**Signature**:
```python
def classify_stage2_schema(
    prompt: str, 
    context: Dict[str, Any], 
    generation_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stage 2: Action Schema Analysis
    
    Analyzes an action's API schema to determine:
    - Which entities are required (Customer, Vendor, Item, Account)
    - Which fields are mandatory vs optional
    - API dependencies and validation rules
    
    Args:
        prompt: Schema analysis prompt from backend
        context: {"stage": "action_schema_analysis", "action": "createInvoice"}
        generation_config: Generation parameters
    
    Returns:
        {
            "entities_required": [
                {
                    "entity_type": "Customer",
                    "field_name": "customer_id",
                    "is_required": true,
                    "can_create": true,
                    "fallback_strategy": "..."
                }
            ],
            "api_dependencies": ["customers", "items"],
            "validation_requirements": [...],
            "reasoning": "..."
        }
    """
    logger.info(f"🎯 [Stage 2] Schema analysis for action: {context.get('action')}")
    
    # Use similar generation logic to classify_stage1
    # Lower temperature (0.05) for precise schema analysis
    # Max tokens: 2000 (backend sends this)
    
    # ... implementation similar to classify_stage1/stage2
```

---

## Testing Checklist

After implementing changes:

- [ ] Test `action_selection` stage (existing)
  - Verify Stage 1 still works
  - Check JSON output structure

- [ ] Test `action_schema_analysis` stage (new)
  - Send test request with `stage: 'action_schema_analysis'`
  - Verify entities_required array populated
  - Check reasoning field present

- [ ] Test `field_mapping_batch` stage (existing)
  - Verify Stage 4 still works
  - Check batch output format

- [ ] Integration test with backend
  - Run full classification flow
  - Verify all 3 GPU stages called correctly
  - Check audit logs for stage completion

---

## Alternative: No Changes Needed?

**Argument**: The current GPU fallback to `generate_with_llama()` for `action_schema_analysis` may be sufficient because:

1. The prompt structure already contains all necessary instructions
2. Mixtral will follow JSON format instructions regardless of routing
3. Backend parses response and validates structure anyway

**Counter-argument**: Dedicated handler provides:
- Consistent logging for debugging
- Stage-specific error handling
- Optimized generation parameters
- Better monitoring/observability

**Recommendation**: **Implement the dedicated handler** for better maintainability and debugging, even if current behavior works.

---

## Summary

| Stage | Backend | GPU Support | Status |
|-------|---------|-------------|--------|
| 0: Duplicate Detection | ✅ | N/A (DB only) | ✅ Aligned |
| 0.5: Math Validation | ✅ | N/A (JS only) | ✅ Aligned |
| 1: Action Selection | ✅ | ✅ `action_selection` | ✅ Aligned |
| 1.5: Feasibility Check | ✅ | N/A (Backend logic) | ✅ Aligned |
| 2: Schema Analysis | ✅ | ❌ Missing route | ❌ **Needs Fix** |
| 3: Entity Resolution | ✅ | N/A (API calls) | ✅ Aligned |
| 4: Field Mapping | ✅ | ✅ `field_mapping_batch` | ✅ Aligned |
| 5: Schema Validation | ✅ | N/A (Backend logic) | ✅ Aligned |

**Action Required**: Add `action_schema_analysis` stage handler to GPU service.

**Estimated Effort**: 1-2 hours (copy classify_stage1 pattern, adjust for schema analysis)

**Priority**: Medium (current fallback works, but dedicated handler is better)
