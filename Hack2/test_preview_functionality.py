#!/usr/bin/env python3
"""
Test script to verify the form preview functionality works correctly.
"""

import os
import sys
import json
import tempfile
from FormFIller import PyMuPDFTemporaryFiller

def test_preview_functionality():
    """Test the form preview and edit functionality"""
    
    # Sample extracted data (matching what we see in the logs)
    extracted_data = {
        "Employee Name Address": "Elon Musk",
        "Employee phone number": "123-456-789", 
        "Employee ID": "907863"
    }
    
    print("🧪 Testing Form Preview Functionality")
    print("=" * 50)
    print(f"Extracted data: {extracted_data}")
    
    # Look for a sample form to test with
    forms_dir = "Forms"
    if os.path.exists(forms_dir):
        pdf_files = [f for f in os.listdir(forms_dir) if f.endswith('.pdf')]
        if pdf_files:
            test_form = os.path.join(forms_dir, pdf_files[0])
            print(f"Testing with form: {test_form}")
            
            # Test the FormFIller functionality
            with PyMuPDFTemporaryFiller() as filler:
                print("\n🔍 Discovering form fields...")
                form_fields = filler.mapper.discover_fields_memory(test_form)
                print(f"Found {len(form_fields)} form fields:")
                for field_name in form_fields.keys():
                    print(f"  - {field_name}")
                
                print("\n🗺️  Testing field mapping...")
                mapped_data = filler.mapper.map_data_to_fields(extracted_data, test_form)
                print(f"Successfully mapped {len(mapped_data)} fields:")
                for key, value in mapped_data.items():
                    print(f"  ✅ {key} = {value}")
                
                if mapped_data:
                    print("\n📄 Testing form filling...")
                    filled_path = filler.fill_single_form(extracted_data, test_form)
                    if filled_path:
                        print(f"✅ Form filled successfully: {filled_path}")
                        print(f"File exists: {os.path.exists(filled_path)}")
                        
                        # Test preview generation (simulate what the web app does)
                        print("\n🖼️  Testing preview generation...")
                        try:
                            import fitz
                            doc = fitz.open(filled_path)
                            page = doc[0]
                            mat = fitz.Matrix(150/72, 150/72)
                            pix = page.get_pixmap(matrix=mat)
                            img_data = pix.tobytes("png")
                            doc.close()
                            
                            print(f"✅ Preview generated successfully ({len(img_data)} bytes)")
                            return True
                        except Exception as e:
                            print(f"❌ Preview generation failed: {e}")
                            return False
                    else:
                        print("❌ Form filling failed")
                        return False
                else:
                    print("❌ No fields could be mapped")
                    return False
        else:
            print("❌ No PDF files found in Forms directory")
            return False
    else:
        print("❌ Forms directory not found")
        return False

if __name__ == "__main__":
    success = test_preview_functionality()
    if success:
        print("\n✅ Preview functionality test PASSED")
    else:
        print("\n❌ Preview functionality test FAILED")
    
    sys.exit(0 if success else 1)
