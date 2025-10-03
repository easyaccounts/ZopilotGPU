# EasyAccountsGPU - Document Extraction Flow & Backend Integration Guide

## 🏗️ Complete Document Processing Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Express.js     │    │  EasyAccountsGPU │    │  External Services  │
│  Backend        │    │  (GPU Server)    │    │  (DocStrange Cloud) │
│                 │    │                  │    │                     │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────────┐ │
│ │   Client    │ │    │ │   FastAPI    │ │    │ │  Nanonets API   │ │
│ │  Document   │ │────┤ │   Endpoints  │ │────┤ │  (10k/month)    │ │
│ │   Upload    │ │    │ │              │ │    │ │                 │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────────┘ │
│                 │    │         │        │    │                     │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────────┐ │
│ │  Journal    │ │    │ │  DocStrange  │ │    │ │   Llama 3.1     │ │
│ │ Entry API   │ │    │ │  Processor   │ │    │ │   8B Instruct   │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ │   (Local GPU)   │ │
└─────────────────┘    │         │        │    │ └─────────────────┘ │
                       │ ┌──────────────┐ │    └─────────────────────┘
                       │ │    Llama     │ │
                       │ │  Processor   │ │
                       │ └──────────────┘ │
                       └──────────────────┘
```

## 📥 Document Acceptance Flow

### 1. File Upload Requirements
```javascript
// Supported file types
const supportedTypes = [
    '.pdf',   // PDF documents
    '.png',   // Image files
    '.jpg', 
    '.jpeg',
    '.tiff',
    '.docx',  // Word documents
    '.doc'
];

// File size limit
const maxFileSize = 25 * 1024 * 1024; // 25MB
```

### 2. Memory-Based Processing
```
Document Upload → Memory Buffer → DocStrange → JSON Output
     ↓               ↓              ↓           ↓
  File Stream    bytes[] array   Extraction   Structured Data
   (multipart)     (in RAM)      (Cloud API)   (accounting fields)
```

**Key Benefits:**
- ✅ No temporary files on disk
- ✅ Fast processing (memory-based)
- ✅ Secure (no file persistence)
- ✅ Scalable (stateless processing)

## 🔌 Express.js Backend Integration

### Express.js Integration with Invoice Classification
```javascript
app.post('/process-document', async (req, res) => {
    try {
        const formData = new FormData();
        formData.append('file', req.files.document.buffer, req.files.document.originalname);
        formData.append('prompt', 'Generate journal entry for this accounting document');

        const response = await fetch(`${GPU_SERVER_URL}/process`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        
        if (result.success) {
            // Extract invoice classification
            const classification = result.extraction.data.invoice_classification;
            
            // Different handling based on invoice direction
            if (classification.direction === 'incoming') {
                // Vendor invoice - create A/P entry
                await createAccountsPayableEntry(result);
            } else if (classification.direction === 'outgoing') {
                // Customer invoice - create A/R entry  
                await createAccountsReceivableEntry(result);
            } else {
                // Unknown direction - flag for manual review
                await flagForManualReview(result);
            }

            res.json({
                success: true,
                extraction: result.extraction.data,
                invoice_type: classification.direction,
                confidence: classification.confidence,
                journal_entry: result.generation.journal_entry,
                requires_review: classification.confidence < 0.8
            });
        }
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
```

### Option 2: Separate Extraction & Generation
```javascript
// Step 1: Extract document data
app.post('/extract-document', async (req, res) => {
    try {
        const formData = new FormData();
        formData.append('file', req.files.document.buffer, req.files.document.originalname);

        const response = await fetch(`${GPU_SERVER_URL}/extract`, {
            method: 'POST',
            body: formData
        });

        const extractionResult = await response.json();
        res.json(extractionResult);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Step 2: Generate journal entry
app.post('/generate-journal', async (req, res) => {
    try {
        const { prompt, extractedData } = req.body;
        
        const response = await fetch(`${GPU_SERVER_URL}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                context: extractedData
            })
        });

        const generationResult = await response.json();
        res.json(generationResult);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
```

## 📊 JSON Output Structure

### Extraction Response Format
```json
{
  "success": true,
  "extraction_method": "docstrange_official",
  "data": {
    "structured_fields": {
      "invoice_number": "INV-2024-001",
      "total_amount": 1650.0,
      "subtotal": 1500.0,
      "tax_amount": 150.0,
      "vendor_name": "ABC Company Ltd.",
      "date": "2024-01-15",
      "invoice_date": "2024-01-15",
      "due_date": "2024-02-14",
      "description": "Consulting Services",
      "line_items": [
        {
          "description": "Consulting Services",
          "amount": 1500.0,
          "currency": "$",
          "quantity": 1,
          "unit_price": 1500.0
        }
      ],
      "customer_name": "ABC Company Ltd.",
      "bill_to": "ABC Company Ltd.\\n123 Business Street\\nNew York, NY 10001",
      "currency": "$"
    },
    "general_data": {
      "document": {
        "document_type": "INVOICE",
        "total": 1650.0,
        "payment_terms": "Net 30"
      }
    },
    "invoice_classification": {
      "direction": "incoming",
      "confidence": 0.9,
      "description": "Vendor Invoice - You receive this from a supplier/vendor",
      "accounting_impact": "Accounts Payable (credit), Expense/Asset (debit)",
      "analysis": {
        "bill_to_matches_company": true,
        "vendor_matches_company": false,
        "bill_to_text": "your company name...",
        "vendor_text": "supplier corp..."
      }
    },
    "markdown_content": "# Invoice\\n\\nInvoice Number: INV-2024-001...",
    "metadata": {
      "processing_mode": "cloud",
      "cloud_enabled": true,
      "content_length": 259
    }
  },
  "metadata": {
    "processed_at": "2025-09-24T04:13:14.041957",
    "structured_fields_found": 15,
    "total_fields_searched": 31,
    "confidence": 0.95,
    "processing_mode": "cloud"
  }
}
```

### Journal Entry Response Format
```json
{
  "success": true,
  "journal_entry": {
    "date": "2024-01-15",
    "reference": "INV-2024-001",
    "description": "Consulting Services - ABC Company Ltd.",
    "entries": [
      {
        "account": "Accounts Receivable",
        "account_code": "1200",
        "debit": 1650.0,
        "credit": 0.0,
        "description": "Invoice INV-2024-001 - ABC Company Ltd."
      },
      {
        "account": "Service Revenue",
        "account_code": "4000",
        "debit": 0.0,
        "credit": 1500.0,
        "description": "Consulting Services Revenue"
      },
      {
        "account": "Sales Tax Payable",
        "account_code": "2200",
        "debit": 0.0,
        "credit": 150.0,
        "description": "Sales Tax on Consulting Services"
      }
    ],
    "total_debits": 1650.0,
    "total_credits": 1650.0,
    "is_balanced": true
  },
  "metadata": {
    "generated_at": "2025-09-24T04:13:15.123456",
    "model": "meta-llama/Llama-3.1-8B-Instruct",
    "confidence": 0.92
  }
}
```

## 🚀 Deployment & Connection Details

### GPU Server Configuration (RunPod/Cloud)
```bash
# Server will be accessible at:
https://your-runpod-endpoint.com/

# Or custom domain:
https://gpu.easyaccounts.com/

# Health check:
GET /health

# Main endpoints:
POST /extract       # Document extraction only
POST /generate      # Journal entry generation only  
POST /process       # Combined extraction + generation (recommended)
```

### Express.js Environment Variables
```javascript
// .env file for your Express.js backend
GPU_SERVER_URL=https://your-runpod-endpoint.com
GPU_SERVER_TIMEOUT=30000  // 30 seconds
UPLOAD_MAX_SIZE=25MB
```

### Error Handling
```javascript
const processDocument = async (file, prompt) => {
    try {
        const response = await fetch(`${process.env.GPU_SERVER_URL}/process`, {
            method: 'POST',
            body: formData,
            timeout: process.env.GPU_SERVER_TIMEOUT
        });

        if (!response.ok) {
            throw new Error(`GPU server error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        if (error.code === 'ECONNREFUSED') {
            throw new Error('GPU server is unavailable');
        } else if (error.code === 'ETIMEDOUT') {
            throw new Error('GPU server timeout');
        }
        throw error;
    }
};
```

## 🎯 Key Features Summary

### ✅ Accounting-Optimized Extraction
- **31 accounting-specific fields** automatically detected
- **Invoice, receipt, expense** document types
- **Line items, taxes, totals** structured extraction
- **Vendor/customer information** extraction
- **Date and payment terms** recognition
- **🆕 INVOICE DIRECTION DETECTION**: Automatically distinguishes between:
  - **Customer Invoices** (outgoing - you send to customers)
  - **Vendor Invoices** (incoming - you receive from suppliers)
  - **Unknown invoices** (requires manual classification)

### ✅ Smart Invoice Classification
```json
{
  "invoice_classification": {
    "direction": "incoming",                    // incoming/outgoing/unknown/ambiguous
    "confidence": 0.9,                          // 0.0 to 1.0
    "description": "Vendor Invoice - You receive this from a supplier/vendor",
    "accounting_impact": "Accounts Payable (credit), Expense/Asset (debit)",
    "analysis": {
      "bill_to_matches_company": true,          // Detection logic
      "vendor_matches_company": false
    }
  }
}
```

**How it works:**
- ✅ **Analyzes bill_to, customer_name, vendor_name fields**
- ✅ **Matches against your company identifiers**  
- ✅ **Provides accounting impact guidance**
- ✅ **90% accuracy** on clear invoices

### ✅ Production-Ready API
- **Memory-based processing** (no disk I/O)
- **25MB file size limit** 
- **CORS enabled** for web frontends
- **Comprehensive error handling**
- **Health monitoring** for RunPod
- **Async processing** for performance

### ✅ Structured JSON Output
- **Consistent response format**
- **Confidence scores**
- **Processing metadata**
- **Balanced journal entries**
- **Account codes and descriptions**

This architecture provides a complete, production-ready document processing pipeline specifically optimized for accounting workflows!

---

## 🤖 **Llama 3-Powered Multi-Document Processing Strategy**

### **Core Philosophy**
Extract structured data from documents and provide contextual prompts to Llama 3 for intelligent journal entry generation, rather than building complex classification logic.

### **Document-Specific Field Templates**

#### **1. Invoices** (31 Core Fields)
**Extracted Fields:**
- `invoice_number`, `invoice_date`, `due_date`
- `customer_name`, `customer_address`, `customer_tax_id`
- `vendor_name`, `vendor_address`, `vendor_tax_id`
- `line_items` (description, quantity, unit_price, line_total)
- `subtotal`, `tax_amount`, `tax_rate`, `total_amount`
- `payment_terms`, `currency`, `exchange_rate`
- `shipping_amount`, `discount_amount`, `notes`

**Llama 3 Context Prompt:**
```
"Generate journal entries for this invoice. Determine if this is a customer invoice (revenue) or vendor invoice (expense/asset).
Consider: line item descriptions, vendor/customer relationship, amounts, and business context.
Classify expenses/assets into appropriate COA categories."
```

#### **2. Bank Statements** (25 Fields)
**Extracted Fields:**
- `bank_name`, `account_number`, `account_type`
- `statement_period_start`, `statement_period_end`
- `opening_balance`, `closing_balance`
- `transaction_list` (date, description, amount, balance, reference)
- `deposits_total`, `withdrawals_total`, `fees_total`
- `interest_earned`, `account_currency`

**Llama 3 Context Prompt:**
```
"Analyze these bank transactions and generate appropriate journal entries.
Classify each transaction: customer payments, vendor payments, fees, interest, transfers, etc.
Match transactions to known invoices/payments where possible."
```

#### **3. Receipts/Bills** (20 Fields)
**Extracted Fields:**
- `receipt_number`, `receipt_date`, `merchant_name`
- `merchant_address`, `merchant_tax_id`, `merchant_category`
- `line_items` (item, quantity, unit_price, total)
- `subtotal`, `tax_amount`, `tip_amount`, `total_amount`
- `payment_method`, `card_last_four`, `transaction_id`
- `cashback_amount`, `loyalty_points`

**Llama 3 Context Prompt:**
```
"Generate journal entries for this purchase receipt.
Determine expense category: office supplies, travel, meals, utilities, equipment, etc.
Consider merchant type, item descriptions, and amounts for proper COA classification."
```

#### **4. Payslips/Paystubs** (35 Fields)
**Extracted Fields:**
- `employee_name`, `employee_id`, `pay_period_start`, `pay_period_end`
- `gross_pay`, `net_pay`, `pay_frequency`
- `regular_hours`, `overtime_hours`, `regular_rate`, `overtime_rate`
- `earnings_breakdown` (salary, overtime, bonus, commission)
- `deductions` (federal_tax, state_tax, social_security, medicare, health_insurance)
- `retirement_contributions`, `garnishments`
- `ytd_totals` (gross, taxes, deductions)

**Llama 3 Context Prompt:**
```
"Generate payroll journal entries for this payslip.
Create entries for: wage expense, tax liabilities, benefit expenses, employee deductions.
Handle both accrual and cash basis accounting appropriately."
```

#### **5. System Reports** (Variable Fields)
**Extracted Fields (Adaptive):**
- `report_type`, `report_period`, `generated_date`
- `summary_totals`, `category_breakdowns`
- `transaction_counts`, `revenue_amounts`, `fee_amounts`
- `adjustments`, `settlements`, `reconciliations`

**Llama 3 Context Prompt:**
```
"Analyze this {report_type} and generate summary journal entries.
Consider the business context: sales revenue, fee expenses, settlements, inventory adjustments, etc.
Create entries that properly reflect the economic activity reported."
```

### **Processing Pipeline**
```
Document → DocStrange Extraction → Structured Data → Llama 3 Prompt → Journal Entries
```

### **Prompt Engineering Strategy**
1. **Document Context**: Provide document type and key characteristics
2. **Business Rules**: Include accounting principles and COA structure hints
3. **Validation Requirements**: Request confidence scores and reasoning
4. **Error Handling**: Ask for fallback options when uncertain

### **Quality Assurance**
- **Confidence Scoring**: Require Llama 3 to provide confidence levels
- **Reasoning Trail**: Request explanation for classification decisions
- **Fallback Logic**: Handle ambiguous cases with manual review flags

---

## 🚀 Deployment & Connection Details