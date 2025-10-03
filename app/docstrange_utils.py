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
        # Initialize DocumentExtractor with GPU acceleration for faster processing
        # Cloud extraction is handled by backend, GPU only does local fallback processing
        # Setting cpu=False allows Docstrange to use GPU if available (RunPod has GPU)
        try:
            self.extractor = DocumentExtractor(cpu=False)
            processing_mode = self.extractor.get_processing_mode()
            logger.info(f"DocStrange initialized with {processing_mode} processing mode")
        except Exception as e:
            logger.error(f"Failed to initialize DocStrange: {e}")
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
                # Extract document using DocStrange
                result = self.extractor.extract(temp_path)
                
                # Extract ALL available fields (no filtering)
                structured_data = result.extract_data()  # Get all fields
                
                # Also get general document data
                general_data = result.extract_data()
                
                # Get clean markdown for text analysis
                markdown_content = result.extract_markdown()
                
                # Combine structured and general extraction - pure data output
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
                
                # Return normalized JSON extraction without classification
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
        """Normalize extracted data to FLAT JSON format."""
        # Calculate confidence based on ALL fields found (no predefined list)
        structured_fields = data.get('structured_fields', {})
        non_empty_fields = {k: v for k, v in structured_fields.items() if v}
        field_count = len(non_empty_fields)
        
        # Dynamic confidence based on number of fields extracted
        # 0-5 fields: 0.3-0.45, 5-10 fields: 0.45-0.6, 10-20 fields: 0.6-0.9, 20+ fields: 0.9-0.95
        confidence = min(0.95, 0.3 + (field_count * 0.03))
        
        # Return FLAT JSON - all fields at root level
        normalized = {
            'extraction_method': method,
            'success': True,
            # Spread all extracted fields at root level
            **non_empty_fields,
            # Add metadata under special key to avoid conflicts
            '_metadata': {
                'processed_at': self._get_timestamp(),
                'structured_fields_found': field_count,
                'total_fields_searched': field_count,
                'confidence': confidence,
                'processing_mode': data.get('metadata', {}).get('processing_mode', 'unknown'),
                'cloud_enabled': data.get('metadata', {}).get('cloud_enabled', False),
                'content_length': data.get('metadata', {}).get('content_length', 0),
                'raw_response': data.get('general_data'),
                'markdown_content': data.get('markdown_content', '')
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