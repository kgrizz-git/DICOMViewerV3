# DICOM Viewer V2

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
- Slice navigation with arrow keys or mouse wheel
- Switch mouse scroll wheel between zooming and slice navigation
- Dark or light interface option

### Metadata and Overlays
- Customizable DICOM metadata overlays on images
- Switch between minimal, detailed, and hidden overlay modes
- Display and edit all DICOM tags, including private tags

### Analysis Tools
- Draw elliptical or rectangular regions of interest (ROIs)
- Calculate statistics (mean, standard deviation) within ROIs
- Measure distances (pixels, mm, or cm based on DICOM metadata)
- Histogram display for whole slice or selected ROI
- Window width and level indication overlaid on histogram
- Combine slices into thicker slices (average or maximum intensity projections)
- Display annotations and RT STRUCT overlays

### Data Management
- Clear ROIs from slice or whole dataset
- Undo/redo functionality for changes

### Export
- Export as JPEG, PNG, or DICOM
- Export single slice, whole series, or whole study

## Project Structure

```
DICOMViewerV2/
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

(To be determined based on project requirements)

