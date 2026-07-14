# Plan: Fix Type-Check Warnings in main.py

## Overview
This plan addresses Pyright-reported type issues centered on `src/main.py` to improve code safety, maintainability, and developer experience. Fixes are grouped by category, with concrete actions for each.

## Scope
- **Primary target:** Diagnostics reported for `src/main.py` (and resolved there when possible).
- **Related modules:** Some fixes may live in types or definitions used by `main.py` (see Related Files). Those edits are in scope when they are the correct place to fix a `main.py` warning.
- **Definition of done:** Zero Pyright diagnostics attributable to `src/main.py` for the agreed severity set (typically errors + warnings used in CI or editor), unless explicitly suppressed with a short comment and rationale.

## Toolchain & baseline
- **Type checker:** Use **Pyright** (repo root `pyrightconfig.json` includes `src`, `tests`, `scripts`).
- **Before changes:** With the project venv activated, run `pyright` from the repo root and note the count (and optionally save the output). That snapshot is the baseline.
- **Venv path:** `pyrightconfig.json` sets `"venv": "venv"`. If your environment folder is `.venv` or another name, align the config or use a local venv named `venv` so CLI results match the IDE.

## Policy (applies across categories)
- Prefer **`is None` / `isinstance` / early returns** so types narrow naturally; use `typing.cast()` only when stubs are wrong or an invariant cannot be expressed otherwise.
- Triage **high-signal rules first** (e.g. optional member access, wrong argument types) before broad refinements of `object` or cosmetic annotations.

## Categories & Actions

### 1. Qt class attribute fixes
- **Action:** Ensure `self.app` and similar are typed as the real Qt types (e.g. `QApplication`) where methods like `setStyle` are used. Annotate on the class, narrow with guards, or use a targeted cast only if needed.

### 2. Enum / Literal usage
- **Action:** Refactor calls to use the correct `Enum` or restrict to allowed string `Literal[...]` types for layout modes and similar parameters so callers and config stay aligned.

### 3. Optionals, `None`, and narrowing
- **Unset attributes:** Add explicit checks or assertions before access when an attribute may be missing at runtime.
- **Optional parameters:** Before passing `T | None` into APIs expecting `T`, narrow (guard, assert, or default) so the type checker and runtime agree.
- **Note:** Sections on “None handling” and “optional parameters” are the same workflow (narrowing); treat them as one category when implementing.

### 4. Callback attributes
- **Action:** Declare callbacks on the owning class with proper types (e.g. coordinator/helper classes that currently use dynamic attributes). Prefer explicit attributes over untyped `setattr` patterns where feasible.

### 5. Specific typing (`object`, `Any`, broad containers)
- **Action:** Replace overly generic types with concrete types, or use runtime checks (and then narrow) after `hasattr`/`getattr` when the real type varies.

### 6. Callable / slot return types (Qt-aware)
- **Action:** Align **declared** types (`Callable`, `@Slot`, signal connections) with **actual** behavior. Some Qt hooks correctly return `bool` (e.g. event filters); others are `None`. Fix mismatches by widening the annotation, changing the implementation, or using the appropriate slot overload — do not blindly force every callback to `None`.

### 7. Method / attribute access
- **Action:** Ensure the receiver is the intended type before calling methods (e.g. avoid invoking `.clear()` on `None` or on a function object mistaken for a collection).

## Steps
1. Activate the project venv, run `pyright` at repo root, and record baseline diagnostics for `src/main.py`.
2. Work category by category (priority: high-signal optional/argument issues first), updating `main.py` and related definitions as needed.
3. Re-run `pyright` until the goal in **Scope** is met.
4. **Regression checks:** Run `python tests/run_tests.py` or `python -m pytest tests/ -v`; smoke-test app launch and a short UI path (open data, layout change) if signal/slot or viewer wiring changed.
5. Document non-trivial behavior or typing contract changes in `CHANGELOG.md` if user-visible or maintainer-relevant.

## Related Files
- `src/main.py`
- `src/gui/image_viewer.py`
- `src/gui/dialogs/overlay_settings_dialog.py`
- `src/utils/config/display_config.py`
- Any class definitions that should own callback types instead of ad hoc attributes
- `pyrightconfig.json` (only if venv path or include scope must match local setup)

## Owner
- Assigned to: [Your Name/Team]

## Status
- Not started

---
*See `dev-docs/TO_DO.md` for tracking and progress.*
