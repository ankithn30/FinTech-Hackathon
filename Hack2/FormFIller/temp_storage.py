"""
Temporary Storage Manager
========================

Handles all temporary storage operations with guaranteed cleanup.
Ensures zero persistence after process completion.
"""

import tempfile
import os
import shutil
import weakref
import gc
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TempStorageManager:
    """
    Manages temporary storage with guaranteed cleanup.
    Uses context managers and weak references to prevent memory leaks.
    """
    
    def __init__(self):
        self.temp_dir: Optional[tempfile.TemporaryDirectory] = None
        self.session_data: Dict[str, Any] = {}
        self.temp_files: List[str] = []
        self._cleanup_registered = False
        
    def __enter__(self):
        """Context manager entry - create temp directory"""
        self.temp_dir = tempfile.TemporaryDirectory(prefix="pdf_filler_")
        logger.debug(f"Created temporary directory: {self.temp_dir.name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - guaranteed cleanup"""
        self.cleanup_all()
        if exc_type:
            logger.error(f"Exception during temp storage: {exc_type.__name__}: {exc_val}")
        
    def get_temp_path(self, filename: str) -> str:
        """Get a temporary file path within the temp directory"""
        if not self.temp_dir:
            raise RuntimeError("TempStorageManager not initialized. Use as context manager.")
        
        temp_path = os.path.join(self.temp_dir.name, filename)
        self.temp_files.append(temp_path)
        return temp_path
    
    def store_session_data(self, key: str, data: Any) -> None:
        """Store data in memory for the session"""
        self.session_data[key] = data
        logger.debug(f"Stored session data for key: {key}")
    
    def get_session_data(self, key: str, default: Any = None) -> Any:
        """Retrieve session data from memory"""
        return self.session_data.get(key, default)
    
    def clear_session_data(self) -> None:
        """Clear all session data from memory"""
        keys_count = len(self.session_data)
        self.session_data.clear()
        logger.debug(f"Cleared {keys_count} session data entries")
    
    def cleanup_all(self) -> None:
        """Force cleanup all temporary storage and memory"""
        try:
            # Clear session data
            self.clear_session_data()
            
            # Clear temp files list
            self.temp_files.clear()
            
            # Cleanup temp directory
            if self.temp_dir:
                try:
                    self.temp_dir.cleanup()
                    logger.debug("Temporary directory cleaned up")
                except Exception as e:
                    logger.warning(f"Error cleaning temp directory: {e}")
                finally:
                    self.temp_dir = None
            
            # Force garbage collection
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_memory_usage_info(self) -> Dict[str, int]:
        """Get current memory usage information"""
        return {
            "session_data_keys": len(self.session_data),
            "temp_files_tracked": len(self.temp_files),
            "temp_dir_active": self.temp_dir is not None
        }


class TemporaryFileHandler:
    """
    Context manager for individual temporary files with automatic cleanup
    """
    
    def __init__(self, storage_manager: TempStorageManager, filename: str):
        self.storage_manager = storage_manager
        self.filename = filename
        self.file_path: Optional[str] = None
    
    def __enter__(self) -> str:
        """Create temporary file and return path"""
        self.file_path = self.storage_manager.get_temp_path(self.filename)
        return self.file_path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup temporary file"""
        if self.file_path and os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                logger.debug(f"Removed temporary file: {self.file_path}")
            except Exception as e:
                logger.warning(f"Could not remove temp file {self.file_path}: {e}")


def create_temp_storage() -> TempStorageManager:
    """Factory function to create a new TempStorageManager"""
    return TempStorageManager()


def ensure_cleanup(storage_manager: TempStorageManager) -> None:
    """Ensure cleanup is called on storage manager"""
    if storage_manager:
        storage_manager.cleanup_all()
