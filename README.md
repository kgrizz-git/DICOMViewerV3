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
- Calculate statistics (mean, standard deviation, min, max, area) within ROIs
- Measure distances (pixels, mm, or cm based on DICOM metadata)
- **Intensity Projections**: Combine multiple slices (2, 3, 4, 6, or 8) to create Average (AIP), Maximum (MIP), or Minimum (MinIP) intensity projections
  - Scroll through projections one underlying slice at a time
  - Access via right panel widget or context menu → "Combine..."
- **Histogram Display**: View pixel value distribution for the currently focused image
  - Press <code>H</code> key to open histogram dialog
  - Shows histogram with window/level box overlay (red dashed box indicating current window center and width)
  - Toggle between linear and logarithmic y-axis scaling
  - Automatically tracks focused subwindow and updates on focus/slice/window-level changes
  - Reflects raw or rescaled pixel values based on current setting
- Display RT STRUCT overlays (Not yet implemented)

### Data Management
- Clear ROIs from slice or whole dataset
- Clear measurements
- Undo/redo functionality for changes
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

### Keyboard Shortcuts
- **P**: Pan mode (move the image around)
- **Z**: Zoom mode (click and drag vertically to zoom)
- **R**: Rectangle ROI mode (draw rectangular regions of interest)
- **E**: Ellipse ROI mode (draw elliptical regions of interest)
- **M**: Measure mode (create distance measurements)
- **S**: Select mode (select ROIs and measurements)
- **W**: Window/Level ROI mode (auto-adjust from ROI)
- **C**: Clear all measurements on current slice
- **D**: Delete all ROIs on current slice
- **V**: Reset view (restore initial zoom, pan, and window/level for focused subwindow)
- **A**: Reset all views (reset zoom, pan, and window/level for all subwindows)
- **H**: Open histogram dialog (shows pixel value distribution with window/level overlay)
- **N**: Toggle series navigator bar visibility
- **Spacebar**: Toggle overlay visibility (cycles through 3 states)
- **Cmd+P / Ctrl+P**: Toggle Privacy View (masks patient-related tags in display)
- **Arrow Keys**: Navigate slices (Up/Down) and series (Left/Right)
- **Delete**: Delete selected ROI or measurement
- **I**: Invert image colors
- **Ctrl+T**: View/Edit DICOM Tags
- **Shift+Ctrl+T**: Export DICOM Tags

## Project Structure

```
DICOMViewerV3/
├── src/           # Source code
├── tests/         # Test files
├── docs/          # Documentation
└── data/          # Sample data and resources
```

## Development Rules

- Modular design: Methods and functions should do only one thing
- File size limit: Individual files should not exceed 500-1000 lines of code
- Extensive documentation: Comments at top of files and throughout code
- Linting: Check for linting errors after code edits
- User-focused: Ask for clarification rather than making assumptions
- UI behavior: Popup windows should initially appear on top and in focus

## Technology Stack

- **Language**: Python 3.9+
- **GUI Framework**: PySide6
- **DICOM Library**: pydicom
- **Image Processing**: NumPy, PIL/Pillow
- **Additional**: matplotlib (for histograms)

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python src/main.py`
