# Changelog

All notable changes to DICOM Viewer V3 are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See [dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md](dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md) for version increment rules.

## [Unreleased]

### Added
- **View menu and image context menu**: "Show/Hide Left Pane" and "Show/Hide Right Pane". When the pane is visible, toggling hides it (width 0); when hidden, toggling shows it at default 250 px. State is persisted via existing `splitter_sizes` config. View menu check state stays in sync when the user drags the splitter.

### Changed
- **Refactor (main.py)**: Main-window panel layout assembly moved to `src/gui/main_window_layout_helper.py`. `_setup_ui` now delegates to `setup_main_window_content()`; behavior unchanged (center/left/right panels, tabs, series navigator, window-slot map callbacks).
- **Refactor (main.py)**: Customization and tag-preset export/import logic moved to `src/core/customization_handlers.py`. `_on_export_customizations`, `_on_import_customizations`, `_on_export_tag_presets`, and `_on_import_tag_presets` now delegate to a `CustomizationHandlers` helper; post-import apply logic remains in main via `_apply_imported_customizations` callback. Behavior unchanged.

### Fixed
- (Add bug fixes here.)

---

## [0.1.0] - (not yet released)

### Added
- Initial changelog and single-source version (src/version.py).
- About dialog now displays application version.

### Notes
- No official release has been made yet. Version 0.1.0 marks initial development; move to 1.0.0 when the public API is stable (see dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md).

[Unreleased]: https://github.com/kgrizz-git/DICOMViewerV3/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kgrizz-git/DICOMViewerV3/releases/tag/v0.1.0
