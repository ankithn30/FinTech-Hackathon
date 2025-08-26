#!/usr/bin/env python3
"""
Test enhanced schema-based form filling with fss4.pdf data
"""

import os
import json
from openai_form_filling_agent import OpenAIFormFillingAgent

def test_schema_based_filling():
    """Test the enhanced schema-based form filling approach"""
    
    print("\n" + "="*80)
    print("🔍 TESTING ENHANCED SCHEMA-BASED FORM FILLING")
    print("="*80)
    print("Step 1: Analyze form schema")
    print("Step 2: Map extracted data intelligently")
    print("Step 3: Fill form based on schema analysis")
    print("="*80)
    
    # Check for OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OpenAI API key not found!")
        return False
    
    print(f"✅ OpenAI API key found: {api_key[:10]}...")
    
    try:
        # Initialize form filling agent
        print("\n🤖 Initializing OpenAI Form Filling Agent...")
        agent = OpenAIFormFillingAgent(api_key=api_key)
        print("✅ Agent initialized successfully!")
        
        # Test files
        json_path = "Documents/fss4_extracted_20250826_004527.json"
        form_path = "Forms/fw4.pdf"
        
        if not os.path.exists(json_path):
            print(f"❌ JSON file not found: {json_path}")
            return False
            
        if not os.path.exists(form_path):
            print(f"❌ Form file not found: {form_path}")
            return False
        
        print(f"\n📄 Using extracted data: {json_path}")
        print(f"📋 Filling form: {form_path}")
        
        # Step 1: Preview the schema-based mapping
        print(f"\n" + "="*80)
        print("🔍 STEP 1: FORM SCHEMA ANALYSIS & MAPPING PREVIEW")
        print("="*80)
        
        preview_result = agent.preview_field_mapping(form_path, json_path)
        
        if preview_result["success"]:
            mapping_result = preview_result["mapping_result"]
            
            print(f"📊 Form Analysis Results:")
            print(f"   Total form fields: {preview_result['total_form_fields']}")
            print(f"   Fields mapped: {preview_result['mapped_fields']}")
            
            if "schema_analysis" in mapping_result:
                schema = mapping_result["schema_analysis"]
                print(f"   Field types found: {schema.get('field_types_found', [])}")
                print(f"   Key fields identified: {schema.get('key_fields_identified', [])}")
            
            print(f"\n📋 Field Mappings with Rationale:")
            field_mappings = mapping_result.get("field_mappings", {})
            mapping_rationale = mapping_result.get("mapping_rationale", {})
            mapping_confidence = mapping_result.get("mapping_confidence", {})
            
            for field_name, mapped_value in field_mappings.items():
                confidence = mapping_confidence.get(field_name, 0.0)
                rationale = mapping_rationale.get(field_name, "No rationale provided")
                print(f"   🎯 {field_name}: '{mapped_value}'")
                print(f"      Confidence: {confidence:.2f}")
                print(f"      Rationale: {rationale}")
                print()
            
            unmapped_fields = mapping_result.get("unmapped_fields", [])
            if unmapped_fields:
                print(f"📝 Unmapped fields ({len(unmapped_fields)}):")
                for field in unmapped_fields[:5]:  # Show first 5
                    print(f"   - {field}")
                if len(unmapped_fields) > 5:
                    print(f"   ... and {len(unmapped_fields) - 5} more")
            
            unused_data = mapping_result.get("unused_data", [])
            if unused_data:
                print(f"\n📊 Unused extracted data:")
                for data in unused_data[:5]:  # Show first 5
                    print(f"   - {data}")
                if len(unused_data) > 5:
                    print(f"   ... and {len(unused_data) - 5} more")
        
        else:
            print(f"❌ Schema analysis failed: {preview_result.get('error', 'Unknown error')}")
            return False
        
        # Step 2: Fill the form using schema-based mapping
        print(f"\n" + "="*80)
        print("📝 STEP 2: SCHEMA-BASED FORM FILLING")
        print("="*80)
        
        fill_result = agent.fill_form_from_json(form_path, json_path)
        
        if fill_result["success"]:
            print(f"✅ Form filled successfully!")
            print(f"📄 Input form: {fill_result['input_pdf']}")
            print(f"📊 Input data: {fill_result['input_json']}")
            print(f"💾 Output form: {fill_result['output_pdf']}")
            print(f"📈 Fields mapped: {fill_result['fields_mapped']}/{fill_result['total_form_fields']}")
            
            # Show the mapping summary
            mapping_result = fill_result.get("mapping_result", {})
            if "schema_analysis" in mapping_result:
                print(f"\n🎯 Schema Analysis Summary:")
                schema = mapping_result["schema_analysis"]
                print(f"   Total form fields analyzed: {schema.get('total_form_fields', 0)}")
                print(f"   Field types discovered: {', '.join(schema.get('field_types_found', []))}")
            
            print(f"\n🎉 SCHEMA-BASED FORM FILLING COMPLETED SUCCESSFULLY!")
            return True
            
        else:
            print(f"❌ Form filling failed: {fill_result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting Enhanced Schema-Based Form Filling Test...")
    success = test_schema_based_filling()
    
    if success:
        print("\n🎉 SCHEMA-BASED FORM FILLING TEST SUCCESSFUL!")
        print("✅ Form schema analyzed first")
        print("✅ Intelligent field mapping based on schema")
        print("✅ Data mapped according to field semantics")
        print("✅ Form filled with schema-guided approach")
    else:
        print("\n💥 SCHEMA-BASED FORM FILLING TEST FAILED!")
        print("Please check the error messages above.")
    
    print("\n" + "="*80)
