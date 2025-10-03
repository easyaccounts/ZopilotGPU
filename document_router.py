"""
Document Router for Llama 3-Powered Journal Entry Generation

This module routes extracted document data to appropriate Llama 3 prompts
based on document type and provides contextual information for intelligent
journal entry generation.
"""

from typing import Dict, Any, Optional
from enum import Enum
import json

class DocumentType(Enum):
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    RECEIPT = "receipt"
    PAYSLIP = "payslip"
    SYSTEM_REPORT = "system_report"
    UNKNOWN = "unknown"

class DocumentRouter:
    """
    Routes documents to appropriate processing based on extracted data
    and generates contextual prompts for Llama 3.
    """

    def __init__(self):
        self.field_templates = {
            DocumentType.INVOICE: self._get_invoice_fields(),
            DocumentType.BANK_STATEMENT: self._get_bank_statement_fields(),
            DocumentType.RECEIPT: self._get_receipt_fields(),
            DocumentType.PAYSLIP: self._get_payslip_fields(),
            DocumentType.SYSTEM_REPORT: self._get_system_report_fields(),
        }

    def route_document(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route document based on extracted data and generate Llama 3 prompt.

        Args:
            extracted_data: Structured data from DocStrange extraction

        Returns:
            Dict containing document_type, fields, prompt, and context
        """
        doc_type = self._classify_document(extracted_data)

        return {
            "document_type": doc_type.value,
            "extracted_fields": self._extract_relevant_fields(extracted_data, doc_type),
            "llama_prompt": self._generate_llama_prompt(doc_type, extracted_data),
            "processing_context": self._get_processing_context(doc_type),
            "confidence_score": self._calculate_confidence(extracted_data, doc_type)
        }

    def _classify_document(self, extracted_data: Dict[str, Any]) -> DocumentType:
        """
        Classify document type based on extracted fields and content patterns.
        """
        # Check for invoice indicators
        if self._has_invoice_indicators(extracted_data):
            return DocumentType.INVOICE

        # Check for bank statement indicators
        if self._has_bank_statement_indicators(extracted_data):
            return DocumentType.BANK_STATEMENT

        # Check for receipt indicators
        if self._has_receipt_indicators(extracted_data):
            return DocumentType.RECEIPT

        # Check for payslip indicators
        if self._has_payslip_indicators(extracted_data):
            return DocumentType.PAYSLIP

        # Check for system report indicators
        if self._has_system_report_indicators(extracted_data):
            return DocumentType.SYSTEM_REPORT

        return DocumentType.UNKNOWN

    def _has_invoice_indicators(self, data: Dict[str, Any]) -> bool:
        """Check for invoice-specific patterns"""
        text_content = json.dumps(data).lower()
        indicators = [
            'invoice', 'inv-', 'bill to', 'ship to', 'payment terms',
            'due date', 'line items', 'subtotal', 'tax amount'
        ]
        return any(indicator in text_content for indicator in indicators)

    def _has_bank_statement_indicators(self, data: Dict[str, Any]) -> bool:
        """Check for bank statement patterns"""
        text_content = json.dumps(data).lower()
        indicators = [
            'statement period', 'opening balance', 'closing balance',
            'deposits', 'withdrawals', 'account number', 'transaction'
        ]
        return any(indicator in text_content for indicator in indicators)

    def _has_receipt_indicators(self, data: Dict[str, Any]) -> bool:
        """Check for receipt patterns"""
        text_content = json.dumps(data).lower()
        indicators = [
            'receipt', 'merchant', 'cashback', 'change', 'thank you',
            'subtotal', 'payment method', 'card ending'
        ]
        return any(indicator in text_content for indicator in indicators)

    def _has_payslip_indicators(self, data: Dict[str, Any]) -> bool:
        """Check for payslip patterns"""
        text_content = json.dumps(data).lower()
        indicators = [
            'pay period', 'gross pay', 'net pay', 'deductions',
            'federal tax', 'social security', 'employee id', 'ytd'
        ]
        return any(indicator in text_content for indicator in indicators)

    def _has_system_report_indicators(self, data: Dict[str, Any]) -> bool:
        """Check for system report patterns"""
        text_content = json.dumps(data).lower()
        indicators = [
            'report', 'summary', 'total sales', 'settlement',
            'period', 'generated', 'transaction count'
        ]
        return any(indicator in text_content for indicator in indicators)

    def _extract_relevant_fields(self, data: Dict[str, Any], doc_type: DocumentType) -> Dict[str, Any]:
        """Extract fields relevant to the document type"""
        template = self.field_templates[doc_type]
        extracted = {}

        # Extract from structured_fields if available
        structured = data.get('structured_fields', {})

        for field in template:
            if field in structured:
                extracted[field] = structured[field]
            elif field in data:
                extracted[field] = data[field]

        return extracted

    def _generate_llama_prompt(self, doc_type: DocumentType, data: Dict[str, Any]) -> str:
        """Generate contextual prompt for Llama 3 based on document type"""

        base_prompts = {
            DocumentType.INVOICE: """
Generate journal entries for this invoice. Determine if this is a customer invoice (revenue) or vendor invoice (expense/asset).
Consider: line item descriptions, vendor/customer relationship, amounts, and business context.
Classify expenses/assets into appropriate COA categories (office supplies, travel, equipment, inventory, etc.).
Provide confidence score and reasoning for your classification.
""",

            DocumentType.BANK_STATEMENT: """
Analyze these bank transactions and generate appropriate journal entries.
Classify each transaction: customer payments, vendor payments, bank fees, interest, transfers, etc.
Match transactions to known invoices/payments where possible.
Group related transactions and provide summary entries where appropriate.
""",

            DocumentType.RECEIPT: """
Generate journal entries for this purchase receipt.
Determine expense category: office supplies, travel, meals, utilities, equipment, inventory, etc.
Consider merchant type, item descriptions, and amounts for proper COA classification.
Handle tax implications and payment method impacts.
""",

            DocumentType.PAYSLIP: """
Generate payroll journal entries for this payslip.
Create entries for: wage expense, tax liabilities, benefit expenses, employee deductions.
Handle both accrual and cash basis accounting appropriately.
Account for employer portions of taxes and benefits.
""",

            DocumentType.SYSTEM_REPORT: """
Analyze this system report and generate summary journal entries.
Consider the business context: sales revenue, fee expenses, settlements, inventory adjustments, etc.
Create entries that properly reflect the economic activity reported.
Handle period-end adjustments and reconciliations.
"""
        }

        prompt = base_prompts.get(doc_type, "Generate appropriate journal entries for this document.")

        # Add document-specific context
        if doc_type == DocumentType.SYSTEM_REPORT:
            report_type = self._infer_report_type(data)
            prompt = prompt.replace("{report_type}", report_type)

        return prompt.strip()

    def _infer_report_type(self, data: Dict[str, Any]) -> str:
        """Infer specific report type for system reports"""
        text_content = json.dumps(data).lower()

        if 'pos' in text_content or 'point of sale' in text_content:
            return "POS Sales Report"
        elif 'ecommerce' in text_content or 'settlement' in text_content:
            return "Ecommerce Settlement Report"
        elif 'inventory' in text_content:
            return "Inventory Report"
        else:
            return "Business Report"

    def _get_processing_context(self, doc_type: DocumentType) -> Dict[str, Any]:
        """Get processing context for the document type"""
        contexts = {
            DocumentType.INVOICE: {
                "requires_classification": True,
                "accounting_impact": "Revenue or Expense recognition",
                "validation_rules": ["amount_balance", "date_reasonable", "party_identified"]
            },
            DocumentType.BANK_STATEMENT: {
                "requires_classification": False,
                "accounting_impact": "Cash reconciliation",
                "validation_rules": ["balance_reconciliation", "transaction_logic"]
            },
            DocumentType.RECEIPT: {
                "requires_classification": True,
                "accounting_impact": "Expense categorization",
                "validation_rules": ["amount_calculation", "tax_logic"]
            },
            DocumentType.PAYSLIP: {
                "requires_classification": False,
                "accounting_impact": "Payroll accounting",
                "validation_rules": ["payroll_calculation", "tax_compliance"]
            },
            DocumentType.SYSTEM_REPORT: {
                "requires_classification": True,
                "accounting_impact": "Period-end adjustments",
                "validation_rules": ["summary_accuracy", "period_coverage"]
            }
        }

        return contexts.get(doc_type, {})

    def _calculate_confidence(self, data: Dict[str, Any], doc_type: DocumentType) -> float:
        """Calculate confidence score for document classification"""
        if doc_type == DocumentType.UNKNOWN:
            return 0.0

        # Simple confidence calculation based on field presence
        template = self.field_templates[doc_type]
        structured = data.get('structured_fields', {})
        found_fields = sum(1 for field in template if field in structured or field in data)

        confidence = min(found_fields / len(template), 1.0)

        # Boost confidence for strong indicators
        text_content = json.dumps(data).lower()
        if doc_type == DocumentType.INVOICE and 'invoice' in text_content:
            confidence = min(confidence + 0.2, 1.0)
        elif doc_type == DocumentType.BANK_STATEMENT and 'statement' in text_content:
            confidence = min(confidence + 0.2, 1.0)

        return round(confidence, 2)

    # Field template definitions
    def _get_invoice_fields(self):
        return [
            'invoice_number', 'invoice_date', 'due_date',
            'customer_name', 'customer_address', 'customer_tax_id',
            'vendor_name', 'vendor_address', 'vendor_tax_id',
            'line_items', 'subtotal', 'tax_amount', 'tax_rate', 'total_amount',
            'payment_terms', 'currency', 'exchange_rate',
            'shipping_amount', 'discount_amount', 'notes'
        ]

    def _get_bank_statement_fields(self):
        return [
            'bank_name', 'account_number', 'account_type',
            'statement_period_start', 'statement_period_end',
            'opening_balance', 'closing_balance',
            'transaction_list', 'deposits_total', 'withdrawals_total',
            'fees_total', 'interest_earned', 'account_currency'
        ]

    def _get_receipt_fields(self):
        return [
            'receipt_number', 'receipt_date', 'merchant_name',
            'merchant_address', 'merchant_tax_id', 'merchant_category',
            'line_items', 'subtotal', 'tax_amount', 'tip_amount', 'total_amount',
            'payment_method', 'card_last_four', 'transaction_id',
            'cashback_amount', 'loyalty_points'
        ]

    def _get_payslip_fields(self):
        return [
            'employee_name', 'employee_id', 'pay_period_start', 'pay_period_end',
            'gross_pay', 'net_pay', 'pay_frequency',
            'regular_hours', 'overtime_hours', 'regular_rate', 'overtime_rate',
            'earnings_breakdown', 'deductions',
            'federal_tax', 'state_tax', 'social_security', 'medicare',
            'health_insurance', 'retirement_contributions', 'garnishments',
            'ytd_totals'
        ]

    def _get_system_report_fields(self):
        return [
            'report_type', 'report_period', 'generated_date',
            'summary_totals', 'category_breakdowns',
            'transaction_counts', 'revenue_amounts', 'fee_amounts',
            'adjustments', 'settlements', 'reconciliations'
        ]