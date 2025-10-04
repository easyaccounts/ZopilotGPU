import os
import logging
import json
from typing import Dict, Any, Optional, List
from docstrange import DocumentExtractor
from docstrange.exceptions import ConversionError, UnsupportedFormatError, FileNotFoundError as DocstrageFileNotFoundError

# Custom exception for GPU extraction failures
class GPUExtractionFailedError(Exception):
    """
    Raised when GPU local extraction fails and backend should route to cloud API.
    This is different from returning error structures - it signals backend to use cloud fallback.
    """
    pass

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
        # Initialize DocumentExtractor with LOCAL extraction only (no cloud API calls)
        # GPU service should NEVER call cloud APIs - that's the backend's job
        # Force cpu=True to ensure local extraction, and explicitly disable cloud
        try:
            # CRITICAL: Force local extraction only (per official API documentation)
            # cpu=True automatically disables cloud mode (self.cloud_mode = not self.cpu)
            # No api_key ensures cloud cannot be used even if enabled
            self.extractor = DocumentExtractor(
                cpu=True,          # Force local CPU/GPU extraction (disables cloud automatically)
                preserve_layout=True,    # Preserve document structure
                include_images=False,    # Skip images to save bandwidth
                ocr_enabled=True         # Enable OCR for scanned documents
            )
            processing_mode = self.extractor.get_processing_mode()
            logger.info(f"DocStrange initialized: mode={processing_mode}, cloud_mode={self.extractor.cloud_mode}")
            logger.info("CRITICAL: GPU will use LOCAL neural models ONLY, NO cloud API calls")
            
            # Verify cloud is actually disabled
            if self.extractor.cloud_mode:
                raise RuntimeError("Cloud mode is enabled! GPU service must use local extraction only.")
                
        except Exception as e:
            logger.error(f"Failed to initialize DocStrange: {e}")
            logger.error("This usually indicates missing dependencies (torchvision, transformers)")
            logger.error("Check that torchvision is installed and compatible with torch version")
            raise
        
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
                # Extract document using DocStrange (official API)
                result = self.extractor.extract(temp_path)
                
                # extract_data() returns: {"document": {...fields...}, "format": "json"}
                # Per official API: https://github.com/NanoNets/docstrange
                extraction_result = result.extract_data()
                
                # Extract the actual document fields (official format)
                document_fields = extraction_result.get('document', {})
                
                # Get clean markdown for text analysis
                markdown_content = result.extract_markdown()
                
                # Prepare data for normalization
                combined_data = {
                    'document_fields': document_fields,
                    'markdown_content': markdown_content[:2000],  # Limit for performance
                    'metadata': {
                        'processing_mode': self.extractor.get_processing_mode(),
                        'cloud_enabled': False,  # Always false - cloud disabled
                        'content_length': len(markdown_content),
                        'extraction_format': extraction_result.get('format', 'json')
                    }
                }
                
                # Return normalized JSON extraction without classification
                if self._validate_extraction(combined_data):
                    logger.info(f"Successfully extracted data using DocStrange (local mode)")
                    return self._normalize_extraction(combined_data, 'docstrange_local')
                else:
                    logger.warning("Extraction validation failed, low confidence result")
                    return self._normalize_extraction(combined_data, 'docstrange_local_low_confidence')
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except DocstrageFileNotFoundError as e:
            logger.error(f"File not found: {filename}")
            raise GPUExtractionFailedError(f"File not found: {str(e)}")
        except UnsupportedFormatError as e:
            logger.error(f"Unsupported file format: {filename}")
            raise GPUExtractionFailedError(f"Unsupported format: {str(e)}")
        except ConversionError as e:
            logger.error(f"DocStrange conversion failed for {filename}: {str(e)}")
            raise GPUExtractionFailedError(f"Conversion error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing {filename}: {str(e)}")
            raise GPUExtractionFailedError(f"Unexpected error: {str(e)}")
    
    def _validate_extraction(self, data: Dict[str, Any]) -> bool:
        """Validate that extraction contains meaningful data for accounting."""
        if not data:
            return False
        
        # Check for document fields (official API format)
        document_fields = data.get('document_fields', {})
        if document_fields and isinstance(document_fields, dict):
            # Count non-empty fields
            filled_fields = [k for k, v in document_fields.items() if v]
            if filled_fields:
                logger.info(f"Found {len(filled_fields)} document fields")
                return True
        
        # Check markdown content as fallback
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
        """
        Normalize extraction data to FLAT JSON format matching backend's Docstrange cloud format.
        
        Backend expects ALL fields at root level (not nested), with _metadata as special key.
        This matches docstrangeExtractor.ts normalizeResponse() format.
        
        Official API returns: {"document": {fields...}, "format": "json"}
        We flatten the 'document' object to root level.
        """
        # Get document fields from official API format
        document_fields = data.get('document_fields', {})
        
        # Calculate confidence based on field count (same as backend)
        field_count = len(document_fields) if isinstance(document_fields, dict) else 0
        # 0-5 fields: 0.3-0.5, 5-10: 0.5-0.7, 10-20: 0.7-0.9, 20+: 0.9-0.95
        confidence = min(0.95, 0.3 + (field_count * 0.03))
        
        # Return FLAT JSON - all fields at root level (matches backend format)
        return {
            'success': True,
            'extraction_method': method,
            # Spread all document fields at root level (FLAT, not nested)
            **document_fields,
            # Add metadata with underscore prefix to avoid field conflicts
            '_metadata': {
                'processed_at': self._get_timestamp(),
                'fields_extracted': field_count,
                'confidence': confidence,
                'processing_mode': data.get('metadata', {}).get('processing_mode', 'local'),
                'cloud_enabled': False,
                'content_length': data.get('metadata', {}).get('content_length', 0),
                'extraction_format': data.get('metadata', {}).get('extraction_format', 'json'),
                'markdown_preview': data.get('markdown_content', '')[:500]
            }
        }
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension for temporary file creation."""
        return os.path.splitext(filename)[1].lower() or '.tmp'
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

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