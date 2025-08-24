"""
Temporary Semantic PDF Form Filler
==================================

A complete semantic PDF form filling system using PyMuPDF with STRICTLY temporary storage only.
This is designed for desktop applications where all data must be ephemeral.

Key Features:
- NO SQLite, NO persistent database
- NO files left after process completion  
- Memory-based only (Python dicts + temp files)
- Auto-cleanup on completion/error
- Session-isolated (fresh start every time)
- Semantic field matching to prevent mapping errors

Core Classes:
- TemporarySemanticMapper: Handles semantic field mapping
- PyMuPDFTemporaryFiller: Main form filling engine
- TempStorageManager: Memory and temporary file management
"""

from .semantic_mapper import TemporarySemanticMapper
from .pymupdf_filler import PyMuPDFTemporaryFiller, fill_forms_with_temporary_storage, preview_field_mappings
from .temp_storage import TempStorageManager

__version__ = "1.0.0"
__all__ = ["TemporarySemanticMapper", "PyMuPDFTemporaryFiller", "TempStorageManager", "fill_forms_with_temporary_storage", "preview_field_mappings"]
