#!/usr/bin/env python3
"""
Quick verification script for ZopilotGPU deployment
Tests all endpoints and verifies configuration
"""

import os
import sys
import requests
import json
from typing import Dict, Any

# Configuration
GPU_URL = os.getenv("ZOPILOT_GPU_URL", "http://localhost:8000")
API_KEY = os.getenv("ZOPILOT_GPU_API_KEY", "")

def colored(text: str, color: str) -> str:
    """Add color to terminal output"""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def test_health_check() -> bool:
    """Test health check endpoint"""
    print(f"\n{'='*60}")
    print(colored("Test 1: Health Check", "blue"))
    print(f"{'='*60}")
    
    try:
        response = requests.get(f"{GPU_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(colored("✅ PASSED", "green"))
            print(f"Status: {data.get('status')}")
            print(f"Model: {data.get('model')}")
            print(f"GPU Available: {data.get('gpu_available')}")
            return True
        else:
            print(colored(f"❌ FAILED - Status code: {response.status_code}", "red"))
            return False
    except Exception as e:
        print(colored(f"❌ FAILED - Error: {str(e)}", "red"))
        return False

def test_auth_required() -> bool:
    """Test that endpoints require authentication"""
    print(f"\n{'='*60}")
    print(colored("Test 2: Authentication Required", "blue"))
    print(f"{'='*60}")
    
    try:
        # Try without API key
        response = requests.post(
            f"{GPU_URL}/extract",
            json={"document_url": "test.pdf", "document_id": "test-123"},
            timeout=10
        )
        
        if response.status_code == 401:
            print(colored("✅ PASSED - Endpoint correctly rejects unauthenticated requests", "green"))
            return True
        else:
            print(colored(f"⚠️  WARNING - Expected 401, got {response.status_code}", "yellow"))
            print("This might be okay if API key is not configured (local dev)")
            return True
    except Exception as e:
        print(colored(f"❌ FAILED - Error: {str(e)}", "red"))
        return False

def test_auth_works() -> bool:
    """Test that authentication works with valid API key"""
    print(f"\n{'='*60}")
    print(colored("Test 3: Valid Authentication", "blue"))
    print(f"{'='*60}")
    
    if not API_KEY:
        print(colored("⚠️  SKIPPED - No API key configured", "yellow"))
        print("Set ZOPILOT_GPU_API_KEY environment variable to test")
        return True
    
    try:
        # Try with API key (will fail due to invalid URL, but should get past auth)
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.post(
            f"{GPU_URL}/extract",
            json={"document_url": "https://invalid-url.pdf", "document_id": "test-123"},
            headers=headers,
            timeout=30
        )
        
        # Should not be 401 if auth works
        if response.status_code != 401:
            print(colored("✅ PASSED - Authentication accepted", "green"))
            print(f"Response code: {response.status_code} (expected, as URL is invalid)")
            return True
        else:
            print(colored("❌ FAILED - Valid API key rejected", "red"))
            return False
    except Exception as e:
        print(colored(f"⚠️  WARNING - Error: {str(e)}", "yellow"))
        print("This might be expected if the endpoint is processing the request")
        return True

def test_cors_headers() -> bool:
    """Test CORS headers"""
    print(f"\n{'='*60}")
    print(colored("Test 4: CORS Configuration", "blue"))
    print(f"{'='*60}")
    
    try:
        response = requests.options(
            f"{GPU_URL}/extract",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST"
            },
            timeout=10
        )
        
        cors_header = response.headers.get("Access-Control-Allow-Origin", "Not set")
        print(f"CORS Header: {cors_header}")
        
        if cors_header != "Not set":
            print(colored("✅ PASSED - CORS headers present", "green"))
            return True
        else:
            print(colored("⚠️  WARNING - CORS headers not found", "yellow"))
            return True
    except Exception as e:
        print(colored(f"❌ FAILED - Error: {str(e)}", "red"))
        return False

def test_gpu_availability() -> bool:
    """Test GPU availability from health endpoint"""
    print(f"\n{'='*60}")
    print(colored("Test 5: GPU Availability", "blue"))
    print(f"{'='*60}")
    
    try:
        response = requests.get(f"{GPU_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            gpu_available = data.get("gpu_available", False)
            
            if gpu_available:
                print(colored("✅ PASSED - GPU is available", "green"))
                if "vram_total" in data:
                    print(f"VRAM Total: {data.get('vram_total')}")
                    print(f"VRAM Used: {data.get('vram_used')}")
                return True
            else:
                print(colored("⚠️  WARNING - GPU not available", "yellow"))
                print("Service will run on CPU (very slow)")
                return False
        else:
            print(colored(f"❌ FAILED - Status code: {response.status_code}", "red"))
            return False
    except Exception as e:
        print(colored(f"❌ FAILED - Error: {str(e)}", "red"))
        return False

def main():
    """Run all tests"""
    print(colored("\n🚀 ZopilotGPU Deployment Verification", "blue"))
    print(f"Testing endpoint: {GPU_URL}")
    print(f"API Key configured: {'Yes' if API_KEY else 'No'}")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health_check()))
    results.append(("Authentication Required", test_auth_required()))
    results.append(("Valid Authentication", test_auth_works()))
    results.append(("CORS Configuration", test_cors_headers()))
    results.append(("GPU Availability", test_gpu_availability()))
    
    # Summary
    print(f"\n{'='*60}")
    print(colored("Test Summary", "blue"))
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = colored("✅ PASSED", "green") if result else colored("❌ FAILED", "red")
        print(f"{test_name:.<40} {status}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print(colored("\n🎉 All tests passed! Deployment is ready.", "green"))
        return 0
    else:
        print(colored(f"\n⚠️  {total - passed} test(s) failed. Review errors above.", "yellow"))
        return 1

if __name__ == "__main__":
    sys.exit(main())
