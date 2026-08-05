# Annotation Clipboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create 15 unit tests in a new test file `tests/utils/test_annotation_clipboard.py` targeting the serialization, fallback, and state logic of `AnnotationClipboard`.

**Architecture:** Write standard Python `pytest` tests using dummy/mock objects to check duck-typing serialization behavior for all annotation kinds (distance/angle measurements, crosshairs, text, arrows, ROIs). Uses the `qapp` fixture for Qt support.

**Tech Stack:** Python, pytest, PySide6

## Global Constraints

*   NEVER edit files under `src/` — this task is strictly tests-only.
*   NEVER weaken, delete, `skip`, or `xfail` an existing test to get green.
*   NEVER assert something just to raise the number. Assert real, meaningful outcomes.
*   NEVER put real patient data (PHI/PII) in a test.
*   Commits must use the noreply author email: `216068303+kgrizz-git@users.noreply.github.com`.
*   Ensure all new tests pass locally under `QT_QPA_PLATFORM=offscreen`.

---

### Task 1: Create tests for `annotation_clipboard`

**Files:**
- Create: `tests/utils/test_annotation_clipboard.py`

**Interfaces:**
- Consumes: `src/utils/annotation_clipboard.py` -> `AnnotationClipboard`
- Produces: None

- [ ] **Step 1: Write a temporary failing assertion**
  Create the file `tests/utils/test_annotation_clipboard.py` with content:
  ```python
  import pytest
  from utils.annotation_clipboard import AnnotationClipboard

  @pytest.mark.qt
  def test_annotation_clipboard_fail_initially(qapp) -> None:
      clip = AnnotationClipboard()
      assert clip.has_data() is True
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_annotation_clipboard.py -v`
  Expected: FAIL with "AssertionError: assert False is True"

- [ ] **Step 3: Write complete correct implementation of tests**
  Overwrite `tests/utils/test_annotation_clipboard.py` with:
  ```python
  """Tests for AnnotationClipboard: serialization, offsets, and copy/paste states."""

  from __future__ import annotations

  import pytest
  from PySide6.QtCore import QPointF

  from utils.annotation_clipboard import AnnotationClipboard

  # Mock classes to duck-type PySide objects/items as expected by the serializer
  class MockPoint:
      def __init__(self, x: float, y: float):
          self._x = x
          self._y = y
      def x(self) -> float: return self._x
      def y(self) -> float: return self._y

  class MockColor:
      def __init__(self, r: int, g: int, b: int):
          self._r = r
          self._g = g
          self._b = b
      def red(self) -> int: return self._r
      def green(self) -> int: return self._g
      def blue(self) -> int: return self._b

  class MockFont:
      def __init__(self, pt_size: int):
          self._pt_size = pt_size
      def pointSize(self) -> int: return self._pt_size

  class MockDistanceMeasurement:
      def __init__(self, start: MockPoint, end: MockPoint, spacing: tuple[float, float]):
          self.start_point = start
          self.end_point = end
          self.pixel_spacing = spacing

  class MockAngleMeasurement:
      def __init__(self, p1: MockPoint, p2: MockPoint, p3: MockPoint, text_offset: MockPoint):
          self.p1 = p1
          self.p2 = p2
          self.p3 = p3
          self.text_offset_viewport = text_offset

  class MockCrosshair:
      def __init__(self, pos: MockPoint, val: str, x: float, y: float, z: float, text_offset: MockPoint):
          self.position = pos
          self.pixel_value_str = val
          self.x_coord = x
          self.y_coord = y
          self.z_coord = z
          self.text_offset_viewport = text_offset

  class MockTextAnnotation:
      def __init__(self, text: str, pos: MockPoint, color: MockColor, font: MockFont):
          self._text = text
          self._pos = pos
          self._color = color
          self._font = font
      def toPlainText(self) -> str: return self._text
      def pos(self) -> MockPoint: return self._pos
      def defaultTextColor(self) -> MockColor: return self._color
      def font(self) -> MockFont: return self._font

  class MockArrowAnnotation:
      def __init__(self, start: MockPoint, end: MockPoint, color: MockColor):
          self.start_point = start
          self.end_point = end
          self.color = color


  @pytest.mark.qt
  def test_clipboard_initial_state(qapp) -> None:
      clip = AnnotationClipboard()
      assert clip.clipboard_data is None
      assert clip.source_slice_key is None
      assert clip.has_data() is False


  @pytest.mark.qt
  def test_clipboard_clear(qapp) -> None:
      clip = AnnotationClipboard()
      clip.copy_annotations([], [], [], "study", "series", 1)
      assert clip.has_data() is True
      clip.clear()
      assert clip.clipboard_data is None
      assert clip.source_slice_key is None
      assert clip.has_data() is False


  @pytest.mark.qt
  def test_clipboard_copy_empty(qapp) -> None:
      clip = AnnotationClipboard()
      res = clip.copy_annotations([], [], [], "study_uid", "series_uid", 5)
      assert res["type"] == "dicom_viewer_annotations"
      assert res["version"] == "1.0"
      assert res["rois"] == []
      assert res["measurements"] == []
      assert res["crosshairs"] == []
      assert res["text_annotations"] == []
      assert res["arrow_annotations"] == []
      assert clip.source_slice_key == ("study_uid", "series_uid", 5)


  @pytest.mark.qt
  def test_paste_annotations(qapp) -> None:
      clip = AnnotationClipboard()
      assert clip.paste_annotations() is None
      res = clip.copy_annotations([], [], [], "study", "series", 1)
      assert clip.paste_annotations() == res


  @pytest.mark.qt
  def test_get_source_slice_key(qapp) -> None:
      clip = AnnotationClipboard()
      assert clip.get_source_slice_key() is None
      clip.copy_annotations([], [], [], "study_abc", "series_xyz", 99)
      assert clip.get_source_slice_key() == ("study_abc", "series_xyz", 99)


  @pytest.mark.qt
  def test_get_paste_offset_different_slice(qapp) -> None:
      clip = AnnotationClipboard()
      clip.copy_annotations([], [], [], "study", "series", 1)
      offset = clip.get_paste_offset(("study", "series", 2))
      assert offset == QPointF(0.0, 0.0)


  @pytest.mark.qt
  def test_get_paste_offset_same_slice_cut(qapp) -> None:
      clip = AnnotationClipboard()
      clip.copy_annotations([], [], [], "study", "series", 1, operation="cut")
      offset = clip.get_paste_offset(("study", "series", 1))
      assert offset == QPointF(0.0, 0.0)


  @pytest.mark.qt
  def test_get_paste_offset_same_slice_copy(qapp) -> None:
      clip = AnnotationClipboard()
      clip.copy_annotations([], [], [], "study", "series", 1, operation="copy")
      offset = clip.get_paste_offset(("study", "series", 1))
      assert offset == QPointF(10.0, 10.0)


  @pytest.mark.qt
  def test_serialize_distance_measurement(qapp) -> None:
      clip = AnnotationClipboard()
      start = MockPoint(1.0, 2.0)
      end = MockPoint(3.0, 4.0)
      m = MockDistanceMeasurement(start, end, (0.5, 0.5))
      res = clip.copy_annotations([], [m], [], "study", "series", 1)
      
      measurements = res["measurements"]
      assert len(measurements) == 1
      assert measurements[0]["measurement_kind"] == "distance"
      assert measurements[0]["start_point"] == {"x": 1.0, "y": 2.0}
      assert measurements[0]["end_point"] == {"x": 3.0, "y": 4.0}
      assert measurements[0]["pixel_spacing"] == (0.5, 0.5)


  @pytest.mark.qt
  def test_serialize_angle_measurement(qapp) -> None:
      clip = AnnotationClipboard()
      p1 = MockPoint(10.0, 10.0)
      p2 = MockPoint(20.0, 20.0)
      p3 = MockPoint(30.0, 10.0)
      text_offset = MockPoint(5.0, 5.0)
      m = MockAngleMeasurement(p1, p2, p3, text_offset)
      res = clip.copy_annotations([], [m], [], "study", "series", 1)
      
      measurements = res["measurements"]
      assert len(measurements) == 1
      assert measurements[0]["measurement_kind"] == "angle"
      assert measurements[0]["p1"] == {"x": 10.0, "y": 10.0}
      assert measurements[0]["p2"] == {"x": 20.0, "y": 20.0}
      assert measurements[0]["p3"] == {"x": 30.0, "y": 10.0}
      assert measurements[0]["text_offset_viewport"] == {"x": 5.0, "y": 5.0}


  @pytest.mark.qt
  def test_serialize_crosshairs(qapp) -> None:
      clip = AnnotationClipboard()
      pos = MockPoint(15.0, 25.0)
      text_offset = MockPoint(2.0, 2.0)
      c = MockCrosshair(pos, "120 HU", 10, 20, 30, text_offset)
      res = clip.copy_annotations([], [], [c], "study", "series", 1)
      
      crosshairs = res["crosshairs"]
      assert len(crosshairs) == 1
      assert crosshairs[0]["position"] == {"x": 15.0, "y": 25.0}
      assert crosshairs[0]["pixel_value_str"] == "120 HU"
      assert crosshairs[0]["x_coord"] == 10
      assert crosshairs[0]["y_coord"] == 20
      assert crosshairs[0]["z_coord"] == 30
      assert crosshairs[0]["text_offset_viewport"] == text_offset


  @pytest.mark.qt
  def test_serialize_text_annotations(qapp) -> None:
      clip = AnnotationClipboard()
      pos = MockPoint(100.0, 200.0)
      color = MockColor(255, 0, 0)
      font = MockFont(12)
      t = MockTextAnnotation("Hello DICOM", pos, color, font)
      res = clip.copy_annotations([], [], [], "study", "series", 1, text_annotations=[t])
      
      texts = res["text_annotations"]
      assert len(texts) == 1
      assert texts[0]["text"] == "Hello DICOM"
      assert texts[0]["position"] == {"x": 100.0, "y": 200.0}
      assert texts[0]["font_size"] == 12
      assert texts[0]["color"] == {"r": 255, "g": 0, "b": 0}


  @pytest.mark.qt
  def test_serialize_arrow_annotations(qapp) -> None:
      clip = AnnotationClipboard()
      start = MockPoint(5.0, 5.0)
      end = MockPoint(50.0, 50.0)
      color = MockColor(0, 255, 0)
      a = MockArrowAnnotation(start, end, color)
      res = clip.copy_annotations([], [], [], "study", "series", 1, arrow_annotations=[a])
      
      arrows = res["arrow_annotations"]
      assert len(arrows) == 1
      assert arrows[0]["start_point"] == {"x": 5.0, "y": 5.0}
      assert arrows[0]["end_point"] == {"x": 50.0, "y": 50.0}
      assert arrows[0]["color"] == {"r": 0, "g": 255, "b": 0}


  @pytest.mark.qt
  def test_serialize_rois_delegation(qapp, monkeypatch) -> None:
      clip = AnnotationClipboard()
      # Mock serialize_rois_for_clipboard to avoid importing complete ROI dependencies
      monkeypatch.setattr(
          "utils.annotation_clipboard.serialize_rois_for_clipboard",
          lambda rois: [{"roi_id": 999}]
      )
      res = clip.copy_annotations(["dummy_roi"], [], [], "study", "series", 1)
      assert res["rois"] == [{"roi_id": 999}]


  @pytest.mark.qt
  def test_has_data_state_transitions(qapp) -> None:
      clip = AnnotationClipboard()
      assert clip.has_data() is False
      clip.copy_annotations([], [], [], "study", "series", 1)
      assert clip.has_data() is True
      clip.clear()
      assert clip.has_data() is False
  ```

- [ ] **Step 4: Run test to verify they pass**
  Run: `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/utils/test_annotation_clipboard.py -v`
  Expected: PASS (15 tests)

- [ ] **Step 5: Run linting check**
  Run: `.venv/bin/ruff check tests/utils/test_annotation_clipboard.py`
  Expected: Clean output

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add tests/utils/test_annotation_clipboard.py
  git commit --author="kgrizz-git <216068303+kgrizz-git@users.noreply.github.com>" -m "test: add unit tests for annotation_clipboard"
  ```
