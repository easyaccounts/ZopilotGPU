"""
Document Classification Module for ZopilotGPU
Handles Stage 1 (Action Selection) and Stage 2 (Field Mapping) for backend

Stage 1: Semantic Analysis + Action Selection
- Analyzes document type, parties, amounts
- Suggests prerequisites, primary action, and follow-ups
- Returns: {semantic_analysis, suggested_actions, overall_confidence}

Stage 2: Field Mapping to API-Ready Format
- Maps extracted data directly to accounting software API request body format
- No transformations needed - output is POST-ready for Zoho/QuickBooks
- Generates entity lookups for ID resolution (Customer, Vendor, Item, Account)
- Performs tax verification and currency detection
- Returns: {api_request_body, lookups_required, validation}

Pipeline Flow:
1. Stage 1: Select action → 2. Stage 2: Build API request → 3. Stage 2.5: Lookup resolution → 4. Direct API POST

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
        {
            "accounting_relevance": {
                "has_accounting_relevance": bool,
                "relevance_reasoning": "...",
                "document_classification": "financial_transaction|informational|administrative|non_accounting",
                "rejection_reason": "If false, reason for rejection"
            },
            "semantic_analysis": {
                "document_type": "invoice|bill|receipt|...",
                "document_direction": "incoming|outgoing",
                "transaction_nature": "sale|purchase|...",
                "is_revenue_transaction": bool,
                "is_expense_transaction": bool,
                "primary_party": {...},
                "total_amount": float,
                "currency": "USD",
                "includes_tax": bool,
                "tax_amount": float,
                ...
            },
            "suggested_actions": [
                {
                    "action": "createCustomer",
                    "entity": "Customer",
                    "action_type": "PREREQUISITE",
                    "priority": 0,
                    "confidence": 95,
                    "reasoning": "...",
                    "auto_execute": true,
                    "requires": []
                },
                {
                    "action": "createInvoice",
                    "entity": "Invoice",
                    "action_type": "PRIMARY",
                    "priority": 1,
                    "confidence": 92,
                    "reasoning": "...",
                    "requires": ["createCustomer"]
                }
            ],
            "overall_confidence": 92,
            "missing_data": [],
            "assumptions": []
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

⚠️ CRITICAL INSTRUCTION ⚠️
You MUST respond with PURE JSON ONLY.
First character of your response MUST be: {{
Last character of your response MUST be: }}
DO NOT write any text like "Based on the document" or "Here is the analysis".
START IMMEDIATELY with the opening brace {{.

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
        response_text = processor.tokenizer.decode(
            outputs[0][input_tokens:], 
            skip_special_tokens=True
        )
        logger.info(f"   Response length: {len(response_text)} chars")
        
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
        
        # Validate Stage 1 structure
        _validate_stage1_response(result)
        
        actions_count = len(result.get('suggested_actions', []))
        doc_type = result.get('semantic_analysis', {}).get('document_type', 'unknown')
        confidence = result.get('overall_confidence', 0)
        
        logger.info(f"🎉 [Stage 1] Classification complete!")
        logger.info(f"   Document type: {doc_type}")
        logger.info(f"   Actions suggested: {actions_count}")
        logger.info(f"   Overall confidence: {confidence}%")
        
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


def classify_stage2(prompt: str, context: Dict[str, Any], generation_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Stage 2: Field Mapping
    
    Args:
        prompt: Field mapping prompt with action spec, semantic analysis, extracted data, COA
        context: {"stage": "field_mapping", "action": "createInvoice", "entity": "Invoice"}
        generation_config: Generation parameters from backend
            - max_new_tokens: Maximum output tokens (default 3000, backend sends 3000)
            - temperature: Sampling temperature (default 0.05, backend sends 0.05)
            - top_p, top_k, repetition_penalty
            - max_input_length: Input truncation limit (default 29491)
    
    Returns:
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
                "total_amount_matches": true,
                "all_required_fields_present": true,
                "calculated_total": 1234.50,
                "extracted_total": 1234.50,
                "warnings": [
                    "Optional field X not found in extracted data",
                    "Date format converted from DD/MM/YYYY to YYYY-MM-DD"
                ],
                "tax_verification": {
                    "tax_calculation_valid": true,
                    "extracted_tax_amount": 123.45,
                    "extracted_tax_rate": 10,
                    "calculated_tax_base": 1234.50,
                    "taxable_charges": ["freight", "service_fee"],
                    "non_taxable_charges": [],
                    "discrepancy": 0.00
                }
            }
        }
        
    Note: Backend relies on API validation for final checks. This validation is informational only.
    Removed stages: Business rule validation (2.6) and currency conversion (2.7) - let API handle.
    """
    action_name = context.get('action', 'unknown')
    logger.info(f"🎯 [Stage 2] Starting field mapping for action: {action_name}")
    
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
    
    logger.info(f"⚙️  [Stage 2] Generation config: max_new_tokens={max_new_tokens}, temp={temperature}, max_input={max_input_length}")
    
    try:
        # Get model processor
        processor = get_llama_processor()
        
        # FIX: Build Mixtral-compatible prompt with JSON prefix forcing
        # Force model to start generation with { to prevent preamble text
        formatted_prompt = f"<s>[INST] {prompt}\n\n⚠️ CRITICAL: Your response must start with the opening brace character {{ and contain ONLY valid JSON. No text before the JSON. No explanations after. [/INST]\n{{"
        
        # Tokenize with CONFIGURABLE max_input_length
        logger.info("🔢 [Stage 2] Tokenizing prompt...")
        inputs = processor.tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=max_input_length)
        inputs = {k: v.to(processor.model.device) for k, v in inputs.items()}
        input_tokens = len(inputs["input_ids"][0])
        logger.info(f"   Input tokens: {input_tokens}")
        
        # Generate with CONFIGURABLE parameters
        logger.info(f"🚀 [Stage 2] Generating field mappings (max {max_new_tokens} tokens)...")
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
        logger.info(f"✅ [Stage 2] Generated {output_tokens} tokens in {gen_time:.1f}s ({tokens_per_sec:.1f} tok/s)")
        
        # FIX: Detect suspiciously low token count (hallucination indicator)
        if output_tokens < 100:
            logger.warning(f"⚠️  [Stage 2] Suspiciously low token count ({output_tokens} tokens) - possible hallucination or early stopping")
        
        # Decode
        logger.info("📖 [Stage 2] Decoding response...")
        response_text = processor.tokenizer.decode(
            outputs[0][input_tokens:], 
            skip_special_tokens=True
        )
        logger.info(f"   Response length: {len(response_text)} chars")
        
        # FIX: Prepend the { we forced in the prompt (model continues from {)
        response_text = "{" + response_text
        
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
        logger.info("🔍 [Stage 2] Parsing JSON response...")
        try:
            result = _parse_classification_response(response_text, stage=2)
        except ValueError as parse_error:
            # FIX: If JSON parsing fails due to preamble/hallucination, retry once with stronger prompt
            if output_tokens < 100 or "No JSON object found" in str(parse_error):
                logger.warning(f"⚠️  [Stage 2] First attempt failed (low tokens or no JSON), retrying with stronger enforcement...")
                
                # Clear cache before retry
                if hasattr(processor.model, 'past_key_values'):
                    processor.model.past_key_values = None
                torch.cuda.empty_cache()
                
                # Retry with even stronger JSON enforcement and higher temperature
                retry_prompt = f"<s>[INST] {prompt}\n\n🚨 CRITICAL REQUIREMENT 🚨\nYour response MUST be valid JSON only. Start immediately with {{ character. No preamble text allowed.\n\nRespond now with JSON: [/INST]\n{{"
                
                retry_inputs = processor.tokenizer(retry_prompt, return_tensors="pt", truncation=True, max_length=max_input_length)
                retry_inputs = {k: v.to(processor.model.device) for k, v in retry_inputs.items()}
                
                logger.info("🔄 [Stage 2] Retry generation with stronger JSON enforcement...")
                with torch.no_grad():
                    retry_outputs = processor.model.generate(
                        **retry_inputs,
                        max_new_tokens=max_new_tokens,
                        temperature=0.15,  # Slightly higher temp for retry
                        do_sample=True,
                        top_p=0.9,
                        top_k=40,
                        repetition_penalty=1.2,
                        pad_token_id=processor.tokenizer.eos_token_id,
                        eos_token_id=processor.tokenizer.eos_token_id
                    )
                
                retry_response = "{" + processor.tokenizer.decode(
                    retry_outputs[0][len(retry_inputs["input_ids"][0]):], 
                    skip_special_tokens=True
                )
                
                logger.info(f"🔄 [Stage 2] Retry generated {len(retry_outputs[0]) - len(retry_inputs['input_ids'][0])} tokens")
                result = _parse_classification_response(retry_response, stage=2)
                logger.info("✅ [Stage 2] Retry successful!")
            else:
                raise  # Re-raise if not a recoverable error
        
        # Validate Stage 2 structure
        _validate_stage2_response(result)
        
        lookups_count = len(result.get('lookups_required', []))
        fields_count = len(result.get('api_request_body', {}))
        
        logger.info(f"🎉 [Stage 2] Field mapping complete for {action_name}!")
        logger.info(f"   API fields mapped: {fields_count}")
        logger.info(f"   Lookups required: {lookups_count}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [Stage 2] Field mapping failed for {action_name}: {str(e)}")
        
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
        preamble_patterns = [
            "Based on the provided",
            "Here's the",
            "Here is the",
            "The following is",
            "Below is the",
            "I'll provide",
            "Let me provide"
        ]
        
        for pattern in preamble_patterns:
            if json_str.lower().startswith(pattern.lower()):
                logger.warning(f"⚠️  Stage {stage} response has preamble text, removing...")
                logger.warning(f"   Preamble: {json_str[:100]}...")
                # Find where JSON actually starts
                json_start = json_str.find('{')
                if json_start > 0:
                    json_str = json_str[json_start:]
                    logger.info(f"   Extracted JSON starting at position {json_start}")
                break
        
        # FIX: LLM sometimes omits opening brace despite [/INST]{ prompt seed
        # If response starts with a quote (likely a JSON key), prepend {
        if json_str and json_str[0] == '"':
            logger.warning(f"⚠️  Stage {stage} response missing opening brace, prepending {{")
            json_str = '{' + json_str
        
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
        
        parsed = json.loads(json_str)
        
        logger.info(f"✅ Successfully parsed Stage {stage} JSON ({len(json_str)} chars)")
        return parsed
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Stage {stage} JSON: {str(e)}")
        logger.error(f"   JSON string: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
        logger.error(f"   Raw response: {response[:500]}...")
        raise ValueError(f"Invalid JSON in Stage {stage} response: {str(e)}")


def _validate_stage1_response(response: Dict[str, Any]) -> None:
    """
    Validate Stage 1 response has required structure.
    Fixes common issues like missing PRIMARY action.
    Handles new accounting_relevance field for filtering non-accounting documents.
    
    Args:
        response: Parsed Stage 1 response dictionary
    
    Raises:
        ValueError: If validation fails
    """
    # Check for accounting_relevance field (new enhancement)
    if 'accounting_relevance' not in response:
        logger.warning("[Stage 1] ⚠️  No 'accounting_relevance' field - assuming has accounting relevance (legacy response)")
        response['accounting_relevance'] = {
            'has_accounting_relevance': True,
            'relevance_reasoning': 'Legacy response - assumed to have accounting relevance',
            'document_classification': 'financial_transaction'
        }
    
    # If document has no accounting relevance, allow empty suggested_actions
    has_accounting_relevance = response['accounting_relevance'].get('has_accounting_relevance', True)
    
    if not has_accounting_relevance:
        logger.info("[Stage 1] ℹ️  Document marked as non-accounting, empty actions allowed")
        # Ensure suggested_actions is empty array for non-accounting documents
        if 'suggested_actions' not in response or not isinstance(response['suggested_actions'], list):
            response['suggested_actions'] = []
        # semantic_analysis can be empty for non-accounting documents
        if 'semantic_analysis' not in response:
            response['semantic_analysis'] = {}
        logger.info("[Stage 1] ✅ Non-accounting document validation passed")
        return
    
    # For accounting documents, enforce strict validation
    # Check required top-level fields
    if 'semantic_analysis' not in response:
        logger.error("❌ Stage 1 response missing 'semantic_analysis'")
        raise ValueError("Stage 1 response missing 'semantic_analysis'")
    
    if 'suggested_actions' not in response:
        logger.error("❌ Stage 1 response missing 'suggested_actions'")
        raise ValueError("Stage 1 response missing 'suggested_actions'")
    
    if not isinstance(response['suggested_actions'], list):
        logger.error("❌ Stage 1 'suggested_actions' must be an array")
        raise ValueError("Stage 1 'suggested_actions' must be an array")
    
    if len(response['suggested_actions']) == 0:
        logger.error("❌ Stage 1 'suggested_actions' array is empty")
        raise ValueError("Stage 1 must suggest at least one action")
    
    # Check for PRIMARY action (exactly 1 required)
    primary_actions = [a for a in response['suggested_actions'] if a.get('action_type') == 'PRIMARY']
    
    if len(primary_actions) == 0:
        logger.warning("[Stage 1] ⚠️  No PRIMARY action found - auto-fixing by marking highest confidence as PRIMARY")
        # Auto-fix: Mark highest confidence action as PRIMARY
        if response['suggested_actions']:
            sorted_actions = sorted(
                response['suggested_actions'], 
                key=lambda a: a.get('confidence', 0), 
                reverse=True
            )
            sorted_actions[0]['action_type'] = 'PRIMARY'
            sorted_actions[0]['priority'] = 1
            logger.info(f"   ✅ Marked '{sorted_actions[0].get('action')}' as PRIMARY (confidence: {sorted_actions[0].get('confidence')}%)")
    
    elif len(primary_actions) > 1:
        logger.warning(f"[Stage 1] ⚠️  Multiple PRIMARY actions found ({len(primary_actions)}) - keeping only highest confidence")
        # Auto-fix: Keep highest confidence primary, demote others
        sorted_primaries = sorted(
            primary_actions, 
            key=lambda a: a.get('confidence', 0), 
            reverse=True
        )
        # Keep first as PRIMARY
        logger.info(f"   ✅ Keeping '{sorted_primaries[0].get('action')}' as PRIMARY")
        # Demote rest to FOLLOW_UP
        for action in sorted_primaries[1:]:
            action['action_type'] = 'FOLLOW_UP'
            action['priority'] = 2
            action['optional'] = True
            action['requires_user_confirmation'] = True
            logger.info(f"   ➡️  Demoted '{action.get('action')}' to FOLLOW_UP")
    
    # Validate action structure
    for i, action in enumerate(response['suggested_actions']):
        if 'action' not in action:
            raise ValueError(f"Action #{i} missing 'action' field")
        
        # Action names should be in snake_case format (create_invoice, create_bill, etc.)
        # No validation needed - backend validates against software-specific action registries
        action_name = action['action']
        
        if 'entity' not in action:
            raise ValueError(f"Action '{action['action']}' missing 'entity' field")
        if 'action_type' not in action:
            raise ValueError(f"Action '{action['action']}' missing 'action_type' field")
        if 'confidence' not in action:
            logger.warning(f"Action '{action['action']}' missing 'confidence' - setting to 80")
            action['confidence'] = 80
        if 'reasoning' not in action:
            logger.warning(f"Action '{action['action']}' missing 'reasoning' - setting default")
            action['reasoning'] = f"Suggested action based on document analysis"
    
    logger.info("[Stage 1] ✅ Validation passed")


def _validate_stage2_response(response: Dict[str, Any]) -> None:
    """
    Validate Stage 2 response has required structure.
    Adds default values for optional fields.
    
    Args:
        response: Parsed Stage 2 response dictionary
    
    Raises:
        ValueError: If validation fails
    """
    # Check required field
    if 'api_request_body' not in response:
        logger.error("❌ Stage 2 response missing 'api_request_body'")
        raise ValueError("Stage 2 response missing 'api_request_body'")
    
    if not isinstance(response['api_request_body'], dict):
        logger.error("❌ Stage 2 'api_request_body' must be an object")
        raise ValueError("Stage 2 'api_request_body' must be an object")
    
    # Optional but recommended fields - add defaults if missing
    if 'lookups_required' not in response:
        logger.warning("[Stage 2] ⚠️  No 'lookups_required' array - setting empty array")
        response['lookups_required'] = []
    
    if not isinstance(response['lookups_required'], list):
        logger.warning("[Stage 2] ⚠️  'lookups_required' is not an array - converting to array")
        response['lookups_required'] = []
    
    if 'validation' not in response:
        logger.warning("[Stage 2] ⚠️  No 'validation' object - creating default")
        response['validation'] = {
            "all_required_fields_present": True,
            "warnings": []
        }
    
    if not isinstance(response['validation'], dict):
        logger.warning("[Stage 2] ⚠️  'validation' is not an object - creating default")
        response['validation'] = {
            "all_required_fields_present": True,
            "warnings": []
        }
    
    logger.info("[Stage 2] ✅ Validation passed")
