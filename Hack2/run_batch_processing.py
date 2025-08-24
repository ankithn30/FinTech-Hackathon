#!/usr/bin/env python3
"""
Simple script to run batch processing with default settings
"""

import os
import sys
from batch_processor import BatchProcessor

def main():
    """
    Run batch processing with default folder structure
    """
    print("🚀 FinTech Batch Processing System")
    print("=" * 50)
    
    # Default folder paths
    documents_folder = "Documents"
    forms_folder = "Forms"
    output_folder = "BatchOutput"
    
    # Check if folders exist
    if not os.path.exists(documents_folder):
        print(f"❌ Documents folder not found: {documents_folder}")
        print(f"Please create the folder and add your PDF documents")
        return 1
    
    if not os.path.exists(forms_folder):
        print(f"❌ Forms folder not found: {forms_folder}")
        print(f"Please create the folder and add your PDF forms")
        return 1
    
    # Create and run batch processor
    processor = BatchProcessor(
        documents_folder=documents_folder,
        forms_folder=forms_folder,
        output_folder=output_folder
    )
    
    try:
        result = processor.run_batch_processing()
        
        if result and result['status'] == 'success':
            print(f"\n🎉 Batch processing completed successfully!")
            print(f"📁 Check the '{output_folder}' folder for results")
            return 0
        else:
            print(f"\n❌ Batch processing failed!")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n⚠️ Processing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
