# GPU-Backend Alignment - Complete Analysis
## Date: October 18, 2025

## Executive Summary

**Critical Finding**: Backend has implemented Stages 0.5 and 1.5 with **hardcoded TypeScript logic**, but the original design requires **ALL stages to be LLM-powered via GPU prompts**.

### Current Misalignment

| Stage | Current Implementation | Expected Implementation | Status |
|-------|----------------------|------------------------|---------|
| 0.5: Math Validation | ❌ TypeScript logic (line 6761) | ✅ LLM via GPU prompt | **MISALIGNED** |
| 1: Action Selection | ✅ GPU (`action_selection`) | ✅ GPU | **ALIGNED** |
| 1.5: Feasibility Check | ❌ TypeScript logic (line 6944) | ✅ LLM via GPU prompt | **MISALIGNED** |
| 2: Schema Analysis | ⚠️ GPU (no dedicated handler) | ✅ GPU (`action_schema_analysis`) | **PARTIAL** |
| 3: Entity Resolution | ✅ Backend API calls | ✅ Backend API calls | **ALIGNED** |
| 4: Field Mapping | ✅ GPU (`field_mapping_batch`) | ✅ GPU | **ALIGNED** |
| 5: Schema Validation | ❌ TypeScript logic (line 7711) | ✅ LLM via GPU prompt? | **UNCLEAR** |

---

## Required Changes

### 1. ❌ REMOVE: Hardcoded Math Validation (Stage 0.5)

**Current Implementation** (line 6761-6943):
```typescript
private validateDocumentMath(extractedData: any): MathValidation {
  // 182 lines of TypeScript calculation logic
  // Validates: subtotal + tax = total
  // Detects: multi-tax, proration, FX, tiered pricing
}
```

**Required Change**: Replace with GPU call
```typescript
private async validateDocumentMath(
  extractedData: GPUExtractionResponse,
  documentId: string
): Promise<MathValidation> {
  const prompt = this.buildMathValidationPrompt(extractedData);
  
  const response = await this.callGPUEndpoint('/prompt', {
    prompt,
    max_tokens: 1500,
    temperature: 0.05,  // Low temp for math accuracy
    context: {
      stage: 'math_validation',
      document_id: documentId
    }
  });
  
  return this.parseMathValidationResponse(response);
}
```

**GPU Handler Needed**: `classify_stage0_5_math()` in `ZopilotGPU/app/classification.py`

---

### 2. ❌ REMOVE: Hardcoded Feasibility Check (Stage 1.5)

**Current Implementation** (line 6944-7035):
```typescript
private async validateActionFeasibility(
  action: SuggestedAction,
  businessProfile: BusinessProfile
): Promise<FeasibilityResult> {
  // 91 lines of TypeScript business rules
  // Checks: inventory capability, fixed asset threshold, foreign currency
}
```

**Required Change**: Replace with GPU call
```typescript
private async validateActionFeasibility(
  action: SuggestedAction,
  businessProfile: BusinessProfile,
  semanticAnalysis: SemanticAnalysis,
  documentId: string
): Promise<FeasibilityResult> {
  const prompt = this.buildFeasibilityCheckPrompt(
    action,
    businessProfile,
    semanticAnalysis
  );
  
  const response = await this.callGPUEndpoint('/prompt', {
    prompt,
    max_tokens: 1000,
    temperature: 0.1,
    context: {
      stage: 'feasibility_check',
      action: action.action,
      document_id: documentId
    }
  });
  
  return this.parseFeasibilityCheckResponse(response);
}
```

**GPU Handler Needed**: `classify_stage1_5_feasibility()` in `ZopilotGPU/app/classification.py`

---

### 3. ⚠️ ADD: Missing Stage 2 Handler (Action Schema Analysis)

**Current Backend Call** (line 7111):
```typescript
const response = await this.callGPUEndpoint('/prompt', {
  prompt,
  max_tokens: 2000,
  temperature: 0.05,
  context: { 
    stage: 'action_schema_analysis',  // ❌ GPU doesn't recognize this
    action: action.action
  }
});
```

**GPU Status**: Falls through to legacy handler (works but not optimal)

**Required**: Add dedicated handler in GPU

---

### 4. ❓ CLARIFY: Schema Validation (Stage 5)

**Current Implementation** (line 7711-7916):
```typescript
private validateAgainstAPISchema(
  mappedFields: any,
  apiSchema: any,
  actionName: string
): SchemaValidationResult {
  // 205 lines of TypeScript schema validation
  // Checks: required fields, invalid fields, data types
}
```

**Question**: Should this also be LLM-powered for intelligent validation?

**Options**:
- **A) Keep as TypeScript** - Schema validation is deterministic, doesn't need LLM
- **B) Make LLM-powered** - For better error messages and intelligent fallbacks

**Recommendation**: Keep as TypeScript (deterministic validation is better for schema)

---

## GPU Service Changes Required

### File 1: `ZopilotGPU/app/main.py`

**Add Stage Routing** (line ~310):
```python
if stage == 'action_selection':
    # Stage 1: Action Selection
    from app.classification import classify_stage1
    output = classify_stage1(data.prompt, data.context, generation_config)

elif stage == 'math_validation':
    # Stage 0.5: Math Validation (NEW)
    from app.classification import classify_stage0_5_math
    output = classify_stage0_5_math(data.prompt, data.context, generation_config)

elif stage == 'feasibility_check':
    # Stage 1.5: Feasibility Check (NEW)
    from app.classification import classify_stage1_5_feasibility
    output = classify_stage1_5_feasibility(data.prompt, data.context, generation_config)

elif stage == 'action_schema_analysis':
    # Stage 2: Action Schema Analysis (NEW)
    from app.classification import classify_stage2_schema
    output = classify_stage2_schema(data.prompt, data.context, generation_config)

elif stage == 'field_mapping' or stage == 'field_mapping_batch':
    # Stage 4: Field Mapping
    from app.classification import classify_stage2
    output = classify_stage2(data.prompt, data.context, generation_config)

else:
    # Legacy fallback
    output = generate_with_llama(data.prompt, data.context, generation_config)
```

---

### File 2: `ZopilotGPU/app/classification.py`

**Add New Functions**:

#### Function 1: Math Validation
```python
def classify_stage0_5_math(
    prompt: str, 
    context: Dict[str, Any], 
    generation_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stage 0.5: Math Validation
    
    Validates document calculations using LLM reasoning.
    Detects: subtotal + tax = total, multi-tax, proration, FX conversion
    
    Returns:
        {
            "passed": bool,
            "errors": [
                {
                    "type": "total_mismatch",
                    "field": "total_amount",
                    "expected": 1000.00,
                    "actual": 1050.00,
                    "discrepancy": -50.00,
                    "message": "..."
                }
            ],
            "warnings": [...],
            "calculations": {
                "subtotal": 900,
                "tax_amount": 90,
                "charges": 10,
                "calculated_total": 1000,
                "document_total": 1050
            },
            "complexity": {
                "has_multiple_taxes": bool,
                "has_proration": bool,
                "has_foreign_currency": bool,
                "needs_llm_validation": bool
            }
        }
    """
    logger.info("🧮 [Stage 0.5] Math validation")
    
    if generation_config is None:
        generation_config = {}
    
    max_new_tokens = generation_config.get('max_new_tokens', 1500)
    temperature = generation_config.get('temperature', 0.05)  # Low for math
    
    # ... implementation
```

#### Function 2: Feasibility Check
```python
def classify_stage1_5_feasibility(
    prompt: str, 
    context: Dict[str, Any], 
    generation_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stage 1.5: Business Feasibility Check
    
    Validates if action is compatible with business capabilities.
    
    Returns:
        {
            "feasible": bool,
            "reason": "...",
            "checks_performed": [
                {
                    "check_name": "inventory_capability",
                    "passed": bool,
                    "reason": "..."
                }
            ],
            "alternative_actions": ["create_expense"],
            "confidence": 85
        }
    """
    logger.info(f"🔍 [Stage 1.5] Feasibility check for {context.get('action')}")
    
    if generation_config is None:
        generation_config = {}
    
    max_new_tokens = generation_config.get('max_new_tokens', 1000)
    temperature = generation_config.get('temperature', 0.1)
    
    # ... implementation
```

#### Function 3: Action Schema Analysis
```python
def classify_stage2_schema(
    prompt: str, 
    context: Dict[str, Any], 
    generation_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Stage 2: Action Schema Analysis
    
    Analyzes action schema to determine required entities and dependencies.
    
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
    logger.info(f"📋 [Stage 2] Schema analysis for {context.get('action')}")
    
    if generation_config is None:
        generation_config = {}
    
    max_new_tokens = generation_config.get('max_new_tokens', 2000)
    temperature = generation_config.get('temperature', 0.05)
    
    # ... implementation
```

---

## Backend Changes Required

### File: `src/services/documentClassification/documentClassificationService.ts`

#### 1. Replace `validateDocumentMath()` method (line 6761-6943)

**Before** (182 lines):
```typescript
private validateDocumentMath(extractedData: any): MathValidation {
  const errors: MathValidation['errors'] = [];
  // ... 180 lines of TypeScript math logic ...
  return { passed, errors, warnings, calculations, complexity };
}
```

**After**:
```typescript
private async validateDocumentMath(
  extractedData: GPUExtractionResponse,
  documentId: string
): Promise<MathValidation> {
  const prompt = this.buildMathValidationPrompt(extractedData);
  
  const response = await this.callGPUEndpoint('/prompt', {
    prompt,
    max_tokens: 1500,
    temperature: 0.05,
    context: {
      stage: 'math_validation',
      document_id: documentId
    }
  });
  
  return this.parseMathValidationResponse(response);
}

private buildMathValidationPrompt(extractedData: GPUExtractionResponse): string {
  return `You are a financial document validator. Analyze the following extracted data and validate all mathematical calculations.

EXTRACTED DATA:
${JSON.stringify(extractedData, null, 2)}

VALIDATION REQUIREMENTS:
1. Check: subtotal + tax_amount + charges = total_amount (allow 5 cent tolerance)
2. Check: tax calculation matches declared rate
3. Check: line items sum to subtotal
4. Detect: multiple tax rates, proration, foreign currency, tiered pricing

RESPOND WITH JSON:
{
  "passed": boolean,
  "errors": [
    {
      "type": "total_mismatch|tax_mismatch|line_items_mismatch",
      "field": "field_name",
      "expected": number,
      "actual": number,
      "discrepancy": number,
      "message": "detailed explanation"
    }
  ],
  "warnings": ["warning messages"],
  "calculations": {
    "subtotal": number,
    "tax_amount": number,
    "charges": number,
    "calculated_total": number,
    "document_total": number
  },
  "complexity": {
    "has_multiple_taxes": boolean,
    "has_proration": boolean,
    "has_foreign_currency": boolean,
    "needs_llm_validation": boolean
  }
}`;
}

private parseMathValidationResponse(response: any): MathValidation {
  try {
    const output = typeof response.output === 'string' 
      ? JSON.parse(response.output) 
      : response.output;
    
    return {
      passed: output.passed,
      errors: output.errors || [],
      warnings: output.warnings || [],
      calculations: output.calculations,
      complexity: output.complexity
    };
  } catch (error) {
    console.error('[Math Validation] Failed to parse GPU response:', error);
    throw new Error('Failed to parse math validation response');
  }
}
```

#### 2. Replace `validateActionFeasibility()` method (line 6944-7035)

**Before** (91 lines):
```typescript
private async validateActionFeasibility(
  action: Partial<SuggestedAction> & { action: string },
  businessProfile: BusinessProfile
): Promise<FeasibilityResult> {
  const checks: FeasibilityResult['checks_performed'] = [];
  // ... 85 lines of TypeScript business rules ...
  return { feasible, reason, checks_performed: checks, alternative_actions, confidence };
}
```

**After**:
```typescript
private async validateActionFeasibility(
  action: SuggestedAction,
  businessProfile: BusinessProfile,
  semanticAnalysis: SemanticAnalysis,
  documentId: string
): Promise<FeasibilityResult> {
  const prompt = this.buildFeasibilityCheckPrompt(action, businessProfile, semanticAnalysis);
  
  const response = await this.callGPUEndpoint('/prompt', {
    prompt,
    max_tokens: 1000,
    temperature: 0.1,
    context: {
      stage: 'feasibility_check',
      action: action.action,
      document_id: documentId
    }
  });
  
  return this.parseFeasibilityCheckResponse(response);
}

private buildFeasibilityCheckPrompt(
  action: SuggestedAction,
  businessProfile: BusinessProfile,
  semanticAnalysis: SemanticAnalysis
): string {
  return `You are a business feasibility analyst. Determine if the selected action is compatible with the business's capabilities.

SELECTED ACTION: ${action.action}
ENTITY: ${action.entity}
REASONING: ${action.reasoning}

BUSINESS PROFILE:
- Business Type: ${businessProfile.business_type}
- Industry: ${businessProfile.industry_sector}
- Has Inventory: ${businessProfile.has_inventory}
- Fixed Asset Threshold: ${businessProfile.fixed_asset_threshold}
- Has Foreign Operations: ${businessProfile.has_foreign_operations}
- Collects Sales Tax: ${businessProfile.collects_sales_tax}

DOCUMENT ANALYSIS:
- Document Type: ${semanticAnalysis.document_type}
- Amount: ${semanticAnalysis.total_amount} ${semanticAnalysis.currency}
- Has Inventory Items: ${semanticAnalysis.has_inventory_items}
- Is Fixed Asset: ${semanticAnalysis.is_fixed_asset}

FEASIBILITY CHECKS:
1. Inventory actions require has_inventory=true
2. Fixed asset actions require amount >= fixed_asset_threshold
3. Multi-currency actions require has_foreign_operations=true
4. Sales tax collection requires collects_sales_tax=true

RESPOND WITH JSON:
{
  "feasible": boolean,
  "reason": "explanation if not feasible",
  "checks_performed": [
    {
      "check_name": "inventory_capability|fixed_asset_threshold|foreign_currency_capability|sales_tax_capability",
      "passed": boolean,
      "reason": "explanation"
    }
  ],
  "alternative_actions": ["action names if not feasible"],
  "confidence": 0-100
}`;
}

private parseFeasibilityCheckResponse(response: any): FeasibilityResult {
  try {
    const output = typeof response.output === 'string' 
      ? JSON.parse(response.output) 
      : response.output;
    
    return {
      feasible: output.feasible,
      reason: output.reason || '',
      checks_performed: output.checks_performed || [],
      alternative_actions: output.alternative_actions || [],
      confidence: output.confidence || 0
    };
  } catch (error) {
    console.error('[Feasibility Check] Failed to parse GPU response:', error);
    throw new Error('Failed to parse feasibility check response');
  }
}
```

#### 3. Update Method Calls in `classifyDocument()`

**Line 360** - Make async:
```typescript
const mathValidation = await this.validateDocumentMath(
  input.extractedData,
  input.documentId
);
```

**Line 510** - Pass additional parameters:
```typescript
let feasibilityResult = await this.validateActionFeasibility(
  primaryAction,
  input.businessProfile,
  stage1Result.semantic_analysis,
  input.documentId
);
```

**Line 564** - Same for retry:
```typescript
feasibilityResult = await this.validateActionFeasibility(
  newPrimaryAction,
  input.businessProfile,
  stage1Result.semantic_analysis,
  input.documentId
);
```

---

## Summary of Changes

### Backend Changes (3 methods to replace)
1. ✅ `validateDocumentMath()` - Replace with GPU call + prompt builder + parser
2. ✅ `validateActionFeasibility()` - Replace with GPU call + prompt builder + parser  
3. ✅ Update 3 call sites to use new async signatures

**Lines to Remove**: ~273 lines of TypeScript logic  
**Lines to Add**: ~150 lines (prompts + parsers)  
**Net Change**: -123 lines, better LLM-powered intelligence

### GPU Changes (3 new handlers + routing)
1. ✅ Add `classify_stage0_5_math()` function (~150 lines)
2. ✅ Add `classify_stage1_5_feasibility()` function (~120 lines)
3. ✅ Add `classify_stage2_schema()` function (~150 lines)
4. ✅ Update routing in `main.py` (+15 lines)

**Total GPU Addition**: ~435 lines

---

## Migration Priority

### Priority 1: CRITICAL (Breaks Design Intent)
1. ✅ Replace Math Validation with GPU (Stage 0.5)
2. ✅ Replace Feasibility Check with GPU (Stage 1.5)

### Priority 2: HIGH (Missing Handler)
3. ✅ Add Action Schema Analysis handler (Stage 2)

### Priority 3: LOW (Works as-is)
4. ⏹️ Schema Validation (Stage 5) - Keep as TypeScript

---

## Estimated Effort

- Backend refactoring: **2-3 hours**
- GPU implementation: **3-4 hours**
- Testing: **2-3 hours**
- **Total: 7-10 hours**

---

## Next Steps

1. Update TODO list with new priorities
2. Start with GPU implementation (can test independently)
3. Then refactor backend to call GPU
4. Test each stage independently
5. Test full flow end-to-end
