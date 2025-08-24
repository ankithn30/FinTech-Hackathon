# How to Download and Install the Financial Document Processor

## Current Status
✅ Your application is built and ready! The files are located in `Hack2/dist/`

## Option 1: Install Directly from Local Files (Immediate)

### For Your Current Mac:
1. **Open Finder and navigate to:**
   ```
   /Users/useer/Downloads/FinTech-Hackathon/Hack2/dist/
   ```

2. **Choose the right file for your Mac:**
   - **Intel Mac**: Double-click `Financial Document Processor-1.0.0.dmg`
   - **Apple Silicon Mac**: Double-click `Financial Document Processor-1.0.0-arm64.dmg`

3. **Install:**
   - The DMG will mount and show a window
   - Drag the "Financial Document Processor" app to the Applications folder
   - Eject the DMG
   - Launch from Applications or Spotlight search

### Quick Terminal Install:
```bash
# Navigate to the dist folder
cd ~/Downloads/FinTech-Hackathon/Hack2/dist/

# For Intel Mac:
open "Financial Document Processor-1.0.0.dmg"

# For Apple Silicon Mac:
open "Financial Document Processor-1.0.0-arm64.dmg"
```

## Option 2: Share via GitHub Releases (For Others to Download)

### Step 1: Create a GitHub Release
```bash
cd ~/Downloads/FinTech-Hackathon/Hack2
./publish-release.sh
```

### Step 2: Manual GitHub Release (Alternative)
1. Go to: https://github.com/ankithn30/FinTech-Hackathon/releases/new
2. Tag version: `v1.0.0`
3. Release title: `Financial Document Processor v1.0.0`
4. Upload these files from `Hack2/dist/`:
   - `Financial Document Processor-1.0.0.dmg` (Intel Mac)
   - `Financial Document Processor-1.0.0-arm64.dmg` (Apple Silicon Mac)
   - `Financial Document Processor-1.0.0-mac.zip` (Intel Mac - Alternative)
   - `Financial Document Processor-1.0.0-arm64-mac.zip` (Apple Silicon Mac - Alternative)

### Step 3: Share the Download Link
Once published, share this link: `https://github.com/ankithn30/FinTech-Hackathon/releases/latest`

## Option 3: Direct File Sharing

### Send Files Directly:
You can send the DMG files directly via:
- **Email** (files are ~65-125 MB each)
- **Cloud storage** (Google Drive, Dropbox, iCloud, etc.)
- **File transfer services** (WeTransfer, etc.)

### File Locations:
```
~/Downloads/FinTech-Hackathon/Hack2/dist/Financial Document Processor-1.0.0.dmg
~/Downloads/FinTech-Hackathon/Hack2/dist/Financial Document Processor-1.0.0-arm64.dmg
```

## For Recipients (Installation Instructions)

### macOS Installation:
1. Download the appropriate DMG file:
   - Intel Macs: `Financial Document Processor-1.0.0.dmg`
   - Apple Silicon Macs: `Financial Document Processor-1.0.0-arm64.dmg`
2. Double-click the downloaded DMG file
3. Drag the app to Applications folder
4. Launch from Applications or Spotlight

### First Launch:
- macOS may show a security warning for unsigned apps
- Go to System Preferences → Security & Privacy → General
- Click "Open Anyway" next to the blocked app message

## System Requirements
- **macOS**: 10.15 (Catalina) or later
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 500MB free space

## Troubleshooting
- If the app won't open, try right-clicking → Open instead of double-clicking
- For "damaged" app warnings, run: `xattr -cr "/Applications/Financial Document Processor.app"`

## Quick Test
After installation, the app should:
1. Launch with your custom Logo icon
2. Start the Flask server automatically
3. Open the web interface in the app window
4. Be ready to process documents

🎉 **Your application is ready to use and share!**
