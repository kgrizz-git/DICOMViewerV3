# Test Coverage Boost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create 15 unit tests across three new test files under `tests/utils/` targeting `accent_presets`, `dicom_vr_helpers`, and `navigation_slider_prefs` in order to raise overall test coverage.

**Architecture:** Write standard Python `pytest` tests validating input/output and fallback behaviors of utility functions without any Qt or user-interface dependencies.

**Tech Stack:** Python, pytest

## Global Constraints

*   NEVER edit files under `src/` — this task is strictly tests-only.
*   NEVER weaken, delete, `skip`, or `xfail` an existing test to get green.
*   NEVER assert something just to raise the number. Assert real, meaningful outcomes.
*   NEVER put real patient data (PHI/PII) in a test.
*   Commits must use the noreply author email: `216068303+kgrizz-git@users.noreply.github.com`.
*   Ensure all new tests pass locally under `QT_QPA_PLATFORM=offscreen`.

---

### Task 1: Create tests for `accent_presets`

**Files:**
- Create: `tests/utils/test_accent_presets.py`

**Interfaces:**
- Consumes: `src/utils/accent_presets.py` -> `get_preset(accent_id: str) -> AccentPreset`, `ACCENT_PRESETS: dict[str, AccentPreset]`, `DEFAULT_ACCENT_ID: str`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_accent_presets.py` with content:
  ```python
  from utils.accent_presets import get_preset

  def test_accent_presets_fail_initially() -> None:
      assert get_preset("steel-blue").label == "Wrong Label"
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_accent_presets.py -v`
  Expected: FAIL with "AssertionError: assert 'Steel Blue' == 'Wrong Label'"

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_accent_presets.py` with:
  ```python
  """Tests for accent_presets: color mapping presets and fallbacks."""

  from __future__ import annotations

  from utils.accent_presets import (
      ACCENT_PRESETS,
      AccentPreset,
      get_preset,
  )


  def test_accent_presets_contain_expected_keys() -> None:
      expected_keys = {"steel-blue", "violet", "navy", "garnet"}
      assert set(ACCENT_PRESETS.keys()) == expected_keys


  def test_get_preset_returns_correct_preset_for_valid_ids() -> None:
      preset = get_preset("violet")
      assert isinstance(preset, AccentPreset)
      assert preset.label == "Violet"
      assert preset.accent == "#7c4dff"


  def test_get_preset_fallback_for_invalid_id() -> None:
      preset = get_preset("invalid-preset-id")
      assert isinstance(preset, AccentPreset)
      assert preset.label == "Steel Blue"
      assert preset.accent == "#4285da"


  def test_get_preset_fallback_for_none_or_empty_string() -> None:
      preset_none = get_preset(None)  # type: ignore[arg-type]
      preset_empty = get_preset("")
      assert preset_none.label == "Steel Blue"
      assert preset_empty.label == "Steel Blue"


  def test_accent_preset_attributes() -> None:
      for preset_id, preset in ACCENT_PRESETS.items():
          assert isinstance(preset, AccentPreset)
          assert len(preset.label) > 0
          assert preset.accent.startswith("#")
          assert preset.accent_light.startswith("#")
          assert preset.accent_dark.startswith("#")
          assert preset.accent_soft.startswith("#")
          assert preset.accent_muted.startswith("#")
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_accent_presets.py -v`
  Expected: PASS (5 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_accent_presets.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_accent_presets.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for accent_presets"
  ```

---

### Task 2: Create tests for `dicom_vr_helpers`

**Files:**
- Create: `tests/utils/test_dicom_vr_helpers.py`

**Interfaces:**
- Consumes: `src/utils/dicom_vr_helpers.py` -> `is_text_vr(vr: str) -> bool`, `is_date_vr(vr: str) -> bool`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_dicom_vr_helpers.py` with content:
  ```python
  from utils.dicom_vr_helpers import is_text_vr

  def test_dicom_vr_helpers_fail_initially() -> None:
      assert is_text_vr("LO") is False
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_dicom_vr_helpers.py -v`
  Expected: FAIL with "AssertionError: assert True is False"

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_dicom_vr_helpers.py` with:
  ```python
  """Tests for dicom_vr_helpers: DICOM Value Representation classifiers."""

  from __future__ import annotations

  from utils.dicom_vr_helpers import is_date_vr, is_text_vr


  def test_is_text_vr_returns_true_for_text_vrs() -> None:
      text_vrs = ("LO", "PN", "SH", "ST", "LT", "UT", "CS", "IS", "DS")
      for vr in text_vrs:
          assert is_text_vr(vr) is True


  def test_is_text_vr_returns_false_for_non_text_vrs() -> None:
      non_text_vrs = ("OB", "OW", "FL", "FD", "DA", "TM", "DT", "UI", "SQ")
      for vr in non_text_vrs:
          assert is_text_vr(vr) is False


  def test_is_date_vr_returns_true_for_date_vrs() -> None:
      date_vrs = ("DA", "TM", "DT")
      for vr in date_vrs:
          assert is_date_vr(vr) is True


  def test_is_date_vr_returns_false_for_non_date_vrs() -> None:
      non_date_vrs = ("LO", "PN", "SH", "OB", "OW", "FL", "FD", "UI", "SQ")
      for vr in non_date_vrs:
          assert is_date_vr(vr) is False


  def test_vr_helpers_case_sensitivity() -> None:
      # DICOM VRs must be strictly uppercase
      assert is_text_vr("lo") is False
      assert is_text_vr("pn") is False
      assert is_date_vr("da") is False
      assert is_date_vr("tm") is False
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_dicom_vr_helpers.py -v`
  Expected: PASS (5 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_dicom_vr_helpers.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_dicom_vr_helpers.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for dicom_vr_helpers"
  ```

---

### Task 3: Create tests for `navigation_slider_prefs`

**Files:**
- Create: `tests/utils/test_navigation_slider_prefs.py`

**Interfaces:**
- Consumes: `src/utils/navigation_slider_prefs.py` -> `normalize_slider_placement(value: Any) -> str`, `normalize_slider_direction(value: Any) -> str`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_navigation_slider_prefs.py` with content:
  ```python
  from utils.navigation_slider_prefs import normalize_slider_placement

  def test_navigation_slider_prefs_fail_initially() -> None:
      assert normalize_slider_placement("bottom") == "invalid"
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_navigation_slider_prefs.py -v`
  Expected: FAIL with "AssertionError: assert 'bottom' == 'invalid'"

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_navigation_slider_prefs.py` with:
  ```python
  """Tests for navigation_slider_prefs: normalizers for placement and directions."""

  from __future__ import annotations

  from utils.navigation_slider_prefs import (
      normalize_slider_direction,
      normalize_slider_placement,
  )


  def test_normalize_slider_placement_valid() -> None:
      for val in ("bottom", "top", "left", "right"):
          assert normalize_slider_placement(val) == val


  def test_normalize_slider_placement_normalization() -> None:
      assert normalize_slider_placement("  Bottom  ") == "bottom"
      assert normalize_slider_placement("TOP") == "top"
      assert normalize_slider_placement("lEfT") == "left"


  def test_normalize_slider_placement_invalid_fallback() -> None:
      assert normalize_slider_placement("invalid") == "bottom"
      assert normalize_slider_placement("") == "bottom"
      assert normalize_slider_placement(None) == "bottom"


  def test_normalize_slider_direction_valid() -> None:
      for val in ("first_at_start", "first_at_end"):
          assert normalize_slider_direction(val) == val


  def test_normalize_slider_direction_normalization_and_fallback() -> None:
      assert normalize_slider_direction("  First_At_Start  ") == "first_at_start"
      assert normalize_slider_direction("FIRST_AT_END") == "first_at_end"
      assert normalize_slider_direction("invalid") == "first_at_start"
      assert normalize_slider_direction("") == "first_at_start"
      assert normalize_slider_direction(None) == "first_at_start"
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_navigation_slider_prefs.py -v`
  Expected: PASS (5 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_navigation_slider_prefs.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_navigation_slider_prefs.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for navigation_slider_prefs"
  ```
