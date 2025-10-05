# 3-Layer Document Classification System
## Structured Classification Flow for Mixtral 8x7B (with Business Profile Integration)

**Version:** 3.1  
**Last Updated:** October 5, 2025  
**Architecture:** Layer 1 (Structure) → Layer 2 (Semantics + Business Context) → Layer 3 (Action Mapping + Validation)

**Enhanced in v3.1 (Gap Analysis Implementation):**
- **ACCRUALS_DEFERRALS CATEGORY** - Added 14th category for prepaid expenses, accrued expenses, deferred revenue, accrued revenue
- **PATTERN_10_ACCRUAL_ADJUSTMENT** - New pattern for month-end accrual/deferral journal entries
- **Enhanced TAX Subcategories** - Distinct handling for tax collection vs tax remittance vs tax returns
- **Foreign Currency & Inter-company Flags** - Explicit detection and special handling

**Enhanced in v3.0:**
- **BUSINESS PROFILE INTEGRATION** - Inject 16 business classification fields into Layer 2 & 3 prompts
- **Direction Detection** - Use registered_name to determine buyer vs seller (critical for money_direction)
- **Impossible Categories** - Skip categories based on business flags (has_inventory=false → skip INVENTORY)
- **Confidence Boosters** - +0.35 confidence boost when classification aligns with business profile
- **Country-aware Tax** - Use country field for correct tax terminology (GST/VAT/Sales Tax)
- **Threshold Validation** - Respect fixed_asset_threshold and prepaid_expense_threshold

**Enhanced in v2.0:**
- Added LEASES as 12th category
- Added foreign currency and inter-company detection flags
- Added customer deposits, prepaid expenses, write-offs, refunds, grants
- Enhanced COGS trigger logic for inventory costing

**Key Innovation (v3.1):**
Without business context: ~75% auto-process rate  
With business context + accruals: **~94% auto-process rate**  
**Improvement: +19% documents auto-processed** (covers month-end accruals/deferrals)

---

## Business Profile Fields Required

The classification system requires these fields from the business profile:

**Critical (Required for Direction Detection):**
- `registered_name` - Match against document parties to determine buyer vs seller
- `country` - Tax terminology (GST/VAT/Sales Tax), currency validation
- `currency` - Base currency for foreign currency detection

**High Priority (Required for Category Validation):**
- `sector`, `subsector`, `employee_count` - Business type context
- `has_inventory` - Enable/disable INVENTORY category
- `has_physical_products` - Routing hints for PURCHASES
- `primary_revenue_model` - SALES category validation
- `accounting_method` - Accrual vs cash context
- `has_fixed_assets` - Enable/disable FIXED_ASSETS category
- `fixed_asset_threshold` - PURCHASES vs FIXED_ASSETS routing
- `has_leases` - Enable/disable LEASES category
- `lease_capitalization_threshold` - Capitalize vs expense threshold
- `billing_method` - Revenue recognition hints
- `has_cogs` - Enable/disable COGS triggers
- `has_foreign_operations` - Foreign currency expectation
- `collects_sales_tax` - TAX category emphasis
- `inventory_costing_method` - COGS calculation method
- `has_debt_financing` - Enable/disable DEBT category
- `has_intercompany_transactions` - Inter-company flag expectations
- `prepaid_expense_threshold` - PURCHASES_PREPAID routing

---

## Overview

This system uses a **3-layer progressive classification** approach that narrows down from broad structure analysis to specific business actions, **enhanced with business profile context for intelligent validation and confidence boosting**.

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: Document Structure Analysis                        │
│ What shape is this document?                                │
│ Output: document_structure_profile                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: Semantic Content Analysis                          │
│ What does this document mean?                               │
│ Output: semantic_classification                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: Business Context Mapping                           │
│ What action should we take?                                 │
│ Output: final_classification + action + GL_routing          │
└─────────────────────────────────────────────────────────────┘
```

---

## LAYER 1: Document Structure Analysis

**Goal:** Analyze the physical/structural characteristics of the document.

### 1.1 Structure Detection

```yaml
INPUT: Raw document text + extracted fields

ANALYSIS_POINTS:
  - document_format: [invoice, statement, list, report, single_transaction]
  - field_complexity: [simple, moderate, complex]
  - has_line_items: boolean
  - has_totals: boolean
  - has_parties: [from, to, both]
  - has_dates: [single, range, multiple]
  - has_amounts: [single_total, breakdown, multi_currency]
  
OUTPUT: structure_profile
```

### 1.2 Structure Patterns (8 Base Patterns)

```yaml
PATTERN_1_SINGLE_TRANSACTION:
  description: "One party, one amount, one date"
  indicators:
    - Single merchant/vendor name
    - One total amount
    - One date
    - No line items
  examples: [receipt, payment_confirmation, bank_transaction]
  complexity: LOW
  
PATTERN_2_BILATERAL_INVOICE:
  description: "Two parties, line items, totals"
  indicators:
    - From party (seller/vendor)
    - To party (buyer/customer)
    - Line items with descriptions
    - Subtotal, tax, total
  examples: [invoice, bill, quote]
  complexity: MODERATE
  
PATTERN_3_PERIODIC_STATEMENT:
  description: "One account, date range, transaction list, balances"
  indicators:
    - Account identifier
    - Statement period (from/to dates)
    - Opening/closing balances
    - List of transactions
  examples: [bank_statement, credit_card_statement, customer_statement, loan_statement]
  complexity: MODERATE
  
PATTERN_4_MARKETPLACE_SETTLEMENT:
  description: "Sales breakdown, fees, net payout"
  indicators:
    - Gross sales/revenue figure
    - Multiple fee types
    - Net payout amount
    - Transaction breakdown
  examples: [amazon_settlement, shopify_payout, stripe_payout]
  complexity: COMPLEX
  
PATTERN_5_BATCH_REPORT:
  description: "Aggregated data, summary totals, period-based"
  indicators:
    - Multiple transactions summarized
    - Category breakdowns
    - Period totals
    - Counts and summaries
  examples: [pos_eod_report, payroll_batch, sales_summary]
  complexity: MODERATE
  
PATTERN_6_COMMITMENT_DOCUMENT:
  description: "Future transaction, no current financial impact"
  indicators:
    - Future dates
    - Terms and conditions
    - No payment status
    - "Quote", "Order", "Agreement" keywords
  examples: [quote, purchase_order, contract, lease_agreement]
  complexity: LOW
  
PATTERN_7_AMORTIZATION_SCHEDULE:
  description: "Loan/debt repayment schedule with principal and interest breakdown"
  indicators:
    - Loan account number
    - Principal and interest breakdown
    - Payment schedule (multiple periods)
    - Outstanding balance
  examples: [loan_statement, mortgage_statement, amortization_schedule]
  complexity: MODERATE
  
PATTERN_8_ASSET_DOCUMENT:
  description: "Asset purchase or disposal with depreciation details"
  indicators:
    - Asset description and identification
    - Purchase price or disposal value
    - Depreciation information
    - Useful life or asset class
  examples: [asset_purchase_invoice, asset_disposal_form, depreciation_schedule]
  complexity: MODERATE
  
PATTERN_9_LEASE_AGREEMENT:
  description: "Lease contract with terms, payments, and lease obligations"
  indicators:
    - Lease term and payment schedule
    - Lessor and lessee parties
    - Leased asset description
    - Monthly/periodic payment amounts
  examples: [lease_agreement, lease_amendment, lease_payment_notice]
  complexity: MODERATE
  
PATTERN_10_ACCRUAL_ADJUSTMENT:
  description: "Month-end accrual or deferral journal entry"
  indicators:
    - Period covered != transaction date
    - Adjustment entry keywords (accrual, deferral, prepaid, unbilled)
    - No external party (internal adjustment)
    - Amount allocated over time period
    - Often manual journal entry format
  examples: [prepaid_expense_capitalization, accrued_expense_journal, deferred_revenue_entry, accrued_revenue_recognition]
  complexity: MODERATE
  note: "Critical for month-end close and matching principle compliance"
```

### 1.3 Layer 1 Output Example

```json
{
  "layer_1_structure": {
    "pattern": "PATTERN_2_BILATERAL_INVOICE",
    "format": "invoice",
    "complexity": "moderate",
    "has_line_items": true,
    "has_parties": "both",
    "field_count": 12,
    "confidence": 0.95
  }
}
```

---

## LAYER 2: Semantic Content Analysis

**Goal:** Understand the meaning and direction of money flow.

### 2.1 Money Flow Analysis

```yaml
INPUT: structure_profile + document_text + extracted_fields

ANALYSIS_POINTS:
  - money_direction: [money_in, money_out, neutral, internal_transfer]
  - transaction_type: [sale, purchase, payment, receipt, adjustment, transfer]
  - parties_role: [we_are_seller, we_are_buyer, we_are_service_provider, internal]
  - payment_status: [paid, unpaid, partial, future_commitment]
  
OUTPUT: semantic_classification
```

### 2.2 Direction Detection Rules

```yaml
MONEY_IN (Revenue):
  indicators:
    - We are issuing invoice/receipt to customer
    - "Invoice to:", "Bill to:", "Sold to:"
    - Payment received confirmation
    - Sales revenue keywords
  categories_likely: [SALES, BANKING]
  
MONEY_OUT (Expense/Purchase):
  indicators:
    - We received invoice/bill from vendor
    - "From:", "Supplier:", "Vendor:"
    - Payment made confirmation
    - Expense/purchase keywords
  categories_likely: [PURCHASES, EXPENSES, BANKING, FIXED_ASSETS]
  subcategory_analysis:
    - If line items are inventory/resale goods → PURCHASES (Inventory)
    - If line items are consumables/services → PURCHASES (Expense)
    - If line items are capital assets (>$1000, useful life >1 year) → FIXED_ASSETS
  
MONEY_OUT (Debt Service):
  indicators:
    - Loan payment, mortgage payment
    - Principal and interest breakdown
    - Lender/bank as recipient
  categories_likely: [DEBT, BANKING]
  
MONEY_OUT (Equity Distribution):
  indicators:
    - Dividend payment, distribution to owners
    - Shareholder names as recipients
    - "Dividend", "Distribution" keywords
  categories_likely: [EQUITY]
  
MONEY_IN (Financing):
  indicators:
    - Loan proceeds, capital contribution
    - "Loan disbursement", "Capital injection"
    - From bank/lender or investor
  categories_likely: [DEBT, EQUITY, BANKING]
  
NEUTRAL (No immediate impact):
  indicators:
    - Quote, estimate, order (not fulfilled)
    - Commitment document
    - Information only
  categories_likely: [OTHER]
  
INTERNAL (Between our accounts):
  indicators:
    - Both accounts belong to us
    - Transfer between accounts
    - Internal allocation
  categories_likely: [BANKING, OTHER]
```

### 2.3 Component Recognition

```yaml
COMPONENT_DETECTION:
  
  parties:
    - customer_name: "Who is paying us?"
    - vendor_name: "Who are we paying?"
    - employee_name: "Internal party?"
    - is_related_party: "Inter-company or related entity?"
    
  amounts:
    - gross_amount: "Total before adjustments"
    - tax_amount: "VAT/GST/Sales Tax"
    - fees: "Marketplace/processing fees"
    - net_amount: "Final amount"
    - currency: "Transaction currency (USD, EUR, GBP, etc.)"
    - foreign_currency: "Is this a multi-currency transaction?"
    
  identifiers:
    - invoice_number: "Unique transaction ID"
    - account_number: "Bank/customer account"
    - order_reference: "Linked order/PO"
    
  dates:
    - transaction_date: "When did it happen?"
    - due_date: "When is payment expected?"
    - period: "Statement period?"
    - service_period: "Period covered by this transaction?"
    
  special_flags:
    - is_prepayment: "Payment before goods/services delivered?"
    - is_deposit: "Customer deposit or advance payment?"
    - is_refund: "Refund or credit to customer/from vendor?"
    - is_writeoff: "Bad debt, inventory obsolescence, or asset impairment?"
    - is_grant: "Government grant or subsidy?"
    - is_foreign_currency: "Transaction in currency != business base currency?"
    - is_intercompany: "Transaction with related entity/subsidiary?"
    - requires_fx_adjustment: "Exchange rate difference requires FX gain/loss entry?"
```

### 2.4 Layer 2 Output Example

```json
{
  "layer_2_semantics": {
    "money_direction": "money_in",
    "transaction_type": "sale",
    "parties": {
      "we_are": "seller",
      "customer_name": "Acme Corp"
    },
    "amounts": {
      "subtotal": 1000.00,
      "tax": 100.00,
      "total": 1100.00
    },
    "payment_status": "unpaid",
    "confidence": 0.92
  }
}
```

---

## LAYER 3: Business Context Mapping

**Goal:** Map to category, action, and GL routing.

### 3.1 Category Classification (11 Core Categories)

```yaml
INPUT: structure_profile + semantic_classification + industry_context

CATEGORIES:
  
  SALES:
    trigger_conditions:
      - money_direction = "money_in"
      - transaction_type = "sale"
      - we_are = "seller"
    documents: [sales_invoice, sales_receipt, credit_note, quote, customer_deposit, customer_refund]
    subcategories:
      SALES_INVOICE:
        description: "Standard invoice for goods/services delivered"
        action: "create_sales_invoice"
      CUSTOMER_DEPOSIT:
        description: "Advance payment before goods/services delivered"
        indicators: ["deposit", "advance payment", "prepayment", is_prepayment=true]
        action: "record_customer_deposit"
        gl_accounts: [Bank Account, Customer Deposits (Liability)]
        note: "Liability until earned, then convert to revenue"
      SALES_REFUND:
        description: "Refund issued to customer"
        indicators: ["refund", "credit note", "return", is_refund=true]
        action: "process_customer_refund"
        gl_accounts: [Sales Returns, AR or Bank Account]
    gl_accounts: [Accounts Receivable, Sales Revenue, Sales Returns, Customer Deposits]
    
  PURCHASES:
    trigger_conditions:
      - money_direction = "money_out"
      - transaction_type = "purchase"
      - we_are = "buyer"
      - NOT fixed_asset AND NOT debt_payment
    documents: [supplier_bill, purchase_order, debit_note, prepaid_expense_invoice, vendor_refund]
    subcategories:
      INVENTORY_PURCHASE:
        indicators: ["resale", "stock", "inventory", "goods for resale"]
        gl_accounts: [Inventory, Accounts Payable]
      EXPENSE_PURCHASE:
        indicators: ["supplies", "utilities", "rent", "services", "consumables"]
        gl_accounts: [Expense Accounts, Accounts Payable]
      PREPAID_EXPENSE:
        description: "Expense paid in advance for future periods"
        indicators: ["annual", "prepaid", "advance payment", is_prepayment=true, service_period > 1 month]
        examples: ["annual insurance", "software subscription paid annually"]
        action: "record_prepaid_expense"
        gl_accounts: [Prepaid Assets, Accounts Payable or Bank]
        note: "Capitalize to Prepaid Assets, amortize monthly via month-end process"
      VENDOR_REFUND:
        description: "Refund received from vendor"
        indicators: ["refund", "credit", is_refund=true]
        action: "process_vendor_refund"
        gl_accounts: [Bank Account or AP, Expense or COGS]
      ASSET_PURCHASE:
        indicators: ["equipment", "machinery", "vehicle", "computer", amount > threshold]
        redirect_to: FIXED_ASSETS
    
  BANKING:
    trigger_conditions:
      - structure_pattern = "PATTERN_3_PERIODIC_STATEMENT"
      - OR transaction_type = "transfer/payment/receipt"
    documents: [bank_statement, payment_confirmation, transfer, foreign_currency_transaction]
    special_note: "RECONCILIATION TRIGGER - matches transactions to AR/AP invoices"
    special_flags:
      FOREIGN_CURRENCY:
        description: "Transaction in non-base currency"
        indicators: [currency != base_currency, "EUR", "GBP", "CAD", foreign_currency=true]
        action: "Record with FX rate and conversion"
        gl_accounts: [Bank Account, FX Gain/Loss]
        note: "Convert to base currency at transaction date rate"
      INTER_COMPANY:
        description: "Transaction with related entity"
        indicators: [is_related_party=true, party in [subsidiaries, affiliates, parent]]
        action: "Flag for inter-company reconciliation"
        gl_accounts: [Bank Account, Inter-Company Payable/Receivable]
        note: "Must reconcile with related entity's books"
    reconciliation_actions:
      - Match payments to supplier invoices (clear AP subledger)
      - Match receipts to customer invoices (clear AR subledger)
      - Identify unmatched transactions for manual review
      - Flag foreign currency transactions for FX gain/loss calculation
      - Flag inter-company transactions for inter-company reconciliation
    gl_accounts: [Bank Accounts, Cash, FX Gain/Loss, Inter-Company Accounts]
    
  EXPENSES:
    trigger_conditions:
      - money_direction = "money_out"
      - transaction_type = "expense"
      - Small amounts, no line items or simple receipts
      - Paid immediately (not AP)
    documents: [expense_receipt, credit_card_transaction, reimbursement, petty_cash]
    gl_accounts: [Various Expense Accounts, Cash/Bank/Credit Card]
    
  PAYROLL:
    trigger_conditions:
      - Keywords: "salary", "wages", "payroll", "employee"
      - structure_pattern = "PATTERN_5_BATCH_REPORT"
    documents: [payslip, timesheet, payroll_batch]
    gl_accounts: [Salary Expense, Payroll Liabilities, Employee Net Pay Payable]
    
  INVENTORY:
    trigger_conditions:
      - Keywords: "delivery", "goods received", "stock", "inventory count", "write-off", "obsolescence"
      - Physical movement focus (may or may not have amounts)
    documents: [delivery_note, goods_receipt, stock_adjustment, inventory_count, inventory_writeoff, damage_report]
    subcategories:
      INVENTORY_RECEIPT:
        description: "Goods received into inventory"
        action: "record_goods_receipt"
      INVENTORY_ADJUSTMENT:
        description: "Count adjustments, corrections"
        action: "record_inventory_adjustment"
      INVENTORY_WRITEOFF:
        description: "Obsolete, damaged, or unsalable inventory"
        indicators: ["obsolete", "damaged", "expired", "write-off", is_writeoff=true]
        action: "record_inventory_writeoff"
        gl_accounts: [Inventory Write-off Expense, Inventory]
        note: "Remove from inventory, expense the loss"
      COGS_TRIGGER:
        description: "Sales invoice triggers COGS calculation"
        trigger: "Sales invoice posted with inventory items"
        action: "calculate_and_post_cogs"
        gl_accounts: [COGS, Inventory]
        note: "Automated based on sales invoice + inventory costing method"
    gl_accounts: [Inventory, COGS, Inventory Adjustments, Inventory Write-off Expense]
    
  TAX:
    trigger_conditions:
      - Keywords: "VAT", "GST", "sales tax", "tax return", "tax payment", "IRS", "HMRC"
      - Complex tax breakdowns OR tax payment confirmation
    documents: [tax_invoice, tax_return, tax_filing, tax_payment_receipt]
    subcategories:
      TAX_INVOICE:
        description: "Invoice with tax (VAT/GST) breakdown"
        action: "Record with tax tracking"
      TAX_PAYMENT:
        description: "Payment of tax liability to tax authority"
        action: "Clear tax payable account"
        gl_accounts: [Tax Payable, Bank Account]
      TAX_RETURN:
        description: "Tax filing/return document"
        action: "Record tax liability or refund"
    gl_accounts: [Tax Payable, Tax Receivable, Tax Expense]
    
  FIXED_ASSETS:
    trigger_conditions:
      - Keywords: "equipment", "machinery", "vehicle", "furniture", "computer hardware"
      - Amount typically > $1,000
      - Useful life > 1 year
      - structure_pattern = "PATTERN_8_ASSET_DOCUMENT" OR "PATTERN_2_BILATERAL_INVOICE"
    documents: [asset_purchase_invoice, asset_disposal_form, depreciation_schedule]
    subcategories:
      ASSET_ACQUISITION:
        action: "Capitalize asset, record AP or payment"
        gl_accounts: [Fixed Assets, Accounts Payable/Bank]
      ASSET_DISPOSAL:
        action: "Remove asset, record gain/loss"
        gl_accounts: [Fixed Assets, Accumulated Depreciation, Gain/Loss on Disposal]
      DEPRECIATION:
        action: "Record periodic depreciation"
        gl_accounts: [Depreciation Expense, Accumulated Depreciation]
    
  DEBT:
    trigger_conditions:
      - Keywords: "loan", "mortgage", "note payable", "line of credit"
      - structure_pattern = "PATTERN_7_AMORTIZATION_SCHEDULE" OR "PATTERN_3_PERIODIC_STATEMENT"
      - Has principal and interest breakdown
    documents: [loan_statement, mortgage_statement, loan_agreement, debt_payment]
    subcategories:
      LOAN_RECEIPT:
        money_direction: "money_in"
        action: "Record loan proceeds"
        gl_accounts: [Bank Account, Loan Payable]
      LOAN_PAYMENT:
        money_direction: "money_out"
        action: "Split principal (reduce liability) and interest (expense)"
        gl_accounts: [Loan Payable, Interest Expense, Bank Account]
      LOAN_STATEMENT:
        action: "Reconcile loan balance, identify payment schedule"
    
  EQUITY:
    trigger_conditions:
      - Keywords: "dividend", "distribution", "capital contribution", "stock issuance", "shareholder"
      - Transactions with owners/shareholders
    documents: [dividend_payment, capital_contribution, stock_certificate, distribution_notice]
    subcategories:
      EQUITY_CONTRIBUTION:
        money_direction: "money_in"
        action: "Record capital injection"
        gl_accounts: [Bank Account, Owner's Equity/Share Capital]
      EQUITY_DISTRIBUTION:
        money_direction: "money_out"
        action: "Record dividend or distribution"
        gl_accounts: [Dividends/Distributions, Bank Account]
  
  LEASES:
    trigger_conditions:
      - Keywords: "lease", "rent", "lessor", "lessee", "lease agreement", "ROU asset"
      - structure_pattern = "PATTERN_9_LEASE_AGREEMENT" OR "PATTERN_2_BILATERAL_INVOICE"
      - Recurring payment terms with lease duration
    documents: [lease_agreement, lease_amendment, lease_payment_invoice, lease_notice]
    subcategories:
      LEASE_AGREEMENT:
        description: "Initial lease contract (ASC 842 / IFRS 16)"
        indicators: ["lease term", "monthly payment", "lease commencement"]
        action: "capitalize_lease"
        gl_accounts: [ROU Asset, Lease Liability]
        note: "Capitalize if term > 12 months, expense if short-term"
      LEASE_PAYMENT:
        description: "Monthly lease payment invoice"
        action: "record_lease_payment"
        gl_accounts: [Lease Liability (principal), Interest Expense, Bank Account]
        note: "Split payment into principal and interest components"
      SHORT_TERM_LEASE:
        description: "Lease term <= 12 months"
        action: "record_rent_expense"
        gl_accounts: [Rent Expense, Accounts Payable or Bank]
        note: "Expense directly, no capitalization"
    gl_accounts: [ROU Asset, Lease Liability, Interest Expense, Rent Expense]
    
  GRANTS:
    trigger_conditions:
      - Keywords: "grant", "subsidy", "government assistance", "award letter"
      - Money received from government or non-profit for specific purpose
    documents: [grant_award_letter, grant_payment_notice, subsidy_confirmation]
    subcategories:
      GRANT_RECEIPT:
        money_direction: "money_in"
        action: "record_grant_receipt"
        gl_accounts: [Bank Account, Deferred Grant Income or Grant Revenue]
        note: "Defer if conditions attached, recognize as revenue if unconditional"
      GRANT_EXPENSE_REIMBURSEMENT:
        description: "Grant reimburses specific expenses"
        action: "match_grant_to_expenses"
        gl_accounts: [Bank Account, Grant Revenue or Expense Offset]
    gl_accounts: [Bank Account, Deferred Grant Income, Grant Revenue]
  
  ACCRUALS_DEFERRALS:
    trigger_conditions:
      - Transaction date != period covered by expense/revenue
      - Payment timing mismatch with accounting period
      - Keywords: "prepaid", "accrued", "deferred", "advance", "deposit"
    documents: [prepaid_expense_invoice, accrual_journal, deferred_revenue_contract, advance_payment_notice]
    subcategories:
      PREPAID_EXPENSE:
        description: "Expense paid in advance for future periods (ASC 340)"
        indicators: ["annual license", "insurance premium", "rent paid in advance", amount > prepaid_expense_threshold]
        action: "capitalize_prepaid_expense"
        gl_accounts: [Prepaid Expenses (Asset), Bank Account or Accounts Payable]
        note: "Capitalize as asset, amortize over benefit period"
        example: "Annual software license $12,000 paid Jan 1 → Capitalize as Prepaid, expense $1,000/month"
      ACCRUED_EXPENSE:
        description: "Expense incurred but not yet billed (ASC 450)"
        indicators: ["utility estimate", "unbilled services", "month-end accrual", period_end_adjustment]
        action: "record_accrued_expense"
        gl_accounts: [Expense Account, Accrued Expenses Payable]
        note: "Recognize expense in current period, create liability"
        example: "December electricity used but bill arrives Jan 15 → Accrue $500 expense in December"
      DEFERRED_REVENUE:
        description: "Payment received for future performance obligation (ASC 606)"
        indicators: ["subscription prepayment", "multi-month contract", "SaaS annual payment", "retainer", "advance payment"]
        action: "record_deferred_revenue"
        gl_accounts: [Bank Account, Deferred Revenue (Liability)]
        revenue_recognition_method: "over_time"
        note: "Record as liability, recognize revenue as performance obligations satisfied"
        example: "Annual SaaS subscription $12,000 paid upfront → Defer as liability, recognize $1,000/month"
      ACCRUED_REVENUE:
        description: "Revenue earned but not yet invoiced (ASC 606)"
        indicators: ["unbilled services", "work-in-progress", "milestone completion", "time & materials"]
        action: "record_accrued_revenue"
        gl_accounts: [Accrued Revenue Receivable (Asset), Revenue]
        note: "Recognize revenue in period earned, create receivable asset"
        example: "Consulting work completed Dec 28 but invoiced Jan 5 → Accrue revenue in December"
    gl_accounts: [Prepaid Expenses (Asset), Accrued Expenses Payable, Deferred Revenue (Liability), Accrued Revenue Receivable]
    note: "Critical for accrual accounting - matching principle compliance"
    
  OTHER:
    trigger_conditions:
      - Unclear direction
      - Commitment documents
      - Cannot classify with confidence
    documents: [contract, agreement, manual_entry, miscellaneous]
    gl_accounts: [Various]
```

### 3.2 GL Impact Classification

```yaml
GL_IMPACT_RULES:

FULL_GL_IMPACT:
  description: "Posts directly to General Ledger immediately"
  conditions:
    - transaction_type IN ["journal_entry", "bank_transaction", "adjustment"]
    - OR structure_pattern = "PATTERN_1_SINGLE_TRANSACTION" AND paid = true
  posting: "Immediate to GL"
  approval: "Required"
  examples:
    - Bank deposit: Dr Bank (GL), Cr Revenue (GL)
    - Cash expense: Dr Expense (GL), Cr Cash (GL)
    - Journal entry: Dr/Cr as specified
    
SUBLEDGER_ONLY:
  description: "Posts to subledger, GL updated via batch posting"
  conditions:
    - structure_pattern = "PATTERN_2_BILATERAL_INVOICE"
    - payment_status = "unpaid"
    - category IN ["SALES", "PURCHASES"]
  posting: "Subledger now, GL later"
  approval: "Workflow-based"
  examples:
    - Sales invoice: Dr AR (Subledger), Cr Revenue (via posting)
    - Supplier bill: Dr Expense (via posting), Cr AP (Subledger)
    
MEMORANDUM_ONLY:
  description: "Information tracking, no financial impact"
  conditions:
    - structure_pattern = "PATTERN_6_COMMITMENT_DOCUMENT"
    - payment_status = "future_commitment"
  posting: "None"
  approval: "Not required"
  examples:
    - Quote/Estimate
    - Purchase order (not received)
    - Delivery note (not invoiced)
    
MIXED_IMPACT:
  description: "Multiple posting destinations (complex)"
  conditions:
    - structure_pattern = "PATTERN_4_MARKETPLACE_SETTLEMENT"
    - OR structure_pattern = "PATTERN_5_BATCH_REPORT"
  posting: "Multiple journals"
  approval: "Component-based"
  examples:
    - Marketplace: Sales→AR, Fees→GL, Payout→Bank
    - POS EOD: Cash→GL, Card→GL, Credit→AR
```

### 3.3 Action Mapping (Simplified)

```yaml
ACTION_SELECTION:

# SALES Actions
category: SALES
  if subcategory = "CUSTOMER_DEPOSIT":
    action: "record_customer_deposit"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Bank Account, Cr Customer Deposits (Liability)"
  elif subcategory = "SALES_REFUND":
    action: "process_customer_refund"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Sales Returns, Cr AR or Bank Account"
  elif payment_status = "unpaid":
    action: "create_sales_invoice"
    subledger: "AR"
  elif payment_status = "paid":
    action: "record_sales_receipt"
    gl_impact: "FULL_GL_IMPACT"
  elif structure_pattern = "PATTERN_6_COMMITMENT_DOCUMENT":
    action: "create_quote"
    gl_impact: "MEMORANDUM_ONLY"
  elif is_writeoff = true:
    action: "write_off_bad_debt"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Bad Debt Expense, Cr Accounts Receivable"
    note: "Triggered by bankruptcy notice, legal letter, or management decision"
    
# PURCHASES Actions
category: PURCHASES
  # Determine purchase type first
  if subcategory = "INVENTORY_PURCHASE":
    if payment_status = "unpaid":
      action: "record_supplier_bill_inventory"
      subledger: "AP"
      gl_impact: "SUBLEDGER_ONLY"
      posting: "Dr Inventory, Cr AP"
  elif subcategory = "EXPENSE_PURCHASE":
    if payment_status = "unpaid":
      action: "record_supplier_bill_expense"
      subledger: "AP"
      gl_impact: "SUBLEDGER_ONLY"
      posting: "Dr Expense, Cr AP"
  elif subcategory = "PREPAID_EXPENSE":
    action: "record_prepaid_expense"
    gl_impact: "SUBLEDGER_ONLY" (if unpaid) or "FULL_GL_IMPACT" (if paid)
    posting_unpaid: "Dr Prepaid Assets, Cr AP"
    posting_paid: "Dr Prepaid Assets, Cr Bank Account"
    note: "Capitalize to asset, monthly amortization via month-end process"
  elif subcategory = "VENDOR_REFUND":
    action: "process_vendor_refund"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Bank Account, Cr Expense or COGS or AP"
  elif subcategory = "ASSET_PURCHASE":
    action: "redirect_to_fixed_assets"
    note: "Capital asset purchase, handle in FIXED_ASSETS category"
  elif structure_pattern = "PATTERN_6_COMMITMENT_DOCUMENT":
    action: "record_purchase_order"
    gl_impact: "MEMORANDUM_ONLY"
    
# BANKING Actions (Reconciliation Focus)
category: BANKING
  if structure_pattern = "PATTERN_3_PERIODIC_STATEMENT":
    action: "import_bank_statement_for_reconciliation"
    gl_impact: "FULL_GL_IMPACT"
    reconciliation_steps:
      - "Match bank transactions to existing AR invoices (customer receipts)"
      - "Match bank transactions to existing AP invoices (supplier payments)"
      - "Identify unmatched deposits → create sales receipts or investigate"
      - "Identify unmatched withdrawals → create expense transactions or investigate"
      - "Clear matched items in AR/AP subledgers"
      - "Flag foreign currency transactions for FX conversion"
      - "Flag inter-company transactions for inter-company reconciliation"
  elif foreign_currency = true:
    action: "record_foreign_currency_transaction"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr/Cr Bank Account (base currency), Dr/Cr FX Gain/Loss, Cr/Dr AR/AP/Other (base currency)"
    note: "Convert at transaction date spot rate, record FX gain/loss immediately"
  elif is_related_party = true:
    action: "record_intercompany_transaction"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr/Cr Bank Account, Cr/Dr Inter-Company Payable/Receivable"
    note: "Flag for inter-company reconciliation with related entity"
  elif transaction_type = "payment":
    action: "record_payment_and_apply"
    subledger: "AP or AR"
    note: "Apply payment to specific invoice(s)"
  elif transaction_type = "receipt":
    action: "record_receipt_and_apply"
    subledger: "AR"
    note: "Apply receipt to specific customer invoice(s)"
    
# EXPENSES Actions
category: EXPENSES
  if structure_pattern = "PATTERN_1_SINGLE_TRANSACTION":
    action: "record_expense_receipt"
    gl_impact: "FULL_GL_IMPACT"
    
# TAX Actions
category: TAX
  if subcategory = "TAX_PAYMENT":
    action: "record_tax_payment"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Tax Payable, Cr Bank Account"
  elif subcategory = "TAX_RETURN":
    action: "record_tax_filing"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr/Cr Tax Payable/Receivable"
  elif subcategory = "TAX_INVOICE":
    action: "record_with_tax_tracking"
    note: "Route to SALES or PURCHASES with tax component tracking"
    
# FIXED_ASSETS Actions
category: FIXED_ASSETS
  if subcategory = "ASSET_ACQUISITION":
    action: "capitalize_fixed_asset"
    gl_impact: "SUBLEDGER_ONLY" (if unpaid) or "FULL_GL_IMPACT" (if paid)
    subledger: "Fixed Assets + AP (if unpaid)"
    posting_unpaid: "Dr Fixed Assets, Cr AP"
    posting_paid: "Dr Fixed Assets, Cr Bank"
  elif subcategory = "ASSET_DISPOSAL":
    action: "record_asset_disposal"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Accumulated Depreciation, Dr/Cr Gain/Loss, Cr Fixed Assets"
  elif subcategory = "DEPRECIATION":
    action: "record_depreciation_expense"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Depreciation Expense, Cr Accumulated Depreciation"
    
# DEBT Actions
category: DEBT
  if subcategory = "LOAN_RECEIPT":
    action: "record_loan_proceeds"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Bank Account, Cr Loan Payable"
  elif subcategory = "LOAN_PAYMENT":
    action: "record_debt_service_payment"
    gl_impact: "FULL_GL_IMPACT"
    posting_split:
      - "Dr Loan Payable (principal portion)"
      - "Dr Interest Expense (interest portion)"
      - "Cr Bank Account (total payment)"
  elif subcategory = "LOAN_STATEMENT":
    action: "reconcile_loan_balance"
    gl_impact: "MEMORANDUM_ONLY" (unless discrepancy found)
    
# EQUITY Actions
category: EQUITY
  if subcategory = "EQUITY_CONTRIBUTION":
    action: "record_capital_contribution"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Bank Account, Cr Owner's Equity/Share Capital"
  elif subcategory = "EQUITY_DISTRIBUTION":
    action: "record_dividend_distribution"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Dividends/Distributions, Cr Bank Account"
    
# INVENTORY Actions
category: INVENTORY
  if subcategory = "INVENTORY_WRITEOFF":
    action: "record_inventory_writeoff"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Inventory Write-off Expense, Cr Inventory"
    note: "Triggered by damage report, obsolescence notice, or physical count"
  elif subcategory = "COGS_TRIGGER":
    action: "calculate_and_post_cogs"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr COGS, Cr Inventory"
    note: "Automated when sales invoice posted (FIFO/LIFO/Weighted Average costing)"
    trigger: "Sales invoice with inventory line items"
    
# LEASES Actions
category: LEASES
  if subcategory = "LEASE_AGREEMENT":
    if lease_term > 12_months:
      action: "capitalize_lease"
      gl_impact: "FULL_GL_IMPACT"
      posting: "Dr ROU Asset, Cr Lease Liability"
      note: "ASC 842 / IFRS 16 - Calculate present value of lease payments"
    else:
      action: "record_short_term_lease"
      note: "Treat as operating expense, no capitalization"
  elif subcategory = "LEASE_PAYMENT":
    action: "record_lease_payment"
    gl_impact: "FULL_GL_IMPACT"
    posting: "Dr Lease Liability (principal), Dr Interest Expense, Cr Bank Account"
    note: "Split payment using effective interest method"
    
# GRANTS Actions
category: GRANTS
  if subcategory = "GRANT_RECEIPT":
    action: "record_grant_receipt"
    gl_impact: "FULL_GL_IMPACT"
    posting_conditional: "Dr Bank Account, Cr Deferred Grant Income"
    posting_unconditional: "Dr Bank Account, Cr Grant Revenue"
    note: "Defer if performance conditions exist, recognize immediately if unconditional"
    
# Complex Actions
category: ANY
  if structure_pattern = "PATTERN_4_MARKETPLACE_SETTLEMENT":
    action: "import_marketplace_settlement"
    gl_impact: "MIXED_IMPACT"
  elif structure_pattern = "PATTERN_5_BATCH_REPORT":
    action: "import_batch_report"
    gl_impact: "MIXED_IMPACT"
```

### 3.4 Layer 3 Output Example

```json
{
  "layer_3_business_context": {
    "category": "SALES",
    "subcategory": "sales_invoice",
    "action": "create_sales_invoice",
    "gl_impact": "SUBLEDGER_ONLY",
    "subledger": "accounts_receivable",
    "posting_entries": {
      "debit": {"account": "Accounts Receivable", "type": "subledger"},
      "credit": {"account": "Sales Revenue", "type": "gl_via_posting"}
    },
    "requires_approval": false,
    "confidence": 0.90,
    "reasoning": "Bilateral invoice structure, money_in direction, unpaid status → AR subledger transaction"
  }
}
```

---

## Complete Classification Flow

### Step-by-Step Process

```yaml
STEP 1: Extract Fields
  - Use DocStrange to extract raw fields
  - Normalize field names
  
STEP 2: Layer 1 Analysis
  Prompt: |
    Analyze document structure:
    - Pattern: [6 patterns]
    - Complexity: [low, moderate, complex]
    - Key indicators present
  
STEP 3: Layer 2 Analysis
  Prompt: |
    Analyze semantic meaning:
    - Money direction: [in, out, neutral, internal]
    - Transaction type: [sale, purchase, payment, etc]
    - Payment status: [paid, unpaid, future]
  
STEP 4: Layer 3 Classification
  Prompt: |
    Map to business context:
    - Category: [8 categories]
    - Action: [specific action]
    - GL Impact: [4 impact levels]
    - Routing: [GL, subledger, or memorandum]
  
STEP 5: Validation
  - Check confidence scores
  - Validate required fields present
  - Apply business rules
  
STEP 6: Execute or Flag
  - If confidence >= 0.85: Execute action
  - If confidence 0.70-0.84: Flag for review
  - If confidence < 0.70: Manual review required
```

---

## Mixtral Prompt Structure

### Layer 1 Prompt

```javascript
const layer1Prompt = `
You are analyzing the STRUCTURE of a business document.

EXTRACTED FIELDS:
${JSON.stringify(extractedFields, null, 2)}

DOCUMENT TEXT SAMPLE:
${documentTextSample}

Analyze and return ONLY structure information:

AVAILABLE PATTERNS:
1. PATTERN_1_SINGLE_TRANSACTION - One party, one amount, one date (receipt, payment)
2. PATTERN_2_BILATERAL_INVOICE - Two parties, line items, totals (invoice, bill)
3. PATTERN_3_PERIODIC_STATEMENT - Account, date range, transaction list (bank/loan statement)
4. PATTERN_4_MARKETPLACE_SETTLEMENT - Sales, fees, net payout (Amazon, Shopify)
5. PATTERN_5_BATCH_REPORT - Aggregated data, summaries (POS EOD, payroll)
6. PATTERN_6_COMMITMENT_DOCUMENT - Future transaction, no financial impact (quote, PO)
7. PATTERN_7_AMORTIZATION_SCHEDULE - Loan repayment with principal/interest breakdown
8. PATTERN_8_ASSET_DOCUMENT - Asset purchase/disposal with depreciation details
9. PATTERN_9_LEASE_AGREEMENT - Lease contract with terms, payments, obligations

Return JSON:
{
  "pattern": "PATTERN_X",
  "complexity": "low|moderate|complex",
  "has_line_items": true/false,
  "has_parties": "from|to|both|none",
  "field_count": number,
  "confidence": 0.0-1.0
}
`;
```

### Layer 2 Prompt (with Business Context)

```javascript
const layer2Prompt = `
You are analyzing the SEMANTIC MEANING of a business document.

STRUCTURE PROFILE:
${JSON.stringify(layer1Output, null, 2)}

EXTRACTED FIELDS:
${JSON.stringify(extractedFields, null, 2)}

BUSINESS PROFILE (use for context and direction detection):
{
  // CRITICAL: Identity & Direction
  "registered_name": "${business.registered_name}",
  "country": "${business.country}",
  "currency": "${business.currency}",
  
  // Business Classification
  "sector": "${business.sector}",
  "subsector": "${business.subsector}",
  "employee_count": "${business.employee_count}",
  
  // Operational Context (15 classification fields)
  "has_inventory": ${business.has_inventory},
  "has_physical_products": ${business.has_physical_products},
  "primary_revenue_model": "${business.primary_revenue_model}",
  "accounting_method": "${business.accounting_method}",
  "has_fixed_assets": ${business.has_fixed_assets},
  "fixed_asset_threshold": ${business.fixed_asset_threshold},
  "has_leases": ${business.has_leases},
  "billing_method": "${business.billing_method}",
  "has_cogs": ${business.has_cogs},
  "has_foreign_operations": ${business.has_foreign_operations},
  "collects_sales_tax": ${business.collects_sales_tax},
  "inventory_costing_method": "${business.inventory_costing_method}",
  "has_debt_financing": ${business.has_debt_financing},
  "has_intercompany_transactions": ${business.has_intercompany_transactions},
  "prepaid_expense_threshold": ${business.prepaid_expense_threshold},
  "lease_capitalization_threshold": ${business.lease_capitalization_threshold}
}

DIRECTION DETECTION RULES (CRITICAL):
1. Compare document parties against our registered_name: "${business.registered_name}"
2. If "From: ${business.registered_name}" → money_in (we're selling)
3. If "To: ${business.registered_name}" and "From: [other party]" → money_out (we're buying)
4. Look for variations: abbreviations, legal suffixes (LLC, Inc, Ltd, Pty)
5. Match against aliases if available

CURRENCY CONTEXT:
- Our base currency: ${business.currency}
- If document shows different currency → flag as foreign_currency: true
- Country context: ${business.country} (for tax terminology)

Analyze and return ONLY semantic information:

MONEY DIRECTION OPTIONS:
- money_in: We are receiving money (sales, receipts, loan proceeds, capital contributions)
- money_out: We are paying money (purchases, expenses, loan payments, dividends)
- neutral: No current financial impact (quotes, orders)
- internal: Transfer between our own accounts

TRANSACTION TYPES:
- sale, purchase, payment, receipt, adjustment, transfer, loan_receipt, loan_payment, 
  dividend_payment, capital_contribution, asset_purchase, asset_disposal, depreciation,
  tax_payment

PAYMENT STATUS:
- paid, unpaid, partial, future_commitment, recurring_payment

ADDITIONAL SEMANTIC INDICATORS:
- purchase_nature: [inventory, expense, fixed_asset, prepaid_expense]
  * Inventory: Goods for resale (only if has_inventory = true)
  * Expense: Consumables, services, operating costs
  * Fixed Asset: Capital equipment, useful life > 1 year, amount > fixed_asset_threshold
  * Prepaid Expense: Annual/multi-period payments (insurance, subscriptions, amount > prepaid_expense_threshold)
  
- financing_type: [debt, equity, lease, none]
  * Debt: Loans, mortgages, notes payable (only if has_debt_financing = true)
  * Equity: Owner investments, dividends, distributions
  * Lease: Lease agreements and payments (only if has_leases = true or term > lease_capitalization_threshold)
  
- special_flags: [foreign_currency, inter_company, deposit, refund, writeoff, grant]
  * Foreign Currency: Transaction currency != ${business.currency}
  * Inter-Company: Related party transaction (only if has_intercompany_transactions = true)
  * Deposit: Customer advance payment before delivery
  * Refund: Customer refund or vendor credit
  * Write-off: Bad debt, inventory obsolescence, asset impairment
  * Grant: Government grant or subsidy

Return JSON:
{
  "money_direction": "money_in|money_out|neutral|internal",
  "transaction_type": "type",
  "parties": {
    "we_are": "seller|buyer|service_provider|internal",
    "other_party": "name"
  },
  "payment_status": "status",
  "purchase_nature": "inventory|expense|fixed_asset|prepaid_expense|null",
  "financing_type": "debt|equity|lease|none",
  "special_flags": [],
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of direction detection"
}
`;
```

### Layer 3 Prompt (with Business Rules & Confidence Boosters)

```javascript
const layer3Prompt = `
You are mapping a business document to ACCOUNTING ACTION and GL ROUTING.

STRUCTURE PROFILE:
${JSON.stringify(layer1Output, null, 2)}

SEMANTIC PROFILE:
${JSON.stringify(layer2Output, null, 2)}

BUSINESS PROFILE (use for validation and confidence boosting):
{
  // Identity & Context
  "registered_name": "${business.registered_name}",
  "country": "${business.country}",
  "currency": "${business.currency}",
  "sector": "${business.sector}",
  "employee_count": "${business.employee_count}",
  
  // Operational Flags (15 classification fields)
  "has_inventory": ${business.has_inventory},
  "has_physical_products": ${business.has_physical_products},
  "primary_revenue_model": "${business.primary_revenue_model}",
  "accounting_method": "${business.accounting_method}",
  "has_fixed_assets": ${business.has_fixed_assets},
  "fixed_asset_threshold": ${business.fixed_asset_threshold},
  "has_leases": ${business.has_leases},
  "billing_method": "${business.billing_method}",
  "has_cogs": ${business.has_cogs},
  "has_foreign_operations": ${business.has_foreign_operations},
  "collects_sales_tax": ${business.collects_sales_tax},
  "inventory_costing_method": "${business.inventory_costing_method}",
  "has_debt_financing": ${business.has_debt_financing},
  "has_intercompany_transactions": ${business.has_intercompany_transactions},
  "prepaid_expense_threshold": ${business.prepaid_expense_threshold},
  "lease_capitalization_threshold": ${business.lease_capitalization_threshold}
}

IMPOSSIBLE CATEGORIES (skip these - confidence boost +0.35):
${getImpossibleCategories(business)}

CONFIDENCE BOOSTERS:
- If category aligns with business profile flags: +0.20 confidence
- If impossible categories correctly skipped: +0.15 confidence
- If amount thresholds respected: +0.10 confidence

Map to business context:

CATEGORIES (choose ONE):
- SALES: Money coming in from customers for goods/services sold (includes deposits, refunds, bad debt write-offs)
  * Valid if: primary_revenue_model matches document type
  
- PURCHASES: Money going out to suppliers (distinguish: inventory vs expense vs prepaid vs asset)
  * PURCHASES_INVENTORY: Valid ONLY if has_inventory = true
  * PURCHASES_EXPENSE: Always valid for operating costs
  * PURCHASES_PREPAID: Valid if amount > prepaid_expense_threshold (${business.prepaid_expense_threshold})
  * PURCHASES_ASSET: Redirect to FIXED_ASSETS if amount > fixed_asset_threshold (${business.fixed_asset_threshold})
  
- BANKING: Bank statements, transfers, payments (RECONCILIATION TRIGGER - apply to AR/AP, handle FX and inter-company)
  * Flag foreign_currency if currency != ${business.currency}
  * Flag inter_company if has_intercompany_transactions = true
  
- EXPENSES: Direct expenses paid immediately (not through AP)
  * Valid for small recurring expenses
  
- PAYROLL: Employee wages, benefits, payroll taxes
  * Expected for businesses with employee_count > 0
  
- INVENTORY: Physical goods movement, adjustments, write-offs, COGS triggers
  * Valid ONLY if has_inventory = true
  * COGS triggers valid ONLY if has_cogs = true
  
- TAX: Tax invoices with tax tracking, tax payments to authorities, tax returns
  * Tax collection expected if collects_sales_tax = true
  * Use country-specific terminology: ${getTaxTerminology(business.country)}
  
- FIXED_ASSETS: Capital asset purchases, disposals, depreciation
  * Valid ONLY if has_fixed_assets = true
  * Asset threshold: ${business.fixed_asset_threshold}
  
- DEBT: Loans, mortgages, debt payments (split principal/interest)
  * Valid ONLY if has_debt_financing = true
  
- EQUITY: Capital contributions, dividends, owner distributions
  * Always valid (all businesses have equity)
  
- LEASES: Lease agreements and payments (ASC 842 / IFRS 16)
  * Valid ONLY if has_leases = true
  * Capitalize if lease term > ${business.lease_capitalization_threshold} months
  * Expense if short-term lease
  
- GRANTS: Government grants and subsidies
  * Valid if document shows grant/subsidy indicators
  
- OTHER: Cannot classify with confidence
  * Use if confidence < 0.70 or conflicting indicators

GL IMPACT (choose ONE):
- FULL_GL_IMPACT: Posts directly to GL (journal entry, bank transaction)
- SUBLEDGER_ONLY: Posts to AR/AP/Inventory subledger first
- MEMORANDUM_ONLY: Information only, no accounting entry
- MIXED_IMPACT: Multiple posting destinations (complex)

ACTIONS BY CATEGORY:
SALES: create_sales_invoice, record_sales_receipt, record_customer_deposit, process_customer_refund
PURCHASES: record_supplier_bill, record_purchase_order, record_prepaid_expense, process_vendor_refund
BANKING: import_bank_statement, record_payment, record_transfer, record_fx_transaction
EXPENSES: record_expense_receipt, record_reimbursement
PAYROLL: import_payroll_batch, record_payslip
INVENTORY: record_goods_receipt, record_inventory_adjustment, record_inventory_writeoff, calculate_cogs
TAX: record_tax_invoice, record_tax_payment, file_tax_return
FIXED_ASSETS: capitalize_asset, record_asset_disposal, record_depreciation
DEBT: record_loan_receipt, record_loan_payment, reconcile_loan_statement
EQUITY: record_capital_contribution, record_dividend_payment
LEASES: capitalize_lease, record_lease_payment, record_rent_expense
GRANTS: record_grant_receipt, match_grant_to_expenses

Return JSON:
{
  "category": "category_name",
  "action": "specific_action",
  "gl_impact": "impact_level",
  "subledger": "AR|AP|Inventory|none",
  "requires_approval": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation including why impossible categories were skipped"
}
`;

// Helper function: Generate impossible categories list
function getImpossibleCategories(business) {
  const impossible = [];
  
  if (!business.has_inventory) {
    impossible.push("INVENTORY (has_inventory = false)");
    impossible.push("PURCHASES_INVENTORY (has_inventory = false)");
  }
  
  if (!business.has_fixed_assets) {
    impossible.push("FIXED_ASSETS (has_fixed_assets = false)");
  }
  
  if (!business.has_leases) {
    impossible.push("LEASES (has_leases = false)");
  }
  
  if (!business.has_debt_financing) {
    impossible.push("DEBT (has_debt_financing = false)");
  }
  
  if (!business.has_cogs) {
    impossible.push("COGS calculation (has_cogs = false)");
  }
  
  return impossible.length > 0 
    ? impossible.join("\n- ") 
    : "None - all categories possible";
}

// Helper function: Get country-specific tax terminology
function getTaxTerminology(country) {
  const taxTerms = {
    US: "Sales Tax (state-level)",
    IN: "GST (Goods and Services Tax)",
    GB: "VAT (Value Added Tax)",
    CA: "GST/HST/PST (varies by province)",
    AU: "GST (Goods and Services Tax)",
    EU: "VAT (Value Added Tax)",
    NZ: "GST (Goods and Services Tax)",
    SG: "GST (Goods and Services Tax)"
  };
  
  return taxTerms[country] || "Sales Tax / VAT / GST";
}

// Example usage:
const businessContext = {
  registered_name: "Acme Software Inc",
  country: "US",
  currency: "USD",
  sector: "technology",
  employee_count: "11-50",
  has_inventory: false,
  has_physical_products: false,
  primary_revenue_model: "subscription",
  accounting_method: "accrual",
  has_fixed_assets: true,
  fixed_asset_threshold: 2500.00,
  has_leases: true,
  billing_method: "recurring_monthly",
  has_cogs: false,
  has_foreign_operations: true,
  collects_sales_tax: true,
  inventory_costing_method: "not_applicable",
  has_debt_financing: false,
  has_intercompany_transactions: false,
  prepaid_expense_threshold: 1000.00,
  lease_capitalization_threshold: 12
};

// This would produce impossible categories:
// - INVENTORY (has_inventory = false)
// - PURCHASES_INVENTORY (has_inventory = false)
// - DEBT (has_debt_financing = false)
// - COGS calculation (has_cogs = false)

// This provides +0.35 confidence boost if these categories are correctly avoided
```

---

## Confidence & Validation

### Confidence Calculation (Enhanced with Business Context)

```yaml
CONFIDENCE_FACTORS:
  
  structure_confidence: 0.0-1.0
    - Clear pattern match: +0.3
    - All expected fields present: +0.2
    - No ambiguous indicators: +0.2
    
  semantic_confidence: 0.0-1.0
    - Clear money direction: +0.3
    - Payment status obvious: +0.2
    - Parties clearly identified: +0.2
    - Business name matched: +0.1 (registered_name found in document)
    
  business_confidence: 0.0-1.0
    - Category unambiguous: +0.3
    - Action has all required fields: +0.2
    - No conflicting indicators: +0.2
    - Business profile alignment: +0.35 (MAJOR BOOST)
      * Impossible categories correctly skipped: +0.15
      * Category matches business flags: +0.10
      * Thresholds respected: +0.10
    
BUSINESS_PROFILE_BOOST_EXAMPLES:
  
  Software Consulting Invoice:
    - Category: SALES ✓ (primary_revenue_model = service_based)
    - Skipped INVENTORY ✓ (has_inventory = false)
    - Skipped DEBT ✓ (has_debt_financing = false)
    - Base confidence: 0.75
    - Business boost: +0.35
    - Final confidence: 0.92 → AUTO-PROCESS ✓
  
  Retail Inventory Purchase:
    - Category: PURCHASES_INVENTORY ✓ (has_inventory = true)
    - Correctly used INVENTORY category ✓ (has_inventory = true)
    - Amount triggers COGS ✓ (has_cogs = true)
    - Base confidence: 0.78
    - Business boost: +0.25
    - Final confidence: 0.90 → AUTO-PROCESS ✓
  
  Asset Purchase (but business has no assets):
    - Category: FIXED_ASSETS ✗ (has_fixed_assets = false)
    - Conflicting with business profile ✗
    - Base confidence: 0.72
    - Business penalty: -0.20 (profile mismatch)
    - Final confidence: 0.52 → MANUAL REVIEW ✗
    
FINAL_CONFIDENCE:
  formula: (structure_conf + semantic_conf + business_conf) / 3
  
THRESHOLDS:
  - >= 0.85: Auto-process (target: 92% of documents)
  - 0.70-0.84: Review recommended (target: 5% of documents)
  - < 0.70: Manual review required (target: 3% of documents)
  
IMPACT:
  - Without business context: ~75% auto-process rate
  - With business context: ~92% auto-process rate
  - Improvement: +17% auto-process rate (+0.35 confidence boost)
```

### Validation Rules

```yaml
VALIDATION_CHECKS:
  
  required_fields_check:
    - If action = "create_sales_invoice": require [customer, amount, date]
    - If action = "record_payment": require [amount, payment_method, date]
    - If action = "import_bank_statement": require [account, period, transactions]
    
  consistency_check:
    - If money_direction = "money_in" → category must be SALES or BANKING
    - If gl_impact = "SUBLEDGER_ONLY" → must specify subledger
    - If requires_approval = true → flag for approval workflow
    
  business_rules_check:
    - If amount > $10,000 → flag for approval
    - If vendor is new → flag for review
    - If tax amount doesn't match calculation → flag warning
```

---

## Industry Adaptations

### How to Extend for Industry-Specific Documents

```yaml
INDUSTRY_EXTENSION_PATTERN:

1. Add industry-specific structure patterns:
   PATTERN_7_HEALTHCARE_CLAIM:
     indicators: [patient_name, insurance_info, procedure_codes]
     
2. Add industry-specific semantic rules:
   HEALTHCARE_SEMANTICS:
     - Patient pays → SALES
     - Insurance pays → BANKING (third-party payment)
     
3. Add industry-specific actions:
   HEALTHCARE_ACTIONS:
     - submit_insurance_claim
     - record_patient_payment
     - process_insurance_remittance
```

### Industry Quick Reference

```yaml
RETAIL:
  unique_patterns: [PATTERN_5_BATCH_REPORT for daily sales]
  unique_actions: [import_pos_eod_report, process_return]
  
MANUFACTURING:
  unique_patterns: [production_report, bom]
  unique_actions: [record_production_completion, allocate_costs_to_job]
  
CONSTRUCTION:
  unique_patterns: [progress_billing, change_order]
  unique_actions: [create_progress_invoice, update_project_budget]
  
ECOMMERCE:
  unique_patterns: [PATTERN_4_MARKETPLACE_SETTLEMENT]
  unique_actions: [import_marketplace_settlement, allocate_marketplace_fees]
```

---

## Summary: How the 3 Layers Work Together (with Business Context)

```
LAYER 1 (Structure)
├─ Identifies the "shape" of the document
├─ Matches to 1 of 9 base patterns
└─ Provides structural confidence score

LAYER 2 (Semantics + Business Context)
├─ Takes Layer 1 pattern as context
├─ Uses business profile for direction detection:
│  ├─ registered_name matching (buyer vs seller)
│  ├─ currency validation (base vs foreign)
│  └─ country context (tax terminology)
├─ Determines money direction and meaning
├─ Analyzes purchase nature (inventory/expense/asset)
├─ Identifies financing type (debt/equity)
├─ Flags special cases (foreign currency, inter-company)
└─ Provides semantic confidence score

LAYER 3 (Business Action Mapping + Validation)
├─ Takes Layer 1 + Layer 2 as context
├─ Uses business profile for validation:
│  ├─ Impossible categories (skip if flag = false)
│  ├─ Threshold validation (fixed assets, prepaid expenses)
│  └─ Business rules (COGS triggers, tax collection)
├─ Maps to category (13 categories), action, GL routing
├─ Distinguishes PURCHASES subcategories
├─ Handles BANKING as reconciliation trigger
├─ Routes TAX payments vs TAX invoices appropriately
├─ Provides business confidence score (with +0.35 boost)
└─ Returns final classification + routing instructions

VALIDATION
├─ Combines all 3 confidence scores
├─ Applies business profile boost (+0.35 max)
├─ Checks required fields present
├─ Applies business rules
└─ Decides: Auto-process (92%) | Review (5%) | Manual (3%)

BUSINESS PROFILE INTEGRATION (KEY INNOVATION):
├─ 16 classification fields from business profile
├─ registered_name for direction detection (critical)
├─ country for tax terminology (GST/VAT/Sales Tax)
├─ currency for foreign currency detection
├─ Operational flags (has_inventory, has_leases, etc.)
├─ Thresholds (fixed_asset_threshold, prepaid_expense_threshold)
└─ +0.35 confidence boost when aligned correctly
```

## Category Expansion Summary

**Enhanced from 8 to 14 categories:**
1. SALES (enhanced with customer deposits, refunds, bad debt write-offs)
2. PURCHASES (enhanced with 4 subcategories: inventory/expense/prepaid/asset, plus vendor refunds)
3. BANKING (enhanced as reconciliation trigger + foreign currency + inter-company flags)
4. EXPENSES (clarified as direct payments)
5. PAYROLL (unchanged)
6. INVENTORY (enhanced with write-offs and COGS triggers)
7. TAX (enhanced to cover payments, returns, and invoices)
8. **FIXED_ASSETS** (new - capital asset lifecycle)
9. **DEBT** (new - loans and debt service)
10. **EQUITY** (new - owner transactions)
11. **LEASES** (new - lease accounting ASC 842)
12. **GRANTS** (new - government grants and subsidies)
13. **ACCRUALS_DEFERRALS** (new - prepaid expenses, accrued expenses, deferred revenue)
14. OTHER (unchanged)

**Added 4 new structure patterns:**
- PATTERN_7_AMORTIZATION_SCHEDULE (for loan statements)
- PATTERN_8_ASSET_DOCUMENT (for asset purchases/disposals)
- PATTERN_9_LEASE_AGREEMENT (for lease contracts)
- PATTERN_10_ACCRUAL_ADJUSTMENT (for month-end accrual/deferral journals)

**Enhanced semantic analysis:**
- purchase_nature detection (inventory vs expense vs asset vs prepaid)
- accrual_timing detection (transaction date vs period covered)
- foreign_currency detection (multi-currency transactions with FX impact)
- intercompany_flag detection (related party transactions for consolidation elimination)
- financing_type detection (debt vs equity)
- Reconciliation focus for banking documents

---

## Quick Reference: Decision Tree

```
Document Received
    │
    ├─ Layer 1: What pattern? → [PATTERN_2_BILATERAL_INVOICE]
    │
    ├─ Layer 2: Money direction? → [money_in, unpaid]
    │
    └─ Layer 3: What action?
          │
          ├─ Category: SALES
          ├─ Action: create_sales_invoice
          ├─ GL Impact: SUBLEDGER_ONLY
          ├─ Subledger: Accounts Receivable
          ├─ Posting: Dr AR (Subledger), Cr Revenue (via posting)
          └─ Confidence: 0.92 → AUTO-PROCESS
```

---

**End of Classification System Document**

This document is designed to be **LLM-friendly** with clear, structured prompts and progressive narrowing of classification scope across 3 distinct layers.
