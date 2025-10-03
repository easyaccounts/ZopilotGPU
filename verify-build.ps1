# Pre-deployment verification script for ZopilotGPU
# Run this before pushing to GitHub/RunPod

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "ZopilotGPU Pre-Deployment Checks" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0

# Check 1: Python syntax
Write-Host "[1/5] Checking Python syntax..." -ForegroundColor Yellow
$files = @("handler.py", "app/main.py", "app/llama_utils.py", "app/docstrange_utils.py")
foreach ($file in $files) {
    python -m py_compile $file 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file has syntax errors" -ForegroundColor Red
        $ErrorCount++
    }
}
Write-Host ""

# Check 2: Requirements file exists
Write-Host "[2/5] Checking requirements.txt..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    $lines = (Get-Content "requirements.txt" | Measure-Object -Line).Lines
    Write-Host "  ✅ requirements.txt found ($lines packages)" -ForegroundColor Green
} else {
    Write-Host "  ❌ requirements.txt missing" -ForegroundColor Red
    $ErrorCount++
}
Write-Host ""

# Check 3: Dockerfile exists
Write-Host "[3/5] Checking Dockerfile..." -ForegroundColor Yellow
if (Test-Path "Dockerfile") {
    Write-Host "  ✅ Dockerfile found" -ForegroundColor Green
} else {
    Write-Host "  ❌ Dockerfile missing" -ForegroundColor Red
    $ErrorCount++
}
Write-Host ""

# Check 4: Environment file check
Write-Host "[4/5] Checking .env files..." -ForegroundColor Yellow
if (Test-Path ".env.production") {
    Write-Host "  ✅ .env.production found" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  .env.production missing (optional)" -ForegroundColor Yellow
}
if (Test-Path ".env.example") {
    Write-Host "  ✅ .env.example found" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  .env.example missing" -ForegroundColor Yellow
}
Write-Host ""

# Check 5: Test imports (requires dependencies installed)
Write-Host "[5/5] Testing Python imports..." -ForegroundColor Yellow
$testImport = @"
try:
    import fastapi
    import uvicorn
    import transformers
    import torch
    print('✅ Core dependencies available')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
    exit(1)
"@

$testImport | python 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Import test passed" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Some dependencies not installed locally (OK if deploying to RunPod)" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "======================================" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "✅ ALL CHECKS PASSED - Safe to deploy!" -ForegroundColor Green
} else {
    Write-Host "❌ $ErrorCount ERROR(S) FOUND - Fix before deploying!" -ForegroundColor Red
    exit 1
}
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To deploy:" -ForegroundColor Cyan
Write-Host "  git add ." -ForegroundColor White
Write-Host "  git commit -m 'Your message'" -ForegroundColor White
Write-Host "  git push" -ForegroundColor White
