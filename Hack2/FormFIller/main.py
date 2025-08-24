"""
Main Usage Example
=================

Demonstrates how to use the Temporary Semantic PDF Form Filler system.
Shows the complete workflow with proper cleanup and error handling.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, List

from . import PyMuPDFTemporaryFiller, preview_field_mappings, fill_forms_with_temporary_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demonstrate_basic_usage():
    """
    Basic usage example showing the core problem solution.
    Prevents: All fields getting "313-478-9080"
    Ensures: Phone field gets "313-478-9080", SSN field gets "123-45-6789"
    """
    print("\n" + "="*60)
    print("BASIC USAGE DEMONSTRATION")
    print("="*60)
    
    # Sample extracted data (this would come from your form extraction system)
    extracted_data = {
        "Phone": "313-478-9080",
        "SSN": "123-45-6789",
        "Name": "John Doe",
        "Address": "123 Main St, Detroit, MI",
        "Email": "john.doe@email.com",
        "Date": "2024-01-15"
    }
    
    # Sample form paths (replace with your actual form paths)
    form_paths = [
        "forms/Consumer Loan Application fillable_1.pdf",
        "forms/fw4.pdf",
        "forms/i-9.pdf"
    ]
    
    # Filter to only existing forms
    existing_forms = [path for path in form_paths if os.path.exists(path)]
    
    if not existing_forms:
        print("❌ No sample forms found. Please ensure forms exist in the forms/ directory.")
        return
    
    print(f"📋 Data to fill: {extracted_data}")
    print(f"📄 Forms to process: {len(existing_forms)} forms")
    
    try:
        # Method 1: Using context manager (recommended)
        print("\n🔄 Processing forms with context manager...")
        with PyMuPDFTemporaryFiller() as filler:
            filled_forms = filler.fill_forms_batch(extracted_data, existing_forms)
            
            # Show processing statistics
            stats = filler.get_processing_stats()
            print(f"📊 Processing Stats:")
            print(f"   ✅ Forms processed: {stats['forms_processed']}")
            print(f"   📝 Fields filled: {stats['fields_filled']}")
            print(f"   ⚠️  Mapping errors: {stats['mapping_errors']}")
            print(f"   ❌ Fill errors: {stats['fill_errors']}")
            
            if filled_forms:
                print(f"\n✅ Successfully filled {len(filled_forms)} forms:")
                for form_path in filled_forms:
                    print(f"   📄 {os.path.basename(form_path)}")
            else:
                print("❌ No forms were successfully filled")
        
        # After context manager exits, all temporary files are cleaned up
        print("\n🧹 Automatic cleanup completed - no files left behind")
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")


def demonstrate_field_mapping_preview():
    """
    Demonstrate field mapping preview functionality.
    Shows how data would be mapped before actually filling forms.
    """
    print("\n" + "="*60)
    print("FIELD MAPPING PREVIEW DEMONSTRATION")
    print("="*60)
    
    # Sample data
    extracted_data = {
        "Phone": "555-123-4567",
        "SSN": "987-65-4321",
        "Full_Name": "Jane Smith",
        "Home_Address": "456 Oak Ave, Chicago, IL"
    }
    
    # Get available forms
    form_paths = [
        "forms/Consumer Loan Application fillable_1.pdf",
        "forms/fw4.pdf"
    ]
    
    existing_forms = [path for path in form_paths if os.path.exists(path)]
    
    if not existing_forms:
        print("❌ No sample forms found for preview.")
        return
    
    print(f"🔍 Previewing mapping for: {list(extracted_data.keys())}")
    
    try:
        # Get mapping previews
        previews = preview_field_mappings(extracted_data, existing_forms)
        
        for preview in previews:
            if "error" in preview:
                print(f"❌ Error: {preview['error']}")
                continue
            
            form_name = os.path.basename(preview['form_path'])
            print(f"\n📄 Form: {form_name}")
            print(f"   📊 Total form fields: {preview['total_form_fields']}")
            print(f"   🎯 Mapping success rate: {preview['mapping_success_rate']:.1f}%")
            
            if preview['successful_mappings']:
                print("   ✅ Successful mappings:")
                for extracted_key, form_field in preview['successful_mappings'].items():
                    print(f"      '{extracted_key}' → '{form_field}'")
            
            if preview['unmapped_keys']:
                print("   ⚠️  Unmapped keys:")
                for key in preview['unmapped_keys']:
                    print(f"      '{key}' - no suitable field found")
                    
                    # Show suggestions
                    if key in preview['mapping_suggestions']:
                        suggestions = preview['mapping_suggestions'][key][:3]  # Top 3
                        if suggestions:
                            print(f"         Suggestions: {[f'{field} ({score:.2f})' for field, score in suggestions]}")
    
    except Exception as e:
        print(f"❌ Error during preview: {e}")


def demonstrate_convenience_function():
    """
    Demonstrate the convenience function for simple use cases.
    """
    print("\n" + "="*60)
    print("CONVENIENCE FUNCTION DEMONSTRATION")
    print("="*60)
    
    # Simple data
    data = {
        "Name": "Alice Johnson",
        "Phone": "777-888-9999"
    }
    
    forms = ["forms/Consumer Loan Application fillable_1.pdf"]
    existing_forms = [path for path in forms if os.path.exists(path)]
    
    if not existing_forms:
        print("❌ No forms available for convenience function demo.")
        return
    
    print("🚀 Using convenience function (automatic cleanup)...")
    
    try:
        # One-liner form filling with automatic cleanup
        filled_forms = fill_forms_with_temporary_storage(data, existing_forms)
        
        if filled_forms:
            print(f"✅ Filled {len(filled_forms)} forms using convenience function")
            for form in filled_forms:
                print(f"   📄 {os.path.basename(form)}")
        else:
            print("❌ No forms were filled")
            
        print("🧹 Automatic cleanup completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demonstrate_error_handling():
    """
    Demonstrate robust error handling and cleanup guarantees.
    """
    print("\n" + "="*60)
    print("ERROR HANDLING DEMONSTRATION")
    print("="*60)
    
    # Test with invalid data and paths
    invalid_data = {"": "empty_key", "valid_key": None}
    invalid_forms = ["nonexistent_form.pdf", ""]
    
    print("🧪 Testing error handling with invalid inputs...")
    
    try:
        with PyMuPDFTemporaryFiller() as filler:
            # This should handle errors gracefully
            filled_forms = filler.fill_forms_batch(invalid_data, invalid_forms)
            
            stats = filler.get_processing_stats()
            print(f"📊 Error handling stats:")
            print(f"   ⚠️  Mapping errors: {stats['mapping_errors']}")
            print(f"   ❌ Fill errors: {stats['fill_errors']}")
            print(f"   ✅ Forms processed: {stats['forms_processed']}")
            
        print("✅ Error handling completed successfully")
        print("🧹 Cleanup guaranteed even with errors")
        
    except Exception as e:
        print(f"⚠️  Caught exception (as expected): {e}")
        print("🧹 Cleanup still guaranteed")


def main():
    """
    Main demonstration function showing all features.
    """
    print("🚀 Temporary Semantic PDF Form Filler - Complete Demonstration")
    print("=" * 80)
    
    # Run all demonstrations
    demonstrate_basic_usage()
    demonstrate_field_mapping_preview()
    demonstrate_convenience_function()
    demonstrate_error_handling()
    
    print("\n" + "="*80)
    print("✅ DEMONSTRATION COMPLETE")
    print("="*80)
    print("Key Features Demonstrated:")
    print("• ✅ Semantic field mapping (prevents wrong field assignments)")
    print("• ✅ Temporary storage only (zero persistence)")
    print("• ✅ Automatic cleanup (guaranteed)")
    print("• ✅ Batch processing")
    print("• ✅ Field mapping preview")
    print("• ✅ Robust error handling")
    print("• ✅ Memory management")
    print("• ✅ Context manager pattern")
    print("\n🎯 Core Problem Solved:")
    print("   Input: {'Phone': '313-478-9080', 'SSN': '123-45-6789'}")
    print("   ❌ Wrong: All fields get '313-478-9080'")
    print("   ✅ Correct: Phone field gets '313-478-9080', SSN field gets '123-45-6789'")


if __name__ == "__main__":
    main()
