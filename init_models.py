#!/usr/bin/env python3
"""
Initialize models on first startup.
Downloads models to network volume only if not already cached.
"""
import os
import sys
from pathlib import Path

def check_and_download_models():
    """Check if models exist, download if needed (LLM-only service)."""
    
    # Check if Mixtral model already exists in volume
    volume_path = Path("/runpod-volume")
    mixtral_path = volume_path / "huggingface"
    
    # Check for Mixtral model cache
    models_exist = False
    if mixtral_path.exists():
        mixtral_models = list(mixtral_path.glob("models--mistralai--Mixtral*"))
        models_exist = len(mixtral_models) > 0
    
    if models_exist:
        print("✅ Mixtral model already cached in network volume - skipping download")
        return True
    
    print("📦 Mixtral model not found in cache - downloading now...")
    print("⏱️  This will take 30-45 minutes (one-time only)")
    
    try:
        # Download Mixtral model (LLM-only service)
        print("\n📦 Downloading Mixtral 8x7B FP16 model (~93GB)...")
        print("   Model will be quantized to 8-bit at load time (~24GB VRAM)")
        from app.llama_utils import get_llama_processor
        get_llama_processor()
        print("✅ Mixtral model downloaded")
        
        print("\n✅ Model cached successfully!")
        print("🚀 Future workers will use cached model (instant startup)")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download models: {e}")
        return False

if __name__ == "__main__":
    success = check_and_download_models()
    sys.exit(0 if success else 1)
