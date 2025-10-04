# Zoho Books API Field Mapping for Classification System Actions

**Version:** 2.0  
**Last Updated:** October 5, 2025  
**Purpose:** Map each classification system action to required and recommended Zoho Books API fields

---

## SALES Category Actions

### 1. create_sales_invoice

**Zoho Books API Endpoint:** `POST /invoices`

**Mandatory Fields:**
- `customer_id` (string) - ID of the customer the invoice is created for
- `line_items` (array) - At least one line item required
  - `item_id` (string) - ID of the item/product/service

**Highly Recommended Fields:**
- `invoice_number` (string) - Invoice number (auto-generated if omitted)
- `date` (string, yyyy-mm-dd) - Invoice date (defaults to today)
- `due_date` (string, yyyy-mm-dd) - Payment due date
- `reference_number` (string) - External reference (e.g., PO number)
- `currency_id` (string) - Currency for the invoice

**Line Item Fields:**
- `name` (string, max 100) - Item name
- `description` (string, max 2000) - Item description
- `rate` (number) - Unit price
- `quantity` (number) - Quantity sold
- `tax_id` (string) - Tax applied to this line item

**Tax & Location Fields:**
- `place_of_supply` (string) - For GST/VAT (IN, GCC editions)
- `gst_treatment` (string) - business_gst | business_none | overseas | consumer (IN)
- `tax_treatment` (string) - vat_registered | vat_not_registered | gcc_vat_registered (GCC, KE, ZA)
- `is_inclusive_tax` (boolean) - Whether prices include tax
- `location_id` (string) - Location where sale occurred

**Optional But Useful:**
- `payment_terms` (integer) - Payment terms in days (e.g., 15, 30, 60)
- `payment_terms_label` (string) - Override default label (e.g., "Net 15")
- `discount` (number) - Discount amount or percentage
- `discount_type` (string) - entity_level | item_level
- `is_discount_before_tax` (boolean) - Apply discount before tax calculation
- `shipping_charge` (number) - Shipping costs
- `adjustment` (number) - Manual adjustments
- `adjustment_description` (string) - Reason for adjustment
- `notes` (string) - Notes to customer
- `terms` (string) - Terms & conditions
- `salesperson_name` (string, max 200) - Salesperson name
- `custom_fields` (array) - Custom field values

**Address Fields:**
- `billing_address_id` (string) - ID of billing address
- `shipping_address_id` (string) - ID of shipping address

**Query Parameters:**
- `send` (boolean) - Send invoice to customer immediately
- `ignore_auto_number_generation` (boolean) - Use custom invoice number

**Documents Required from Classification:**
- customer_name → resolve to customer_id
- transaction_date → date
- due_date → due_date
- line_items with descriptions, quantities, rates
- tax_amount → tax_id lookup
- total_amount (for validation)

---

### 2. record_customer_deposit

**Zoho Books API Endpoint:** `POST /journals`

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Deposit date
- `reference_number` (string) - Check number, transaction ID
- `notes` (string) - "Customer deposit from [Customer Name]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Bank Account (asset)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 2 (Credit): Customer Deposits / Unearned Revenue (liability)
    - `account_id` (string)
    - `credit` (number)
    - `description` (string)

**Highly Recommended Fields:**
- `currency_id` (string) - Transaction currency
- `custom_fields` (array) - Customer reference for tracking

**Documents Required from Classification:**
- customer_name → in notes
- deposit_amount → debit/credit amounts
- deposit_date → journal_date
- payment_method → in description

---

### 3. process_customer_refund (Credit Note)

**Zoho Books API Endpoint:** `POST /creditnotes`

**Mandatory Fields:**
- `customer_id` (string) - Customer receiving refund
- `creditnote_number` (string) - Credit note number (if ignore_auto_number_generation=true)
- `date` (string, yyyy-mm-dd) - Credit note date
- `line_items` (array) - Items being credited
  - `item_id` (string) - ID of the item
  - `quantity` (number) - Quantity being refunded
  - `rate` (number) - Unit price

**Highly Recommended Fields:**
- `invoice_id` (string) - Original invoice ID (if crediting specific invoice)
- `reference_number` (string) - RMA number, return authorization, etc.
- `reason` (string) - Reason for credit note

**Optional But Useful:**
- `notes` (string) - Notes to customer
- `terms` (string) - Terms & conditions
- `custom_fields` (array) - Custom field values

**Query Parameters:**
- `invoice_id` (query param) - Link to original invoice
- `ignore_auto_number_generation` (boolean) - Use custom credit note number

**To Process Actual Refund:**
1. Create credit note (above)
2. Use `POST /creditnotes/{creditnote_id}/refunds` to issue refund
   - `date` (string) - Refund date
   - `refund_mode` (string) - Payment method for refund
   - `amount` (number) - Amount refunded
   - `from_account_id` (string) - Account to refund from

**Documents Required from Classification:**
- customer_name → resolve to customer_id
- original_invoice_number → resolve to invoice_id
- refund_amount → amount
- refund_reason → reason
- line_items being refunded

---

### 4. record_sales_receipt (Paid Invoice)

**Option 1: Create Invoice + Payment in One Go**

Same as `create_sales_invoice` but immediately followed by:

**Zoho Books API Endpoint:** `POST /customerpayments`

**Mandatory Fields:**
- `customer_id` (string) - Customer who paid
- `payment_mode` (string) - cash | check | bank_transfer | etc.
- `amount` (number) - Payment amount
- `date` (string, yyyy-mm-dd) - Payment date
- `account_id` (string) - Bank/cash account
- `invoices` (array) - Invoices being paid
  - `invoice_id` (string) - Invoice ID
  - `amount_applied` (number) - Amount applied to this invoice

**Documents Required from Classification:**
- All fields from create_sales_invoice
- payment_method → payment_mode
- payment_date → date
- bank_account → account_id

---

### 5. write_off_bad_debt

**Zoho Books API Endpoint:** `POST /invoices/{invoice_id}/writeoff`

**Mandatory Fields:**
- `invoice_id` (path parameter) - Invoice to write off

**No Request Body Required**

**Optional:**
- Use invoice comment API to add reason: `POST /invoices/{invoice_id}/comments`
  - `description` (string) - Reason for write-off

**Documents Required from Classification:**
- invoice_number → resolve to invoice_id
- write_off_reason → add as comment

---

## PURCHASES Category Actions

### 6. record_supplier_bill_inventory

**Zoho Books API Endpoint:** `POST /bills`

**Mandatory Fields:**
- `vendor_id` (string) - Vendor who sent the bill
- `bill_number` (string) - Bill/invoice number from vendor
- `date` (string, yyyy-mm-dd) - Bill date
- `line_items` (array) - At least one line item
  - `item_id` (string) - Inventory item ID
  - `name` (string) - Item name
  - `rate` (number) - Unit cost
  - `quantity` (number) - Quantity purchased
  - `account_id` (string) - Should be Inventory asset account

**Highly Recommended Fields:**
- `due_date` (string, yyyy-mm-dd) - Payment due date
- `reference_number` (string) - Your internal PO number
- `currency_id` (string) - Currency of the bill

**Line Item Fields:**
- `description` (string) - Item description
- `tax_id` (string) - Tax applied
- `project_id` (string) - Project association

**Optional But Useful:**
- `notes` (string) - Internal notes
- `terms` (string) - Vendor terms
- `custom_fields` (array) - Custom fields

**Query Parameters:**
- `attachment` (binary) - Attach bill PDF/image

**Documents Required from Classification:**
- vendor_name → resolve to vendor_id
- bill_number from document
- bill_date → date
- due_date if present
- line_items with inventory items
- tax_amount → tax_id lookup

---

### 7. record_supplier_bill_expense

**Zoho Books API Endpoint:** `POST /bills`

**Same as record_supplier_bill_inventory except:**

**Line Item Fields:**
- `account_id` (string) - Expense account (not Inventory account)
  - Examples: "Rent Expense", "Utilities", "Office Supplies"

**Documents Required from Classification:**
- Same as inventory bill
- Expense category → map to expense account_id

---

### 8. record_prepaid_expense

**Zoho Books API Endpoint:** `POST /journals`

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Payment/accrual date
- `reference_number` (string) - Vendor invoice number
- `notes` (string) - "Prepaid [expense type] from [Vendor] - Service period [dates]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Prepaid Expenses (asset account)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 2 (Credit): Bank Account OR Accounts Payable
    - `account_id` (string)
    - `credit` (number)
    - `description` (string)

**Highly Recommended Fields:**
- `currency_id` (string) - Transaction currency
- `custom_fields` (array) - Store service period, amortization details

**Documents Required from Classification:**
- vendor_name → in notes or resolve to vendor_id
- expense_amount → debit/credit amounts
- payment_date → journal_date
- service_period → in notes and custom_fields

---

### 9. process_vendor_refund (Vendor Credit)

**Zoho Books API Endpoint:** `POST /vendorcredits`

**Mandatory Fields:**
- `vendor_id` (string) - Vendor issuing credit
- `vendor_credit_number` (string) - Credit note number (if ignore_auto_number_generation=true)
- `date` (string, yyyy-mm-dd) - Credit note date
- `line_items` (array) - Items being credited
  - `item_id` (string) - Item ID (optional if using account_id)
  - `account_id` (string) - Expense/inventory account
  - `name` (string) - Line item name
  - `rate` (number) - Unit price
  - `quantity` (number) - Quantity

**Highly Recommended Fields:**
- `bill_id` (string) - Original bill ID being credited
- `reference_number` (string) - Vendor's credit note number

**Optional But Useful:**
- `notes` (string) - Internal notes
- `custom_fields` (array) - Custom fields

**Query Parameters:**
- `ignore_auto_number_generation` (boolean) - Use custom number
- `bill_id` (query param) - Associate with bill

**To Receive Actual Refund:**
Use `POST /vendorcredits/{vendor_credit_id}/refunds`
- `date` (string) - Refund date
- `refund_mode` (string) - Payment method
- `amount` (number) - Refund amount
- `deposit_to` (string) - Bank account receiving refund

**Documents Required from Classification:**
- vendor_name → resolve to vendor_id
- original_bill_number → resolve to bill_id
- credit_amount → amount
- line_items being credited

---

### 10. record_purchase_order (Memorandum)

**Zoho Books API Endpoint:** `POST /purchaseorders`

**Mandatory Fields:**
- `vendor_id` (string) - Vendor for PO
- `line_items` (array) - At least one line item
  - `item_id` (string) - Item ID
  - `rate` (number) - Unit price
  - `quantity` (number) - Quantity ordered

**Highly Recommended Fields:**
- `purchaseorder_number` (string) - PO number
- `date` (string, yyyy-mm-dd) - PO date
- `delivery_date` (string, yyyy-mm-dd) - Expected delivery date
- `reference_number` (string) - Your internal reference

**Optional But Useful:**
- `notes` (string) - Notes to vendor
- `terms` (string) - Terms & conditions
- `shipping_address_id` (string) - Delivery address
- `custom_fields` (array) - Custom fields

**No GL Impact - Memorandum Only**

**Documents Required from Classification:**
- vendor_name → resolve to vendor_id
- po_number
- line_items with item details
- delivery_date if present

---

## BANKING Category Actions

### 11. import_bank_statement_for_reconciliation

**Zoho Books API Endpoint:** `POST /banktransactions`

**Mandatory Fields:**
- `from_account_id` (string) - Bank account ID
- `transaction_type` (string) - deposit | withdrawal | transfer
- `amount` (number) - Transaction amount
- `date` (string, yyyy-mm-dd) - Transaction date

**Highly Recommended Fields:**
- `reference_number` (string) - Check number, transaction ID
- `description` (string) - Transaction description
- `payee` (string) - Who you paid or who paid you

**For Deposits:**
- `transaction_type` = "deposit"
- `to_account_id` (string) - Bank account (same as from_account_id for deposits)

**For Withdrawals:**
- `transaction_type` = "withdrawal"
- `paid_through_account_id` (string) - Bank account

**Categorization (Post-Import):**

**Match to Existing Invoice (Customer Receipt):**
Use `POST /customerpayments` with:
- `customer_id` (string)
- `amount` (number)
- `date` (string)
- `account_id` (string) - Bank account
- `invoices` (array) - Link to invoices
  - `invoice_id` (string)
  - `amount_applied` (number)

**Match to Existing Bill (Vendor Payment):**
Use `POST /vendorpayments` with:
- `vendor_id` (string)
- `amount` (number)
- `date` (string)
- `paid_through_account_id` (string) - Bank account
- `bills` (array) - Link to bills
  - `bill_id` (string)
  - `amount_applied` (number)

**Uncategorized Transaction:**
- Leave as bank transaction
- Manually categorize later via `PUT /banktransactions/{transaction_id}`

**Documents Required from Classification:**
- bank_account → from_account_id
- transaction_list with dates, amounts, descriptions
- Match logic: amount + date + party name

---

### 12. record_foreign_currency_transaction

**Zoho Books API Endpoint:** Same as above but with:

**Additional Mandatory Fields:**
- `currency_id` (string) - Transaction currency
- `exchange_rate` (number) - Exchange rate to base currency

**FX Gain/Loss:**
- Automatically calculated by Zoho Books
- Posted to FX Gain/Loss account in chart of accounts

**Documents Required from Classification:**
- transaction_currency → currency_id
- exchange_rate from document or market rate
- base_currency_amount for validation

---

### 13. record_intercompany_transaction

**Zoho Books API Endpoint:** `POST /journals`

**Note:** No native inter-company transaction support. Use journal entries.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Transaction date
- `reference_number` (string) - Inter-company transaction reference
- `notes` (string) - "Inter-company transaction with [Entity Name]"
- `line_items` (array) - At least 2 lines:
  - Line 1: Bank Account / AR / AP
    - `account_id` (string)
    - `debit` (number) or `credit` (number)
    - `description` (string)
  - Line 2: Inter-Company Receivable/Payable account
    - `account_id` (string)
    - `debit` (number) or `credit` (number)
    - `description` (string)

**Documents Required from Classification:**
- related_party_name → description
- transaction_amount → amount
- transaction_type (payment vs receipt)

---

## EXPENSES Category Actions

### 14. record_expense_receipt

**Zoho Books API Endpoint:** `POST /expenses`

**Mandatory Fields:**
- `account_id` (string) - Expense account (e.g., "Meals & Entertainment")
- `amount` (number) - Expense amount
- `date` (string, yyyy-mm-dd) - Expense date
- `paid_through_account_id` (string) - Cash, bank, credit card account

**Highly Recommended Fields:**
- `vendor_id` (string) - Merchant/vendor ID
- `description` (string) - What was purchased
- `reference_number` (string) - Receipt number

**Optional But Useful:**
- `currency_id` (string) - Currency
- `exchange_rate` (number) - If foreign currency
- `tax_id` (string) - Tax applied
- `project_id` (string) - Project association
- `customer_id` (string) - If billable to customer
- `is_billable` (boolean) - true if customer reimbursable
- `custom_fields` (array) - Custom fields

**Query Parameters:**
- `receipt` (binary) - Attach receipt image/PDF

**Documents Required from Classification:**
- merchant_name → resolve to vendor_id or create
- expense_amount → amount
- expense_date → date
- expense_category → map to account_id
- payment_method → map to paid_through_account_id

---

## PAYROLL Category Actions

### 15. import_payroll_batch

**Zoho Books API Endpoint:** Multiple journals or expenses

**Note:** Zoho Books doesn't have a dedicated payroll module. Options:

**Option A: Journal Entry**

Use `POST /journals` with:
- `journal_date` (string) - Payroll date
- `reference_number` (string) - Payroll batch ID
- `notes` (string) - "Payroll for period [dates]"
- `line_items` (array)
  - Debit: Salary Expense, Payroll Tax Expense
  - Credit: Employee Net Pay Payable, Tax Payable

**Option B: Individual Expenses**

Create expense per employee using `POST /expenses`

**Documents Required from Classification:**
- payroll_date → journal_date
- employee_list with gross pay, deductions, net pay
- employer_taxes → separate line items
- payroll_period → in description/notes

---

## INVENTORY Category Actions

### 16. record_goods_receipt

**Zoho Books API Endpoint:** Handled via receiving against Purchase Order

**Step 1: Update Purchase Order Status**

`PUT /purchaseorders/{po_id}` - Mark as received

**Step 2: Create Bill (if not created yet)**

`POST /bills` - Convert PO to bill
- Link to `purchaseorder_id`

**Zoho Books Updates Inventory Automatically:**
- When bill is created from PO
- Inventory quantity increases
- Inventory value increases (at bill rate)

**Documents Required from Classification:**
- po_number → resolve to purchaseorder_id
- items_received with quantities

---

### 17. record_inventory_adjustment

**Zoho Books API Endpoint:** `POST /inventoryadjustments`

**Mandatory Fields:**
- `date` (string, yyyy-mm-dd) - Adjustment date
- `reason` (string) - Reason for adjustment
- `adjustment_type` (string) - quantity | value
- `line_items` (array)
  - `item_id` (string) - Item being adjusted
  - `quantity_adjusted` (number) - Quantity change (+/-)
  - `warehouse_id` (string) - Warehouse (if multi-warehouse)

**Highly Recommended Fields:**
- `reference_number` (string) - Physical count reference
- `description` (string) - Detailed notes

**Documents Required from Classification:**
- adjustment_date → date
- items with quantity adjustments
- adjustment_reason → reason

---

### 18. record_inventory_writeoff

**Zoho Books API Endpoint:** `POST /inventoryadjustments`

**Mandatory Fields:**
- `date` (string, yyyy-mm-dd) - Write-off date
- `reason` (string) - "Obsolete" | "Damaged" | "Expired"
- `adjustment_type` = "quantity"
- `line_items` (array)
  - `item_id` (string)
  - `quantity_adjusted` (number) - Negative quantity
  - `warehouse_id` (string)

**GL Posting:**
- Zoho Books posts:
  - Debit: Inventory Adjustment/Write-off Expense account
  - Credit: Inventory asset account

**Documents Required from Classification:**
- writeoff_date → date
- items with quantities to write off
- writeoff_reason → reason

---

### 19. calculate_and_post_cogs (Automated)

**Zoho Books Behavior:**

**COGS is automatically calculated and posted when:**
- Sales invoice is created with inventory items
- Invoice status changes to "Sent" or "Paid"

**COGS Calculation Method (Set in Settings):**
- FIFO (First In First Out)
- LIFO (Last In First Out) - if allowed by jurisdiction
- Average Cost

**GL Posting (Automatic):**
- Debit: Cost of Goods Sold (COGS) account
- Credit: Inventory asset account

**No API Call Required - Fully Automated**

**Validation:**
- Use `GET /invoices/{invoice_id}` and check inventory movement
- Use inventory reports to validate COGS posting

---

## TAX Category Actions

### 20. record_tax_invoice (with tax tracking)

**Same as create_sales_invoice or record_supplier_bill**

**Tax-Specific Fields:**
- `tax_id` (string) - Tax rate ID (per line item)
- `is_inclusive_tax` (boolean) - Tax included in price
- `place_of_supply` (string) - Tax jurisdiction (GST/VAT)
- `gst_treatment` | `tax_treatment` | `vat_treatment` - Customer tax status

**Tax authorities and tax rates must be pre-configured in Zoho Books**

---

### 21. record_tax_payment

**Recommended Approach: Journal Entry (Proper Accounting)**

**Zoho Books API Endpoint:** `POST /journals`

**Why Journal Entry:**
- Clears liability account directly
- Matches tax accrual from sales/purchases
- Cleaner audit trail
- No vendor confusion (tax authority as vendor is messy)

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Payment date
- `reference_number` (string) - Tax payment reference/receipt number
- `notes` (string) - "[Tax Type] payment to [Tax Authority] for period [dates]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit):
    - `account_id` (string) - Tax Payable (liability account)
    - `debit` (number) - Payment amount
    - `description` (string) - "GST/VAT/Sales Tax payment for Q1 2024"
  - Line 2 (Credit):
    - `account_id` (string) - Bank Account (asset)
    - `credit` (number) - Payment amount
    - `description` (string) - "Payment to [Tax Authority Name]"

**Highly Recommended Fields:**
- `currency_id` (string) - Transaction currency
- `custom_fields` (array) - Store:
  - Tax period (start/end dates)
  - Tax authority name
  - Tax return reference number

**Tax Payable Account Setup:**
- Create separate accounts for different tax types:
  - "GST Payable" or "VAT Payable"
  - "Sales Tax Payable"
  - "Payroll Tax Payable"
  - "Income Tax Payable"

**Documents Required from Classification:**
- tax_authority → in notes
- tax_amount → debit/credit amounts
- tax_period → in notes and custom_fields
- payment_date → journal_date
- tax_type → determine correct Tax Payable account

---

### 22. record_tax_filing (Tax Return)

**Zoho Books API Endpoint:** `POST /journals`

**Mandatory Fields:**
- `journal_date` (string) - Filing date
- `reference_number` (string) - Return filing number
- `notes` (string) - "Tax return for period [dates]"
- `line_items` (array)
  - Debit or Credit: Tax Payable/Receivable accounts
  - Offsetting entries based on tax liability or refund

**Documents Required from Classification:**
- filing_date → journal_date
- tax_liability_or_refund → line item amounts
- tax_period → in notes

---

## FIXED_ASSETS Category Actions

### 23. capitalize_fixed_asset

**Zoho Books API Endpoint:** `POST /fixedassets`

**Mandatory Fields:**
- `asset_name` (string) - Name of the asset
- `asset_type_id` (string) - Asset type ID (must be pre-configured)
- `purchase_date` (string, yyyy-mm-dd) - Purchase date
- `purchase_price` (number) - Asset cost
- `depreciation_method` (string) - straight_line | reducing_balance | double_declining
- `salvage_value` (number) - Residual value at end of life
- `useful_life_years` (number) - Asset useful life in years

**Highly Recommended Fields:**
- `description` (string) - Asset description
- `serial_number` (string) - Asset serial/identification number
- `vendor_id` (string) - Vendor who sold the asset
- `location` (string) - Physical location
- `depreciation_start_date` (string, yyyy-mm-dd) - When to start depreciation

**To Link to Bill:**
1. Create bill first: `POST /bills`
2. Then create asset with `bill_id` reference (if supported) or use custom_field

**GL Posting (Automatic when asset created):**
- Debit: Fixed Assets account
- Credit: Accounts Payable or Bank Account

**Documents Required from Classification:**
- asset_description → asset_name
- purchase_price → purchase_price
- purchase_date → purchase_date
- vendor_name → resolve to vendor_id
- useful_life → useful_life_years
- asset_category → map to asset_type_id

---

### 24. record_asset_disposal

**Zoho Books API Endpoint:** `PUT /fixedassets/{asset_id}/dispose`

**Mandatory Fields:**
- `disposal_date` (string, yyyy-mm-dd) - Date of disposal
- `disposal_type` (string) - sale | write_off | donation
- `disposal_amount` (number) - Sale proceeds (or 0 if write-off)

**Optional:**
- `notes` (string) - Disposal notes

**GL Posting (Automatic):**
- Removes asset from books
- Calculates and posts gain/loss on disposal
  - Debit: Accumulated Depreciation
  - Debit: Bank/Cash (if sold) or Loss on Disposal
  - Credit: Fixed Asset account
  - Credit: Gain on Disposal (if gain)

**Documents Required from Classification:**
- asset_identification → resolve to asset_id
- disposal_date → disposal_date
- disposal_amount → disposal_amount
- disposal_type → disposal_type

---

### 25. record_depreciation_expense

**Zoho Books Behavior:**

**Depreciation is automatically calculated and can be posted:**

**Option 1: Automatic Posting (Recommended)**
- Set up depreciation schedules when creating assets
- Zoho Books auto-generates journal entries monthly/annually
- No API call needed

**Option 2: Manual Journal Entry**

`POST /journals` with:
- `journal_date` (string) - End of depreciation period
- `reference_number` (string) - "Depreciation [Month Year]"
- `notes` (string) - "Monthly depreciation"
- `line_items` (array)
  - Debit: Depreciation Expense account
  - Credit: Accumulated Depreciation account

**Documents Required from Classification:**
- depreciation_period → journal_date
- depreciation_amount per asset → line items

---

## DEBT Category Actions

### 26. record_loan_proceeds

**Zoho Books API Endpoint:** `POST /journals` (REQUIRED - No loan module)

**Note:** Zoho Books has no dedicated loan/debt management module. Use journal entries.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Date loan proceeds received
- `reference_number` (string) - Loan agreement number
- `notes` (string) - "Loan proceeds from [Lender Name] - Loan #[number]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Bank Account (asset)
    - `account_id` (string)
    - `debit` (number) - Loan principal amount
    - `description` (string)
  - Line 2 (Credit): Loan Payable (long-term liability)
    - `account_id` (string)
    - `credit` (number) - Loan principal amount
    - `description` (string)

**Documents Required from Classification:
- lender_name → in notes or vendor_id
- loan_amount → line item amounts
- loan_date → journal_date
- loan_agreement_number → reference_number

---

### 27. record_debt_service_payment

**Zoho Books API Endpoint:** `POST /journals` (REQUIRED - No automatic split)

**Note:** No automatic principal/interest split. Calculate externally using amortization schedule.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Payment date
- `reference_number` (string) - Payment confirmation number
- `notes` (string) - "Loan payment to [Lender] - Payment [X] of [Y]"
- `line_items` (array) - 3 lines:
  1. **Line 1 - Debit:** Loan Payable (liability reduction) - principal portion
  2. **Line 2 - Debit:** Interest Expense - interest portion
  3. **Line 3 - Credit:** Bank Account - total payment amount

**Note:** Calculate principal/interest split externally from amortization schedule.

**Documents Required from Classification:
- payment_date → journal_date
- total_payment_amount → credit to bank
- principal_portion → debit to loan payable
- interest_portion → debit to interest expense
- lender_name → in notes

---

### 28. reconcile_loan_balance

**Zoho Books API Endpoint:** `POST /journals` (if adjustment needed)

**Note:** Manual reconciliation process. Only create journal entry if discrepancy found.

**Process:**
1. Get current loan balance: Query Loan Payable account via reports or `GET /chartofaccounts`
2. Compare to loan statement balance from lender
3. If discrepancy exists, create adjustment journal entry

**Adjustment Journal Entry (if needed):**
- `journal_date` (string) - Reconciliation date
- `reference_number` (string) - Loan statement number
- `notes` (string) - "Loan balance adjustment - reconciliation to statement"
- `line_items` (array)
  - Debit: Loan Payable (if balance overstated) OR Credit: Loan Payable (if understated)
  - Credit: Interest Expense / Other Expense (if overstated) OR Debit: Interest Expense (if understated)

**Common Discrepancies:**
- Missed payment recording
- Incorrect principal/interest split
- Late fees not recorded
- Prepayment penalty not recorded

**Documents Required from Classification:**
- loan_statement_balance → compare to books balance
- any missing payments or fees → create journal entries

---

## EQUITY Category Actions

### 29. record_capital_contribution

**Zoho Books API Endpoint:** `POST /journals` (REQUIRED - No equity module)

**Note:** Zoho Books has no equity management module. Use journal entries.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Date of contribution
- `reference_number` (string) - Share certificate number, bank deposit reference
- `notes` (string) - "Capital contribution from [Owner Name] - [Ownership %]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Bank Account (asset)
    - `account_id` (string)
    - `debit` (number) - Contribution amount
    - `description` (string)
  - Line 2 (Credit): Owner's Equity or Share Capital (equity)
    - `account_id` (string)
    - `credit` (number) - Contribution amount
    - `description` (string)

**Documents Required from Classification:
- owner_name → in notes
- contribution_amount → line item amounts
- contribution_date → journal_date

---

### 30. record_dividend_distribution

**Zoho Books API Endpoint:** `POST /journals` (REQUIRED - No dividend module)

**Note:** No dividend management. Track shareholder allocations externally.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Declaration date (if accrual) or payment date (if cash)
- `reference_number` (string) - Dividend resolution number or payment reference
- `notes` (string) - "Dividend distribution - [Period] - [$ per share]"
- `line_items` (array)

**Two-Step Process:**

**Step 1 - Declaration (if accrual accounting):**
- Debit: Dividends Declared or Retained Earnings (equity)
- Credit: Dividends Payable (current liability)

**Step 2 - Payment:**
- Debit: Dividends Payable (current liability)
- Credit: Bank Account (asset)

**Documents Required from Classification:
- shareholder_name → in notes
- dividend_amount → line item amounts
- declaration_date vs payment_date

---

## LEASES Category Actions

### 31. capitalize_lease

**Zoho Books API Endpoint:** `POST /journals` (No lease accounting module)

**⚠️ NOTE:** Zoho Books has NO lease accounting module. External calculation required for ASC 842 / IFRS 16 compliance.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Lease commencement date
- `reference_number` (string) - Lease agreement number
- `notes` (string) - "Lease capitalization - [Asset Description] - ASC 842"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Right-of-Use (ROU) Asset account
    - `account_id` (string)
    - `debit` (number) - Present value of lease payments
    - `description` (string)
  - Line 2 (Credit): Lease Liability (long-term liability)
    - `account_id` (string)
    - `credit` (number) - Present value of lease payments
    - `description` (string)

**Documents Required from Classification:**
- lease_commencement_date → journal_date
- lease_term → for PV calculation
- monthly_payment → for PV calculation
- discount_rate → for PV calculation
- present_value_of_lease_payments → line item amounts

---

### 32. record_lease_payment

**Zoho Books API Endpoint:** `POST /journals` (No automatic amortization)

**Note:** Calculate principal/interest split externally using effective interest method.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Payment date
- `reference_number` (string) - Payment confirmation / check number
- `notes` (string) - "Lease payment [Month] - [Asset] - Payment [X] of [Y]"
- `line_items` (array) - 3 lines required:
  - Line 1 (Debit): Lease Liability (principal portion)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 2 (Debit): Interest Expense (interest portion)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 3 (Credit): Bank Account (total payment)
    - `account_id` (string)
    - `credit` (number)
    - `description` (string)

**Documents Required from Classification:**
- payment_date → journal_date
- monthly_payment → total credit to bank
- interest_portion (calculated) → debit to interest expense
- principal_portion (calculated) → debit to lease liability

---

### 33. record_rent_expense (Short-term Lease)

**Zoho Books API Endpoint:** `POST /expenses` or `POST /bills`

**Option A: Expense (if paid immediately)**

`POST /expenses` with:
- `account_id` (string) - Rent Expense account
- `amount` (number) - Rent amount
- `date` (string) - Payment date
- `paid_through_account_id` (string) - Bank account
- `vendor_id` (string) - Landlord/lessor
- `description` (string) - "Rent for [month] - [Property Address]"

**Option B: Bill (if invoice received)**

`POST /bills` with:
- `vendor_id` (string) - Landlord
- `bill_number` (string) - Invoice number
- `date` (string) - Bill date
- `line_items` (array)
  - `account_id` (string) - Rent Expense account
  - `name` (string) - "Rent"
  - `rate` (number) - Rent amount
  - `quantity` = 1

**Documents Required from Classification:**
- landlord_name → resolve to vendor_id
- rent_amount → amount
- rent_period → in description
- payment_date → date

---

## GRANTS Category Actions

### 34. record_grant_receipt

**Zoho Books API Endpoint:** `POST /journals` (No grant module)

**Note:** Track grant conditions and milestones externally.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Date grant funds received
- `reference_number` (string) - Grant award number
- `notes` (string) - "Grant from [Grantor] - [Purpose] - [Conditional/Unconditional]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Bank Account
    - `account_id` (string)
    - `debit` (number) - Grant amount
    - `description` (string)
  - Line 2 (Credit): Grant Revenue (unconditional) OR Deferred Grant Income (conditional)
    - `account_id` (string)
    - `credit` (number) - Grant amount
    - `description` (string)

**Highly Recommended Fields:**
- `custom_fields` (array) - Store grant conditions, milestones, recognition schedule

**Documents Required from Classification:**
- grantor_name → in notes
- grant_amount → line item amounts
- grant_date → journal_date
- grant_conditions → determine if deferred

---

### 35. match_grant_to_expenses

**Zoho Books API Endpoint:** `POST /journals` (No automatic matching)

**Note:** Track eligible expenses using Projects, Tags, or Custom Fields.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Recognition date
- `reference_number` (string) - Grant award ID + period reference
- `notes` (string) - "Grant revenue recognition - [Amount] eligible expenses - [Period]"
- `line_items` (array) - 2 lines required:
  - Line 1 (Debit): Deferred Grant Income (release liability)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 2 (Credit): Grant Revenue (recognize income)
    - `account_id` (string)
    - `credit` (number)
    - `description` (string)

**Documents Required from Classification:**
- grant_award_id → reference_number
- eligible_expenses → amount to recognize
- recognition_date → journal_date

---

## OTHER Category Actions

### 36. import_marketplace_settlement

**Zoho Books API Endpoint:** `POST /journals` (No native marketplace support)

**Note:** Parse settlement report externally before posting. Consider using marketplace integrations or middleware (Webgility, A2X).

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Settlement date
- `reference_number` (string) - Settlement ID from marketplace
- `notes` (string) - "Marketplace settlement from [Platform] - Period [dates] - [X] orders"
- `line_items` (array) - Typical structure:
  - Line 1 (Debit): Bank Account (net payout)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 2 (Debit): Marketplace Fees Expense (total fees)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 3 (Debit): Sales Returns & Allowances (if refunds exist)
    - `account_id` (string)
    - `debit` (number)
    - `description` (string)
  - Line 4 (Credit): Sales Revenue (gross sales)
    - `account_id` (string)
    - `credit` (number)
    - `description` (string)

**Highly Recommended Fields:**
- `custom_fields` (array) - Store settlement report URL, order count, fee breakdown

**Documents Required from Classification:**
- settlement_date → journal_date
- settlement_id → reference_number
- gross_sales → credit to revenue
- fees_breakdown → debit to expense accounts by type
- refunds_total → debit to returns & allowances
- net_payout → debit to bank account

---

### 37. import_batch_report

**Zoho Books API Endpoint:** `POST /journals` (No native batch import support)

**Note:** Parse batch report externally (POS EOD, payroll summary, payment processor settlement) before posting. Consider using POS/payroll integrations.

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Batch date
- `reference_number` (string) - Batch report number
- `notes` (string) - "[Batch Type] for [Location] - [Date] - [Transaction Count]"
- `line_items` (array) - Variable based on batch type, must balance

**Common Line Items (POS EOD):**
- Debits: Cash, Credit Card Clearing, Processing Fees, Discounts, Refunds
- Credits: Sales Revenue, Tax Payable, Tips Payable

**Common Line Items (Payroll):**
- Debits: Gross Wages, Employer Taxes
- Credits: Net Pay, Tax Withholdings, Payroll Clearing

**Highly Recommended Fields:**
- `custom_fields` (array) - Store batch ID, transaction count, location identifier

**Documents Required from Classification:**
- batch_date → journal_date
- batch_id → reference_number
- batch_type → in notes
- line_item_breakdown → parse to journal line_items
- transaction_count → in notes

---

### 38. manual_journal_entry

**Zoho Books API Endpoint:** `POST /journals`

**Mandatory Fields:**
- `journal_date` (string, yyyy-mm-dd) - Journal entry date
- `line_items` (array) - At least 2 lines (debits and credits must balance)
  - `account_id` (string) - Chart of accounts account ID
  - `debit` (number) - Debit amount (use 0 if credit)
  - `credit` (number) - Credit amount (use 0 if debit)
  - `description` (string) - Line item description

**Highly Recommended Fields:**
- `reference_number` (string) - JE reference number (e.g., "JE-2025-001")
- `notes` (string) - Overall journal entry purpose and explanation
- `currency_id` (string) - Currency (if multi-currency)

**Documents Required from Classification:**
- journal_date → journal_date
- line_items with account names/numbers, amounts, debit/credit indicator
- reference_number
- explanation → notes

---

## Field Priority Legend

**🔴 MANDATORY** - API will reject request without this field  
**🟡 HIGHLY RECOMMENDED** - Needed for proper business workflow  
**🟢 OPTIONAL** - Enhances data quality and reporting

---

## API Reference

**Base URL:** `https://www.zohoapis.com/books/v3/{endpoint}?organization_id={org_id}`

**Authentication:** OAuth 2.0 - Include `Authorization: Zoho-oauthtoken {access_token}` header

**Rate Limit:** 100 API calls per minute per organization

---

**End of Zoho Books Field Mapping Document**
