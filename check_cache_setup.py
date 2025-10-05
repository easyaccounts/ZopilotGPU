#!/usr/bin/env python3
"""
Diagnostic script to verify model cache setup on RunPod
Run this on your RunPod serverless worker to check cache status
"""
import os
import sys
from pathlib import Path

print("=" * 80)
print("ZOPILOT GPU - CACHE DIAGNOSTIC TOOL")
print("=" * 80)

# 1. Check Environment Variables
print("\n📋 ENVIRONMENT VARIABLES:")
print("-" * 80)
env_vars = {
    'XDG_CACHE_HOME': os.getenv('XDG_CACHE_HOME'),
    'HF_HOME': os.getenv('HF_HOME'),
    'TRANSFORMERS_CACHE': os.getenv('TRANSFORMERS_CACHE'),
    'TORCH_HOME': os.getenv('TORCH_HOME'),
    'HUGGING_FACE_TOKEN': os.getenv('HUGGING_FACE_TOKEN', '')[:20] + '...' if os.getenv('HUGGING_FACE_TOKEN') else 'NOT SET',
}

for key, value in env_vars.items():
    status = "✅" if value and value != 'NOT SET' else "❌"
    print(f"{status} {key:25} = {value}")

# 2. Check /workspace mount
print("\n📁 WORKSPACE MOUNT STATUS:")
print("-" * 80)
workspace = Path("/workspace")
if workspace.exists():
    if workspace.is_dir():
        # Check if writable
        try:
            test_file = workspace / ".diagnostic_test"
            test_file.write_text("test")
            test_file.unlink()
            print(f"✅ /workspace exists and is WRITABLE")
        except Exception as e:
            print(f"⚠️  /workspace exists but NOT WRITABLE: {e}")
    else:
        print(f"❌ /workspace exists but is NOT a directory")
else:
    print(f"❌ /workspace DOES NOT EXIST (Network Volume not mounted!)")
    sys.exit(1)

# 3. Check cache directory structure
print("\n📂 CACHE DIRECTORY STRUCTURE:")
print("-" * 80)

cache_dirs = {
    "DocStrange Models": Path("/workspace/docstrange/models"),
    "DocStrange Root": Path("/workspace/docstrange"),
    "HuggingFace Hub": Path("/workspace/huggingface/hub"),
    "HuggingFace Root": Path("/workspace/huggingface"),
    "Torch Cache": Path("/workspace/torch"),
}

for name, path in cache_dirs.items():
    if path.exists():
        if path.is_dir():
            try:
                # Count files in directory
                file_count = len(list(path.rglob("*")))
                size_mb = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)
                print(f"✅ {name:25} EXISTS - {file_count} items, {size_mb:.1f} MB")
            except Exception as e:
                print(f"✅ {name:25} EXISTS (cannot read: {e})")
        else:
            print(f"⚠️  {name:25} exists but is NOT a directory")
    else:
        print(f"❌ {name:25} NOT FOUND")

# 4. Check for specific model files
print("\n🤖 MODEL FILE CHECK:")
print("-" * 80)

# DocStrange models
docstrange_models = Path("/workspace/docstrange/models")
if docstrange_models.exists():
    model_files = list(docstrange_models.rglob("*.pt")) + list(docstrange_models.rglob("*.bin"))
    if model_files:
        print(f"✅ Found {len(model_files)} DocStrange model files")
        for f in model_files[:3]:  # Show first 3
            print(f"   - {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")
    else:
        print(f"⚠️  DocStrange models directory exists but NO MODEL FILES found")
else:
    print(f"❌ DocStrange models directory not found")

# Mixtral models
mixtral_path = Path("/workspace/huggingface/hub")
if mixtral_path.exists():
    mixtral_dirs = list(mixtral_path.glob("models--mistralai--Mixtral*"))
    if mixtral_dirs:
        print(f"✅ Found Mixtral model cache: {mixtral_dirs[0].name}")
        snapshots = list(mixtral_dirs[0].glob("snapshots/*"))
        if snapshots:
            print(f"   - {len(snapshots)} snapshot(s) available")
    else:
        print(f"⚠️  HuggingFace hub exists but NO MIXTRAL models found")
else:
    print(f"❌ HuggingFace hub directory not found")

# 5. Check XDG_CACHE_HOME resolution
print("\n🔍 PATH RESOLUTION:")
print("-" * 80)
xdg_cache = os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
print(f"XDG_CACHE_HOME resolves to: {xdg_cache}")
print(f"DocStrange will look for models at: {xdg_cache}/docstrange/models")

docstrange_expected = Path(xdg_cache) / "docstrange" / "models"
if docstrange_expected.exists():
    print(f"✅ DocStrange expected path EXISTS")
else:
    print(f"❌ DocStrange expected path DOES NOT EXIST")
    print(f"   This means DocStrange will download models on first use!")

# 6. Summary and Recommendations
print("\n" + "=" * 80)
print("SUMMARY & RECOMMENDATIONS:")
print("=" * 80)

issues = []
warnings = []

if not os.getenv('XDG_CACHE_HOME'):
    issues.append("XDG_CACHE_HOME not set")
if not os.getenv('HF_HOME'):
    issues.append("HF_HOME not set")
if not Path("/workspace").exists():
    issues.append("/workspace not mounted")
if not docstrange_expected.exists():
    warnings.append(f"DocStrange models not found at {docstrange_expected}")
if not mixtral_path.exists() or not list(mixtral_path.glob("models--mistralai--Mixtral*")):
    warnings.append("Mixtral models not found in HuggingFace cache")

if issues:
    print("\n❌ CRITICAL ISSUES:")
    for issue in issues:
        print(f"   - {issue}")
    print("\n   ACTION REQUIRED: Fix environment variables and ensure /workspace is mounted")
elif warnings:
    print("\n⚠️  WARNINGS:")
    for warning in warnings:
        print(f"   - {warning}")
    print("\n   Models will be downloaded on first use (~100GB, 30-45 min)")
else:
    print("\n✅ ALL CHECKS PASSED!")
    print("   Models are cached and ready to use")
    print("   Worker should start quickly without downloading")

print("=" * 80)
