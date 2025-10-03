# Keep-Warm Setup for ZopilotGPU

## Why Keep-Warm?
- **Cold start**: 5-10 minutes (model loading)
- **Warm start**: 6-8 seconds
- **Trade-off**: Pay ~$3-5/month to avoid cold starts

---

## Method 1: Health Check Ping (Recommended - $3/month)

### Using UptimeRobot (Free tier)
1. Sign up at https://uptimerobot.com
2. Create new monitor:
   - **Monitor Type**: HTTP(s)
   - **URL**: `https://your-runpod-endpoint.runpod.net/health`
   - **Monitoring Interval**: 5 minutes
   - **Monitor Timeout**: 30 seconds

3. Add HTTP headers:
   ```
   X-API-Key: b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI
   ```

**Cost**: FREE (UptimeRobot free tier)
**Keeps warm**: Pings every 5 minutes = 8,640 pings/month
**RunPod cost**: 8,640 × 2 seconds × $0.00019 = ~$3.28/month

### Using Cron-Job.org (Free alternative)
1. Sign up at https://cron-job.org
2. Create new cron job:
   - **URL**: `https://your-runpod-endpoint.runpod.net/health`
   - **Interval**: Every 5 minutes
   - **Timeout**: 30 seconds
3. Add custom header:
   ```
   X-API-Key: b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI
   ```

---

## Method 2: Backend Scheduled Task ($4/month)

### Using Railway Cron Job (if backend is on Railway)
1. Create a new file in your backend:

**backend/cron/keep-gpu-warm.js**
```javascript
const axios = require('axios');

async function pingGPU() {
  try {
    const response = await axios.get(process.env.ZOPILOT_GPU_URL + '/health', {
      headers: {
        'X-API-Key': process.env.ZOPILOT_GPU_API_KEY
      },
      timeout: 30000
    });
    console.log(`GPU warm ping: ${response.data.status}`);
  } catch (error) {
    console.error('GPU warm ping failed:', error.message);
  }
}

// Run every 5 minutes
setInterval(pingGPU, 5 * 60 * 1000);

// Initial ping
pingGPU();
```

2. Add to your backend startup (e.g., in `server.js`):
```javascript
// Keep GPU warm
require('./cron/keep-gpu-warm');
```

**Cost**: ~$4/month (8,640 × 2 seconds × $0.00019)

---

## Method 3: RunPod Active Workers ($50-60/month)

⚠️ **NOT RECOMMENDED** for your use case - too expensive

1. Go to RunPod endpoint settings
2. Set **"Min Workers"** to `1`
3. This keeps 1 worker always running

**Cost**: ~$50-60/month (RunPod charges idle rate)

---

## Recommended Setup

### For Your Use Case (5k docs + 5k prompts/month)

✅ **Use UptimeRobot free tier**
- **Total cost**: $13 (processing) + $3 (warm) = **$16/month**
- **Response time**: 6-8 seconds (no cold starts)
- **No code changes needed**

### Configuration:
```
Service: UptimeRobot
URL: https://api-YOUR_ENDPOINT_ID.runpod.net/health
Interval: 5 minutes
HTTP Headers: X-API-Key: b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI
```

---

## Without Keep-Warm

If you skip keep-warm:
- **First request after idle**: 5-10 minutes (model loading)
- **Subsequent requests**: 6-8 seconds (normal speed)
- **Idle timeout**: ~5 minutes of inactivity triggers shutdown
- **Total cost**: ~$13/month

**User experience impact**:
- Morning first request: Slow (cold start)
- After 5+ minute breaks: Slow (cold start)
- Regular usage: Fast (already warm)

---

## Decision Matrix

| Strategy | Cost/Month | First Request | After 5min Idle |
|----------|------------|---------------|-----------------|
| **No warming** | $13 | 5-10 min | 5-10 min |
| **UptimeRobot** | $16 | 6-8 sec | 6-8 sec |
| **Backend cron** | $17 | 6-8 sec | 6-8 sec |
| **Active workers** | $63 | 2-3 sec | 2-3 sec |

---

## Setup Steps (UptimeRobot)

1. **Deploy GPU to RunPod first** (follow DEPLOY_NOW.md)
2. **Get your endpoint URL** from RunPod dashboard
3. **Sign up at UptimeRobot.com**
4. **Create monitor**:
   - Name: "ZopilotGPU Warm"
   - Type: HTTP(s)
   - URL: `https://api-YOUR_ID.runpod.net/health`
   - Interval: 5 minutes
5. **Add custom HTTP header**:
   - Header: `X-API-Key`
   - Value: `b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI`
6. **Save and activate**

Done! Your GPU will stay warm for ~$3/month extra.

---

## Testing Keep-Warm

After setup, wait 10 minutes then test:
```bash
# Should respond in 6-8 seconds (not 5-10 minutes)
curl -X POST https://api-YOUR_ID.runpod.net/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI" \
  -d '{
    "document_url": "https://example.com/invoice.pdf"
  }'
```

If it takes 5+ minutes, keep-warm isn't working.
If it takes 6-8 seconds, keep-warm is working! ✅
