# Code Documentation Index

This file lists documentation that explains how the application works or serves as user guides, and points to where in-app help content is maintained in the codebase.

---

## Documentation files (how the code works / user guides)

### Overview and user-facing

| Document | Description |
|----------|-------------|
| [README.md](../README.md) | Project overview, install, run, and pointers to in-app help and `user-docs/`. |
| [USER_GUIDE.md](../user-docs/USER_GUIDE.md) | User guide hub (links to MPR, pylinac QA, fusion, etc.). |
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
| [BUILDING_EXECUTABLES.md](info/BUILDING_EXECUTABLES.md) | Building executables (e.g. PyInstaller). |
| [PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md](info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md) | PyInstaller bundle size estimates, per-OS measurement, baseline table. |
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
- **Content file:** [resources/help/quick_start_guide.html](../resources/help/quick_start_guide.html) — short HTML with a table of contents; **http(s)** links open in the system browser.  
- **Loader / UI:** [src/gui/dialogs/quick_start_guide_dialog.py](../src/gui/dialogs/quick_start_guide_dialog.py) — reads the HTML file, applies theme placeholders, and displays it in a `QTextBrowser`.  
- **Maintenance:** Edit the HTML when workflows or menu paths change; keep GitHub URLs in that file aligned with `main` branch paths under `user-docs/`.

### User documentation (browser)

- **Menu:** Help → Documentation (browser)…  
- **Behavior:** Opens the user guide hub on GitHub via `QDesktopServices` from [src/gui/dialog_coordinator.py](../src/gui/dialog_coordinator.py) (`open_user_documentation_in_browser`).  
- **Configurable URL:** Edit **`USER_DOCS_GITHUB_PREFIX`** in [src/utils/doc_urls.py](../src/utils/doc_urls.py) (forks / different branch). Quick Start HTML uses placeholders `{doc_*}` (including `{doc_CONFIGURATION}`) filled in [src/gui/dialogs/quick_start_guide_dialog.py](../src/gui/dialogs/quick_start_guide_dialog.py); keep placeholders in sync when adding new `user-docs/*.md` links.

### About dialog

- **Menu:** Help → About  
- **Source:** [src/gui/main_window.py](../src/gui/main_window.py)  
- **Content:** The About text is built in **`_show_about()`** (approximately lines 1619–1753). The HTML string is in the **`html_content`** variable (around lines 1664–1742).  
- **Note:** The dialog is created and shown in `_show_about()`; edits to the visible About text should be made in that method’s `html_content`.
