#!/bin/bash

# Financial Document Processor - Release Publisher
# This script helps publish the built application to GitHub releases

set -e

echo "🚀 Financial Document Processor Release Publisher"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Please run this script from the Hack2 directory"
    exit 1
fi

# Check if dist directory exists
if [ ! -d "dist" ]; then
    echo "❌ Error: No dist directory found. Please build the application first:"
    echo "   npm run build-mac"
    exit 1
fi

# Get version from package.json
VERSION=$(node -p "require('./package.json').version")
echo "📦 Version: $VERSION"

# List available files
echo ""
echo "📁 Available distribution files:"
ls -lh dist/*.dmg dist/*.zip 2>/dev/null || echo "No distribution files found"

echo ""
echo "🔧 Publishing Options:"
echo "1. Automatic publish to GitHub releases:"
echo "   npx electron-builder --publish=always"
echo ""
echo "2. Manual GitHub release creation:"
echo "   - Go to: https://github.com/ankithn30/FinTech-Hackathon/releases/new"
echo "   - Tag version: v$VERSION"
echo "   - Upload files from the dist/ directory"
echo ""
echo "3. Build for all platforms and publish:"
echo "   npm run build -- --publish=always"

echo ""
read -p "🤔 Do you want to automatically publish to GitHub releases now? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Publishing to GitHub releases..."
    
    # Check if GitHub token is set
    if [ -z "$GH_TOKEN" ] && [ -z "$GITHUB_TOKEN" ]; then
        echo "⚠️  Warning: No GitHub token found in environment variables."
        echo "   Please set GH_TOKEN or GITHUB_TOKEN for automatic publishing."
        echo "   You can create a token at: https://github.com/settings/tokens"
        echo ""
        echo "   For now, we'll build without publishing."
        echo "   You can manually upload the files to GitHub releases."
    fi
    
    # Publish using electron-builder
    npx electron-builder --publish=always
    
    echo "✅ Release published successfully!"
    echo "🌐 View releases at: https://github.com/ankithn30/FinTech-Hackathon/releases"
else
    echo "📋 Manual steps to create a release:"
    echo "1. Go to: https://github.com/ankithn30/FinTech-Hackathon/releases/new"
    echo "2. Create tag: v$VERSION"
    echo "3. Release title: Financial Document Processor v$VERSION"
    echo "4. Upload these files:"
    echo "   - Financial Document Processor-$VERSION.dmg (Intel Mac)"
    echo "   - Financial Document Processor-$VERSION-arm64.dmg (Apple Silicon Mac)"
    echo "   - Financial Document Processor-$VERSION-mac.zip (Intel Mac)"
    echo "   - Financial Document Processor-$VERSION-arm64-mac.zip (Apple Silicon Mac)"
    echo ""
    echo "📖 See DISTRIBUTION_GUIDE.md for detailed instructions"
fi

echo ""
echo "🎉 Done! Your application is ready for distribution."
