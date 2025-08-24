#!/usr/bin/env python3
"""
Test script to verify strict matching behavior in FormFIller.
This demonstrates that only exclusive matches are filled, uncertain matches are skipped.
"""

import sys
import os
import logging
from FormFIller import PyMuPDFTemporaryFiller

# Set up logging to see the detailed matching process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_strict_matching():
    """Test the strict matching behavior with sample data"""
    
    print("🧪 Testing Strict Matching Behavior")
    print("=" * 50)
    
    # Sample extracted data that might have ambiguous matches
    test_data = {
        "Phone": "555-123-4567",
        "SSN": "123-45-6789", 
        "Name": "John Doe",
        "Address": "123 Main St",
        "Email": "john@example.com",
        "AmbiguousField": "Some Value",  # This should be skipped if no clear match
        "UnknownData": "Random Info"     # This should definitely be skipped
    }
    
    print(f"📋 Test Data: {test_data}")
    print()
    
    # Check if we have any sample forms to test with
    forms_dir = "Forms"
    if os.path.exists(forms_dir):
        form_files = [f for f in os.listdir(forms_dir) if f.endswith('.pdf')]
        if form_files:
            test_form = os.path.join(forms_dir, form_files[0])
            print(f"📄 Testing with form: {test_form}")
        else:
            print("❌ No PDF forms found in Forms directory")
            return
    else:
        print("❌ Forms directory not found")
        return
    
    print("\n🔍 Starting Strict Matching Test...")
    print("-" * 40)
    
    try:
        with PyMuPDFTemporaryFiller() as filler:
            # Get field mapping preview first
            preview = filler.get_field_mapping_preview(test_data, test_form)
            
            if "error" in preview:
                print(f"❌ Error in preview: {preview['error']}")
                return
            
            print(f"📊 Form Analysis:")
            print(f"   Total form fields: {preview['total_form_fields']}")
            print(f"   Mapping success rate: {preview['mapping_success_rate']:.1f}%")
            print()
            
            if preview['successful_mappings']:
                print("✅ Fields that WILL be filled:")
                for extracted_key, form_field in preview['successful_mappings'].items():
                    print(f"   '{extracted_key}' → '{form_field}'")
            else:
                print("✅ No fields will be filled (no exclusive matches)")
            
            print()
            
            if preview['unmapped_keys']:
                print("❌ Fields that will be SKIPPED (no exclusive match):")
                for key in preview['unmapped_keys']:
                    print(f"   '{key}' = '{test_data[key]}'")
                    
                    # Show suggestions for unmapped keys
                    if key in preview['mapping_suggestions']:
                        suggestions = preview['mapping_suggestions'][key][:3]  # Top 3
                        if suggestions:
                            print(f"      Possible matches (but not confident enough):")
                            for field, score in suggestions:
                                print(f"        - '{field}' (similarity: {score:.2f})")
            
            print()
            print("🎯 Key Benefits of Strict Matching:")
            print("   • Only fills fields with high confidence matches")
            print("   • Prevents incorrect data from being placed in wrong fields")
            print("   • Leaves uncertain fields empty rather than guessing")
            print("   • Reduces risk of form filling errors")
            
            # Actually fill the form to demonstrate
            print(f"\n🚀 Attempting to fill form with strict matching...")
            filled_path = filler.fill_single_form(test_data, test_form)
            
            if filled_path:
                stats = filler.get_processing_stats()
                print(f"✅ Form filled successfully!")
                print(f"   Fields filled: {stats['fields_filled']}")
                print(f"   Mapping errors: {stats['mapping_errors']}")
                print(f"   Fill errors: {stats['fill_errors']}")
                print(f"   Output: {filled_path}")
            else:
                print("❌ Form filling failed or no fields were filled")
                
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strict_matching()
