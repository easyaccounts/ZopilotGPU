#!/usr/bin/env python3
"""
Fix the 9 failed QuickBooks schema conversions:
- 7 sales order actions: Backend maps to SalesOrderRequest/Response, should be SalesReceiptRequest/Response
- 2 user actions: Backend maps to UserRequest (doesn't exist), users are READ-ONLY in QB API
"""

import json
import logging
import sys
from pathlib import Path
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QuickBooksSchemaFixer:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.backend_dir = self.base_dir.parent / "zopilot-backend"
        self.schemas_dir = self.base_dir / "schemas" / "stage_4" / "actions" / "quickbooks"
        
        # Schema path corrections
        self.corrections = {
            'create_sales_order': ('salesorder.yml', 'components.schemas.SalesReceiptRequest'),
            'update_sales_order': ('salesorder.yml', 'components.schemas.SalesReceiptRequest'),
            'get_sales_order': ('salesorder.yml', 'components.schemas.SalesReceiptResponse'),
            'list_sales_orders': ('salesorder.yml', 'components.schemas.SalesReceiptResponse'),
            'delete_sales_order': ('salesorder.yml', 'components.schemas.SalesReceiptRequest'),
            'void_sales_order': ('salesorder.yml', 'components.schemas.SalesReceiptRequest'),
            'email_sales_order': ('salesorder.yml', 'components.schemas.SalesReceiptRequest'),
            # User actions - use UserResponse since create/delete don't exist
            'create_user': ('user.yml', 'components.schemas.UserResponse'),
            'delete_user': ('user.yml', 'components.schemas.UserResponse'),
        }
        
        self.spec_cache = {}
    
    def load_openapi_spec(self, spec_file: str) -> dict:
        """Load and cache OpenAPI spec"""
        if spec_file in self.spec_cache:
            return self.spec_cache[spec_file]
        
        spec_path = self.backend_dir / "quickbooks-api-reference" / spec_file
        if not spec_path.exists():
            logger.error(f"Spec file not found: {spec_path}")
            return None
        
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
                self.spec_cache[spec_file] = spec
                return spec
        except Exception as e:
            logger.error(f"Error loading spec {spec_file}: {e}")
            return None
    
    def resolve_refs_recursively(self, schema: dict, spec: dict, visited: set = None) -> dict:
        """Resolve all $ref references in a schema"""
        if visited is None:
            visited = set()
        
        if not isinstance(schema, dict):
            return schema
        
        # Handle $ref
        if '$ref' in schema:
            ref_path = schema['$ref']
            if ref_path in visited:
                return {'type': 'object', 'description': f'Circular reference: {ref_path}'}
            
            visited.add(ref_path)
            
            # Parse reference path
            if ref_path.startswith('#/'):
                parts = ref_path[2:].split('/')
                ref_schema = spec
                for part in parts:
                    ref_schema = ref_schema.get(part, {})
                
                # Recursively resolve the referenced schema
                resolved = self.resolve_refs_recursively(ref_schema, spec, visited.copy())
                
                # Merge with any other properties in the original schema
                result = {k: v for k, v in schema.items() if k != '$ref'}
                result.update(resolved)
                return result
        
        # Recursively process nested structures
        result = {}
        for key, value in schema.items():
            if isinstance(value, dict):
                result[key] = self.resolve_refs_recursively(value, spec, visited)
            elif isinstance(value, list):
                result[key] = [
                    self.resolve_refs_recursively(item, spec, visited) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        
        return result
    
    def convert_openapi_to_json_schema(self, openapi_schema: dict) -> dict:
        """Convert OpenAPI 3.0 schema to JSON Schema Draft 7"""
        # Start with the schema as-is
        json_schema = openapi_schema.copy()
        
        # Add JSON Schema metadata
        json_schema['$schema'] = 'http://json-schema.org/draft-07/schema#'
        
        # Remove OpenAPI-specific fields
        for field in ['example', 'externalDocs', 'xml', 'discriminator']:
            json_schema.pop(field, None)
        
        # Convert format fields if needed
        if 'format' in json_schema:
            # JSON Schema Draft 7 supports these formats natively
            pass
        
        # Recursively clean nested schemas
        def clean_schema(schema):
            if not isinstance(schema, dict):
                return schema
            
            cleaned = {}
            for key, value in schema.items():
                if key in ['example', 'externalDocs', 'xml', 'discriminator', 'readOnly', 'writeOnly']:
                    continue
                if isinstance(value, dict):
                    cleaned[key] = clean_schema(value)
                elif isinstance(value, list):
                    cleaned[key] = [clean_schema(item) if isinstance(item, dict) else item for item in value]
                else:
                    cleaned[key] = value
            return cleaned
        
        return clean_schema(json_schema)
    
    def fix_action_schema(self, action_name: str) -> bool:
        """Fix schema for a single action"""
        logger.info(f"\n--- Fixing {action_name} ---")
        
        spec_file, correct_schema_path = self.corrections[action_name]
        
        # Load OpenAPI spec
        spec = self.load_openapi_spec(spec_file)
        if not spec:
            logger.error(f"  ❌ Failed to load spec: {spec_file}")
            return False
        
        # Navigate to the schema
        parts = correct_schema_path.split('.')
        schema = spec
        for part in parts:
            schema = schema.get(part, {})
        
        if not schema:
            logger.error(f"  ❌ Schema not found: {correct_schema_path}")
            return False
        
        # Resolve all $ref references
        resolved_schema = self.resolve_refs_recursively(schema, spec)
        
        # Convert to JSON Schema Draft 7
        json_schema = self.convert_openapi_to_json_schema(resolved_schema)
        
        # Add metadata
        json_schema['title'] = f"{action_name} API Request (QUICKBOOKS)"
        json_schema['description'] = f"Schema for {action_name} - extracted from quickbooks OpenAPI spec"
        
        # Add note for user actions
        if 'user' in action_name:
            json_schema['description'] += " - NOTE: QuickBooks Users are READ-ONLY, this is for reference only"
        
        # Save to file
        output_path = self.schemas_dir / f"{action_name}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_schema, f, indent=2)
        
        props_count = len(json_schema.get('properties', {}))
        logger.info(f"  ✅ Fixed: {action_name}.json ({props_count} properties)")
        return True
    
    def fix_all(self):
        """Fix all failed schemas"""
        logger.info("=" * 80)
        logger.info("FIXING FAILED QUICKBOOKS SCHEMAS")
        logger.info("=" * 80)
        
        success_count = 0
        failed_count = 0
        
        for action_name in self.corrections.keys():
            try:
                if self.fix_action_schema(action_name):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"  ❌ Exception fixing {action_name}: {e}")
                failed_count += 1
        
        logger.info("\n" + "=" * 80)
        logger.info("FIX SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Successfully fixed: {success_count}/9")
        logger.info(f"❌ Failed: {failed_count}/9")
        
        if failed_count == 0:
            logger.info("\n🎉 All failed schemas have been fixed!")
            logger.info(f"QuickBooks coverage: {135 + success_count}/144 = {((135 + success_count) / 144 * 100):.1f}%")
        else:
            logger.info(f"\n⚠️ {failed_count} schemas still need attention")
        
        return failed_count == 0

if __name__ == '__main__':
    fixer = QuickBooksSchemaFixer()
    success = fixer.fix_all()
    sys.exit(0 if success else 1)
