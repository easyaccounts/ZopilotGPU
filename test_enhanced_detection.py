#!/usr/bin/env python3
"""
Test enhanced invoice direction detection with the updated DocStrange processor.
"""

import json
from app.docstrange_utils import extract_with_docstrange

def test_enhanced_invoice_detection():
    """Test the enhanced invoice direction detection."""
    
    # Sample invoices with clear direction indicators
    test_cases = [
        {
            'name': 'Customer Invoice (Outgoing)',
            'content': """
            EasyAccounts LLC
            123 Business St
            
            INVOICE #INV-001
            Date: 2024-01-15
            
            Bill To:
            Customer Company Inc.
            456 Customer Ave
            
            Services: $1,000.00
            Total: $1,000.00
            """,
            'expected_direction': 'outgoing'
        },
        {
            'name': 'Vendor Invoice (Incoming)',
            'content': """
            Supplier Corp
            789 Vendor Lane
            
            INVOICE #SUPP-001
            Date: 2024-01-15
            
            Bill To:
            EasyAccounts LLC
            123 Business St
            
            Office Supplies: $500.00
            Total: $500.00
            """,
            'expected_direction': 'incoming'
        },
        {
            'name': 'Generic Company (Unknown)',
            'content': """
            Generic Company
            999 Unknown St
            
            INVOICE #GEN-001
            Date: 2024-01-15
            
            Bill To:
            Some Other Company
            111 Other Ave
            
            Products: $750.00
            Total: $750.00
            """,
            'expected_direction': 'unknown'
        }
    ]
    
    print("Enhanced Invoice Direction Detection Test")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 50)
        
        # Process with enhanced detection
        content = test_case['content'].encode('utf-8')
        result = extract_with_docstrange(content, f"test_invoice_{i}.txt")
        
        # Get classification results
        classification = result.get('data', {}).get('invoice_classification', {})
        structured_fields = result.get('data', {}).get('structured_fields', {})
        
        print(f"Expected Direction: {test_case['expected_direction']}")
        print(f"Detected Direction: {classification.get('direction', 'unknown')}")
        print(f"Confidence: {classification.get('confidence', 0.0):.1f}")
        print(f"Description: {classification.get('description', 'N/A')}")
        print(f"Accounting Impact: {classification.get('accounting_impact', 'N/A')}")
        
        # Show key extracted fields
        print(f"\nKey Fields Extracted:")
        key_fields = ['bill_to', 'customer_name', 'vendor_name', 'supplier', 'total_amount']
        for field in key_fields:
            value = structured_fields.get(field)
            if value:
                print(f"  {field}: {value}")
        
        # Analysis details
        analysis = classification.get('analysis', {})
        if analysis:
            print(f"\nDetection Analysis:")
            print(f"  Bill-to matches company: {analysis.get('bill_to_matches_company', False)}")
            print(f"  Vendor matches company: {analysis.get('vendor_matches_company', False)}")
        
        # Validation
        expected = test_case['expected_direction']
        detected = classification.get('direction', 'unknown')
        status = "✅ CORRECT" if expected == detected else "❌ INCORRECT"
        print(f"\nValidation: {status}")

if __name__ == "__main__":
    test_enhanced_invoice_detection()