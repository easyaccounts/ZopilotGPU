# Month-End Workflow & Recurring Templates
## System-Generated Period-End Adjustments

**Version:** 1.0  
**Last Updated:** October 3, 2025  
**Purpose:** Handle accounting adjustments NOT driven by physical documents

---

## Overview

This document covers **system-generated** accounting activities that occur at month-end or period-end. These are distinct from the **document-driven** classification workflow because they:

- Have **no physical document** triggering them (estimates, calculations, allocations)
- Require **management judgment** or **automated calculations**
- Are **period-based** (monthly, quarterly, annually)
- Often use **recurring templates** that auto-populate

```
┌─────────────────────────────────────────────────────────────┐
│ DOCUMENT CLASSIFICATION                                     │
│ (Physical documents arrive → classify → post)               │
│ Example: Annual insurance invoice arrives → Record prepaid  │
└─────────────────────────────────────────────────────────────┘
                              ↕
                    Document triggers initial setup
                              ↕
┌─────────────────────────────────────────────────────────────┐
│ MONTH-END WORKFLOW                                          │
│ (No document, system-generated → calculate → post)          │
│ Example: Month-end → Amortize 1/12 of prepaid insurance     │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Architecture

### 1. Month-End Checklist System

**Purpose:** Ensure all period-end adjustments are completed before closing books.

```yaml
CHECKLIST_STRUCTURE:
  
  frequency: [monthly, quarterly, annually]
  
  checklist_items:
    - item_id: unique_identifier
    - description: "What needs to be done"
    - category: [accruals, deferrals, depreciation, allocations, provisions, revaluations]
    - requires_data: [source_documents, calculations, management_input]
    - posting_template: template_reference
    - auto_process: true/false
    - requires_approval: true/false
    - status: [not_started, in_progress, completed, reviewed, approved]
    
  workflow_steps:
    1. Generate checklist at period-end
    2. Auto-populate data from system (where possible)
    3. Flag items requiring manual input
    4. Execute postings (auto or manual)
    5. Review and approve
    6. Close period
```

### 2. Recurring Template Engine

**Purpose:** Store and auto-execute repetitive period-end entries.

```yaml
TEMPLATE_STRUCTURE:
  
  template_id: unique_identifier
  template_name: "Descriptive name"
  frequency: [monthly, quarterly, annually]
  posting_type: [journal_entry, adjustment, allocation]
  
  source_data:
    - data_source: [fixed_value, system_calculation, user_input, external_data]
    - calculation_method: "Formula or logic"
    
  posting_entries:
    - line_1:
        account: "Account number or name"
        debit: amount or formula
        credit: amount or formula
        description: "Line description"
    - line_2: ...
    
  auto_reverse: true/false
  reversal_date: "1st of next period"
  
  requires_approval: true/false
  approval_threshold: amount
```

---

## Month-End Activities

### Category 1: Accrued Expenses

**Definition:** Expenses incurred but not yet invoiced/paid.

#### 1.1 Utilities Accrual

```yaml
SCENARIO:
  situation: "Electricity bill not received by month-end"
  no_document: "No invoice available yet"
  action_required: "Estimate and accrue expense"
  
TEMPLATE: accrued_utilities
  frequency: monthly
  source_data:
    - prior_month_bill: $1,200
    - estimate_method: "Use prior month amount or average"
  posting:
    - Dr: Utilities Expense $1,200
    - Cr: Accrued Utilities Payable $1,200
  auto_reverse: true
  reversal_date: "1st of next month"
  note: "Reverses automatically when actual invoice arrives"
```

#### 1.2 Rent Accrual (When Invoice Missing)

```yaml
SCENARIO:
  situation: "Landlord hasn't sent invoice by month-end"
  no_document: "No invoice, but rent amount known from lease"
  action_required: "Accrue rent expense"
  
TEMPLATE: accrued_rent
  frequency: monthly
  source_data:
    - lease_agreement: "Fixed monthly rent $5,000"
  posting:
    - Dr: Rent Expense $5,000
    - Cr: Accrued Rent Payable $5,000
  auto_reverse: true
  reversal_date: "1st of next month"
  note: "Use ONLY when invoice not received; if invoice arrives, classify via document workflow"
```

#### 1.3 Interest Accrual

```yaml
SCENARIO:
  situation: "Loan interest accrues daily, but payment is monthly/quarterly"
  no_document: "No statement/invoice for current period interest"
  action_required: "Calculate and accrue interest"
  
TEMPLATE: accrued_interest
  frequency: monthly
  source_data:
    - loan_balance: "Current outstanding balance"
    - interest_rate: "Annual rate / 12"
    - calculation: "Balance × (Rate / 12)"
  posting:
    - Dr: Interest Expense (calculated)
    - Cr: Accrued Interest Payable (calculated)
  auto_reverse: false
  note: "Clears when actual payment made (classified via DEBT category)"
```

---

### Category 2: Prepaid Expense Amortization

**Definition:** Monthly expense recognition from prepaid assets (document already classified).

#### 2.1 Prepaid Insurance Amortization

```yaml
SCENARIO:
  situation: "Annual insurance premium paid 6 months ago"
  document_already_classified: "Invoice was recorded as Dr Prepaid Assets"
  action_required: "Expense 1/12 monthly"
  
TEMPLATE: amortize_prepaid_insurance
  frequency: monthly
  source_data:
    - prepaid_balance: $12,000
    - months_remaining: 6
    - monthly_expense: $12,000 / 12 = $1,000
  posting:
    - Dr: Insurance Expense $1,000
    - Cr: Prepaid Insurance Asset $1,000
  auto_reverse: false
  auto_process: true (if prepaid register maintained)
  note: "Initial prepaid setup was via document classification"
```

#### 2.2 Prepaid Rent Amortization

```yaml
TEMPLATE: amortize_prepaid_rent
  frequency: monthly
  source_data:
    - prepaid_balance: "Remaining prepaid rent asset"
    - amortization_schedule: "From lease terms"
  posting:
    - Dr: Rent Expense (monthly portion)
    - Cr: Prepaid Rent Asset (monthly portion)
  auto_reverse: false
```

#### 2.3 Software Subscription Amortization

```yaml
TEMPLATE: amortize_software_subscriptions
  frequency: monthly
  source_data:
    - annual_subscription: $6,000
    - monthly_expense: $6,000 / 12 = $500
  posting:
    - Dr: Software Expense $500
    - Cr: Prepaid Subscriptions $500
  auto_reverse: false
```

---

### Category 3: Deferred Revenue Recognition

**Definition:** Recognize revenue from customer deposits/prepayments (document already classified).

#### 3.1 Customer Deposit Revenue Recognition

```yaml
SCENARIO:
  situation: "Customer paid $10,000 deposit 2 months ago for 10-month service contract"
  document_already_classified: "Deposit recorded as Dr Bank, Cr Customer Deposits (Liability)"
  action_required: "Recognize 1/10 revenue monthly as service delivered"
  
TEMPLATE: recognize_deferred_revenue
  frequency: monthly
  source_data:
    - customer_deposits_balance: $10,000
    - contract_duration: 10 months
    - monthly_revenue: $10,000 / 10 = $1,000
  posting:
    - Dr: Customer Deposits (Liability) $1,000
    - Cr: Service Revenue $1,000
  auto_reverse: false
  note: "Initial deposit setup was via document classification (SALES → CUSTOMER_DEPOSIT)"
```

#### 3.2 Subscription Revenue Recognition

```yaml
TEMPLATE: recognize_subscription_revenue
  frequency: monthly
  source_data:
    - annual_subscriptions_received: "Total deferred"
    - monthly_recognition: "Per customer contract terms"
  posting:
    - Dr: Deferred Revenue (Liability)
    - Cr: Subscription Revenue
  auto_reverse: false
```

---

### Category 4: Accrued Revenue

**Definition:** Revenue earned but not yet invoiced.

#### 4.1 Unbilled Professional Services

```yaml
SCENARIO:
  situation: "Consultants worked 80 hours in December, invoice sent in January"
  no_document: "No invoice yet created"
  action_required: "Recognize revenue in period earned"
  
TEMPLATE: accrue_unbilled_revenue
  frequency: monthly
  source_data:
    - hours_worked: 80 (from timesheet system)
    - hourly_rate: $150
    - unbilled_amount: 80 × $150 = $12,000
  posting:
    - Dr: Accrued Revenue (Asset) $12,000
    - Cr: Service Revenue $12,000
  auto_reverse: true
  reversal_date: "1st of next month"
  note: "Reverses when actual invoice created via document classification (SALES)"
```

#### 4.2 Construction/Project Revenue (Percentage of Completion)

```yaml
TEMPLATE: accrue_project_revenue
  frequency: monthly
  source_data:
    - project_completion_percentage: "From project management system"
    - total_contract_value: $100,000
    - revenue_to_recognize: $100,000 × completion%
    - revenue_recognized_to_date: "Cumulative from prior periods"
    - current_period_revenue: "revenue_to_recognize - revenue_recognized_to_date"
  posting:
    - Dr: Unbilled Revenue (Asset) (current_period_revenue)
    - Cr: Project Revenue (current_period_revenue)
  auto_reverse: false
  note: "Complex calculation, may require management input"
```

---

### Category 5: Depreciation Expense

**Definition:** Systematic allocation of fixed asset cost over useful life.

#### 5.1 Fixed Asset Depreciation

```yaml
SCENARIO:
  situation: "Company owns equipment purchased 2 years ago"
  document_already_classified: "Purchase invoice recorded as Dr Fixed Assets"
  action_required: "Record monthly depreciation"
  
TEMPLATE: record_depreciation
  frequency: monthly
  source_data:
    - fixed_assets_register: "All depreciable assets"
    - depreciation_method: [straight_line, declining_balance, units_of_production]
    - calculation: "Automated from asset register"
  posting:
    - Dr: Depreciation Expense (total for all assets)
    - Cr: Accumulated Depreciation (total for all assets)
  auto_reverse: false
  auto_process: true (if fixed asset module integrated)
  
CALCULATION_EXAMPLES:
  straight_line:
    formula: "(Cost - Salvage Value) / Useful Life in Months"
    example: "($50,000 - $5,000) / 60 months = $750/month"
  
  declining_balance:
    formula: "Book Value × (Depreciation Rate / 12)"
    example: "$50,000 × (40% / 12) = $1,667 first month"
```

#### 5.2 Right-of-Use Asset Amortization (Leases)

```yaml
TEMPLATE: amortize_rou_asset
  frequency: monthly
  source_data:
    - rou_asset_cost: "From lease capitalization (LEASES category)"
    - lease_term: "Total months"
    - monthly_amortization: "ROU Asset Cost / Lease Term"
  posting:
    - Dr: Lease Amortization Expense
    - Cr: Accumulated Amortization - ROU Asset
  auto_reverse: false
  note: "Separate from lease payment posting (which is document-driven)"
```

---

### Category 6: Foreign Currency Revaluation

**Definition:** Adjust outstanding foreign currency balances to current exchange rates.

#### 6.1 FX Revaluation of AR/AP

```yaml
SCENARIO:
  situation: "EUR 10,000 receivable outstanding, exchange rate changed"
  document_already_classified: "Original EUR invoice recorded when rate was 1.10"
  action_required: "Revalue to current rate at month-end"
  
TEMPLATE: revalue_foreign_currency_balances
  frequency: monthly (or more frequently)
  source_data:
    - foreign_currency_balances: "All AR/AP in foreign currencies"
    - original_fx_rates: "Rate when transaction recorded"
    - current_fx_rate: "Spot rate at period-end"
    - unrealized_gain_loss: "(Current Rate - Original Rate) × Foreign Amount"
  posting:
    - Dr: Accounts Receivable (if gain) or Cr (if loss)
    - Cr: Unrealized FX Gain (if gain) or Dr: Unrealized FX Loss (if loss)
  auto_reverse: false
  requires_approval: true
  
EXAMPLE:
  original_transaction: "EUR 10,000 invoice at 1.10 = $11,000"
  month_end_rate: 1.15
  revalued_amount: EUR 10,000 × 1.15 = $11,500
  unrealized_gain: $11,500 - $11,000 = $500
  posting:
    - Dr: Accounts Receivable $500
    - Cr: Unrealized FX Gain $500
```

---

### Category 7: Provisions & Allowances

**Definition:** Estimates for future obligations or losses.

#### 7.1 Bad Debt Allowance Adjustment

```yaml
SCENARIO:
  situation: "Aging analysis shows increased risk of non-collection"
  no_document: "Management estimate based on aging report"
  action_required: "Adjust allowance for doubtful accounts"
  
TEMPLATE: adjust_bad_debt_allowance
  frequency: monthly or quarterly
  source_data:
    - ar_aging_report: "All outstanding receivables"
    - allowance_method: [percentage_of_sales, aging_method]
    - required_allowance: "Calculated based on method"
    - current_allowance_balance: "Existing balance"
    - adjustment_needed: "required_allowance - current_allowance_balance"
  posting:
    - Dr: Bad Debt Expense (adjustment_needed)
    - Cr: Allowance for Doubtful Accounts (adjustment_needed)
  auto_reverse: false
  requires_approval: true
  
NOTE: |
  This is different from actual bad debt write-off (which IS document-driven,
  triggered by bankruptcy notice or legal letter via SALES category).
  
  Allowance adjustment = estimate of future bad debts
  Bad debt write-off = specific invoice written off (document-driven)
```

#### 7.2 Warranty Provision

```yaml
TEMPLATE: accrue_warranty_provision
  frequency: monthly
  source_data:
    - sales_with_warranty: "Product sales this month"
    - warranty_percentage: "Historical warranty claim rate (e.g., 2%)"
    - provision_amount: "sales_with_warranty × warranty_percentage"
  posting:
    - Dr: Warranty Expense (provision_amount)
    - Cr: Warranty Provision (Liability) (provision_amount)
  auto_reverse: false
  note: "Actual warranty claims reduce provision (document-driven via EXPENSES)"
```

#### 7.3 Legal Provision

```yaml
TEMPLATE: accrue_legal_provision
  frequency: as_needed (triggered by legal event)
  source_data:
    - legal_case_details: "From legal counsel"
    - estimated_loss: "Management/counsel estimate"
    - probability: "Probable/Possible/Remote"
  posting:
    - Dr: Legal Expense (estimated_loss)
    - Cr: Legal Provision (Liability) (estimated_loss)
  auto_reverse: false
  requires_approval: true
  note: "Only accrue if loss is probable and estimable (ASC 450)"
```

---

### Category 8: Inventory Valuation Adjustments

#### 8.1 Lower of Cost or Market (LCM) Adjustment

```yaml
SCENARIO:
  situation: "Inventory market value dropped below cost"
  no_document: "Management determination based on market analysis"
  action_required: "Write down inventory to market value"
  
TEMPLATE: inventory_lcm_adjustment
  frequency: quarterly or annually
  source_data:
    - inventory_cost: "From inventory system"
    - market_value: "Current replacement cost or NRV"
    - writedown_amount: "cost - market (if market < cost)"
  posting:
    - Dr: Inventory Write-down Expense (writedown_amount)
    - Cr: Inventory Valuation Reserve (writedown_amount)
  auto_reverse: false
  requires_approval: true
  
NOTE: |
  This is different from physical inventory write-off (which IS document-driven,
  triggered by damage report or obsolescence notice via INVENTORY category).
  
  LCM adjustment = market value decline (estimate)
  Physical write-off = damaged/obsolete units (document-driven)
```

---

### Category 9: Cost Allocations

#### 9.1 Overhead Allocation

```yaml
TEMPLATE: allocate_overhead_costs
  frequency: monthly
  source_data:
    - total_overhead: "Rent, utilities, admin salaries"
    - allocation_basis: [square_footage, headcount, revenue, direct_labor_hours]
    - departments: "List of cost centers"
  posting:
    - Dr: Department A Overhead (allocated amount)
    - Dr: Department B Overhead (allocated amount)
    - Cr: Overhead Pool (total overhead)
  auto_reverse: false
  requires_approval: false
```

#### 9.2 Shared Service Allocation

```yaml
TEMPLATE: allocate_shared_services
  frequency: monthly
  source_data:
    - shared_service_costs: "IT, HR, Finance department costs"
    - allocation_method: "Agreed upon basis"
  posting:
    - Dr: Various Departments (allocated portions)
    - Cr: Shared Services Pool
  auto_reverse: false
```

---

## Month-End Checklist Template

```yaml
MONTH_END_CHECKLIST:
  period: "December 2025"
  generated_date: "2025-12-31"
  due_date: "2026-01-05"
  
  categories:
    
    1_ACCRUALS:
      - item: "Accrue utilities expense"
        template: accrued_utilities
        status: not_started
        requires_data: "Prior month bill amount"
        auto_process: false
        
      - item: "Accrue rent (if invoice not received)"
        template: accrued_rent
        status: not_started
        check_first: "Has rent invoice been received and classified?"
        auto_process: false
        
      - item: "Accrue interest on loans"
        template: accrued_interest
        status: not_started
        auto_process: true
        
      - item: "Accrue unbilled professional services"
        template: accrue_unbilled_revenue
        status: not_started
        requires_data: "Timesheet data from PM system"
        auto_process: false
        
    2_DEFERRALS:
      - item: "Amortize prepaid insurance"
        template: amortize_prepaid_insurance
        status: not_started
        auto_process: true (if prepaid register exists)
        
      - item: "Amortize prepaid rent"
        template: amortize_prepaid_rent
        status: not_started
        auto_process: true
        
      - item: "Recognize deferred revenue (customer deposits)"
        template: recognize_deferred_revenue
        status: not_started
        requires_data: "Contract terms and service delivery status"
        auto_process: false
        
    3_DEPRECIATION:
      - item: "Record fixed asset depreciation"
        template: record_depreciation
        status: not_started
        auto_process: true (if fixed asset module integrated)
        
      - item: "Amortize ROU assets (leases)"
        template: amortize_rou_asset
        status: not_started
        auto_process: true
        
    4_REVALUATIONS:
      - item: "Revalue foreign currency AR/AP balances"
        template: revalue_foreign_currency_balances
        status: not_started
        requires_data: "Current FX rates"
        auto_process: false
        requires_approval: true
        
    5_PROVISIONS:
      - item: "Adjust bad debt allowance"
        template: adjust_bad_debt_allowance
        status: not_started
        requires_data: "AR aging report"
        auto_process: false
        requires_approval: true
        
      - item: "Accrue warranty provision"
        template: accrue_warranty_provision
        status: not_started
        auto_process: true (if sales data available)
        
    6_ALLOCATIONS:
      - item: "Allocate overhead costs"
        template: allocate_overhead_costs
        status: not_started
        auto_process: true
        
    7_INVENTORY:
      - item: "LCM adjustment (if needed)"
        template: inventory_lcm_adjustment
        status: not_started
        frequency: quarterly
        requires_approval: true
        
  completion_summary:
    total_items: 13
    completed: 0
    in_progress: 0
    not_started: 13
    requires_approval: 3
```

---

## Workflow Steps

### Step 1: Generate Checklist

```yaml
TRIGGER:
  - User clicks "Start Month-End Close"
  - System date reaches period-end + 1 day
  
ACTION:
  - System generates checklist from templates
  - Auto-populates data where available
  - Flags items requiring manual input
  - Sets due dates based on close calendar
```

### Step 2: Auto-Process Items

```yaml
FOR EACH item WHERE auto_process = true:
  1. Retrieve source data from system
  2. Calculate posting amounts
  3. Generate journal entry
  4. Post to GL (if approval not required)
  5. Mark item as "completed"
  6. Log transaction details
```

### Step 3: Manual Items

```yaml
FOR EACH item WHERE auto_process = false:
  1. Display item in review queue
  2. Show data entry form (if user input needed)
  3. Display calculated amounts (if formula exists)
  4. Allow user to edit/confirm
  5. Generate journal entry
  6. Mark item as "in_progress"
```

### Step 4: Approval Process

```yaml
FOR EACH item WHERE requires_approval = true:
  1. Generate posting for review
  2. Route to approver
  3. Approver reviews source data and calculation
  4. Approver approves or rejects
  5. If approved: post to GL
  6. If rejected: return to preparer with comments
```

### Step 5: Period Close

```yaml
WHEN all_items_completed = true:
  1. Run final validation checks
  2. Generate month-end reports (TB, P&L, BS)
  3. Close period (prevent further postings)
  4. Archive checklist and supporting documents
  5. Open next period
```

---

## Integration with Document Classification

### Clear Boundaries

```yaml
DOCUMENT_CLASSIFICATION handles:
  ✅ Physical document arrives → classify → post
  ✅ Examples:
    - Annual insurance invoice arrives → Record as prepaid asset
    - Customer pays $10K deposit → Record as customer deposit liability
    - Lease agreement signed → Capitalize ROU asset and lease liability
    - Vendor refund check arrives → Process refund
    
MONTH_END_WORKFLOW handles:
  ✅ No document, system-generated → calculate → post
  ✅ Examples:
    - Month-end → Amortize 1/12 of prepaid insurance
    - Month-end → Recognize 1/10 of customer deposit as revenue
    - Month-end → Record depreciation on fixed assets
    - Month-end → Accrue unbilled services
```

### Data Flow

```
DOCUMENT CLASSIFICATION
        ↓
   Initial Setup
   (Prepaid Asset,
    Customer Deposit,
    Fixed Asset, etc.)
        ↓
   Stored in System
   (GL, Subledgers)
        ↓
MONTH-END WORKFLOW
        ↓
   Amortization/Recognition
   (Monthly adjustments)
        ↓
   Updated Balances
```

### Example: Prepaid Insurance Flow

```yaml
MONTH 1 (January):
  Document Classification:
    - Document: Annual insurance invoice $12,000 arrives
    - Action: Record prepaid asset
    - Posting: Dr Prepaid Insurance $12,000, Cr Bank $12,000
    
MONTH 1-12 (Each Month):
  Month-End Workflow:
    - No document, just recurring template
    - Action: Amortize 1/12 monthly
    - Posting: Dr Insurance Expense $1,000, Cr Prepaid Insurance $1,000
```

### Example: Customer Deposit Flow

```yaml
MONTH 1 (January):
  Document Classification:
    - Document: Customer payment $10,000 for 10-month service contract
    - Action: Record customer deposit liability
    - Posting: Dr Bank $10,000, Cr Customer Deposits $10,000
    
MONTH 1-10 (Each Month as service delivered):
  Month-End Workflow:
    - No document, just recurring template based on contract terms
    - Action: Recognize 1/10 revenue monthly
    - Posting: Dr Customer Deposits $1,000, Cr Service Revenue $1,000
```

---

## Recurring Template Library

### Template Storage

```yaml
TEMPLATE_REGISTRY:
  
  template_id: "TPL-001"
  template_name: "Amortize Prepaid Insurance"
  category: "Deferrals"
  frequency: "monthly"
  active: true
  
  source_accounts:
    - account: "Prepaid Insurance" (Asset)
    - data_source: "GL balance"
    
  calculation:
    method: "Fixed amount per prepaid asset"
    formula: "Prepaid Balance / Remaining Months"
    
  posting_entries:
    - debit:
        account: "Insurance Expense"
        amount: "calculated"
        description: "Monthly insurance amortization"
    - credit:
        account: "Prepaid Insurance"
        amount: "calculated"
        description: "Monthly insurance amortization"
        
  auto_reverse: false
  auto_process: true
  requires_approval: false
  
  last_executed: "2025-11-30"
  next_execution: "2025-12-31"
```

### Template Categories

```yaml
TEMPLATE_CATEGORIES:
  
  ACCRUALS:
    - Accrued Utilities
    - Accrued Rent
    - Accrued Interest
    - Accrued Revenue
    
  DEFERRALS:
    - Amortize Prepaid Insurance
    - Amortize Prepaid Rent
    - Amortize Software Subscriptions
    - Recognize Deferred Revenue
    
  DEPRECIATION:
    - Fixed Asset Depreciation
    - ROU Asset Amortization
    
  REVALUATIONS:
    - FX Revaluation AR/AP
    - Inventory LCM Adjustment
    
  PROVISIONS:
    - Bad Debt Allowance
    - Warranty Provision
    - Legal Provision
    
  ALLOCATIONS:
    - Overhead Allocation
    - Shared Services Allocation
```

---

## Auto-Reversing Entries

### Concept

Some month-end accruals are **estimates** that reverse automatically when the actual transaction occurs.

```yaml
AUTO_REVERSE_PATTERN:
  
  Month 1 (December 31):
    Accrual Entry:
      Dr: Utilities Expense $1,200
      Cr: Accrued Utilities Payable $1,200
    Status: "Estimate based on prior month"
    
  Month 2 (January 1):
    Reversal Entry (automatic):
      Dr: Accrued Utilities Payable $1,200
      Cr: Utilities Expense $1,200
    Status: "Auto-reversed"
    
  Month 2 (January 15):
    Actual Invoice (via document classification):
      Dr: Utilities Expense $1,250
      Cr: Accounts Payable $1,250
    Status: "Actual invoice received and classified"
    
  NET RESULT:
    December: $1,200 expense (estimate)
    January: $1,250 - $1,200 = $50 expense (correction)
```

### Templates with Auto-Reverse

```yaml
TEMPLATES_WITH_AUTO_REVERSE:
  - Accrued Utilities
  - Accrued Rent (when invoice not received)
  - Accrued Unbilled Revenue
  
  auto_reverse: true
  reversal_date: "1st of next period"
  reversal_method: "Exact reversal of original entry"
```

---

## Approval Workflows

### Approval Thresholds

```yaml
APPROVAL_RULES:
  
  no_approval_required:
    - Auto-calculated entries (depreciation, standard amortization)
    - Amount < $1,000
    - Recurring templates previously approved
    
  manager_approval:
    - Amount $1,000 - $10,000
    - New recurring templates
    - Manual accruals
    
  controller_approval:
    - Amount > $10,000
    - Provisions and allowances
    - FX revaluations
    - Inventory write-downs
    - Non-standard adjustments
```

### Approval Process

```yaml
APPROVAL_WORKFLOW:
  
  1. Entry Generated:
    - System creates journal entry
    - Status: "Pending Approval"
    - Notifies approver
    
  2. Approver Reviews:
    - Views entry details
    - Reviews supporting calculation
    - Checks source data
    
  3. Decision:
    - Approve → Entry posts to GL
    - Reject → Returns to preparer with comments
    - Request Info → Flags for additional detail
    
  4. Audit Trail:
    - Logs approver, timestamp, decision
    - Stores comments and supporting documents
```

---

## Reporting & Analytics

### Month-End Dashboard

```yaml
DASHBOARD_WIDGETS:
  
  checklist_progress:
    - Total items: 13
    - Completed: 8
    - In progress: 3
    - Not started: 2
    - % Complete: 62%
    
  approval_queue:
    - Pending approval: 3 items
    - Total value: $45,000
    - Oldest pending: "FX Revaluation (2 days)"
    
  recurring_templates:
    - Active templates: 15
    - Auto-processed this month: 9
    - Manual entries required: 6
    
  period_close_status:
    - Target close date: "January 5, 2026"
    - Days remaining: 3
    - On track: Yes
```

### Month-End Adjustment Report

```yaml
REPORT_STRUCTURE:
  
  period: "December 2025"
  report_date: "2026-01-05"
  
  summary_by_category:
    - Accruals: $18,500
    - Deferrals: $5,200
    - Depreciation: $12,750
    - Provisions: $3,000
    - Revaluations: $500
    - Total Adjustments: $39,950
    
  detail_by_entry:
    - Entry 1:
        description: "Accrue utilities expense"
        debit: "Utilities Expense $1,200"
        credit: "Accrued Utilities Payable $1,200"
        auto_reverse: Yes
        approved_by: "Controller"
        posted_date: "2025-12-31"
```

---

## Summary: Document-Driven vs System-Generated

```
┌─────────────────────────────────────────────────────────────┐
│ DOCUMENT CLASSIFICATION (Module 1)                          │
├─────────────────────────────────────────────────────────────┤
│ • Physical document arrives                                 │
│ • Mixtral classifies into 13 categories                     │
│ • Posts initial transaction                                 │
│ • Examples:                                                 │
│   - Invoice → Record prepaid asset                          │
│   - Deposit → Record customer deposit liability             │
│   - Lease → Capitalize ROU asset                            │
└─────────────────────────────────────────────────────────────┘
                              ↕
                    Feeds data to month-end
                              ↕
┌─────────────────────────────────────────────────────────────┐
│ MONTH-END WORKFLOW (Module 2)                               │
├─────────────────────────────────────────────────────────────┤
│ • No physical document                                      │
│ • System-generated calculations/estimates                   │
│ • Recurring templates execute                               │
│ • Examples:                                                 │
│   - Amortize prepaid asset monthly                          │
│   - Recognize customer deposit as revenue                   │
│   - Calculate depreciation                                  │
│   - Accrue unbilled services                                │
└─────────────────────────────────────────────────────────────┘
```

### Key Differences

| Aspect | Document Classification | Month-End Workflow |
|--------|------------------------|-------------------|
| **Trigger** | Physical document arrives | Period-end date |
| **Input** | Document text + fields | System data + formulas |
| **Processing** | Mixtral AI classification | Templates + calculations |
| **Frequency** | Continuous (as documents arrive) | Monthly/quarterly/annually |
| **Examples** | Invoices, receipts, statements | Depreciation, accruals, deferrals |
| **Automation** | AI-driven pattern recognition | Formula-driven templates |
| **Approval** | Based on confidence score | Based on amount/materiality |

---

## Implementation Roadmap

### Phase 1: Core Templates (Weeks 1-2)

```yaml
DELIVERABLES:
  - Recurring template engine
  - 5 core templates:
    * Depreciation
    * Prepaid amortization
    * Deferred revenue recognition
    * Accrued expenses
    * Bad debt allowance
  - Manual entry interface
```

### Phase 2: Checklist System (Weeks 3-4)

```yaml
DELIVERABLES:
  - Month-end checklist generator
  - Auto-process engine
  - Approval workflow
  - Progress tracking dashboard
```

### Phase 3: Advanced Features (Weeks 5-6)

```yaml
DELIVERABLES:
  - FX revaluation engine
  - Provisions and allocations
  - Auto-reversing entry logic
  - Integration with document classification
```

---

**End of Month-End Workflow Document**

This document ensures that **system-generated** period-end adjustments are handled separately from **document-driven** classification, creating clear boundaries and workflows for each.
