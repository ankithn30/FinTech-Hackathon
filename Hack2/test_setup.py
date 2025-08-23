#!/usr/bin/env python3
"""
Test script to verify the PDF Text Extractor setup
"""

import sys
import os

def test_imports():
    """Test if all required packages can be imported"""
    print("Testing imports...")
    
    try:
        import flask
        print(f"✓ Flask {flask.__version__}")
    except ImportError as e:
        print(f"✗ Flask import failed: {e}")
        return False
    
    try:
        import llama_cloud_services
        print(f"✓ LlamaCloud Services")
    except ImportError as e:
        print(f"✗ LlamaCloud Services import failed: {e}")
        return False
    
    try:
        import pydantic
        print(f"✓ Pydantic {pydantic.__version__}")
    except ImportError as e:
        print(f"✗ Pydantic import failed: {e}")
        return False
    
    try:
        import dotenv
        print(f"✓ Python-dotenv")
    except ImportError as e:
        print(f"✗ Python-dotenv import failed: {e}")
        return False
    
    return True

def test_environment():
    """Test environment setup"""
    print("\nTesting environment...")
    
    # Check if .env file exists
    if os.path.exists('.env'):
        print("✓ .env file exists")
        
        # Check if API key is set
        with open('.env', 'r') as f:
            content = f.read()
            if 'your_api_key_here' in content:
                print("⚠ .env file contains placeholder - please add your actual API key")
                return False
            elif 'LLAMA_CLOUD_API_KEY' in content:
                print("✓ API key appears to be configured")
                return True
            else:
                print("⚠ .env file doesn't contain LLAMA_CLOUD_API_KEY")
                return False
    else:
        print("✗ .env file not found - please run start.sh first")
        return False

def test_directories():
    """Test if required directories exist"""
    print("\nTesting directories...")
    
    if os.path.exists('uploads'):
        print("✓ uploads directory exists")
    else:
        print("✗ uploads directory missing")
        return False
    
    if os.path.exists('templates'):
        print("✓ templates directory exists")
    else:
        print("✗ templates directory missing")
        return False
    
    return True

def test_files():
    """Test if required files exist"""
    print("\nTesting files...")
    
    required_files = [
        'app.py',
        'requirements.txt',
        'templates/index.html',
        'start.sh'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} missing")
            return False
    
    return True

def main():
    """Run all tests"""
    print("PDF Text Extractor - Setup Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_environment,
        test_directories,
        test_files
    ]
    
    all_passed = True
    for test in tests:
        if not test():
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ All tests passed! Your setup is ready.")
        print("\nTo start the application:")
        print("1. Make sure you have a valid LlamaCloud API key in .env")
        print("2. Run: ./start.sh")
        print("3. Open: http://localhost:5001")
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        print("\nCommon solutions:")
        print("- Run: pip install -r requirements.txt")
        print("- Run: ./start.sh (to create .env file)")
        print("- Add your LlamaCloud API key to .env file")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
