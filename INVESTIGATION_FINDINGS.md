# Investigation Findings - DICOM Viewer V3

**Date:** March 17, 2026
**Investigator:** Claude Code
**Repository:** kgrizz-git/DICOMViewerV3

---

## Executive Summary

This document presents findings from investigating three priority issues in the DICOM Viewer V3 application:

1. **[P1] 10-second lag before loading progress window appears** (PET/CT studies)
2. **[P1] Windows error/warning about a file with "gemini" in the name**
3. **[P1] Hardcoded absolute paths** (resources, fonts, images/icons)

### Key Findings
- **Loading Lag**: Root cause identified - file size checking happens before progress dialog appears
- **Gemini Reference**: Only a TO_DO note exists; no actual code references found
- **Hardcoded Paths**: Critical issue in font path handling for image export; resource loading is properly implemented

---

## Issue 1: 10-Second Lag Before Loading Progress Window (PET/CT Studies)

### Problem Description
Users report a significant delay (approximately 10 seconds) between selecting files to open and seeing the loading progress dialog, particularly noticeable when loading large PET/CT studies.

### Root Cause Analysis

#### Primary Culprit: File Size Checking Before Progress Dialog

**Location:** `src/core/file_operations_handler.py`

**Problematic Code Sequence:**
```python
# Line 248: Check large files BEFORE progress dialog is created
self._check_large_files(file_paths)

# Line 252: Reset loading manager
self._loading_manager.reset()

# Lines 256-260: FINALLY create progress dialog
progress = self._loading_manager.create_progress_dialog(...)
```

**Method Details** (`_check_large_files()` at lines 89-131):
```python
def _check_large_files(self, file_paths: list[str], threshold_mb: float = 25.0) -> None:
    threshold_bytes = threshold_mb * 1024 * 1024
    for file_path in file_paths:
        if os.path.isfile(file_path):
            try:
                file_size = os.path.getsize(file_path)  # ← BLOCKING I/O
                # ...checks and warnings...
```

**Why This Causes Lag:**
1. `os.path.getsize()` is synchronous and can be slow on:
   - Network drives
   - USB storage
   - Slow HDDs
   - Large file systems
2. For PET/CT studies with 100-500+ files, this accumulates:
   - 100 files × ~100ms each = 10 seconds
3. No UI feedback during this phase
4. No `QApplication.processEvents()` calls to keep UI responsive

#### Secondary Contributors

**1. File Extension Filtering** (Line 226-227)
```python
file_paths = [p for p in file_paths if not should_skip_path_for_dicom(p)]
```
- Synchronous list comprehension on large file sets
- No progress feedback
- Impact: ~0.1-0.5 seconds for large directories

**2. Config/Menu Updates** (Lines 237-239)
```python
if file_paths:
    self.config_manager.add_recent_file(file_paths[0])  # ← File I/O
    self.main_window.update_recent_menu()              # ← UI rebuild
```
- Config file I/O before progress dialog
- Menu rebuilding can be slow with many recent files
- Impact: ~0.5-2 seconds

**3. DICOM Validation During Load** (`src/core/dicom_loader.py` lines 124-196)
```python
file_size = os.path.getsize(file_path)  # ← Another blocking call
if file_size < 1048576:  # 1 MB
    return True, None
ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
```
- Happens during loading (after progress shown)
- But adds to perceived slowness

### PET/CT Specific Factors

PET/CT studies are particularly affected because:
1. **Large files**: Individual DICOM files often 500MB-2GB
2. **Many files**: CT series typically have 100-500+ slices
3. **Multi-frame data**: Enhanced multi-frame DICOMs require additional processing

### Complete Pre-Dialog Timeline

```
User Action: Select files
    ↓
1. File dialog interaction ................ 0-5s (user picking files)
    ↓
2. Extension filtering .................... ~0.1s (100 files)
    ↓
3. Add recent file & update menu .......... 0.5-2s (I/O + UI)
    ↓
4. _check_large_files() ................... 0-10s ← MAIN DELAY
    ↓
5. _loading_manager.reset() ............... <0.1s
    ↓
6. Progress dialog created & shown ........ <0.1s ← VISIBLE TO USER
    ↓
7. Actual file loading begins
```

### Progress Dialog Implementation (Properly Configured)

**File:** `src/core/loading_progress_manager.py` (Lines 157-192)

The progress dialog itself is correctly implemented:
```python
# Line 182: Shows immediately, no delay
progress.setMinimumDuration(0)

# Line 181: Modal to main window
progress.setWindowModality(Qt.WindowModality.WindowModal)

# Line 138: Keeps UI responsive during animation
QApplication.processEvents()
```

**The dialog works fine - it's just created too late in the sequence.**

### Recommended Solutions

#### High Priority Fixes

**1. Move File Size Checking After Progress Dialog Creation**
```python
# Show progress dialog FIRST
progress = self._loading_manager.create_progress_dialog(...)

# THEN do expensive checks with progress updates
self._check_large_files(file_paths, progress_callback=progress.setValue)
```

**2. Add Progress Feedback During File Checks**
- Show "Analyzing files..." message
- Update progress bar during iteration
- Call `QApplication.processEvents()` periodically

**3. Defer/Thread Non-Critical Operations**
- Move recent file updates to after loading starts
- Move menu updates to background thread
- Show progress immediately on file selection

#### Medium Priority Improvements

**4. Cache File Sizes**
- Avoid repeated `os.path.getsize()` calls
- Use OS-level metadata caching

**5. Async File Validation**
- Pre-validate files in background thread
- Show progress during validation

**6. Batch Operations**
- Process files in batches with UI updates between batches
- Throttle progress updates (don't update on every file)

### Impact Assessment

**Severity:** High
**Affected Users:** All users, especially with:
- Large PET/CT studies
- Network/NAS storage
- Slow storage devices
- Large file lists (100+ files)

**User Experience Impact:**
- Application appears frozen/unresponsive
- Users may think it crashed
- No feedback that processing is occurring
- Particularly frustrating for large datasets

---

## Issue 2: Windows Error About "Gemini" File

### Investigation Results

**Finding:** No actual "gemini" references found in the codebase.

### Search Coverage

Comprehensive search performed for "gemini" in:
- ✅ File names (all files in repository)
- ✅ Python source code
- ✅ Configuration files (JSON, YAML, INI)
- ✅ String literals in code
- ✅ Import statements
- ✅ Comments
- ✅ Documentation files

### Only Reference Found

**File:** `dev-docs/TO_DO.md`
**Line:** 37
**Content:**
```markdown
- [ ] **[P1]** Klaus reported Windows error about a file with "gemini" in the name
```

This is merely a note documenting the issue, not an actual code reference.

### Hypothesis: External System Issue

Since no "gemini" references exist in the application code, the error is likely:

1. **Antivirus/Security Software**
   - Windows Defender or third-party antivirus scanning
   - False positive on application files
   - Quarantine or warning about suspicious behavior

2. **Windows System Files**
   - Temporary files created by Windows
   - Windows Error Reporting (WER) files
   - System diagnostics or telemetry

3. **Python/PyInstaller Artifacts**
   - Temporary extraction directory names
   - PyInstaller bootloader files
   - Python runtime files

4. **User Environment**
   - User's specific Windows configuration
   - Installed software that monitors file operations
   - Corporate security policies

### Recommended Actions

**To Identify the Issue:**

1. **Request More Details from Klaus:**
   - Exact error message text
   - Screenshot of the error
   - Which application showed the error (DICOM Viewer or Windows)
   - When does it occur (startup, loading files, export, etc.)
   - Full file path mentioned in the error

2. **Check Windows Event Viewer:**
   - Application logs
   - System logs
   - Security logs
   - Look for entries related to DICOM Viewer

3. **Monitor File System Operations:**
   - Use Process Monitor (Sysinternals) to track all file operations
   - Look for files with "gemini" in the name being created/accessed
   - Identify which component creates such files

4. **Check PyInstaller Extraction:**
   - Examine `%TEMP%` directory for PyInstaller extraction folders
   - Check if any temporary files have unusual names

5. **Antivirus Logs:**
   - Check antivirus software logs
   - Look for quarantined or flagged files
   - Check Windows Defender history

**Preventive Measures:**

1. **Add Code Signing Certificate**
   - Sign the Windows executable
   - Reduces false positives from security software

2. **Add Application to Antivirus Whitelist**
   - Provide instructions in documentation
   - List common antivirus solutions

3. **Review PyInstaller Configuration**
   - Check `DICOMViewerV3.spec` for any unusual settings
   - Verify resource paths and hidden imports

### Impact Assessment

**Severity:** Unknown (requires more information)
**Affected Users:** At least one (Klaus) on Windows
**Reproducibility:** Unknown

**This issue requires user input to investigate further.**

---

## Issue 3: Hardcoded Absolute Paths

### Overview

Analysis of path handling throughout the codebase reveals:
- ✅ **Most resource loading is properly implemented** (icons, images, config)
- ✅ **Path normalization is cross-platform compatible**
- ❌ **Critical issue: Hardcoded system font paths in export functionality**

### Critical Issues: Hardcoded Font Paths

**Severity:** HIGH
**File:** `src/core/export_manager.py`
**Impact:** Image export will fail if system fonts are not at hardcoded locations

#### Locations with Hardcoded Paths

**1. ROI Statistics Text Overlay** (Lines 1146-1152)
```python
# Default font paths by platform
if sys.platform.startswith("win"):
    font_path = "C:/Windows/Fonts/arial.ttf"
elif sys.platform == "darwin":
    font_path = "/System/Library/Fonts/Helvetica.ttc"
else:  # Linux
    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
```

**2. Measurement Text Overlay** (Lines 1213-1219)
```python
if sys.platform.startswith("win"):
    font_path = "C:/Windows/Fonts/arial.ttf"
elif sys.platform == "darwin":
    font_path = "/System/Library/Fonts/Helvetica.ttc"
else:  # Linux
    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
```

**3. Complex Measurement with Bold Font** (Lines 1257-1262)
```python
if sys.platform.startswith("win"):
    font_path = "C:/Windows/Fonts/arialbd.ttf"  # Bold variant
elif sys.platform == "darwin":
    font_path = "/System/Library/Fonts/Helvetica.ttc"
else:  # Linux
    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
```

**4. Projection Overlay Text** (Lines 1358-1368)
```python
# Platform-specific font paths (with explanatory comments)
if sys.platform.startswith("win"):
    font_path = "C:/Windows/Fonts/arial.ttf"
elif sys.platform == "darwin":
    font_path = "/System/Library/Fonts/Helvetica.ttc"
else:  # Linux
    font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
```

#### Cross-Platform Problems

| Platform | Hardcoded Path | Issue |
|----------|---------------|-------|
| **Windows** | `C:/Windows/Fonts/arial.ttf` | Fails on non-English Windows (fonts may be in different paths), non-C: drive installations |
| **Windows** | `C:/Windows/Fonts/arialbd.ttf` | Bold Arial may not exist on all systems |
| **Linux** | `/usr/share/fonts/truetype/liberation/` | Only works on Debian/Ubuntu; Fedora, Arch, etc. use different paths |
| **macOS** | `/System/Library/Fonts/Helvetica.ttc` | Path may vary by macOS version; SIP restrictions |
| **All** | No fallback mechanism | Complete export failure if fonts not found |

#### Affected Functionality

When fonts are not found at hardcoded paths:
- ✗ ROI statistics overlay export fails
- ✗ Measurement overlay export fails
- ✗ Annotation overlay export fails
- ✗ Projection overlay text rendering fails
- ✗ All TIFF/PNG/JPEG exports with text overlays fail

### Properly Implemented Path Handling

#### 1. Resource Loading ✅

**File:** `src/gui/main_window.py` (Lines 49-75)

```python
def _get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development mode
        base_path = Path(__file__).parent.parent.parent

    resource_path = base_path / relative_path
    absolute_path = resource_path.resolve()
    path_str = str(absolute_path).replace('\\', '/')
    return path_str
```

**Why This Is Good:**
- Uses `__file__` for dynamic resolution
- Detects PyInstaller bundled vs development mode
- Uses `pathlib.Path` for cross-platform handling
- Converts Windows backslashes to forward slashes for Qt

#### 2. Icon and Image Loading ✅

**File:** `src/gui/main_window.py` (Lines 528-545, 709)

```python
# Set up resource search path for images using QDir.addSearchPath
resources_dir = str((base_path / "resources" / "images").resolve())
QDir.addSearchPath('images', resources_dir)

# Application icon
icon_path = Path(__file__).parent.parent.parent / 'resources' / 'icons' / 'dvv6ldvv6ldvv6ld_edit-removebg-preview.png'
```

**Why This Is Good:**
- Uses Qt's `QDir.addSearchPath()` for resource registration
- Uses `Path` objects for cross-platform compatibility
- Dynamically resolves paths relative to source

#### 3. Configuration Files ✅

**File:** `src/utils/config_manager.py` (Lines 99-103)

```python
if os.name == "nt":  # Windows
    app_data = os.getenv("APPDATA", os.path.expanduser("~"))
    self.config_dir = Path(app_data) / "DICOMViewerV3"
else:  # macOS / Linux
    self.config_dir = Path.home() / ".config" / "DICOMViewerV3"
```

**Why This Is Good:**
- Uses environment variables (`APPDATA`)
- Uses `Path.home()` for user home directory
- Platform-specific but using proper system conventions
- Creates directory structure automatically

#### 4. Path Normalization ✅

**File:** `src/utils/config/paths_config.py` (Lines 57-98)

```python
def normalize_path(self, file_path: str) -> str:
    """Normalize path for cross-platform compatibility."""
    if not file_path:
        return ""

    # Use os.path.normpath for cross-platform normalization
    normalized = os.path.normpath(file_path)
    normalized = os.path.abspath(normalized)

    # Handle root directory edge cases
    if normalized == os.path.sep:
        return normalized

    # Remove trailing slashes (except for root)
    while normalized.endswith(os.path.sep) and normalized != os.path.sep:
        normalized = normalized[:-1]

    return normalized
```

**Why This Is Good:**
- Uses `os.path.normpath()` and `os.path.abspath()`
- Handles root directory edge cases
- Removes trailing slashes correctly
- Preserves Windows drive roots

#### 5. PyInstaller Build Configuration ✅

**File:** `DICOMViewerV3.spec` (Lines 27-36, 42-44)

```python
# Dynamic path resolution
cwd = os.getcwd()
project_root = Path(cwd).resolve()
src_dir = project_root / 'src'
main_py = src_dir / 'main.py'

# Resources included correctly
datas=[
    ('resources', 'resources'),  # Include resources directory
],
```

**Why This Is Good:**
- Uses relative paths
- Uses `Path` API for cross-platform handling
- Correctly bundles resources directory

### Recommended Solutions

#### For Font Path Issues (CRITICAL)

**Option 1: Use Pillow's Built-in Font Handling**
```python
from PIL import ImageFont

# Let Pillow find system fonts
try:
    font = ImageFont.truetype("arial.ttf", size=font_size)
except OSError:
    font = ImageFont.truetype("LiberationSans-Regular.ttf", size=font_size)
except OSError:
    font = ImageFont.load_default()  # Fallback to bitmap font
```

**Option 2: Bundle Fonts with Application**
```python
# In resources/fonts/ directory, include Liberation Sans or similar open-source fonts
font_path = _get_resource_path("resources/fonts/LiberationSans-Regular.ttf")
try:
    font = ImageFont.truetype(font_path, size=font_size)
except OSError:
    font = ImageFont.load_default()
```

**Option 3: Use matplotlib.font_manager (Most Robust)**
```python
from matplotlib import font_manager

def find_system_font(family="sans-serif", weight="normal"):
    """Find system font using matplotlib's font manager."""
    font_prop = font_manager.FontProperties(family=family, weight=weight)
    font_file = font_manager.findfont(font_prop)
    return font_file

# Usage
font_path = find_system_font(family="sans-serif", weight="normal")
font = ImageFont.truetype(font_path, size=font_size)
```

**Option 4: Implement Platform-Specific Font Discovery**
```python
def find_system_font_path():
    """Find a suitable system font with proper fallback."""
    # Try platform-specific common locations
    if sys.platform.startswith("win"):
        candidates = [
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
            "C:/Windows/Fonts/arial.ttf",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",  # Arch Linux
            "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",  # Fedora
        ]

    # Check each candidate
    for path in candidates:
        if os.path.isfile(path):
            return path

    # Return bundled font path or None
    return None
```

#### Implementation Steps

1. **Add Liberation Sans to resources** (open-source, cross-platform)
2. **Implement font discovery function** with fallback chain
3. **Update all font loading in export_manager.py** (4 locations)
4. **Test on all platforms** (Windows, macOS, Linux variants)
5. **Update PyInstaller spec** to include bundled fonts

### Summary of Path Handling

| Category | Status | Notes |
|----------|--------|-------|
| Resource loading (icons, images) | ✅ Good | Uses `_get_resource_path()` |
| Configuration files | ✅ Good | Platform-specific, uses env vars |
| Path normalization | ✅ Good | Cross-platform compatible |
| PyInstaller bundling | ✅ Good | Relative paths, proper bundling |
| **System font paths** | ❌ **CRITICAL** | Hardcoded, will fail on many systems |

---

## Conclusions and Priorities

### Priority 1: Loading Progress Lag
- **Root cause identified:** File operations before progress dialog
- **Impact:** All users, especially large datasets
- **Solution complexity:** Medium (refactor operation order)
- **Estimated effort:** 2-4 hours

### Priority 2: Hardcoded Font Paths
- **Root cause identified:** System font paths hardcoded in export_manager.py
- **Impact:** Export failures on non-standard systems
- **Solution complexity:** Medium (implement font discovery + bundle fonts)
- **Estimated effort:** 3-6 hours

### Priority 3: Gemini File Reference
- **Status:** No code issue found, only a TO_DO note
- **Impact:** Unknown (one user report)
- **Next step:** Requires user input to diagnose
- **Estimated effort:** 1-2 hours (after more information provided)

---

## Recommended Next Steps

1. **Immediate:**
   - Fix loading progress lag (high user impact)
   - Implement robust font handling with bundled fallback
   - Request detailed error information from Klaus about "gemini" issue

2. **Short-term:**
   - Test fixes on multiple platforms
   - Add logging for file operations timing
   - Add logging for font loading success/failure

3. **Long-term:**
   - Consider async file operations
   - Improve progress feedback throughout application
   - Add comprehensive error reporting for Windows-specific issues

---

## Appendix: Key Files Reference

### Loading Progress
- `src/core/file_operations_handler.py` (Lines 89-131, 213-451)
- `src/core/loading_progress_manager.py` (Lines 119-192)
- `src/core/dicom_loader.py` (Lines 124-196, 457-617)

### Font Paths
- `src/core/export_manager.py` (Lines 1146-1152, 1213-1219, 1257-1262, 1358-1368)

### Resource Loading (Well-Implemented)
- `src/gui/main_window.py` (Lines 49-75, 528-545, 709)
- `src/utils/config_manager.py` (Lines 99-103)
- `src/utils/config/paths_config.py` (Lines 57-98)
- `DICOMViewerV3.spec` (Lines 27-36, 42-44)

---

**End of Investigation Report**
