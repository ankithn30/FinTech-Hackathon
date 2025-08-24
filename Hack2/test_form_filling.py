#!/usr/bin/env python3
"""
Test script for PDF form filling functionality
"""

import os
import sys
from pdfwriter import fill_pdf_from_llama

def test_form_filling():
    """Test the form filling with sample data"""
    
    # Sample extracted data (what you'd get from Llama parser)
    sample_data = {
        "name": "John Doe",
        "phone_number": "(555) 123-4567",
        "address": "123 Main Street, Anytown, USA 12345",
        "email": "john.doe@email.com"
    }
    
    # Check if we have a sample PDF to fill
    sample_pdf = "Sample.pdf"
    if not os.path.exists(sample_pdf):
        print(f"❌ Sample PDF not found: {sample_pdf}")
        print("Please upload a PDF form first through the web interface")
        return False
    
    # Test the form filling
    output_path = "test_filled_form.pdf"
    print("🔄 Testing form filling...")
    print(f"Input data: {sample_data}")
    print(f"Template PDF: {sample_pdf}")
    print(f"Output PDF: {output_path}")
    
    success = fill_pdf_from_llama(sample_data, sample_pdf, output_path)
    
    if success:
        print(f"✅ Form filled successfully! Check: {output_path}")
        return True
    else:
        print("❌ Form filling failed")
        return False

if __name__ == "__main__":
    test_form_filling()
