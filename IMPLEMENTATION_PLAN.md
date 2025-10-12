# GPU Classification Implementation Plan

## 🎯 Goal
Update ZopilotGPU to generate document classification responses (Stage 1 & Stage 2) that match backend expectations.

---

## 📊 Current State vs Target State

### ❌ Current (Journal Entry Generation)
```python
# llama_utils.py generates:
{
  "date": "2024-10-12",
  "description": "...",
  "account_debits": [...],
  "account_credits": [...],
  "total_debit": 0.00,
  "total_credit": 0.00
}
```

### ✅ Target (Document Classification)
```json
{
  "semantic_analysis": {...},
  "suggested_actions": [...],
  "overall_confidence": 90
}
```

---

## 🏗️ Implementation Strategy

### Phase 1: Create Classification Module ✅
**File**: `app/classification.py`

**Functions to implement:**
1. `classify_stage1(prompt: str, context: dict) -> dict`
   - Parse backend prompt to extract business context and extracted data
   - Generate semantic analysis
   - Generate suggested actions (prerequisites + primary + follow-ups)
   - Return Stage 1 response

2. `classify_stage2(prompt: str, context: dict) -> dict`
   - Parse field mapping prompt
   - Extract action specification
   - Generate field mappings
   - Generate lookups_required array
   - Return Stage 2 response with validation

### Phase 2: Update Handler Routing ✅
**File**: `handler.py`

**Changes needed:**
```python
def handler(job):
    input_data = job['input']
    context = input_data.get('context', {})
    stage = context.get('stage', 'action_selection')  # Default to Stage 1
    
    if stage == 'action_selection':
        # Stage 1: Semantic analysis + action selection
        result = classify_stage1(input_data['prompt'], context)
    elif stage == 'field_mapping':
        # Stage 2: Field mapping
        result = classify_stage2(input_data['prompt'], context)
    else:
        # Legacy journal entry generation (keep for backward compatibility)
        result = generate_journal_entry(input_data['prompt'], context)
    
    return {
        "metadata": {...},
        "output": result,
        "success": True
    }
```

### Phase 3: Keep Journal Entry Logic ✅
**File**: `app/llama_utils.py` (Keep existing)

**Reason**: May still be useful for future journal entry features. Just add classification alongside it.

---

## 📝 Detailed Implementation

### 1. Create `app/classification.py`

```python
"""
Document Classification Module
Handles Stage 1 (Action Selection) and Stage 2 (Field Mapping)
"""

import json
import re
import torch
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.llama_utils import get_llama_processor

# Import logging
import logging
logger = logging.getLogger(__name__)


def classify_stage1(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 1: Semantic Analysis + Action Selection
    
    Input:
        prompt: Full backend prompt with business context, extracted data, action registry
        context: {"stage": "action_selection", "business": "...", "software": "..."}
    
    Output:
        {
            "semantic_analysis": {...},
            "suggested_actions": [...],
            "overall_confidence": 90,
            "missing_data": [],
            "assumptions": []
        }
    """
    logger.info("🎯 [Stage 1] Starting semantic analysis and action selection...")
    
    try:
        # Get model processor
        processor = get_llama_processor()
        
        # Build Mixtral-compatible prompt
        formatted_prompt = f"<s>[INST] {prompt}\n\nRespond with ONLY valid JSON. No markdown, no explanations. [/INST]"
        
        # Tokenize
        inputs = processor.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(processor.model.device) for k, v in inputs.items()}
        
        # Generate
        logger.info(f"🚀 [Stage 1] Generating response (max 2500 tokens)...")
        gen_start = __import__('time').time()
        
        with torch.no_grad():
            outputs = processor.model.generate(
                **inputs,
                max_new_tokens=2500,  # Backend uses 2500 for Stage 1
                temperature=0.1,      # Backend uses 0.1 for consistent analysis
                do_sample=True,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.1,
                pad_token_id=processor.tokenizer.eos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id
            )
        
        gen_time = __import__('time').time() - gen_start
        output_tokens = len(outputs[0]) - len(inputs["input_ids"][0])
        logger.info(f"✅ [Stage 1] Generated {output_tokens} tokens in {gen_time:.1f}s")
        
        # Decode
        response_text = processor.tokenizer.decode(
            outputs[0][len(inputs["input_ids"][0]):], 
            skip_special_tokens=True
        )
        
        # Clear KV cache
        if hasattr(processor.model, 'past_key_values'):
            processor.model.past_key_values = None
        torch.cuda.empty_cache()
        
        # Parse JSON
        result = _parse_classification_response(response_text, stage=1)
        
        # Validate Stage 1 structure
        _validate_stage1_response(result)
        
        logger.info(f"🎉 [Stage 1] Classification complete - {len(result.get('suggested_actions', []))} actions suggested")
        return result
        
    except Exception as e:
        logger.error(f"❌ [Stage 1] Classification failed: {str(e)}")
        raise RuntimeError(f"Stage 1 classification failed: {str(e)}") from e


def classify_stage2(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage 2: Field Mapping
    
    Input:
        prompt: Field mapping prompt with action spec, semantic analysis, extracted data, COA
        context: {"stage": "field_mapping", "action": "createInvoice", "entity": "Invoice"}
    
    Output:
        {
            "field_mappings": {...},
            "lookups_required": [...],
            "validation": {...}
        }
    """
    logger.info(f"🎯 [Stage 2] Starting field mapping for {context.get('action', 'unknown')}...")
    
    try:
        # Get model processor
        processor = get_llama_processor()
        
        # Build Mixtral-compatible prompt
        formatted_prompt = f"<s>[INST] {prompt}\n\nRespond with ONLY valid JSON. No markdown, no explanations. [/INST]"
        
        # Tokenize
        inputs = processor.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(processor.model.device) for k, v in inputs.items()}
        
        # Generate
        logger.info(f"🚀 [Stage 2] Generating field mappings (max 2000 tokens)...")
        gen_start = __import__('time').time()
        
        with torch.no_grad():
            outputs = processor.model.generate(
                **inputs,
                max_new_tokens=2000,  # Backend uses 2000 for Stage 2
                temperature=0.1,
                do_sample=True,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.1,
                pad_token_id=processor.tokenizer.eos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id
            )
        
        gen_time = __import__('time').time() - gen_start
        output_tokens = len(outputs[0]) - len(inputs["input_ids"][0])
        logger.info(f"✅ [Stage 2] Generated {output_tokens} tokens in {gen_time:.1f}s")
        
        # Decode
        response_text = processor.tokenizer.decode(
            outputs[0][len(inputs["input_ids"][0]):], 
            skip_special_tokens=True
        )
        
        # Clear KV cache
        if hasattr(processor.model, 'past_key_values'):
            processor.model.past_key_values = None
        torch.cuda.empty_cache()
        
        # Parse JSON
        result = _parse_classification_response(response_text, stage=2)
        
        # Validate Stage 2 structure
        _validate_stage2_response(result)
        
        logger.info(f"🎉 [Stage 2] Field mapping complete")
        return result
        
    except Exception as e:
        logger.error(f"❌ [Stage 2] Field mapping failed: {str(e)}")
        raise RuntimeError(f"Stage 2 field mapping failed: {str(e)}") from e


def _parse_classification_response(response: str, stage: int) -> Dict[str, Any]:
    """Parse JSON from model response, handling markdown code blocks."""
    try:
        # Remove markdown code blocks
        json_str = response.replace('```json\n', '').replace('```\n', '').replace('```', '').strip()
        
        # Find JSON boundaries
        start = json_str.find('{')
        end = json_str.rfind('}') + 1
        
        if start == -1 or end == 0:
            raise ValueError(f"No JSON found in Stage {stage} response")
        
        json_str = json_str[start:end]
        parsed = json.loads(json_str)
        
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Stage {stage} JSON: {str(e)}")
        logger.error(f"   Response: {response[:500]}...")
        raise ValueError(f"Invalid JSON in Stage {stage} response: {str(e)}")


def _validate_stage1_response(response: Dict[str, Any]) -> None:
    """Validate Stage 1 response structure."""
    # Check required fields
    if 'semantic_analysis' not in response:
        raise ValueError("Stage 1 response missing 'semantic_analysis'")
    
    if 'suggested_actions' not in response:
        raise ValueError("Stage 1 response missing 'suggested_actions'")
    
    if not isinstance(response['suggested_actions'], list):
        raise ValueError("Stage 1 'suggested_actions' must be an array")
    
    # Check for PRIMARY action
    primary_actions = [a for a in response['suggested_actions'] if a.get('action_type') == 'PRIMARY']
    if len(primary_actions) == 0:
        logger.warning("[Stage 1] No PRIMARY action found - marking highest confidence as primary")
        if response['suggested_actions']:
            response['suggested_actions'][0]['action_type'] = 'PRIMARY'
            response['suggested_actions'][0]['priority'] = 1
    elif len(primary_actions) > 1:
        logger.warning(f"[Stage 1] Multiple PRIMARY actions found ({len(primary_actions)}) - keeping only first")
    
    logger.info("[Stage 1] Validation passed ✅")


def _validate_stage2_response(response: Dict[str, Any]) -> None:
    """Validate Stage 2 response structure."""
    if 'field_mappings' not in response:
        raise ValueError("Stage 2 response missing 'field_mappings'")
    
    # Optional but recommended
    if 'lookups_required' not in response:
        logger.warning("[Stage 2] No 'lookups_required' array (setting empty)")
        response['lookups_required'] = []
    
    if 'validation' not in response:
        logger.warning("[Stage 2] No 'validation' object (creating default)")
        response['validation'] = {
            "all_required_fields_present": True,
            "warnings": []
        }
    
    logger.info("[Stage 2] Validation passed ✅")
```

### 2. Update `handler.py`

```python
# Add at top
from app.classification import classify_stage1, classify_stage2

# Update handler function
def handler(job):
    """RunPod serverless handler with classification support."""
    try:
        input_data = job.get('input', {})
        
        # Get context to determine stage
        context = input_data.get('context', {})
        stage = context.get('stage', 'action_selection')
        
        logger.info(f"📥 Received job: stage={stage}")
        
        # Route based on stage
        if stage == 'action_selection':
            # Stage 1: Semantic analysis + action selection
            logger.info("[Handler] Routing to Stage 1: Action Selection")
            result = classify_stage1(input_data.get('prompt', ''), context)
            
        elif stage == 'field_mapping':
            # Stage 2: Field mapping
            logger.info("[Handler] Routing to Stage 2: Field Mapping")
            result = classify_stage2(input_data.get('prompt', ''), context)
            
        else:
            # Legacy: Journal entry generation (backward compatibility)
            logger.info("[Handler] Routing to legacy: Journal Entry Generation")
            from app.llama_utils import generate_with_llama
            result = generate_with_llama(input_data.get('prompt', ''), context)
        
        # Wrap response
        return {
            "metadata": {
                "stage": stage,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "model": "Mixtral-8x7B-Instruct-v0.1",
                "gpu": "RTX 5090"
            },
            "output": result,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"❌ Handler failed: {str(e)}")
        return {
            "error": str(e),
            "success": False
        }
```

---

## ✅ Testing Plan

### 1. Unit Test Stage 1
```python
# test_classification.py
from app.classification import classify_stage1

test_prompt = """You are an expert accounting AI...
[Full backend Stage 1 prompt]"""

result = classify_stage1(test_prompt, {"stage": "action_selection"})

assert 'semantic_analysis' in result
assert 'suggested_actions' in result
assert len([a for a in result['suggested_actions'] if a['action_type'] == 'PRIMARY']) == 1
```

### 2. Unit Test Stage 2
```python
from app.classification import classify_stage2

test_prompt = """## ACTION TO EXECUTE
Action: createInvoice
[Full backend Stage 2 prompt]"""

result = classify_stage2(test_prompt, {"stage": "field_mapping", "action": "createInvoice"})

assert 'field_mappings' in result
assert 'lookups_required' in result
```

### 3. Integration Test with Backend
```bash
# Upload test document
# Check backend logs for:
# - [Stage 1] GPU response received
# - [Stage 1] Parsing complete
# - [Stage 2] GPU response received (per action)
# - [Stage 2] Field mapping complete
```

---

## 🚀 Deployment Steps

1. **Create classification.py** ✅
2. **Update handler.py** ✅
3. **Test locally with test script** ⏳
4. **Build Docker image** ⏳
5. **Push to RunPod registry** ⏳
6. **Deploy to serverless endpoint** ⏳
7. **Test with real backend** ⏳
8. **Monitor logs and fix any issues** ⏳

---

## 📊 Expected Results

### Before (Current Error)
```
[err] [Stage 1] Failed to parse response: 
      missing semantic_analysis or suggested_actions
```

### After (Success)
```
[inf] [Stage 1] GPU response received (response_length: 2847)
[inf] [Stage 1] Parsing complete (actions_parsed: 2)
[inf] [Stage 1] Complete. Document type: invoice
[inf] [Stage 1] Selected 2 actions with confidence 92%
```

---

## 🎯 Success Criteria

- ✅ GPU generates valid Stage 1 response with semantic_analysis and suggested_actions
- ✅ Backend parser successfully parses GPU response
- ✅ Exactly 1 PRIMARY action in suggested_actions
- ✅ Prerequisites have priority < 1 and auto_execute=true
- ✅ Follow-ups have priority > 1 and optional=true
- ✅ Stage 2 field mapping generates proper lookups_required array
- ✅ End-to-end classification flow completes without errors
- ✅ Frontend displays classification results and actions

