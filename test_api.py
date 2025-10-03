#!/usr/bin/env python3
"""
Test script for EasyAccountsGPU API
Validates all endpoints and functionality
"""

import asyncio
import aiofiles
import httpx
import json
import os
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

async def test_health_endpoint():
    """Test health check endpoint."""
    print("🏥 Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health", timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data['status']}")
                print(f"   Models loaded: {data['models_loaded']}")
                print(f"   GPU available: {data['gpu_available']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {str(e)}")
            return False

async def test_extract_endpoint():
    """Test document extraction endpoint."""
    print("\\n📄 Testing extract endpoint...")
    
    # Create a simple test file
    test_content = """
    INVOICE
    Date: 2025-09-24
    To: ABC Company
    Amount: $150.00
    Description: Office Supplies
    """.strip()
    
    test_file_path = "test_invoice.txt"
    async with aiofiles.open(test_file_path, "w") as f:
        await f.write(test_content)
    
    try:
        async with httpx.AsyncClient() as client:
            with open(test_file_path, "rb") as f:
                files = {"file": ("test_invoice.txt", f, "text/plain")}
                response = await client.post(
                    f"{API_BASE_URL}/extract",
                    files=files,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Extraction successful: {data['extraction_method']}")
                    print(f"   Success: {data['success']}")
                    print(f"   Data keys: {list(data['data'].keys())}")
                    return data
                else:
                    print(f"❌ Extraction failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
    except Exception as e:
        print(f"❌ Extraction error: {str(e)}")
        return None
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

async def test_generate_endpoint(context_data=None):
    """Test journal entry generation endpoint."""
    print("\\n✏️ Testing generate endpoint...")
    
    test_data = {
        "prompt": "Generate a journal entry for office supplies purchase",
        "context": context_data or {
            "amount": 150.00,
            "vendor": "Office Depot",
            "date": "2025-09-24",
            "description": "Office Supplies"
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/generate",
                json=test_data,
                timeout=120.0  # Longer timeout for generation
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Generation successful")
                print(f"   Success: {data['success']}")
                if data['success']:
                    journal = data['journal_entry']
                    print(f"   Date: {journal.get('date', 'N/A')}")
                    print(f"   Description: {journal.get('description', 'N/A')}")
                    print(f"   Debits: {len(journal.get('account_debits', []))}")
                    print(f"   Credits: {len(journal.get('account_credits', []))}")
                    print(f"   Total Debit: ${journal.get('total_debit', 0):.2f}")
                    print(f"   Total Credit: ${journal.get('total_credit', 0):.2f}")
                return data
            else:
                print(f"❌ Generation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
    except Exception as e:
        print(f"❌ Generation error: {str(e)}")
        return None

async def test_process_endpoint():
    """Test combined process endpoint."""
    print("\\n🔄 Testing process endpoint...")
    
    # Create a test document
    test_content = """
    RECEIPT
    Store: Office Max
    Date: September 24, 2025
    Item: Printer Paper - $25.00
    Item: Pens - $15.00
    Item: Stapler - $12.50
    Tax: $4.20
    Total: $56.70
    Payment: Credit Card
    """.strip()
    
    test_file_path = "test_receipt.txt"
    async with aiofiles.open(test_file_path, "w") as f:
        await f.write(test_content)
    
    try:
        async with httpx.AsyncClient() as client:
            with open(test_file_path, "rb") as f:
                files = {"file": ("test_receipt.txt", f, "text/plain")}
                data = {"prompt": "Create a journal entry for this receipt"}
                
                response = await client.post(
                    f"{API_BASE_URL}/process",
                    files=files,
                    data=data,
                    timeout=180.0  # Long timeout for full processing
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Processing successful")
                    print(f"   Overall success: {result['success']}")
                    
                    if 'extraction' in result:
                        ext = result['extraction']
                        print(f"   Extraction method: {ext['extraction_method']}")
                        print(f"   Extraction success: {ext['success']}")
                    
                    if 'generation' in result:
                        gen = result['generation']
                        print(f"   Generation success: {gen['success']}")
                        if gen['success']:
                            journal = gen['journal_entry']
                            print(f"   Generated journal total: ${journal.get('total_debit', 0):.2f}")
                    
                    return result
                else:
                    print(f"❌ Processing failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
    except Exception as e:
        print(f"❌ Processing error: {str(e)}")
        return None
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

async def main():
    """Run all tests."""
    print("🚀 Starting EasyAccountsGPU API Tests")
    print(f"Testing API at: {API_BASE_URL}")
    print("=" * 50)
    
    # Test health endpoint
    health_ok = await test_health_endpoint()
    if not health_ok:
        print("❌ Health check failed - stopping tests")
        return
    
    # Test extraction
    extraction_result = await test_extract_endpoint()
    
    # Test generation (with extracted context if available)
    context = extraction_result.get('data') if extraction_result else None
    generation_result = await test_generate_endpoint(context)
    
    # Test combined processing
    process_result = await test_process_endpoint()
    
    # Summary
    print("\\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Health Check: {'✅ Pass' if health_ok else '❌ Fail'}")
    print(f"   Extraction: {'✅ Pass' if extraction_result else '❌ Fail'}")
    print(f"   Generation: {'✅ Pass' if generation_result else '❌ Fail'}")
    print(f"   Processing: {'✅ Pass' if process_result else '❌ Fail'}")
    
    if all([health_ok, extraction_result, generation_result, process_result]):
        print("\\n🎉 All tests passed! API is ready for production.")
    else:
        print("\\n⚠️  Some tests failed. Check the logs above.")

if __name__ == "__main__":
    # Allow customizing the API URL
    if len(os.sys.argv) > 1:
        API_BASE_URL = os.sys.argv[1]
    
    print(f"Using API URL: {API_BASE_URL}")
    asyncio.run(main())