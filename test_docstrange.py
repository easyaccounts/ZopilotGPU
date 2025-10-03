#!/usr/bin/env python3
"""
Test script to validate the updated DocStrange implementation against official API patterns.
"""

import json
from app.docstrange_utils import extract_with_docstrange

def test_docstrange_extraction():
    """Test document extraction with sample content."""
    
    # Create a sample invoice-like content as bytes
    sample_invoice = """
    INVOICE
    
    Invoice Number: INV-2024-001
    Date: 2024-01-15
    
    Bill To:
    ABC Company Ltd.
    123 Business Street
    New York, NY 10001
    
    Description: Consulting Services
    Amount: $1,500.00
    Tax: $150.00
    Total: $1,650.00
    
    Payment Terms: Net 30
    Due Date: 2024-02-14
    """
    
    # Convert to bytes
    file_content = sample_invoice.encode('utf-8')
    
    # Test extraction
    print("Testing DocStrange extraction with sample invoice...")
    result = extract_with_docstrange(file_content, "sample_invoice.txt")
    
    print("\nExtraction Result:")
    print("=" * 50)
    print(json.dumps(result, indent=2, default=str))
    
    # Validate result structure
    print("\nValidation:")
    print("=" * 50)
    print(f"Success: {result.get('success', False)}")
    print(f"Method: {result.get('extraction_method', 'unknown')}")
    
    # Check structured fields
    structured_fields = result.get('data', {}).get('structured_fields', {})
    if structured_fields:
        print(f"Structured fields found: {len([v for v in structured_fields.values() if v])}")
        print("Fields extracted:")
        for key, value in structured_fields.items():
            if value:
                print(f"  - {key}: {value}")
    
    # Check processing mode
    metadata = result.get('metadata', {})
    processing_mode = metadata.get('processing_mode', 'unknown')
    print(f"Processing mode: {processing_mode}")
    
    return result

if __name__ == "__main__":
    test_docstrange_extraction()