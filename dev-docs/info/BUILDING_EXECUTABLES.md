# Building Executables for DICOM Viewer V3

This guide explains how to compile the DICOM Viewer V3 application into standalone executables for macOS, Windows, and Linux.

## Overview

The recommended approach is to use **PyInstaller**, which works well with PySide6/Qt applications and supports all three platforms. PyInstaller bundles your Python application and all its dependencies into a single package that can be distributed without requiring users to install Python or any dependencies.

**Two build methods are available:**
1. **Local builds** (Steps 1-6): Build executables on your local machine for the current platform
2. **Automated builds with GitHub Actions** (Step 7): Automatically build executables for all platforms (Windows, macOS, Linux) using GitHub's servers - ideal if you only have access to one platform but need executables for all three

## Prerequisites

- Python 3.9 or higher installed
- All project dependencies installed (see `requirements.txt`)
- Build requirements installed (see Step 1 below)

## Step 1: Install Build Requirements

Install PyInstaller and other build tools:

```bash
pip install -r requirements-build.txt
```

Alternatively, install PyInstaller directly:

```bash
pip install pyinstaller
```

## Step 2: PyInstaller Spec File

A `DICOMViewerV3.spec` file is already included in the project root. This file configures how PyInstaller builds the executable.

**Note:** The spec file is already created and ready to use. You can skip to Step 3 if you want to use the default configuration, or modify the spec file if you need custom settings.

### Spec File Location

The spec file is located at: `DICOMViewerV3.spec` in the project root directory.

### Version Control Note

**Important:** The project's `.gitignore` file currently includes `*.spec`, which ignores all spec files. However, `DICOMViewerV3.spec` should be committed to version control because:

- It's required for GitHub Actions automated builds
- It ensures reproducible builds across team members
- It documents the build configuration

To include the spec file in Git despite the ignore pattern, use:
```bash
git add -f DICOMViewerV3.spec
```

See the "Version Control Considerations" section below for more details.

### Spec File Contents

The included spec file contains:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),  # Include resources directory
    ],
    hiddenimports=[
        'pydicom',
        'pydicom.encoders',
        'pydicom.decoders',
        'numpy',
        'PIL',
        'PIL._tkinter_finder',
        'matplotlib',
        'openpyxl',
        'pylibjpeg',
        'pyjpegls',
        'pylibjpeg.libjpeg',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DICOMViewerV3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging, False for windowed app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico/.icns file if you have one
)
```

### Spec File Options Explained

- **`datas`**: Includes non-Python files (like images, data files) that need to be bundled
- **`hiddenimports`**: Explicitly includes modules that PyInstaller might not automatically detect
- **`console=False`**: Creates a windowed application (no console window). Set to `True` for debugging
- **`upx=True`**: Enables UPX compression to reduce executable size (requires UPX to be installed)
- **`icon`**: Path to an icon file (`.ico` for Windows, `.icns` for macOS)

## Step 3: Build Executables

**Note:** Make sure you've installed the build requirements (Step 1) and that the `DICOMViewerV3.spec` file exists in the project root before proceeding.

### For macOS

1. Navigate to the project root directory
2. Run PyInstaller:
   ```bash
   pyinstaller DICOMViewerV3.spec
   ```
3. The executable will be created at `dist/DICOMViewerV3.app`

#### Creating a DMG (Optional)

To create a distributable DMG file for macOS:

1. Install `create-dmg` (if not already installed):
   ```bash
   brew install create-dmg
   ```

2. Create the DMG:
   ```bash
   create-dmg dist/DICOMViewerV3.app dist/
   ```

### For Windows

1. Navigate to the project root directory
2. Run PyInstaller:
   ```bash
   pyinstaller DICOMViewerV3.spec
   ```
3. The executable will be created at `dist/DICOMViewerV3.exe`

#### Adding an Icon (Optional)

1. Create or obtain a `.ico` file for your application
2. Update the spec file:
   ```python
   icon='path/to/your/icon.ico',
   ```
3. Rebuild the executable

### For Linux

1. Navigate to the project root directory
2. Run PyInstaller:
   ```bash
   pyinstaller DICOMViewerV3.spec
   ```
3. The executable will be created at `dist/DICOMViewerV3` (executable file)

#### Creating an AppImage (Optional)

For maximum portability on Linux, you can create an AppImage:

1. Install `appimagetool`:
   ```bash
   # Download from https://github.com/AppImage/AppImageKit/releases
   # Or install via package manager if available
   ```

2. Create an AppDir structure and package your executable
3. Use `appimagetool` to create the final AppImage

## Step 4: Platform-Specific Considerations

### macOS

#### Code Signing

For distribution outside the Mac App Store, you should code sign your application:

```bash
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/DICOMViewerV3.app
```

**Requirements:**
- Apple Developer account ($99/year)
- Valid code signing certificate

#### Notarization

For macOS Catalina (10.15) and later, you may need to notarize your application to avoid Gatekeeper warnings:

1. Create an app-specific password in your Apple ID account
2. Notarize using `xcrun notarytool`:
   ```bash
   xcrun notarytool submit dist/DICOMViewerV3.app \
       --apple-id your@email.com \
       --team-id YOUR_TEAM_ID \
       --password YOUR_APP_SPECIFIC_PASSWORD \
       --wait
   ```

3. Staple the notarization ticket:
   ```bash
   xcrun stapler staple dist/DICOMViewerV3.app
   ```

### Windows

#### Code Signing (Optional but Recommended)

Code signing helps avoid false positive antivirus warnings:

1. Obtain a code signing certificate (from a Certificate Authority or self-signed for testing)
2. Sign the executable:
   ```bash
   signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist/DICOMViewerV3.exe
   ```

#### Antivirus False Positives

PyInstaller executables sometimes trigger false positives from antivirus software. Code signing helps reduce this, but it may still occur. Consider:
- Submitting your executable to antivirus vendors for whitelisting
- Using a code signing certificate from a trusted CA
- Providing clear download instructions to users

### Linux

#### Library Dependencies

PyInstaller usually bundles Qt libraries, but you should test on a clean system to ensure all dependencies are included. If issues occur:

1. Test on a system without Python or Qt installed
2. Check for missing libraries using `ldd` (Linux) or `otool -L` (macOS)
3. Add missing libraries to the spec file's `binaries` section

#### Distribution Formats

Consider creating distribution packages:
- **Debian/Ubuntu**: `.deb` package
- **Red Hat/Fedora**: `.rpm` package
- **Universal**: AppImage (recommended for portability)

## Step 5: One-File vs One-Folder Distribution

The spec file above creates a **one-folder** distribution (executable + supporting files in a folder). For a **single-file executable**, modify the spec file:

```python
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DICOMViewerV3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DICOMViewerV3',
)
```

**Trade-offs:**
- **One-file**: Easier distribution, but slower startup (extracts to temp directory)
- **One-folder**: Faster startup, but requires distributing the entire folder

## Step 6: Quick Start (Alternative Method)

If you want to quickly test without using the spec file (though the spec file is recommended):

1. First, install build requirements:
   ```bash
   pip install -r requirements-build.txt
   ```

2. Then run PyInstaller directly:
   ```bash
   pyinstaller --name=DICOMViewerV3 \
       --windowed \
       --add-data "resources:resources" \
       --hidden-import=pydicom \
       --hidden-import=numpy \
       --hidden-import=PIL \
       --hidden-import=matplotlib \
       --hidden-import=openpyxl \
       src/main.py
   ```

This creates a basic executable. The spec file approach (using `DICOMViewerV3.spec`) is recommended for production builds as it provides more control and is already configured for this project.

## Step 7: Automated Builds with GitHub Actions

GitHub Actions provides a convenient way to automatically build executables for all three platforms (Windows, macOS, and Linux) without needing local machines for each platform. This is especially useful if you only have access to one platform (e.g., only a Mac) but need to create Windows and Linux executables.

### What is GitHub Actions?

GitHub Actions is a CI/CD (Continuous Integration/Continuous Deployment) service built directly into GitHub. It provides:

- **Virtual machines (runners)**: GitHub provides free virtual machines running Windows, macOS, and Linux
- **Automated workflows**: Define build processes in YAML files that run automatically
- **Event triggers**: Builds can trigger on pushes, tags, pull requests, or manual dispatch
- **Artifact storage**: Built executables can be stored as downloadable artifacts
- **Release integration**: Executables can be automatically attached to GitHub Releases

### Why Use GitHub Actions for Building?

**Key Advantages:**

1. **Cross-platform builds without local machines**: Build Windows executables on a Mac, Linux executables on Windows, etc.
2. **Automated and consistent**: Every build runs in a clean environment, ensuring reproducibility
3. **Free for public repositories**: Unlimited build minutes for public repos
4. **Parallel builds**: All three platforms build simultaneously, saving time
5. **Easy distribution**: Executables automatically attached to releases for easy download
6. **No setup required**: No need to install Python, dependencies, or build tools on multiple machines

**When to Use:**

- You only have access to one platform but need executables for all three
- You want automated builds on every release
- You want consistent, reproducible builds in a clean environment
- You want to distribute executables easily through GitHub Releases

### Overview

The included GitHub Actions workflow allows you to:
- Build executables on GitHub's servers (Windows, macOS, and Linux runners)
- Automatically build when you push version tags
- Store executables as downloadable artifacts or attach them to releases
- Build all platforms simultaneously

### Benefits

- **No local Windows/macOS/Linux machines needed**: Build Windows executables even if you only have a Mac
- **Automated**: Builds trigger automatically when you push version tags
- **Free for public repositories**: Unlimited build minutes for public repos
- **Consistent builds**: Clean environment for each build ensures reproducibility
- **Easy distribution**: Executables can be automatically attached to GitHub Releases

### Setup

A GitHub Actions workflow file is already included in the project at `.github/workflows/build.yml`. This workflow will:

1. **Trigger automatically** when you push a version tag (e.g., `v1.0.0`)
2. **Build on all platforms** simultaneously (Windows, macOS, Linux)
3. **Upload artifacts** that are available for 90 days
4. **Create releases** with executables attached when you push tags

### How to Use

#### Option 1: Build on Tag Push (Recommended for Releases)

1. **Create and push a version tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **GitHub Actions automatically**:
   - Detects the tag
   - Builds executables on all three platforms
   - Creates a GitHub Release
   - Attaches all executables to the release

3. **Download executables**:
   - Go to your repository on GitHub
   - Click on "Releases" in the right sidebar
   - Download the executables from the latest release

#### Option 2: Manual Trigger

1. Go to your repository on GitHub
2. Click on the "Actions" tab
3. Select "Build Executables" workflow
4. Click "Run workflow" button
5. Select the branch and click "Run workflow"
6. Wait for builds to complete
7. Download artifacts from the completed workflow run

### Understanding Artifacts vs Releases

GitHub Actions provides two ways to store and distribute your built executables:

#### Artifacts (Temporary Storage)

**What are Artifacts?**
- Artifacts are files uploaded during a workflow run
- They're stored temporarily and can be downloaded from the Actions tab
- Perfect for testing builds before creating official releases

**Characteristics:**
- **Storage duration**: 90 days for public repos, 400 days for private repos
- **Access**: Available from the "Actions" tab → workflow run → "Artifacts" section
- **Purpose**: Testing, development builds, temporary distribution
- **Size limit**: 10 GB per artifact, 1 GB per file
- **Download**: Must download from GitHub (not direct links)

**When to Use Artifacts:**
- Testing builds before creating a release
- Development or pre-release builds
- Sharing builds with team members for testing
- Quick access to build results without creating a release

**How to Access Artifacts:**

1. Go to your repository on GitHub
2. Click on the "Actions" tab
3. Find the completed workflow run (you'll see a green checkmark if successful)
4. Click on the workflow run to view details
5. Scroll down to the "Artifacts" section at the bottom
6. Download the artifact for your platform:
   - `DICOMViewerV3-Windows` (contains `.exe` and supporting files)
   - `DICOMViewerV3-macOS` (contains `.app` bundle)
   - `DICOMViewerV3-Linux` (contains Linux executable and supporting files)

**Note:** Artifacts are ZIP files. After downloading, extract them to access the executables.

#### Releases (Permanent Storage)

**What are Releases?**
- Releases are permanent, versioned distributions of your software
- They appear on your repository's Releases page
- Perfect for official distribution to end users

**Characteristics:**
- **Storage duration**: Permanent (as long as the release exists)
- **Access**: Available from the "Releases" page, visible to all repository visitors
- **Purpose**: Official distribution, version tracking, user downloads
- **Size limit**: No practical limit (GitHub allows very large files)
- **Download**: Direct download links, can be shared publicly
- **Versioning**: Each release has a version tag (e.g., v1.0.0)

**When to Use Releases:**
- Official software releases
- Distributing to end users
- Creating versioned software distributions
- When you want permanent, publicly accessible downloads

**How to Access Releases:**

1. Go to your repository on GitHub
2. Click on "Releases" in the right sidebar (or go to `https://github.com/yourusername/repo/releases`)
3. Find your release (created automatically when you push a version tag)
4. Download executables directly from the release page
5. Each platform's executable is listed as a downloadable asset

**Release Features:**
- Release notes (auto-generated or custom)
- Direct download links
- Version tags (e.g., v1.0.0)
- Changelog tracking
- Public visibility (for public repos)

### Comparison: Artifacts vs Releases

| Feature | Artifacts | Releases |
|---------|-----------|----------|
| **Storage Duration** | 90 days (public), 400 days (private) | Permanent |
| **Access** | Actions tab only | Public Releases page |
| **Purpose** | Testing, development | Official distribution |
| **Download Links** | Must download from GitHub | Direct, shareable links |
| **Versioning** | No version tags | Version tags (v1.0.0) |
| **Visibility** | Repository contributors | Public (for public repos) |
| **Best For** | Testing builds | User distribution |

### Workflow Behavior

The included workflow (`.github/workflows/build.yml`) creates both:

1. **Artifacts**: Always created for every build (manual or tag-triggered)
   - Available for 90 days
   - Accessible from Actions tab
   - Useful for testing

2. **Releases**: Only created when you push a version tag (e.g., `v1.0.0`)
   - Permanent storage
   - Publicly accessible
   - Includes release notes
   - Best for distribution

**Recommended Workflow:**
1. **Test with artifacts**: Use manual trigger to build and test via artifacts
2. **Create release**: When ready, push a version tag to create a permanent release

### Workflow Configuration

The workflow file (`.github/workflows/build.yml`) is configured to:

- **Build on**: Windows, macOS, and Linux
- **Python version**: 3.11
- **Trigger on**: Version tags (`v*`) and manual dispatch
- **Install**: All dependencies from `requirements.txt` and `requirements-build.txt`
- **Build**: Using `DICOMViewerV3.spec`
- **Output**: Executables in `dist/` directory

### Customizing the Workflow

You can modify `.github/workflows/build.yml` to:
- Change Python version
- Add additional build steps
- Modify artifact names
- Change release settings
- Add code signing (requires additional setup)

### Limitations

- **Requires GitHub repository**: You need to push your code to GitHub
- **Build time**: Free tier includes 2000 minutes/month for private repos (unlimited for public)
- **No code signing**: macOS/Windows executables won't be code signed (you'd need to sign them locally or use additional services)
- **Artifact expiration**: Artifacts expire after 90 days (unless attached to releases)

### Cost

- **Public repositories**: Free, unlimited build minutes
- **Private repositories**: Free tier includes 2000 minutes/month, additional minutes available for purchase

### Troubleshooting GitHub Actions Builds

If builds fail:

1. **Check workflow logs**: Click on the failed workflow run and examine the logs
2. **Test locally first**: Ensure the build works locally before pushing
3. **Verify dependencies**: Make sure all dependencies are in `requirements.txt` and `requirements-build.txt`
4. **Check Python version**: Ensure the Python version in the workflow matches your local version
5. **Remove typing package**: The workflow automatically removes the obsolete `typing` package, but you can do this manually if needed

### Complete Workflow Examples

#### Example 1: Testing Builds with Artifacts (No Release)

For testing builds without creating a release:

1. **Make sure your code is committed and pushed**:
   ```bash
   git add .
   git commit -m "Update for testing"
   git push origin main
   ```

2. **Manually trigger the workflow**:
   - Go to GitHub → Actions tab
   - Select "Build Executables" workflow
   - Click "Run workflow"
   - Select your branch and click "Run workflow"

3. **Wait for builds to complete** (usually 10-20 minutes)

4. **Download artifacts**:
   - Click on the completed workflow run
   - Scroll to "Artifacts" section
   - Download and test each platform's executable

5. **No release is created** - this is just for testing

#### Example 2: Creating an Official Release

For creating a permanent release with executables:

```bash
# 1. Make sure all changes are committed
git add .
git commit -m "Release version 1.0.0"
git push origin main

# 2. Create and push a version tag
git tag v1.0.0
git push origin v1.0.0

# 3. GitHub Actions automatically:
#    - Detects the tag push
#    - Builds executables on all platforms (Windows, macOS, Linux)
#    - Creates a GitHub Release with version v1.0.0
#    - Attaches all executables to the release
#    - Generates release notes automatically

# 4. Access your release:
#    - Go to GitHub → Releases page
#    - Find version v1.0.0
#    - Download executables directly
#    - Share the release URL with users
```

**Result:**
- Permanent release at `https://github.com/yourusername/repo/releases/tag/v1.0.0`
- All three platform executables available for download
- Release notes automatically generated
- Artifacts also available (for 90 days) in Actions tab

#### Example 3: Pre-release Testing Workflow

Recommended workflow for testing before release:

```bash
# 1. Test locally first
pyinstaller DICOMViewerV3.spec --clean
# Test the local build

# 2. Push code and test with artifacts
git add .
git commit -m "Prepare for release"
git push origin main

# 3. Manually trigger workflow to test
# (Use GitHub Actions manual trigger)

# 4. Download artifacts and test on each platform

# 5. If tests pass, create release
git tag v1.0.0
git push origin v1.0.0
```

## Step 8: Testing Checklist

Before distributing your executable, test thoroughly:

### Basic Functionality
- [ ] Application launches successfully
- [ ] Main window displays correctly
- [ ] All menu items are accessible
- [ ] Keyboard shortcuts work

### File Operations
- [ ] Can open DICOM files
- [ ] Can open DICOM directories
- [ ] Can load multi-frame DICOM files
- [ ] Can navigate between slices
- [ ] Can navigate between series

### Image Display
- [ ] Images display correctly
- [ ] Zoom functionality works
- [ ] Pan functionality works
- [ ] Window/Level adjustments work
- [ ] Image inversion works
- [ ] Overlays display correctly

### Tools and Features
- [ ] ROI drawing works (rectangles, ellipses)
- [ ] Crosshair tool works
- [ ] Measurement tool works
- [ ] Histogram displays correctly
- [ ] Cine playback works (for multi-frame)
- [ ] Intensity projections work

### Export and Save
- [ ] Can export images (PNG, JPEG)
- [ ] Can export to DICOM
- [ ] Can export DICOM tags to Excel/CSV
- [ ] Resource images load correctly (checkmarks)

### Testing Environment
- [ ] Test on a clean system (without Python installed)
- [ ] Test on target operating system version
- [ ] Test with various DICOM file types
- [ ] Test with compressed DICOM files (if supported)

## Troubleshooting

### Resources Not Found

If resource files (like images) aren't loading in the executable:

1. **Check resource paths in code**: The application may need to handle both development and bundled modes
2. **Use `sys._MEIPASS`**: PyInstaller sets this to the temporary directory where resources are extracted
3. **Update resource loading code** to check for bundled mode:
   ```python
   import sys
   import os
   
   def resource_path(relative_path):
       """Get absolute path to resource, works for dev and PyInstaller"""
       if getattr(sys, 'frozen', False):
           # Running in a bundle
           base_path = sys._MEIPASS
       else:
           # Running in development
           base_path = os.path.abspath(".")
       return os.path.join(base_path, relative_path)
   ```

### Missing Imports

If you get "ModuleNotFoundError" at runtime:

1. **Add to hiddenimports**: Add the missing module to the `hiddenimports` list in the spec file
2. **Check for dynamic imports**: Some modules are imported dynamically and PyInstaller can't detect them
3. **Use `--debug=all`**: Run PyInstaller with debug output to see what's being included:
   ```bash
   pyinstaller --debug=all DICOMViewerV3.spec
   ```

### Large Executable Size

Executables can be large (100-500 MB) due to bundled dependencies. To reduce size:

1. **Exclude unused modules**: Add to `excludes` in the spec file:
   ```python
   excludes=['matplotlib.tests', 'numpy.tests', 'PIL.tests'],
   ```

2. **Use UPX compression**: Already enabled in the spec file, but requires UPX to be installed
3. **Consider one-folder distribution**: Slightly smaller than one-file due to shared libraries

### Debugging Issues

If the executable crashes or doesn't work:

1. **Enable console output**: Set `console=True` in the spec file to see error messages
2. **Check logs**: PyInstaller may create log files in the build directory
3. **Test in development mode**: Ensure the application works when run with `python src/main.py` first
4. **Use `--log-level=DEBUG`**: Get detailed output during the build process:
   ```bash
   pyinstaller --log-level=DEBUG DICOMViewerV3.spec
   ```

### PySide6/Qt Issues

If Qt-related errors occur:

1. **Check Qt plugins**: Some Qt features require plugins that may not be automatically included
2. **Add Qt plugins explicitly**: In the spec file, add to `binaries`:
   ```python
   binaries=[
       ('path/to/qt/plugins', 'qt_plugins'),
   ],
   ```

3. **Set Qt environment variables**: May need to set `QT_PLUGIN_PATH` in runtime hooks

## Additional Resources

- [PyInstaller Documentation](https://pyinstaller.org/)
- [PyInstaller Manual](https://pyinstaller.org/en/stable/man/pyinstaller.html)
- [PySide6 Deployment Guide](https://doc.qt.io/qtforpython/deployment.html)
- [macOS Code Signing Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Windows Code Signing Guide](https://docs.microsoft.com/en-us/windows/win32/seccrypto/cryptography-tools)

## Build Scripts (Optional)

You can create build scripts to automate the process:

### `build_mac.sh`
```bash
#!/bin/bash
pyinstaller DICOMViewerV3.spec
# Add code signing and notarization steps here
```

### `build_windows.bat`
```batch
@echo off
pyinstaller DICOMViewerV3.spec
REM Add code signing steps here
```

### `build_linux.sh`
```bash
#!/bin/bash
pyinstaller DICOMViewerV3.spec
# Add AppImage creation steps here
```

Make scripts executable:
```bash
chmod +x build_mac.sh build_linux.sh
```

## Version Control Considerations

### Should Spec Files Be in Git?

**Recommendation: YES, include spec files in version control**

The `DICOMViewerV3.spec` file should be committed to your Git repository. Here's why:

**Reasons to Include Spec Files:**

1. **Reproducible builds**: Team members and CI/CD systems need the same spec file to build identical executables
2. **Configuration tracking**: The spec file contains important build configuration that should be version controlled
3. **GitHub Actions**: Automated builds require the spec file to be in the repository
4. **Collaboration**: Multiple developers can contribute to build configuration
5. **Documentation**: The spec file documents how executables are built

**Current Status:**

The project's `.gitignore` file currently includes `*.spec` (line 33), which means spec files are being ignored. However, since this project includes a specific, important spec file (`DICOMViewerV3.spec`), you should:

1. **Remove `*.spec` from `.gitignore`** (or make it more specific)
2. **Add `DICOMViewerV3.spec` to Git**:
   ```bash
   git add -f DICOMViewerV3.spec
   git commit -m "Add PyInstaller spec file to version control"
   ```

**Alternative Approach:**

If you want to keep the general `*.spec` ignore pattern but include the specific file:

1. Keep `*.spec` in `.gitignore`
2. Use `git add -f DICOMViewerV3.spec` to force-add the specific file
3. The file will be tracked even though `*.spec` is ignored

**What About Auto-Generated Spec Files?**

PyInstaller can auto-generate spec files when you run `pyinstaller` without a spec file. These auto-generated files:
- Should remain ignored (via `*.spec` in `.gitignore`)
- Are regenerated each time and don't need version control
- May differ between developers' environments

**Best Practice:**

- ✅ **Include**: Project-specific, manually created spec files (like `DICOMViewerV3.spec`)
- ❌ **Ignore**: Auto-generated spec files from PyInstaller
- ✅ **Document**: Keep the spec file in the repository for reproducible builds

### Build Artifacts and Git

**What to Ignore:**

The following build-related files and directories should be in `.gitignore`:

- `build/` - Temporary build directory created by PyInstaller
- `dist/` - Final executables and distribution files
- `*.spec` - Auto-generated spec files (but not your project spec file)
- `__pycache__/` - Python bytecode cache
- `.pyc` files - Compiled Python files

**What to Include:**

- `DICOMViewerV3.spec` - Your project's build configuration
- `.github/workflows/build.yml` - GitHub Actions workflow
- `requirements.txt` - Runtime dependencies
- `requirements-build.txt` - Build dependencies

## Notes

- **Build on target platform**: 
  - **Local builds**: You must build Windows executables on Windows, macOS executables on macOS, etc. (or use cross-compilation tools, which are more complex)
  - **Automated builds**: Use GitHub Actions (see Step 7) to build executables for all platforms without needing local machines for each platform
- **Python version**: Use the same Python version (or compatible) as your target users
- **Dependencies**: 
  - Ensure all runtime dependencies in `requirements.txt` are installed before building
  - Install build requirements from `requirements-build.txt` (includes PyInstaller)
- **File size**: Executables will be large (typically 100-500 MB) due to bundled Python interpreter and libraries
- **Startup time**: One-file executables may have slower startup times as they extract to a temporary directory
- **Spec file**: The `DICOMViewerV3.spec` file should be committed to version control for reproducible builds
- **GitHub Actions**: A workflow file (`.github/workflows/build.yml`) is included for automated cross-platform builds

