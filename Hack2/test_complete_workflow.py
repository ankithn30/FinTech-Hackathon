#!/usr/bin/env python3
"""
Complete workflow test: Extract from Documents → Save JSON → Fill Forms
"""

import os
import sys
import json
from datetime import datetime
from openai_extraction_agent import OpenAIExtractionAgent
from openai_form_filling_agent import OpenAIFormFillingAgent

def test_complete_workflow():
    """Test the complete two-agent workflow with Documents and Forms folders"""
    
    print("\n" + "="*80)
    print("🚀 COMPLETE TWO-AGENT WORKFLOW TEST")
    print("="*80)
    print("📁 Documents folder → Extract data → Save JSON")
    print("📄 Forms folder → Fill forms with extracted data")
    print("="*80)
    
    # Check for OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OpenAI API key not found!")
        print("Please set the OPENAI_API_KEY environment variable:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        return False
    
    print(f"✅ OpenAI API key found: {api_key[:10]}...")
    
    try:
        # Step 1: Initialize agents
        print("\n🤖 Initializing OpenAI Agents...")
        extraction_agent = OpenAIExtractionAgent(api_key=api_key)
        filling_agent = OpenAIFormFillingAgent(api_key=api_key)
        print("✅ Both agents initialized successfully!")
        
        # Step 2: Find documents for extraction
        documents_folder = "Documents"
        forms_folder = "Forms"
        
        if not os.path.exists(documents_folder):
            print(f"❌ Documents folder not found: {documents_folder}")
            return False
            
        if not os.path.exists(forms_folder):
            print(f"❌ Forms folder not found: {forms_folder}")
            return False
        
        # Get all PDF files from Documents folder
        document_files = []
        for file in os.listdir(documents_folder):
            if file.lower().endswith('.pdf'):
                document_files.append(os.path.join(documents_folder, file))
        
        # Get all PDF files from Forms folder
        form_files = []
        for file in os.listdir(forms_folder):
            if file.lower().endswith('.pdf'):
                form_files.append(os.path.join(forms_folder, file))
        
        print(f"\n📄 Found {len(document_files)} documents for extraction:")
        for doc in document_files:
            print(f"   - {doc}")
            
        print(f"\n📋 Found {len(form_files)} forms for filling:")
        for form in form_files:
            print(f"   - {form}")
        
        if not document_files:
            print("❌ No PDF documents found for extraction!")
            return False
            
        if not form_files:
            print("❌ No PDF forms found for filling!")
            return False
        
        # Step 3: Extract data from documents
        print(f"\n" + "="*80)
        print("📊 PHASE 1: DATA EXTRACTION")
        print("="*80)
        
        all_extracted_data = {}
        json_files = []
        
        for doc_path in document_files:
            print(f"\n🔍 Processing document: {os.path.basename(doc_path)}")
            
            # Extract data from this document
            result = extraction_agent.extract_from_document(doc_path)
            
            if result["success"]:
                extracted_data = result["extracted_data"]
                
                # Save JSON to Documents folder (not extracted_data folder)
                base_name = os.path.splitext(os.path.basename(doc_path))[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_filename = f"{base_name}_extracted_{timestamp}.json"
                json_path = os.path.join(documents_folder, json_filename)
                
                # Create the JSON data structure
                json_data = {
                    "metadata": {
                        "extraction_timestamp": datetime.now().isoformat(),
                        "source_file": doc_path,
                        "extraction_agent": "OpenAI Extraction Agent",
                        "model_used": extraction_agent.model
                    },
                    "extracted_data": extracted_data
                }
                
                # Save JSON to Documents folder
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                
                print(f"💾 JSON saved to Documents folder: {json_path}")
                json_files.append(json_path)
                
                # Merge data for form filling
                for key, value in extracted_data.items():
                    if isinstance(value, dict):
                        if key not in all_extracted_data:
                            all_extracted_data[key] = {}
                        all_extracted_data[key].update(value)
                    else:
                        all_extracted_data[key] = value
                        
                print(f"✅ Successfully extracted {result['extraction_summary']['total_fields']} fields")
            else:
                print(f"❌ Extraction failed: {result.get('error', 'Unknown error')}")
        
        if not all_extracted_data:
            print("❌ No data was successfully extracted!")
            return False
        
        # Step 4: Fill forms with extracted data
        print(f"\n" + "="*80)
        print("📝 PHASE 2: FORM FILLING")
        print("="*80)
        
        # Create a combined JSON file for form filling
        combined_json_filename = f"combined_extracted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        combined_json_path = os.path.join(documents_folder, combined_json_filename)
        
        combined_data = {
            "metadata": {
                "extraction_timestamp": datetime.now().isoformat(),
                "source_files": document_files,
                "extraction_agent": "OpenAI Extraction Agent",
                "combined_from": len(document_files)
            },
            "extracted_data": all_extracted_data
        }
        
        with open(combined_json_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Combined JSON saved: {combined_json_path}")
        
        # Fill each form
        filled_forms = []
        for form_path in form_files:
            print(f"\n📋 Filling form: {os.path.basename(form_path)}")
            
            try:
                result = filling_agent.fill_form_from_json(form_path, combined_json_path)
                
                if result["success"]:
                    filled_form_path = result["output_pdf"]
                    filled_forms.append(filled_form_path)
                    print(f"✅ Form filled successfully: {filled_form_path}")
                    
                    # Show mapping summary
                    if "field_mappings" in result:
                        mapped_count = len([m for m in result["field_mappings"] if m.get("mapped_value")])
                        total_fields = len(result["field_mappings"])
                        print(f"📊 Mapped {mapped_count}/{total_fields} fields")
                else:
                    print(f"❌ Form filling failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Error filling form {form_path}: {str(e)}")
        
        # Step 5: Summary
        print(f"\n" + "="*80)
        print("📋 WORKFLOW SUMMARY")
        print("="*80)
        print(f"📄 Documents processed: {len(document_files)}")
        print(f"💾 JSON files created: {len(json_files) + 1}")  # +1 for combined
        print(f"📋 Forms filled: {len(filled_forms)}")
        print(f"✅ Success rate: {len(filled_forms)}/{len(form_files)} forms")
        
        print(f"\n📁 Files created in Documents folder:")
        for json_file in json_files + [combined_json_path]:
            print(f"   - {os.path.basename(json_file)}")
        
        print(f"\n📋 Filled forms created in Forms folder:")
        for filled_form in filled_forms:
            print(f"   - {os.path.basename(filled_form)}")
        
        print("="*80)
        
        if filled_forms:
            print("🎉 COMPLETE WORKFLOW TEST PASSED!")
            return True
        else:
            print("💥 WORKFLOW TEST FAILED - No forms were filled!")
            return False
            
    except Exception as e:
        print(f"\n❌ WORKFLOW ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting Complete Two-Agent Workflow Test...")
    success = test_complete_workflow()
    
    if success:
        print("\n🎉 COMPLETE WORKFLOW TEST SUCCESSFUL!")
        print("✅ Data extracted from Documents folder")
        print("✅ JSON files saved to Documents folder") 
        print("✅ Forms filled using extracted data")
        print("✅ Terminal output shows all processing steps")
    else:
        print("\n💥 WORKFLOW TEST FAILED!")
        print("Please check the error messages above.")
    
    print("\n" + "="*80)
