# Pre-Deployment Verification Guide

## Quick Verification (Before Every Push)

### Option 1: Run Verification Script (Recommended)
```powershell
cd d:\Desktop\Zopilot\ZopilotGPU
.\verify-build.ps1
```

✅ Checks:
- Python syntax
- Required files exist
- Dependencies can resolve
- Imports work

---

## Manual Verification Commands

### 1. Check Python Syntax (5 seconds)
```powershell
python -m py_compile handler.py app/main.py app/llama_utils.py app/docstrange_utils.py
```
**When to use**: After editing Python files

### 2. Test Requirements (30 seconds)
```powershell
pip install --dry-run -r requirements.txt
```
**When to use**: After changing requirements.txt

### 3. Test Imports (10 seconds)
```powershell
python -c "import handler; import app.main; print('✅ OK')"
```
**When to use**: Quick sanity check

### 4. Build Docker Locally (10-15 minutes)
```powershell
docker build -t zopilotgpu-test .
```
**When to use**: Before major deployments (catches ALL errors)

---

## Full Local Docker Test

If you want to test EXACTLY what RunPod will do:

```powershell
# Build image
docker build -t zopilotgpu-test .

# Run container (requires GPU for full test)
docker run --gpus all -p 8000:8000 `
  -e HUGGING_FACE_TOKEN="your_token" `
  -e ZOPILOT_GPU_API_KEY="your_key" `
  zopilotgpu-test

# Test endpoint
curl http://localhost:8000/health
```

---

## Automated Pre-Push Hook (Optional)

Add this to `.git/hooks/pre-push` to auto-verify before every push:

```bash
#!/bin/bash
cd "$(git rev-parse --show-toplevel)"
./verify-build.sh
exit $?
```

Make it executable:
```powershell
chmod +x .git/hooks/pre-push
```

Now Git will automatically run checks before every push!

---

## Common Errors & Fixes

### Error: "ModuleNotFoundError: No module named 'X'"
**Fix**: Add to requirements.txt or install locally:
```powershell
pip install X
```

### Error: "SyntaxError: invalid syntax"
**Fix**: Check line number in error, fix Python code

### Error: "ResolutionImpossible: dependency conflicts"
**Fix**: Use flexible version ranges in requirements.txt:
```
package>=1.0.0,<2.0.0  # Instead of package==1.0.0
```

### Error: "Dockerfile: command not found"
**Fix**: Make sure Docker is installed and running

---

## Workflow Summary

```
1. Edit code
2. Run verify-build.ps1          ← Quick check
3. Fix any errors
4. git add .
5. git commit -m "message"
6. Run verify-build.ps1 again    ← Final check
7. git push                      ← Deploy!
```

---

## VS Code Integration (Bonus)

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Verify Build",
      "type": "shell",
      "command": ".\\verify-build.ps1",
      "group": {
        "kind": "test",
        "isDefault": true
      },
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    }
  ]
}
```

Then press `Ctrl+Shift+B` to run verification!
