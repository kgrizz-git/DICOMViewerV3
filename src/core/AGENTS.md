# Core agent guidance

Apply the root [`AGENTS.md`](../../AGENTS.md) first. This file adds guidance
for changes under `src/core/`.

## Boundaries and entry points

- Keep pure DICOM, geometry, and array work in the relevant `*_io.py`,
  `*_geometry.py`, or other non-Qt helper. Do not introduce Qt widget imports
  into those layers.
- Start with [`ARCHITECTURE.md`](../../ARCHITECTURE.md#where-to-change-what) and
  the on-demand [module tree](../../dev-docs/info/SOURCE_LAYOUT_MODULE_TREE.md)
  before tracing a workflow.
- `src/main.py` delegates application orchestration; preserve the explicit
  initialization order and route new Qt connections through
  `core/app_signal_wiring.py` rather than adding ad-hoc `connect()` calls.
- Treat privacy, DICOM loading, and export paths as safety-sensitive. Follow
  the root privacy checks and inspect the narrowest source needed before
  editing.

## Focused verification

- Core changes: `python -m pytest tests/core -q`
- Loading/decoder changes: add `tests/test_dicom_loader.py`
  `tests/test_dicom_parser.py`; run decoder fixture smoke when relevant.
- MPR changes: add `tests/test_mpr_*.py tests/core/test_mpr_*.py -q` and the
  manual MPR smoke for UI-visible behavior.
- Privacy/output changes: run the relevant `tests/test_privacy_*.py` and the
  root-required privacy hook lane.

Use the routing table in [`dev-docs/HARNESS.md`](../../dev-docs/HARNESS.md#change-routing-and-focused-verification)
to choose additional tests, then run the full suite when the change crosses
domains.
