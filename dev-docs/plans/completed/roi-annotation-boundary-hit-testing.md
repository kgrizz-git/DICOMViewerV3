# Boundary-Only Hit Testing for ROIs and Annotations

**Goal:** Tighten hit areas so that selection responds to the **boundary** (outline) of shapes—with a small tolerance—rather than the entire interior. This allows, for example, drawing an ellipse inside an existing ellipse without the inner click being captured by the outer ROI.

**Related TO_DO:** dev-docs/TO_DO.md item: *"tighten 'hitboxes' or whatever for annotations and ROIs - eg, for a large ellipse ROI, would be better if only the ellipse boundary (with some tolerance) was hitbox, not entire interior as well"*.

---

## 1. Current Behavior

- **ROIs (ellipse, rectangle):** Implemented as `ROIGraphicsEllipseItem` and `ROIGraphicsRectItem` in `src/tools/roi_manager.py`. They do **not** override `shape()`, so Qt uses the default: the **filled** shape (full ellipse or rectangle). Any click inside the shape selects/moves the ROI.
- **Measurements:** Already use boundary-only hit testing. In `src/tools/measurement_items.py`, `MeasurementItem.shape()` returns a **stroked line** (line path + `QPainterPathStroker` with width 4), so only the line (and a small margin) is clickable.
- **Annotations (arrow, text, DICOM overlays):** Arrow and text are groups or text items; DICOM overlay shapes (ellipse, polygon, etc.) in `annotation_manager.py` use standard Qt shape items. None currently override `shape()` for boundary-only hit testing.

---

## 2. Qt Concepts

- **`shape()`:** Used for hit testing and collision detection. If not overridden, `QGraphicsItem` uses `boundingRect()` to build a rectangular shape; shape items like ellipse/rect typically use the full geometric shape (filled).
- **`boundingRect()`:** Used for drawing/culling. Must always fully contain the result of `shape()`; otherwise rendering and hit-test can be wrong.
- **`QPainterPathStroker`:** Takes a path (e.g. ellipse outline, rect outline, line) and produces a new path representing the “stroke” with a given width. That stroked path is ideal for “boundary plus tolerance” hit testing.

So the approach: **override `shape()`** to return a **stroked outline** of the shape (ellipse, rect, or line), with a tolerance width (e.g. pen width + a few units). Keep `boundingRect()` unchanged so it still encloses the whole shape for drawing.

---

## 3. Implementation Plan

### 3.1 ROIs (priority)

**Files:** `src/tools/roi_manager.py`

**ROIGraphicsEllipseItem**

- Override `shape()`:
  - Build a path with `QPainterPath.addEllipse(self.rect())` (ellipse outline only).
  - Use `QPainterPathStroker` with a stroke width = hit tolerance (e.g. `max(pen width, 4)` in scene units, or a constant like 6–8 for a comfortable click margin).
  - Return `stroker.createStroke(path)`.
- Leave `boundingRect()` as the default (based on `rect()`); it already contains the full ellipse, so it will contain the stroked outline.

**ROIGraphicsRectItem**

- Same idea: override `shape()` with a path from `QPainterPath.addRect(self.rect())`, then stroke it with the same kind of tolerance and return the stroked path.
- Leave `boundingRect()` unchanged.

**Tolerance**

- Use a constant (e.g. 6–8 scene units) or derive from the item’s pen width so that the hit area is at least as wide as the visible stroke. Optional: add a config key (e.g. in `roi_config`) for “boundary hit tolerance” later.

**Reference**

- Follow the same pattern as `MeasurementItem.shape()` in `src/tools/measurement_items.py` (line path → stroker → return stroked path). For ellipse/rect, the path is the outline only (addEllipse/addRect), so the stroked result is “boundary + tolerance”.

### 3.2 Annotations (optional / later)

**Arrow annotations** (`src/tools/arrow_annotation_tool.py`)

- `ArrowAnnotationItem` is a `QGraphicsItemGroup` (line + arrowhead). To make hit area “boundary-only”:
  - Override `shape()` to return the union of:
    - A stroked path for the line (like `MeasurementItem`: line segment → `QPainterPathStroker`).
    - A small path or rect for the arrowhead so the tip remains clickable.
  - Keep `boundingRect()` enclosing the full arrow.

**Text annotations**

- Typically keep hit testing as the text bounding box so the whole label is clickable. No change unless we explicitly want “only visible text pixels” (much more complex and rarely needed).

**DICOM overlay shapes** (`src/tools/annotation_manager.py`)

- If those shapes (ellipse, polygon) are selectable and would benefit from boundary-only hit testing, apply the same pattern: build path from the shape outline, stroke it with a tolerance, return from `shape()`. This may require custom item subclasses or a small wrapper that overrides `shape()`.

---

## 4. Code Hints (ROI)

**Imports** (in `roi_manager.py`): add `QPainterPath` and `QPainterPathStroker` from `PySide6.QtGui` (already have `QPen`, `QColor` there).

**ROIGraphicsEllipseItem.shape():**

```python
def shape(self) -> QPainterPath:
    """Return shape for hit testing - ellipse boundary plus tolerance, not filled interior."""
    path = QPainterPath()
    path.addEllipse(self.rect())
    tolerance = 6.0  # scene units; or max(self.pen().widthF(), 4.0)
    pen = QPen(Qt.PenStyle.SolidLine)
    pen.setWidthF(tolerance)
    stroker = QPainterPathStroker(pen)
    return stroker.createStroke(path)
```

**ROIGraphicsRectItem.shape():**

```python
def shape(self) -> QPainterPath:
    """Return shape for hit testing - rectangle boundary plus tolerance, not filled interior."""
    path = QPainterPath()
    path.addRect(self.rect())
    tolerance = 6.0
    pen = QPen(Qt.PenStyle.SolidLine)
    pen.setWidthF(tolerance)
    stroker = QPainterPathStroker(pen)
    return stroker.createStroke(path)
```

If the item’s pen width is available and you want the hit area to match the visible stroke, use e.g. `tolerance = max(self.pen().widthF(), 4.0)` (with a minimum of 4 so the boundary remains clickable at thin pens).

---

## 5. Testing

- **ROI ellipse:** Create a large ellipse, then draw a smaller ellipse inside. Clicks inside the inner ellipse should **not** select the outer ROI; clicks on or near the outer ellipse boundary should select it.
- **ROI rectangle:** Same idea with nested rectangles.
- **Drag:** Ensure selecting on the boundary still allows normal drag-to-move.
- **Regression:** Ensure ROIs that are already in use (load/save, statistics, list panel selection) still work; only hit-test behavior should change, not data or painting.

---

## 6. Summary

| Item                         | Current hit area   | Change                                      |
|-----------------------------|--------------------|---------------------------------------------|
| ROI ellipse                 | Full interior      | Override `shape()` → stroked ellipse only   |
| ROI rectangle               | Full interior      | Override `shape()` → stroked rect only      |
| Measurement line            | Already stroked    | No change                                   |
| Arrow annotation            | Full group bounds  | Optional: stroked line + arrowhead area     |
| Text annotation             | Text bbox          | Optional: keep as-is                        |
| DICOM overlay shapes        | Per-item default   | Optional: same stroked-outline approach     |

Implementing the ROI part (3.1) achieves the TO_DO goal (e.g. drawing an ellipse inside another). Annotation tightening (3.2) can be done later if desired.
