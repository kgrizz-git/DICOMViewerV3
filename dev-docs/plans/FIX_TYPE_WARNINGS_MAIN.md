# Plan: Fix Type-Check Warnings in main.py

## Overview
This plan addresses all type-check warnings in `src/main.py` to improve code safety, maintainability, and developer experience. The fixes are grouped by category, with concrete actions for each.

## Categories & Actions

### 1. Qt Class Attribute Fixes
- **Action:** Ensure `self.app` is typed as `QApplication` where `setStyle` is called. Add type annotation or cast as needed.

### 2. Enum/Literal Usage
- **Action:** Refactor calls to use the correct Enum or restrict to allowed string literals for layout modes and similar parameters.

### 3. None Handling
- **Action:** Add explicit `if` checks or `assert` statements before accessing attributes or passing possibly-None values to functions.

### 4. Callback Attributes
- **Action:** Add missing callback attributes to class definitions with proper type annotations in the relevant classes (e.g., `DialogCoordinator`).

### 5. Optional Parameters
- **Action:** Add checks or assertions before passing possibly-None values to functions that expect non-optional types.

### 6. Specific Typing
- **Action:** Replace generic `object` types with more specific types or use runtime checks/casts after `hasattr`.

### 7. Callback Return Types
- **Action:** Ensure all callbacks return the expected type (`None`), not `bool` or other types.

### 8. Method/Attribute Access
- **Action:** Add type checks or refactor to ensure correct types before attribute access (e.g., avoid calling `.clear()` on a method or None).

## Steps
1. Review all type-check warnings in `src/main.py`.
2. Apply the above actions category by category, updating code and type annotations as needed.
3. Run type checker (e.g., pyright/mypy) to confirm all warnings are resolved.
4. Test application to ensure no regressions.
5. Document any non-trivial changes in the changelog.

## Related Files
- `src/main.py`
- `src/gui/image_viewer.py`
- `src/gui/dialogs/overlay_settings_dialog.py`
- `src/utils/config/display_config.py`
- Any class definitions for callback attributes

## Owner
- Assigned to: [Your Name/Team]

## Status
- Not started

---
*See TO_DO.md for tracking and progress.*
