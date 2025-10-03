# ZopilotGPU Cloud Deployment Guide

## 🎯 Overview

This guide covers deploying ZopilotGPU with Mixtral 8x7B to cloud GPU providers.

## 📋 Prerequisites

### GPU Requirements
- **Minimum**: 24GB VRAM (for 4-bit quantized Mixtral 8x7B)
- **Recommended GPUs**:
  - NVIDIA RTX 4090 (24GB) - ~$0.50-0.80/hr
  - NVIDIA A5000 (24GB) - ~$0.70-1.00/hr
  - NVIDIA A6000 (48GB) - ~$1.00-1.50/hr
  - NVIDIA A100 (40GB/80GB) - ~$1.50-2.50/hr

### Required Accounts
1. **Hugging Face**: https://huggingface.co/join
   - Create account
   - Generate access token: https://huggingface.co/settings/tokens
   - Accept Mixtral license: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1

2. **Cloud GPU Provider** (choose one):
   - RunPod: https://runpod.io
   - Vast.ai: https://vast.ai
   - Lambda Labs: https://lambdalabs.com

3. **Optional - NanoNets** (for enhanced OCR):
   - Sign up: https://app.nanonets.com
   - Get API key: https://app.nanonets.com/#/keys
   - 10,000 pages/month free tier

## 🚀 Deployment Options

### Option 1: RunPod (Recommended)

#### Step 1: Create Pod Template
1. Go to RunPod → Templates → New Template
2. Configure:
   ```
   Name: ZopilotGPU-Mixtral
   Container Image: nvidia/cuda:12.1.0-devel-ubuntu22.04
   Docker Command: /bin/bash
   Container Disk: 50GB
   Volume Disk: 100GB (for model cache)
   Expose HTTP Ports: 8000
   Expose TCP Ports: (leave empty)
   ```

#### Step 2: Set Environment Variables
Click "Edit Template" → "Environment Variables":
```bash
HUGGING_FACE_TOKEN=your_hf_token_here
ZOPILOT_GPU_API_KEY=your_secure_api_key_here
ALLOWED_ORIGINS=https://your-backend-domain.com
NANONETS_API_KEY=your_nanonets_key_here
PRELOAD_MODELS=false
HEALTH_CHECK_PUBLIC=true
LOG_LEVEL=INFO
```

#### Step 3: Deploy Pod
1. Go to Pods → Deploy
2. Select GPU:
   - Filter: GPU Memory ≥ 24GB
   - Recommended: RTX 4090, A5000, A6000
3. Select your template: "ZopilotGPU-Mixtral"
4. Storage: Volume Mount Path = `/app/models`
5. Click "Deploy On-Demand" or "Deploy Spot"

#### Step 4: Setup Container
Once pod is running, connect via SSH:
```bash
# Update system
apt-get update && apt-get install -y git curl

# Clone your repository
cd /workspace
git clone https://github.com/yourusername/ZopilotGPU.git
cd ZopilotGPU

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.production .env
nano .env  # Update with your actual values

# Make start script executable
chmod +x start.sh

# Start service
./start.sh
```

#### Step 5: Get Public URL
1. RunPod provides automatic HTTPS proxy
2. Note your pod's public URL: `https://xxxxx-8000.proxy.runpod.net`
3. Update backend `.env`:
   ```bash
   ZOPILOT_GPU_URL=https://xxxxx-8000.proxy.runpod.net
   ZOPILOT_GPU_API_KEY=your_secure_api_key_here
   ```

---

### Option 2: Vast.ai (Budget Option)

#### Step 1: Find Instance
1. Go to Vast.ai → Search
2. Filter:
   - GPU Memory ≥ 24GB
   - Disk Space ≥ 150GB
   - Sort by: $/hr (lowest first)
3. Look for: RTX 4090, RTX 3090 Ti, A5000

#### Step 2: Launch Instance
1. Select instance → "Rent"
2. Choose image: `nvidia/cuda:12.1.0-devel-ubuntu22.04`
3. On-start script:
   ```bash
   apt-get update && apt-get install -y git curl python3.10 python3-pip
   cd /workspace
   git clone https://github.com/yourusername/ZopilotGPU.git
   cd ZopilotGPU
   pip install -r requirements.txt
   cp .env.production .env
   chmod +x start.sh
   ./start.sh
   ```

#### Step 3: Configure Port Forwarding
1. Vast.ai provides direct port mapping
2. Note your instance IP and port
3. Access: `http://<instance-ip>:<mapped-port>`

#### Step 4: Setup HTTPS (Optional but Recommended)
Use Cloudflare Tunnel or similar:
```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
./cloudflared-linux-amd64 tunnel --url http://localhost:8000
```

---

### Option 3: Lambda Labs (Enterprise)

#### Step 1: Create Instance
1. Go to Lambda Cloud → Instances
2. Select GPU: A6000 (48GB) or A100 (40GB/80GB)
3. Choose: Ubuntu 22.04 LTS + CUDA 12.1

#### Step 2: SSH Setup
```bash
ssh ubuntu@<instance-ip>

# Clone repository
git clone https://github.com/yourusername/ZopilotGPU.git
cd ZopilotGPU

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.production .env
nano .env  # Update values

# Start service
chmod +x start.sh
./start.sh
```

#### Step 3: Persistent Service
Create systemd service:
```bash
sudo nano /etc/systemd/system/zopilot-gpu.service
```

```ini
[Unit]
Description=ZopilotGPU Mixtral Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ZopilotGPU
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ubuntu/ZopilotGPU/start.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable zopilot-gpu
sudo systemctl start zopilot-gpu
sudo systemctl status zopilot-gpu
```

---

## 🔧 Post-Deployment Configuration

### 1. Update Backend Environment
Update `zopilot-backend/.env`:
```bash
# Production GPU URL (from your cloud provider)
ZOPILOT_GPU_URL=https://your-gpu-instance.com
ZOPILOT_GPU_API_KEY=your_secure_api_key_here
ZOPILOT_GPU_TIMEOUT=300000  # 5 minutes for first request (model loading)
```

### 2. Update GPU CORS Configuration
Update `ZopilotGPU/.env`:
```bash
# Use your actual backend domain
ALLOWED_ORIGINS=https://api.yourdomain.com,https://app.yourdomain.com
```

### 3. Test Integration
```bash
# From backend server
curl -X POST https://your-gpu-instance.com/health \
  -H "Authorization: Bearer your_secure_api_key_here"

# Should return: {"status": "healthy", "model": "Mixtral-8x7B-Instruct-v0.1"}
```

---

## 📊 Cost Optimization

### Spot/Preemptible Instances
- **RunPod Spot**: Save 50-70% vs on-demand
- **Vast.ai**: Always spot pricing (cheapest option)
- **Lambda**: No spot instances (on-demand only)

### Model Caching
- Use persistent volumes to cache model (47GB)
- First startup: ~15-30 minutes to download
- Subsequent starts: ~2-5 minutes (model cached)

### Auto-Scaling (Advanced)
For production with variable load:
1. Use RunPod Serverless (API-based scaling)
2. Implement request queuing in backend
3. Scale GPU instances based on queue depth

**Example Cost Comparison (RTX 4090, 24GB):**
- RunPod On-Demand: ~$0.69/hr
- RunPod Spot: ~$0.34/hr
- Vast.ai: ~$0.25-0.40/hr
- Lambda: ~$1.10/hr

---

## 🔒 Security Checklist

- [ ] API key configured (32+ character random string)
- [ ] CORS limited to specific domains (not `*`)
- [ ] HTTPS enabled (via provider or reverse proxy)
- [ ] Firewall rules restrict port 8000 access
- [ ] Environment variables never committed to git
- [ ] Regular security updates: `apt-get update && apt-get upgrade`
- [ ] Monitoring and alerting configured
- [ ] Backup strategy for model cache and logs

---

## 📈 Monitoring

### Health Check
```bash
# Public health check (no API key)
curl https://your-gpu-instance.com/health

# Detailed metrics (requires API key)
curl https://your-gpu-instance.com/metrics \
  -H "Authorization: Bearer your_api_key"
```

### Logs
```bash
# Container logs
docker logs -f <container-id>

# Application logs
tail -f /app/logs/*.log

# GPU utilization
watch -n 1 nvidia-smi
```

### Common Issues

**Issue**: Model loading fails with OOM error
- **Solution**: Ensure GPU has ≥24GB VRAM, check CUDA memory fragmentation

**Issue**: First request times out
- **Solution**: Increase `ZOPILOT_GPU_TIMEOUT` to 300000 (5 min) for first request

**Issue**: CORS errors in browser
- **Solution**: Add frontend domain to `ALLOWED_ORIGINS`

**Issue**: 401 Unauthorized
- **Solution**: Verify `ZOPILOT_GPU_API_KEY` matches between backend and GPU service

---

## 🚦 Deployment Verification

Run this checklist after deployment:

```bash
# 1. Health check
curl https://your-gpu-instance.com/health

# 2. Authentication test
curl https://your-gpu-instance.com/extract \
  -H "Authorization: Bearer wrong_key" \
  -H "Content-Type: application/json" \
  -d '{"document_url":"test.pdf"}'
# Should return 401

# 3. Valid extraction test
curl https://your-gpu-instance.com/extract \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "https://your-test-document-url.pdf",
    "document_id": "test-123"
  }'
# Should return extraction data

# 4. CORS test (from browser console on your frontend domain)
fetch('https://your-gpu-instance.com/health')
  .then(r => r.json())
  .then(console.log)
# Should NOT show CORS error

# 5. GPU utilization
ssh into-instance
nvidia-smi
# Should show model loaded in GPU memory (~23GB)
```

---

## 📞 Support

- **Hugging Face**: https://huggingface.co/docs
- **RunPod**: https://docs.runpod.io
- **Vast.ai**: https://vast.ai/docs
- **Lambda Labs**: https://lambdalabs.com/service/gpu-cloud

---

## 🔄 Updates

To update the service:
```bash
# SSH into instance
cd /workspace/ZopilotGPU  # or your path

# Pull latest code
git pull origin main

# Restart service
pkill -f uvicorn
./start.sh
```

For systemd service:
```bash
sudo systemctl restart zopilot-gpu
```
