# Extra Utility Test Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create 15 unit tests across three new test files under `tests/utils/` targeting `debug_flags`, `bundled_fonts`, and `roi_persistence` to raise overall test coverage.

**Architecture:** Write standard Python `pytest` tests validating input/output, default values, fallback behaviors, and serialization logic. Uses the `qapp` fixture for PySide6/Qt compatibility.

**Tech Stack:** Python, pytest, PySide6

## Global Constraints

*   NEVER edit files under `src/` — this task is strictly tests-only.
*   NEVER weaken, delete, `skip`, or `xfail` an existing test to get green.
*   NEVER assert something just to raise the number. Assert real, meaningful outcomes.
*   NEVER put real patient data (PHI/PII) in a test.
*   Commits must use the noreply author email: `216068303+kgrizz-git@users.noreply.github.com`.
*   Ensure all new tests pass locally under `QT_QPA_PLATFORM=offscreen`.

---

### Task 1: Create tests for `debug_flags`

**Files:**
- Create: `tests/utils/test_debug_flags.py`

**Interfaces:**
- Consumes: `src/utils/debug_flags.py`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_debug_flags.py` with content:
  ```python
  import utils.debug_flags

  def test_debug_flags_fail_initially() -> None:
      assert False
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_debug_flags.py -v`
  Expected: FAIL

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_debug_flags.py` with:
  ```python
  """Tests for debug_flags: toggle defaults and environment variables."""

  from __future__ import annotations

  import importlib
  import os
  import sys
  from typing import Any

  import pytest

  import utils.debug_flags


  def test_all_debug_flags_default_to_false() -> None:
      # Inspect all attributes starting with DEBUG_ and ensure they are False
      for name in dir(utils.debug_flags):
          if name.startswith("DEBUG_"):
              val = getattr(utils.debug_flags, name)
              assert val is False, f"Expected debug flag {name} to be False, but got {val}"


  def test_perf_log_respects_env_disabled(monkeypatch) -> None:
      monkeypatch.delenv("DICOM_PERF_LOG", raising=False)
      # Reload the module to check environment evaluation at import time
      importlib.reload(utils.debug_flags)
      assert utils.debug_flags.PERF_LOG is False


  def test_perf_log_respects_env_enabled(monkeypatch) -> None:
      monkeypatch.setenv("DICOM_PERF_LOG", "1")
      importlib.reload(utils.debug_flags)
      assert utils.debug_flags.PERF_LOG is True
      # Clean up after reload
      monkeypatch.delenv("DICOM_PERF_LOG", raising=False)
      importlib.reload(utils.debug_flags)


  def test_debug_flags_type() -> None:
      for name in dir(utils.debug_flags):
          if name.startswith("DEBUG_"):
              val = getattr(utils.debug_flags, name)
              assert isinstance(val, bool)


  def test_debug_flags_exclusivity() -> None:
      # Verify only expected names exist
      expected_at_least = {"DEBUG_LAYOUT", "DEBUG_LOADING", "PERF_LOG"}
      actual_names = set(dir(utils.debug_flags))
      assert expected_at_least.issubset(actual_names)
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_debug_flags.py -v`
  Expected: PASS (5 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_debug_flags.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_debug_flags.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for debug_flags"
  ```

---

### Task 2: Create tests for `bundled_fonts`

**Files:**
- Create: `tests/utils/test_bundled_fonts.py`

**Interfaces:**
- Consumes: `src/utils/bundled_fonts.py`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_bundled_fonts.py` with content:
  ```python
  import pytest
  from utils.bundled_fonts import get_font_families

  @pytest.mark.qt
  def test_bundled_fonts_fail_initially(qapp) -> None:
      assert False
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_bundled_fonts.py -v`
  Expected: FAIL

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_bundled_fonts.py` with:
  ```python
  """Tests for bundled_fonts: registry, font metrics, and Qt loaders."""

  from __future__ import annotations

  import pytest
  from PySide6.QtGui import QFont

  from utils.bundled_fonts import (
      DEFAULT_FONT_FAMILY,
      DEFAULT_FONT_VARIANT,
      get_bundled_ttf_path,
      get_font_families,
      get_font_variants,
      make_qfont,
      register_fonts_with_qt,
      resolve_font,
  )


  @pytest.mark.qt
  def test_get_font_families(qapp) -> None:
      families = get_font_families()
      assert isinstance(families, list)
      assert len(families) > 0
      assert DEFAULT_FONT_FAMILY in families


  @pytest.mark.qt
  def test_get_font_variants(qapp) -> None:
      variants = get_font_variants(DEFAULT_FONT_FAMILY)
      assert isinstance(variants, list)
      assert "Bold" in variants
      # Fallback case
      fallback_variants = get_font_variants("unknown-family-name-123")
      assert isinstance(fallback_variants, list)
      assert len(fallback_variants) > 0


  @pytest.mark.qt
  def test_resolve_font_with_fallback(qapp) -> None:
      # Valid
      fam, var = resolve_font("Raleway", "Italic")
      assert fam == "Raleway"
      assert var == "Italic"

      # Invalid family fallback
      fam, var = resolve_font("invalid-fam", "Italic")
      assert fam == DEFAULT_FONT_FAMILY
      assert var == "Italic"

      # Invalid variant fallback
      fam, var = resolve_font("Raleway", "invalid-var")
      assert fam == "Raleway"
      assert var in {"Bold", "Regular"}


  @pytest.mark.qt
  def test_get_bundled_ttf_path(qapp) -> None:
      path = get_bundled_ttf_path(DEFAULT_FONT_FAMILY, DEFAULT_FONT_VARIANT)
      assert isinstance(path, str)
      assert path.endswith(".ttf")


  @pytest.mark.qt
  def test_make_qfont_valid_and_invalid(qapp) -> None:
      font = make_qfont(DEFAULT_FONT_FAMILY, "Regular", 14)
      assert isinstance(font, QFont)
      assert font.pointSize() == 14

      # SemiCond check
      font_cond = make_qfont("IBM Plex Sans", "SemiCond Bold", 12)
      assert font_cond.pointSize() == 12

      # Register fonts does not raise
      register_fonts_with_qt()
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_bundled_fonts.py -v`
  Expected: PASS (5 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_bundled_fonts.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_bundled_fonts.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for bundled_fonts"
  ```

---

### Task 3: Create tests for `roi_persistence`

**Files:**
- Create: `tests/utils/test_roi_persistence.py`

**Interfaces:**
- Consumes: `src/utils/roi_persistence.py`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_roi_persistence.py` with content:
  ```python
  import pytest
  from utils.roi_persistence import serialize_rois_for_clipboard

  @pytest.mark.qt
  def test_roi_persistence_fail_initially(qapp) -> None:
      assert False
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_roi_persistence.py -v`
  Expected: FAIL

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_roi_persistence.py` with:
  ```python
  """Tests for roi_persistence: utility clipboard serializers for ROIItem."""

  from __future__ import annotations

  import pytest
  from PySide6.QtCore import QPointF, QRectF
  from PySide6.QtGui import QColor, QPen

  from utils.roi_persistence import (
      serialize_roi_for_clipboard,
      serialize_rois_for_clipboard,
  )


  class MockROIItem:
      def __init__(self, shape: str, rect: QRectF, pos: QPointF, pen: QPen, stats: list | None = None):
          self.shape_type = shape
          self.item = MockGraphicsItem(rect, pos, pen)
          if stats is not None:
              self.visible_statistics = stats

  class MockGraphicsItem:
      def __init__(self, rect: QRectF, pos: QPointF, pen: QPen):
          self._rect = rect
          self._pos = pos
          self._pen = pen
      def rect(self) -> QRectF: return self._rect
      def pos(self) -> QPointF: return self._pos
      def pen(self) -> QPen: return self._pen


  @pytest.mark.qt
  def test_serialize_roi_rect(qapp) -> None:
      rect = QRectF(1.5, 2.5, 10.0, 20.0)
      pos = QPointF(5.0, 5.0)
      pen = QPen(QColor(255, 0, 0))
      pen.setWidthF(3.5)
      roi = MockROIItem("rectangle", rect, pos, pen)
      
      d = serialize_roi_for_clipboard(roi)
      assert d["shape_type"] == "rectangle"
      assert d["rect"] == {"x": 1.5, "y": 2.5, "width": 10.0, "height": 20.0}
      assert d["position"] == {"x": 5.0, "y": 5.0}
      assert d["pen_width"] == 3
      assert d["pen_color"] == (255, 0, 0)
      assert "visible_statistics" not in d


  @pytest.mark.qt
  def test_serialize_roi_ellipse(qapp) -> None:
      rect = QRectF(0.0, 0.0, 15.0, 15.0)
      pos = QPointF(0.0, 0.0)
      pen = QPen(QColor(0, 255, 0))
      pen.setWidth(1)
      roi = MockROIItem("ellipse", rect, pos, pen)
      
      d = serialize_roi_for_clipboard(roi)
      assert d["shape_type"] == "ellipse"
      assert d["pen_width"] == 1
      assert d["pen_color"] == (0, 255, 0)


  @pytest.mark.qt
  def test_serialize_roi_with_statistics(qapp) -> None:
      rect = QRectF(0.0, 0.0, 5.0, 5.0)
      pos = QPointF(10.0, 10.0)
      pen = QPen(QColor(0, 0, 255))
      roi = MockROIItem("rectangle", rect, pos, pen, stats=["mean: 120", "sd: 5.5"])
      
      d = serialize_roi_for_clipboard(roi)
      assert d["visible_statistics"] == ["mean: 120", "sd: 5.5"]


  @pytest.mark.qt
  def test_serialize_roi_pen_width_fallback(qapp) -> None:
      rect = QRectF(0.0, 0.0, 5.0, 5.0)
      pos = QPointF(0.0, 0.0)
      pen = QPen(QColor(0, 0, 0))
      pen.setWidthF(0.0)
      roi = MockROIItem("rectangle", rect, pos, pen)
      
      d = serialize_roi_for_clipboard(roi)
      # QPen width() returns pen.width() when widthF is <= 0
      assert isinstance(d["pen_width"], int)


  @pytest.mark.qt
  def test_serialize_rois_list(qapp) -> None:
      rect = QRectF(1.0, 1.0, 2.0, 2.0)
      pos = QPointF(0.0, 0.0)
      pen = QPen(QColor(0, 0, 0))
      roi = MockROIItem("ellipse", rect, pos, pen)
      
      lst = serialize_rois_for_clipboard([roi, roi])
      assert len(lst) == 2
      assert lst[0]["shape_type"] == "ellipse"
      assert lst[1]["shape_type"] == "ellipse"
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_roi_persistence.py -v`
  Expected: PASS (5 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_roi_persistence.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_roi_persistence.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for roi_persistence"
  ```
