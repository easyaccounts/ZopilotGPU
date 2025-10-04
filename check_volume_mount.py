#!/usr/bin/env python3
"""
Check where the network volume is actually mounted.
Run this in the pod to verify the mount path.
"""
import os
from pathlib import Path

print("=" * 80)
print("🔍 Network Volume Mount Detection")
print("=" * 80)

# Common mount paths to check
common_paths = [
    "/runpod-volume",
    "/workspace",
    "/data",
    "/mnt/volume",
    "/volume",
    "/storage"
]

print("\n📂 Checking common mount paths:")
for path in common_paths:
    p = Path(path)
    exists = p.exists()
    is_mount = os.path.ismount(path) if exists else False
    writable = os.access(path, os.W_OK) if exists else False
    
    status = "✅" if exists else "❌"
    mount_indicator = " [MOUNTED]" if is_mount else ""
    write_indicator = " [WRITABLE]" if writable else " [READ-ONLY]" if exists else ""
    
    print(f"{status} {path}{mount_indicator}{write_indicator}")

print("\n🔍 Environment variables:")
print(f"XDG_CACHE_HOME: {os.getenv('XDG_CACHE_HOME', 'NOT SET')}")
print(f"TRANSFORMERS_CACHE: {os.getenv('TRANSFORMERS_CACHE', 'NOT SET')}")
print(f"HF_HOME: {os.getenv('HF_HOME', 'NOT SET')}")

print("\n📊 Disk usage:")
os.system("df -h | grep -E 'Filesystem|volume|workspace|data'")

print("\n💡 Recommendation:")
mounted_volumes = [p for p in common_paths if Path(p).exists() and os.path.ismount(p)]
if mounted_volumes:
    print(f"✅ Use this path: {mounted_volumes[0]}")
else:
    print("⚠️  No mounted volumes detected!")
    print("   Volume may not be attached or uses different path")

print("=" * 80)
