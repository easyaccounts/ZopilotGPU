#!/usr/bin/env python3
"""
Warmup script to pre-download models to network volume.
Run this once after deployment to cache models before workers start handling requests.

Usage:
    python warmup_cache.py
    
Or call via HTTP:
    curl -X POST https://your-endpoint.runpod.io/warmup
"""
import os
import sys
import time
from pathlib import Path

def warmup_models():
    """Download and cache all models."""
    print("=" * 80)
    print("🔥 WARMUP: Pre-downloading models to network volume")
    print("=" * 80)
    
    # Check volume exists
    volume_path = Path("/workspace")
    if not volume_path.exists():
        print("⚠️  WARNING: /workspace not found - models will download to container")
        print("   Make sure network volume is mounted!")
    else:
        print(f"✅ Network volume found: {volume_path}")
    
    start_time = time.time()
    
    try:
        # 1. Download Docstrange models
        print("\n" + "=" * 80)
        print("📦 Step 1/2: Downloading Docstrange models (~6GB)")
        print("=" * 80)
        
        from app.docstrange_utils import get_docstrange_processor
        docstrange_start = time.time()
        processor = get_docstrange_processor()
        docstrange_time = time.time() - docstrange_start
        
        print(f"✅ Docstrange models cached in {docstrange_time:.1f}s")
        
        # 2. Download Mixtral model
        print("\n" + "=" * 80)
        print("📦 Step 2/2: Downloading Mixtral 8x7B FP16 model (~93GB)")
        print("   Model will be quantized to 8-bit at load time (~24GB VRAM)")
        print("⏱️  This will take 30-45 minutes depending on network speed...")
        print("=" * 80)
        
        from app.llama_utils import get_llama_processor
        mixtral_start = time.time()
        llama_processor = get_llama_processor()
        mixtral_time = time.time() - mixtral_start
        
        print(f"✅ Mixtral model cached in {mixtral_time/60:.1f} minutes")
        
        # Summary
        total_time = time.time() - start_time
        print("\n" + "=" * 80)
        print("🎉 WARMUP COMPLETE!")
        print("=" * 80)
        print(f"Total time: {total_time/60:.1f} minutes")
        print(f"  - Docstrange: {docstrange_time:.1f}s")
        print(f"  - Mixtral: {mixtral_time/60:.1f} min")
        print("\n✅ All models cached successfully!")
        print("🚀 Workers can now start instantly using cached models")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: Failed to download models")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🔥 Starting model warmup...")
    print("💡 TIP: Run this once after deployment to pre-cache models\n")
    
    success = warmup_models()
    
    if success:
        print("\n✅ SUCCESS: Models are now cached and ready!")
        print("   You can now deploy workers - they will start instantly")
        sys.exit(0)
    else:
        print("\n❌ FAILED: Model warmup encountered errors")
        sys.exit(1)
