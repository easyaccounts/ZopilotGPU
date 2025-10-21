"""
OpenAPI to Outlines JSON Schema Converter

This script converts OpenAPI 3.0 YAML schemas to JSON Schema Draft 7 format
optimized for Outlines grammar-constrained generation.

Purpose:
- Extract request schemas from OpenAPI specs for QuickBooks and Zoho Books
- Convert to JSON Schema format compatible with Outlines library
- Generate action-specific schemas for Stage 4 field mapping
- Maintain field descriptions, types, and validation rules

Output:
- schemas/stage_4/actions/{software}/{action_name}.json

Usage:
    python scripts/convert_openapi_to_outlines_schemas.py
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# ACTION TO SCHEMA MAPPING
# Maps Zopilot action names to OpenAPI spec locations
# ============================================================================

ACTION_MAP = {
    # Invoices
    'create_invoice': {
        'zohobooks': {
            'spec_file': 'openapi-all/invoices.yml',
            'schema_path': 'components.schemas.create-an-invoice-request',
            'endpoint': 'POST /invoices'
        }
    },
    'update_invoice': {
        'zohobooks': {
            'spec_file': 'openapi-all/invoices.yml',
            'schema_path': 'components.schemas.update-an-invoice-request',
            'endpoint': 'PUT /invoices/{invoice_id}'
        }
    },
    
    # Bills
    'create_bill': {
        'zohobooks': {
            'spec_file': 'openapi-all/bills.yml',
            'schema_path': 'components.schemas.create-a-bill-request',
            'endpoint': 'POST /bills'
        }
    },
    'update_bill': {
        'zohobooks': {
            'spec_file': 'openapi-all/bills.yml',
            'schema_path': 'components.schemas.update-a-bill-request',
            'endpoint': 'PUT /bills/{bill_id}'
        }
    },
    
    # Expenses
    'create_expense': {
        'zohobooks': {
            'spec_file': 'openapi-all/expenses.yml',
            'schema_path': 'components.schemas.create-an-expense-request',
            'endpoint': 'POST /expenses'
        }
    },
    'update_expense': {
        'zohobooks': {
            'spec_file': 'openapi-all/expenses.yml',
            'schema_path': 'components.schemas.update-an-expense-request',
            'endpoint': 'PUT /expenses/{expense_id}'
        }
    },
    
    # Credit Notes
    'create_credit_note': {
        'zohobooks': {
            'spec_file': 'openapi-all/credit-notes.yml',
            'schema_path': 'components.schemas.create-a-credit-note-request',
            'endpoint': 'POST /creditnotes'
        }
    },
    
    # Vendor Credits
    'create_vendor_credit': {
        'zohobooks': {
            'spec_file': 'openapi-all/vendor-credits.yml',
            'schema_path': 'components.schemas.create-a-vendor-credit-request',
            'endpoint': 'POST /vendorcredits'
        }
    },
    
    # Customer Payments
    'record_customer_payment': {
        'zohobooks': {
            'spec_file': 'openapi-all/customer-payments.yml',
            'schema_path': 'components.schemas.create-a-payment-request',
            'endpoint': 'POST /customerpayments'
        }
    },
    
    # Vendor Payments
    'record_vendor_payment': {
        'zohobooks': {
            'spec_file': 'openapi-all/vendor-payments.yml',
            'schema_path': 'components.schemas.create-a-vendor-payment-request',
            'endpoint': 'POST /vendorpayments'
        }
    },
    
    # Contacts
    'create_contact': {
        'zohobooks': {
            'spec_file': 'openapi-all/contacts.yml',
            'schema_path': 'components.schemas.create-a-contact-request',
            'endpoint': 'POST /contacts'
        }
    },
    'update_contact': {
        'zohobooks': {
            'spec_file': 'openapi-all/contacts.yml',
            'schema_path': 'components.schemas.update-a-contact-request',
            'endpoint': 'PUT /contacts/{contact_id}'
        }
    },
    
    # Items
    'create_item': {
        'zohobooks': {
            'spec_file': 'openapi-all/items.yml',
            'schema_path': 'components.schemas.create-an-item-request',
            'endpoint': 'POST /items'
        }
    },
    'update_item': {
        'zohobooks': {
            'spec_file': 'openapi-all/items.yml',
            'schema_path': 'components.schemas.update-an-item-request',
            'endpoint': 'PUT /items/{item_id}'
        }
    },
    
    # Purchase Orders
    'create_purchase_order': {
        'zohobooks': {
            'spec_file': 'openapi-all/purchase-order.yml',
            'schema_path': 'components.schemas.create-a-purchase-order-request',
            'endpoint': 'POST /purchaseorders'
        }
    },
    
    # Sales Orders
    'create_sales_order': {
        'zohobooks': {
            'spec_file': 'openapi-all/sales-order.yml',
            'schema_path': 'components.schemas.create-a-sales-order-request',
            'endpoint': 'POST /salesorders'
        }
    },
    
    # Estimates
    'create_estimate': {
        'zohobooks': {
            'spec_file': 'openapi-all/estimates.yml',
            'schema_path': 'components.schemas.create-an-estimate-request',
            'endpoint': 'POST /estimates'
        }
    },
    
    # Chart of Accounts
    'create_account': {
        'zohobooks': {
            'spec_file': 'openapi-all/chart-of-accounts.yml',
            'schema_path': 'components.schemas.create-an-account-request',
            'endpoint': 'POST /chartofaccounts'
        }
    },
    
    # Projects
    'create_project': {
        'zohobooks': {
            'spec_file': 'openapi-all/projects.yml',
            'schema_path': 'components.schemas.create-a-project-request',
            'endpoint': 'POST /projects'
        }
    },
    
    # Journal Entries
    'create_journal': {
        'zohobooks': {
            'spec_file': 'openapi-all/journals.yml',
            'schema_path': 'components.schemas.create-a-journal-request',
            'endpoint': 'POST /journals'
        }
    },
}


class OpenAPIToOutlinesConverter:
    """Converts OpenAPI schemas to Outlines-compatible JSON Schema"""
    
    def __init__(self, backend_root: str, gpu_root: str):
        self.backend_root = Path(backend_root)
        self.gpu_root = Path(gpu_root)
        self.schema_cache: Dict[str, Any] = {}
        
    def load_openapi_spec(self, spec_file: str) -> Optional[Dict]:
        """Load and parse an OpenAPI YAML file"""
        spec_path = self.backend_root / spec_file
        
        if not spec_path.exists():
            logger.error(f"❌ Spec file not found: {spec_path}")
            return None
        
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
            logger.info(f"✅ Loaded OpenAPI spec: {spec_file}")
            return spec
        except Exception as e:
            logger.error(f"❌ Failed to load {spec_file}: {e}")
            return None
    
    def resolve_schema_ref(self, spec: Dict, ref_path: str) -> Optional[Dict]:
        """Resolve $ref pointers in OpenAPI schema"""
        if not ref_path.startswith('#/'):
            logger.warning(f"⚠️  Cannot resolve external ref: {ref_path}")
            return None
        
        # Remove leading '#/' and split by '.'
        path_parts = ref_path[2:].replace('/', '.').split('.')
        
        # Navigate through spec
        current = spec
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                logger.warning(f"⚠️  Cannot resolve ref path: {ref_path}")
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
                logger.error(f"❌ Schema path not found: {schema_path}")
                return None
        
        return current
    
    def resolve_all_refs(self, schema: Any, spec: Dict, depth: int = 0) -> Any:
        """Recursively resolve all $ref pointers in a schema"""
        if depth > 10:  # Prevent infinite recursion
            logger.warning("⚠️  Max ref resolution depth reached")
            return schema
        
        if isinstance(schema, dict):
            # Handle $ref
            if '$ref' in schema:
                ref_path = schema['$ref']
                resolved = self.resolve_schema_ref(spec, ref_path)
                if resolved:
                    # Merge other properties (like description) that might exist alongside $ref
                    merged = {**schema}
                    del merged['$ref']
                    resolved_deep = self.resolve_all_refs(resolved, spec, depth + 1)
                    return {**resolved_deep, **merged}
                else:
                    return schema
            
            # Recurse into nested schemas
            result = {}
            for key, value in schema.items():
                result[key] = self.resolve_all_refs(value, spec, depth)
            return result
        
        elif isinstance(schema, list):
            return [self.resolve_all_refs(item, spec, depth) for item in schema]
        
        else:
            return schema
    
    def convert_to_json_schema_draft7(self, openapi_schema: Dict, action_name: str) -> Dict:
        """Convert OpenAPI schema to JSON Schema Draft 7 for Outlines"""
        
        # Start with JSON Schema Draft 7 base
        json_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{action_name} API Request Body",
            "description": f"JSON Schema for {action_name} action - extracted from OpenAPI spec",
            "type": "object"
        }
        
        # Copy over properties
        if 'properties' in openapi_schema:
            json_schema['properties'] = openapi_schema['properties']
        
        # Copy over required fields
        if 'required' in openapi_schema:
            json_schema['required'] = openapi_schema['required']
        
        # Copy over description if present
        if 'description' in openapi_schema:
            json_schema['description'] = openapi_schema['description']
        
        # Handle additionalProperties (Outlines needs this explicit)
        if 'additionalProperties' in openapi_schema:
            json_schema['additionalProperties'] = openapi_schema['additionalProperties']
        else:
            # Default to false for strict validation
            json_schema['additionalProperties'] = False
        
        return json_schema
    
    def simplify_schema_for_outlines(self, schema: Dict) -> Dict:
        """Simplify schema to make it more compatible with Outlines"""
        
        simplified = {}
        
        # Remove OpenAPI-specific fields not supported by JSON Schema Draft 7
        openapi_only_fields = ['example', 'examples', 'xml', 'externalDocs', 
                               'deprecated', 'x-node_available_in', 'x-node_unavailable_in']
        
        for key, value in schema.items():
            if key in openapi_only_fields:
                continue  # Skip OpenAPI-only fields
            
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
    
    def convert_action(self, action_name: str, software: str) -> bool:
        """Convert a single action's schema"""
        
        if action_name not in ACTION_MAP:
            logger.warning(f"⚠️  Action {action_name} not in ACTION_MAP")
            return False
        
        if software not in ACTION_MAP[action_name]:
            logger.warning(f"⚠️  Software {software} not supported for {action_name}")
            return False
        
        config = ACTION_MAP[action_name][software]
        
        # Load OpenAPI spec
        spec = self.load_openapi_spec(config['spec_file'])
        if not spec:
            return False
        
        # Extract request schema
        openapi_schema = self.extract_schema_from_path(spec, config['schema_path'])
        if not openapi_schema:
            return False
        
        # Resolve all $ref pointers
        logger.info(f"🔄 Resolving references for {action_name}...")
        resolved_schema = self.resolve_all_refs(openapi_schema, spec)
        
        # Convert to JSON Schema Draft 7
        json_schema = self.convert_to_json_schema_draft7(resolved_schema, action_name)
        
        # Simplify for Outlines compatibility
        simplified_schema = self.simplify_schema_for_outlines(json_schema)
        
        # Save to file
        output_dir = self.gpu_root / 'schemas' / 'stage_4' / 'actions' / software
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{action_name}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(simplified_schema, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Created schema: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to save schema for {action_name}: {e}")
            return False
    
    def convert_all_actions(self, software: str = 'zohobooks') -> Dict[str, bool]:
        """Convert all actions for a given software"""
        
        results = {}
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Converting OpenAPI schemas to Outlines JSON Schema for {software.upper()}")
        logger.info(f"{'='*80}\n")
        
        for action_name in ACTION_MAP.keys():
            logger.info(f"\n--- Processing: {action_name} ---")
            results[action_name] = self.convert_action(action_name, software)
        
        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info("CONVERSION SUMMARY")
        logger.info(f"{'='*80}")
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        logger.info(f"✅ Successful: {successful}/{total}")
        logger.info(f"❌ Failed: {total - successful}/{total}")
        
        if total - successful > 0:
            logger.info("\nFailed actions:")
            for action, success in results.items():
                if not success:
                    logger.info(f"  - {action}")
        
        return results


def main():
    """Main execution"""
    
    # Paths
    backend_root = r"d:\Desktop\Zopilot\zopilot-backend"
    gpu_root = r"d:\Desktop\Zopilot\ZopilotGPU"
    
    # Initialize converter
    converter = OpenAPIToOutlinesConverter(backend_root, gpu_root)
    
    # Convert Zoho Books schemas (primary software)
    results = converter.convert_all_actions(software='zohobooks')
    
    # Exit with appropriate code
    failed_count = sum(1 for success in results.values() if not success)
    exit(0 if failed_count == 0 else 1)


if __name__ == '__main__':
    main()
