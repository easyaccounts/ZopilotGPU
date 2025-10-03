import os
import logging
import json
from typing import Dict, Any, Optional, List
from docstrange import DocumentExtractor
from docstrange.exceptions import ConversionError, UnsupportedFormatError, FileNotFoundError as DocstrageFileNotFoundError

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, try to load manually
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ.setdefault(key, value)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocstrageProcessor:
    def __init__(self):
        # Initialize DocumentExtractor with API key from environment for cloud processing
        # This provides 10k documents/month without requiring login authentication
        api_key = os.environ.get('NANONETS_API_KEY')
        
        try:
            if api_key and api_key != 'your_nanonets_api_key_here':
                # Use API key for authenticated cloud processing (10k docs/month)
                self.extractor = DocumentExtractor(api_key=api_key)
                logger.info(f"DocStrange initialized with API key authentication (10k docs/month)")
            else:
                logger.warning("NANONETS_API_KEY not found or not set in environment")
                # Fallback to default cloud mode (rate-limited)
                self.extractor = DocumentExtractor()
                logger.info("DocStrange initialized with default cloud processing (rate-limited)")
                
        except Exception as e:
            logger.warning(f"Cloud initialization failed, falling back to local processing: {e}")
            # Fallback to local CPU processing if cloud is unavailable
            self.extractor = DocumentExtractor(cpu=True)
            logger.info("DocStrange initialized with local CPU processing")
        
        # Define accounting-specific fields for structured extraction
        self.accounting_fields = [
            "invoice_number", "receipt_number", "transaction_id",
            "total_amount", "subtotal", "tax_amount", "discount",
            "vendor_name", "supplier", "merchant_name", "company_name",
            "date", "invoice_date", "transaction_date", "due_date",
            "description", "memo", "purpose", "category",
            "account_number", "reference", "payment_method",
            "line_items", "items", "products", "services",
            "customer_name", "bill_to", "ship_to",
            "currency", "exchange_rate"
        ]
        
        # Company name patterns for invoice direction detection
        self.company_identifiers = [
            "your company", "your business", "your corp", "your inc",
            "easyaccounts", "easy accounts"  # Add your actual company name here
        ]
        
    def extract_with_docstrange(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extracts structured JSON data from document content using DocStrange official API.
        Uses structured field extraction optimized for accounting documents.
        """
        try:
            logger.info(f"Processing document: {filename} ({len(file_content)} bytes)")
            
            # Create temporary file for DocStrange processing
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=self._get_file_extension(filename), delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file.flush()
                temp_path = temp_file.name
            
            try:
                # Extract document using DocStrange
                result = self.extractor.extract(temp_path)
                
                # Use structured field extraction for accounting documents
                structured_data = result.extract_data(specified_fields=self.accounting_fields)
                
                # Also get general document data
                general_data = result.extract_data()
                
                # Get clean markdown for text analysis
                markdown_content = result.extract_markdown()
                
                # Combine structured and general extraction
                combined_data = {
                    'structured_fields': structured_data.get('extracted_fields', {}),
                    'general_data': general_data,
                    'markdown_content': markdown_content[:2000],  # Limit for performance
                    'metadata': {
                        'processing_mode': self.extractor.get_processing_mode(),
                        'cloud_enabled': self.extractor.is_cloud_enabled(),
                        'content_length': len(markdown_content)
                    }
                }
                
                # Add invoice direction detection
                invoice_direction = self._detect_invoice_direction(combined_data['structured_fields'])
                combined_data['invoice_classification'] = invoice_direction
                
                if self._validate_extraction(combined_data):
                    logger.info(f"Successfully extracted data using DocStrange ({self.extractor.get_processing_mode()} mode)")
                    return self._normalize_extraction(combined_data, 'docstrange_official')
                else:
                    logger.warning("Extraction validation failed, low confidence result")
                    return self._normalize_extraction(combined_data, 'docstrange_low_confidence')
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except DocstrageFileNotFoundError as e:
            logger.error(f"File not found: {filename}")
            return self._error_fallback(filename, f"File not found: {str(e)}")
        except UnsupportedFormatError as e:
            logger.error(f"Unsupported file format: {filename}")
            return self._error_fallback(filename, f"Unsupported format: {str(e)}")
        except ConversionError as e:
            logger.error(f"DocStrange conversion failed for {filename}: {str(e)}")
            return self._error_fallback(filename, f"Conversion error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing {filename}: {str(e)}")
            return self._error_fallback(filename, f"Unexpected error: {str(e)}")
    
    def _validate_extraction(self, data: Dict[str, Any]) -> bool:
        """Validate that extraction contains meaningful data for accounting."""
        if not data:
            return False
        
        # Check for structured fields extraction
        structured_fields = data.get('structured_fields', {})
        if structured_fields and any(v for v in structured_fields.values() if v):
            logger.info(f"Found {len([v for v in structured_fields.values() if v])} structured fields")
            return True
        
        # Check general data
        general_data = data.get('general_data', {})
        if isinstance(general_data, dict) and general_data.get('content'):
            return True
        
        # Check markdown content
        markdown = data.get('markdown_content', '')
        if markdown and len(markdown.strip()) > 50:  # At least some meaningful content
            return True
        
        return False
    
    def _error_fallback(self, filename: str, error_msg: str) -> Dict[str, Any]:
        """Return error structure when extraction fails."""
        return {
            'extraction_method': 'error',
            'success': False,
            'data': {
                'error': error_msg,
                'file_name': filename,
                'processing_mode': getattr(self.extractor, 'get_processing_mode', lambda: 'unknown')()
            },
            'metadata': {
                'processed_at': self._get_timestamp(),
                'requires_manual_review': True,
                'confidence': 0.0,
                'error_type': 'extraction_failure'
            }
        }
    
    def _normalize_extraction(self, data: Dict[str, Any], method: str) -> Dict[str, Any]:
        """Normalize extracted data to consistent format."""
        # Calculate confidence based on structured fields found
        structured_fields = data.get('structured_fields', {})
        non_empty_fields = {k: v for k, v in structured_fields.items() if v}
        confidence = min(0.95, len(non_empty_fields) * 0.1 + 0.3)  # Base confidence + field bonus
        
        normalized = {
            'extraction_method': method,
            'success': True,
            'data': data,
            'metadata': {
                'processed_at': self._get_timestamp(),
                'structured_fields_found': len(non_empty_fields),
                'total_fields_searched': len(self.accounting_fields),
                'confidence': confidence,
                'processing_mode': data.get('metadata', {}).get('processing_mode', 'unknown')
            }
        }
        return normalized
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension for temporary file creation."""
        return os.path.splitext(filename)[1].lower() or '.tmp'
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _detect_invoice_direction(self, structured_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect if invoice is incoming (vendor bill) or outgoing (customer invoice).
        
        Returns:
            Dict with invoice direction classification and confidence
        """
        try:
            # Get key fields for analysis
            bill_to = str(structured_fields.get('bill_to', '')).lower()
            customer_name = str(structured_fields.get('customer_name', '')).lower() 
            vendor_name = str(structured_fields.get('vendor_name', '')).lower()
            supplier = str(structured_fields.get('supplier', '')).lower()
            
            # Check if bill_to or customer contains your company identifiers
            is_incoming = any(identifier in bill_to or identifier in customer_name 
                            for identifier in self.company_identifiers)
            
            # Check if vendor/supplier contains your company identifiers
            is_outgoing = any(identifier in vendor_name or identifier in supplier
                            for identifier in self.company_identifiers)
            
            # Determine direction with confidence
            if is_incoming and not is_outgoing:
                direction = "incoming"  # Vendor bill (you owe money)
                confidence = 0.9
                description = "Vendor Invoice - You receive this from a supplier/vendor"
                accounting_impact = "Accounts Payable (credit), Expense/Asset (debit)"
            elif is_outgoing and not is_incoming:
                direction = "outgoing"  # Customer invoice (they owe you)
                confidence = 0.9
                description = "Customer Invoice - You send this to a customer" 
                accounting_impact = "Accounts Receivable (debit), Revenue (credit)"
            elif is_incoming and is_outgoing:
                # Ambiguous case - both directions detected
                direction = "ambiguous"
                confidence = 0.3
                description = "Ambiguous - Cannot clearly determine direction"
                accounting_impact = "Manual review required"
            else:
                # No clear direction detected
                direction = "unknown"
                confidence = 0.1
                description = "Unknown - No company identifiers found"
                accounting_impact = "Manual classification needed"
            
            return {
                'direction': direction,
                'confidence': confidence,
                'description': description,
                'accounting_impact': accounting_impact,
                'analysis': {
                    'bill_to_matches_company': is_incoming,
                    'vendor_matches_company': is_outgoing,
                    'bill_to_text': bill_to[:100],  # First 100 chars for debugging
                    'vendor_text': (vendor_name or supplier)[:50]  # First 50 chars
                }
            }
            
        except Exception as e:
            logger.warning(f"Invoice direction detection failed: {str(e)}")
            return {
                'direction': 'error',
                'confidence': 0.0,
                'description': f"Detection failed: {str(e)}",
                'accounting_impact': 'Manual review required',
                'analysis': {'error': str(e)}
            }

# Global instance
_docstrange_processor = None

def get_docstrange_processor() -> DocstrageProcessor:
    """Get or create global docstrange processor instance."""
    global _docstrange_processor
    if _docstrange_processor is None:
        _docstrange_processor = DocstrageProcessor()
    return _docstrange_processor

def extract_with_docstrange(file_content: bytes, filename: str) -> Dict[str, Any]:
    """Extract data from document content using docstrange with cloud API fallback."""
    processor = get_docstrange_processor()
    return processor.extract_with_docstrange(file_content, filename)