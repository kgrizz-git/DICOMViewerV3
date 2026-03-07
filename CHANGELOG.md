# Changelog

All notable changes to DICOM Viewer V3 are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See [dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md](dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md) for version increment rules.

## [Unreleased]

### Added
- **Multi-study loading (Phase 6)**: File menu item renamed from "Close" to "Close All" with status tip. After additive load (Open Files, Open Folder, Recents, drag-and-drop), status bar shows: "Loaded {n} new series across {m} studies", "Added {k} slice(s) to existing series", or "No new files — all {total} already loaded". When any files were skipped as duplicates, a toast message "{n} file(s) already loaded and skipped" appears at bottom-center and auto-dismisses after 3 seconds (implemented via `MainWindow.show_toast_message()`).
- **Export (anonymized DICOM)**: When "Anonymize patient information" is enabled, the export folder structure (Patient ID / Study Date - Study Description / Series Number - Series Description) is now built from anonymized tag values so folder paths do not leak patient data.
- **SliceDisplayManager.clear_display_state()**: Clears current_dataset, current_studies, and UIDs so no stale cached state is used after close/open.
- **View menu and image context menu**: "Show/Hide Left Pane" and "Show/Hide Right Pane". When the pane is visible, toggling hides it (width 0); when hidden, toggling shows it at default 250 px. State is persisted via existing `splitter_sizes` config. View menu check state stays in sync when the user drags the splitter.
- **View menu and context menu**: "Show/Hide Series Navigator" added to the View menu (checkable) and to the image right-click context menu (immediately after "Show/Hide Right Pane"). Toggles the series navigator bar; View menu check state is kept in sync when toggling.

### Changed
- **Privacy**: Crosshair managers are no longer updated when toggling privacy mode; crosshairs always show full content and do not hide anything in privacy mode, so the call was unnecessary and could crash when Qt objects were already deleted.
- **Clear/close**: When closing files or opening new folder/files, all subwindows' `slice_display_manager` state (current_dataset, current_studies, UIDs, slice index) is now cleared via `clear_display_state()`, preventing stale redisplay (e.g. series reappearing in another window on privacy toggle).
- **Refactor (main.py)**: Privacy propagation and overlay refresh after privacy change moved to `src/core/privacy_controller.py`. `_on_privacy_view_toggled` and `_refresh_overlays_after_privacy_change` now delegate to `PrivacyController`; behavior unchanged.
- **Refactor (main.py)**: Main-window panel layout assembly moved to `src/gui/main_window_layout_helper.py`. `_setup_ui` now delegates to `setup_main_window_content()`; behavior unchanged (center/left/right panels, tabs, series navigator, window-slot map callbacks).
- **Refactor (main.py)**: Customization and tag-preset export/import logic moved to `src/core/customization_handlers.py`. `_on_export_customizations`, `_on_import_customizations`, `_on_export_tag_presets`, and `_on_import_tag_presets` now delegate to a `CustomizationHandlers` helper; post-import apply logic remains in main via `_apply_imported_customizations` callback. Behavior unchanged.

### Fixed
- **Privacy + crosshair**: Toggling privacy after drawing a crosshair and then loading a different exam no longer raises `RuntimeError: Internal C++ object (DraggableCrosshairText) already deleted`. CrosshairItem.update_privacy_mode now catches RuntimeError when the Qt text item was already deleted; PrivacyController also catches RuntimeError when calling crosshair_manager.set_privacy_mode.
- **Privacy + reload study**: Toggling privacy after loading a different study and then reloading the first study no longer redisplays stale series in non-focused windows. PrivacyController.refresh_overlays now only refreshes subwindows that have an entry in subwindow_data (i.e. have loaded data), so windows that were not updated when the other study was loaded are skipped.

---

## [0.1.0] - (not yet released)

### Added
- Initial changelog and single-source version (src/version.py).
- About dialog now displays application version.

### Notes
- No official release has been made yet. Version 0.1.0 marks initial development; move to 1.0.0 when the public API is stable (see dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md).

[Unreleased]: https://github.com/kgrizz-git/DICOMViewerV3/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kgrizz-git/DICOMViewerV3/releases/tag/v0.1.0
