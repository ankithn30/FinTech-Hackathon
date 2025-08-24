"""
PyMuPDF Temporary Filler
=======================

Main form filling engine using PyMuPDF with strictly temporary storage.
Handles batch processing of multiple forms with semantic field mapping.
"""

import os
import tempfile
from typing import Dict, List, Optional, Any, Tuple
import logging
import fitz  # PyMuPDF
from pathlib import Path

from .semantic_mapper import TemporarySemanticMapper
from .temp_storage import TempStorageManager, TemporaryFileHandler

logger = logging.getLogger(__name__)


class PyMuPDFTemporaryFiller:
    """
    Main PDF form filling engine with temporary storage only.
    Processes multiple forms with semantic field mapping and guaranteed cleanup.
    """
    
    def __init__(self):
        self.mapper = TemporarySemanticMapper()
        self.storage_manager: Optional[TempStorageManager] = None
        self._processing_stats = {
            'forms_processed': 0,
            'fields_filled': 0,
            'mapping_errors': 0,
            'fill_errors': 0
        }
    
    def __enter__(self):
        """Context manager entry - initialize storage"""
        self.storage_manager = TempStorageManager()
        self.storage_manager.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - guaranteed cleanup"""
        self.cleanup_all()
        if exc_type:
            logger.error(f"Exception in PyMuPDFTemporaryFiller: {exc_type.__name__}: {exc_val}")
    
    def fill_single_form(self, extracted_data: Dict[str, Any], form_path: str, 
                        output_filename: Optional[str] = None) -> Optional[str]:
        """
        Fill a single PDF form with extracted data using semantic mapping.
        
        Args:
            extracted_data: Dictionary of data to fill (e.g., {"Phone": "313-478-9080"})
            form_path: Path to the source PDF form
            output_filename: Optional custom output filename
            
        Returns:
            Path to filled PDF file in temp directory, or None on error
        """
        if not self.storage_manager:
            raise RuntimeError("PyMuPDFTemporaryFiller not initialized. Use as context manager.")
        
        if not os.path.exists(form_path):
            logger.error(f"Form file not found: {form_path}")
            self._processing_stats['fill_errors'] += 1
            return None
        
        if not extracted_data:
            logger.warning(f"No data provided for form: {form_path}")
            self._processing_stats['fill_errors'] += 1
            return None
        
        try:
            # Generate output filename
            if not output_filename:
                base_name = Path(form_path).stem
                output_filename = f"filled_{base_name}_{self._processing_stats['forms_processed']}.pdf"
            
            # Get temporary output path
            output_path = self.storage_manager.get_temp_path(output_filename)
            
            # Map extracted data to actual form field names
            logger.info(f"Mapping data for form: {os.path.basename(form_path)}")
            mapped_data = self.mapper.map_data_to_fields(extracted_data, form_path)
            
            if not mapped_data:
                logger.warning(f"No fields could be mapped for form: {form_path}")
                self._processing_stats['mapping_errors'] += 1
                return None
            
            # Fill the PDF form
            success = self._fill_pdf_with_pymupdf(form_path, mapped_data, output_path)
            
            if success:
                self._processing_stats['forms_processed'] += 1
                self._processing_stats['fields_filled'] += len(mapped_data)
                logger.info(f"Successfully filled form: {output_filename}")
                return output_path
            else:
                self._processing_stats['fill_errors'] += 1
                return None
                
        except Exception as e:
            logger.error(f"Error filling form {form_path}: {e}")
            self._processing_stats['fill_errors'] += 1
            return None
    
    def _fill_pdf_with_pymupdf(self, form_path: str, mapped_data: Dict[str, str], 
                              output_path: str) -> bool:
        """
        Fill PDF form using PyMuPDF with mapped field data.
        
        Args:
            form_path: Source PDF path
            mapped_data: Dictionary of {field_name: value} mappings
            output_path: Output PDF path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Open the source PDF
            doc = fitz.open(form_path)
            
            filled_fields = 0
            total_attempts = len(mapped_data)
            
            # Iterate through all pages
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get form widgets on this page
                widgets = page.widgets()
                
                for widget in widgets:
                    field_name = widget.field_name
                    
                    if field_name and field_name in mapped_data:
                        try:
                            # Get the value to fill
                            fill_value = mapped_data[field_name]
                            
                            # Update the widget value
                            widget.field_value = fill_value
                            widget.update()
                            
                            filled_fields += 1
                            logger.debug(f"Filled field '{field_name}' with '{fill_value}'")
                            
                        except Exception as e:
                            logger.warning(f"Error filling field '{field_name}': {e}")
            
            # Save the filled PDF
            doc.save(output_path, garbage=4, deflate=True)
            doc.close()
            
            logger.info(f"Filled {filled_fields}/{total_attempts} fields in {os.path.basename(form_path)}")
            return filled_fields > 0
            
        except Exception as e:
            logger.error(f"PyMuPDF error filling {form_path}: {e}")
            return False
    
    def fill_forms_batch(self, extracted_data: Dict[str, Any], form_paths: List[str]) -> List[str]:
        """
        Process multiple forms with the same extracted data.
        
        Args:
            extracted_data: Data to fill in all forms
            form_paths: List of PDF form paths to process
            
        Returns:
            List of paths to successfully filled PDF files
        """
        if not self.storage_manager:
            raise RuntimeError("PyMuPDFTemporaryFiller not initialized. Use as context manager.")
        
        if not extracted_data:
            logger.error("No extracted data provided for batch processing")
            return []
        
        if not form_paths:
            logger.error("No form paths provided for batch processing")
            return []
        
        logger.info(f"Starting batch processing of {len(form_paths)} forms")
        logger.info(f"Data keys to fill: {list(extracted_data.keys())}")
        
        filled_forms = []
        
        for i, form_path in enumerate(form_paths):
            logger.info(f"Processing form {i+1}/{len(form_paths)}: {os.path.basename(form_path)}")
            
            # Fill individual form
            filled_path = self.fill_single_form(extracted_data, form_path)
            
            if filled_path:
                filled_forms.append(filled_path)
                logger.info(f"✓ Successfully processed: {os.path.basename(filled_path)}")
            else:
                logger.warning(f"✗ Failed to process: {os.path.basename(form_path)}")
        
        # Log batch results
        success_rate = (len(filled_forms) / len(form_paths)) * 100 if form_paths else 0
        logger.info(f"Batch processing complete: {len(filled_forms)}/{len(form_paths)} forms filled ({success_rate:.1f}%)")
        
        return filled_forms
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        stats = self._processing_stats.copy()
        
        # Add mapper stats
        if self.mapper:
            mapper_stats = self.mapper.get_session_stats()
            stats.update({
                'mapper_forms_processed': mapper_stats['forms_processed'],
                'cached_mappings': mapper_stats['cached_mappings'],
                'total_fields_discovered': mapper_stats['total_fields_discovered']
            })
        
        # Add storage stats
        if self.storage_manager:
            storage_stats = self.storage_manager.get_memory_usage_info()
            stats.update({
                'temp_files_tracked': storage_stats['temp_files_tracked'],
                'temp_dir_active': storage_stats['temp_dir_active']
            })
        
        return stats
    
    def get_field_mapping_preview(self, extracted_data: Dict[str, Any], 
                                 form_path: str) -> Dict[str, Any]:
        """
        Preview how extracted data would be mapped to form fields without filling.
        
        Args:
            extracted_data: Data to preview mapping for
            form_path: PDF form to analyze
            
        Returns:
            Dictionary with mapping preview information
        """
        if not os.path.exists(form_path):
            return {"error": f"Form file not found: {form_path}"}
        
        try:
            # Discover form fields
            form_fields = self.mapper.discover_fields_memory(form_path)
            
            if not form_fields:
                return {"error": f"No form fields found in {form_path}"}
            
            # Get mapping preview
            mapped_data = self.mapper.map_data_to_fields(extracted_data, form_path)
            
            # Get suggestions for unmapped keys
            unmapped_suggestions = {}
            for key in extracted_data.keys():
                if key not in [k for k, v in mapped_data.items()]:
                    suggestions = self.mapper.get_field_suggestions(key, form_path, limit=3)
                    unmapped_suggestions[key] = suggestions
            
            return {
                "form_path": form_path,
                "total_form_fields": len(form_fields),
                "available_fields": list(form_fields.keys()),
                "extracted_data_keys": list(extracted_data.keys()),
                "successful_mappings": mapped_data,
                "unmapped_keys": list(unmapped_suggestions.keys()),
                "mapping_suggestions": unmapped_suggestions,
                "mapping_success_rate": (len(mapped_data) / len(extracted_data)) * 100 if extracted_data else 0
            }
            
        except Exception as e:
            return {"error": f"Error previewing mapping: {e}"}
    
    def cleanup_all(self) -> None:
        """Force cleanup all temporary storage and memory"""
        try:
            # Clear mapper cache
            if self.mapper:
                self.mapper.clear_session_cache()
            
            # Cleanup storage manager
            if self.storage_manager:
                self.storage_manager.cleanup_all()
                self.storage_manager = None
            
            # Reset stats
            self._processing_stats = {
                'forms_processed': 0,
                'fields_filled': 0,
                'mapping_errors': 0,
                'fill_errors': 0
            }
            
            logger.debug("PyMuPDFTemporaryFiller cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def fill_forms_with_temporary_storage(extracted_data: Dict[str, Any], 
                                    form_paths: List[str]) -> List[str]:
    """
    Convenience function to fill forms with automatic cleanup.
    
    Args:
        extracted_data: Data to fill in forms
        form_paths: List of PDF form paths
        
    Returns:
        List of paths to filled PDF files (in temporary directory)
    """
    with PyMuPDFTemporaryFiller() as filler:
        return filler.fill_forms_batch(extracted_data, form_paths)


def preview_field_mappings(extracted_data: Dict[str, Any], 
                          form_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Preview how data would be mapped to fields in multiple forms.
    
    Args:
        extracted_data: Data to preview
        form_paths: List of PDF form paths
        
    Returns:
        List of mapping preview dictionaries
    """
    previews = []
    
    with PyMuPDFTemporaryFiller() as filler:
        for form_path in form_paths:
            preview = filler.get_field_mapping_preview(extracted_data, form_path)
            previews.append(preview)
    
    return previews
