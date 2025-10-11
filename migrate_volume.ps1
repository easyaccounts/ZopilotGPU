# RunPod Network Volume Migration Script
# Downloads models locally, then uploads to new volume

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "🔄 RunPod Network Volume Migration" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

# Step 1: Set Hugging Face Token
Write-Host "`n📝 Step 1: Set Hugging Face Token" -ForegroundColor Yellow
if (-not $env:HUGGING_FACE_TOKEN) {
    Write-Host "❌ HUGGING_FACE_TOKEN not set!" -ForegroundColor Red
    Write-Host "Run: `$env:HUGGING_FACE_TOKEN='hf_your_token'" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Token found: $($env:HUGGING_FACE_TOKEN.Substring(0,10))..." -ForegroundColor Green

# Step 2: Download models locally
Write-Host "`n📦 Step 2: Downloading Models Locally (~93GB)" -ForegroundColor Yellow
Write-Host "⏱️  This will take 30-60 minutes..." -ForegroundColor Gray
python download_models_locally.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Model download failed!" -ForegroundColor Red
    exit 1
}

# Step 3: Compress cache
Write-Host "`n🗜️  Step 3: Compressing Model Cache" -ForegroundColor Yellow
$cacheDir = "model_cache"
$archiveName = "zopilot-models-cache.tar.gz"

if (Test-Path $archiveName) {
    Write-Host "Removing old archive..." -ForegroundColor Gray
    Remove-Item $archiveName
}

Write-Host "Compressing $cacheDir to $archiveName..." -ForegroundColor Gray
# Use tar.exe (built into Windows 10+)
tar -czf $archiveName -C . $cacheDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Compression failed!" -ForegroundColor Red
    exit 1
}

$archiveSize = (Get-Item $archiveName).Length / 1GB
Write-Host "✅ Archive created: $archiveName ($([math]::Round($archiveSize, 2)) GB)" -ForegroundColor Green

# Step 4: Instructions for upload
Write-Host "`n📤 Step 4: Upload to New RunPod Volume" -ForegroundColor Yellow
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host @"

Choose one of these methods:

METHOD A: RunPod Web Interface (Easiest)
-----------------------------------------
1. Create new network volume in TARGET region:
   - Go to: https://www.runpod.io/console/user/storage
   - Click "Create Network Volume"
   - Select region with good 32GB/48GB GPU availability
   - Size: 100GB
   - Name: zopilot-gpu-new

2. Deploy temporary CPU pod in NEW region:
   - Template: RunPod Pytorch
   - Attach: zopilot-gpu-new volume
   - Expose port 8000

3. Upload via web terminal or SFTP:
   - Open pod web terminal
   - Use "Upload Files" button to upload $archiveName
   - Or use SFTP (get credentials from pod settings)

4. Extract in pod terminal:
   cd /workspace
   tar -xzf $archiveName
   ls -lah huggingface/  # Verify extraction

METHOD B: Google Drive Bridge (Recommended for large files)
-------------------------------------------------------------
1. Upload archive to Google Drive from Windows
2. In RunPod pod terminal:
   apt-get update && apt-get install -y curl
   curl https://rclone.org/install.sh | sudo bash
   rclone config  # Configure Google Drive
   rclone copy gdrive:$archiveName /workspace/
   cd /workspace
   tar -xzf $archiveName

METHOD C: Direct Download in Pod (Slower but simplest)
-------------------------------------------------------
Skip local download, just run in new pod:
   cd /workspace
   python /app/download_models_locally.py

"@ -ForegroundColor White

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "`n✅ Local preparation complete!" -ForegroundColor Green
Write-Host "📦 Archive: $archiveName ($([math]::Round($archiveSize, 2)) GB)" -ForegroundColor Cyan
Write-Host "`nNext: Upload to new RunPod volume using one of the methods above" -ForegroundColor Yellow
