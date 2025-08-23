#!/bin/bash

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp env_example.txt .env
    echo "Please edit .env file and add your LlamaCloud API key"
    echo "Then run this script again"
    exit 1
fi

# Check if API key is set
if grep -q "your_api_key_here" .env; then
    echo "Please edit .env file and add your actual LlamaCloud API key"
    exit 1
fi

echo "Starting PDF Text Extractor..."
echo "Open your browser and go to: http://localhost:5001"
echo "Press Ctrl+C to stop the application"
echo ""

python app.py
