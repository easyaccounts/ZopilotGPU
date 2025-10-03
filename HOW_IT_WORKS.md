# How the 3-Layer System + Taxonomy Work Together
## Visual Guide

---

## Document Roles

### 📋 CLASSIFICATION_SYSTEM.md (Process Logic)
**Purpose:** How to classify documents using 3-layer analysis  
**Used by:** Mixtral classification prompts  
**Contains:** Rules, patterns, decision trees  

### 📚 DOCUMENT_TAXONOMY.md (Reference Encyclopedia)
**Purpose:** Comprehensive reference of document types  
**Used by:** Business users, developers, validation  
**Contains:** 60+ document types with GL routing details  

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. DOCUMENT ARRIVES                                             │
│ Example: Supplier sends us an invoice PDF                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. DOCSTRANGE EXTRACTION                                        │
│ Extracts: invoice_number, vendor_name, amount, line_items, etc.│
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. LAYER 1 ANALYSIS (Structure)                                │
│ Prompt: "What pattern does this match?"                        │
│                                                                 │
│ Mixtral analyzes:                                              │
│ ✓ Two parties (from + to) → Both present                      │
│ ✓ Line items → Yes                                            │
│ ✓ Totals breakdown → Subtotal, tax, total                     │
│                                                                 │
│ Decision: PATTERN_2_BILATERAL_INVOICE                          │
│ Confidence: 0.95                                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. LAYER 2 ANALYSIS (Semantics)                                │
│ Prompt: "What does this mean financially?"                     │
│                                                                 │
│ Mixtral analyzes:                                              │
│ ✓ "From: Acme Supplies" → We are receiver                     │
│ ✓ "To: Our Company" → We are buyer                            │
│ ✓ Document title: "Invoice" → They're billing us              │
│                                                                 │
│ Decision:                                                       │
│ - money_direction: "money_out"                                 │
│ - transaction_type: "purchase"                                 │
│ - we_are: "buyer"                                              │
│ - payment_status: "unpaid" (due date in future)                │
│ Confidence: 0.92                                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. LAYER 3 MAPPING (Business Context)                          │
│ Prompt: "What accounting action should we take?"               │
│                                                                 │
│ Mixtral maps using CLASSIFICATION_SYSTEM rules:               │
│ ✓ money_out + purchase + unpaid → PURCHASES category          │
│ ✓ PATTERN_2 + unpaid → SUBLEDGER_ONLY                        │
│ ✓ PURCHASES + SUBLEDGER_ONLY → record_supplier_bill          │
│                                                                 │
│ Decision:                                                       │
│ - category: "PURCHASES"                                        │
│ - action: "record_supplier_bill"                               │
│ - gl_impact: "SUBLEDGER_ONLY"                                  │
│ - subledger: "accounts_payable"                                │
│ Confidence: 0.90                                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. VALIDATION & ENRICHMENT                                     │
│ Now consult DOCUMENT_TAXONOMY.md for details                   │
│                                                                 │
│ Look up: PURCHASES → supplier_bill section                     │
│                                                                 │
│ Get from taxonomy:                                             │
│ ✓ Required fields: [invoice_number, vendor_name, amount, date]│
│ ✓ Financial impact:                                            │
│     Debit: Expense Account (via AP posting)                    │
│     Credit: Accounts Payable (Subledger)                       │
│ ✓ Approval workflow: May require approval if > threshold       │
│ ✓ Alternative actions: [record_expense, match_to_po]          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. FINAL DECISION                                               │
│                                                                 │
│ Combined confidence: (0.95 + 0.92 + 0.90) / 3 = 0.92          │
│ Threshold check: 0.92 >= 0.85 → AUTO-PROCESS ✓                │
│                                                                 │
│ Action: Create supplier bill in accounting system              │
│ Posting: Dr Expense, Cr AP (Subledger)                        │
│ Approval: Check if amount > $10,000                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Concrete Example: Amazon Settlement Report

### Input Document
```
Amazon Seller Central - Settlement Report
Settlement ID: 12345678901234567890
Period: Sep 1-15, 2025

Gross Product Sales: $15,234.50
Amazon Fees: -$2,285.18
FBA Fees: -$823.45
Promotional Rebates: -$150.00
-----------------------------------
Net Proceeds: $11,975.87

Transferred to Bank Account: ****1234
Transfer Date: Sep 16, 2025
```

### Layer 1 Analysis (Structure)

```yaml
Input to Mixtral:
  "Analyze structure of this document using 6 patterns..."

Mixtral identifies:
  - Multiple amount breakdowns ✓
  - Gross → Fees → Net pattern ✓
  - Transfer/payout information ✓
  - Period-based report ✓
  
Output:
  pattern: "PATTERN_4_MARKETPLACE_SETTLEMENT"
  complexity: "complex"
  confidence: 0.94
```

### Layer 2 Analysis (Semantics)

```yaml
Input to Mixtral:
  "Structure is PATTERN_4_MARKETPLACE_SETTLEMENT.
   What does this mean financially?"

Mixtral identifies:
  - Gross sales = revenue to us (money_in)
  - Fees = expense from us (money_out)
  - Net payout = bank deposit (money_in)
  - Multiple transaction types in one document
  
Output:
  money_direction: "mixed" (in + out)
  transaction_type: "marketplace_settlement"
  payment_status: "paid" (transferred to bank)
  confidence: 0.89
```

### Layer 3 Mapping (Business Context)

```yaml
Input to Mixtral:
  "Structure: PATTERN_4_MARKETPLACE_SETTLEMENT
   Semantics: mixed direction, marketplace_settlement, paid
   What category and action?"

Mixtral maps:
  - PATTERN_4 → Always complex marketplace transaction
  - Multiple components → MIXED_IMPACT
  - Specific action for this pattern exists
  
Output:
  category: "SALES" (primary) + "EXPENSES" (fees)
  action: "import_marketplace_settlement"
  gl_impact: "MIXED_IMPACT"
  subledgers: ["accounts_receivable", "none_for_fees"]
  confidence: 0.91
```

### Validation with Taxonomy

```yaml
System looks up in DOCUMENT_TAXONOMY.md:
  → Section: SALES Documents → 1.5 Marketplace Settlement Report

Gets detailed posting instructions:
  transaction_1_sales:
    debit: Accounts Receivable (Subledger)
    credit: Sales Revenue
    
  transaction_2_fees:
    debit: Marketplace Fees Expense (GL)
    credit: Accounts Receivable (Subledger)
    
  transaction_3_payout:
    debit: Bank Account (GL)
    credit: Accounts Receivable (Subledger)
    
Gets validation rules:
  required_fields: [settlement_id, gross_sales, marketplace_fee, net_payout, date]
  ✓ All present
  
  platforms: [Amazon, eBay, Shopify, Etsy, Walmart]
  ✓ Amazon identified
```

### Final Output

```json
{
  "classification": {
    "category": "SALES",
    "subcategory": "marketplace_settlement",
    "action": "import_marketplace_settlement",
    "gl_impact": "MIXED_IMPACT",
    "confidence": 0.91
  },
  "posting_instructions": [
    {
      "type": "sales_revenue",
      "debit": {"account": "Accounts Receivable", "amount": 15234.50, "subledger": "AR"},
      "credit": {"account": "Sales Revenue", "amount": 15234.50, "type": "GL"}
    },
    {
      "type": "marketplace_fees",
      "debit": {"account": "Marketplace Fees Expense", "amount": 3258.63, "type": "GL"},
      "credit": {"account": "Accounts Receivable", "amount": 3258.63, "subledger": "AR"}
    },
    {
      "type": "bank_deposit",
      "debit": {"account": "Bank Account ****1234", "amount": 11975.87, "type": "GL"},
      "credit": {"account": "Accounts Receivable", "amount": 11975.87, "subledger": "AR"}
    }
  ],
  "requires_approval": false,
  "decision": "AUTO_PROCESS"
}
```

---

## When to Use Each Document

### During Classification (Runtime)

```
┌─────────────────────────────────────────────────┐
│ USE: CLASSIFICATION_SYSTEM.md                  │
│                                                 │
│ For:                                           │
│ • Building Mixtral prompts (Layer 1, 2, 3)    │
│ • Decision rules (if/then logic)               │
│ • Pattern matching (6 base patterns)          │
│ • Confidence calculation                       │
│ • Validation thresholds                        │
│                                                 │
│ This is your PROCESS GUIDE                     │
└─────────────────────────────────────────────────┘
```

### After Classification (Validation & Execution)

```
┌─────────────────────────────────────────────────┐
│ USE: DOCUMENT_TAXONOMY.md                      │
│                                                 │
│ For:                                           │
│ • Detailed GL posting instructions             │
│ • Required field validation                    │
│ • Industry-specific variations                 │
│ • Approval workflow rules                      │
│ • Alternative actions if primary fails         │
│                                                 │
│ This is your REFERENCE ENCYCLOPEDIA            │
└─────────────────────────────────────────────────┘
```

---

## Why Two Documents?

### Problem with One Big Document
❌ Too complex for LLM prompts (token overload)  
❌ Mixes process logic with reference data  
❌ Hard to maintain (changes affect everything)  
❌ Confusing for both LLM and humans  

### Solution: Separation of Concerns

```
CLASSIFICATION_SYSTEM.md (Thin & Focused)
├─ Only what LLM needs to decide
├─ Clear prompts, simple rules
├─ 6 patterns, 8 categories, 4 GL impacts
└─ Fast classification decisions

DOCUMENT_TAXONOMY.md (Deep & Comprehensive)
├─ Everything else (60+ document types)
├─ Detailed GL posting instructions
├─ Industry variations
└─ Used AFTER classification for execution
```

---

## Implementation Flow

### Step 1: Classification (Use CLASSIFICATION_SYSTEM.md)

```javascript
// Build prompts from CLASSIFICATION_SYSTEM.md
const layer1 = await mixtral.classify(layer1Prompt);
const layer2 = await mixtral.classify(layer2Prompt);
const layer3 = await mixtral.classify(layer3Prompt);

// Result: Basic classification
{
  category: "PURCHASES",
  action: "record_supplier_bill",
  gl_impact: "SUBLEDGER_ONLY",
  confidence: 0.90
}
```

### Step 2: Enrichment (Use DOCUMENT_TAXONOMY.md)

```javascript
// Look up detailed info in DOCUMENT_TAXONOMY.md
const taxonomy = loadTaxonomy();
const details = taxonomy.PURCHASES.supplier_bill;

// Get posting instructions
const postingInstructions = details.financial_impact;
const requiredFields = details.field_patterns.required;
const approvalRules = details.approval_workflow;

// Validate
if (!hasAllRequiredFields(document, requiredFields)) {
  return flagForReview("Missing required fields");
}

if (document.amount > approvalRules.threshold) {
  return flagForApproval("Amount exceeds threshold");
}

// Execute
executePosting(postingInstructions);
```

---

## Quick Decision Guide

### "Should I use CLASSIFICATION_SYSTEM or TAXONOMY?"

```
┌────────────────────────────────────────────────────┐
│ Question: Am I building a Mixtral prompt?         │
│ YES → Use CLASSIFICATION_SYSTEM.md                │
│ NO  → Continue below                              │
└────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────┐
│ Question: Do I need GL posting instructions?      │
│ YES → Use DOCUMENT_TAXONOMY.md                    │
│ NO  → Continue below                              │
└────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────┐
│ Question: Do I need industry-specific details?    │
│ YES → Use DOCUMENT_TAXONOMY.md                    │
│ NO  → Continue below                              │
└────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────┐
│ Question: Am I validating required fields?        │
│ YES → Use DOCUMENT_TAXONOMY.md                    │
│ NO  → You probably need CLASSIFICATION_SYSTEM     │
└────────────────────────────────────────────────────┘
```

---

## Summary

### 📋 CLASSIFICATION_SYSTEM.md
- **Role:** Process engine
- **Size:** ~15KB, focused
- **Used:** During classification (Mixtral prompts)
- **Contains:** 6 patterns, 8 categories, 3-layer logic
- **Goal:** Fast, accurate classification

### 📚 DOCUMENT_TAXONOMY.md
- **Role:** Reference encyclopedia
- **Size:** ~60KB, comprehensive
- **Used:** After classification (validation & execution)
- **Contains:** 60+ document types, GL postings, industry details
- **Goal:** Complete execution instructions

### 🔄 Together They Provide:
1. **Fast classification** (CLASSIFICATION_SYSTEM)
2. **Accurate execution** (TAXONOMY)
3. **Maintainability** (separate concerns)
4. **Scalability** (add industries without bloating prompts)

---

**The 3-layer system classifies → The taxonomy executes**
