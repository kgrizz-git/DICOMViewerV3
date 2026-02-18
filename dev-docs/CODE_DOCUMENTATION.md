# Code Documentation Index

This file lists documentation that explains how the application works or serves as user guides, and points to where in-app help content is maintained in the codebase.

---

## Documentation files (how the code works / user guides)

### Overview and user-facing

| Document | Description |
|----------|-------------|
| [README.md](../README.md) | Project overview, setup, running the application, and high-level usage. |
| [IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md](../user-docs/IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md) | Technical and user-facing documentation for the image fusion feature (PET/SPECT on CT/MR). |

### Developer and technical (dev-docs)

| Document | Description |
|----------|-------------|
| [DICOM_SUPPORT_ANALYSIS.md](DICOM_SUPPORT_ANALYSIS.md) | Analysis of DICOM support in the codebase. |
| [IMAGE_FUSION_RESEARCH.md](IMAGE_FUSION_RESEARCH.md) | Research and background for image fusion. |
| [IMAGE_FUSION_IMPLEMENTATION_PLAN.md](IMAGE_FUSION_IMPLEMENTATION_PLAN.md) | Implementation plan for image fusion. |
| [KO_PR_OVERLAYS_EXPLANATION.md](KO_PR_OVERLAYS_EXPLANATION.md) | Key Object and PR overlays in the viewer. |
| [MULTI_FRAME_DICOM_RESEARCH.md](MULTI_FRAME_DICOM_RESEARCH.md) | Multi-frame DICOM handling and research. |
| [MULTI_FRAME_FIX_SUMMARY.md](MULTI_FRAME_FIX_SUMMARY.md) | Summary of multi-frame fixes. |
| [PYLINAC_INTEGRATION_OVERVIEW.md](PYLINAC_INTEGRATION_OVERVIEW.md) | Pylinac integration overview. |
| [BUILDING_EXECUTABLES.md](BUILDING_EXECUTABLES.md) | Building executables (e.g. PyInstaller). |
| [APPIMAGE_CREATION_GUIDE.md](APPIMAGE_CREATION_GUIDE.md) | Creating AppImage builds. |
| [CODE_SIGNING_AND_NOTARIZATION.md](CODE_SIGNING_AND_NOTARIZATION.md) | Code signing and notarization. |
| [GITHUB_RELEASES_AND_VERSIONING.md](GITHUB_RELEASES_AND_VERSIONING.md) | GitHub releases and versioning. |
| [SEMANTIC_VERSIONING_GUIDE.md](SEMANTIC_VERSIONING_GUIDE.md) | Semantic versioning for the project. |
| [CROSSHAIR_AND_PATIENT_COORDINATES.md](CROSSHAIR_AND_PATIENT_COORDINATES.md) | How crosshair ROI displayed coordinates (x, y, z) and patient coordinates are determined; how `pixel_to_patient_coordinates` works for axial, sagittal, and coronal views. |

---

## In-app content (where it is written in the codebase)

Text shown in the running application for **Quick Start Guide** and **About** is defined in the following source files.

### Quick Start Guide

- **Menu:** Help → Quick Start Guide  
- **Source:** [src/gui/dialogs/quick_start_guide_dialog.py](../src/gui/dialogs/quick_start_guide_dialog.py)  
- **Content:** The full guide HTML is built in **`_get_guide_content()`** (approximately lines 119–497).  
- **Note:** The module docstring states that after changing functionality or controls, this guide should be updated in `_get_guide_content()` as needed.

### About dialog

- **Menu:** Help → About  
- **Source:** [src/gui/main_window.py](../src/gui/main_window.py)  
- **Content:** The About text is built in **`_show_about()`** (approximately lines 1619–1753). The HTML string is in the **`html_content`** variable (around lines 1664–1742).  
- **Note:** The dialog is created and shown in `_show_about()`; edits to the visible About text should be made in that method’s `html_content`.
