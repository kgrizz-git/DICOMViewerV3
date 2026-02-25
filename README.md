# DICOM Viewer V3

A cross-platform DICOM viewer application for Windows, Mac, and Linux systems.

## Overview

This application provides comprehensive DICOM image viewing capabilities with advanced features for medical imaging analysis, including ROI drawing, measurements, annotations, and export functionality.

## Features

### File Management
- Open DICOM directories, files, folders, volumes, stacks, and series
- Recursive folder search when loading folders
- Attempt to load all files as DICOM regardless of extension (with warnings for unloadable files)
- Remember path of last folder or file opened
- Select and open multiple files at once

### Image Display
- Zoom and pan functionality
- Resizable image display window
- Window width and level adjustment (numerical input and mouse control)
- **Window/Level Presets**: Multiple presets from DICOM tags (WindowWidth/WindowCenter arrays)
  - Context menu to switch between presets
  - Status bar shows current preset name
  - First preset (W1, C1) loaded by default
  - If no presets found, window center uses median value, width uses range (max-min)
- Slice navigation with arrow keys or mouse wheel
- **Image Inversion**: Press <code>I</code> key or use context menu to invert image colors
- Series navigation with thumbnail navigator
- Switch mouse scroll wheel between zooming and slice navigation
- Dark or light interface option
- Reset view to fit viewport
- **Image Smoothing**: Optional image smoothing when zoomed (View menu or image context menu); off by default; persisted in config
- **Intensity Projections**: Combine multiple slices (2, 3, 4, 6, or 8) to view Average (AIP), Maximum (MIP), or Minimum (MinIP) intensity projections
  - Scroll through combined projections one underlying slice at a time
  - Access via right panel widget or context menu → "Combine..."
- **Image Inversion**: Toggle image inversion with <code>I</code> key or context menu
- **Cine Playback** (for multi-frame DICOM series):
  - Automatic frame-by-frame playback
  - Play, pause, and stop controls
  - Adjustable playback speed (0.25x, 0.5x, 1x, 2x, 4x)
  - Loop playback option
  - Frame slider for manual navigation
  - Real-time FPS display
  - Frame position indicator (current/total)
- **Image Fusion**: Overlay functional imaging (PET/SPECT) on anatomical imaging (CT/MR)
  - Fuse images from different series in the same study
  - Automatic spatial alignment using DICOM spatial metadata
  - Two resampling modes: Fast (2D) for compatible series, High Accuracy (3D) for different orientations
  - Adjustable opacity, threshold, and colormap for overlay visualization
  - Independent window/level controls for overlay series
  - Manual translation offset adjustment for fine-tuning alignment
  - Multiple interpolation methods (linear, nearest, cubic, b-spline) for 3D resampling
  - Access via right panel "Image Fusion" widget

### Metadata and Overlays
- Customizable DICOM metadata overlays on images
- Toggle overlay visibility with configurable content (3 states: all visible, corner text hidden, all text hidden)
- **DICOM Tag Editing:**
  - View and edit all DICOM tags, including private tags
  - Tree view for browsing tags organized by groups
  - **Tag filtering/search**: Search functionality for finding specific tags (case-insensitive, searches tag number, name, VR, and value)
  - **Expand/collapse groups**: Double-click group headers or use context menu to expand/collapse tag groups
  - **Reorder columns**: Drag column headers to reorder columns (Tag, Name, VR, Value) - preferences are saved
  - Undo/redo support for tag edits
  - Save changes to DICOM files
- **Annotations Support:**
  - Display DICOM Presentation States
  - Display Key Object Selection Documents
  - Display embedded overlays and graphic annotations in image files
- **DICOM Tag Export:**
  - Export selected DICOM tags to Excel (.xlsx) or CSV files
  - Choose which tags to export
  - Export from multiple slices or entire series
  - Save reusable **tag export presets** (named sets of tags) and apply them in the export dialog
  - Export and import tag export presets as JSON files for sharing between systems

### Privacy and Anonymization
- **Privacy View**: Toggle privacy mode to mask patient-related DICOM tags in the UI
  - Patient tags (Patient Name, Patient ID, Patient Date of Birth, etc.) display as "PRIVACY MODE"
  - Applies to metadata panel, tag viewer, and image overlays
  - Display-only feature - underlying data unchanged
  - Access via View menu, context menu, or Cmd+P/Ctrl+P shortcut
- **Anonymization on Export**: Option to anonymize patient information when exporting to DICOM format
  - Text-valued patient tags replaced with "ANONYMIZED"
  - Date/time patient tags removed
  - Available in export dialog when exporting to DICOM format

### Analysis Tools
- Draw elliptical or rectangular regions of interest (ROIs)
- Text annotations: Add and edit text labels on images (T key)
- Arrow annotations: Add arrows to point to features (A key)
- Draw crosshairs to display pixel values and coordinates at clicked points (crosshairs are a type of ROI)
- Calculate statistics (mean, standard deviation, min, max, area) within ROIs
- Measure distances (pixels, mm, or cm based on DICOM metadata)
- Undo/redo support for ROI and measurement operations (create, move, delete) - access via Edit menu or keyboard shortcuts
- **Intensity Projections**: Combine multiple slices (2, 3, 4, 6, or 8) to create Average (AIP), Maximum (MIP), or Minimum (MinIP) intensity projections
  - Scroll through projections one underlying slice at a time
  - Access via right panel widget or context menu → "Combine..."
- **Histogram Display**: View pixel value distribution for the currently focused image
  - Press <code>Cmd+Shift+H</code> / <code>Ctrl+Shift+H</code> to open histogram dialog
  - Shows histogram with window/level box overlay (red dashed box indicating current window center and width)
  - Toggle between linear and logarithmic y-axis scaling
  - Automatically tracks focused subwindow and updates on focus/slice/window-level changes
  - Reflects raw or rescaled pixel values based on current setting
- Display RT STRUCT overlays (Not yet implemented)

### Data Management
- Clear ROIs from slice or whole dataset (including crosshairs)
- Clear measurements
- Copy and paste annotations (ROIs, measurements, crosshairs, text annotations, arrow annotations)
  - Select annotations and copy with Cmd+C/Ctrl+C
  - Paste to current slice with Cmd+V/Ctrl+V
  - Smart offset: duplicates appear offset when pasting to same slice, no offset when pasting to different slice
  - Supports cross-slice pasting
- Undo/redo functionality for ROI, measurement, text annotation, and arrow annotation operations (create, move, delete, paste)
- ROI list panel with selection
- Status bar updates during file loading showing number of studies, series, and files loaded

### Export
- Export selected DICOM tags to Excel or CSV files
- Export images as JPEG, PNG, or DICOM with hierarchical selection
  - Select studies, series, and individual slices/instances using checkboxes
  - Export at displayed resolution (apply current zoom for high-resolution output)
  - Include overlays, ROIs, and measurements in exported images
  - Choose window/level settings (current viewer or dataset default)
  - Organized folder structure: Patient ID / Study Date - Study Description / Series Number - Series Description
  - Remembers last export directory between sessions
- **Export/Import Customizations**: Save and share your customization settings
  - Export overlay configuration, annotation options, metadata panel column widths, and theme to a JSON file
  - Import customizations from JSON file to quickly apply saved settings
  - Access via File → Export Customizations or File → Import Customizations
  - Use separate **Tag Preset** export/import (File → Export Tag Presets / Import Tag Presets) to back up or share just DICOM tag export presets

### Keyboard Shortcuts
- **P**: Pan mode (move the image around)
- **Z**: Zoom mode (click and drag vertically to zoom)
- **R**: Rectangle ROI mode (draw rectangular regions of interest)
- **E**: Ellipse ROI mode (draw elliptical regions of interest)
- **M**: Measure mode (create distance measurements)
- **S**: Select mode (select ROIs, measurements, text annotations, and arrow annotations)
- **W**: Window/Level ROI mode (auto-adjust from ROI)
- **T**: Text annotation mode (click to place and edit text labels)
- **A**: Arrow annotation mode (click and drag to draw arrows)
- **C**: Clear all measurements on current slice
- **D**: Delete all ROIs on current slice (including crosshairs)
- **Cmd+C / Ctrl+C**: Copy selected annotations (ROIs, measurements, crosshairs, text annotations, arrow annotations) - works in image viewer
- **Cmd+V / Ctrl+V**: Paste annotations to current slice - works in image viewer
- **Cmd+Z / Ctrl+Z**: Undo last operation (ROI/measurement/text/arrow annotation creation, move, or deletion)
- **Cmd+Shift+Z / Ctrl+Shift+Z**: Redo last undone operation
- **V**: Reset view (restore initial zoom, pan, and window/level for focused subwindow)
- **Shift+V**: Reset view (same as V)
- **Shift+A**: Reset all views (reset zoom, pan, and window/level for all subwindows)
- **Cmd+Shift+H / Ctrl+Shift+H**: Open histogram dialog (shows pixel value distribution with window/level overlay)
- **N**: Toggle series navigator bar visibility
- **Spacebar**: Toggle overlay visibility (cycles through 3 states)
- **Cmd+P / Ctrl+P**: Toggle Privacy View (masks patient-related tags in display)
- **Arrow Keys**: Navigate slices (Up/Down) and series (Left/Right)
- **Delete**: Delete selected ROI, measurement, text annotation, or arrow annotation
- **I**: Invert image colors
- **Ctrl+T**: View/Edit DICOM Tags (copy/paste for DICOM tags works in the Tag Viewer Dialog)
- **Shift+Ctrl+T**: Export DICOM Tags

## Project Structure

```
DICOMViewerV3/
├── src/           # Source code
├── tests/         # Test files
├── docs/          # Documentation
└── data/          # Sample data and resources
```

## Technology Stack

- **Language**: Python 3.9+
- **GUI Framework**: PySide6 (>=6.6.0)
- **DICOM Library**: pydicom (>=2.4.0)
- **Image Processing**: NumPy (>=1.24.0), Pillow (>=10.0.0)
- **Additional Libraries**: 
  - matplotlib (>=3.8.0) for histogram display
  - openpyxl (>=3.1.0) for Excel export functionality
  - pylibjpeg, pyjpegls, pylibjpeg-libjpeg for compressed DICOM support (optional but recommended)

## Installation

### Downloading the Application

You can download the DICOM Viewer V3 in one of two ways:

#### Option 1: Download as ZIP (Recommended for beginners)

1. Go to the [GitHub repository](https://github.com/kgrizz-git/DICOMViewerV3)
2. Click the green **"Code"** button
3. Select **"Download ZIP"**
4. Extract the ZIP file to a location of your choice
5. Navigate to the extracted folder (e.g., `DICOMViewerV3-main`)

#### Option 2: Clone with Git (Recommended for developers)

1. Open a terminal/command prompt
2. Navigate to where you want to download the project
3. Run:
   ```bash
   git clone https://github.com/kgrizz-git/DICOMViewerV3.git
   ```
4. Navigate into the project folder:
   ```bash
   cd DICOMViewerV3
   ```

### Installing Dependencies

1. **Navigate to the project root directory** (the folder containing `requirements.txt` and the `src` folder)
   - If you downloaded the ZIP, this is the extracted `DICOMViewerV3-main` or `DICOMViewerV3` folder
   - If you cloned with Git, this is the `DICOMViewerV3` folder

2. **Install Python dependencies** using one of the following methods:

   **Using pip (recommended):**
   ```bash
   pip install -r requirements.txt
   ```
   
   **If you need to specify the full path to requirements.txt:**
   ```bash
   pip install -r /path/to/DICOMViewerV3/requirements.txt
   ```
   
   **Using a virtual environment (recommended for isolation but not required):**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment (required before running the app or tests)
   # On Windows (Command Prompt):
   venv\Scripts\activate
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

### Running the Application

1. **Make sure you're in the project root directory** (the same folder where `requirements.txt` is located)

2. **Run the application** using one of the following methods:

   **From the project root directory:**
   ```bash
   python src/main.py
   ```
   
   **Or using Python module syntax:**
   ```bash
   python -m src.main
   ```
   
   **If you need to specify the full path:**
   ```bash
   python /path/to/DICOMViewerV3/src/main.py
   ```

3. The application window should open and you can start loading DICOM files!

### Running tests

**Activate the project venv first** (in the `venv` directory; see Installation). Then from the project root:

Unit tests can be run from the project root (with the virtual environment activated).

**Optional:** Install the test runner:
```bash
pip install pytest
```

**Run all tests (pytest or unittest):**
```bash
# From project root; venv activated
python tests/run_tests.py
```
This script sets `PYTHONPATH` to `src` and runs pytest if available, otherwise unittest.

**Run with pytest directly:**
```bash
# Windows (PowerShell)
$env:PYTHONPATH = "src"; python -m pytest tests -v --tb=short

# macOS/Linux
PYTHONPATH=src python -m pytest tests -v --tb=short
```

**Run with unittest:**
```bash
$env:PYTHONPATH = "src"; python -m unittest discover -s tests -p "test_*.py" -v
# or
python tests/run_tests.py --unittest
```

Tests live in `tests/`: `test_dicom_parser.py`, `test_dicom_loader.py`, `test_dicom_utils.py`, `test_export_manager.py`. No DICOM files are required for the current tests.

### Troubleshooting

- **"Module not found" errors**: Make sure you've installed all dependencies with `pip install -r requirements.txt`
- **"No such file or directory"**: Make sure you're running the command from the project root directory, or use the full path to `src/main.py`
- **Python version issues**: Ensure you have Python 3.9 or higher installed. Check with `python --version`
