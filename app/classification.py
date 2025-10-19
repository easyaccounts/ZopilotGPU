"""
Document Classification Module for ZopilotGPU
Handles GPU-accelerated classification stages for backend

Stage 0.5: Math Validation (LLM-Powered)
- Validates mathematical calculations in documents
- Detects discrepancies, rounding errors, tax mismatches
- Returns: {is_valid, issues[], corrected_values, confidence}

Stage 1: Semantic Analysis + Action Selection (LLM-Powered)
- Analyzes document type, parties, amounts
- Suggests prerequisites, primary action, and follow-ups
- Returns: {semantic_analysis, suggested_actions, overall_confidence}

Stage 4: Field Mapping (LLM-Powered)
- Maps extracted data directly to accounting software API request body format
- No transformations needed - output is POST-ready for Zoho/QuickBooks
- Generates entity lookups for ID resolution (Customer, Vendor, Item, Account)
- Performs tax verification and currency detection
- Returns: {api_request_body, lookups_required, validation}

REMOVED STAGES (now run in backend):
- Stage 2: Action Schema Analysis (uses ActionRegistry + APISchemaLoader, CPU-only ~5-20ms)

Pipeline Flow:
1. Stage 1: Select action → 2. [Backend] Schema analysis → 3. [Backend] Entity resolution → 4. Stage 4: Build API request → 5. Direct API POST

Removed Stages (rely on API validation instead):
- Stage 2.6: Business rule validation (doesn't scale to 145+ actions)
- Stage 2.7: Currency conversion (creates reconciliation errors - let accounting software handle)
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


def classify_stage1(prompt: str, context: Dict[str, Any], generation_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Stage 1: Semantic Analysis + Action Selection
    
    Args:
        prompt: Full backend prompt with business context, extracted data, action registry
        context: {"stage": "action_selection", "business": "...", "software": "..."}
        generation_config: Generation parameters from backend
            - max_new_tokens: Maximum output tokens (default 2500)
            - temperature: Sampling temperature (default 0.1)
            - top_p, top_k, repetition_penalty
            - max_input_length: Input truncation limit (default 29491)
    
    Returns:
        Simplified format as requested by backend prompt:
        {
            "business_relevant": bool,
            "selected_action": string|null,  // snake_case action name or null
            "confidence": number,  // 0-100
            "reasoning": string,  // 2-3 sentences explaining the decision
            "document_type": string,  // "invoice", "bill", "receipt", etc.
            "transaction_direction": "incoming"|"outgoing"|"neutral",
            "primary_party": {
                "name": string|null,
                "role": "customer"|"vendor"|"employee"|"other"|null
            },
            "extracted_summary": {
                "total_amount": number|null,
                "currency": string|null,  // "USD", "EUR", etc.
                "document_date": string|null,  // "YYYY-MM-DD"
                "document_number": string|null
            }
        }
    """
    logger.info("🎯 [Stage 1] Starting semantic analysis and action selection...")
    
    # Extract generation parameters with defaults
    if generation_config is None:
        generation_config = {}
    
    max_new_tokens = generation_config.get('max_new_tokens', 2500)
    temperature = generation_config.get('temperature', 0.1)
    top_p = generation_config.get('top_p', 0.95)
    top_k = generation_config.get('top_k', 50)
    repetition_penalty = generation_config.get('repetition_penalty', 1.1)
    max_input_length = generation_config.get('max_input_length', 29491)
    
    # Validate token limits (Mixtral max: 32768)
    if max_new_tokens > 32768:
        logger.warning(f"⚠️  max_new_tokens {max_new_tokens} exceeds 32k limit, capping to 32768")
        max_new_tokens = 32768
    if max_input_length > 32768:
        logger.warning(f"⚠️  max_input_length {max_input_length} exceeds 32k limit, capping to 32768")
        max_input_length = 32768
    
    logger.info(f"⚙️  [Stage 1] Generation config: max_new_tokens={max_new_tokens}, temp={temperature}, max_input={max_input_length}")
    
    try:
        # Get model processor
        processor = get_llama_processor()
        
        # Build Mixtral-compatible prompt with instruction tags and STRONG JSON enforcement
        formatted_prompt = f"""<s>[INST] {prompt}

🚨 CRITICAL INSTRUCTIONS 🚨
You MUST respond with PURE JSON ONLY.
1. First character MUST be: {{
2. Last character MUST be: }}
3. NO preamble text allowed (no 'Based on...', 'Here is...', etc.)
4. NO explanations before or after JSON
5. NO markdown code blocks
START IMMEDIATELY with opening brace.

[/INST]{{"""
        
        # Tokenize input with CONFIGURABLE max_input_length
        logger.info("🔢 [Stage 1] Tokenizing prompt...")
        inputs = processor.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=max_input_length)
        inputs = {k: v.to(processor.model.device) for k, v in inputs.items()}
        input_tokens = len(inputs["input_ids"][0])
        logger.info(f"   Input tokens: {input_tokens}")
        
        # Generate response with CONFIGURABLE parameters
        logger.info(f"🚀 [Stage 1] Generating classification response (max {max_new_tokens} tokens)...")
        gen_start = __import__('time').time()
        
        with torch.no_grad():
            outputs = processor.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,        # ✅ From request (backend sends 2500)
                temperature=temperature,              # ✅ From request (backend sends 0.1)
                do_sample=temperature > 0,            # Only sample if temp > 0
                top_p=top_p,                         # ✅ From request
                top_k=top_k,                         # ✅ From request
                repetition_penalty=repetition_penalty, # ✅ From request
                pad_token_id=processor.tokenizer.eos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id
            )
        
        gen_time = __import__('time').time() - gen_start
        output_tokens = len(outputs[0]) - input_tokens
        tokens_per_sec = output_tokens / gen_time if gen_time > 0 else 0
        logger.info(f"✅ [Stage 1] Generated {output_tokens} tokens in {gen_time:.1f}s ({tokens_per_sec:.1f} tok/s)")
        
        # Decode response
        logger.info("📖 [Stage 1] Decoding response...")
        # FIX: Prompt ends with [/INST]{ to force JSON start, but decoder excludes prompt tokens
        # So we need to prepend the { that we forced in the prompt
        decoded_output = processor.tokenizer.decode(
            outputs[0][input_tokens:], 
            skip_special_tokens=True
        )
        # Prepend { since prompt forced it but it's not in the decoded generated tokens
        response_text = "{" + decoded_output
        logger.info(f"   Response length: {len(response_text)} chars (prepended opening brace)")
        
        # CRITICAL: Clear KV cache to prevent memory leak
        if hasattr(processor.model, 'past_key_values'):
            processor.model.past_key_values = None
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        
        # Report memory after cleanup
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            logger.info(f"🧹 KV cache cleared: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
        
        # Parse JSON response
        logger.info("🔍 [Stage 1] Parsing JSON response...")
        result = _parse_classification_response(response_text, stage=1)
        
        # Validate Stage 1 structure (ensures proper simplified format)
        _validate_stage1_response(result)
        
        # ✅ CRITICAL: Add 'format' field for backend detection
        # Backend relies on this field to distinguish simplified vs legacy format
        result['format'] = 'simplified'
        
        # Extract values from simplified format
        business_relevant = result.get('business_relevant', False)
        selected_action = result.get('selected_action', None)
        doc_type = result.get('document_type', 'unknown')
        confidence = result.get('confidence', 0)
        
        logger.info(f"🎉 [Stage 1] Classification complete!")
        logger.info(f"   Format: simplified")
        logger.info(f"   Business relevant: {business_relevant}")
        logger.info(f"   Document type: {doc_type}")
        logger.info(f"   Selected action: {selected_action}")
        logger.info(f"   Confidence: {confidence}%")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [Stage 1] Classification failed: {str(e)}")
        
        # CRITICAL: Clean up KV cache even on error
        try:
            if hasattr(processor.model, 'past_key_values'):
                processor.model.past_key_values = None
            torch.cuda.empty_cache()
            logger.info("🧹 KV cache cleared after error")
        except:
            pass
        
        raise RuntimeError(f"Stage 1 classification failed: {str(e)}") from e


def classify_stage2_5_entity_extraction(prompt: str, context: Dict[str, Any], generation_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Stage 2.5: Entity Field Extraction (LLM-Powered)
    
    Extracts complete entity creation fields from document for each required entity type.
    Uses semantic analysis context to correctly identify party roles, account types, and item classifications.
    
    Args:
        prompt: Entity extraction prompt with:
            - semantic_analysis (document context, party roles, transaction nature)
            - entities_required (entity types to extract)
            - extracted_data (raw OCR data)
            - entity_creation_schemas (Zoho/QB API schemas)
        context: {"stage": "entity_extraction", "entity_types": [...], "accounting_software": "zohobooks"}
        generation_config: Generation parameters
            - max_new_tokens: Default 2000 (entity extraction needs detail)
            - temperature: Default 0.1 (low for accurate extraction)
            - top_p: 0.95, top_k: 50
    
    Returns:
        {
            "entities_to_resolve": [
                {
                    "entity_type": "customer",
                    "extracted_fields": {
                        "contact_name": "ABC Corp",
                        "email": "info@abccorp.com",
                        "phone": "+1-555-0123",
                        "contact_type": "customer"
                    },
                    "search_criteria": {
                        "primary": "ABC Corp",
                        "alternatives": ["ABC Corporation", "ABC Corp."]
                    },
                    "confidence": 95,
                    "extraction_reasoning": "Primary party identified as customer from incoming invoice"
                }
            ],
            "extraction_metadata": {
                "total_entities": 3,
                "entities_by_type": {"customer": 1, "item": 2},
                "average_confidence": 94
            }
        }
    """
    logger.info("🔍 [Stage 2.5] Starting LLM-powered entity field extraction...")
    
    # Extract generation parameters with defaults
    max_new_tokens = 2000
    temperature = 0.1  # Low for accurate extraction
    top_p = 0.95
    top_k = 50
    repetition_penalty = 1.1
    max_input_length = 29491
    
    if generation_config:
        max_new_tokens = generation_config.get('max_new_tokens', max_new_tokens)
        temperature = generation_config.get('temperature', temperature)
        top_p = generation_config.get('top_p', top_p)
        top_k = generation_config.get('top_k', top_k)
        repetition_penalty = generation_config.get('repetition_penalty', repetition_penalty)
        max_input_length = generation_config.get('max_input_length', max_input_length)
    
    entity_types = context.get('entity_types', []) if context else []
    logger.info(f"[Stage 2.5] Extracting fields for entity types: {entity_types}")
    logger.info(f"[Stage 2.5] Config: max_tokens={max_new_tokens}, temp={temperature}, top_p={top_p}, top_k={top_k}")
    
    try:
        # Get model and tokenizer
        model, tokenizer = get_llama_processor()
        
        # Truncate prompt if needed
        prompt_tokens = tokenizer.encode(prompt, add_special_tokens=False)
        if len(prompt_tokens) > max_input_length:
            logger.warning(f"[Stage 2.5] ⚠️  Prompt too long ({len(prompt_tokens)} tokens), truncating to {max_input_length}")
            prompt_tokens = prompt_tokens[:max_input_length]
            prompt = tokenizer.decode(prompt_tokens, skip_special_tokens=True)
        else:
            logger.info(f"[Stage 2.5] Prompt length: {len(prompt_tokens)} tokens (within limit)")
        
        # Tokenize with chat template
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True
        )
        
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        logger.info(f"[Stage 2.5] Generating with {inputs['input_ids'].shape[1]} input tokens...")
        
        # Generate response
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                do_sample=True if temperature > 0 else False,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode response
        full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract only the assistant's response
        if "[/INST]" in full_output:
            response_text = full_output.split("[/INST]")[-1].strip()
        else:
            response_text = full_output
        
        logger.info(f"[Stage 2.5] Generated {len(response_text)} characters")
        logger.debug(f"[Stage 2.5] Raw response: {response_text[:500]}...")
        
        # Parse JSON response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            logger.error("❌ Stage 2.5: No JSON found in response")
            raise ValueError("Stage 2.5 response did not contain valid JSON")
        
        response = json.loads(json_match.group(0))
        logger.info("[Stage 2.5] ✅ JSON parsed successfully")
        
        # Validate response structure
        if 'entities_to_resolve' not in response:
            logger.error("❌ Stage 2.5 response missing 'entities_to_resolve' field")
            raise ValueError("Stage 2.5 response missing 'entities_to_resolve' field")
        
        if not isinstance(response['entities_to_resolve'], list):
            logger.error("❌ Stage 2.5 'entities_to_resolve' must be array")
            raise ValueError("Stage 2.5 'entities_to_resolve' must be array")
        
        # Validate each entity
        for i, entity in enumerate(response['entities_to_resolve']):
            if 'entity_type' not in entity:
                logger.error(f"❌ Entity {i} missing 'entity_type'")
                raise ValueError(f"Entity {i} missing 'entity_type'")
            if 'extracted_fields' not in entity:
                logger.error(f"❌ Entity {i} missing 'extracted_fields'")
                raise ValueError(f"Entity {i} missing 'extracted_fields'")
            if 'search_criteria' not in entity:
                logger.warning(f"⚠️  Entity {i} missing 'search_criteria', adding default")
                entity['search_criteria'] = {
                    "primary": entity['extracted_fields'].get('contact_name') or entity['extracted_fields'].get('name') or 'Unknown',
                    "alternatives": []
                }
            if 'confidence' not in entity:
                logger.warning(f"⚠️  Entity {i} missing 'confidence', setting to 80")
                entity['confidence'] = 80
        
        # Add metadata if missing
        if 'extraction_metadata' not in response:
            total_entities = len(response['entities_to_resolve'])
            entities_by_type = {}
            total_confidence = 0
            
            for entity in response['entities_to_resolve']:
                entity_type = entity['entity_type']
                entities_by_type[entity_type] = entities_by_type.get(entity_type, 0) + 1
                total_confidence += entity.get('confidence', 80)
            
            response['extraction_metadata'] = {
                "total_entities": total_entities,
                "entities_by_type": entities_by_type,
                "average_confidence": round(total_confidence / total_entities, 1) if total_entities > 0 else 0
            }
        
        logger.info(f"[Stage 2.5] ✅ Entity extraction complete: {response['extraction_metadata']['total_entities']} entities extracted")
        logger.info(f"[Stage 2.5] Entities by type: {response['extraction_metadata']['entities_by_type']}")
        logger.info(f"[Stage 2.5] Average confidence: {response['extraction_metadata']['average_confidence']}%")
        
        return response
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Stage 2.5: JSON parsing failed: {str(e)}")
        logger.error(f"Response text: {response_text[:1000]}")
        raise ValueError(f"Stage 2.5 returned invalid JSON: {str(e)}") from e
    
    except Exception as e:
        logger.error(f"❌ Stage 2.5 failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Clean up GPU memory on error
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        raise RuntimeError(f"Stage 2.5 entity extraction failed: {str(e)}") from e


def classify_stage2(prompt: str, context: Dict[str, Any], generation_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Stage 4: Field Mapping (Single Action or Batch)
    
    NOTE: Function name 'classify_stage2' is legacy naming - this is actually STAGE 4 in the pipeline.
    Stage 2 (Action Schema Analysis) now runs in backend using ActionRegistry.
    
    Args:
        prompt: Field mapping prompt with action spec, semantic analysis, extracted data, COA
        context: 
            Single: {"stage": "field_mapping", "action": "createInvoice", "entity": "Invoice"}
            Batch:  {"stage": "field_mapping_batch", "action_count": 2, "actions": ["createContact", "createBill"]}
        generation_config: Generation parameters from backend
            - max_new_tokens: Maximum output tokens (default 4000 for batch, 3000 for single)
            - temperature: Sampling temperature (default 0.05, backend sends 0.05)
            - top_p, top_k, repetition_penalty
            - max_input_length: Input truncation limit (default 29491)
    
    Returns (Single Action):
        {
            "api_request_body": {
                "customer_id": "{{lookup:Customer:ABC Corp}}",
                "invoice_number": "INV-12345",
                "date": "2024-10-12",
                "line_items": [...]
            },
            "lookups_required": [
                {
                    "entity": "Customer",
                    "field": "customer_id",
                    "lookup_value": "ABC Corp",
                    "create_if_missing": false
                }
            ],
            "validation": {
                "warnings": [],
                "missing_fields": []
            }
        }
    
    Returns (Batch Actions - NEW):
        {
            "actions": [
                {
                    "action_index": 0,
                    "action_name": "create_contact",
                    "api_request_body": {...},
                    "lookups_required": [...],
                    "validation": {...}
                },
                {
                    "action_index": 1,
                    "action_name": "create_bill",
                    "api_request_body": {...},
                    "lookups_required": [...],
                    "validation": {...}
                }
            ]
        }
        
    Note: 
    - GPU code is agnostic to single vs batch - both use same generation logic
    - Backend prompt structure determines output format (single or batch)
    - Batch processing allows consistent mapping across multiple actions from same document
    - Backend removed stages: Business rule validation (2.6) and currency conversion (2.7)
    """
    action_name = context.get('action', context.get('actions', ['unknown'])[0] if context.get('actions') else 'unknown')
    action_count = context.get('action_count', 1)
    
    if action_count > 1:
        logger.info(f"🎯 [Stage 4] Starting BATCH field mapping for {action_count} actions")
    else:
        logger.info(f"🎯 [Stage 4] Starting field mapping for action: {action_name}")
    
    # Extract generation parameters with defaults (FIX: Increase temp from 0.05 to 0.1 for better JSON adherence)
    if generation_config is None:
        generation_config = {}
    
    max_new_tokens = generation_config.get('max_new_tokens', 3000)  # Backend sends 3000
    temperature = generation_config.get('temperature', 0.1)         # FIX: Default 0.1 instead of 0.05 (less deterministic)
    top_p = generation_config.get('top_p', 0.95)
    top_k = generation_config.get('top_k', 50)
    repetition_penalty = generation_config.get('repetition_penalty', 1.15)  # FIX: Increased from 1.1 to prevent repetition
    max_input_length = generation_config.get('max_input_length', 29491)
    
    # Validate token limits
    if max_new_tokens > 32768:
        logger.warning(f"⚠️  max_new_tokens {max_new_tokens} exceeds 32k limit, capping to 32768")
        max_new_tokens = 32768
    if max_input_length > 32768:
        logger.warning(f"⚠️  max_input_length {max_input_length} exceeds 32k limit, capping to 32768")
        max_input_length = 32768
    
    logger.info(f"⚙️  [Stage 4] Generation config: max_new_tokens={max_new_tokens}, temp={temperature}, max_input={max_input_length}")
    
    try:
        # Get model processor
        processor = get_llama_processor()
        
        # Build Mixtral-compatible prompt with JSON prefix forcing
        formatted_prompt = f"""<s>[INST] {prompt}

🚨 CRITICAL INSTRUCTIONS 🚨
You MUST respond with PURE JSON ONLY.
1. First character MUST be: {{
2. Last character MUST be: }}
3. NO preamble text allowed (no 'Based on...', 'Here is...', etc.)
4. NO explanations before or after JSON
5. NO markdown code blocks
START IMMEDIATELY with opening brace.

[/INST]{{"""
        
        # Tokenize with CONFIGURABLE max_input_length
        logger.info("🔢 [Stage 4] Tokenizing prompt...")
        inputs = processor.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=max_input_length)
        inputs = {k: v.to(processor.model.device) for k, v in inputs.items()}
        input_tokens = len(inputs["input_ids"][0])
        logger.info(f"   Input tokens: {input_tokens}")
        
        # Generate with CONFIGURABLE parameters
        logger.info(f"🚀 [Stage 4] Generating field mappings (max {max_new_tokens} tokens)...")
        gen_start = __import__('time').time()
        
        with torch.no_grad():
            outputs = processor.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,        # ✅ From request (backend sends 3000)
                temperature=temperature,              # ✅ From request (backend sends 0.05)
                do_sample=temperature > 0,            # Only sample if temp > 0
                top_p=top_p,                         # ✅ From request
                top_k=top_k,                         # ✅ From request
                repetition_penalty=repetition_penalty, # ✅ From request
                pad_token_id=processor.tokenizer.eos_token_id,
                eos_token_id=processor.tokenizer.eos_token_id
            )
        
        gen_time = __import__('time').time() - gen_start
        output_tokens = len(outputs[0]) - input_tokens
        tokens_per_sec = output_tokens / gen_time if gen_time > 0 else 0
        logger.info(f"✅ [Stage 4] Generated {output_tokens} tokens in {gen_time:.1f}s ({tokens_per_sec:.1f} tok/s)")
        
        # FIX: Detect suspiciously low token count (hallucination indicator)
        if output_tokens < 100:
            logger.warning(f"⚠️  [Stage 4] Suspiciously low token count ({output_tokens} tokens) - possible hallucination or early stopping")
        
        # Decode
        logger.info("📖 [Stage 4] Decoding response...")
        # FIX: Prompt ends with [/INST]{ to force JSON start, but decoder excludes prompt tokens
        # So we need to prepend the { that we forced in the prompt
        decoded_output = processor.tokenizer.decode(
            outputs[0][input_tokens:], 
            skip_special_tokens=True
        )
        # Prepend { since prompt forced it but it's not in the decoded generated tokens
        response_text = "{" + decoded_output
        logger.info(f"   Response length: {len(response_text)} chars (prepended opening brace)")
        logger.info(f"   Raw decoded response: {response_text[:200]}...")
        
        # CRITICAL: Clear KV cache
        if hasattr(processor.model, 'past_key_values'):
            processor.model.past_key_values = None
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        
        # Report memory
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            logger.info(f"🧹 KV cache cleared: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
        
        # Parse JSON
        logger.info("🔍 [Stage 4] Parsing JSON response...")
        try:
            result = _parse_classification_response(response_text, stage=2)
        except ValueError as parse_error:
            # FIX: If JSON parsing fails due to preamble/hallucination, retry once with stronger prompt
            if output_tokens < 100 or "No JSON object found" in str(parse_error):
                logger.warning(f"⚠️  [Stage 4] First attempt failed (low tokens or no JSON), retrying with stronger enforcement...")
                
                # Clear cache before retry
                if hasattr(processor.model, 'past_key_values'):
                    processor.model.past_key_values = None
                torch.cuda.empty_cache()
                
                # Retry with even stronger JSON enforcement and zero temperature
                retry_prompt = f"""<s>[INST] {prompt}

🚨🚨🚨 ABSOLUTE REQUIREMENT 🚨🚨🚨
You MUST respond with PURE JSON ONLY.
FORBIDDEN:
- Any text before opening {{ brace
- Any text after closing }} brace
- Phrases like 'Based on', 'Here is', 'Sure', etc.
- Markdown formatting or code blocks
- Any explanations
REQUIRED:
- Start with {{ character
- End with }} character
- Valid JSON syntax only
Generate JSON immediately:

[/INST]{{"""
                
                retry_inputs = processor.tokenizer(retry_prompt, return_tensors="pt", truncation=True, max_length=max_input_length)
                retry_inputs = {k: v.to(processor.model.device) for k, v in retry_inputs.items()}
                
                logger.info("🔄 [Stage 4] Retry generation with stronger JSON enforcement...")
                with torch.no_grad():
                    retry_outputs = processor.model.generate(
                        **retry_inputs,
                        max_new_tokens=max_new_tokens,
                        temperature=0.0,  # Zero temperature for maximum determinism - no sampling
                        do_sample=False,  # Greedy decoding only
                        top_p=0.9,
                        top_k=40,
                        repetition_penalty=1.2,
                        pad_token_id=processor.tokenizer.eos_token_id,
                        eos_token_id=processor.tokenizer.eos_token_id
                    )
                
                retry_decoded = processor.tokenizer.decode(
                    retry_outputs[0][len(retry_inputs["input_ids"][0]):], 
                    skip_special_tokens=True
                )
                # FIX: Prepend { since retry prompt also ends with [/INST]{
                retry_response = "{" + retry_decoded
                logger.info(f"   Retry response length: {len(retry_response)} chars (prepended opening brace)")
                logger.info(f"   Retry raw decoded response: {retry_response[:200]}...")
                
                logger.info(f"🔄 [Stage 4] Retry generated {len(retry_outputs[0]) - len(retry_inputs['input_ids'][0])} tokens")
                result = _parse_classification_response(retry_response, stage=2)
                logger.info("✅ [Stage 4] Retry successful!")
            else:
                raise  # Re-raise if not a recoverable error
        
        # Validate Stage 2 structure
        _validate_stage2_response(result)
        
        lookups_count = len(result.get('lookups_required', []))
        fields_count = len(result.get('api_request_body', {}))
        
        logger.info(f"🎉 [Stage 4] Field mapping complete for {action_name}!")
        logger.info(f"   API fields mapped: {fields_count}")
        logger.info(f"   Lookups required: {lookups_count}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [Stage 4] Field mapping failed for {action_name}: {str(e)}")
        
        # CRITICAL: Clean up KV cache even on error
        try:
            processor = get_llama_processor()
            if hasattr(processor.model, 'past_key_values'):
                processor.model.past_key_values = None
            torch.cuda.empty_cache()
            logger.info("🧹 KV cache cleared after error")
        except:
            pass
        
        raise RuntimeError(f"Stage 2 field mapping failed: {str(e)}") from e


# ============================================================================
# Helper Functions
# ============================================================================

# ============================================================================
# JSON Parsing & Validation
# ============================================================================

def _repair_malformed_json(json_str: str, stage: int) -> str:
    """
    Repair common JSON malformations from LLM output.
    
    CRITICAL FIX: Models often generate multiple JSON objects separated by commas
    instead of one properly nested object. This function fixes that.
    
    Common issues fixed:
    1. Multiple JSON objects: {"obj1": {...}}, {"obj2": {...}} → {"obj1": {...}, "obj2": {...}}
    2. Missing root braces: "field": value, ... → {"field": value, ...}
    3. Trailing commas: {..., } → {...}
    4. Extra closing braces: {...}}, → {...}
    5. Missing commas between fields
    
    Args:
        json_str: Raw JSON string from model
        stage: Classification stage (1 or 2) for logging
    
    Returns:
        Repaired JSON string
    """
    import re
    
    original_len = len(json_str)
    original_str = json_str  # Keep original for debugging
    logger.info(f"🔧 [JSON Repair] Attempting to repair Stage {stage} JSON ({original_len} chars)...")
    
    # Strip leading/trailing whitespace first
    json_str = json_str.strip()
    
    # Issue #1: DISABLED - This was incorrectly removing valid nested object closing braces
    # The pattern "},\n  "field" appears in VALID nested JSON like:
    # { "obj1": { "inner": "value" }, "obj2": { ... } }
    #                              ^^^ This is VALID, not a bug!
    # 
    # Original intent was to fix model outputting multiple separate root objects:
    # { "obj1": "val" }
    # { "obj2": "val" }
    # 
    # But this case is extremely rare with Mixtral when prompt forces JSON format.
    # The decoder fix (prepending {) already handles the root issue.
    # Leaving this aggressive repair causes MORE problems than it solves.
    #
    # if '},\n' in json_str or '},\r\n' in json_str or '},  "' in json_str:
    #     logger.warning(f"   🔧 Detected multiple JSON objects separated by closing braces")
    #     ... DISABLED ...
    
    # Issue #2: Missing opening brace at start
    needs_outer_wrapper = not json_str.startswith('{')
    if needs_outer_wrapper:
        logger.warning(f"   🔧 JSON doesn't start with opening brace, adding...")
        json_str = '{\n' + json_str
    
    # Issue #3: Missing closing brace at end
    if not json_str.endswith('}'):
        logger.warning(f"   🔧 JSON doesn't end with closing brace, adding...")
        json_str = json_str + '\n}'
    
    # Issue #4: Trailing commas before closing braces
    # {..."field": value,} → {..."field": value}
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Issue #5: Multiple consecutive commas
    json_str = re.sub(r',\s*,', ',', json_str)
    
    # Count braces for balance check
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    
    # Issue #6: Extra closing braces at end
    if close_braces > open_braces:
        logger.warning(f"   🔧 Found {close_braces} closing braces but only {open_braces} opening braces")
        while json_str.count('}') > json_str.count('{'):
            last_brace = json_str.rfind('}')
            if last_brace > 0:
                json_str = json_str[:last_brace] + json_str[last_brace+1:]
                logger.warning(f"   🔧 Removed extra closing brace at position {last_brace}")
    
    # Issue #7: Extra opening braces at start
    # IMPORTANT: Only remove if we DIDN'T add a wrapper in Issue #2
    # This prevents the bug where we add { then immediately remove it
    if not needs_outer_wrapper and json_str.count('{') > json_str.count('}'):
        logger.warning(f"   🔧 Found {json_str.count('{')} opening braces but only {json_str.count('}')} closing braces")
        # Only remove if there's actually a duplicate at the start
        if json_str.startswith('{{'):
            json_str = json_str[1:]
            logger.warning(f"   🔧 Removed duplicate opening brace at start")
    
    repaired_len = len(json_str)
    if repaired_len != original_len:
        logger.info(f"   ✅ Repaired JSON ({original_len} → {repaired_len} chars)")
    else:
        logger.info(f"   ℹ️  No repairs needed")
    
    return json_str


def _parse_classification_response(response: str, stage: int) -> Dict[str, Any]:
    """
    Parse JSON from model response, handling markdown code blocks and preamble text.
    
    Args:
        response: Raw model output text
        stage: 1 or 2 (for error messages)
    
    Returns:
        Parsed JSON dictionary
    
    Raises:
        ValueError: If JSON cannot be parsed
    """
    try:
        # Remove markdown code blocks (```json ... ```)
        json_str = response.replace('```json\n', '').replace('```json', '')
        json_str = json_str.replace('```\n', '').replace('```', '').strip()
        
        # FIX: Detect and remove preamble text (e.g., "Based on the provided document...")
        # Look for common preamble patterns that appear before JSON
        # CRITICAL: Check ANYWHERE in first 200 chars, not just at start (preamble might come after forced {)
        preamble_patterns = [
            "Based on the provided",
            "Based on the document",
            "Based on this",
            "Here's the",
            "Here is the",
            "The following is",
            "Below is the",
            "I'll provide",
            "Let me provide",
            "Sure, here",
            "Certainly",
            "Looking at the document",
            "From the document"
        ]
        
        # Check if any preamble pattern exists in the first 200 characters
        preamble_found = False
        for pattern in preamble_patterns:
            if pattern.lower() in json_str[:200].lower():
                logger.warning(f"⚠️  Stage {stage} response has preamble text, removing...")
                logger.warning(f"   Preamble pattern detected: '{pattern}'")
                logger.warning(f"   First 200 chars: {json_str[:200]}...")
                # Find where JSON actually starts (first '{' in the string)
                json_start = json_str.find('{')
                if json_start > 0:
                    json_str = json_str[json_start:]
                    logger.info(f"   ✅ Extracted JSON starting at position {json_start}")
                preamble_found = True
                break
        
        # Find JSON boundaries (first { to last })
        start = json_str.find('{')
        end = json_str.rfind('}') + 1
        
        if start == -1 or end == 0:
            logger.error(f"❌ No JSON found in Stage {stage} response")
            logger.error(f"   Response preview: {response[:200]}...")
            raise ValueError(f"No JSON object found in Stage {stage} response")
        
        json_str = json_str[start:end]
        
        # FIX: Validate JSON is not suspiciously short
        if len(json_str) < 50 and stage == 2:
            logger.error(f"❌ Stage 2 JSON too short ({len(json_str)} chars) - likely incomplete response")
            logger.error(f"   JSON: {json_str}")
            raise ValueError(f"Stage 2 JSON response too short ({len(json_str)} chars) - incomplete generation")
        
        # CRITICAL: Attempt JSON repair BEFORE parsing
        json_str = _repair_malformed_json(json_str, stage)
        
        # Try to parse the repaired JSON
        parsed = json.loads(json_str)
        
        logger.info(f"✅ Successfully parsed Stage {stage} JSON ({len(json_str)} chars)")
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Stage {stage} JSON even after repair: {str(e)}")
        logger.error(f"   JSON string: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
        logger.error(f"   Raw response: {response[:500]}...")
        
        # Last resort: Try to extract valid JSON using regex
        try:
            logger.warning(f"🔧 Attempting last-resort JSON extraction...")
            import re
            # Try to find the largest valid JSON object
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_matches:
                largest_json = max(json_matches, key=len)
                logger.warning(f"   Found potential JSON ({len(largest_json)} chars)")
                # Try to repair and parse the extracted JSON
                largest_json = _repair_malformed_json(largest_json, stage)
                parsed = json.loads(largest_json)
                logger.info(f"✅ Successfully extracted JSON using regex fallback")
                return parsed
        except Exception as fallback_error:
            logger.error(f"   ❌ Regex fallback also failed: {str(fallback_error)}")
        
        raise ValueError(f"Invalid JSON in Stage {stage} response: {str(e)}")


def _validate_stage1_response(response: Dict[str, Any]) -> None:
    """
    Validate Stage 1 response has required SIMPLIFIED format structure.
    Expected format from backend prompt:
    {
        "business_relevant": boolean,
        "selected_action": string|null,
        "confidence": number,
        "reasoning": string,
        "document_type": string,
        "transaction_direction": "incoming"|"outgoing"|"neutral",
        "primary_party": {...},
        "extracted_summary": {...}
    }
    
    Args:
        response: Parsed Stage 1 response dictionary
    
    Raises:
        ValueError: If validation fails
    """
    # Check required top-level fields for simplified format
    if 'business_relevant' not in response:
        logger.error("❌ Stage 1 response missing 'business_relevant' field")
        raise ValueError("Stage 1 response missing 'business_relevant' field")
    
    if not isinstance(response['business_relevant'], bool):
        logger.error("❌ Stage 1 'business_relevant' must be a boolean")
        raise ValueError("Stage 1 'business_relevant' must be a boolean")
    
    if 'selected_action' not in response:
        logger.error("❌ Stage 1 response missing 'selected_action' field")
        raise ValueError("Stage 1 response missing 'selected_action' field")
    
    if 'confidence' not in response:
        logger.error("❌ Stage 1 response missing 'confidence' field")
        raise ValueError("Stage 1 response missing 'confidence' field")
    
    if 'reasoning' not in response:
        logger.error("❌ Stage 1 response missing 'reasoning' field")
        raise ValueError("Stage 1 response missing 'reasoning' field")
    
    if 'document_type' not in response:
        logger.warning("[Stage 1] ⚠️  Missing 'document_type' - setting to 'unknown'")
        response['document_type'] = 'unknown'
    
    if 'transaction_direction' not in response:
        logger.warning("[Stage 1] ⚠️  Missing 'transaction_direction' - setting to 'neutral'")
        response['transaction_direction'] = 'neutral'
    
    # Validate business_relevant logic
    business_relevant = response['business_relevant']
    selected_action = response['selected_action']
    confidence = response['confidence']
    
    # If not business relevant, selected_action must be null and confidence must be 0
    if not business_relevant:
        if selected_action is not None:
            logger.warning(f"[Stage 1] ⚠️  business_relevant=false but selected_action='{selected_action}' - setting to null")
            response['selected_action'] = None
        if confidence != 0:
            logger.warning(f"[Stage 1] ⚠️  business_relevant=false but confidence={confidence} - setting to 0")
            response['confidence'] = 0
        logger.info("[Stage 1] ✅ Non-business document validation passed")
        return
    
    # If business_relevant is true, validate further
    if selected_action is not None:
        # Validate action name format (snake_case)
        if not isinstance(selected_action, str):
            logger.error(f"❌ Stage 1 'selected_action' must be string or null, got {type(selected_action)}")
            raise ValueError(f"Stage 1 'selected_action' must be string or null")
        
        # Basic format validation: snake_case with underscores
        if not re.match(r'^[a-z][a-z0-9_]*$', selected_action):
            logger.warning(f"⚠️  Action '{selected_action}' has suspicious format (expected snake_case)")
            # Don't fail here - backend will validate against actual registry
        
        # Check for common hallucination patterns
        hallucination_patterns = [
            'super_', 'advanced_', 'custom_', 'special_', 'auto_', 'smart_',
            'new_', 'enhanced_', 'improved_', 'optimized_', 'fast_'
        ]
        for pattern in hallucination_patterns:
            if selected_action.startswith(pattern):
                logger.warning(f"⚠️  Action '{selected_action}' may be hallucinated (suspicious prefix: {pattern})")
    
    # Validate confidence range
    if not isinstance(confidence, (int, float)):
        logger.error(f"❌ Stage 1 'confidence' must be a number, got {type(confidence)}")
        raise ValueError("Stage 1 'confidence' must be a number")
    
    if confidence < 0 or confidence > 100:
        logger.warning(f"[Stage 1] ⚠️  confidence {confidence} out of range [0-100] - clamping")
        response['confidence'] = max(0, min(100, confidence))
    
    # Validate transaction_direction
    valid_directions = ['incoming', 'outgoing', 'neutral']
    if response['transaction_direction'] not in valid_directions:
        logger.warning(f"[Stage 1] ⚠️  Invalid transaction_direction '{response['transaction_direction']}' - setting to 'neutral'")
        response['transaction_direction'] = 'neutral'
    
    # Ensure primary_party exists (optional but should be present)
    if 'primary_party' not in response:
        logger.warning("[Stage 1] ⚠️  Missing 'primary_party' - setting to null")
        response['primary_party'] = None
    
    # Ensure extracted_summary exists
    if 'extracted_summary' not in response:
        logger.warning("[Stage 1] ⚠️  Missing 'extracted_summary' - creating default")
        response['extracted_summary'] = {
            'total_amount': None,
            'currency': None,
            'document_date': None,
            'document_number': None
        }
    
    logger.info(f"[Stage 1] ✅ Validation passed - business_relevant={business_relevant}, action={selected_action}, confidence={confidence}%")


def _validate_stage2_response(response: Dict[str, Any]) -> None:
    """
    Validate Stage 2 response has required structure.
    Handles both single action and batch formats.
    Adds default values for optional fields.
    
    Args:
        response: Parsed Stage 2 response dictionary
            Single: {"api_request_body": {...}, "lookups_required": [...], "validation": {...}}
            Batch:  {"actions": [{"action_index": 0, "action_name": "...", "api_request_body": {...}, ...}]}
    
    Raises:
        ValueError: If validation fails
    """
    # Detect format: batch (has 'actions' array) or single (has 'api_request_body' at root)
    is_batch = 'actions' in response
    
    if is_batch:
        # Batch format validation
        if not isinstance(response['actions'], list):
            logger.error("❌ Stage 2 batch response 'actions' must be an array")
            raise ValueError("Stage 2 batch response 'actions' must be an array")
        
        if len(response['actions']) == 0:
            logger.error("❌ Stage 2 batch response 'actions' array is empty")
            raise ValueError("Stage 2 batch response 'actions' array is empty")
        
        # Validate each action in batch
        for i, action in enumerate(response['actions']):
            if not isinstance(action, dict):
                logger.error(f"❌ Stage 2 batch action[{i}] must be an object")
                raise ValueError(f"Stage 2 batch action[{i}] must be an object")
            
            # Required fields per action
            if 'api_request_body' not in action:
                logger.error(f"❌ Stage 2 batch action[{i}] missing 'api_request_body'")
                raise ValueError(f"Stage 2 batch action[{i}] missing 'api_request_body'")
            
            if not isinstance(action['api_request_body'], dict):
                logger.error(f"❌ Stage 2 batch action[{i}] 'api_request_body' must be an object")
                raise ValueError(f"Stage 2 batch action[{i}] 'api_request_body' must be an object")
            
            # Optional fields - add defaults
            if 'lookups_required' not in action:
                logger.debug(f"[Stage 4] Action[{i}] no 'lookups_required' - setting empty array")
                action['lookups_required'] = []
            
            if not isinstance(action['lookups_required'], list):
                logger.warning(f"[Stage 4] ⚠️  Action[{i}] 'lookups_required' not array - converting")
                action['lookups_required'] = []
            
            if 'validation' not in action:
                logger.debug(f"[Stage 4] Action[{i}] no 'validation' - creating default")
                action['validation'] = {
                    "all_required_fields_present": True,
                    "warnings": []
                }
            
            if not isinstance(action['validation'], dict):
                logger.warning(f"[Stage 4] ⚠️  Action[{i}] 'validation' not object - creating default")
                action['validation'] = {
                    "all_required_fields_present": True,
                    "warnings": []
                }
        
        logger.info(f"[Stage 4] ✅ Batch validation passed ({len(response['actions'])} actions)")
        
    else:
        # Single action format validation
        if 'api_request_body' not in response:
            logger.error("❌ Stage 2 response missing 'api_request_body'")
            raise ValueError("Stage 2 response missing 'api_request_body'")
        
        if not isinstance(response['api_request_body'], dict):
            logger.error("❌ Stage 2 'api_request_body' must be an object")
            raise ValueError("Stage 2 'api_request_body' must be an object")
        
        # Optional but recommended fields - add defaults if missing
        if 'lookups_required' not in response:
            logger.warning("[Stage 4] ⚠️  No 'lookups_required' array - setting empty array")
            response['lookups_required'] = []
        
        if not isinstance(response['lookups_required'], list):
            logger.warning("[Stage 4] ⚠️  'lookups_required' is not an array - converting to array")
            response['lookups_required'] = []
        
        if 'validation' not in response:
            logger.warning("[Stage 4] ⚠️  No 'validation' object - creating default")
            response['validation'] = {
                "all_required_fields_present": True,
                "warnings": []
            }
        
        if not isinstance(response['validation'], dict):
            logger.warning("[Stage 4] ⚠️  'validation' is not an object - creating default")
            response['validation'] = {
                "all_required_fields_present": True,
                "warnings": []
            }
        
        logger.info("[Stage 4] ✅ Single action validation passed")


def classify_stage0_5_math(prompt: str, context: Dict[str, Any], generation_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Stage 0.5: Math Validation (LLM-Powered)
    
    Validates mathematical consistency in financial documents using LLM reasoning.
    Replaces hardcoded TypeScript validation with intelligent analysis.
    
    Args:
        prompt: Math validation prompt with extracted financial data
        context: {"stage": "math_validation", "document_type": "invoice"}
        generation_config: Generation parameters
            - max_new_tokens: Default 1500 (math analysis needs less than field mapping)
            - temperature: Default 0.05 (very low for math accuracy)
            - top_p: 0.9, top_k: 40
    
    Returns:
        {
            "passed": bool,  # Overall validation result
            "errors": [  # Critical math errors
                {
                    "field": "total",
                    "issue": "Total calculation incorrect",
                    "expected": 1150.0,
                    "actual": 1200.0,
                    "severity": "error"
                }
            ],
            "warnings": [  # Non-critical issues
                {
                    "field": "discount",
                    "issue": "Discount percentage seems high",
                    "value": 50,
                    "severity": "warning"
                }
            ],
            "calculations": {  # LLM's calculation breakdown
                "subtotal_verified": true,
                "tax_calculation_method": "percentage",
                "total_breakdown": "1000 + 150 (tax) + 50 (shipping) - 50 (discount) = 1150"
            },
            "complexity": "simple|moderate|complex"
        }
    """
    logger.info("🧮 [Stage 0.5] Starting LLM-powered math validation...")
    
    # Extract generation parameters with defaults optimized for math
    max_new_tokens = 1500
    temperature = 0.05  # Very low for math accuracy
    top_p = 0.9
    top_k = 40
    repetition_penalty = 1.1
    max_input_length = 29491
    
    if generation_config:
        max_new_tokens = generation_config.get('max_new_tokens', max_new_tokens)
        temperature = generation_config.get('temperature', temperature)
        top_p = generation_config.get('top_p', top_p)
        top_k = generation_config.get('top_k', top_k)
        repetition_penalty = generation_config.get('repetition_penalty', repetition_penalty)
        max_input_length = generation_config.get('max_input_length', max_input_length)
    
    logger.info(f"[Stage 0.5] Config: max_tokens={max_new_tokens}, temp={temperature}, top_p={top_p}, top_k={top_k}")
    
    try:
        # Get model and tokenizer
        model, tokenizer = get_llama_processor()
        
        # Truncate prompt if needed
        prompt_tokens = tokenizer.encode(prompt, add_special_tokens=False)
        if len(prompt_tokens) > max_input_length:
            logger.warning(f"[Stage 0.5] ⚠️  Prompt too long ({len(prompt_tokens)} tokens), truncating to {max_input_length}")
            prompt_tokens = prompt_tokens[:max_input_length]
            prompt = tokenizer.decode(prompt_tokens, skip_special_tokens=True)
        else:
            logger.info(f"[Stage 0.5] Prompt length: {len(prompt_tokens)} tokens (within limit)")
        
        # Tokenize with chat template
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True
        )
        
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        logger.info(f"[Stage 0.5] Generating with {inputs['input_ids'].shape[1]} input tokens...")
        
        # Generate response
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                do_sample=True if temperature > 0 else False,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Decode response
        full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract only the assistant's response (after the prompt)
        if "[/INST]" in full_output:
            response_text = full_output.split("[/INST]")[-1].strip()
        else:
            response_text = full_output
        
        logger.info(f"[Stage 0.5] Generated {len(response_text)} characters")
        logger.debug(f"[Stage 0.5] Raw response: {response_text[:500]}...")
        
        # Parse JSON response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            logger.error("❌ Stage 0.5: No JSON found in response")
            raise ValueError("Stage 0.5 response did not contain valid JSON")
        
        response = json.loads(json_match.group(0))
        logger.info("[Stage 0.5] ✅ JSON parsed successfully")
        
        # Validate response structure
        if 'passed' not in response:
            logger.error("❌ Stage 0.5 response missing 'passed' field")
            raise ValueError("Stage 0.5 response missing 'passed' field")
        
        if not isinstance(response['passed'], bool):
            logger.error("❌ Stage 0.5 'passed' must be boolean")
            raise ValueError("Stage 0.5 'passed' must be boolean")
        
        # Add defaults for optional fields
        if 'errors' not in response:
            response['errors'] = []
        if 'warnings' not in response:
            response['warnings'] = []
        if 'calculations' not in response:
            response['calculations'] = {}
        if 'complexity' not in response:
            response['complexity'] = 'moderate'
        
        logger.info(f"[Stage 0.5] ✅ Validation complete: passed={response['passed']}, errors={len(response['errors'])}, warnings={len(response['warnings'])}")
        
        return response
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Stage 0.5: JSON parsing failed: {str(e)}")
        logger.error(f"Response text: {response_text[:1000]}")
        raise ValueError(f"Stage 0.5 returned invalid JSON: {str(e)}") from e
    
    except Exception as e:
        logger.error(f"❌ Stage 0.5 failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Clean up GPU memory on error
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        raise RuntimeError(f"Stage 0.5 math validation failed: {str(e)}") from e


# ============================================
# STAGE 2: REMOVED - Now runs in backend
# ============================================
# Stage 2 (Action Schema Analysis) has been moved to backend
# Uses ActionRegistry + APISchemaLoader (CPU-only, ~5-20ms)
# No longer requires GPU inference
# Backend implementation: documentClassificationService.performActionSchemaAnalysis()
