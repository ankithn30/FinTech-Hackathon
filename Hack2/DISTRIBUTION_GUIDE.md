# Financial Document Processor - Distribution Guide

## Overview
This guide explains how to distribute the Financial Document Processing System desktop application to external users via GitHub releases.

## Current Build Configuration
The application is configured to build for multiple platforms:
- **macOS**: DMG and ZIP formats for both Intel (x64) and Apple Silicon (ARM64)
- **Windows**: NSIS installer and portable executable for x64 and ia32
- **Linux**: AppImage and DEB packages for x64

## Setting Up GitHub Releases for External Distribution

### 1. Automatic Release Publishing
The application is already configured for GitHub releases in `package.json`:
```json
"publish": {
  "provider": "github",
  "owner": "ankithn30",
  "repo": "FinTech-Hackathon"
}
```

### 2. Publishing to GitHub Releases
To publish a new release with the built packages:

```bash
# Build and publish automatically
npm run build -- --publish=always

# Or build first, then publish
npm run build
npx electron-builder --publish=always
```

### 3. Manual Release Creation
Alternatively, you can create releases manually:

1. **Build the packages:**
   ```bash
   npm run build-mac    # For macOS
   npm run build-win    # For Windows
   npm run build-linux  # For Linux
   ```

2. **Create a GitHub release:**
   - Go to your repository: https://github.com/ankithn30/FinTech-Hackathon
   - Click "Releases" → "Create a new release"
   - Tag version: `v1.0.0` (or increment as needed)
   - Release title: `Financial Document Processor v1.0.0`
   - Upload the built files from the `dist/` directory

### 4. Built Files Location
After building, distributable files are located in `Hack2/dist/`:

**macOS:**
- `Financial Document Processor-1.0.0.dmg` (Intel x64)
- `Financial Document Processor-1.0.0-arm64.dmg` (Apple Silicon)
- `Financial Document Processor-1.0.0-mac.zip` (Intel x64)
- `Financial Document Processor-1.0.0-arm64-mac.zip` (Apple Silicon)

**Windows:**
- `Financial Document Processor Setup 1.0.0.exe` (NSIS installer)
- `Financial Document Processor 1.0.0.exe` (Portable)

**Linux:**
- `Financial Document Processor-1.0.0.AppImage`
- `financial-document-processor_1.0.0_amd64.deb`

## User Installation Instructions

### macOS Users
1. Download the appropriate DMG file:
   - Intel Macs: `Financial Document Processor-1.0.0.dmg`
   - Apple Silicon Macs: `Financial Document Processor-1.0.0-arm64.dmg`
2. Double-click the DMG file
3. Drag the app to the Applications folder
4. Launch from Applications or Spotlight

### Windows Users
1. Download `Financial Document Processor Setup 1.0.0.exe`
2. Run the installer and follow the setup wizard
3. Launch from Start Menu or Desktop shortcut

### Linux Users
1. **AppImage (Recommended):**
   - Download `Financial Document Processor-1.0.0.AppImage`
   - Make it executable: `chmod +x Financial\ Document\ Processor-1.0.0.AppImage`
   - Run: `./Financial\ Document\ Processor-1.0.0.AppImage`

2. **DEB Package (Ubuntu/Debian):**
   - Download `financial-document-processor_1.0.0_amd64.deb`
   - Install: `sudo dpkg -i financial-document-processor_1.0.0_amd64.deb`

## System Requirements
- **macOS**: 10.15 (Catalina) or later
- **Windows**: Windows 10 or later
- **Linux**: Ubuntu 18.04+ or equivalent
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 500MB free space
- **Python**: 3.8+ (automatically managed by the app)

## Features
- AI-powered document processing using LlamaParse
- PDF form filling with extracted data
- Batch processing capabilities
- Secure local processing
- Cross-platform compatibility

## Support
For issues or questions:
- GitHub Issues: https://github.com/ankithn30/FinTech-Hackathon/issues
- Email: support@fintechprocessor.com

## License
MIT License - See LICENSE file for details
