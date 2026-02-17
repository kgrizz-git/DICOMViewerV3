# AppImage Creation Guide for DICOM Viewer V3

This guide explains how to create an AppImage distribution for DICOM Viewer V3 on Linux. AppImage is a universal Linux package format that allows users to run applications without installation.

## Table of Contents

1. [Overview](#overview)
2. [What is AppImage?](#what-is-appimage)
3. [Prerequisites](#prerequisites)
4. [Automated Script (Recommended)](#automated-script-recommended)
5. [Manual Creation Process](#manual-creation-process)
6. [Automated Creation with GitHub Actions](#automated-creation-with-github-actions)
7. [Testing the AppImage](#testing-the-appimage)
8. [Distribution](#distribution)
9. [Troubleshooting](#troubleshooting)
10. [Implementation Checklist](#implementation-checklist)

## Overview

AppImage packages your PyInstaller-built Linux executable into a single, portable file that:
- Runs on most Linux distributions without installation
- Includes all dependencies and resources
- Provides desktop integration (icon, menu entry)
- Can be "installed" by simply moving to a directory like `~/Applications` or `~/.local/bin`

**Current Build Configuration:**
- Your PyInstaller spec file creates a **one-folder distribution** (`exclude_binaries=True`)
- This means you have `dist/DICOMViewerV3/` containing:
  - `DICOMViewerV3` (main executable)
  - Supporting libraries and files
  - `resources/` directory with bundled assets

## What is AppImage?

AppImage is a format for distributing portable applications on Linux. Key features:

- **Single file**: Everything bundled into one `.AppImage` file
- **No installation**: Just download, make executable, and run
- **Portable**: Works across different Linux distributions
- **Desktop integration**: Includes `.desktop` file and icon for menu integration
- **Self-contained**: Includes all dependencies

## Prerequisites

Before creating an AppImage, ensure you have:

1. **Completed PyInstaller build** for Linux
   - Run `pyinstaller DICOMViewerV3.spec` on a Linux system
   - Verify `dist/DICOMViewerV3/` directory exists with all files

2. **AppImageTool**
   - Download from: https://github.com/AppImage/AppImageKit/releases
   - Look for `appimagetool-x86_64.AppImage` (or appropriate architecture)
   - Make it executable: `chmod +x appimagetool-x86_64.AppImage`

3. **Application icon**
   - PNG format (ideally 256x256 or larger)
   - Located at: `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png`

4. **Linux system** (for manual creation)
   - Ubuntu, Debian, Fedora, or similar
   - Basic command-line tools (bash, cp, mkdir, chmod)

## Automated Script (Recommended)

The easiest way to create an AppImage is using the provided automation script. This script automates all the manual steps described below.

### Quick Start

1. **Build with PyInstaller:**
   ```bash
   pyinstaller DICOMViewerV3.spec --clean --noconfirm
   ```

2. **Run the script:**
   ```bash
   chmod +x scripts/create_appimage.sh
   ./scripts/create_appimage.sh [version]
   ```

   Replace `[version]` with your version number (e.g., `3.0.0`). If omitted, it defaults to `latest`.

   Example:
   ```bash
   ./scripts/create_appimage.sh 3.0.0
   ```

3. **Result:**
   - Creates `DICOMViewerV3-3.0.0-x86_64.AppImage` in the project root
   - Script handles all steps automatically

### What the Script Does

The `scripts/create_appimage.sh` script automates the entire process:

1. **Downloads AppImageTool** if not present
2. **Creates AppDir structure** with proper directory hierarchy
3. **Copies PyInstaller build** from `dist/DICOMViewerV3/` to AppDir
4. **Creates desktop entry file** with proper metadata
5. **Copies application icon** to correct location
6. **Creates AppRun script** for AppImage entry point
7. **Builds the AppImage** using AppImageTool
8. **Makes AppImage executable**
9. **Provides summary** with file location and size

### Script Features

- **Automatic error checking**: Verifies PyInstaller build exists before proceeding
- **Version support**: Accepts version number as argument for proper naming
- **Clean output**: Colored output with clear status messages
- **Optional cleanup**: Prompts to remove AppDir after creation
- **Error handling**: Exits on errors with helpful messages

### Script Usage

```bash
# Basic usage (creates DICOMViewerV3-latest-x86_64.AppImage)
./scripts/create_appimage.sh

# With version (creates DICOMViewerV3-3.0.0-x86_64.AppImage)
./scripts/create_appimage.sh 3.0.0

# Make sure script is executable first
chmod +x scripts/create_appimage.sh
```

### Script Requirements

The script requires:
- PyInstaller build in `dist/DICOMViewerV3/`
- Icon file at `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png`
- Internet connection (for downloading AppImageTool on first run)
- Bash shell (standard on Linux)

### Script Output

When successful, the script outputs:
```
========================================
AppImage Creation Complete!
========================================

File: DICOMViewerV3-3.0.0-x86_64.AppImage
Size: 350M
Location: /path/to/DICOMViewerV3/DICOMViewerV3-3.0.0-x86_64.AppImage

To test the AppImage:
  ./DICOMViewerV3-3.0.0-x86_64.AppImage
```

### Troubleshooting the Script

**Script won't run:**
```bash
# Make sure it's executable
chmod +x scripts/create_appimage.sh

# Run from project root
cd /path/to/DICOMViewerV3
./scripts/create_appimage.sh
```

**PyInstaller build not found:**
- Ensure you've run `pyinstaller DICOMViewerV3.spec` first
- Check that `dist/DICOMViewerV3/` directory exists

**Icon not found:**
- Verify icon exists at `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png`
- Check file permissions

**AppImageTool download fails:**
- Check internet connection
- Verify GitHub releases URL is accessible
- Manually download AppImageTool and place in project root

### Customizing the Script

The script is located at `scripts/create_appimage.sh` and can be customized:

- **Change AppImage name**: Edit `APPIMAGE_NAME` variable
- **Modify desktop entry**: Edit the heredoc section that creates the `.desktop` file
- **Add additional files**: Add copy commands before the AppImage build step
- **Change icon location**: Modify `ICON_SOURCE` variable

## Manual Creation Process

If you prefer to create the AppImage manually, or if you need to customize the process, follow these steps. **Note:** The automated script above performs all these steps automatically.

Follow these steps to manually create an AppImage from your PyInstaller build.

### Step 1: Download AppImageTool

```bash
# Download AppImageTool
cd /tmp
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage

# Move to a permanent location (optional)
sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool
sudo chmod +x /usr/local/bin/appimagetool
```

### Step 2: Build with PyInstaller

Ensure you have a fresh PyInstaller build:

```bash
cd /path/to/DICOMViewerV3
pyinstaller DICOMViewerV3.spec --clean --noconfirm
```

Verify the build output:
```bash
ls -la dist/DICOMViewerV3/
# Should show: DICOMViewerV3 (executable) and supporting files
```

### Step 3: Create AppDir Structure

Create the AppDir directory structure that mimics a Linux filesystem:

```bash
# Create base AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p AppDir/usr/share/icons/hicolor/scalable/apps
```

### Step 4: Copy PyInstaller Build

Since your spec file creates a **one-folder distribution**, copy the entire `dist/DICOMViewerV3/` directory contents:

```bash
# Copy all files from PyInstaller build
cp -r dist/DICOMViewerV3/* AppDir/usr/bin/

# Verify the executable is present
ls -la AppDir/usr/bin/DICOMViewerV3
```

**Important:** The executable must be in `AppDir/usr/bin/` and be executable:
```bash
chmod +x AppDir/usr/bin/DICOMViewerV3
```

### Step 5: Create Desktop Entry File

Create `AppDir/usr/share/applications/DICOMViewerV3.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=DICOM Viewer V3
Comment=Medical imaging DICOM viewer application
Exec=DICOMViewerV3
Icon=DICOMViewerV3
Categories=Graphics;MedicalSoftware;Viewer;
Terminal=false
StartupNotify=true
MimeType=application/dicom;
```

**Key fields explained:**
- `Name`: Display name in application menus
- `Comment`: Tooltip/description text
- `Exec`: Command to run (relative to AppDir/usr/bin)
- `Icon`: Icon name (without extension)
- `Categories`: Desktop categories for menu organization
- `MimeType`: Associated file types (optional, for file associations)

### Step 6: Copy Application Icon

Copy your PNG icon to the AppDir:

```bash
# Copy 256x256 icon
cp resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png \
   AppDir/usr/share/icons/hicolor/256x256/apps/DICOMViewerV3.png

# Optionally create scalable version (SVG) if you have one
# cp resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.svg \
#    AppDir/usr/share/icons/hicolor/scalable/apps/DICOMViewerV3.svg
```

**Note:** The icon filename must match the `Icon` field in the `.desktop` file (without extension).

### Step 7: Create AppRun Script

Create `AppDir/AppRun` - this is the entry point that AppImage executes:

```bash
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/DICOMViewerV3" "$@"
```

Create the file:
```bash
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/DICOMViewerV3" "$@"
EOF

# Make it executable
chmod +x AppDir/AppRun
```

**How it works:**
- `HERE` gets the directory where AppRun is located (inside the mounted AppImage)
- `exec` runs your executable with all passed arguments
- The `"$@"` passes all command-line arguments to your application

### Step 8: Build the AppImage

Use AppImageTool to create the final AppImage:

```bash
# If appimagetool is in PATH
appimagetool AppDir DICOMViewerV3-x86_64.AppImage

# Or if using full path
./appimagetool-x86_64.AppImage AppDir DICOMViewerV3-x86_64.AppImage
```

**Output:**
- Creates `DICOMViewerV3-x86_64.AppImage` in the current directory
- File size will be large (200-500MB) as it includes all dependencies

### Step 9: Make AppImage Executable

```bash
chmod +x DICOMViewerV3-x86_64.AppImage
```

### Step 10: Test the AppImage

Test that the AppImage works:

```bash
# Run the AppImage
./DICOMViewerV3-x86_64.AppImage

# Or test with verbose output
./DICOMViewerV3-x86_64.AppImage --help
```

## Automated Creation with GitHub Actions

To automatically create AppImages during CI/CD, add steps to your GitHub Actions workflow.

### Overview

The workflow should:
1. Build the PyInstaller executable (already done)
2. Download AppImageTool
3. Create AppDir structure
4. Copy files and create desktop entry
5. Build AppImage
6. Upload as artifact/release asset

### Implementation Steps

Add these steps to `.github/workflows/build.yml` in the Linux build job:

```yaml
# Add after the "Build executable" step, before "Verify executable exists"

- name: Download AppImageTool
  if: matrix.os == 'ubuntu-latest'
  run: |
    wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
    sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool

- name: Create AppDir structure
  if: matrix.os == 'ubuntu-latest'
  run: |
    mkdir -p AppDir/usr/bin
    mkdir -p AppDir/usr/share/applications
    mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

- name: Copy PyInstaller build to AppDir
  if: matrix.os == 'ubuntu-latest'
  run: |
    cp -r dist/DICOMViewerV3/* AppDir/usr/bin/
    chmod +x AppDir/usr/bin/DICOMViewerV3

- name: Create desktop entry
  if: matrix.os == 'ubuntu-latest'
  run: |
    cat > AppDir/usr/share/applications/DICOMViewerV3.desktop << 'EOF'
    [Desktop Entry]
    Type=Application
    Name=DICOM Viewer V3
    Comment=Medical imaging DICOM viewer application
    Exec=DICOMViewerV3
    Icon=DICOMViewerV3
    Categories=Graphics;MedicalSoftware;Viewer;
    Terminal=false
    StartupNotify=true
    MimeType=application/dicom;
    EOF

- name: Copy icon
  if: matrix.os == 'ubuntu-latest'
  run: |
    cp resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png \
       AppDir/usr/share/icons/hicolor/256x256/apps/DICOMViewerV3.png

- name: Create AppRun script
  if: matrix.os == 'ubuntu-latest'
  run: |
    cat > AppDir/AppRun << 'EOF'
    #!/bin/bash
    HERE="$(dirname "$(readlink -f "${0}")")"
    exec "${HERE}/usr/bin/DICOMViewerV3" "$@"
    EOF
    chmod +x AppDir/AppRun

- name: Build AppImage
  if: matrix.os == 'ubuntu-latest'
  run: |
    appimagetool AppDir DICOMViewerV3-x86_64.AppImage
    chmod +x DICOMViewerV3-x86_64.AppImage
    ls -lh DICOMViewerV3-x86_64.AppImage

- name: Verify AppImage exists
  if: matrix.os == 'ubuntu-latest'
  run: |
    if [ ! -f "DICOMViewerV3-x86_64.AppImage" ]; then
      echo "Error: AppImage not created"
      exit 1
    fi
    file DICOMViewerV3-x86_64.AppImage
```

### Update Artifact Upload

Modify the "Upload build artifacts" step to include the AppImage:

```yaml
- name: Upload build artifacts
  uses: actions/upload-artifact@v4
  with:
    name: ${{ matrix.artifact_name }}
    path: |
      dist/DICOMViewerV3*
      DICOMViewerV3-x86_64.AppImage
      build/
    retention-days: 90
```

### Update Release Upload

Modify the "Create Release" step to include the AppImage:

```yaml
- name: Create Release (on tag push)
  if: startsWith(github.ref, 'refs/tags/')
  uses: softprops/action-gh-release@v1
  with:
    files: |
      dist/DICOMViewerV3*
      DICOMViewerV3-x86_64.AppImage
    draft: false
    prerelease: false
    generate_release_notes: true
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Testing the AppImage

Before distributing, thoroughly test the AppImage:

### Basic Functionality Tests

1. **Launch test:**
   ```bash
   ./DICOMViewerV3-x86_64.AppImage
   ```
   - Application should launch without errors
   - Main window should display correctly

2. **File association test:**
   - Right-click a DICOM file
   - Check if "Open with DICOM Viewer V3" appears (if MIME type configured)

3. **Menu integration test:**
   - Check application menu/launcher
   - Icon should appear correctly
   - Application name should be visible

4. **Resource loading test:**
   - Open a DICOM file
   - Verify images display correctly
   - Check that bundled resources (icons, checkmarks) load

5. **Cross-distribution test:**
   - Test on Ubuntu
   - Test on Fedora (if possible)
   - Test on Debian (if possible)

### Testing Checklist

- [ ] AppImage launches successfully
- [ ] Main window displays correctly
- [ ] Can open DICOM files
- [ ] Can open DICOM directories
- [ ] Images display correctly
- [ ] All menu items accessible
- [ ] Keyboard shortcuts work
- [ ] Resource images load (checkmarks, icons)
- [ ] Export functionality works
- [ ] Application icon appears in menu
- [ ] Desktop entry works (can launch from menu)
- [ ] No console errors on startup
- [ ] Application closes cleanly

## Distribution

### File Naming Convention

AppImages should follow this naming convention:
```
<ApplicationName>-<Version>-<Architecture>.AppImage
```

Example:
```
DICOMViewerV3-3.0.0-x86_64.AppImage
```

### Distribution Methods

1. **GitHub Releases** (Recommended)
   - Upload AppImage as a release asset
   - Provides versioning and download tracking
   - Users can download directly

2. **Direct download**
   - Host on your website
   - Provide direct download link
   - Include checksums (SHA256) for verification

3. **AppImage Hub** (Optional)
   - Submit to https://www.appimagehub.com/
   - Provides discovery and automatic updates
   - Requires additional metadata file

### User Instructions

Provide these instructions to users:

```markdown
## Linux Installation (AppImage)

1. Download `DICOMViewerV3-x86_64.AppImage`

2. Make it executable:
   ```bash
   chmod +x DICOMViewerV3-x86_64.AppImage
   ```

3. Run it:
   ```bash
   ./DICOMViewerV3-x86_64.AppImage
   ```

4. (Optional) Move to Applications directory for easy access:
   ```bash
   mkdir -p ~/Applications
   mv DICOMViewerV3-x86_64.AppImage ~/Applications/
   ```

5. (Optional) Create desktop shortcut:
   - Right-click the AppImage
   - Select "Integrate and run" (if available)
   - Or manually create a `.desktop` file in `~/.local/share/applications/`
```

## Troubleshooting

### AppImage Won't Run

**Problem:** AppImage doesn't execute or shows permission denied.

**Solutions:**
```bash
# Make executable
chmod +x DICOMViewerV3-x86_64.AppImage

# Check if it's actually executable
ls -l DICOMViewerV3-x86_64.AppImage

# Try running with explicit interpreter
bash DICOMViewerV3-x86_64.AppImage
```

### Application Crashes on Launch

**Problem:** AppImage launches but crashes immediately.

**Solutions:**
1. **Check for missing libraries:**
   ```bash
   # Extract and inspect
   ./DICOMViewerV3-x86_64.AppImage --appimage-extract
   cd squashfs-root
   ldd usr/bin/DICOMViewerV3
   ```

2. **Run with debug output:**
   ```bash
   APPIMAGE_DEBUG=1 ./DICOMViewerV3-x86_64.AppImage
   ```

3. **Check Qt/PySide6 dependencies:**
   - Ensure all Qt libraries are bundled
   - Check for missing Qt plugins

### Resources Not Found

**Problem:** Application can't find bundled resources (images, icons).

**Solutions:**
1. **Verify resources are in AppDir:**
   ```bash
   ./DICOMViewerV3-x86_64.AppImage --appimage-extract
   ls -la squashfs-root/usr/bin/resources/
   ```

2. **Check resource path handling in code:**
   - Ensure code uses `sys._MEIPASS` for PyInstaller
   - AppImage mounts at a different path - may need special handling

3. **Test resource loading:**
   - Add debug output to verify resource paths
   - Check if paths are relative or absolute

### Icon Not Displaying

**Problem:** Application icon doesn't appear in menus.

**Solutions:**
1. **Verify icon file exists:**
   ```bash
   ./DICOMViewerV3-x86_64.AppImage --appimage-extract
   ls -la squashfs-root/usr/share/icons/hicolor/256x256/apps/
   ```

2. **Check desktop entry:**
   - Verify `Icon` field matches filename (without extension)
   - Ensure icon is in correct directory structure

3. **Update icon cache:**
   ```bash
   # On user's system (not in AppImage)
   gtk-update-icon-cache ~/.local/share/icons/hicolor/
   ```

### Large File Size

**Problem:** AppImage is very large (500MB+).

**Solutions:**
1. **This is normal** - AppImages bundle all dependencies
   - Python interpreter: ~50MB
   - PySide6/Qt: ~100-200MB
   - NumPy/SciPy: ~50-100MB
   - Other dependencies: ~50-100MB
   - Total: 250-450MB is typical

2. **Reduce size (if needed):**
   - Exclude unnecessary modules in PyInstaller spec
   - Use UPX compression (already enabled)
   - Remove debug symbols

### Desktop Entry Not Working

**Problem:** Application doesn't appear in application menu.

**Solutions:**
1. **Verify desktop entry:**
   ```bash
   ./DICOMViewerV3-x86_64.AppImage --appimage-extract
   cat squashfs-root/usr/share/applications/DICOMViewerV3.desktop
   ```

2. **Check desktop entry syntax:**
   - Ensure no syntax errors
   - Verify all required fields present
   - Check Categories field format

3. **Test desktop entry:**
   ```bash
   desktop-file-validate AppDir/usr/share/applications/DICOMViewerV3.desktop
   ```

## Implementation Checklist

Use this checklist when implementing AppImage creation:

### Automated Script Setup (Recommended)
- [ ] Make script executable: `chmod +x scripts/create_appimage.sh`
- [ ] Verify PyInstaller build exists: `dist/DICOMViewerV3/`
- [ ] Verify icon exists: `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png`
- [ ] Run script: `./scripts/create_appimage.sh [version]`
- [ ] Test created AppImage
- [ ] Verify AppImage file size and location

### Manual Setup (Alternative)
- [ ] Download AppImageTool
- [ ] Make AppImageTool executable
- [ ] Verify PyInstaller build works
- [ ] Create AppDir structure
- [ ] Copy PyInstaller build to AppDir
- [ ] Create desktop entry file
- [ ] Copy application icon
- [ ] Create AppRun script
- [ ] Build AppImage
- [ ] Make AppImage executable
- [ ] Test AppImage locally

### GitHub Actions Integration
- [ ] Add AppImageTool download step
- [ ] Add AppDir creation step
- [ ] Add file copy steps
- [ ] Add desktop entry creation
- [ ] Add icon copy step
- [ ] Add AppRun creation step
- [ ] Add AppImage build step
- [ ] Update artifact upload to include AppImage
- [ ] Update release upload to include AppImage
- [ ] Test workflow on Linux runner

### Testing
- [ ] Test AppImage launches
- [ ] Test file opening
- [ ] Test resource loading
- [ ] Test icon display
- [ ] Test desktop integration
- [ ] Test on multiple Linux distributions (if possible)
- [ ] Verify all application features work

### Documentation
- [ ] Update README with AppImage instructions
- [ ] Add user installation guide
- [ ] Document any special requirements
- [ ] Add troubleshooting section

### Distribution
- [ ] Upload to GitHub Releases
- [ ] Verify download works
- [ ] Test on clean Linux system
- [ ] Provide user instructions
- [ ] (Optional) Submit to AppImage Hub

## Additional Resources

- **AppImage Documentation:** https://docs.appimage.org/
- **AppImageTool GitHub:** https://github.com/AppImage/AppImageKit
- **Desktop Entry Specification:** https://specifications.freedesktop.org/desktop-entry-spec/
- **AppImage Hub:** https://www.appimagehub.com/

## Notes

- **File Size:** AppImages are large (200-500MB) because they bundle everything. This is normal and expected.
- **Architecture:** This guide covers x86_64. For ARM64, use `appimagetool-aarch64.AppImage` and adjust naming.
- **Versioning:** Consider including version in filename: `DICOMViewerV3-3.0.0-x86_64.AppImage`
- **Updates:** AppImages don't auto-update. Users download new versions manually.
- **Security:** Users should verify AppImage checksums before running.
