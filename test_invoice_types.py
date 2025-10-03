#!/usr/bin/env python3
"""
Test script to check if DocStrange can distinguish between customer and vendor invoices.
"""

import json
from app.docstrange_utils import extract_with_docstrange

def test_customer_vs_vendor_invoice():
    """Test DocStrange's ability to distinguish customer vs vendor invoices."""
    
    # Sample CUSTOMER INVOICE (outgoing - you send to customer)
    customer_invoice = """
    YOUR COMPANY NAME
    123 Your Street
    Your City, State 12345
    
    INVOICE
    
    Invoice Number: INV-2024-001
    Date: 2024-01-15
    
    Bill To:
    ABC Customer Ltd.
    456 Customer Street
    Customer City, NY 10001
    
    Description: Web Development Services
    Amount: $2,500.00
    Tax: $250.00
    Total: $2,750.00
    
    Payment Terms: Net 30
    Due Date: 2024-02-14
    
    Thank you for your business!
    """
    
    # Sample VENDOR INVOICE (incoming - you receive from vendor)
    vendor_invoice = """
    SUPPLIER COMPANY INC.
    789 Vendor Avenue
    Vendor City, CA 90210
    
    INVOICE
    
    Invoice Number: SUPP-2024-005
    Date: 2024-01-20
    
    Bill To:
    YOUR COMPANY NAME
    123 Your Street
    Your City, State 12345
    
    Description: Office Supplies
    Amount: $850.00
    Tax: $85.00
    Total: $935.00
    
    Payment Terms: Due on Receipt
    Due Date: 2024-01-27
    
    Please remit payment promptly.
    """
    
    print("Testing Customer Invoice vs Vendor Invoice Detection")
    print("=" * 60)
    
    # Test customer invoice
    print("\n1. CUSTOMER INVOICE (Outgoing - you send to customer)")
    print("-" * 50)
    customer_content = customer_invoice.encode('utf-8')
    customer_result = extract_with_docstrange(customer_content, "customer_invoice.txt")
    
    print("Structured fields found:")
    customer_fields = customer_result.get('data', {}).get('structured_fields', {})
    for key, value in customer_fields.items():
        if value:
            print(f"  - {key}: {value}")
    
    # Check for direction indicators
    print(f"\nDirection Analysis:")
    print(f"  Bill To: {customer_fields.get('bill_to', 'Not found')}")
    print(f"  Customer Name: {customer_fields.get('customer_name', 'Not found')}")
    print(f"  Vendor Name: {customer_fields.get('vendor_name', 'Not found')}")
    
    # Test vendor invoice
    print("\n\n2. VENDOR INVOICE (Incoming - you receive from vendor)")
    print("-" * 50)
    vendor_content = vendor_invoice.encode('utf-8')
    vendor_result = extract_with_docstrange(vendor_content, "vendor_invoice.txt")
    
    print("Structured fields found:")
    vendor_fields = vendor_result.get('data', {}).get('structured_fields', {})
    for key, value in vendor_fields.items():
        if value:
            print(f"  - {key}: {value}")
    
    # Check for direction indicators
    print(f"\nDirection Analysis:")
    print(f"  Bill To: {vendor_fields.get('bill_to', 'Not found')}")
    print(f"  Customer Name: {vendor_fields.get('customer_name', 'Not found')}")
    print(f"  Vendor Name: {vendor_fields.get('vendor_name', 'Not found')}")
    
    # Analysis
    print("\n\n3. ANALYSIS")
    print("-" * 50)
    
    # Compare bill_to fields
    customer_bill_to = str(customer_fields.get('bill_to', '')).lower()
    vendor_bill_to = str(vendor_fields.get('bill_to', '')).lower()
    
    print(f"Customer Invoice - Bill To contains 'abc customer': {'abc customer' in customer_bill_to}")
    print(f"Vendor Invoice - Bill To contains 'your company': {'your company' in vendor_bill_to}")
    
    # Check if we can determine direction
    customer_is_outgoing = 'abc customer' in customer_bill_to or 'customer' in customer_bill_to
    vendor_is_incoming = 'your company' in vendor_bill_to or 'your' in vendor_bill_to
    
    print(f"\nDirection Detection:")
    print(f"  Customer Invoice detected as OUTGOING: {customer_is_outgoing}")
    print(f"  Vendor Invoice detected as INCOMING: {vendor_is_incoming}")
    
    return {
        'customer_result': customer_result,
        'vendor_result': vendor_result,
        'can_distinguish': customer_is_outgoing and vendor_is_incoming
    }

if __name__ == "__main__":
    test_customer_vs_vendor_invoice()