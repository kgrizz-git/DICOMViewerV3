# Changelog

All notable changes to DICOM Viewer V3 are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). See [dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md](dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md) for version increment rules.

## [Unreleased]

### Added
- (Add new changes here before a release.)

### Changed
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
