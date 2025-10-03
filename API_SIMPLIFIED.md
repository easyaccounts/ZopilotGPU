# ZopilotGPU API - Simplified 2-Endpoint Design

## 🎯 Overview

Simplified GPU service with **2 main endpoints**:
1. **`/extract`** - Document extraction using Docstrange
2. **`/prompt`** - AI prompting using Mixtral 8x7B

Plus health check endpoint for monitoring.

---

## 📡 Endpoints

### 1. GET `/health` - Health Check
**Authentication**: Public (no API key required)

**Response**:
```json
{
  "status": "healthy",
  "models_loaded": {
    "llama": true,
    "docstrange": true
  },
  "gpu_available": true,
  "memory_info": { ... }
}
```

---

### 2. POST `/extract` - Document Extraction
**Authentication**: Required (API key)

**Purpose**: Extract structured data from documents (invoices, receipts, bills) using Docstrange OCR.

**Request**:
```json
{
  "document_url": "https://r2-storage-url/document.pdf",
  "document_id": "doc-123-456",
  "document_type": "invoice"
}
```

**Response**:
```json
{
  "success": true,
  "document_id": "doc-123-456",
  "extraction_method": "docstrange_local",
  "data": {
    "invoice_number": "INV-2024-001",
    "date": "2024-03-15",
    "total": 1500.00,
    "vendor": "ACME Corp",
    "line_items": [...]
  },
  "metadata": {
    "processed_at": "2024-03-15T10:30:00Z",
    "confidence_score": 0.95,
    "processing_time_ms": 3421
  }
}
```

**Use Cases**:
- Step 1 of document processing pipeline
- Extract invoice/receipt data
- OCR scanned documents
- Get structured JSON from PDFs

---

### 3. POST `/prompt` - Mixtral AI Prompting
**Authentication**: Required (API key)

**Purpose**: Send any prompt to Mixtral 8x7B and get AI-generated response.

**Request**:
```json
{
  "prompt": "Analyze this invoice and determine the accounting category",
  "context": {
    "invoice_number": "INV-001",
    "vendor": "Office Supplies Inc",
    "total": 250.00,
    "items": ["Paper", "Pens", "Folders"]
  }
}
```

**Response**:
```json
{
  "success": true,
  "output": "Based on the invoice, this should be categorized as 'Office Supplies' expense...",
  "metadata": {
    "generated_at": "2024-03-15T10:30:05Z",
    "prompt_length": 68,
    "context_provided": true,
    "model": "mistralai/Mixtral-8x7B-Instruct-v0.1"
  }
}
```

**Use Cases**:
- Generate journal entries
- Categorize transactions
- Analyze document content
- Determine actions
- Extract insights
- Any AI reasoning task

**Flexible Output**: The `output` field can contain:
- Plain text explanations
- JSON strings (parse on backend)
- Structured data
- Analysis results

---

## 🔐 Authentication

All endpoints (except `/health`) require API key:

```bash
# Option 1: Authorization Bearer
Authorization: Bearer your_api_key_here

# Option 2: X-API-Key header
X-API-Key: your_api_key_here
```

---

## 💡 Usage Examples

### Example 1: Extract Invoice Data
```bash
curl -X POST https://your-gpu-url/extract \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "https://storage.com/invoice.pdf",
    "document_id": "doc-123",
    "document_type": "invoice"
  }'
```

### Example 2: Generate Journal Entry
```bash
curl -X POST https://your-gpu-url/prompt \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a journal entry for this invoice",
    "context": {
      "invoice_number": "INV-001",
      "vendor": "ACME Corp",
      "total": 1500.00,
      "date": "2024-03-15"
    }
  }'
```

### Example 3: Categorize Transaction
```bash
curl -X POST https://your-gpu-url/prompt \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What accounting module and action should this go to? Reply with JSON: {\"module\": \"...\", \"action\": \"...\"}",
    "context": {
      "document_type": "invoice",
      "vendor": "Office Depot",
      "total": 250.00
    }
  }'
```

### Example 4: Analyze Without Context
```bash
curl -X POST https://your-gpu-url/prompt \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What are the key fields typically found in an invoice?"
  }'
```

---

## 🔄 Integration Flow

### Step 1: Extract Document
```
Backend → /extract → Returns structured data
```

### Step 2: Prompt for Analysis
```
Backend → /prompt (with extracted data) → Returns AI insights
```

### Step 3: Use Output
```
Backend processes AI output → Take action
```

---

## ⚡ Performance

- **Extraction**: 3-8 seconds
- **Prompting**: 5-10 seconds  
- **Cold start**: 2-5 minutes (model loading)
- **First download**: 15-30 minutes (47GB model)

---

## 📊 Comparison to Old API

### Old Design (4 endpoints):
- ❌ `/extract` - Extract only
- ❌ `/generate` - Fixed journal entry generation
- ❌ `/process` - Combined but rigid
- ❌ `/health` - Health check

### New Design (2 endpoints):
- ✅ `/extract` - Extract only (same)
- ✅ `/prompt` - **Flexible AI prompting** (replaces generate + adds flexibility)
- ✅ `/health` - Health check (same)

**Benefits**:
- Simpler API surface
- More flexible (any prompt, any task)
- Backend controls the logic
- Can generate journal entries, categorize, analyze, or anything else
- No need to update GPU code for new use cases

---

## 🎯 When to Use Each Endpoint

**Use `/extract` when**:
- Processing uploaded documents
- Need structured data from PDFs
- OCR scanned images
- First step of pipeline

**Use `/prompt` when**:
- Need AI reasoning/analysis
- Generate journal entries
- Categorize transactions
- Determine next action
- Extract insights from data
- Any natural language task

---

## 🔧 Configuration

**Environment Variables**:
```bash
ZOPILOT_GPU_API_KEY=b8uGNkdOJtbzd9mOgoUGg28d2Z94rAD2ysFuBI5EhsI
ALLOWED_ORIGINS=https://your-backend.com
HUGGING_FACE_TOKEN=your_hf_token
NANONETS_API_KEY=your_nanonets_key  # Optional
```

---

## 📝 Notes

- Both endpoints are stateless
- No data stored on GPU
- Documents processed in memory
- Context data helps improve AI accuracy
- Prompt can be any natural language instruction
- Output format depends on your prompt
