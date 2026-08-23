# GUI agent guidance

Apply the root [`AGENTS.md`](../../AGENTS.md) first. This file adds guidance
for changes under `src/gui/`.

## Qt ownership and navigation

- Read [`ARCHITECTURE.md`](../../ARCHITECTURE.md#where-to-change-what) before
  selecting an entry point; use the on-demand
  [module tree](../../dev-docs/info/SOURCE_LAYOUT_MODULE_TREE.md) only for
  file-level detail.
- Keep signal connections in the `DICOMViewerApp._connect_signals` family via
  `gui/app_signal_wiring.py`. Do not add `connect()` calls to unrelated
  initialization helpers.
- Preserve controller/widget ownership and avoid moving DICOM or geometry
  calculations into widgets when a core helper can own them.
- Never create a `QCoreApplication` in a test; use the session `qapp` fixture.
  Use `src/utils/debug_flags.py` for diagnostic prints and reset flags to
  `False` before commit.

## Focused verification

- General widget/dialog changes: `python -m pytest tests/gui -q`
- Main-window/signal changes: add `tests/test_main_signal_wiring.py`
  `tests/test_main_signals_view.py`
- Navigator/overlay/shortcut changes: add
  `tests/test_keyboard_overlay_shortcuts.py tests/test_series_navigator_tooltips.py`
  and smoke Space on normal and MPR panes.
- Run the relevant manual step in
  [`AGENT_SMOKE.md`](../../dev-docs/orchestration/AGENT_SMOKE.md) for
  UI-visible behavior.

Use [`dev-docs/HARNESS.md`](../../dev-docs/HARNESS.md#change-routing-and-focused-verification)
to select a narrower command when possible.
