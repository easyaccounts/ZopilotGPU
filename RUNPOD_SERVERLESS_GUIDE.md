# 🚀 RunPod Serverless Deployment Guide for ZopilotGPU

## Overview

RunPod Serverless provides **auto-scaling GPU instances** that:
- Start only when requests come in (saves money)
- Scale automatically based on demand
- Bill per second of actual GPU usage
- Keep models cached for faster cold starts

**Best for**: Production apps with variable/unpredictable traffic

---

## 📋 Prerequisites

### 1. RunPod Account
- Sign up: https://runpod.io
- Add payment method
- Get API key: https://runpod.io/console/user/settings

### 2. Docker Hub Account
- Sign up: https://hub.docker.com
- Create repository: `yourusername/zopilot-gpu`
- Get access token for CLI

### 3. Required Tokens
- **Hugging Face Token**: https://huggingface.co/settings/tokens
  - Accept Mixtral license: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1
- **API Key**: Already generated: `b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI`

---

## 🏗️ Step 1: Prepare Docker Image

### 1.1 Update Dockerfile for Serverless

Your current Dockerfile is good, but let's verify it's optimized:

```bash
cd D:\Desktop\Zopilot\ZopilotGPU
```

The Dockerfile should have:
- ✅ Model cache to `/app/models`
- ✅ CUDA 12.1 support
- ✅ Fast startup script

### 1.2 Build Docker Image

```powershell
# Build the image (this will take 10-15 minutes)
docker build -t yourusername/zopilot-gpu:latest .

# Test locally (optional - requires GPU)
docker run --gpus all -p 8000:8000 --env-file .env.production yourusername/zopilot-gpu:latest
```

### 1.3 Push to Docker Hub

```powershell
# Login to Docker Hub
docker login

# Push image (this will take 10-20 minutes - image is large)
docker push yourusername/zopilot-gpu:latest
```

**Image size**: ~15-20GB (includes CUDA, Python, dependencies)

---

## 🎯 Step 2: Create RunPod Serverless Endpoint

### 2.1 Go to RunPod Console
1. Open: https://runpod.io/console/serverless
2. Click **"+ New Endpoint"**

### 2.2 Configure Endpoint

**Basic Settings:**
```
Name: zopilot-gpu
Container Image: yourusername/zopilot-gpu:latest
Container Registry Credentials: (add if private repo)
```

**Container Configuration:**
```
Container Disk: 20 GB
Volume Disk: 100 GB (for model caching)
Volume Mount Path: /app/models
```

**GPU Selection:**
```
GPU Types: RTX 4090, A5000, A6000, A100 40GB
Min Workers: 0 (scale to zero when idle)
Max Workers: 3 (adjust based on expected load)
Idle Timeout: 5 seconds
```

**Environment Variables:**
```
ZOPILOT_GPU_API_KEY = b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI
HUGGING_FACE_TOKEN = your_hf_token_here
ALLOWED_ORIGINS = https://zopilot-backend-production.up.railway.app
NANONETS_API_KEY = your_nanonets_key (optional)
HEALTH_CHECK_PUBLIC = true
LOG_LEVEL = INFO
TRANSFORMERS_CACHE = /app/models
HF_HOME = /app/models
TORCH_HOME = /app/models
PORT = 8000
HOST = 0.0.0.0
```

**Advanced Settings:**
```
Max Concurrency: 1 (Mixtral uses full GPU)
```

### 2.3 Save & Deploy

Click **"Deploy"** - RunPod will:
1. Pull your Docker image
2. Provision GPU instances
3. Start your endpoint

**Initial deployment**: 5-10 minutes

---

## 📡 Step 3: Get Your Endpoint URL

After deployment completes:

1. Go to your endpoint page
2. Copy the **Endpoint URL**:
   ```
   https://api.runpod.ai/v2/{endpoint-id}/runsync
   ```

3. Note your **Endpoint ID** (shown in URL)

---

## 🔧 Step 4: Update Backend Configuration

Update `zopilot-backend/.env`:

```bash
# Old (local)
ZOPILOT_GPU_URL=http://localhost:8000

# New (RunPod Serverless)
ZOPILOT_GPU_URL=https://api.runpod.ai/v2/{your-endpoint-id}
ZOPILOT_GPU_API_KEY=b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI
ZOPILOT_GPU_TIMEOUT=300000
```

---

## 🎮 Step 5: Create Backend Integration Helper

RunPod Serverless uses a **different API format** than direct FastAPI. Create a wrapper:

### Option A: Modify Backend Service

Update `aiProcessingService.ts` to handle RunPod format:

```typescript
private async callRunPodEndpoint(endpoint: string, data: any): Promise<any> {
  const isRunPod = this.config.baseUrl.includes('runpod.ai');
  
  if (isRunPod) {
    // RunPod Serverless format
    const response = await axios.post(
      `${this.config.baseUrl}/runsync`,
      {
        input: {
          endpoint: endpoint, // "/extract" or "/prompt"
          data: data
        }
      },
      {
        headers: this.getHeaders(),
        timeout: this.config.timeout
      }
    );
    
    return response.data.output;
  } else {
    // Direct FastAPI format
    const response = await axios.post(
      `${this.config.baseUrl}${endpoint}`,
      data,
      {
        headers: this.getHeaders(),
        timeout: this.config.timeout
      }
    );
    
    return response.data;
  }
}
```

### Option B: Create RunPod Handler (Recommended)

Create `handler.py` in ZopilotGPU root:

```python
"""
RunPod Serverless Handler
Wraps FastAPI endpoints for RunPod serverless format
"""
import runpod
import asyncio
from app.main import app, extract_endpoint, prompt_endpoint
from app.main import ExtractionInput, PromptInput

async def async_handler(job):
    """Handle RunPod serverless job"""
    job_input = job['input']
    
    endpoint = job_input.get('endpoint')
    data = job_input.get('data')
    
    try:
        if endpoint == '/extract':
            input_data = ExtractionInput(**data)
            result = await extract_endpoint(None, input_data)
            return result.dict()
            
        elif endpoint == '/prompt':
            input_data = PromptInput(**data)
            result = await prompt_endpoint(None, input_data)
            return result.dict()
            
        else:
            return {"error": f"Unknown endpoint: {endpoint}"}
            
    except Exception as e:
        return {"error": str(e)}

def handler(job):
    """Sync wrapper for async handler"""
    return asyncio.run(async_handler(job))

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
```

Update `requirements.txt`:
```
runpod>=1.3.0
```

Update `Dockerfile` CMD:
```dockerfile
CMD ["python", "-m", "runpod"]
```

---

## ✅ Step 6: Test Your Deployment

### Test 1: Health Check
```powershell
curl -X POST https://api.runpod.ai/v2/{endpoint-id}/runsync `
  -H "Content-Type: application/json" `
  -d '{\"input\": {\"endpoint\": \"/health\"}}'
```

### Test 2: Extract Document
```powershell
curl -X POST https://api.runpod.ai/v2/{endpoint-id}/runsync `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI" `
  -d '{
    \"input\": {
      \"endpoint\": \"/extract\",
      \"data\": {
        \"document_url\": \"https://your-test-doc.pdf\",
        \"document_id\": \"test-123\"
      }
    }
  }'
```

### Test 3: Prompt Mixtral
```powershell
curl -X POST https://api.runpod.ai/v2/{endpoint-id}/runsync `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI" `
  -d '{
    \"input\": {
      \"endpoint\": \"/prompt\",
      \"data\": {
        \"prompt\": \"What are the main fields in an invoice?\"
      }
    }
  }'
```

---

## 💰 Cost Estimation

### RunPod Serverless Pricing (as of 2024)

**GPU Options:**
- RTX 4090 (24GB): ~$0.69/hr = ~$0.00019/sec
- A5000 (24GB): ~$0.79/hr = ~$0.00022/sec
- A6000 (48GB): ~$1.29/hr = ~$0.00036/sec
- A100 40GB: ~$1.89/hr = ~$0.00053/sec

**Processing Time:**
- Cold start (first request): ~30-60 seconds
- Warm requests: ~5-10 seconds per document

**Monthly Cost Examples:**

**Scenario 1: 100 docs/month**
- 100 docs × 10 sec = 1,000 seconds
- RTX 4090: 1,000 × $0.00019 = **$0.19/month**

**Scenario 2: 1,000 docs/month**
- 1,000 docs × 10 sec = 10,000 seconds
- RTX 4090: 10,000 × $0.00019 = **$1.90/month**

**Scenario 3: 10,000 docs/month**
- 10,000 docs × 10 sec = 100,000 seconds
- RTX 4090: 100,000 × $0.00019 = **$19/month**

**Cold Starts:**
- If endpoint goes idle (no requests for 5 min), next request has 30-60s delay
- Solution: Keep endpoint "warm" with periodic health checks

---

## 🔥 Step 7: Keep Endpoint Warm (Optional)

To avoid cold starts, ping your endpoint every 3-5 minutes:

### Option 1: UptimeRobot
1. Sign up: https://uptimerobot.com (free)
2. Add HTTP(s) monitor
3. URL: `https://api.runpod.ai/v2/{endpoint-id}/health`
4. Interval: 5 minutes

### Option 2: Backend Cron Job
```typescript
// In your backend
import cron from 'node-cron';

// Ping GPU every 4 minutes
cron.schedule('*/4 * * * *', async () => {
  try {
    await axios.post(
      `${process.env.ZOPILOT_GPU_URL}/runsync`,
      { input: { endpoint: '/health' } }
    );
    console.log('GPU kept warm');
  } catch (error) {
    console.error('Failed to keep GPU warm:', error);
  }
});
```

**Note**: Keeping warm costs ~$0.10-0.20/day but eliminates 30-60s delays

---

## 📊 Step 8: Monitor Your Deployment

### RunPod Dashboard
- View: https://runpod.io/console/serverless
- Metrics: Requests, latency, errors, costs
- Logs: Real-time container logs

### Important Metrics:
- **Cold start rate**: % of requests that start new container
- **Execution time**: Average processing time
- **Error rate**: Failed requests
- **Active workers**: Current running instances

---

## 🐛 Troubleshooting

### Issue: Container fails to start
**Solution**: Check logs in RunPod dashboard
- Verify Docker image is public or credentials added
- Check environment variables are set
- Ensure Hugging Face token is valid

### Issue: First request times out
**Solution**: Cold start takes 30-60 seconds
- Increase backend timeout to 120 seconds for first request
- Consider keeping endpoint warm

### Issue: Out of memory error
**Solution**: Mixtral needs 24GB VRAM
- Use RTX 4090 or larger GPU
- Don't use RTX 3090 (only 24GB, barely enough)

### Issue: High costs
**Solution**: Optimize usage
- Reduce idle timeout (scale to zero faster)
- Use smaller GPU if possible
- Batch requests when possible

---

## 🚀 Alternative: RunPod Pods (Traditional)

If serverless is too complex, use **RunPod Pods** (always-on):

1. Go to: https://runpod.io/console/pods
2. Select GPU: RTX 4090
3. Use template: pytorch
4. SSH and setup as per `CLOUD_DEPLOYMENT_GUIDE.md`
5. Get pod URL: `https://xxxxx-8000.proxy.runpod.net`

**Cost**: ~$0.34-0.69/hr continuous (even when idle)

**Best for**: Predictable traffic, always-on needs

---

## 📝 Quick Command Reference

```powershell
# Build & push image
docker build -t yourusername/zopilot-gpu:latest .
docker push yourusername/zopilot-gpu:latest

# Test locally
docker run --gpus all -p 8000:8000 --env-file .env yourusername/zopilot-gpu:latest

# Test RunPod endpoint
curl -X POST https://api.runpod.ai/v2/{endpoint-id}/runsync `
  -H "Content-Type: application/json" `
  -d '{\"input\": {\"endpoint\": \"/health\"}}'
```

---

## 🎯 Next Steps After Deployment

1. ✅ Deploy to RunPod Serverless
2. ✅ Update backend with endpoint URL
3. ✅ Test extraction endpoint
4. ✅ Test prompt endpoint
5. ✅ Monitor costs for 1 week
6. ⏭️ Setup monitoring alerts
7. ⏭️ Implement endpoint warming if needed
8. ⏭️ Optimize based on usage patterns

---

## 📞 Support

- **RunPod Docs**: https://docs.runpod.io/serverless/overview
- **Discord**: https://discord.gg/runpod
- **Status**: https://status.runpod.io
