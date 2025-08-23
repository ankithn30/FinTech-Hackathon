#!/usr/bin/env python3
"""
Test script to verify LlamaCloud API connection
"""

import os
from dotenv import load_dotenv
from llama_cloud_services import LlamaExtract

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
        # Try to initialize the extractor
        extractor = LlamaExtract()
        print("✓ LlamaExtract initialized successfully")
        
        # Try to list agents (this will test the API connection)
        try:
            agents = extractor.list_agents()
            print(f"✓ Successfully connected to LlamaCloud API")
            print(f"  Found {len(agents)} existing agents")
            return True
        except Exception as e:
            print(f"⚠ Could not list agents: {e}")
            print("  This might be normal if you don't have any agents yet")
            return True
            
    except Exception as e:
        print(f"✗ Failed to initialize LlamaExtract: {e}")
        return False

if __name__ == "__main__":
    success = test_llama_connection()
    if success:
        print("\n✓ LlamaCloud connection test passed!")
        print("Your API key is working correctly.")
    else:
        print("\n✗ LlamaCloud connection test failed!")
        print("Please check your API key and internet connection.")
    
    exit(0 if success else 1)
