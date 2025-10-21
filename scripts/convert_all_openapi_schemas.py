"""
Comprehensive OpenAPI to Outlines Schema Converter

Extracts ALL action mappings from backend's apiSchemaLoader.ts and converts
ALL actions for BOTH QuickBooks and Zoho Books to Outlines-compatible schemas.

This ensures 100% coverage across all supported actions and software platforms.
"""

import os
import json
import yaml
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComprehensiveSchemaConverter:
    """Converts all actions from apiSchemaLoader.ts to Outlines schemas"""
    
    def __init__(self, backend_root: str, gpu_root: str):
        self.backend_root = Path(backend_root)
        self.gpu_root = Path(gpu_root)
        self.schema_cache: Dict[str, Any] = {}
        self.action_map: Dict[str, Dict[str, Any]] = {}
        
    def extract_action_map_from_backend(self) -> Dict[str, Dict[str, Any]]:
        """
        Parse apiSchemaLoader.ts and extract the complete ACTION_TO_SCHEMA_MAP.
        Returns a dict mapping action_name -> {software: {spec_file, schema_path, endpoint}}
        """
        api_schema_loader_path = self.backend_root / 'src/services/documentClassification/apiSchemaLoader.ts'
        
        if not api_schema_loader_path.exists():
            logger.error(f"❌ apiSchemaLoader.ts not found at {api_schema_loader_path}")
            return {}
        
        logger.info(f"📖 Reading {api_schema_loader_path}")
        
        with open(api_schema_loader_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the ACTION_TO_SCHEMA_MAP object
        # Find the const declaration
        match = re.search(
            r'const ACTION_TO_SCHEMA_MAP:\s*Record<string,\s*Record<AccountingSoftware,\s*APISchemaInfo>>\s*=\s*\{(.*?)\n\};',
            content,
            re.DOTALL
        )
        
        if not match:
            logger.error("❌ Could not find ACTION_TO_SCHEMA_MAP in apiSchemaLoader.ts")
            return {}
        
        map_content = match.group(1)
        
        # Parse action entries using regex
        # Pattern: 'action_name': { ... }
        action_pattern = re.compile(
            r"'([a-z_]+)':\s*\{(.*?)\n\s\s\}",
            re.DOTALL
        )
        
        action_map = {}
        
        for action_match in action_pattern.finditer(map_content):
            action_name = action_match.group(1)
            action_content = action_match.group(2)
            
            # Parse software entries within this action
            software_pattern = re.compile(
                r"'(quickbooks|zohobooks|zoho-books)':\s*\{(.*?)\n\s\s\s\s\}",
                re.DOTALL
            )
            
            software_configs = {}
            
            for software_match in software_pattern.finditer(action_content):
                software = software_match.group(1)
                software_content = software_match.group(2)
                
                # Extract specFile, schemaPath, endpoint
                spec_file_match = re.search(r"specFile:\s*'([^']+)'", software_content)
                schema_path_match = re.search(r"schemaPath:\s*'([^']+)'", software_content)
                endpoint_match = re.search(r"endpoint:\s*'([^']+)'", software_content)
                
                if spec_file_match and schema_path_match:
                    software_configs[software] = {
                        'spec_file': spec_file_match.group(1),
                        'schema_path': schema_path_match.group(1),
                        'endpoint': endpoint_match.group(1) if endpoint_match else ''
                    }
            
            if software_configs:
                action_map[action_name] = software_configs
        
        logger.info(f"✅ Extracted {len(action_map)} actions from apiSchemaLoader.ts")
        
        return action_map
    
    def load_openapi_spec(self, spec_file: str) -> Optional[Dict]:
        """Load and parse an OpenAPI YAML file with caching"""
        if spec_file in self.schema_cache:
            return self.schema_cache[spec_file]
        
        spec_path = self.backend_root / spec_file
        
        if not spec_path.exists():
            logger.warning(f"⚠️  Spec file not found: {spec_file}")
            return None
        
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
            self.schema_cache[spec_file] = spec
            return spec
        except Exception as e:
            logger.error(f"❌ Failed to load {spec_file}: {e}")
            return None
    
    def resolve_schema_ref(self, spec: Dict, ref_path: str) -> Optional[Dict]:
        """Resolve $ref pointers in OpenAPI schema"""
        if not ref_path.startswith('#/'):
            return None
        
        path_parts = ref_path[2:].replace('/', '.').split('.')
        current = spec
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def extract_schema_from_path(self, spec: Dict, schema_path: str) -> Optional[Dict]:
        """Extract schema from OpenAPI spec using dot notation path"""
        path_parts = schema_path.split('.')
        current = spec
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def resolve_all_refs(self, schema: Any, spec: Dict, depth: int = 0) -> Any:
        """Recursively resolve all $ref pointers"""
        if depth > 15:
            return schema
        
        if isinstance(schema, dict):
            if '$ref' in schema:
                ref_path = schema['$ref']
                resolved = self.resolve_schema_ref(spec, ref_path)
                if resolved:
                    merged = {**schema}
                    del merged['$ref']
                    resolved_deep = self.resolve_all_refs(resolved, spec, depth + 1)
                    return {**resolved_deep, **merged}
            
            result = {}
            for key, value in schema.items():
                result[key] = self.resolve_all_refs(value, spec, depth)
            return result
        
        elif isinstance(schema, list):
            return [self.resolve_all_refs(item, spec, depth) for item in schema]
        
        return schema
    
    def simplify_schema_for_outlines(self, schema: Dict) -> Dict:
        """Remove OpenAPI-specific fields for Outlines compatibility"""
        simplified = {}
        
        openapi_only_fields = {'example', 'examples', 'xml', 'externalDocs', 
                               'deprecated', 'x-node_available_in', 'x-node_unavailable_in',
                               'readOnly', 'writeOnly', 'nullable'}
        
        for key, value in schema.items():
            if key in openapi_only_fields:
                continue
            
            if isinstance(value, dict):
                simplified[key] = self.simplify_schema_for_outlines(value)
            elif isinstance(value, list):
                simplified[key] = [
                    self.simplify_schema_for_outlines(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                simplified[key] = value
        
        return simplified
    
    def convert_to_json_schema_draft7(self, openapi_schema: Dict, action_name: str, software: str) -> Dict:
        """Convert OpenAPI schema to JSON Schema Draft 7"""
        json_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{action_name} API Request ({software.upper()})",
            "description": f"Schema for {action_name} - extracted from {software} OpenAPI spec",
            "type": "object"
        }
        
        if 'properties' in openapi_schema:
            json_schema['properties'] = openapi_schema['properties']
        
        if 'required' in openapi_schema:
            json_schema['required'] = openapi_schema['required']
        
        if 'description' in openapi_schema:
            json_schema['description'] = openapi_schema['description']
        
        json_schema['additionalProperties'] = openapi_schema.get('additionalProperties', False)
        
        return json_schema
    
    def convert_action_for_software(self, action_name: str, software: str, 
                                    config: Dict) -> Tuple[bool, str]:
        """
        Convert a single action for a specific software.
        Returns (success, error_message)
        """
        # Normalize software name
        normalized_software = 'zohobooks' if software in ['zohobooks', 'zoho-books'] else 'quickbooks'
        
        spec_file = config['spec_file']
        schema_path = config['schema_path']
        
        # Load OpenAPI spec
        spec = self.load_openapi_spec(spec_file)
        if not spec:
            return False, f"Spec file not found: {spec_file}"
        
        # Extract request schema
        openapi_schema = self.extract_schema_from_path(spec, schema_path)
        if not openapi_schema:
            return False, f"Schema path not found: {schema_path}"
        
        # Resolve all $ref pointers
        resolved_schema = self.resolve_all_refs(openapi_schema, spec)
        
        # Convert to JSON Schema Draft 7
        json_schema = self.convert_to_json_schema_draft7(resolved_schema, action_name, normalized_software)
        
        # Simplify for Outlines
        simplified_schema = self.simplify_schema_for_outlines(json_schema)
        
        # Save to file
        output_dir = self.gpu_root / 'schemas' / 'stage_4' / 'actions' / normalized_software
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{action_name}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(simplified_schema, f, indent=2, ensure_ascii=False)
            return True, ""
        except Exception as e:
            return False, f"Failed to save: {e}"
    
    def convert_all_actions_batch(self, batch_size: int = 50) -> Dict[str, Any]:
        """
        Convert all actions in batches to avoid memory issues.
        Returns detailed conversion report.
        """
        # Extract action map from backend
        self.action_map = self.extract_action_map_from_backend()
        
        if not self.action_map:
            logger.error("❌ No actions found in apiSchemaLoader.ts")
            return {}
        
        total_actions = len(self.action_map)
        logger.info(f"\n{'='*80}")
        logger.info(f"COMPREHENSIVE SCHEMA CONVERSION")
        logger.info(f"Total Actions: {total_actions}")
        logger.info(f"Target Software: QuickBooks + Zoho Books")
        logger.info(f"{'='*80}\n")
        
        results = {
            'zohobooks': {'success': [], 'failed': []},
            'quickbooks': {'success': [], 'failed': []}
        }
        
        action_items = list(self.action_map.items())
        total_conversions = 0
        
        for i in range(0, len(action_items), batch_size):
            batch = action_items[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(action_items) + batch_size - 1) // batch_size
            
            logger.info(f"\n{'='*80}")
            logger.info(f"BATCH {batch_num}/{total_batches} (Actions {i+1}-{min(i+batch_size, len(action_items))})")
            logger.info(f"{'='*80}")
            
            for action_name, software_configs in batch:
                logger.info(f"\n--- {action_name} ---")
                
                for software, config in software_configs.items():
                    normalized_software = 'zohobooks' if software in ['zohobooks', 'zoho-books'] else 'quickbooks'
                    
                    success, error = self.convert_action_for_software(action_name, software, config)
                    total_conversions += 1
                    
                    if success:
                        results[normalized_software]['success'].append(action_name)
                        logger.info(f"  ✅ {normalized_software}: {action_name}")
                    else:
                        results[normalized_software]['failed'].append((action_name, error))
                        logger.warning(f"  ❌ {normalized_software}: {action_name} - {error}")
            
            # Clear spec cache after each batch to free memory
            self.schema_cache.clear()
            
            logger.info(f"\nBatch {batch_num} complete. Progress: {min(i+batch_size, len(action_items))}/{len(action_items)} actions")
        
        # Print final summary
        self._print_summary(results, total_actions)
        
        return results
    
    def _print_summary(self, results: Dict, total_actions: int):
        """Print detailed conversion summary"""
        logger.info(f"\n{'='*80}")
        logger.info("FINAL CONVERSION SUMMARY")
        logger.info(f"{'='*80}")
        
        for software in ['zohobooks', 'quickbooks']:
            success_count = len(results[software]['success'])
            failed_count = len(results[software]['failed'])
            total = success_count + failed_count
            success_rate = (success_count / total * 100) if total > 0 else 0
            
            logger.info(f"\n{software.upper()}:")
            logger.info(f"  ✅ Successful: {success_count}/{total} ({success_rate:.1f}%)")
            logger.info(f"  ❌ Failed: {failed_count}/{total}")
            
            if failed_count > 0 and failed_count <= 20:
                logger.info(f"\n  Failed actions:")
                for action, error in results[software]['failed'][:20]:
                    logger.info(f"    - {action}: {error}")
                if failed_count > 20:
                    logger.info(f"    ... and {failed_count - 20} more")
        
        total_success = len(results['zohobooks']['success']) + len(results['quickbooks']['success'])
        total_failed = len(results['zohobooks']['failed']) + len(results['quickbooks']['failed'])
        total_conversions = total_success + total_failed
        
        logger.info(f"\n{'='*80}")
        logger.info(f"OVERALL:")
        logger.info(f"  Total Actions: {total_actions}")
        logger.info(f"  Total Conversions Attempted: {total_conversions}")
        logger.info(f"  ✅ Total Successful: {total_success}")
        logger.info(f"  ❌ Total Failed: {total_failed}")
        logger.info(f"  Success Rate: {(total_success/total_conversions*100):.1f}%")
        logger.info(f"{'='*80}\n")


def main():
    """Main execution"""
    backend_root = r"d:\Desktop\Zopilot\zopilot-backend"
    gpu_root = r"d:\Desktop\Zopilot\ZopilotGPU"
    
    converter = ComprehensiveSchemaConverter(backend_root, gpu_root)
    
    # Convert all actions in batches of 50
    results = converter.convert_all_actions_batch(batch_size=50)
    
    # Exit with appropriate code
    total_failed = len(results['zohobooks']['failed']) + len(results['quickbooks']['failed'])
    exit(0 if total_failed == 0 else 1)


if __name__ == '__main__':
    main()
