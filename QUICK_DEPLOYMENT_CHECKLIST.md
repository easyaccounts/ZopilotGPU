# 🚀 Quick Deployment Checklist

## Pre-Deployment Preparation

### 1. Get Required Credentials ✅
- [ ] **Hugging Face Token** 
  - Sign up: https://huggingface.co/join
  - Create token: https://huggingface.co/settings/tokens (Read access)
  - Accept Mixtral license: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1

- [ ] **Generate API Key**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
  Save this key - you'll use it in both backend and GPU service

- [ ] **NanoNets API Key** (Optional - 10k pages/month free)
  - Sign up: https://app.nanonets.com
  - Get key: https://app.nanonets.com/#/keys

### 2. Choose Cloud Provider ✅
- [ ] **RunPod** (Recommended - Easy setup, reliable)
  - RTX 4090: ~$0.34-0.69/hr
  - Sign up: https://runpod.io
  
- [ ] **Vast.ai** (Budget - Cheapest option)
  - RTX 4090: ~$0.25-0.40/hr
  - Sign up: https://vast.ai
  
- [ ] **Lambda Labs** (Enterprise - Best uptime)
  - A6000: ~$1.10/hr
  - Sign up: https://lambdalabs.com

---

## Cloud GPU Deployment

### RunPod Quick Setup
```bash
# 1. Deploy GPU Pod
- Go to RunPod → Pods → Deploy
- GPU Filter: Memory ≥ 24GB
- Select: RTX 4090 / A5000 / A6000
- Template: pytorch 2.1.0 (or start from scratch)
- Volume Size: 100GB (for model cache)

# 2. Connect via SSH and setup
ssh root@<pod-ip> -p <port> -i ~/.ssh/id_ed25519

# Install git if needed
apt-get update && apt-get install -y git curl

# Clone repository (replace with your repo)
cd /workspace
git clone https://github.com/yourusername/ZopilotGPU.git
cd ZopilotGPU

# Install Python dependencies
pip install -r requirements.txt

# Setup environment
cp .env.production .env
nano .env
# Update: HUGGING_FACE_TOKEN, ZOPILOT_GPU_API_KEY, ALLOWED_ORIGINS

# Start service
chmod +x start.sh
./start.sh
```

### Get Your GPU Endpoint URL
- **RunPod**: Check pod details for proxy URL
  ```
  https://xxxxx-8000.proxy.runpod.net
  ```
- **Vast.ai**: Note instance IP and mapped port
  ```
  http://<instance-ip>:<port>
  ```
- **Lambda**: Use instance public IP
  ```
  http://<instance-ip>:8000
  ```

---

## Backend Configuration

### Update Backend .env
```bash
# Open backend .env file
cd /path/to/zopilot-backend
nano .env

# Add/Update these lines:
ZOPILOT_GPU_URL=https://your-gpu-endpoint-from-above
ZOPILOT_GPU_API_KEY=your_secure_api_key_from_step_1
ZOPILOT_GPU_TIMEOUT=300000  # 5 minutes for first request
```

### Update GPU Service CORS
```bash
# Get backend domain
echo $BACKEND_DOMAIN  # e.g., https://api.yourdomain.com

# SSH to GPU instance and update .env
nano /workspace/ZopilotGPU/.env

# Update ALLOWED_ORIGINS
ALLOWED_ORIGINS=https://api.yourdomain.com,https://app.yourdomain.com

# Restart service
pkill -f uvicorn && ./start.sh
```

---

## Verification Tests

### 1. Health Check ✅
```bash
curl https://your-gpu-endpoint/health
```
**Expected Response:**
```json
{
  "status": "healthy",
  "model": "Mixtral-8x7B-Instruct-v0.1",
  "gpu_available": true
}
```

### 2. Authentication Test ✅
```bash
# Should FAIL with 401
curl -X POST https://your-gpu-endpoint/extract \
  -H "Content-Type: application/json" \
  -d '{"document_url":"test.pdf"}'

# Should SUCCEED
curl -X POST https://your-gpu-endpoint/extract \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"document_url":"test.pdf"}'
```

### 3. CORS Test ✅
From browser console on your frontend domain:
```javascript
fetch('https://your-gpu-endpoint/health')
  .then(r => r.json())
  .then(console.log)
```
**Should NOT show CORS error**

### 4. Full Integration Test ✅
Upload a test document through your backend:
```bash
# From backend server
curl -X POST http://localhost:8080/api/documents/upload \
  -H "Authorization: Bearer your_backend_token" \
  -F "file=@test-invoice.pdf" \
  -F "category=invoice"

# Check logs for GPU processing
tail -f logs/combined.log | grep "GPU"
```

### 5. GPU Status Check ✅
```bash
# SSH to GPU instance
nvidia-smi

# Should show:
# - GPU utilization when processing
# - ~23GB memory used (Mixtral model loaded)
```

---

## Performance Benchmarks

### First Request (Cold Start)
- **Model not cached**: 15-30 minutes (downloading 47GB)
- **Model cached**: 2-5 minutes (loading to GPU)
- **Model loaded**: 8-15 seconds (extraction + generation)

### Subsequent Requests
- **Extraction only**: 3-8 seconds
- **Extraction + Generation**: 8-15 seconds
- **Concurrent processing**: 1 request at a time (single worker)

### Cost Estimates (Monthly)
**Scenario: 1000 documents/month, 10 seconds average**
- Total processing time: ~2.8 hours/month
- RunPod RTX 4090 Spot: ~$1-2/month
- RunPod RTX 4090 On-Demand: ~$2-3/month
- Lambda A6000: ~$3-4/month

---

## Troubleshooting

### Issue: Model fails to load (OOM)
**Symptoms**: `CUDA out of memory` error
**Solutions**:
1. Verify GPU has ≥24GB VRAM: `nvidia-smi`
2. Kill other GPU processes: `pkill -f python`
3. Restart container/pod
4. Upgrade to larger GPU (A6000 48GB)

### Issue: First request times out
**Symptoms**: 504 Gateway Timeout on first document
**Solutions**:
1. Increase backend timeout: `ZOPILOT_GPU_TIMEOUT=300000`
2. Pre-load model: Set `PRELOAD_MODELS=true` in GPU .env
3. Wait 5-10 minutes after service start before testing

### Issue: CORS errors
**Symptoms**: Browser shows CORS policy error
**Solutions**:
1. Add frontend domain to `ALLOWED_ORIGINS`
2. Use HTTPS (not HTTP) for production
3. Restart GPU service after changing CORS

### Issue: 401 Unauthorized
**Symptoms**: All requests return 401
**Solutions**:
1. Verify API keys match between backend and GPU
2. Check header format: `Authorization: Bearer <key>`
3. Or use: `X-API-Key: <key>`
4. Ensure no extra spaces in .env file

### Issue: Extraction returns empty data
**Symptoms**: Response `{"data": {}}` or `null`
**Solutions**:
1. Verify document URL is accessible from GPU instance
2. Check document format (PDF, PNG, JPG supported)
3. Review GPU logs: `tail -f /app/logs/*.log`
4. Test with sample document from docs

---

## Monitoring Setup

### Basic Monitoring
```bash
# GPU utilization
watch -n 1 nvidia-smi

# Service logs
tail -f /workspace/ZopilotGPU/logs/*.log

# Application logs
journalctl -u zopilot-gpu -f  # If using systemd
```

### Production Monitoring (Recommended)
1. **UptimeRobot** - Ping health endpoint every 5 minutes
   - URL: `https://your-gpu-endpoint/health`
   - Alert on: Status != 200

2. **Sentry** - Error tracking
   - Add to GPU .env: `SENTRY_DSN=your_sentry_dsn`
   
3. **Datadog/Prometheus** - Metrics
   - GPU utilization, request latency, error rates

---

## Security Best Practices

- [x] API key is 32+ characters random string
- [x] CORS limited to specific domains (not `*`)
- [x] HTTPS enabled (via cloud provider proxy)
- [x] Environment variables not in git (use .env files)
- [x] Regular updates: `apt-get update && apt-get upgrade`
- [x] Firewall rules restrict port access
- [x] Monitoring and alerting configured
- [x] Backup strategy for logs

---

## Production Readiness Checklist

### GPU Service ✅
- [ ] Model downloads successfully
- [ ] Health check returns 200
- [ ] API key authentication works
- [ ] CORS allows backend domain
- [ ] Extraction endpoint works
- [ ] Generation endpoint works
- [ ] Logs are being written
- [ ] GPU memory usage is normal (~23GB)

### Backend Integration ✅
- [ ] Backend can reach GPU endpoint
- [ ] API key configured in backend .env
- [ ] Timeout set to 300000 (5 min)
- [ ] Web uploads trigger extraction
- [ ] G-Drive sync triggers extraction
- [ ] Status updates to 'extracted'
- [ ] Extracted data saved to database
- [ ] Error handling works

### Monitoring ✅
- [ ] Health check monitoring active
- [ ] Error alerting configured
- [ ] GPU utilization tracking
- [ ] Log aggregation setup
- [ ] Backup strategy defined

---

## Next Steps

1. **Deploy to Production** ✅
   - Follow RunPod/Vast/Lambda setup above
   - Verify all tests pass
   - Monitor for 24 hours

2. **Implement Step 2** (Module/Action Determination)
   - Use extracted data from Step 1
   - Determine accounting module and action
   - Update status to 'determining_action'

3. **Implement Step 3** (Action Execution)
   - Execute determined action
   - Update status to 'completed'
   - Store results in database

4. **Scale** (When needed)
   - Add request queuing
   - Implement auto-scaling
   - Add load balancing

---

## Support Resources

- **Technical Issues**: Check logs first, then GitHub issues
- **Cloud Provider Help**:
  - RunPod: https://docs.runpod.io
  - Vast.ai: https://vast.ai/docs
  - Lambda: https://lambdalabs.com/service/gpu-cloud
- **Model Issues**: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1/discussions

---

**Last Updated**: 2025-01-03  
**Service Version**: 1.0.0  
**Model**: Mixtral 8x7B Instruct v0.1
