#!/usr/bin/env python3
"""
Initialize models on first startup.
Downloads models to network volume only if not already cached.
"""
import os
import sys
from pathlib import Path

def check_and_download_models():
    """Check if models exist, download if needed."""
    
    # Check if models already exist in volume
    volume_path = Path("/workspace")
    docstrange_path = volume_path / "docstrange" / "models"
    mixtral_path = volume_path / "huggingface" / "hub"
    
    models_exist = (
        docstrange_path.exists() and 
        any(docstrange_path.iterdir()) and
        mixtral_path.exists() and 
        any(mixtral_path.iterdir())
    )
    
    if models_exist:
        print("✅ Models already cached in network volume - skipping download")
        return True
    
    print("📦 Models not found in cache - downloading now...")
    print("⏱️  This will take 20-30 minutes (one-time only)")
    
    try:
        # Download Docstrange models
        print("\n1️⃣ Downloading Docstrange models (~6GB)...")
        from app.docstrange_utils import get_docstrange_processor
        get_docstrange_processor()
        print("✅ Docstrange models downloaded")
        
        # Download Mixtral model
        print("\n2️⃣ Downloading Mixtral 8x7B FP16 model (~93GB)...")
        print("   Model will be quantized to 8-bit at load time (~24GB VRAM)")
        from app.llama_utils import get_llama_processor
        get_llama_processor()
        print("✅ Mixtral model downloaded")
        
        print("\n✅ All models cached successfully!")
        print("🚀 Future workers will use cached models (instant startup)")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download models: {e}")
        return False

if __name__ == "__main__":
    success = check_and_download_models()
    sys.exit(0 if success else 1)
