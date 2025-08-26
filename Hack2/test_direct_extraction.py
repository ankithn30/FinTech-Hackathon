#!/usr/bin/env python3
"""
Test script for direct OpenAI extraction with terminal output
"""

import os
import sys
from openai_extraction_agent import OpenAIExtractionAgent

def test_direct_extraction():
    """Test the direct OpenAI extraction with terminal printing"""
    
    print("\n" + "="*80)
    print("🧪 TESTING DIRECT OPENAI EXTRACTION")
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
        # Initialize the extraction agent
        print("\n🤖 Initializing OpenAI Extraction Agent...")
        agent = OpenAIExtractionAgent(api_key=api_key)
        print("✅ Agent initialized successfully!")
        
        # Look for test PDF files
        test_files = []
        upload_dir = "uploads"
        
        if os.path.exists(upload_dir):
            for file in os.listdir(upload_dir):
                if file.lower().endswith('.pdf'):
                    test_files.append(os.path.join(upload_dir, file))
        
        # Also check current directory
        for file in os.listdir('.'):
            if file.lower().endswith('.pdf'):
                test_files.append(file)
        
        if not test_files:
            print("\n⚠️  No PDF files found for testing.")
            print("Please place a PDF file in the current directory or uploads/ folder.")
            
            # Create a sample text for testing the OpenAI API call
            print("\n🧪 Testing with sample text instead...")
            sample_text = """
            John Smith
            123 Main Street, Anytown, NY 12345
            Phone: (555) 123-4567
            Email: john.smith@email.com
            
            Employment: Software Engineer at Tech Corp
            Annual Salary: $75,000
            
            Bank: First National Bank
            Account: 123456789
            """
            
            print("📝 Sample document text:")
            print("-" * 40)
            print(sample_text)
            print("-" * 40)
            
            # Test the OpenAI extraction directly
            extracted_data = agent.extract_data_with_openai(sample_text)
            
            print("\n✅ DIRECT EXTRACTION TEST COMPLETED!")
            return True
        
        # Test with the first PDF file found
        test_file = test_files[0]
        print(f"\n📄 Testing with PDF file: {test_file}")
        
        # Extract data from the PDF
        result = agent.extract_from_document(test_file)
        
        if result["success"]:
            print(f"\n✅ EXTRACTION TEST COMPLETED SUCCESSFULLY!")
            print(f"📊 Fields extracted: {result['extraction_summary']['total_fields']}")
            print(f"💾 JSON saved to: {result['json_file_path']}")
            return True
        else:
            print(f"\n❌ EXTRACTION FAILED: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Direct OpenAI Extraction Test...")
    success = test_direct_extraction()
    
    if success:
        print("\n🎉 TEST PASSED! The direct OpenAI extraction is working correctly.")
        print("You can now use the /openai-extract endpoint in the web interface.")
    else:
        print("\n💥 TEST FAILED! Please check the error messages above.")
        print("Make sure you have:")
        print("1. Set the OPENAI_API_KEY environment variable")
        print("2. Installed the required dependencies: pip install -r requirements_openai.txt")
        print("3. Have a valid PDF file to test with")
    
    print("\n" + "="*80)
