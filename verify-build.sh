#!/bin/bash
# Quick pre-deployment check for ZopilotGPU

echo "🔍 Quick Build Verification..."
echo ""

# Check Python syntax
echo "Checking Python files..."
python -m py_compile handler.py app/main.py app/llama_utils.py app/docstrange_utils.py
if [ $? -eq 0 ]; then
    echo "✅ Python syntax OK"
else
    echo "❌ Python syntax errors found"
    exit 1
fi

# Check requirements can be parsed
echo "Checking requirements.txt..."
pip install --dry-run -r requirements.txt > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Dependencies can resolve"
else
    echo "⚠️  Dependency conflicts detected (check requirements.txt)"
fi

# Check critical files exist
echo "Checking files..."
files=("Dockerfile" "requirements.txt" "handler.py" "app/main.py")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ Missing: $file"
        exit 1
    fi
done

echo ""
echo "✅ Build verification passed! Safe to push."
