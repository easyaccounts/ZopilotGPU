# Stage 2 Removal from GPU - Complete

## Date: October 19, 2025

## Summary
Removed obsolete Stage 2 (Action Schema Analysis) code from GPU server. Stage 2 now runs entirely in the backend using ActionRegistry + APISchemaLoader (CPU-only, ~5-20ms).

## Changes Made

### 1. `app/classification.py`

**Removed:**
- `classify_stage2_schema()` function (was lines 1059-1231, ~176 lines)
  - LLM-powered schema analysis (2000 tokens, temp 0.05)
  - Returned entities_required, api_dependencies, validation_requirements
  - **No longer called by backend**

**Updated:**
- File header docstring:
  - Removed Stage 2 from "Handles Stage 1 and Stage 2" description
  - Added Stage 0.5 (Math Validation) documentation
  - Clarified Stage 4 is Field Mapping
  - Added "REMOVED STAGES" section noting Stage 2 now runs in backend
  - Updated pipeline flow diagram

- `classify_stage2()` function docstring:
  - Renamed to "Stage 4: Field Mapping" in documentation
  - Added NOTE about legacy naming (function name is stage2 but actually Stage 4)
  - Clarified Stage 2 (Action Schema Analysis) runs in backend

- Log messages:
  - Changed all `[Stage 2]` log messages to `[Stage 4]` (~20+ occurrences)
  - Now accurately reflects pipeline position

**Replaced with:**
```python
# ============================================
# STAGE 2: REMOVED - Now runs in backend
# ============================================
# Stage 2 (Action Schema Analysis) has been moved to backend
# Uses ActionRegistry + APISchemaLoader (CPU-only, ~5-20ms)
# No longer requires GPU inference
# Backend implementation: documentClassificationService.performActionSchemaAnalysis()
```

### 2. `app/main.py`

**Removed:**
- `action_schema_analysis` stage handler (was lines 325-330, ~6 lines)
  ```python
  elif stage == 'action_schema_analysis':
      logger.info(f"[PROMPT] 📋 Stage 2: Action Schema Analysis")
      from app.classification import classify_stage2_schema
      output = await asyncio.get_event_loop().run_in_executor(
          None, classify_stage2_schema, data.prompt, data.context, generation_config
      )
  ```

**Result:**
- GPU server no longer accepts `action_schema_analysis` stage requests
- Backend won't send these requests anyway (uses local ActionRegistry)

## Current GPU Stage Handlers

After removal, GPU server handles:

1. ✅ **Stage 0.5**: `math_validation` → `classify_stage0_5_math()`
2. ✅ **Stage 1**: `action_selection` → `classify_stage1()`
3. ❌ **Stage 2**: REMOVED (runs in backend)
4. ❌ **Stage 3**: Never used GPU (backend entity resolution)
5. ✅ **Stage 4**: `field_mapping` / `field_mapping_batch` → `classify_stage2()` (legacy name)

## Backend Stage 2 Implementation

**Location**: `zopilot-backend/src/services/documentClassification/documentClassificationService.ts`

**Method**: `performActionSchemaAnalysis()` (line 7044)

**How it works**:
```typescript
// Use ActionRegistry to get required entity types (FAST - no GPU call!)
const actionRegistry = this.getActionRegistry(businessProfile.accounting_software);
const requiredEntityTypes = actionRegistry.getRequiredEntitiesForAction(action.action);

// Get API schema for field structure (local file load)
const apiSchema = await APISchemaLoader.getSchemaForAction(...);

// Deterministic mapping (5-20ms, no GPU!)
const entitiesRequired = requiredEntityTypes.map(entityType => {...});
```

**Performance**: ~5-20ms CPU-only vs 500ms-2s GPU call

## Lines Removed

- **classification.py**: ~176 lines removed
- **main.py**: ~6 lines removed
- **Total**: ~182 lines of obsolete GPU code removed

## Benefits

1. ✅ **Faster**: 5-20ms CPU vs 500ms-2s GPU
2. ✅ **Deterministic**: No LLM hallucination risk
3. ✅ **Scalable**: No GPU VRAM consumption for schema analysis
4. ✅ **Maintainable**: Schema logic in one place (ActionRegistry)
5. ✅ **Cost-effective**: No GPU compute costs for Stage 2

## Verification

**Checked:**
- ✅ No `classify_stage2_schema` references in classification.py
- ✅ No `action_schema_analysis` handler in main.py
- ✅ File headers updated to reflect Stage 2 removal
- ✅ All `[Stage 2]` logs changed to `[Stage 4]` for field mapping
- ✅ Function docstrings updated with clarifications

**Pipeline Flow:**
```
Document Upload
    ↓
Stage 0.5: Math Validation (GPU) [OPTIONAL]
    ↓
Stage 1: Action Selection (GPU)
    ↓
Stage 2: Action Schema Analysis (BACKEND - ActionRegistry) ← REMOVED FROM GPU
    ↓
Stage 3: Entity Resolution (BACKEND - Database lookups)
    ↓
Stage 4: Field Mapping (GPU - classify_stage2 function)
    ↓
Stage 5: API Execution (BACKEND - POST to accounting software)
```

## Related Documentation

- Backend Stage 2: `documentClassificationService.ts` line 7044
- Action Registry: `actionRegistry.ts` 
- API Schema Loader: `apiSchemaLoader.ts`
- GPU Stages: `ZopilotGPU/app/classification.py`

## Notes

- `classify_stage2()` function name is legacy - it actually handles **Stage 4** (Field Mapping)
- Stage numbering was reorganized but function names kept for backwards compatibility
- All log messages now correctly show `[Stage 4]` instead of misleading `[Stage 2]`
