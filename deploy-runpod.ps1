# ZopilotGPU RunPod Serverless Deployment Script
# Run this from PowerShell to deploy to RunPod

Write-Host "🚀 ZopilotGPU RunPod Deployment" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$DOCKER_USERNAME = Read-Host "Enter your Docker Hub username"
$IMAGE_NAME = "zopilot-gpu"
$IMAGE_TAG = "latest"
$FULL_IMAGE = "${DOCKER_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

Write-Host ""
Write-Host "📦 Building Docker image: $FULL_IMAGE" -ForegroundColor Yellow
Write-Host ""

# Build Docker image
docker build -t $FULL_IMAGE .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Build successful!" -ForegroundColor Green
Write-Host ""
Write-Host "📤 Pushing to Docker Hub..." -ForegroundColor Yellow
Write-Host ""

# Push to Docker Hub
docker push $FULL_IMAGE

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker push failed! Make sure you're logged in: docker login" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Push successful!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Go to: https://runpod.io/console/serverless" -ForegroundColor White
Write-Host "2. Click '+ New Endpoint'" -ForegroundColor White
Write-Host "3. Use this image: $FULL_IMAGE" -ForegroundColor Yellow
Write-Host "4. Set environment variables:" -ForegroundColor White
Write-Host "   - ZOPILOT_GPU_API_KEY=b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI" -ForegroundColor Gray
Write-Host "   - HUGGING_FACE_TOKEN=your_token" -ForegroundColor Gray
Write-Host "   - ALLOWED_ORIGINS=https://zopilot-backend-production.up.railway.app" -ForegroundColor Gray
Write-Host "5. Select GPU: RTX 4090 or A5000" -ForegroundColor White
Write-Host "6. Set Volume: 100GB at /app/models" -ForegroundColor White
Write-Host "7. Deploy!" -ForegroundColor White
Write-Host ""
Write-Host "📖 Full guide: See RUNPOD_SERVERLESS_GUIDE.md" -ForegroundColor Cyan
Write-Host ""
