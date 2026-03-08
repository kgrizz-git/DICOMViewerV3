# Changelog

All notable changes to DICOM Viewer V3 are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See [dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md](dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md) for version increment rules.

## [Unreleased]

### Added
- **Quick Window/Level (Q)**: Context menu item "Quick Window/Level (Q)" and keyboard shortcut **Q** open a small dialog to enter window center and width (Tab between fields, Enter or OK to apply). Applies to the focused subwindow; values and ranges match the right-panel WL controls (rescaled or raw).
- **Window/level debug logging**: `DEBUG_WL` in `utils/debug_flags.py` (default `False`). Set to `True` to trace default WL when switching series: at each display_slice it logs study/series, modality, is_new_study_series, is_same_series, rescale slope/intercept, use_rescaled_values; whether the series was found in current_studies; embedded WL source (first preset vs get_window_level_from_dataset) and raw wc/ww/is_rescaled; any rescaled↔raw conversion; stored_wc/stored_ww; fallback path (when series not in current_studies) with same detail; and final window_center/window_width/apply_rescale passed to dataset_to_image. Use when investigating embedded WL not applied correctly across studies.
- **Series navigation debug logging**: All `[DEBUG-NAV]` and "Series navigation:" print statements are gated behind a new `DEBUG_NAV` flag in `utils/debug_flags.py`. Default is `False`; set to `True` to restore verbose series-navigation key/request/lock tracing in `series_navigator`, `image_viewer`, and `file_series_loading_coordinator`.
- **Status bar (processed vs loaded)**: After loading, the status bar shows "X files processed - Y studies, Z series, A files loaded from {source}" with optional " (B non-DICOM and C duplicate files not loaded)" when applicable, so counts stay accurate when canceling, when some files are non-DICOM, or when duplicates are skipped.
- **Extension skip for non-DICOM files**: Files with known non-DICOM extensions (e.g. pdf, png, jpg, doc, docx, py, md, zip, mp4) are no longer attempted as DICOM. They are excluded from "files processed" and from failed/duplicate counts. Open Files and drag-and-drop file lists are filtered before loading; folder load excludes them during directory scan. If all selected files are skipped, a short warning is shown.
- **Multi-study loading (Phase 6)**: File menu item renamed from "Close" to "Close All" with status tip. After additive load (Open Files, Open Folder, Recents, drag-and-drop), status bar shows: "Loaded {n} new series across {m} studies", "Added {k} slice(s) to existing series", or "No new files — all {total} already loaded". When any files were skipped as duplicates, a toast message "{n} file(s) already loaded and skipped" appears at bottom-center and auto-dismisses after 3 seconds (implemented via `MainWindow.show_toast_message()`).
- **Export (anonymized DICOM)**: When "Anonymize patient information" is enabled, the export folder structure (Patient ID / Study Date - Study Description / Series Number - Series Description) is now built from anonymized tag values so folder paths do not leak patient data.
- **SliceDisplayManager.clear_display_state()**: Clears current_dataset, current_studies, and UIDs so no stale cached state is used after close/open.
- **View menu and image context menu**: "Show/Hide Left Pane" and "Show/Hide Right Pane". When the pane is visible, toggling hides it (width 0); when hidden, toggling shows it at default 250 px. State is persisted via existing `splitter_sizes` config. View menu check state stays in sync when the user drags the splitter.
- **View menu and context menu**: "Show/Hide Series Navigator" added to the View menu (checkable) and to the image right-click context menu (immediately after "Show/Hide Right Pane"). Toggles the series navigator bar; View menu check state is kept in sync when toggling.

### Changed
- **Series navigator**: Series number labels (e.g. "S01") in the navigator thumbnails use a smaller font (9 pt instead of 12 pt).
- **Status bar**: Removed the "X files processed - " prefix. Status line is now "{studies}, {series}, {files} loaded from {source}". When any files were skipped, the suffix is "(Y non-DICOM, Z duplicates skipped)" (or only one of Y/Z when applicable); Y combines extension-skipped and failed-to-load non-DICOM counts.
- **Privacy**: Crosshair managers are no longer updated when toggling privacy mode; crosshairs always show full content and do not hide anything in privacy mode, so the call was unnecessary and could crash when Qt objects were already deleted.
- **Clear/close**: When closing files or opening new folder/files, all subwindows' `slice_display_manager` state (current_dataset, current_studies, UIDs, slice index) is now cleared via `clear_display_state()`, preventing stale redisplay (e.g. series reappearing in another window on privacy toggle).
- **Refactor (main.py)**: Privacy propagation and overlay refresh after privacy change moved to `src/core/privacy_controller.py`. `_on_privacy_view_toggled` and `_refresh_overlays_after_privacy_change` now delegate to `PrivacyController`; behavior unchanged.
- **Refactor (main.py)**: Main-window panel layout assembly moved to `src/gui/main_window_layout_helper.py`. `_setup_ui` now delegates to `setup_main_window_content()`; behavior unchanged (center/left/right panels, tabs, series navigator, window-slot map callbacks).
- **Refactor (main.py)**: Customization and tag-preset export/import logic moved to `src/core/customization_handlers.py`. `_on_export_customizations`, `_on_import_customizations`, `_on_export_tag_presets`, and `_on_import_tag_presets` now delegate to a `CustomizationHandlers` helper; post-import apply logic remains in main via `_apply_imported_customizations` callback. Behavior unchanged.

### Fixed
- **Default window/level overwritten after series switch**: When switching from a series with large WL (e.g. PET 35121/63217) to one with small embedded WL (e.g. CT 30/100), the WL controls were updated after `set_ranges()`. Changing the spinbox range caused Qt to clamp the old values and emit `valueChanged`, so `handle_window_changed` overwrote view state with the clamped values (e.g. 235/63217). Subsequent `display_slice` (same series) then read those wrong values. The fix is to set the WL control values (and unit) **before** calling `set_ranges()` for a new series, so the spinboxes already hold the correct values and no clamp/emit occurs.
- **Default window/level when switching series across studies**: When switching to a series from a different study, if the series lookup in `current_studies` did not yield window/level (e.g. key mismatch or missing entry), the image could be built without applying the new series’ embedded WL and the WL control ranges could stay from the previous series. A fallback now computes embedded window/level from the dataset being loaded (presets or single tags, with correct rescaled/raw conversion), sets the series pixel range from that slice, and applies the values so both the image and the right-panel controls use the correct default for the new series. Additionally, the image conversion now always receives explicit window_center/window_width whenever we have them (not only when is_same_series), so the image and controls use the same values and rescale state.
- **First series auto-loaded**: The series auto-displayed when opening a batch is chosen using the same logic as the series navigator: first study in navigator order (dict iteration), then series with lowest SeriesNumber in that study. So the auto-loaded series is always from the first study shown in the navigator; both additive and replace load paths use this logic.
- **Toast**: Toast message now stays visible longer (default 5 s), uses a larger font (14px) and padding, and is positioned higher (100px from bottom) for better visibility.
- **Fit-to-view on cancel/partial load**: When loading is cancelled but some files were already loaded, a deferred fit-to-view is now applied to the subwindow that received the loaded series so the image is correctly fitted after layout is stable.
- **Fit-to-view for new series**: Additive load schedules a deferred fit-to-view on the target subwindow's viewer so fit is applied reliably for newly loaded series (including when the new series goes to a non-focused subwindow).
- **Window/level wrong subwindow**: When a new series is added to a non-focused subwindow, the global window/level controls and metadata panel are no longer updated with the new series' values; only the subwindow that received the new series is updated, so the focused subwindow's W/L is not overwritten.
- **Status bar**: Corrected typo "studyies" to "study" / "studies" in the final load status message. Status bar now shows only the current batch’s study/series/file counts (from `MergeResult`), so counts are accurate when loading is cancelled (partial load) or when duplicate files are skipped.
- **Progress dialog on cancel**: When loading is cancelled before all files are loaded, the progress dialog and status bar now show the number of files actually loaded (e.g. 6) instead of the batch total (e.g. 11). Loader final progress uses `len(loaded_files)`; handler uses the callback’s current (actual) count for the "Loaded X file(s). Organizing..." message.
- **Privacy + crosshair**: Toggling privacy after drawing a crosshair and then loading a different exam no longer raises `RuntimeError: Internal C++ object (DraggableCrosshairText) already deleted`. CrosshairItem.update_privacy_mode now catches RuntimeError when the Qt text item was already deleted; PrivacyController also catches RuntimeError when calling crosshair_manager.set_privacy_mode.
- **Privacy + reload study**: Toggling privacy after loading a different study and then reloading the first study no longer redisplays stale series in non-focused windows. PrivacyController.refresh_overlays now only refreshes subwindows that have an entry in subwindow_data (i.e. have loaded data), so windows that were not updated when the other study was loaded are skipped.

---

## [0.1.1] - (not yet released)

### Fixed
- **Toast**: Longer visibility (5 s default), larger font (14px) and padding, position moved up (100px from bottom).
- **Fit-to-view**: Deferred fit applied to target subwindow after additive load (including cancel-with-partial-load).
- **Window/level**: New series in non-focused subwindow no longer overwrites global W/L controls or focused subwindow.

---

## [0.1.0] - (not yet released)

### Added
- Initial changelog and single-source version (src/version.py).
- About dialog now displays application version.

### Notes
- No official release has been made yet. Version 0.1.0 marks initial development; move to 1.0.0 when the public API is stable (see dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md).

[Unreleased]: https://github.com/kgrizz-git/DICOMViewerV3/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/kgrizz-git/DICOMViewerV3/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kgrizz-git/DICOMViewerV3/releases/tag/v0.1.0
