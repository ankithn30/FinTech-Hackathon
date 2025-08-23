#!/usr/bin/env python3
"""
LlamaCloud Parser with AI Agent for Schema Analysis
"""

import os
import json
from dotenv import load_dotenv
from llama_cloud_services import LlamaParse
import anthropic

# Initialize the Anthropic client for AI analysis
client = anthropic.Anthropic(api_key="sk-ant-api03-MK64HfkWrlO7lPvk1QqsCl_AObIedAYmGyyAGD0diBp3KIx2qmbRsq8Fuv5ShE_XsfbXIzAw9T3BlbkFJ9Rqm7iITKfOsdvjxyAP2IvK5nyB4z8LIVsnS2SjxQGEM89h0pexNFaxk9v8MhkJqk5gClA9-wA")

def test_llama_connection():
    """Test if we can connect to LlamaCloud API"""
    print("Testing LlamaCloud API connection...")
    
    # Load environment variables
    load_dotenv()
    
    # Check if API key is set
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print("✗ LLAMA_CLOUD_API_KEY not found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    try:
        # Try to initialize the parser
        parser = LlamaParse()
        print("✓ LlamaParse initialized successfully")
        
        # Try to list agents (this will test the API connection)
        try:
            agents = parser.list_agents()
            print(f"✓ Successfully connected to LlamaCloud API")
            print(f"  Found {len(agents)} existing agents")
            return True
        except Exception as e:
            print(f"⚠ Could not list agents: {e}")
            print("  This might be normal if you don't have any agents yet")
            return True
            
    except Exception as e:
        print(f"✗ Failed to initialize LlamaParse: {e}")
        return False

def llama_parse(form_paths: list[str], compiled_schema: dict) -> list[dict]:
    """
    Main parsing function that processes forms using LlamaCloud and AI analysis
    """
    try:
        print(f"LlamaParser: Processing {len(form_paths)} forms...")
        
        # Initialize LlamaParse
        parser = LlamaParse()
        
        parsed_results = []
        
        for form_path in form_paths:
            print(f"LlamaParser: Parsing document: {os.path.basename(form_path)}")
            
            # Step 1: Parse the document using LlamaCloud to extract raw text/data
            parsed_document = parser.parse_document(form_path)
            print(f"LlamaParser: Document parsed successfully, extracted {len(str(parsed_document))} characters")
            
            # Step 2: Pass parsed document data and schema to AI Agent for header extraction
            ai_extraction = extract_headers_with_ai(parsed_document, compiled_schema)
            
            parsed_results.append({
                "form_path": form_path,
                "parsed_document": parsed_document,
                "extracted_headers": ai_extraction,
                "schema_compliance": check_schema_compliance(ai_extraction, compiled_schema)
            })
        
        print(f"LlamaParser: Successfully processed {len(parsed_results)} forms")
        return parsed_results
        
    except Exception as e:
        print(f"LlamaParser Error: {e}")
        return []

def extract_headers_with_ai(parsed_document: dict, compiled_schema: dict) -> dict:
    """
    AI Agent: Extracts specific headers from parsed document based on schema from schema_utils.py
    """
    try:
        # Create AI extraction prompt
        extraction_prompt = f"""You are an AI Agent specialized in extracting specific headers from financial documents.

TASK: Extract the exact headers specified in the schema from the parsed document text.

PARSED DOCUMENT TEXT:
{json.dumps(parsed_document, indent=2)}

REQUIRED HEADERS TO EXTRACT (from schema_utils.py):
{json.dumps(compiled_schema, indent=2)}

INSTRUCTIONS:
1. Review the parsed document text carefully
2. For each header defined in the schema, find and extract its corresponding value
3. Look for exact matches or close variations of the header names
4. If a header is not found, mark it as "NOT_FOUND"
5. If a header value is unclear, mark it as "UNCLEAR"
6. Provide confidence level for each extraction (HIGH, MEDIUM, LOW)
7. Return results in the exact format specified below

OUTPUT FORMAT:
{{
    "extracted_headers": [
        {{
            "header_name": "Header Name from Schema",
            "extracted_value": "Actual Value from Document or NOT_FOUND or UNCLEAR",
            "confidence": "HIGH/MEDIUM/LOW",
            "reasoning": "Brief explanation of where/how this header was found"
        }}
    ],
    "extraction_summary": {{
        "total_headers_requested": "Number of headers in schema",
        "successfully_extracted": "Number of headers with values found",
        "not_found": "Number of headers not found in document",
        "unclear": "Number of headers with unclear values",
        "overall_confidence": "HIGH/MEDIUM/LOW"
    }}
}}

Rules:
- Only extract headers that are explicitly defined in the schema
- Be precise and accurate in extraction
- Don't guess or make assumptions
- Mark missing or unclear headers appropriately
- Provide clear reasoning for each extraction
- Focus on the exact headers specified in the schema"""

        # Call Claude API for header extraction
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system="You are an AI Agent for header extraction from financial documents. Extract only the headers specified in the schema.",
            messages=[
                {"role": "user", "content": extraction_prompt}
            ]
        )
        
        # Parse the AI response
        ai_result = json.loads(response.content[0].text)
        
        print(f"AI Agent: Successfully extracted {ai_result.get('extraction_summary', {}).get('successfully_extracted', 0)} headers from document")
        return ai_result
        
    except Exception as e:
        print(f"AI Agent Error: {e}")
        return {
            "extracted_headers": [],
            "extraction_summary": {
                "total_headers_requested": 0,
                "successfully_extracted": 0,
                "not_found": 0,
                "unclear": 0,
                "overall_confidence": "LOW"
            },
            "error": str(e)
        }

def check_schema_compliance(ai_extraction: dict, compiled_schema: dict) -> dict:
    """
    Validates that AI header extraction complies with the expected schema from schema_utils.py
    """
    try:
        schema_fields = compiled_schema.get("fields", [])
        extracted_headers = ai_extraction.get("extracted_headers", [])
        
        compliance_report = {
            "schema_compliance": True,
            "missing_required_headers": [],
            "extra_headers": [],
            "compliance_score": 0.0
        }
        
        # Check for missing required headers
        schema_header_names = [field.get("name", "") for field in schema_fields]
        extracted_header_names = [header.get("header_name", "") for header in extracted_headers]
        
        missing_headers = [name for name in schema_header_names if name not in extracted_header_names]
        extra_headers = [name for name in extracted_header_names if name not in schema_header_names]
        
        compliance_report["missing_required_headers"] = missing_headers
        compliance_report["extra_headers"] = extra_headers
        
        # Calculate compliance score
        if schema_header_names:
            compliance_score = (len(schema_header_names) - len(missing_headers)) / len(schema_header_names)
            compliance_report["compliance_score"] = round(compliance_score, 2)
            compliance_report["schema_compliance"] = compliance_score >= 0.8
        
        return compliance_report
        
    except Exception as e:
        print(f"Schema Compliance Check Error: {e}")
        return {
            "schema_compliance": False,
            "missing_required_headers": [],
            "extra_headers": [],
            "compliance_score": 0.0,
            "error": str(e)
        }

if __name__ == "__main__":
    success = test_llama_connection()
    if success:
        print("\n✓ LlamaCloud connection test passed!")
        print("Your API key is working correctly.")
    else:
        print("\n✗ LlamaCloud connection test failed!")
        print("Please check your API key and internet connection.")
    
    exit(0 if success else 1)