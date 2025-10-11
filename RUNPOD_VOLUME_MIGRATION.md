# RunPod Network Volume Migration Guide

## Current Situation
- **Current Volume**: Network volume in region with low 32GB GPU supply
- **Data to migrate**: 
  - Hugging Face model cache: `models--mistralai--Mixtral-8x7B-Instruct-v0.1` (~47GB)
  - EasyOCR models: `/runpod-volume/easyocr`
  - DocStrange models: `/runpod-volume/docstrange/models`
  - Torch cache: `/runpod-volume/torch`

## Migration Steps

### Option A: Direct Copy via Temporary Pod (Recommended)

#### 1. Create New Network Volume in Target Region
```bash
# Via RunPod Console:
# 1. Go to Storage > Network Volumes
# 2. Click "Create Network Volume"
# 3. Select TARGET REGION with good 32GB GPU availability
# 4. Size: 100GB (or match current volume size)
# 5. Name: "zopilot-gpu-cache-[region]"
```

#### 2. Spin Up Temporary Migration Pod
```bash
# In OLD region (with existing volume):
# 1. Deploy a cheap GPU pod (RTX 3090/4090) or CPU pod
# 2. Attach existing volume as /old-volume
# 3. Container: runpod/pytorch:latest or ubuntu:22.04
```

#### 3. Install rsync and Create Backup Archive
```bash
# Connect to old pod terminal
apt-get update && apt-get install -y rsync awscli curl

# Create compressed archive
cd /old-volume
tar -czf /tmp/zopilot-cache.tar.gz huggingface/ easyocr/ docstrange/ torch/

# Check archive size
ls -lh /tmp/zopilot-cache.tar.gz
```

#### 4. Upload to Cloud Storage (Temporary Bridge)

**Option 4a: AWS S3 (if you have AWS account)**
```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure

# Upload archive
aws s3 cp /tmp/zopilot-cache.tar.gz s3://YOUR-BUCKET/zopilot-migration/

# Get download URL (valid 7 days)
aws s3 presign s3://YOUR-BUCKET/zopilot-migration/zopilot-cache.tar.gz --expires-in 604800
```

**Option 4b: RunPod S3 (Free for RunPod users)**
```bash
# RunPod provides temporary S3-compatible storage
# Use RunPod's built-in file manager to upload large files
# Or use their API for direct transfer
```

**Option 4c: Google Drive (Free, Manual)**
```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure Google Drive
rclone config
# Follow prompts to add Google Drive remote (name it "gdrive")

# Upload to Google Drive
rclone copy /tmp/zopilot-cache.tar.gz gdrive:RunPod-Migration/
```

#### 5. Download to New Volume
```bash
# In NEW region:
# 1. Deploy cheap GPU/CPU pod
# 2. Attach NEW volume as /runpod-volume
# 3. Container: same as step 2

# Download from cloud storage
# For AWS S3:
aws s3 cp s3://YOUR-BUCKET/zopilot-migration/zopilot-cache.tar.gz /tmp/

# For Google Drive:
rclone copy gdrive:RunPod-Migration/zopilot-cache.tar.gz /tmp/

# Extract to new volume
cd /runpod-volume
tar -xzf /tmp/zopilot-cache.tar.gz

# Verify extraction
ls -lah /runpod-volume/huggingface/
ls -lah /runpod-volume/easyocr/
```

#### 6. Verify Model Integrity
```bash
# Check Mixtral model files
ls -lR /runpod-volume/huggingface/models--mistralai--Mixtral-8x7B-Instruct-v0.1/

# Should see 19 safetensors shards + config files
# Expected files:
# - config.json
# - tokenizer.json
# - tokenizer_config.json
# - model-00001-of-00019.safetensors
# - ... (all 19 shards)
# - model.safetensors.index.json
```

### Option B: Direct Download to New Volume (Slower but Simpler)

If you prefer to skip cloud storage and re-download models:

#### 1. Create New Network Volume (same as Option A, step 1)

#### 2. Deploy Pod in New Region with New Volume

#### 3. Re-download Models
```bash
# Your Docker container will automatically download models on first run
# This takes 15-30 minutes for Mixtral 8x7B

# Or manually download:
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
    cache_dir="/runpod-volume/huggingface",
    token="YOUR_HF_TOKEN"
)
```

## Update Deployment Configuration

### 1. Update RunPod Serverless Template
```bash
# In RunPod Console > Templates:
# 1. Edit your ZopilotGPU template
# 2. Update "Network Volume" to NEW volume ID
# 3. Ensure region matches new volume region
# 4. Save template
```

### 2. Update Environment Variables (if needed)
```bash
# In your backend (Railway):
# Update RUNPOD_ENDPOINT_ID if endpoint changes
# Region change doesn't affect endpoint URL typically
```

### 3. Test Deployment
```bash
# Deploy new serverless endpoint in new region
# Make test classification request
# Verify model loads from new volume cache
```

## Cost Optimization

**During Migration:**
- Temporary pod cost: ~$0.20-0.50/hour (use cheapest GPU or CPU pod)
- Network egress: Free within RunPod
- Cloud storage: $0.02-0.10 per GB for temporary storage

**After Migration:**
- Delete OLD network volume: Save $5-10/month
- Use RTX 5090 32GB in high-availability region: Better uptime
- Or use A40 48GB: More consistent availability

## Estimated Timeline

| Task | Time | Notes |
|------|------|-------|
| Create new volume | 2 min | Instant provisioning |
| Spin up old pod | 5 min | Deploy + attach volume |
| Create archive | 10-20 min | ~47GB compression |
| Upload to cloud | 20-60 min | Depends on bandwidth |
| Spin up new pod | 5 min | Deploy + attach volume |
| Download archive | 20-60 min | Depends on bandwidth |
| Extract archive | 10-15 min | Decompression |
| Verify + test | 10 min | Model integrity check |
| **Total** | **90-180 min** | 1.5-3 hours |

## Troubleshooting

### Issue: Archive Too Large for Cloud Storage
**Solution**: Split into chunks
```bash
# Split into 5GB chunks
split -b 5G /tmp/zopilot-cache.tar.gz zopilot-part-

# Upload each chunk
for part in zopilot-part-*; do
    aws s3 cp $part s3://YOUR-BUCKET/zopilot-migration/
done

# On new pod, download and reassemble
cat zopilot-part-* > zopilot-cache.tar.gz
```

### Issue: Slow Transfer Speeds
**Solution**: Use parallel transfers
```bash
# For rclone with Google Drive
rclone copy /old-volume gdrive:RunPod-Migration/ \
    --transfers 8 \
    --checkers 16 \
    --drive-chunk-size 256M
```

### Issue: Out of Disk Space During Migration
**Solution**: Stream directly without temp file
```bash
# Stream from old to new via cloud storage
cd /old-volume
tar -czf - huggingface/ | aws s3 cp - s3://BUCKET/cache.tar.gz

# On new pod
aws s3 cp s3://BUCKET/cache.tar.gz - | tar -xzf - -C /runpod-volume/
```

## Alternative: Use vast.ai Instead

If RunPod supply issues persist, consider migrating to vast.ai:
- RTX 5090 32GB available at $0.336/hr ($19.49/month for 58hrs)
- Better availability in multiple regions
- 72% cheaper than RunPod A40 48GB
- See `VASTAI_MIGRATION_GUIDE.md` for details

## Post-Migration Checklist

- [ ] New volume contains all model files
- [ ] Mixtral model verified (19 shards present)
- [ ] EasyOCR models present
- [ ] Old volume backed up (optional)
- [ ] New serverless endpoint deployed
- [ ] Test classification request successful
- [ ] Backend environment variables updated
- [ ] Old volume deleted (after verification)
- [ ] Old pods terminated

## Quick Commands Reference

```bash
# Check volume contents
du -sh /runpod-volume/*

# Test Mixtral model loading
python -c "from transformers import AutoTokenizer; \
    AutoTokenizer.from_pretrained('mistralai/Mixtral-8x7B-Instruct-v0.1', \
    cache_dir='/runpod-volume/huggingface')"

# Monitor GPU memory
nvidia-smi --query-gpu=memory.used,memory.free --format=csv -l 1

# Check network speed
speedtest-cli
```

## Support

If you encounter issues:
1. RunPod Discord: https://discord.gg/runpod
2. RunPod Docs: https://docs.runpod.io/
3. Open ticket in RunPod Console > Support
