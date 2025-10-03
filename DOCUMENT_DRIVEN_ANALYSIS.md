# Document-Driven vs System-Generated Transactions
## Rethinking the Classification Gaps

**Key Question:** Should the classification system handle these, or are they **system-generated adjustments**?

---

## Analysis: What's Document-Driven vs System-Generated?

### ✅ **DOCUMENT-DRIVEN (Classification System Should Handle)**

These arrive as **physical documents** that need classification:

#### 1. **Foreign Currency Invoices** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Foreign vendor invoice (EUR invoice received by USD company)
WORKFLOW:
  1. DocStrange extracts: Amount=€1,000, Vendor=German Co
  2. Classification: PURCHASES + FOREIGN_CURRENCY flag
  3. System asks: "Exchange rate?" or pulls from daily rates
  4. Posts: Dr Expense $1,080, Cr AP $1,080 (at spot rate)
  5. FX gain/loss calculated later when paid

SUGGESTED_ACTIONS:
  - record_foreign_currency_bill
  - set_exchange_rate
  - track_for_fx_realization
```

#### 2. **Inter-Company Invoices** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Invoice from subsidiary company
WORKFLOW:
  1. DocStrange extracts: Invoice, amounts
  2. System detects vendor is in "related entities" list
  3. Classification: PURCHASES + INTERCOMPANY flag
  4. Posts to: Dr Expense, Cr Intercompany Payable (not regular AP)

SUGGESTED_ACTIONS:
  - record_intercompany_bill
  - flag_for_consolidation_elimination
```

#### 3. **Customer Prepayments/Deposits** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Customer payment receipt (before work is done)
WORKFLOW:
  1. DocStrange extracts: Payment $5,000, Customer=ABC Corp
  2. System sees: No invoice reference
  3. Classification asks: "Is this for future services?"
  4. User confirms → Posts: Dr Bank, Cr Deferred Revenue

SUGGESTED_ACTIONS:
  - record_customer_deposit
  - create_deferred_revenue_liability
  - schedule_revenue_recognition (optional)
```

#### 4. **Prepaid Expense Invoices** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Annual insurance invoice
WORKFLOW:
  1. DocStrange extracts: Amount=$12,000, Period=12 months, Vendor=Insurance Co
  2. System detects: Period > 1 month
  3. Classification suggests: "Prepaid asset or expense?"
  4. User selects prepaid → Posts: Dr Prepaid Insurance, Cr Bank/AP

SUGGESTED_ACTIONS:
  - record_prepaid_expense
  - set_amortization_schedule (12 months)
  - create_recurring_amortization_entries (optional automation)
```

#### 5. **Lease Agreements** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Lease agreement or lease payment invoice
WORKFLOW:
  1. DocStrange extracts: Monthly payment, lease term
  2. Classification: LEASES category
  3. System asks: "Finance or operating lease?"
  4. User selects → System calculates PV of payments

SUGGESTED_ACTIONS:
  - recognize_lease_liability
  - record_lease_payment
  - amortize_rou_asset
```

#### 6. **Bad Debt Notices** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Collection agency notice or bankruptcy filing
WORKFLOW:
  1. User uploads bankruptcy notice
  2. Classification: SALES → BAD_DEBT_WRITEOFF
  3. System shows outstanding AR for that customer
  4. User confirms → Posts: Dr Bad Debt Expense, Cr AR

SUGGESTED_ACTIONS:
  - write_off_customer_account
  - adjust_allowance_for_doubtful_accounts
```

#### 7. **Inventory Write-off Forms** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Inventory count adjustment form, damage report
WORKFLOW:
  1. User uploads inventory adjustment document
  2. Classification: INVENTORY → INVENTORY_WRITEOFF
  3. Posts: Dr COGS/Inventory Loss, Cr Inventory

SUGGESTED_ACTIONS:
  - record_inventory_writeoff
  - adjust_inventory_quantity
```

#### 8. **Loan Statements with Principal/Interest** ✅ ALREADY COVERED
```yaml
DOCUMENT: Loan statement showing payment breakdown
WORKFLOW:
  1. Classification: DEBT → LOAN_PAYMENT
  2. System extracts principal vs interest
  3. Posts: Dr Loan Payable, Dr Interest Expense, Cr Bank

ALREADY IN SYSTEM ✓
```

#### 9. **Refund Receipts** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Vendor refund check, customer refund request
WORKFLOW:
  1. DocStrange extracts: Refund amount, party
  2. Classification distinguishes:
     - Vendor refund (money in) vs
     - Customer refund (money out, not credit note)

SUGGESTED_ACTIONS:
  - record_vendor_refund (Dr Bank, Cr Expense)
  - record_customer_refund (Dr Refunds, Cr Bank)
```

#### 10. **Government Grant Award Letters** ✅ KEEP IN CLASSIFICATION
```yaml
DOCUMENT: Grant award letter, subsidy payment notice
WORKFLOW:
  1. User uploads grant award letter
  2. Classification: GRANTS → GOVERNMENT_GRANT
  3. System asks: "Conditional or unconditional?"

SUGGESTED_ACTIONS:
  - record_grant_income (if unconditional)
  - record_deferred_grant (if conditional)
```

---

### ❌ **SYSTEM-GENERATED (Month-End Checklist, NOT Classification)**

These are **NOT documents** - they're accounting adjustments:

#### 1. **Accrued Expenses** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: No document exists
EXAMPLE: Accrued rent, accrued utilities (bill hasn't arrived yet)

BETTER WORKFLOW: Month-End Checklist
  □ Review rent expense - accrue if not billed
  □ Review utilities - accrue based on estimate
  □ Review interest expense - accrue based on loan balance

SYSTEM FEATURE: Recurring Templates
  - "Rent Accrual Template"
    * Posts: Dr Rent Expense, Cr Accrued Rent Payable
    * Auto-reverses 1st of next month
  - User clicks "Post Template" during month-end close

NOT A DOCUMENT CLASSIFICATION PROBLEM ✗
```

#### 2. **Depreciation** ❌ REMOVE FROM CLASSIFICATION (Already system-generated)
```yaml
PROBLEM: No document exists
WORKFLOW: System automatically calculates from fixed asset register
  - Monthly depreciation based on asset class, useful life
  - Posts: Dr Depreciation Expense, Cr Accumulated Depreciation

SYSTEM FEATURE: Automated depreciation runs
NOT A DOCUMENT CLASSIFICATION PROBLEM ✗
```

#### 3. **Prepaid Amortization** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: Monthly amortization is system-generated
DOCUMENT-DRIVEN PART: Initial prepaid recording (when invoice arrives)
SYSTEM-GENERATED PART: Monthly amortization

SPLIT WORKFLOW:
  1. Invoice arrives → Classification handles: "Record as prepaid asset"
  2. System creates recurring template: "$1,000/month amortization"
  3. User posts template monthly (or auto-posts)

CLASSIFICATION HANDLES: Step 1 only (document arrival)
MONTH-END HANDLES: Step 3 (recurring entry)
```

#### 4. **Revenue Recognition (Deferred Revenue Amortization)** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: Monthly revenue recognition is system-generated
DOCUMENT-DRIVEN PART: Customer prepayment receipt
SYSTEM-GENERATED PART: Monthly revenue recognition

SPLIT WORKFLOW:
  1. Payment received → Classification: "Deferred revenue"
  2. System creates recurring template: "$X/month revenue recognition"
  3. User posts template monthly

CLASSIFICATION HANDLES: Step 1 only
MONTH-END HANDLES: Step 3
```

#### 5. **Accrued Revenue (Unbilled)** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: No document exists (work done but not invoiced yet)
BETTER WORKFLOW: Month-End Checklist
  □ Review unbilled hours/projects
  □ Accrue revenue for completed milestones
  □ Reverse accrual when invoice is created

SYSTEM FEATURE: Project/timesheet integration
  - "Unbilled Revenue Report"
  - User reviews and posts accrual
  - Auto-reverses when invoice created

NOT A DOCUMENT CLASSIFICATION PROBLEM ✗
```

#### 6. **FX Revaluation** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: No document, period-end adjustment only
DOCUMENT-DRIVEN PART: Foreign currency invoice (handled above)
SYSTEM-GENERATED PART: Month-end FX revaluation

WORKFLOW:
  1. Foreign invoice recorded at spot rate (document-driven)
  2. Month-end: System revalues open foreign AP/AR
  3. Posts: Dr/Cr FX Gain/Loss

CLASSIFICATION HANDLES: Step 1 only
MONTH-END HANDLES: Step 2-3
```

#### 7. **Provisions (Warranty, Legal)** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: No document, management estimate
WORKFLOW: Month-End/Quarter-End
  - Management estimates warranty liability
  - Posts: Dr Warranty Expense, Cr Warranty Liability

SYSTEM FEATURE: Provision calculator
  - Based on sales % or historical data

NOT A DOCUMENT CLASSIFICATION PROBLEM ✗
```

#### 8. **Allowance for Doubtful Accounts** ❌ REMOVE FROM CLASSIFICATION
```yaml
PROBLEM: No document, periodic estimate
DOCUMENT-DRIVEN PART: Specific bad debt write-off (handled above)
SYSTEM-GENERATED PART: Allowance adjustment

WORKFLOW:
  1. Specific write-off → Classification handles (document exists)
  2. Allowance adjustment → Month-end process (no document)

CLASSIFICATION HANDLES: Specific write-offs only
MONTH-END HANDLES: Allowance adjustments
```

---

## Revised Gap Analysis

### ✅ **KEEP IN CLASSIFICATION (Document-Driven)**

1. **Foreign Currency Transactions** ✅
   - Foreign vendor/customer invoices
   - Multi-currency bank statements
   - **Action:** Add FOREIGN_CURRENCY flag to PURCHASES/SALES/BANKING

2. **Inter-Company Transactions** ✅
   - Inter-company invoices/payments
   - **Action:** Add INTERCOMPANY flag to all categories

3. **Customer Deposits/Prepayments** ✅
   - Payment received before work done
   - **Action:** Add to SALES category: record_customer_deposit

4. **Prepaid Expense Recording** ✅
   - Annual insurance invoice, prepaid rent invoice
   - **Action:** Add to PURCHASES: record_prepaid_expense

5. **Lease Documents** ✅
   - Lease agreements, lease payment invoices
   - **Action:** Add LEASES category

6. **Bad Debt Write-offs** ✅
   - Collection notices, bankruptcy filings
   - **Action:** Add to SALES: write_off_customer_account

7. **Inventory Write-offs** ✅
   - Damage reports, count adjustments
   - **Action:** Add to INVENTORY: record_inventory_writeoff

8. **Refunds** ✅
   - Vendor refund checks, customer refund requests
   - **Action:** Add refund actions to SALES/PURCHASES

9. **Government Grants** ✅
   - Grant award letters, subsidy notices
   - **Action:** Add GRANTS category (optional)

10. **COGS Recognition** ✅ (if triggered by document)
    - When sales invoice created → trigger COGS entry
    - **Action:** Enhance SALES to auto-calculate COGS

---

### ❌ **REMOVE FROM CLASSIFICATION (Month-End Checklist)**

These should be **separate month-end workflow**, NOT document classification:

1. **Accrued Expenses** (no document)
   - Recurring templates
   - Month-end checklist item

2. **Depreciation** (automated)
   - System calculates from asset register
   - Already separate process

3. **Prepaid Amortization** (system-generated)
   - Initial recording: Document-driven ✓
   - Monthly amortization: Recurring template ✗

4. **Deferred Revenue Recognition** (system-generated)
   - Initial recording: Document-driven ✓
   - Monthly recognition: Recurring template ✗

5. **Accrued Revenue/Unbilled** (no document)
   - Project/timesheet based
   - Month-end checklist item

6. **FX Revaluation** (period-end adjustment)
   - Initial FX transaction: Document-driven ✓
   - Period-end revaluation: Automated ✗

7. **Provisions** (management estimates)
   - No document, manual adjustment
   - Month-end/quarter-end item

8. **Allowance Adjustments** (periodic estimates)
   - Specific write-offs: Document-driven ✓
   - Allowance adjustment: Month-end ✗

---

## Recommended System Architecture

### 1. Document Classification Module (Current Focus)
```
Purpose: Classify incoming documents
Input: Physical documents (PDFs, images)
Output: Category + Action + GL routing
Coverage: 90% of daily transactions
```

### 2. Month-End Checklist Module (New, Separate)
```
Purpose: Guide period-end adjustments
Input: None (or system data like asset register)
Output: Journal entries for adjustments

Features:
  - Recurring templates (rent accrual, depreciation)
  - Auto-reversing entries
  - Checklist workflow
  - Approval routing

Items:
  □ Post depreciation (automated)
  □ Accrue rent expense (template)
  □ Accrue utilities (template)
  □ Amortize prepaid insurance (template)
  □ Recognize deferred revenue (template)
  □ Review unbilled revenue (manual)
  □ Revalue foreign currency balances (automated)
  □ Adjust allowance for doubtful accounts (manual)
  □ Review provisions (manual)
```

### 3. Recurring Entry Templates
```
Purpose: Automate repetitive adjustments

Examples:
  - "Monthly Rent Accrual" ($5,000)
    * Posts: Dr Rent Expense, Cr Accrued Rent
    * Auto-reverses: 1st of next month
    
  - "Prepaid Insurance Amortization" ($1,000/month)
    * Posts: Dr Insurance Expense, Cr Prepaid Insurance
    * Runs: Monthly for 12 months
    
  - "Depreciation - Office Equipment"
    * Posts: Dr Depreciation Expense, Cr Accumulated Depreciation
    * Auto-calculates from asset register
```

---

## Updated Classification System Scope

### IN SCOPE (Document Classification)
1. Foreign currency invoices/payments ✅
2. Inter-company transactions ✅
3. Customer deposits ✅
4. Prepaid expense invoices ✅
5. Lease agreements/payments ✅
6. Bad debt write-offs ✅
7. Inventory write-offs ✅
8. Refunds ✅
9. Government grants ✅
10. COGS calculation (on sales) ✅

### OUT OF SCOPE (Month-End Module)
1. Accrued expenses ❌
2. Depreciation ❌
3. Prepaid amortization ❌
4. Deferred revenue recognition ❌
5. Accrued revenue ❌
6. FX revaluation ❌
7. Provisions ❌
8. Allowance adjustments ❌

---

## Implementation Priority (Revised)

### Phase 1: Critical Document-Driven Enhancements

```yaml
1. FOREIGN_CURRENCY handling:
   - Flag on PURCHASES/SALES/BANKING
   - Exchange rate capture
   - FX gain/loss tracking

2. INTERCOMPANY flag:
   - All categories get inter-company indicator
   - Routes to Intercompany AR/AP

3. CUSTOMER_DEPOSITS:
   - Add to SALES: record_customer_deposit
   - Posts to Deferred Revenue

4. PREPAID_EXPENSES:
   - Add to PURCHASES: record_prepaid_expense
   - Posts to Prepaid Asset
   - Optional: Create amortization template

5. LEASES:
   - New category for lease documents
   - Finance vs operating distinction

6. WRITEOFFS:
   - Bad debt (SALES)
   - Inventory (INVENTORY)

7. REFUNDS:
   - Vendor refunds (PURCHASES)
   - Customer refunds (SALES)
```

**Estimated Timeline:** 2-3 weeks  
**Coverage Improvement:** 75% → 85%

### Phase 2: Month-End Module (Separate Project)

```yaml
Features:
  - Recurring entry templates
  - Month-end checklist
  - Auto-reversing entries
  - Automated depreciation
  - FX revaluation
  - Provision calculators

This is NOT part of document classification ✗
```

---

## Revised Category Count

**Current:** 11 categories  
**After Phase 1:** 12 categories + enhancements

```yaml
CATEGORIES (12 total):
  1. SALES (enhanced: deposits, bad debt, refunds)
  2. PURCHASES (enhanced: prepaid, foreign currency, inter-company)
  3. BANKING (enhanced: foreign currency, inter-company)
  4. EXPENSES (unchanged)
  5. PAYROLL (unchanged)
  6. INVENTORY (enhanced: write-offs)
  7. TAX (unchanged)
  8. FIXED_ASSETS (unchanged)
  9. DEBT (unchanged)
  10. EQUITY (unchanged)
  11. LEASES (new)
  12. OTHER (unchanged)

ENHANCEMENTS TO ALL:
  - Foreign currency flag
  - Inter-company flag
```

**Removed from scope:**
- ACCRUALS_DEFERRALS category (most items are system-generated, not document-driven)
- PROVISIONS category (no documents)
- Specific accrual/deferral subcategories

---

## Conclusion

**Key Insight:** The classification system should only handle **documents that arrive**, not **adjustments accountants make**.

**Document-Driven:** Invoice arrives → Classify → Post  
**System-Generated:** Month-end → Run template → Post

**Revised Gap List:**
- ✅ Keep: 10 document-driven enhancements
- ❌ Remove: 8 system-generated items (move to month-end module)

**This makes the system:**
- More focused
- Easier to implement
- Clearer boundaries
- Better separation of concerns

**Answer to your question:**
- **Accrued rent:** Month-end template (not classification)
- **Prepaid recording:** Classification handles (document exists)
- **Prepaid amortization:** Month-end template (not classification)
- **Best workflow:** Two separate modules working together

**Do you agree with this document-driven approach?**
