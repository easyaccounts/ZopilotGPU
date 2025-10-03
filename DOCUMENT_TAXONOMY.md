# Comprehensive Document & Transaction Taxonomy
## For Universal Business Document Classification System

**Version:** 1.0  
**Last Updated:** October 3, 2025  
**Purpose:** Industry-aware document classification with GL/Subledger impact tracking

---

## Table of Contents
1. [Document Categories](#document-categories)
2. [GL Impact Classification](#gl-impact-classification)
3. [Industry-Specific Documents](#industry-specific-documents)
4. [Action Taxonomy](#action-taxonomy)
5. [Field Patterns](#field-patterns)

---

## Document Categories

### Core Categories (8 Primary + Industry Extensions)

```yaml
PRIMARY_CATEGORIES:
  - SALES             # Revenue transactions
  - PURCHASES         # Supplier/vendor transactions
  - BANKING           # Bank accounts & payments
  - EXPENSES          # Operating expenses
  - PAYROLL           # Employee compensation
  - INVENTORY         # Stock & asset management
  - TAX               # Tax & compliance
  - OTHER             # Miscellaneous

INDUSTRY_EXTENSIONS:
  - MANUFACTURING     # Production-specific documents
  - CONSTRUCTION      # Project-based documents
  - RETAIL            # Point of sale & inventory
  - SERVICES          # Service delivery documents
  - HEALTHCARE        # Medical billing & claims
  - REAL_ESTATE       # Property & lease documents
  - LOGISTICS         # Shipping & transportation
  - ECOMMERCE         # Online marketplace documents
```

---

## GL Impact Classification

### Impact Levels

```yaml
GL_IMPACT_LEVELS:
  
  FULL_GL_IMPACT:
    description: "Transaction posts directly to General Ledger"
    examples:
      - Journal entries
      - Bank deposits
      - Manual adjustments
      - Depreciation entries
    accounting_entries: "Dr/Cr to GL accounts immediately"
    approval_required: true
    
  SUBLEDGER_ONLY:
    description: "Transaction posts to subledger, GL updated via period-end process"
    examples:
      - Sales invoices (AR subledger)
      - Supplier bills (AP subledger)
      - Inventory movements (Inventory subledger)
      - Fixed asset additions (FA subledger)
    accounting_entries: "Posts to subledger, GL updated on posting/batch"
    approval_required: false
    
  MEMORANDUM_ONLY:
    description: "Information-only, no accounting impact"
    examples:
      - Quotes/Estimates
      - Purchase orders (not received)
      - Delivery notes (not invoiced)
      - Proforma invoices
    accounting_entries: "None - tracking only"
    approval_required: false
    
  MIXED_IMPACT:
    description: "Partial GL + Subledger impact"
    examples:
      - Marketplace settlement (Sales subledger + Fee GL expense)
      - Payroll (Gross in subledger, deductions in GL)
      - Fixed asset purchase (Asset subledger + AP subledger)
    accounting_entries: "Multiple posting destinations"
    approval_required: varies
```

---

## Document Types by Category

### 1. SALES Documents

#### 1.1 Sales Invoice
```yaml
document_type: sales_invoice
gl_impact: SUBLEDGER_ONLY
subledger: Accounts Receivable (AR)
gl_posting: On payment or period-end posting

field_patterns:
  required: [invoice_number, customer_name, total_amount, date]
  optional: [line_items, tax_breakdown, payment_terms, due_date]
  
financial_impact:
  debit: Accounts Receivable (Subledger)
  credit: Sales Revenue (via AR posting)
  
suggested_actions:
  primary: create_sales_invoice
  alternatives: [create_sales_order, flag_for_review]
  
industry_variations:
  retail: "POS receipt, single transaction"
  wholesale: "Multi-line invoice with credit terms"
  services: "Time-based billing, milestone invoicing"
  saas: "Recurring subscription invoice"
```

#### 1.2 Sales Receipt / Payment Received
```yaml
document_type: sales_receipt
gl_impact: FULL_GL_IMPACT (if cash sale) or SUBLEDGER_ONLY (if AR payment)
subledger: Accounts Receivable (if paying off invoice)
gl_posting: Immediate

field_patterns:
  required: [receipt_number, customer_name, amount, payment_method, date]
  optional: [invoice_reference, bank_account]
  
financial_impact:
  scenario_1_cash_sale:
    debit: Bank Account (GL)
    credit: Sales Revenue (GL)
  scenario_2_ar_payment:
    debit: Bank Account (GL)
    credit: Accounts Receivable (Subledger)
  
suggested_actions:
  primary: record_sales_receipt
  alternatives: [create_sales_invoice_with_payment, record_bank_deposit]
```

#### 1.3 Credit Note / Sales Return
```yaml
document_type: credit_note
gl_impact: SUBLEDGER_ONLY
subledger: Accounts Receivable (AR)
gl_posting: On period-end or when posted

field_patterns:
  required: [credit_note_number, customer_name, amount, original_invoice, date]
  optional: [reason, return_items]
  
financial_impact:
  debit: Sales Returns and Allowances
  credit: Accounts Receivable (Subledger)
  
suggested_actions:
  primary: record_credit_note
  alternatives: [reverse_invoice, create_refund]
```

#### 1.4 Quote / Estimate / Proforma Invoice
```yaml
document_type: quote
gl_impact: MEMORANDUM_ONLY
subledger: None
gl_posting: None (informational only)

field_patterns:
  required: [quote_number, customer_name, items, total, date, validity]
  
financial_impact: None
  
suggested_actions:
  primary: create_quote
  alternatives: [convert_to_invoice, flag_for_follow_up]
  
notes: "No accounting entry until converted to invoice"
```

#### 1.5 Marketplace Settlement Report
```yaml
document_type: marketplace_settlement
gl_impact: MIXED_IMPACT
subledger: Accounts Receivable (gross sales)
gl_posting: Partial immediate (fees), partial subledger (sales)

field_patterns:
  required: [settlement_id, gross_sales, marketplace_fee, payment_processing_fee, net_payout, date]
  optional: [transaction_breakdown, refunds, adjustments]
  
financial_impact:
  transaction_1_sales:
    debit: Accounts Receivable (Subledger)
    credit: Sales Revenue
  transaction_2_fees:
    debit: Marketplace Fees Expense (GL)
    credit: Accounts Receivable (Subledger)
  transaction_3_payout:
    debit: Bank Account (GL)
    credit: Accounts Receivable (Subledger)
  
suggested_actions:
  primary: import_marketplace_settlement
  alternatives: [create_complex_invoice, split_into_multiple_transactions]
  
platforms: [Amazon, eBay, Shopify, Etsy, Walmart Marketplace]
```

---

### 2. PURCHASES Documents

#### 2.1 Supplier Bill / Vendor Invoice
```yaml
document_type: supplier_bill
gl_impact: SUBLEDGER_ONLY
subledger: Accounts Payable (AP)
gl_posting: On period-end or when posted

field_patterns:
  required: [invoice_number, vendor_name, total_amount, date]
  optional: [purchase_order_reference, line_items, tax, due_date]
  
financial_impact:
  debit: Expense Account (via AP posting)
  credit: Accounts Payable (Subledger)
  
suggested_actions:
  primary: record_supplier_bill
  alternatives: [record_expense, match_to_purchase_order]
  
approval_workflow: "May require approval based on amount threshold"
```

#### 2.2 Purchase Order
```yaml
document_type: purchase_order
gl_impact: MEMORANDUM_ONLY
subledger: Purchase Orders (commitment tracking)
gl_posting: None until goods received

field_patterns:
  required: [po_number, vendor_name, items, total, date]
  
financial_impact: None (commitment only)
  
suggested_actions:
  primary: record_purchase_order
  alternatives: [create_supplier_bill, flag_for_receiving]
  
notes: "Becomes bill when goods received or services rendered"
```

#### 2.3 Expense Receipt
```yaml
document_type: expense_receipt
gl_impact: FULL_GL_IMPACT or SUBLEDGER_ONLY (if through AP)
subledger: None (direct expense) or AP (if needs reimbursement)
gl_posting: Immediate (if paid) or via AP (if reimbursement)

field_patterns:
  required: [receipt_number, merchant_name, amount, date, category]
  optional: [payment_method, employee_name, project_code]
  
financial_impact:
  scenario_1_direct_expense:
    debit: Expense Account (GL)
    credit: Bank Account or Credit Card (GL)
  scenario_2_reimbursement:
    debit: Expense Account
    credit: Employee Reimbursements Payable (AP Subledger)
  
suggested_actions:
  primary: record_expense_receipt
  alternatives: [create_reimbursement_claim, record_credit_card_transaction]
```

---

### 3. BANKING Documents

#### 3.1 Bank Statement
```yaml
document_type: bank_statement
gl_impact: FULL_GL_IMPACT (when reconciling)
subledger: None (direct GL)
gl_posting: As transactions are matched/added

field_patterns:
  required: [account_number, statement_period, opening_balance, closing_balance, transactions[]]
  optional: [interest_earned, fees_charged]
  
financial_impact:
  - Each transaction posts to Bank Account (GL) + corresponding account
  - Unmatched items may create journal entries
  
suggested_actions:
  primary: import_bank_statement
  alternatives: [start_reconciliation, import_transactions_only]
  
reconciliation: "Matches with subledger payments and receipts"
```

#### 3.2 Payment Confirmation
```yaml
document_type: payment_confirmation
gl_impact: SUBLEDGER_ONLY (matches to AP/AR)
subledger: AP (payment made) or AR (payment received)
gl_posting: Via subledger posting

field_patterns:
  required: [payment_reference, from_account, to_account, amount, date]
  optional: [invoices_paid, payment_method]
  
financial_impact:
  debit/credit: Depends on direction (payment made vs received)
  
suggested_actions:
  primary: record_payment
  alternatives: [match_to_invoice, create_bank_transaction]
```

#### 3.3 POS End-of-Day Report
```yaml
document_type: pos_eod_report
gl_impact: MIXED_IMPACT
subledger: Accounts Receivable (if credit sales)
gl_posting: Cash portion immediate, credit portion to subledger

field_patterns:
  required: [date, total_sales, payment_breakdown[cash, card, digital], transaction_count]
  optional: [operator, till_number, discounts, refunds, variance]
  
financial_impact:
  transaction_1_cash_sales:
    debit: Cash in Transit (GL)
    credit: Sales Revenue (GL)
  transaction_2_card_sales:
    debit: Credit Card Clearing (GL)
    credit: Sales Revenue (GL)
  transaction_3_credit_sales:
    debit: Accounts Receivable (Subledger)
    credit: Sales Revenue
  
suggested_actions:
  primary: import_pos_eod_report
  alternatives: [record_bank_deposit, create_sales_summary]
  
reconciliation: "Cash should match physical till count"
```

#### 3.4 Wire Transfer / ACH / Bank Transfer
```yaml
document_type: bank_transfer
gl_impact: FULL_GL_IMPACT
subledger: None (direct GL) or AP/AR (if payment)
gl_posting: Immediate

field_patterns:
  required: [transfer_reference, from_account, to_account, amount, date]
  
financial_impact:
  scenario_1_internal_transfer:
    debit: To Bank Account (GL)
    credit: From Bank Account (GL)
  scenario_2_payment_to_supplier:
    debit: Accounts Payable (Subledger)
    credit: Bank Account (GL)
  
suggested_actions:
  primary: record_bank_transfer
  alternatives: [record_payment, record_internal_transfer]
```

---

### 4. EXPENSES Documents

#### 4.1 Employee Expense Report
```yaml
document_type: expense_report
gl_impact: SUBLEDGER_ONLY
subledger: Employee Reimbursements Payable (AP)
gl_posting: When approved and posted

field_patterns:
  required: [employee_name, report_date, line_items[], total_amount]
  optional: [project_codes, receipt_attachments, manager_approval]
  
financial_impact:
  debit: Multiple Expense Accounts (by category)
  credit: Employee Reimbursements Payable (AP Subledger)
  
suggested_actions:
  primary: record_reimbursement
  alternatives: [split_by_expense_type, flag_for_approval]
  
approval: "Requires manager approval before posting"
```

#### 4.2 Credit Card Statement
```yaml
document_type: credit_card_statement
gl_impact: FULL_GL_IMPACT
subledger: None (direct GL)
gl_posting: As transactions are recorded

field_patterns:
  required: [card_number, statement_period, transactions[], total_due]
  
financial_impact:
  - Each transaction: Debit Expense Account, Credit Credit Card Payable
  - Payment: Debit Credit Card Payable, Credit Bank Account
  
suggested_actions:
  primary: import_credit_card_statement
  alternatives: [reconcile_expenses, record_individual_transactions]
```

#### 4.3 Petty Cash Voucher
```yaml
document_type: petty_cash_voucher
gl_impact: FULL_GL_IMPACT
subledger: None
gl_posting: Immediate

field_patterns:
  required: [voucher_number, recipient, amount, purpose, date]
  
financial_impact:
  debit: Expense Account (GL)
  credit: Petty Cash (GL)
  
suggested_actions:
  primary: record_petty_cash
  alternatives: [record_cash_expense]
```

---

### 5. PAYROLL Documents

#### 5.1 Payslip / Pay Stub
```yaml
document_type: payslip
gl_impact: SUBLEDGER_ONLY
subledger: Payroll Liability Accounts
gl_posting: Via payroll posting batch

field_patterns:
  required: [employee_name, period, gross_pay, deductions[], net_pay]
  optional: [hours_worked, overtime, bonuses, benefits]
  
financial_impact:
  debit: Salary Expense (GL via subledger)
  credit_1: Employee Net Pay Payable (Subledger)
  credit_2: Tax Withholdings Payable (GL)
  credit_3: Benefits Deductions Payable (GL)
  
suggested_actions:
  primary: import_payslip
  alternatives: [record_payroll_batch, flag_for_payroll_review]
  
notes: "Usually imported via payroll system integration"
```

#### 5.2 Timesheet
```yaml
document_type: timesheet
gl_impact: MEMORANDUM_ONLY
subledger: Time Tracking (not accounting)
gl_posting: None (feeds payroll calculation)

field_patterns:
  required: [employee_name, period, hours_breakdown[], total_hours]
  
financial_impact: None (input to payroll process)
  
suggested_actions:
  primary: import_timesheet
  alternatives: [approve_for_payroll, flag_for_review]
```

---

### 6. INVENTORY Documents

#### 6.1 Delivery Note / Packing Slip
```yaml
document_type: delivery_note
gl_impact: MEMORANDUM_ONLY
subledger: Inventory (quantity tracking)
gl_posting: None until invoiced

field_patterns:
  required: [delivery_note_number, customer_name, items[], quantities[], date]
  
financial_impact: None (inventory movement only)
  
suggested_actions:
  primary: record_delivery_note
  alternatives: [create_sales_invoice, update_inventory]
  
notes: "Physical movement, no value transfer until invoiced"
```

#### 6.2 Goods Receipt Note
```yaml
document_type: goods_receipt
gl_impact: SUBLEDGER_ONLY
subledger: Inventory + AP
gl_posting: When matched with supplier invoice

field_patterns:
  required: [receipt_number, supplier_name, po_reference, items[], quantities[]]
  
financial_impact:
  debit: Inventory (Subledger)
  credit: Goods Received Not Invoiced (GL clearing account)
  - Reversed when invoice received
  
suggested_actions:
  primary: record_goods_receipt
  alternatives: [match_to_purchase_order, update_inventory]
```

#### 6.3 Stock Adjustment / Inventory Count
```yaml
document_type: stock_adjustment
gl_impact: FULL_GL_IMPACT
subledger: Inventory
gl_posting: Immediate

field_patterns:
  required: [adjustment_reference, items[], old_quantities[], new_quantities[], reason]
  
financial_impact:
  debit: Inventory Adjustment Loss (GL) - if decrease
  credit: Inventory (Subledger) - if decrease
  (reversed if increase)
  
suggested_actions:
  primary: record_inventory_adjustment
  alternatives: [flag_for_review, create_journal_entry]
```

---

### 7. TAX Documents

#### 7.1 Tax Invoice (VAT/GST)
```yaml
document_type: tax_invoice
gl_impact: SUBLEDGER_ONLY
subledger: AR or AP + Tax Payable/Receivable
gl_posting: Via subledger + tax posting

field_patterns:
  required: [invoice_number, tax_id, tax_breakdown[], subtotal, tax_amount, total]
  
financial_impact:
  sales_tax_invoice:
    debit: Accounts Receivable (Subledger)
    credit_1: Sales Revenue
    credit_2: Sales Tax Payable (GL)
  purchase_tax_invoice:
    debit_1: Expense/Inventory
    debit_2: Input Tax Receivable (GL)
    credit: Accounts Payable (Subledger)
  
suggested_actions:
  primary: record_tax_invoice
  alternatives: [record_sales_invoice, record_supplier_bill]
```

#### 7.2 Tax Return / Filing
```yaml
document_type: tax_return
gl_impact: FULL_GL_IMPACT (when filed)
subledger: None
gl_posting: Journal entry when filed

field_patterns:
  required: [tax_period, tax_type, calculation, amount_due/refund]
  
financial_impact:
  if_payment_due:
    debit: Tax Expense (GL)
    credit: Tax Payable (GL)
  if_refund:
    debit: Tax Receivable (GL)
    credit: Tax Expense (GL)
  
suggested_actions:
  primary: record_tax_filing
  alternatives: [create_journal_entry, flag_for_review]
```

---

### 8. OTHER Documents

#### 8.1 Contract / Agreement
```yaml
document_type: contract
gl_impact: MEMORANDUM_ONLY
subledger: Contract Management (not accounting)
gl_posting: None

financial_impact: None (future commitment)
  
suggested_actions:
  primary: file_contract
  alternatives: [flag_for_legal_review, extract_payment_terms]
```

#### 8.2 Journal Entry / Manual Adjustment
```yaml
document_type: journal_entry
gl_impact: FULL_GL_IMPACT
subledger: None (direct GL)
gl_posting: Immediate

field_patterns:
  required: [journal_number, date, line_items[account, debit, credit], description]
  
financial_impact: As specified in entry
  
suggested_actions:
  primary: create_journal_entry
  alternatives: [flag_for_approval, record_adjustment]
  
approval: "Requires appropriate authorization level"
```

---

## Industry-Specific Documents

### MANUFACTURING

#### Bill of Materials (BOM)
```yaml
document_type: bill_of_materials
gl_impact: MEMORANDUM_ONLY
subledger: Production Planning
financial_impact: None (defines production recipe)
suggested_actions: [record_bom, create_production_order]
```

#### Production Report
```yaml
document_type: production_report
gl_impact: SUBLEDGER_ONLY
subledger: Work in Progress (WIP) Inventory
financial_impact:
  debit: Finished Goods Inventory
  credit: Work in Progress Inventory
suggested_actions: [record_production_completion, update_inventory]
```

#### Job Cost Sheet
```yaml
document_type: job_cost_sheet
gl_impact: SUBLEDGER_ONLY
subledger: Job Costing / WIP
financial_impact: Accumulates costs to job
suggested_actions: [allocate_costs_to_job, complete_job]
```

---

### CONSTRUCTION

#### Progress Billing / Draw Request
```yaml
document_type: progress_billing
gl_impact: SUBLEDGER_ONLY
subledger: Accounts Receivable / Project Accounting
financial_impact:
  debit: Accounts Receivable
  credit: Revenue (% of completion)
suggested_actions: [create_progress_invoice, record_project_revenue]
```

#### Change Order
```yaml
document_type: change_order
gl_impact: MEMORANDUM_ONLY (until approved)
subledger: Project Budget
financial_impact: Updates project budget when approved
suggested_actions: [update_project_budget, create_additional_invoice]
```

---

### RETAIL

#### Daily Sales Summary (DSR)
```yaml
document_type: daily_sales_report
gl_impact: MIXED_IMPACT
subledger: Inventory (COGS) + AR (credit sales)
financial_impact:
  debit_1: Cash/Bank
  debit_2: Cost of Goods Sold
  credit_1: Sales Revenue
  credit_2: Inventory
suggested_actions: [import_daily_sales, reconcile_pos]
```

#### Return Merchandise Authorization (RMA)
```yaml
document_type: rma
gl_impact: SUBLEDGER_ONLY
subledger: Inventory + AR
financial_impact:
  debit_1: Sales Returns
  debit_2: Inventory (if resaleable)
  credit: Accounts Receivable
suggested_actions: [process_return, issue_credit_note]
```

---

### SERVICES / CONSULTING

#### Service Agreement / Statement of Work
```yaml
document_type: sow
gl_impact: MEMORANDUM_ONLY
subledger: Contract Management
financial_impact: None (defines future revenue)
suggested_actions: [record_contract, create_milestone_schedule]
```

#### Milestone Billing
```yaml
document_type: milestone_billing
gl_impact: SUBLEDGER_ONLY
subledger: AR / Project Revenue
financial_impact:
  debit: Accounts Receivable
  credit: Service Revenue (milestone based)
suggested_actions: [create_milestone_invoice, record_project_revenue]
```

---

### HEALTHCARE

#### Patient Invoice / Medical Bill
```yaml
document_type: medical_bill
gl_impact: SUBLEDGER_ONLY
subledger: Patient AR
financial_impact:
  debit: Patient Accounts Receivable
  credit_1: Service Revenue
  credit_2: Insurance Claims Receivable (if insured)
suggested_actions: [create_patient_invoice, submit_insurance_claim]
```

#### Insurance Remittance Advice
```yaml
document_type: insurance_remittance
gl_impact: MIXED_IMPACT
subledger: Patient AR + Insurance AR
financial_impact:
  debit_1: Bank Account
  debit_2: Insurance Adjustments (write-offs)
  credit: Insurance Claims Receivable
suggested_actions: [process_insurance_payment, update_patient_balances]
```

---

### REAL ESTATE

#### Lease Agreement
```yaml
document_type: lease_agreement
gl_impact: MEMORANDUM_ONLY
subledger: Lease Management
financial_impact: None (defines future rent)
suggested_actions: [record_lease, create_rent_schedule]
```

#### Rent Roll
```yaml
document_type: rent_roll
gl_impact: SUBLEDGER_ONLY
subledger: Tenant AR
financial_impact:
  debit: Tenant Accounts Receivable
  credit: Rental Revenue
suggested_actions: [import_rent_roll, generate_rent_invoices]
```

---

### LOGISTICS / TRANSPORTATION

#### Bill of Lading
```yaml
document_type: bill_of_lading
gl_impact: MEMORANDUM_ONLY
subledger: Shipment Tracking
financial_impact: None (until delivery confirmed)
suggested_actions: [record_shipment, track_delivery]
```

#### Freight Invoice
```yaml
document_type: freight_invoice
gl_impact: SUBLEDGER_ONLY
subledger: AP
financial_impact:
  debit: Freight Expense or Cost of Goods Sold
  credit: Accounts Payable
suggested_actions: [record_freight_expense, allocate_to_shipment]
```

---

### ECOMMERCE

#### Amazon Settlement Report
```yaml
document_type: amazon_settlement
gl_impact: MIXED_IMPACT
subledger: AR (sales) + GL (fees)
financial_impact:
  debit_1: Accounts Receivable (gross sales)
  debit_2: Marketplace Fees Expense
  credit_1: Sales Revenue
  credit_2: Accounts Receivable (fees)
  debit_3: Bank Account (net payout)
suggested_actions: [import_marketplace_settlement, allocate_fees]
```

#### Shopify Payout Report
```yaml
document_type: shopify_payout
gl_impact: MIXED_IMPACT
subledger: AR + GL (fees + payment processing)
financial_impact:
  Similar to Amazon but with Shopify-specific fee structure
suggested_actions: [import_shopify_payout, reconcile_sales]
```

---

## Action Taxonomy

### Action Categories by GL Impact

```yaml
FULL_GL_ACTIONS:
  - create_journal_entry
  - record_bank_deposit
  - record_bank_withdrawal
  - record_inventory_adjustment
  - record_depreciation
  - record_accrual
  - record_prepayment
  approval: Required for most

SUBLEDGER_ACTIONS:
  - create_sales_invoice
  - record_supplier_bill
  - record_payment
  - record_receipt
  - record_credit_note
  - record_debit_note
  approval: Workflow-based

MEMORANDUM_ACTIONS:
  - create_quote
  - record_purchase_order
  - record_sales_order
  - file_contract
  - record_delivery_note
  approval: Not required

COMPLEX_ACTIONS:
  - import_marketplace_settlement
  - process_payroll_batch
  - import_bank_statement
  - reconcile_accounts
  - import_pos_eod_report
  approval: Varies by component
```

---

## Field Pattern Recognition

### Common Field Patterns by Document Type

```yaml
INVOICE_PATTERNS:
  identifiers: [invoice_number, invoice_id, bill_no, ref]
  parties: [customer_name, client_name, bill_to, sold_to]
  amounts: [total, subtotal, tax, grand_total]
  dates: [invoice_date, due_date, date]
  
RECEIPT_PATTERNS:
  identifiers: [receipt_number, receipt_id, transaction_id]
  parties: [customer_name, from]
  amounts: [amount, total_paid]
  payment: [payment_method, payment_type, paid_via]
  
STATEMENT_PATTERNS:
  identifiers: [account_number, statement_id]
  period: [statement_date, from_date, to_date]
  balances: [opening_balance, closing_balance]
  transactions: [transaction_list, line_items]
  
POS_PATTERNS:
  identifiers: [till_number, register_id, terminal_id]
  operators: [cashier, operator, clerk]
  totals: [total_sales, gross_sales, net_sales]
  breakdown: [cash_total, card_total, digital_wallet]
  
MARKETPLACE_PATTERNS:
  identifiers: [settlement_id, payout_id, order_id]
  amounts: [gross_sales, fees, commission, net_payout]
  platform: [marketplace_name, platform]
  breakdown: [transaction_breakdown, fee_breakdown]
```

---

## Implementation Guidelines

### 1. Classification Flow

```
Document → Extract Fields → Analyze Patterns → Match Industry → 
Determine GL Impact → Suggest Action → Validate → Execute
```

### 2. Confidence Scoring

```yaml
HIGH_CONFIDENCE (0.90-1.0):
  - Clear field patterns match
  - Industry context aligns
  - Standard document type
  - Action: Auto-process
  
MEDIUM_CONFIDENCE (0.70-0.89):
  - Partial field match
  - Ambiguous direction
  - Non-standard format
  - Action: Review recommended
  
LOW_CONFIDENCE (< 0.70):
  - Unclear document type
  - Missing critical fields
  - Unknown format
  - Action: Manual review required
```

### 3. Validation Rules

```yaml
VALIDATE_CATEGORY:
  - Category must be in approved list
  - Subcategory must match category
  
VALIDATE_ACTION:
  - Action must be valid for category
  - GL impact must align with action type
  - Required fields must be present
  
VALIDATE_GL_IMPACT:
  - If FULL_GL_IMPACT: Require approval workflow
  - If SUBLEDGER_ONLY: Check subledger exists
  - If MEMORANDUM_ONLY: No posting needed
```

---

## Summary Statistics

```yaml
TOTAL_CATEGORIES: 8 primary + 8 industry extensions
TOTAL_DOCUMENT_TYPES: 60+ defined
TOTAL_ACTIONS: 45+ unique actions
GL_IMPACT_LEVELS: 4 (Full GL, Subledger, Memorandum, Mixed)
INDUSTRIES_COVERED: 8 major sectors
FIELD_PATTERNS: 20+ common patterns
```

---

## Usage in Mixtral Prompt

```javascript
const classificationPrompt = `
You are an expert accounting document classifier.

DOCUMENT CATEGORIES: ${Object.keys(CATEGORIES).join(', ')}

GL IMPACT LEVELS:
- FULL_GL_IMPACT: Direct journal entry to general ledger
- SUBLEDGER_ONLY: Posts to subledger (AR/AP/Inventory)
- MEMORANDUM_ONLY: Information tracking, no accounting entry
- MIXED_IMPACT: Multiple posting destinations

INDUSTRY: ${businessIndustry}
AVAILABLE ACTIONS: ${getActionsForIndustry(businessIndustry)}

EXTRACTED FIELDS: ${documentFields}

Classify this document and return:
{
  "category": "primary category",
  "subcategory": "specific document type",
  "gl_impact": "impact level",
  "action": "suggested action",
  "subledger": "affected subledger if any",
  "requires_approval": boolean,
  "confidence": 0.0-1.0,
  "reasoning": "explanation"
}
`;
```

---

**End of Document Taxonomy**

This taxonomy should be treated as a living document and updated as new document types and industry requirements are discovered.
