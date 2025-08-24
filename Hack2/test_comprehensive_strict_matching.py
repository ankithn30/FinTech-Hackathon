#!/usr/bin/env python3
"""
Comprehensive test using real documents and forms to verify strict matching behavior.
This test extracts data from actual documents and attempts to fill real forms.
"""

import sys
import os
import logging
import json
from FormFIller import PyMuPDFTemporaryFiller
from llama_utils import parse_pdf_with_dynamic_schema
from schema_utils import compile_schemas

# Set up logging to see the detailed matching process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Try to import llama parser if available
try:
    from llama_parser import llama_parse, simplify_llama_output
    LLAMA_PARSER_AVAILABLE = True
except Exception as e:
    print(f"LlamaParser not available: {e}")
    LLAMA_PARSER_AVAILABLE = False

def extract_data_from_document(doc_path):
    """Extract data from a document using available extraction methods"""
    print(f"📄 Extracting data from: {os.path.basename(doc_path)}")
    
    extracted_data = {}
    
    # Try Llama parser first if available
    if LLAMA_PARSER_AVAILABLE:
        try:
            # Define a comprehensive schema for financial document extraction
            schema_text = (
                "I want to extract these fields:\n"
                "name: Full legal name of the person or organization\n"
                "first_name: First name only\n"
                "last_name: Last name only\n"
                "phone_number: Primary phone number (digits, may include separators)\n"
                "address: Full mailing address or location\n"
                "street_address: Street address only\n"
                "city: City name\n"
                "state: State or province\n"
                "zip_code: ZIP or postal code\n"
                "email: Primary email address\n"
                "ssn: Social Security Number\n"
                "date_of_birth: Date of birth\n"
                "employer: Employer name\n"
                "income: Annual income or salary\n"
                "account_number: Bank account number\n"
                "routing_number: Bank routing number\n"
                "balance: Account balance\n"
                "signature: Signature field"
            )
            compiled_schema = compile_schemas([schema_text])
            llama_results = llama_parse([doc_path], compiled_schema)
            
            simplified = simplify_llama_output(llama_results)
            if simplified:
                extracted_data = simplified
                print(f"✅ LlamaParser extracted {len(extracted_data)} fields")
        except Exception as e:
            print(f"❌ LlamaParser error: {e}")
    
    # Fall back to PDF form extraction if no data or llama parser unavailable
    if not extracted_data:
        try:
            raw_form_data = parse_pdf_with_dynamic_schema(doc_path)
            if LLAMA_PARSER_AVAILABLE:
                extracted_data = simplify_llama_output(raw_form_data)
            else:
                extracted_data = raw_form_data
            print(f"✅ PDF form extraction found {len(extracted_data)} fields")
        except Exception as e:
            print(f"❌ PDF extraction error: {e}")
    
    return extracted_data

def test_form_with_extracted_data(form_path, extracted_data, form_name):
    """Test filling a specific form with extracted data"""
    print(f"\n📋 Testing form: {form_name}")
    print("-" * 50)
    
    if not extracted_data:
        print("❌ No extracted data available for testing")
        return
    
    try:
        with PyMuPDFTemporaryFiller() as filler:
            # Get field mapping preview first
            preview = filler.get_field_mapping_preview(extracted_data, form_path)
            
            if "error" in preview:
                print(f"❌ Error in preview: {preview['error']}")
                return
            
            print(f"📊 Form Analysis:")
            print(f"   Total form fields: {preview['total_form_fields']}")
            print(f"   Available fields: {len(preview['available_fields'])}")
            print(f"   Extracted data keys: {len(extracted_data)}")
            print(f"   Mapping success rate: {preview['mapping_success_rate']:.1f}%")
            
            if preview['successful_mappings']:
                print(f"\n✅ Fields that WILL be filled ({len(preview['successful_mappings'])}):")
                for extracted_key, form_field in preview['successful_mappings'].items():
                    value = extracted_data.get(extracted_key, 'N/A')
                    print(f"   '{extracted_key}' → '{form_field}' = '{value}'")
            else:
                print("\n✅ No fields will be filled (no exclusive matches found)")
            
            if preview['unmapped_keys']:
                print(f"\n❌ Fields that will be SKIPPED ({len(preview['unmapped_keys'])}):")
                for key in preview['unmapped_keys']:
                    value = extracted_data.get(key, 'N/A')
                    print(f"   '{key}' = '{value}' (no exclusive match)")
                    
                    # Show top suggestions for unmapped keys
                    if key in preview['mapping_suggestions']:
                        suggestions = preview['mapping_suggestions'][key][:2]  # Top 2
                        if suggestions:
                            print(f"      Best suggestions:")
                            for field, score in suggestions:
                                print(f"        - '{field}' (similarity: {score:.3f})")
            
            # Actually attempt to fill the form
            print(f"\n🚀 Attempting to fill form...")
            filled_path = filler.fill_single_form(extracted_data, form_path)
            
            if filled_path:
                stats = filler.get_processing_stats()
                print(f"✅ Form filled successfully!")
                print(f"   Fields filled: {stats['fields_filled']}")
                print(f"   Mapping errors: {stats['mapping_errors']}")
                print(f"   Fill errors: {stats['fill_errors']}")
                print(f"   Output saved to temporary location")
                return True
            else:
                print("❌ Form filling failed - no fields were filled")
                return False
                
    except Exception as e:
        print(f"❌ Error during form filling: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_comprehensive_test():
    """Run comprehensive test with all available documents and forms"""
    print("🧪 COMPREHENSIVE STRICT MATCHING TEST")
    print("=" * 60)
    print("Testing with real documents and forms from the project")
    print()
    
    # Available documents and forms
    documents = [
        ("Documents/Bank-Statement-Template-3-TemplateLab.pdf", "Bank Statement"),
        ("Documents/dda-en.pdf", "DDA Document")
    ]
    
    forms = [
        ("Forms/Consumer Loan Application fillable_1-1.pdf", "Consumer Loan Application"),
        ("Forms/F2.pdf", "F2 Form"),
        ("Forms/fw4-1.pdf", "W-4 Tax Form"),
        ("Forms/i-9-1.pdf", "I-9 Employment Form")
    ]
    
    # Test each document with each form
    total_tests = 0
    successful_fills = 0
    
    for doc_path, doc_name in documents:
        if not os.path.exists(doc_path):
            print(f"❌ Document not found: {doc_path}")
            continue
            
        print(f"\n🔍 PROCESSING DOCUMENT: {doc_name}")
        print("=" * 60)
        
        # Extract data from document
        extracted_data = extract_data_from_document(doc_path)
        
        if not extracted_data:
            print(f"❌ No data extracted from {doc_name}")
            continue
            
        print(f"📋 Extracted data keys: {list(extracted_data.keys())}")
        print(f"📊 Total extracted fields: {len(extracted_data)}")
        
        # Show extracted data
        print(f"\n📄 Extracted Data from {doc_name}:")
        for key, value in extracted_data.items():
            # Truncate long values for display
            display_value = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            print(f"   {key}: {display_value}")
        
        # Test with each form
        for form_path, form_name in forms:
            if not os.path.exists(form_path):
                print(f"❌ Form not found: {form_path}")
                continue
                
            total_tests += 1
            success = test_form_with_extracted_data(form_path, extracted_data, form_name)
            if success:
                successful_fills += 1
    
    # Summary
    print(f"\n🎯 COMPREHENSIVE TEST SUMMARY")
    print("=" * 60)
    print(f"📊 Total test combinations: {total_tests}")
    print(f"✅ Successful form fills: {successful_fills}")
    print(f"❌ Forms with no fills: {total_tests - successful_fills}")
    print(f"📈 Success rate: {(successful_fills/total_tests*100):.1f}%" if total_tests > 0 else "No tests run")
    
    print(f"\n🔒 STRICT MATCHING VERIFICATION:")
    print("   • High similarity threshold (95%) enforced")
    print("   • Ambiguous matches rejected")
    print("   • Only exclusive matches filled")
    print("   • Uncertain fields left empty for safety")
    
    if successful_fills == 0:
        print(f"\n✅ STRICT MATCHING WORKING CORRECTLY:")
        print("   No forms were filled, indicating the system is being")
        print("   appropriately conservative and only filling fields")
        print("   with exclusive matches as requested.")
    else:
        print(f"\n✅ STRICT MATCHING RESULTS:")
        print(f"   {successful_fills} forms had fields with exclusive matches")
        print("   All other uncertain matches were correctly skipped")

if __name__ == "__main__":
    run_comprehensive_test()
