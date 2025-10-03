# ✅ Production Deployment Checklist

## 📦 Essential Files (Push to GitHub)
- ✅ `app/` - Main application code
- ✅ `handler.py` - RunPod serverless handler
- ✅ `Dockerfile` - Container configuration
- ✅ `requirements.txt` - Python dependencies
- ✅ `start.sh` - Startup script
- ✅ `.gitignore` - Exclude secrets/tests
- ✅ `README.md` - Documentation

## 🚫 Files to Keep Local (NOT in GitHub)
- ❌ `.env` - Contains secrets (use .env.example instead)
- ❌ `test_*.py` - Test files
- ❌ `document_router.py` - Old unused code
- ❌ `*.log` - Log files

## 🔐 Before Deploying
1. [ ] Hugging Face token ready
2. [ ] API key set: `b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI`
3. [ ] Backend domain: `https://zopilot-backend-production.up.railway.app`
4. [ ] No secrets in code

## 🚀 Deploy Steps
```bash
# 1. Push to GitHub
cd D:\Desktop\Zopilot\ZopilotGPU
git add .
git commit -m "Production ready"
git push

# 2. RunPod Serverless
# - Go to: https://runpod.io/console/serverless
# - New Endpoint → GitHub → easyaccounts/ZopilotGPU
# - Add env vars, select GPU, deploy

# 3. Update backend
# ZOPILOT_GPU_URL=https://api.runpod.ai/v2/{endpoint-id}
```

## ✨ You're Done!
RunPod auto-deploys on every git push.
