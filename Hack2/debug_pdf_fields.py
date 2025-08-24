#!/usr/bin/env python3
"""
Debug script to examine PDF form fields and test filling
"""

import os
import pdfrw
from pdfwriter import create_pdf_field_mapping, fill_pdf_from_llama

def examine_pdf_fields(pdf_path):
    """Examine the fields in a PDF form"""
    try:
        pdf = pdfrw.PdfReader(pdf_path)
        print(f"\n📄 PDF: {pdf_path}")
        print(f"Pages: {len(pdf.pages)}")
        
        if not pdf.Root.AcroForm:
            print("❌ No AcroForm found in PDF")
            return False
            
        if not pdf.Root.AcroForm.Fields:
            print("❌ No form fields found in PDF")
            return False
            
        fields = pdf.Root.AcroForm.Fields
        print(f"✅ Found {len(fields)} form fields:")
        
        for i, field in enumerate(fields):
            field_name = field.T if hasattr(field, 'T') else 'Unknown'
            field_type = field.FT if hasattr(field, 'FT') else 'Unknown'
            field_value = field.V if hasattr(field, 'V') else 'Empty'
            
            print(f"  {i+1}. Name: '{field_name}' | Type: {field_type} | Current Value: '{field_value}'")
            
        return True
        
    except Exception as e:
        print(f"❌ Error examining PDF: {e}")
        return False

def test_field_mapping(pdf_path, sample_data):
    """Test the field mapping logic"""
    print(f"\n🔍 Testing field mapping for: {pdf_path}")
    print(f"Sample data: {sample_data}")
    
    mapping = create_pdf_field_mapping(sample_data, pdf_path)
    print(f"Field mapping result: {mapping}")
    
    return mapping

def test_form_filling(pdf_path, sample_data, output_path):
    """Test the complete form filling process"""
    print(f"\n🚀 Testing form filling:")
    print(f"Input PDF: {pdf_path}")
    print(f"Output PDF: {output_path}")
    print(f"Data: {sample_data}")
    
    success = fill_pdf_from_llama(sample_data, pdf_path, output_path)
    
    if success:
        print(f"✅ Form filling successful! Check: {output_path}")
        return True
    else:
        print("❌ Form filling failed")
        return False

def main():
    """Main debug function"""
    print("🔍 PDF Form Field Debugger")
    print("=" * 50)
    
    # Sample data to test with
    sample_data = {
        "name": "John Doe",
        "phone_number": "(555) 123-4567",
        "address": "123 Main Street, Anytown, USA 12345",
        "email": "john.doe@email.com"
    }
    
    # Check for sample PDFs
    pdfs_to_test = []
    
    # Look for PDFs in current directory and uploads folder
    directories_to_check = ['.', 'uploads']
    
    for directory in directories_to_check:
        if os.path.exists(directory):
            for file in os.listdir(directory):
                if file.endswith('.pdf') and not file.startswith('filled_') and not file.startswith('debug_filled_'):
                    full_path = os.path.join(directory, file)
                    pdfs_to_test.append(full_path)
    
    if not pdfs_to_test:
        print("❌ No PDF files found in current directory")
        print("Please upload some PDF forms first")
        return
    
    print(f"Found PDFs: {pdfs_to_test}")
    
    # Test each PDF
    for pdf_file in pdfs_to_test:
        print(f"\n{'='*60}")
        
        # Examine the PDF structure
        has_fields = examine_pdf_fields(pdf_file)
        
        if has_fields:
            # Test field mapping
            mapping = test_field_mapping(pdf_file, sample_data)
            
            if mapping:
                # Test form filling
                output_file = f"debug_filled_{pdf_file}"
                test_form_filling(pdf_file, sample_data, output_file)
            else:
                print("⚠️  No field mapping found - form may not be fillable")
        else:
            print("⚠️  This PDF doesn't appear to have fillable form fields")
    
    print(f"\n{'='*60}")
    print("💡 Tips for fillable PDFs:")
    print("- Use PDFs created with form creation tools (Adobe Acrobat, etc.)")
    print("- Ensure the PDF has 'form fields' not just text")
    print("- Check that fields are named appropriately (Name, Email, etc.)")
    print("- Test with a simple contact form first")

if __name__ == "__main__":
    main()
