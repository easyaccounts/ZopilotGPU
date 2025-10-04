#!/bin/bash
# Cleanup script to remove partial Mixtral downloads and prepare for full FP16 model
# Run this on your RunPod instance before downloading the new model

echo "=========================================="
echo "🧹 Cleaning up old partial downloads"
echo "=========================================="

# Show current disk usage
echo ""
echo "Current disk usage:"
df -h /workspace

# Remove old Mixtral cache if exists
if [ -d "/workspace/huggingface/hub/models--mistralai--Mixtral-8x7B-Instruct-v0.1" ]; then
    echo ""
    echo "📦 Found old Mixtral cache, checking size..."
    du -sh /workspace/huggingface/hub/models--mistralai--Mixtral-8x7B-Instruct-v0.1
    
    echo "🗑️  Removing old Mixtral cache..."
    rm -rf /workspace/huggingface/hub/models--mistralai--Mixtral-8x7B-Instruct-v0.1
    echo "✅ Old cache removed"
else
    echo "ℹ️  No old Mixtral cache found"
fi

# Remove any xet cache if still exists
if [ -d "/workspace/huggingface/xet" ]; then
    echo ""
    echo "🗑️  Removing xet cache..."
    du -sh /workspace/huggingface/xet
    rm -rf /workspace/huggingface/xet
    echo "✅ Xet cache removed"
fi

# Clean up temp files
if [ -d "/workspace/tmp" ]; then
    echo ""
    echo "🗑️  Cleaning temp files..."
    find /workspace/tmp -type f -mtime +1 -delete 2>/dev/null || true
    echo "✅ Temp files cleaned"
fi

# Show final disk usage
echo ""
echo "=========================================="
echo "Final disk usage:"
df -h /workspace
echo ""
echo "Available space breakdown:"
du -sh /workspace/* 2>/dev/null | sort -hr
echo "=========================================="
echo ""
echo "✅ Cleanup complete!"
echo "You now have space for the full 93GB Mixtral FP16 model"
echo ""
echo "Next steps:"
echo "1. Run: python warmup_cache.py"
echo "2. Wait 30-45 minutes for full model download"
echo "3. Model will auto-load in 8-bit mode (24GB VRAM)"
echo "=========================================="
