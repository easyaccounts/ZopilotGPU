#!/usr/bin/env python3
"""
Download models locally, then sync to RunPod network volume.
This avoids burning GPU credits on model downloads.

Steps:
1. Run this script locally to download models (~53GB)
2. Zip the cache directory
3. Upload to RunPod network volume via runpodctl or web interface
"""
import os
from pathlib import Path

# Set cache directory
CACHE_DIR = Path("./model_cache")
CACHE_DIR.mkdir(exist_ok=True)

# Point all model caches to local directory
# IMPORTANT: Models stored directly in huggingface/ (legacy transformers structure, matches network volume)
os.environ["HF_HOME"] = str(CACHE_DIR / "huggingface")
os.environ["TRANSFORMERS_CACHE"] = str(CACHE_DIR / "huggingface")
os.environ["HF_HUB_CACHE"] = str(CACHE_DIR / "huggingface")
os.environ["TORCH_HOME"] = str(CACHE_DIR / "torch")
os.environ["XDG_CACHE_HOME"] = str(CACHE_DIR)

print("=" * 80)
print("📦 Downloading Models Locally")
print(f"Cache directory: {CACHE_DIR.absolute()}")
print("=" * 80)

# Need these installed locally
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install torch transformers bitsandbytes accelerate")
    exit(1)

def download_mixtral():
    """Download Mixtral model."""
    print("\n📦 Downloading Mixtral 8x7B FP16 model (~93GB)...")
    print("   Model will be quantized to 8-bit at load time (~24GB VRAM)")
    print("⚠️  You need HUGGING_FACE_TOKEN environment variable set")
    
    hf_token = os.getenv("HUGGING_FACE_TOKEN")
    if not hf_token:
        print("❌ HUGGING_FACE_TOKEN not set!")
        print("   export HUGGING_FACE_TOKEN=hf_your_token")
        return False
    
    model_name = "mistralai/Mixtral-8x7B-Instruct-v0.1"
    
    try:
        print(f"Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            token=hf_token,
            cache_dir=str(CACHE_DIR / "huggingface")
        )
        
        print(f"Downloading model (this will take 30-60 min)...")
        # Download model files without loading (saves RAM)
        from transformers import AutoConfig
        config = AutoConfig.from_pretrained(
            model_name,
            token=hf_token,
            cache_dir=str(CACHE_DIR / "huggingface")
        )
        
        # Trigger download of model weights
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=model_name,
            token=hf_token,
            cache_dir=str(CACHE_DIR / "huggingface")
        )
        
        print("✅ Mixtral downloaded successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download Mixtral: {e}")
        return False

def download_docstrange():
    """Download Docstrange models."""
    print("\n📦 Downloading Docstrange models (~6GB)...")
    
    # Note: This requires the docstrange package which may not be pip-installable
    # You may need to download these manually from the source
    print("⚠️  Docstrange models must be downloaded via the actual package")
    print("   Skipping for now - these will download on first GPU worker run (only 5 min)")
    return True

if __name__ == "__main__":
    print("\n🚀 Starting local model download...")
    
    # Download models
    mixtral_ok = download_mixtral()
    docstrange_ok = download_docstrange()
    
    if mixtral_ok and docstrange_ok:
        print("\n" + "=" * 80)
        print("✅ Models downloaded successfully!")
        print("=" * 80)
        print(f"\nCache location: {CACHE_DIR.absolute()}")
        print(f"\nNext steps:")
        print("1. Zip the cache directory:")
        print(f"   tar -czf model_cache.tar.gz -C {CACHE_DIR.parent} {CACHE_DIR.name}")
        print("\n2. Upload to RunPod network volume:")
        print("   - Use RunPod web interface to upload")
        print("   - Or use runpodctl: runpodctl send model_cache.tar.gz")
        print("\n3. Extract in network volume:")
        print("   tar -xzf model_cache.tar.gz -C /runpod-volume/")
        print("=" * 80)
    else:
        print("\n❌ Some downloads failed")
        exit(1)
