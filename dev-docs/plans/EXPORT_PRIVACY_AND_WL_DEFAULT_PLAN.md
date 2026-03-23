# Export Privacy and Window/Level Defaults Plan

Last updated: 2026-03-22
Owner: DICOM Viewer V3
Status: Draft implementation plan

## Goal

Improve PNG/JPG export behavior by:

1. Adding anonymization support for PNG/JPG exports.
2. Making embedded window/level the default option for PNG/JPG exports.

## Scope

- Export dialog option model and UI for image exports.
- Export pipeline propagation for anonymization and window/level mode.
- Persistence of default/last-used behavior where applicable.

## Constraints and Existing Architecture Notes

- Reuse existing privacy/anonymization utilities and avoid duplicate logic.
- Preserve current behavior for DICOM export paths unless explicitly changed.
- Keep option wiring consistent through dialog coordinator and export manager flow.

## 1. PNG/JPG Export Anonymization

### Proposed Design

- Add an anonymization option for PNG/JPG in export UI.
- Reuse privacy-safe formatting and metadata suppression paths used by overlays and metadata views where possible.
- Ensure exported image overlays/text honor anonymization selection.

### Implementation Steps

1. Extend export options schema for image formats with anonymize toggle.
2. Add UI control in export dialog and default state handling.
3. Thread option through export manager/image-render path.
4. Verify file naming and optional sidecar metadata do not leak PHI.

### Validation

- Export PNG/JPG with anonymize on and off.
- Compare outputs for expected PHI suppression.
- Confirm no regression in existing privacy mode interactions.

## 2. Embedded Window/Level Default for PNG/JPG

### Proposed Design

- Set PNG/JPG export default to embedded window/level in dialog initialization.
- Preserve explicit user overrides for current session and saved preferences where already supported.

### Implementation Steps

1. Identify current default initialization path for image export window/level mode.
2. Change default to embedded WL for PNG/JPG only.
3. Keep separate defaults for other export formats if they differ.
4. Add a regression check for export option persistence.

### Validation

- Open export dialog after app launch and verify PNG/JPG default is embedded WL.
- Confirm manual change persists per current app behavior.
- Validate exported image appearance for embedded/default and manual override modes.

## Test Plan

1. Manual smoke tests for common export combinations:
   - PNG/JPG + anonymize on/off.
   - Embedded WL default, then manual override.
   - With/without overlays and annotations.
2. Add targeted tests for:
   - Option schema defaults.
   - Export pipeline option propagation.
3. Run current export-related test suite and full smoke test checklist.

## Risk and Mitigation

- Risk: Mismatch between dialog selection and pipeline behavior.
  - Mitigation: Pass a single immutable options object end-to-end and assert key fields in tests.
- Risk: Privacy leaks via overlay text or filenames.
  - Mitigation: Audit all output text sources and sanitize centrally.

## Suggested Delivery Order

1. Add anonymization option wiring end-to-end.
2. Update PNG/JPG default to embedded WL.
3. Execute export smoke tests and targeted regressions.
