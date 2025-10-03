# Mixtral 8x7B Deployment Checklist ✅

**Model:** mistralai/Mixtral-8x7B-Instruct-v0.1  
**Date:** October 3, 2025

---

## ✅ Pre-Deployment Checks

### **1. System Requirements**

- [ ] GPU with 24GB+ VRAM available
  ```bash
  nvidia-smi  # Check available memory
  ```

- [ ] Minimum 48GB free disk space for model
  ```bash
  df -h  # Check disk space
  ```

- [ ] Python 3.8+ installed
  ```bash
  python --version
  ```

- [ ] CUDA toolkit installed
  ```bash
  nvidia-smi  # Should show CUDA version
  ```

---

### **2. Dependencies**

- [ ] All packages installed
  ```bash
  cd ZopilotGPU
  pip install -r requirements.txt
  ```

- [ ] HuggingFace token configured
  ```bash
  # In .env file
  HUGGING_FACE_TOKEN=your_token_here
  ```

- [ ] Mixtral license accepted
  - [ ] Visit: https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1
  - [ ] Click "Agree and access repository"

---

### **3. Code Changes Verified**

- [ ] `app/llama_utils.py` updated with Mixtral config
- [ ] `app/main.py` API description updated
- [ ] Model name: `mistralai/Mixtral-8x7B-Instruct-v0.1`
- [ ] Prompt format: Mistral `[INST]` tags
- [ ] Generation parameters optimized

---

## 🚀 Deployment Steps

### **Step 1: Initial Test**

```bash
# Terminal 1: Start service
cd ZopilotGPU
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Expected: Model download starts (first time only, ~10 minutes)
# Watch for: "Loading mistralai/Mixtral-8x7B-Instruct-v0.1..."
```

**✅ Success indicators:**
```
INFO: Loading mistralai/Mixtral-8x7B-Instruct-v0.1 (MoE architecture)...
INFO: Note: Mixtral 8x7B requires ~24GB VRAM with 4-bit quantization
INFO: Model loaded successfully
INFO: Application startup complete
```

**❌ Failure indicators:**
```
RuntimeError: CUDA out of memory
OSError: model not found
ConnectionError: timeout downloading
```

---

### **Step 2: Health Check**

```bash
# Terminal 2: Test health endpoint
curl http://localhost:8000/health | jq
```

**✅ Expected response:**
```json
{
  "status": "healthy",
  "models_loaded": {
    "docstrange": true,
    "llama": true
  },
  "gpu_available": true,
  "memory_info": {
    "allocated": "23.5 GB",
    "reserved": "24.0 GB"
  }
}
```

- [ ] Status is "healthy"
- [ ] Both models loaded
- [ ] GPU available is true
- [ ] Memory usage ~23-24GB

---

### **Step 3: Extraction Test**

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "YOUR_TEST_PDF_URL",
    "document_type": "invoice"
  }' | jq
```

**✅ Expected response:**
```json
{
  "success": true,
  "extraction_method": "docstrange_official",
  "data": {
    "structured_fields": {
      "invoice_number": "...",
      "total_amount": 1500.00,
      ...
    }
  },
  "metadata": {
    "confidence": 0.85,
    "processed_at": "2025-10-03T..."
  }
}
```

- [ ] Success is true
- [ ] Data contains structured fields
- [ ] Confidence score present
- [ ] Response time < 30 seconds

---

### **Step 4: Generation Test**

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate a journal entry for this invoice",
    "context": {
      "invoice_number": "INV-001",
      "vendor_name": "Test Vendor",
      "total_amount": 1500.00,
      "invoice_date": "2025-10-03"
    }
  }' | jq
```

**✅ Expected response:**
```json
{
  "success": true,
  "journal_entry": {
    "date": "2025-10-03",
    "description": "Invoice from Test Vendor",
    "account_debits": [...],
    "account_credits": [...],
    "total_debit": 1500.00,
    "total_credit": 1500.00
  },
  "metadata": {
    "generated_at": "2025-10-03T...",
    "model": "mistralai/Mixtral-8x7B-Instruct-v0.1"
  }
}
```

- [ ] Success is true
- [ ] Valid JSON structure
- [ ] Debits equal credits
- [ ] Accounts make sense
- [ ] Response time < 10 seconds
- [ ] Model name shows Mixtral

---

### **Step 5: Complex Transaction Test**

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate journal entries for multi-currency invoice with tax",
    "context": {
      "invoice_number": "INV-002",
      "vendor_name": "International Supplier",
      "amount_foreign": 1000.00,
      "currency": "EUR",
      "exchange_rate": 1.10,
      "amount_usd": 1100.00,
      "tax_rate": 0.10,
      "tax_amount": 110.00,
      "total": 1210.00
    }
  }' | jq
```

**✅ Expected:**
- [ ] Handles multi-currency correctly
- [ ] Tax calculated properly
- [ ] Exchange rate applied
- [ ] Multiple debit/credit lines
- [ ] All amounts balance

---

### **Step 6: Error Handling Test**

```bash
# Test with invalid input
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "",
    "context": {}
  }' | jq
```

**✅ Expected:**
- [ ] Returns error gracefully
- [ ] Appropriate HTTP status code
- [ ] Error message is helpful
- [ ] Service remains running

---

### **Step 7: Performance Test**

```bash
# Run 10 requests and measure
for i in {1..10}; do
  time curl -X POST http://localhost:8000/generate \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Test", "context": {"amount": 100}}' \
    > /dev/null 2>&1
done
```

**✅ Expected:**
- [ ] Average response time: 3-5 seconds
- [ ] No memory errors
- [ ] Consistent performance
- [ ] No crashes

---

## 📊 Monitoring Setup

### **Step 8: GPU Monitoring**

```bash
# Start GPU monitoring in separate terminal
watch -n 1 nvidia-smi
```

**Monitor these metrics:**
- [ ] GPU memory usage: ~23-24GB
- [ ] GPU utilization: 80-100% during inference
- [ ] Temperature: < 85°C
- [ ] Power draw: Normal for your GPU

---

### **Step 9: Application Logs**

```bash
# View logs
tail -f gpu_service.log

# Or with timestamps
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
```

**Watch for:**
- [ ] No error messages
- [ ] Successful inference logs
- [ ] Reasonable processing times
- [ ] No memory warnings

---

## ✅ Production Readiness

### **Step 10: Integration Test**

Test full pipeline with backend:

```bash
# From zopilot-backend
curl -X POST http://localhost:8080/api/documents/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "document=@test_invoice.pdf" \
  -F "category=invoice"

# Wait for processing (check logs)

# Verify extracted_data populated
curl http://localhost:8080/api/documents/DOCUMENT_ID \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.extracted_data'
```

**✅ Expected:**
- [ ] Document uploaded successfully
- [ ] GPU extraction triggered
- [ ] Data extracted correctly
- [ ] Status set to 'extracted'
- [ ] Response stored in database

---

### **Step 11: Stress Test**

```bash
# Upload multiple documents
for i in {1..5}; do
  curl -X POST http://localhost:8080/api/documents/upload \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -F "document=@test_invoice_${i}.pdf" \
    -F "category=invoice" &
done
wait
```

**✅ Expected:**
- [ ] All requests handled
- [ ] No OOM errors
- [ ] Queue processes correctly
- [ ] All documents extracted

---

### **Step 12: Error Recovery**

```bash
# Test with corrupted file
curl -X POST http://localhost:8000/extract \
  -F "file=@corrupted.pdf"

# Test with oversized file (>25MB)
curl -X POST http://localhost:8000/extract \
  -F "file=@huge.pdf"
```

**✅ Expected:**
- [ ] Errors handled gracefully
- [ ] Appropriate error messages
- [ ] Service keeps running
- [ ] No crashes

---

## 🎯 Final Checklist

### **Before Going Live:**

- [ ] All tests pass
- [ ] Performance acceptable
- [ ] Error handling works
- [ ] Monitoring in place
- [ ] Logs being captured
- [ ] GPU memory stable
- [ ] No memory leaks
- [ ] Documentation complete
- [ ] Team trained on new model
- [ ] Rollback plan ready

### **Documentation:**

- [ ] ✅ MIXTRAL_UPGRADE_GUIDE.md - Read
- [ ] ✅ MIXTRAL_UPGRADE_SUMMARY.md - Read
- [ ] ✅ README.md - Updated
- [ ] ✅ This checklist - Completed

---

## 🚀 Go Live!

Once all checks pass:

1. **Update production config**
   ```bash
   # Set production environment variables
   ENVIRONMENT=production
   ZOPILOT_GPU_URL=https://your-gpu-service.com
   ```

2. **Deploy to production GPU**
   ```bash
   # Deploy with your method (Docker, systemd, etc.)
   ```

3. **Monitor closely for first 24 hours**
   - Watch GPU metrics
   - Monitor error rates
   - Check response times
   - Verify accuracy

4. **Celebrate!** 🎉
   You're now running Mixtral 8x7B in production!

---

## 📞 Support

**Issues during deployment?**

1. Check the troubleshooting section in `MIXTRAL_UPGRADE_GUIDE.md`
2. Review application logs
3. Verify GPU status with `nvidia-smi`
4. Test with simple requests first
5. Increase logging verbosity if needed

**Common fixes:**
- Restart service: `Ctrl+C` then re-run uvicorn
- Clear GPU cache: `python -c "import torch; torch.cuda.empty_cache()"`
- Check VRAM: `nvidia-smi` should show ~1GB free
- Verify model: Check HuggingFace token and license

---

**Status:** Ready for deployment ✅  
**Next Step:** Run through this checklist systematically!
