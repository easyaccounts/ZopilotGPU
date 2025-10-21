"""
Schema Loader for Outlines Grammar-Constrained Generation

Loads JSON schemas for different stages and provides utilities
for schema management and caching.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Base directory for schemas
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

# Schema cache to avoid repeated file reads
_schema_cache: Dict[str, Any] = {}


def load_schema(schema_path: str) -> Optional[Dict[str, Any]]:
    """
    Load a JSON schema from file with caching.
    
    Args:
        schema_path: Relative path from schemas/ directory
                    e.g., "stage_2_5/entity_extraction_base.json"
    
    Returns:
        Loaded JSON schema dict or None if not found
    """
    # Check cache first
    if schema_path in _schema_cache:
        logger.debug(f"[Schema Loader] Cache hit: {schema_path}")
        return _schema_cache[schema_path]
    
    # Load from file
    full_path = SCHEMAS_DIR / schema_path
    
    if not full_path.exists():
        logger.error(f"[Schema Loader] Schema not found: {full_path}")
        return None
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Cache for future use
        _schema_cache[schema_path] = schema
        logger.info(f"[Schema Loader] Loaded schema: {schema_path}")
        return schema
        
    except json.JSONDecodeError as e:
        logger.error(f"[Schema Loader] Invalid JSON in {schema_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"[Schema Loader] Error loading {schema_path}: {e}")
        return None


def get_stage_2_5_schema() -> Optional[Dict[str, Any]]:
    """
    Get the base Stage 2.5 entity extraction schema.
    
    Returns:
        Stage 2.5 JSON schema or None if not found
    """
    return load_schema("stage_2_5/entity_extraction_base.json")


def get_stage_1_schema() -> Optional[Dict[str, Any]]:
    """
    Get the Stage 1 semantic analysis schema.
    
    Returns:
        Stage 1 JSON schema or None if not found
    """
    return load_schema("stage_1/semantic_analysis.json")


def get_stage_4_schema(is_batch: bool = False, action_name: Optional[str] = None,
                       software: str = 'zohobooks') -> Optional[Dict[str, Any]]:
    """
    Get the Stage 4 field mapping schema.
    
    Args:
        is_batch: If True, returns batch schema; if False, returns single action schema
        action_name: If provided, returns action-specific API schema (e.g., 'create_bill')
        software: Accounting software ('zohobooks' or 'quickbooks'), default 'zohobooks'
    
    Returns:
        Stage 4 JSON schema or None if not found
    """
    # Priority 1: Action-specific schema (most precise, eliminates field hallucination)
    if action_name:
        action_schema_path = f"stage_4/actions/{software}/{action_name}.json"
        action_schema = load_schema(action_schema_path)
        if action_schema:
            logger.info(f"✅ [Stage 4] Using action-specific schema for {action_name}")
            # Wrap action schema in field_mapping structure for Stage 4 output
            return {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "required": ["api_request_body"],
                "properties": {
                    "api_request_body": action_schema,
                    "lookups_required": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity placeholders like ${account:123}"
                    },
                    "validation": {
                        "type": "object",
                        "required": ["is_valid"],
                        "properties": {
                            "is_valid": {"type": "boolean"},
                            "missing_required_fields": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "warnings": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                },
                "additionalProperties": False
            }
        else:
            logger.warning(f"⚠️  [Stage 4] Action schema not found for {action_name}, falling back to generic")
    
    # Priority 2: Generic batch or single schema (fallback)
    if is_batch:
        return load_schema("stage_4/field_mapping_batch.json")
    else:
        return load_schema("stage_4/field_mapping_single.json")


def clear_cache():
    """Clear the schema cache (useful for testing or hot-reloading)."""
    global _schema_cache
    _schema_cache.clear()
    logger.info("[Schema Loader] Cache cleared")


def validate_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate that a schema is a valid JSON Schema Draft 7.
    
    Args:
        schema: Schema dict to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        from jsonschema import Draft7Validator
        Draft7Validator.check_schema(schema)
        return True
    except Exception as e:
        logger.error(f"[Schema Loader] Invalid schema: {e}")
        return False


# Pre-load schemas at module import for faster access
def _preload_schemas():
    """Pre-load common schemas into cache."""
    try:
        get_stage_2_5_schema()
        logger.info("[Schema Loader] Pre-loaded Stage 2.5 schema")
        get_stage_4_schema(is_batch=False)
        logger.info("[Schema Loader] Pre-loaded Stage 4 single schema")
        get_stage_4_schema(is_batch=True)
        logger.info("[Schema Loader] Pre-loaded Stage 4 batch schema")
    except Exception as e:
        logger.warning(f"[Schema Loader] Could not pre-load schemas: {e}")


# Preload on import
_preload_schemas()
