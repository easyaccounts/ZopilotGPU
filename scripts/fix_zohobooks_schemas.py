#!/usr/bin/env python3
"""
Fix Zoho Books schema failures by correcting schema path naming patterns.
The main issue is backend maps to patterns like 'delete-X-response' but actual schemas are 'delete-a-X-response'.
"""

import json
import logging
import sys
from pathlib import Path
import yaml
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ZohoBooksSchemaFixer:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.backend_dir = self.base_dir.parent / "zopilot-backend"
        self.schemas_dir = self.base_dir / "schemas" / "stage_4" / "actions" / "zohobooks"
        self.openapi_dir = self.backend_dir / "openapi-all"
        
        # Cache for loaded specs
        self.spec_cache = {}
        
        # Track successes and failures
        self.successful = []
        self.failed = []
    
    def load_openapi_spec(self, spec_file: str) -> dict:
        """Load and cache OpenAPI spec"""
        if spec_file in self.spec_cache:
            return self.spec_cache[spec_file]
        
        # Remove 'openapi-all/' prefix if present since we already have it in openapi_dir
        if spec_file.startswith('openapi-all/'):
            spec_file = spec_file.replace('openapi-all/', '', 1)
        
        spec_path = self.openapi_dir / spec_file
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
    
    def find_schema_in_spec(self, spec: dict, original_path: str) -> tuple:
        """
        Try to find the schema in the spec, trying various naming patterns.
        Returns (found_schema, actual_path) or (None, None)
        """
        # Get the schema name from the path
        schema_name = original_path.split('.')[-1]
        
        # Try variations of the schema name
        variations = [
            schema_name,  # Original
            schema_name.replace('-response', '-a-response'),  # delete-bill-response -> delete-a-bill-response
            schema_name.replace('-request', '-a-request'),  # Similar pattern for requests
            schema_name.replace('delete-', 'delete-a-'),
            schema_name.replace('void-', 'void-a-'),
            schema_name.replace('list-', 'list-'),  # Keep as is
            schema_name.replace('-response', ''),  # Try without -response suffix
            schema_name.replace('Response', ''),  # Try camelCase variant
        ]
        
        # Try to navigate to components.schemas
        if 'components' not in spec or 'schemas' not in spec['components']:
            return None, None
        
        schemas = spec['components']['schemas']
        
        # Try each variation
        for variant in variations:
            if variant in schemas:
                actual_path = f"components.schemas.{variant}"
                return schemas[variant], actual_path
        
        # If still not found, try case-insensitive search
        schema_name_lower = schema_name.lower()
        for key in schemas.keys():
            if key.lower() == schema_name_lower or schema_name_lower in key.lower():
                actual_path = f"components.schemas.{key}"
                logger.info(f"  Found via fuzzy match: {schema_name} -> {key}")
                return schemas[key], actual_path
        
        return None, None
    
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
                
                if not ref_schema:
                    return {'type': 'object', 'description': f'Unresolved reference: {ref_path}'}
                
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
        json_schema = openapi_schema.copy()
        
        # Add JSON Schema metadata
        json_schema['$schema'] = 'http://json-schema.org/draft-07/schema#'
        
        # Remove OpenAPI-specific fields
        for field in ['example', 'externalDocs', 'xml', 'discriminator']:
            json_schema.pop(field, None)
        
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
    
    def get_failed_actions_from_backend(self) -> dict:
        """Parse backend's apiSchemaLoader.ts to find all Zoho Books actions"""
        api_schema_path = self.backend_dir / "src" / "services" / "documentClassification" / "apiSchemaLoader.ts"
        
        with open(api_schema_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract actions that have zohobooks mappings
        # Pattern: 'action_name': { ... 'zohobooks': { specFile: '...', schemaPath: '...' } }
        action_pattern = r"'([a-z_]+)':\s*\{(.*?)\n\s\s\}"
        
        actions = {}
        for match in re.finditer(action_pattern, content, re.DOTALL):
            action_name = match.group(1)
            action_config = match.group(2)
            
            # Check if it has zohobooks config
            if "'zohobooks'" in action_config or '"zohobooks"' in action_config:
                # Extract zohobooks config
                zoho_match = re.search(
                    r"'(?:zohobooks|zoho-books)':\s*\{(.*?)\n\s\s\s\s\}",
                    action_config,
                    re.DOTALL
                )
                
                if zoho_match:
                    zoho_config = zoho_match.group(1)
                    
                    # Extract specFile and schemaPath
                    spec_match = re.search(r"specFile:\s*'([^']+)'", zoho_config)
                    schema_match = re.search(r"schemaPath:\s*'([^']+)'", zoho_config)
                    
                    if spec_match and schema_match:
                        actions[action_name] = {
                            'spec_file': spec_match.group(1),
                            'schema_path': schema_match.group(1)
                        }
        
        return actions
    
    def fix_action_schema(self, action_name: str, spec_file: str, original_schema_path: str) -> bool:
        """Fix schema for a single action"""
        # Check if schema already exists and is valid
        output_path = self.schemas_dir / f"{action_name}.json"
        if output_path.exists():
            # Schema already exists, skip
            return True
        
        # Load OpenAPI spec
        spec = self.load_openapi_spec(spec_file)
        if not spec:
            logger.warning(f"  ⚠️ {action_name}: Could not load spec {spec_file}")
            return False
        
        # Try to find the schema
        schema, actual_path = self.find_schema_in_spec(spec, original_schema_path)
        
        if not schema:
            logger.warning(f"  ❌ {action_name}: Schema not found (tried: {original_schema_path})")
            return False
        
        # Resolve all $ref references
        try:
            resolved_schema = self.resolve_refs_recursively(schema, spec)
        except Exception as e:
            logger.warning(f"  ❌ {action_name}: Error resolving refs - {e}")
            return False
        
        # Convert to JSON Schema Draft 7
        json_schema = self.convert_openapi_to_json_schema(resolved_schema)
        
        # Add metadata
        json_schema['title'] = f"{action_name} API Request (ZOHOBOOKS)"
        json_schema['description'] = f"Schema for {action_name} - extracted from zohobooks OpenAPI spec"
        if actual_path != original_schema_path:
            json_schema['description'] += f" (corrected path: {actual_path})"
        
        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_schema, f, indent=2)
        
        props_count = len(json_schema.get('properties', {}))
        logger.info(f"  ✅ {action_name}: Fixed ({props_count} properties)")
        return True
    
    def fix_all(self):
        """Fix all failed Zoho Books schemas"""
        logger.info("=" * 80)
        logger.info("FIXING ZOHO BOOKS SCHEMAS")
        logger.info("=" * 80)
        logger.info("")
        
        # Get all actions from backend
        logger.info("Extracting Zoho Books actions from backend...")
        actions = self.get_failed_actions_from_backend()
        logger.info(f"Found {len(actions)} Zoho Books actions in backend\n")
        
        # Process each action
        for action_name, config in sorted(actions.items()):
            try:
                if self.fix_action_schema(action_name, config['spec_file'], config['schema_path']):
                    self.successful.append(action_name)
                else:
                    self.failed.append(action_name)
            except Exception as e:
                logger.error(f"  ❌ {action_name}: Exception - {e}")
                self.failed.append(action_name)
        
        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("FIX SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total actions processed: {len(actions)}")
        logger.info(f"✅ Successfully fixed/verified: {len(self.successful)}")
        logger.info(f"❌ Failed: {len(self.failed)}")
        
        # Count final schemas
        total_schemas = len(list(self.schemas_dir.glob("*.json")))
        logger.info(f"\nFinal Zoho Books coverage: {total_schemas}/144")
        logger.info(f"Coverage: {(total_schemas / 144 * 100):.1f}%")
        
        if self.failed:
            logger.info(f"\n⚠️ Failed actions:")
            for action in self.failed[:20]:  # Show first 20
                logger.info(f"  - {action}")
            if len(self.failed) > 20:
                logger.info(f"  ... and {len(self.failed) - 20} more")
        else:
            logger.info("\n🎉 All Zoho Books schemas successfully processed!")
        
        return len(self.failed) == 0

if __name__ == '__main__':
    fixer = ZohoBooksSchemaFixer()
    success = fixer.fix_all()
    sys.exit(0 if success else 1)
