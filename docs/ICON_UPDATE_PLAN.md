## Icon Update Plan for Executable and About Dialog

### Overview
This plan describes the changes needed to update the application and installer icons, as well as the image used in the About dialog, to use the new `dvv6ldvv6ldvv6ld_edit-removebg-preview` assets.

### Goals
- **Update PyInstaller configuration** so that:
  - The Windows executable uses `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.ico`.
  - The macOS `.app` bundle uses `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.icns`.
- **Update the About dialog image** so that it uses:
  - `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png` instead of `resources/images/Gemini_Generated_Image_dvv6ldvv6ldvv6ld_edit-removebg-preview.png`.

### Files to Modify
- `DICOMViewerV3.spec`
  - Replace references to `resources/icons/luk40iluk40iluk4-removebg-preview.ico` with `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.ico`.
  - Replace references to `resources/icons/luk40iluk40iluk4-removebg-preview.icns` with `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.icns`.
- `src/gui/main_window.py`
  - In the `_show_about` method, update the `icon_path` construction to point to `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png` instead of the current `resources/images/Gemini_Generated_Image_dvv6ldvv6ldvv6ld_edit-removebg-preview.png`.

### Implementation Checklist
- [ ] Update Windows icon path in `DICOMViewerV3.spec`.
- [ ] Update macOS icon path in `DICOMViewerV3.spec`.
- [ ] Update About dialog image path in `src/gui/main_window.py`.
- [ ] Run linters (or at least a syntax check) on modified Python files.
- [ ] (Optional) Rebuild the executable with PyInstaller to confirm new icons are applied.

### Suggested Tests
- **Local run test (no rebuild needed):**
  - Launch the application from source (`python src/main.py` or your preferred entry command).
  - Open the **Help → About** menu item.
  - Confirm that the About dialog now shows the new MPDV icon coming from `resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.png`.
- **Build test (requires PyInstaller):**
  - Rebuild the application using:
    - `pyinstaller DICOMViewerV3.spec`
  - On **Windows**:
    - Verify that the generated `.exe` shows the new icon in Explorer and in the taskbar.
  - On **macOS**:
    - Verify that `DICOMViewerV3.app` shows the new icon in Finder and the Dock.

### Questions for You
- Do you want me to proceed with implementing this plan now?
- After code changes are made, would you like me to:
  - Run any automated checks available in this project (e.g., `pytest`, linting)?
  - Propose or run a PyInstaller build command (non-interactively) to regenerate the bundled app so you can verify the new icons visually?


