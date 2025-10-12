"""
Final validation: Check if ZopilotGPU files can be imported without errors
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("FINAL VALIDATION: ZopilotGPU LLM-Only Service")
print("=" * 70)

errors = []

# Test 1: Check handler.py can be parsed
print("\n1. Checking handler.py syntax...")
try:
    with open('handler.py', 'r', encoding='utf-8') as f:
        compile(f.read(), 'handler.py', 'exec')
    print("   ✅ handler.py: No syntax errors")
except SyntaxError as e:
    errors.append(f"handler.py: {e}")
    print(f"   ❌ handler.py: Syntax error at line {e.lineno}: {e.msg}")

# Test 2: Check app/main.py can be parsed
print("\n2. Checking app/main.py syntax...")
try:
    with open('app/main.py', 'r', encoding='utf-8') as f:
        compile(f.read(), 'app/main.py', 'exec')
    print("   ✅ app/main.py: No syntax errors")
except SyntaxError as e:
    errors.append(f"app/main.py: {e}")
    print(f"   ❌ app/main.py: Syntax error at line {e.lineno}: {e.msg}")

# Test 3: Check for removed dependencies
print("\n3. Checking removed OCR dependencies...")
with open('handler.py', 'r') as f:
    handler_content = f.read()
with open('app/main.py', 'r') as f:
    main_content = f.read()

bad_imports = []
if 'docstrange_utils' in handler_content or 'docstrange_utils' in main_content:
    bad_imports.append("docstrange_utils still imported")
if 'from app.docstrange_utils' in main_content:
    bad_imports.append("app.docstrange_utils import still exists")
if 'ExtractionInput' in handler_content.split('# Configure logging')[0]:  # Only check imports section
    bad_imports.append("ExtractionInput still imported in handler.py")

if bad_imports:
    for imp in bad_imports:
        print(f"   ❌ {imp}")
        errors.append(imp)
else:
    print("   ✅ No OCR imports found")

# Test 4: Check for required LLM dependencies
print("\n4. Checking LLM dependencies are present...")
if 'from app.llama_utils import' in main_content:
    print("   ✅ llama_utils imported")
else:
    print("   ❌ llama_utils NOT imported")
    errors.append("llama_utils not imported")

if 'PromptInput' in handler_content:
    print("   ✅ PromptInput model present")
else:
    print("   ❌ PromptInput NOT found")
    errors.append("PromptInput not found")

# Test 5: Check endpoints
print("\n5. Checking endpoint configuration...")
if "if endpoint == '/prompt':" in handler_content:
    print("   ✅ /prompt endpoint present")
else:
    print("   ❌ /prompt endpoint NOT found")
    errors.append("/prompt endpoint not found")

if "if endpoint == '/extract':" in handler_content:
    print("   ❌ /extract endpoint still present (should be removed)")
    errors.append("/extract endpoint still exists")
else:
    print("   ✅ /extract endpoint removed")

# Final summary
print("\n" + "=" * 70)
if errors:
    print(f"❌ VALIDATION FAILED: {len(errors)} error(s) found")
    print("\nErrors:")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
else:
    print("✅ ALL VALIDATIONS PASSED")
    print("\nZopilotGPU is ready for LLM-only deployment on RTX 5090!")
    print("=" * 70)
