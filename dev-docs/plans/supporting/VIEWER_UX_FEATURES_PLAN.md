# Viewer UX Features – Implementation Plan

**Created:** 2026-03-21  
**Status:** Draft, reviewed 2026-03-21  
**Covers:** Six UX/viewer features from TO_DO.md, plus **ROI per-channel statistics** (**ROI_RGB1**).

---

## Table of Contents

1. [ROI Editing (Resize Handles)](#1-roi-editing-resize-handles)
2. [Window/Level Remembered Per Series](#2-windowlevel-remembered-per-series)
3. [Scale Markers (Ruler Ticks)](#3-scale-markers-ruler-ticks)
4. [Direction Labels (A/P/L/R/S/I)](#4-direction-labels-aplrsi)
5. [Flip and Rotate Image](#5-flip-and-rotate-image)
6. [Subwindow Slice / Frame Slider Bars](#6-subwindow-slice--frame-slider-bars)
7. [ROI per-channel statistics (RGB) — ROI_RGB1](#7-roi-per-channel-statistics-rgb--roi_rgb1)

---

## 1. ROI Editing (Resize Handles)

**Priority:** P2  
**TO_DO entry:** "Add ability to edit a drawn ellipse or rectangle ROI"  
**Status:** Implemented — see **Shipped behavior** below; the **Step-by-Step Plan** block is the original design sketch (kept for history).

### Goal

After an ROI has been drawn (and is in the finished state with `ItemIsMovable = True`), the user should be able to resize it by dragging handle points at the corners or cardinal edges of the bounding rectangle.

### Current Architecture

- `ROIGraphicsEllipseItem` / `ROIGraphicsRectItem` in `src/tools/roi_manager.py` – custom `QGraphicsItem` subclasses that notify the parent `ROIItem` on position change (for move).
- `ROIItem` wraps the graphics item and exposes the shape's bounding rect.
- `ROIManager` owns all `ROIItem`s and coordinates drawing state (`start_drawing`, `update_drawing`, `finish_drawing`).
- ROI items are placed in a `QGraphicsScene` managed by `ImageViewer` (`src/gui/image_viewer.py`).

### Shipped behavior (implementation map)

| Concern | Where |
|--------|--------|
| Handle type | `ROIResizeHandleItem` in `src/tools/roi_manager.py` (`QGraphicsRectItem`, `ItemIgnoresTransformations`, high `zValue`). |
| Layout | Eight handles (**tl, tm, tr, ml, mr, bl, bm, br**) on the scene bounding box (ellipse uses the same box as the rect item). |
| Geometry | `apply_roi_scene_bounding_rect()` + `compute_resized_scene_rect_from_handle()` — `setPos(topLeft)` + `setRect(0,0,w,h)` in scene units. |
| Session | `ROIManager.enter_roi_geometry_edit_mode` / `exit_roi_geometry_edit_mode`; auto-exit on slice change (`set_current_slice`), `select_roi` to another ROI, ROI delete/clear, and empty image click (`handle_image_clicked_no_roi`). |
| Selection / menu | Handles appear when a rectangle or ellipse ROI is selected (click, ROI list, scene `selectionChanged`, or right after draw finish). Optional: `ImageViewer.roi_geometry_edit_requested` → `handle_roi_geometry_edit_requested` (select + enter mode; wired in `subwindow_lifecycle_controller.py`). |
| Escape | `KeyboardEventHandler` optional callback from `app_handler_bootstrap` → `roi_coordinator.exit_roi_geometry_edit_mode()`. |
| Live stats | Handle drag calls the same `on_moved_callback` path as moving the ROI. |
| Undo | `ROIGeometryResizeCommand` in `src/utils/undo_redo.py` — one command per handle gesture (press → release). |
| Hit testing | `image_viewer_input.py` normalizes a pick of `ROIResizeHandleItem` to the parent ROI shape item so ROI tools / deselect logic stay consistent. |
| Move lock | `ItemIsMovable` disabled on the ROI shape while a handle drag is active. |

### Approach – Overlay Handle Items

Add eight `QGraphicsRectItem` handle items (corners + edge midpoints; four for an ellipse: N/S/E/W) as sibling items in the scene, attached conceptually to the selected ROI. Dragging a handle resizes the underlying shape.

**Important implementation note:** do not rely on `ItemIsMovable` alone for handle behavior. For resize handles, it is safer to treat mouse movement as input and immediately reposition the handle back onto the recomputed ROI edge after each drag step. That avoids handle drift and keeps the ROI geometry authoritative.

### Step-by-Step Plan

#### Step 1 – Define a `ROIHandleItem` class (`src/tools/roi_manager.py`)

```python
class ROIHandleItem(QGraphicsRectItem):
    HANDLE_SIZE = 8  # screen-space pixels; scale-invariant via ScaleInvariant flag

    def __init__(self, roi_item: 'ROIItem', handle_pos: str, callback):
        super().__init__(-self.HANDLE_SIZE/2, -self.HANDLE_SIZE/2,
                         self.HANDLE_SIZE, self.HANDLE_SIZE)
        self._roi_item = roi_item
        self._handle_pos = handle_pos  # "tl", "tm", "tr", "ml", "mr", "bl", "bm", "br"
        self._callback = callback
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(100)
        self.setPen(QPen(Qt.white, 1))
        self.setBrush(QBrush(Qt.cyan))

    def mousePressEvent(self, event):
        self._drag_start_scene_pos = event.scenePos()
        event.accept()

    def mouseMoveEvent(self, event):
        self._callback(self._handle_pos, event.scenePos())
        event.accept()
```

Use `QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations` so handles stay the same screen size regardless of zoom.

#### Step 2 – Add handle management to `ROIItem`

Add methods:
- `show_handles(scene)` – creates the eight (or four for ellipse) `ROIHandleItem`s, adds them to `scene`, positions them at the bounding rect corners/midpoints.
- `hide_handles(scene)` – removes handle items from `scene` and clears the list.
- `update_handle_positions()` – recalculates handle scene positions after a move or resize.
- `_on_handle_dragged(handle_pos: str, scene_pos: QPointF)` – resizes the underlying `QGraphicsItem` rect based on which handle is dragged.

Resize logic in `_on_handle_dragged`:
- Convert `scene_pos` to item-local coordinates.
- Adjust the item's `rect()` (via `setRect()`) according to which handle was dragged (e.g., "tl" changes top-left of rect, "mr" changes right edge only).
- Call `update_handle_positions()` after.
- Emit the existing move/change callback so statistics update.

#### Step 3 – Add "edit mode" to `ROIManager`

Add `self._editing_roi: Optional[ROIItem] = None`.

- When the user right-clicks a finished ROI → context menu offers **"Edit ROI"** (or double-click activates edit mode).
- Selecting **"Edit ROI"**: call `roi.show_handles(self.scene)`, store in `_editing_roi`.
- Clicking elsewhere or pressing Escape: call `roi.hide_handles(self.scene)`, clear `_editing_roi`.

#### Step 4 – Wire into `ROICoordinator` / `ImageViewer`

In `src/gui/roi_coordinator.py` (or `image_viewer.py` mouse event handling):
- On right-click over a ROI item in ROI mode → show context menu including an **Edit** option.
- Pass the activation through to `ROIManager.enter_edit_mode(roi_item)`.

#### Step 5 – Statistics update on resize

After each resize (every `mouseMoveEvent` of a handle), call the existing ROI statistics callback so that the stats panel live-updates. This reuses the existing callback path from `ROIItem._on_item_moved` / `on_moved_callback`.

#### Step 6 – Persist geometry

ROI coordinates are stored as bounding rect + shape type. No changes needed here – the modified rect is already the authoritative geometry. Undo/redo should capture a before/after snapshot of the rect; integrate with the existing `UndoRedoManager` like move does.

### Edge Cases / Risks

- Handles must be hidden when the viewer switches slices (ROI might not belong to the new slice).
- The `ItemIgnoresTransformations` flag keeps handles screen-size-fixed but also means their scene positions must be manually placed – avoid relying on Qt's transform for layout.
- Minimum size constraint: prevent negative-area rects (clamp rect dimensions ≥ 2 px).
- **Context menu:** Right-click must treat a handle like its parent ROI (normalize pick) so delete/statistics actions target the shape item, not the handle widget class alone.

---

## 2. Window/Level Remembered Per Series

**Priority:** P2  
**TO_DO entry:** "Make window/level settings remembered when switching series and then switching back"

### Goal

When the user adjusts W/L on a series and then navigates away (switching to another series in the same subwindow), on switching back the previously set W/L should be restored instead of re-loading the DICOM-embedded defaults.

### Current Architecture

- `ViewStateManager` (`src/core/view_state_manager.py`) already has:
  - `series_defaults: Dict[str, Dict]` – keyed by `series_identifier`; currently stores W/L at the time a series is *first loaded*.
  - `current_series_identifier` – updated on each new slice load.
  - `store_initial_view_state()` – saves defaults on first load (sets `window_level_defaults_set` flag to avoid overwriting).
  - `reset_window_level_state()` – clears `current_window_center/width` and `initial_*` fields.
- `FileSeriesLoadingCoordinator.display_series()` (`src/core/file_series_loading_coordinator.py`) calls `reset_window_level_state()` before loading a new series into a subwindow.

### Gap

The *user-adjusted* W/L is never saved back into `series_defaults`. Only the first-load (DICOM default) value is stored. When returning to a series, `store_initial_view_state` sees `window_level_defaults_set = True` and does not overwrite – so the returned view always uses the DICOM default.

### Approach

Introduce a separate per-series **user-adjusted W/L cache** that is saved when a series is unloaded and restored when it is reloaded.

**Important implementation note:** do not bolt the restore path onto `store_initial_view_state()`. That method already restores defaults and triggers redisplay in some cases. Adding another restore/redisplay there is likely to duplicate work and can recurse through the existing display pipeline.

### Step-by-Step Plan

#### Step 1 – Add user W/L cache to `ViewStateManager`

```python
# Key: series_identifier, Value: {"window_center": float, "window_width": float}
self._user_wl_cache: Dict[str, Dict[str, float]] = {}
```

Add methods:
```python
def save_user_window_level(self) -> None:
    """Save current (user-adjusted) W/L for the current series."""
    if self.current_series_identifier and self.current_window_center is not None:
        self._user_wl_cache[self.current_series_identifier] = {
            "window_center": self.current_window_center,
            "window_width": self.current_window_width,
        }

def get_user_window_level(self, series_id: str) -> Optional[Dict[str, float]]:
    """Return saved user W/L for series_id, or None if never adjusted."""
    return self._user_wl_cache.get(series_id)

def clear_user_window_level(self, series_id: str) -> None:
    """Discard saved user W/L (e.g. on study close)."""
    self._user_wl_cache.pop(series_id, None)
```

#### Step 2 – Save before series switch

In `FileSeriesLoadingCoordinator.display_series()` (or the subwindow lifecycle controller's series-assignment flow), before calling `reset_window_level_state()`, call `view_state_manager.save_user_window_level()`.

The most appropriate place is the start of `display_series()` just before the reset, e.g.:
```python
if view_state_manager_0.current_series_identifier:
    view_state_manager_0.save_user_window_level()
view_state_manager_0.reset_window_level_state()
```

#### Step 3 – Restore after series switch

Add a dedicated restore hook in the series display path, before the first rendered redisplay for the newly assigned series is finalized. Prefer a flow like:

1. Determine the incoming `series_identifier`.
2. Load embedded DICOM defaults as today.
3. If `_user_wl_cache` has an entry for that identifier, replace the pending W/L values before updating controls and before the final display refresh.

That should live in the normal series/slice display flow, not inside `store_initial_view_state()`.

Example shape:
```python
user_wl = self.get_user_window_level(series_identifier)
if user_wl:
    self.current_window_center = user_wl["window_center"]
    self.current_window_width = user_wl["window_width"]
    self.window_level_controls.set_window_level(
        self.current_window_center,
        self.current_window_width,
        block_signals=True,
        unit=self.rescale_type if self.use_rescaled_values else None,
    )
```

The key is that the normal display flow should render once using the final chosen values, instead of rendering with DICOM defaults and then immediately re-rendering.

#### Step 4 – Clear cache on study close

In the study-close / file-close path in `DICOMViewerApp` (the `_on_close_*` handlers), iterate over series identifiers belonging to the closed study and call `clear_user_window_level()` for each.

#### Step 5 – Reset on "Reset W/L" action

The existing "Reset Window/Level" menu action already calls `reset_window_level_state()`. Additionally call `clear_user_window_level(current_series_identifier)` so that the next series switch does not restore the old adjusted values.

### Edge Cases / Risks

- MPR series: MPR views derive their W/L from the base series; the MPR series identifier may differ. Ensure the MPR identifier is cleared correctly when the MPR is cleared.
- If the user opens a file, adjusts W/L, closes the file, and reopens it, the in-memory cache is gone. This is acceptable (cache is session-only). If persistence across sessions is ever wanted, serialize to config.

---

## 3. Scale Markers (Ruler Ticks)

**Priority:** P1  
**TO_DO entry:** "Add scale markers on left and bottom (small ticks every image mm, large every cm)"

### Goal

Draw a graduated ruler in a subtle, unobtrusive strip along one horizontal edge (top or bottom) and one vertical edge (left or right) of each viewer. Small ticks every 1 mm, large ticks every 10 mm (1 cm), with minimal labeling at cm intervals. The ruler should not appear as a grid or extend across the image interior.

### Current Architecture

- `ImageViewer` (`src/gui/image_viewer.py`) is a `QGraphicsView`. The viewport's `paintEvent` can be extended, or a lightweight overlay widget can be placed on top.
- `get_pixel_spacing(dataset)` in `src/utils/dicom_utils.py` returns `(row_spacing_mm, col_spacing_mm)`.
- The current zoom factor is `ImageViewer.current_zoom`.
- `OverlayManager` (`src/gui/overlay_manager.py`) manages text overlays drawn as `QGraphicsTextItem`s in the scene. A ruler is better drawn in viewport (screen) coordinates rather than scene coordinates, to stay fixed to the window edge and scale correctly.

### Recommended Approach – `ScaleRulerWidget` overlay

Create a transparent `QWidget` (`ScaleRulerWidget`) that is placed as a child of the `ImageViewer` viewport, fills it, and reimplements `paintEvent` to draw the rulers in viewport coordinates. This approach:
- Avoids interfering with the scene/zoom transform.
- Naturally redraws when the viewer resizes or zooms (connect to `ImageViewer.zoom_changed` signal and `resizeEvent`).
- Is easy to show/hide with a menu toggle.

The widget may cover the full viewport for convenience, but it should paint only two narrow edge strips. Nothing should be drawn through the center of the image, and there should be no grid-like extension into the image area.

### Step-by-Step Plan

#### Step 1 – Create `ScaleRulerWidget` (`src/gui/scale_ruler_widget.py`)

```python
class ScaleRulerWidget(QWidget):
    RULER_THICKNESS = 14   # px, narrow and unobtrusive
    TICK_SMALL = 3         # px, 1mm tick height
    TICK_LARGE = 7         # px, 1cm tick height
    LABEL_OFFSET = 2       # px from tick tip to label
    BG_COLOR = QColor(0, 0, 0, 45)
    TICK_COLOR = QColor(255, 255, 255, 120)
    LABEL_COLOR = QColor(255, 255, 255, 150)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._pixel_spacing_row: Optional[float] = None  # mm per row pixel
        self._pixel_spacing_col: Optional[float] = None  # mm per col pixel
        self._zoom: float = 1.0
        self._image_origin: QPoint = QPoint(0, 0)  # viewport pos of image top-left
        self._horizontal_edge: str = "bottom"  # or "top"
        self._vertical_edge: str = "left"      # or "right"

    def update_state(self, pixel_spacing, zoom: float, image_origin: QPoint):
        if pixel_spacing:
            self._pixel_spacing_row, self._pixel_spacing_col = pixel_spacing
        else:
            self._pixel_spacing_row = self._pixel_spacing_col = None
        self._zoom = zoom
        self._image_origin = image_origin
        self.update()

    def paintEvent(self, event):
        if not self._pixel_spacing_col:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        self._draw_horizontal_ruler(painter)
        self._draw_vertical_ruler(painter)
```

Ruler drawing helpers:
- `_draw_horizontal_ruler`: Draw only a narrow strip along the configured top or bottom edge. Iterate in viewport `x`, stepping by `zoom / col_spacing_mm` px per mm. Draw short ticks at each mm, tall ticks at each cm, and label sparingly.
- `_draw_vertical_ruler`: Same along the configured left or right edge, using `row_spacing_mm`.

Coordinate math for bottom ruler:
```python
x0 = image_origin.x()
y_base = height() - RULER_THICKNESS if self._horizontal_edge == "bottom" else 0
for mm in range(0, max_mm):
    vx = x0 + mm * zoom / pixel_spacing_col
    tick_h = TICK_LARGE if mm % 10 == 0 else TICK_SMALL
    tick_y0 = y_base + (RULER_THICKNESS - tick_h if self._horizontal_edge == "bottom" else 0)
    tick_y1 = y_base + RULER_THICKNESS if self._horizontal_edge == "bottom" else y_base + tick_h
    painter.drawLine(vx, tick_y0, vx, tick_y1)
    if mm % 10 == 0 and mm > 0 and mm % 20 == 0:
        painter.drawText(vx + LABEL_OFFSET, y_base + RULER_THICKNESS - 1, f"{mm//10}")
```

Default visual choice should be `bottom + left`, but the implementation should leave room for switching to `top + right` later if that proves cleaner in some layouts.

#### Step 2 – Instantiate and manage in `ImageViewer`

In `ImageViewer.__init__`, create `self._ruler = ScaleRulerWidget(self.viewport())`.

Resize it to match the viewport in `resizeEvent`:
```python
def resizeEvent(self, event):
    super().resizeEvent(event)
    self._ruler.resize(self.viewport().size())
    self._update_ruler()
```

Add `_update_ruler()`:
```python
def _update_ruler(self):
    if self._pixel_spacing and self._ruler.isVisible():
        # Map image scene origin to viewport coordinates
        scene_origin = self.mapFromScene(QPointF(0, 0))
        self._ruler.update_state(self._pixel_spacing, self.current_zoom, scene_origin)
```

Call `_update_ruler()` from:
- `zoom_changed` signal handler.
- After `set_image()` (when new pixel spacing is provided).
- `scrollContentsBy` override (scroll changes image position).

Only the two ruler strips should repaint. Do not draw a full-viewport overlay background.

#### Step 3 – Supply pixel spacing to `ImageViewer`

Add `set_pixel_spacing(spacing: Optional[Tuple[float, float]])` to `ImageViewer`. Call it from the slice display path after loading the dataset (pass `get_pixel_spacing(dataset)`).

#### Step 4 – Add toggle to View menu and context menu

In `src/gui/main_window_menu_builder.py`, add a **Show Ruler** checkable action under the View menu and wire it to `image_viewer.set_ruler_visible(bool)`.

Mirror the action in the right-click context menu (as per TO_DO item for overlay configuration in context menu).

Persist the setting via `ConfigManager` (`display_config.py` mixin):
```python
def show_scale_ruler(self) -> bool: ...
def set_show_scale_ruler(self, v: bool) -> None: ...
```

#### Step 5 – Handle edge cases

- No pixel spacing available (e.g., secondary captures, screenshots): hide ruler quietly; do not add extra text.
- Very high zoom (ruler ticks too dense): thin out labels beyond a density threshold (e.g. only show every 5 mm if ticks are < 3 px apart).
- Very low zoom (ticks too sparse): only show cm ticks.
- MPR views: MPR pixel spacing is computed during resampling; supply it the same way.
- The ruler should remain visually secondary to the image. If labels feel busy, prefer fewer labels over more opacity.

---

## 4. Direction Labels (A/P/L/R/S/I)

**Priority:** P1  
**TO_DO entry:** "Add direction labels (A/P/L/R/S/I) on viewer window"

### Goal

Show anatomical direction labels at the four edges of the displayed image (top, bottom, left, right) indicating the patient anatomical direction that each edge of the image faces. Standard DICOM convention: L=Left, R=Right, A=Anterior, P=Posterior, S=Superior, I=Inferior.

### DICOM Background

`ImageOrientationPatient` (IOP) tag contains six cosines: `[F0, F1, F2, F3, F4, F5]` where `[F0, F1, F2]` is the row direction cosine vector (direction a row travels, in patient LPS), and `[F3, F4, F5]` is the column direction cosine. The label for an edge is determined by which principal patient axis the row/column vector most closely aligns with.

```python
def cosines_to_label(cosines: list[float]) -> str:
    """Return A/P/L/R/S/I label for a direction cosine triplet [X, Y, Z] in LPS."""
    labels = [("L", "R"), ("P", "A"), ("I", "S")]  # LPS axes
    label = ""
    for i in range(3):
        if abs(cosines[i]) > 0.1:
            label += labels[i][0 if cosines[i] < 0 else 1]
    return label or "?"
```

Edge labels:
- **Right edge** = row direction label (`cosines_to_label([F0, F1, F2])`)
- **Left edge** = opposite of right edge
- **Bottom edge** = column direction label (`cosines_to_label([F3, F4, F5])`)
- **Top edge** = opposite of bottom edge

For oblique images, the label may be two letters (e.g. "AL" for anterior-left).

### Current Architecture

- `DicomParser.parse_dicom_metadata()` already extracts `ImageOrientationPatient` into the metadata dict.
- `OverlayManager` currently places text overlays (corner labels, series info) in the `QGraphicsScene` as `QGraphicsTextItem`s. Direction labels at the edges could be added the same way, or drawn in a separate overlay widget.
- `ViewStateManager` holds `current_dataset` as a reference.

### Recommended Approach – Viewport overlay labels in `OverlayManager`

Use the existing `ViewportOverlayWidget` / `QLabel` overlay path in `OverlayManager`, not new scene-based `QGraphicsTextItem`s. The current code already favors viewport widgets for stable overlay positioning during zoom/pan, so direction labels should follow that path instead of introducing a second overlay model.

### Step-by-Step Plan

#### Step 1 – Add IOP parsing utility (`src/utils/dicom_utils.py`)

```python
def get_image_orientation_labels(dataset) -> Optional[dict]:
    """
    Return edge direction labels derived from ImageOrientationPatient.
    Returns dict with keys 'top', 'bottom', 'left', 'right', or None if IOP missing.
    """
    iop = getattr(dataset, 'ImageOrientationPatient', None)
    if not iop or len(iop) < 6:
        return None
    row_cos = [float(iop[0]), float(iop[1]), float(iop[2])]
    col_cos = [float(iop[3]), float(iop[4]), float(iop[5])]
    right_label  = _cosines_to_label(row_cos)
    left_label   = _cosines_to_label([-v for v in row_cos])
    bottom_label = _cosines_to_label(col_cos)
    top_label    = _cosines_to_label([-v for v in col_cos])
    return {'top': top_label, 'bottom': bottom_label,
            'left': left_label, 'right': right_label}

def _cosines_to_label(cosines: list) -> str:
    axes = [("L","R"), ("P","A"), ("I","S")]
    label = ""
    for i in range(3):
        if abs(cosines[i]) > 0.1:
            label += axes[i][0 if cosines[i] < 0 else 1]
    return label or "?"
```

#### Step 2 – Add direction label widgets to `ViewportOverlayWidget`

In the viewport overlay widget used by `OverlayManager`, add four edge `QLabel`s (`top_center`, `bottom_center`, `left_center`, `right_center`). Style them consistently with the existing overlay labels but slightly larger and centered on the corresponding edge.

Add `set_direction_labels(labels: Optional[dict])`:
```python
def set_direction_labels(self, labels: Optional[dict]) -> None:
    if not labels:
        for label in self._direction_labels.values():
            label.setVisible(False)
        return
    for edge, label in self._direction_labels.items():
        label.setText(labels.get(edge, ""))
        label.setVisible(self._direction_labels_visible)
```

Update the viewport overlay widget layout logic to position each label at the center of its corresponding image edge, in viewport coordinates:
```python
# Example for bottom label
label.adjustSize()
label.move((self.width() - label.width()) // 2, self.height() - label.height() - 6)
```

#### Step 3 – Feed labels to `OverlayManager` on slice change

In the slice display path (the `ViewStateManager` → overlay update flow), after loading a new dataset:
```python
from utils.dicom_utils import get_image_orientation_labels
labels = get_image_orientation_labels(dataset)
overlay_manager.set_direction_labels(labels)
```

The natural place is alongside where `overlay_manager` is currently called to update displayed tags.

#### Step 4 – Add visibility toggle

Add toggle to View menu and context menu (**Show Direction Labels**), mirroring the pattern for other overlay visibility toggles. Persist with `overlay_config.py` mixin as `show_direction_labels: bool` (default `True`).

Wire to `overlay_manager.set_direction_labels_visible(bool)`.

#### Step 5 – Handle MPR

MPR views already compute a synthetic IOP from the resampled plane. In `mpr_controller.py`, the `mpr_orientation` string is set. Extend the MPR activation path to also call `set_direction_labels()` with labels derived from the MPR plane's row/column cosines. Prefer deriving from cosines over hard-coded axial/coronal/sagittal presets so oblique and future rotated views stay correct.

#### Step 6 – Handle missing/unknown IOP

If IOP is absent (e.g. secondary captures, screen saves), hide all four labels gracefully.

---

## 5. Flip and Rotate Image

**Priority:** P2  
**TO_DO entry:** "Allow flipping and rotating image"

### Goal

Allow the user to horizontally flip, vertically flip, and rotate the displayed image in 90° increments (90°, 180°, 270°, reset). These transforms should:
- Apply instantly and non-destructively (no pixel re-processing; use Qt transform).
- Be remembered per-series (so switching series and back restores the flip/rotation).
- Work correctly with zoom, pan, and overlay positions.

### Current Architecture

- `ImageViewer` uses a `QTransform` to represent scale (zoom). `setTransform(QTransform.fromScale(zoom, zoom))` is called from `_apply_zoom()` and related methods.
- `self.current_zoom` tracks the scale factor; `self.last_transform` caches the last applied transform.
- Overlays (ROIs, annotations, ruler ticks) are in the scene coordinate system and will automatically mirror with the transform.
- Direction labels and scale ruler are in viewport coordinates – they need special handling.

### Approach – Compose flip/rotation into the `QTransform`

Maintain `flip_h: bool`, `flip_v: bool`, and `rotation_deg: int` (0/90/180/270) state in `ImageViewer`. Build the full transform as:

```
T = scale(zoom) ∘ translate(center) ∘ rotate(rotation_deg) ∘ scale(flip_h ? -1 : 1, flip_v ? -1 : 1) ∘ translate(-center)
```

In practice, `QTransform` can represent combined scale+rotate+flip as a single matrix. Rebuild the transform whenever any component changes.

**Important implementation note:** the current viewer code frequently reads zoom back from the transform matrix using `transform().m11()` and also calls `setTransform()`, `resetTransform()`, and `fitInView()` from several places. That works for scale-only transforms, but it becomes unreliable once 90°/270° rotation is introduced because `m11()` no longer equals the visual zoom factor.

### Step-by-Step Plan

#### Step 1 – Add flip/rotation state to `ImageViewer`

```python
self._flip_h: bool = False
self._flip_v: bool = False
self._rotation_deg: int = 0  # 0, 90, 180, 270
```

Add `set_flip_h(v: bool)`, `set_flip_v(v: bool)`, `set_rotation(deg: int)` methods, each calling `_apply_view_transform()`.

#### Step 2 – Add `_apply_view_transform()` to `ImageViewer`

Replace current direct `setTransform(QTransform.fromScale(...))` calls with a single method that composes all components. Treat `self.current_zoom` as the authoritative scalar instead of recalculating it from `m11()` after rotation.

```python
def _apply_view_transform(self) -> None:
    t = QTransform()
    if self._rotation_deg or self._flip_h or self._flip_v:
        t.rotate(self._rotation_deg)
        sx = -1 if self._flip_h else 1
        sy = -1 if self._flip_v else 1
        t.scale(sx, sy)
    t.scale(self.current_zoom, self.current_zoom)
    self.setTransform(t)
    self.last_transform = t
    self.zoom_changed.emit(self.current_zoom)
```

All existing zoom-change paths that call `setTransform`, `resetTransform`, or rely on `transform().m11()` should be routed through this helper or adjusted to preserve the explicit `current_zoom` state.

Before implementation, audit every direct transform call in `image_viewer.py`, especially the `set_image()`, `fit_to_view()`, zoom-in/out, reset-view, and wheel-zoom paths.

#### Step 3 – Make fit-to-view rotation-safe

The current `fit_to_view()` flow derives zoom from `transform().m11()` after `fitInView()`. That is safe for scale-only transforms but not for 90°/270° rotation. Update this path so the computed fit zoom is stored explicitly and does not depend on extracting `m11()` from a rotated transform.

One practical option is:

1. Compute the fit scale from viewport and image bounds directly.
2. Store that scalar in `self.current_zoom`.
3. Call `_apply_view_transform()`.

That keeps zoom math stable even when orientation is not identity.

**Note on rotation center:** `QGraphicsView.setTransform` applies the transform centered on the view, not the scene origin. Use `rotate()` with a center point if needed, or center the scene item at `(0,0)` so rotation is naturally around the image center.

#### Step 4 – Per-series persistence in `ViewStateManager`

Extend the `series_defaults` dict to include flip/rotation:
```python
self.series_defaults[series_id] = {
    ...existing fields...,
    'flip_h': False,
    'flip_v': False,
    'rotation_deg': 0,
}
```

Add `save_flip_rotation()` (analogous to `save_user_window_level()`) and `restore_flip_rotation(series_id)`.

Wire into the series-switch save/restore flow described in Feature 2, Step 2-3.

#### Step 5 – Add UI controls

Add to the **View menu** (and image right-click context menu):
- **Flip Horizontal** (shortcut: `H`)
- **Flip Vertical** (shortcut: `V`)
- **Rotate 90° CW** (shortcut: `R`)
- **Rotate 90° CCW**
- **Reset Orientation** – clears all flips and rotation

These should be placed in a "Orientation" submenu or a separator group.

In `src/gui/main_window_menu_builder.py`, add these actions and connect them to `image_viewer.set_flip_h(...)`, etc.

#### Step 6 – Update direction labels and ruler on transform change

After `_apply_view_transform()`:
- Direction labels: swap left/right if `_flip_h`, swap top/bottom if `_flip_v`, rotate label positions for 90°/270° rotations. The simplest approach: recompute the four labels based on the composed transform applied to the IOP row/col vectors.
- Scale ruler: the ruler overlay widget is in viewport space; reposition its anchor (which edge it draws on) if rotation is 90° or 270°. Keep logic simple: always draw the bottom ruler using column spacing *before* rotation, then rotate placement logic for 90°/270°.

#### Step 7 – Export compatibility

When exporting a screenshot or rendering an image with overlays, the export path must use the same composed transform so the exported image matches the screen view. Verify `_apply_view_transform()` is respected in the export rendering path in `src/core/export_manager.py`.

#### Step 8 – Undo/Redo support

Add flip/rotation commands to the undo stack alongside move/delete ROI commands, using the existing `UndoRedoManager`. Each orientation change pushes a reversible action.

### Edge Cases / Risks

- Crosshair manager: the crosshair position is in scene coordinates and will naturally flip/rotate with the scene transform. Verify visually.
- MPR views: MPR already applies a fixed orientation; flip/rotate should still work but the direction labels need to be recomputed from the post-flip IOP vectors.
- Fusion overlay: the fusion image is drawn in the same scene and will transform correctly.
- Rotation of 90°/270° swaps the effective width and height; this may affect the initial fit-to-view zoom. Call `_fit_to_view()` after applying rotation.

---

## 6. Subwindow Slice / Frame Slider Bars

**Priority:** P1  
**TO_DO entry:** "Slice / frame slider bars in subwindows - ideally only appears when you mouse over near some edge of the window"

### Goal

Provide an in-view slider for slice or frame navigation inside each subwindow so users can scrub without moving to other controls. The slider should stay visually out of the way by default and only reveal itself when the pointer approaches the relevant viewer edge or while the slider is actively being used.

### Current Architecture

- `ImageViewer` in `src/gui/image_viewer.py` owns the per-subwindow `QGraphicsView` and already handles mouse enter/leave, zoom, pan, and context-menu interaction.
- Slice and frame navigation state currently flows through the existing loading/navigation coordinators and the subwindow-scoped state managers rather than being owned directly by the viewer widget.
- The codebase already uses viewport overlays for viewer-adjacent UI (`OverlayManager`, planned ruler/labels), which is a better fit here than scene items because the control should remain pinned to the subwindow edge.

### Recommended Approach – Edge-Revealed Viewport Overlay Slider

Add a lightweight overlay widget hosted inside each `ImageViewer` viewport. That widget contains a single `QSlider` and a compact label showing the current position, and it fades in only when:

- the pointer enters a small activation zone near the chosen edge,
- the user hovers the slider itself,
- or the user is currently dragging the thumb.

The overlay should hide again after a short idle delay once the pointer leaves both the activation zone and the slider.

Use one slider control per viewer, but let its label and range adapt to the active content:

- normal stack: `Slice X / N`
- multi-frame instance: `Frame X / N`
- future dual-axis cases: keep this first version single-axis and do not over-design for Tier 3 yet

### Step-by-Step Plan

#### Step 1 – Create `EdgeRevealSliderOverlay` (`src/gui/edge_reveal_slider_overlay.py`)

Create a transparent child widget of the `ImageViewer` viewport containing:

- a horizontal or vertical `QSlider` depending on chosen edge placement,
- a small `QLabel` for `Slice 14 / 120` or `Frame 3 / 20`,
- a `QTimer` used to delay auto-hide,
- a simple opacity animation (`QGraphicsOpacityEffect` + `QPropertyAnimation`) so reveal/hide feels intentional rather than abrupt.

Recommended initial placement: along the right edge as a vertical slider. That keeps it out of the way of bottom overlays and matches the user's note about appearing near an edge.

Key methods:

```python
def set_range_and_value(self, minimum: int, maximum: int, value: int, label_text: str) -> None: ...
def reveal(self) -> None: ...
def schedule_hide(self) -> None: ...
def set_interaction_enabled(self, enabled: bool) -> None: ...
```

The overlay widget itself should accept mouse input, but any transparent area around the slider should not block normal image interaction.

#### Step 2 – Manage activation zones in `ImageViewer`

In `src/gui/image_viewer.py`, add logic to detect when the pointer is close enough to the activation edge. A small threshold such as 20 to 28 px is enough.

Add helpers such as:

```python
def _is_in_slider_activation_zone(self, pos: QPoint) -> bool: ...
def _update_slider_overlay_visibility(self, pos: QPoint | None = None) -> None: ...
```

Wire them from:

- `mouseMoveEvent`
- `enterEvent`
- `leaveEvent`
- `resizeEvent`

Important implementation note: do not reveal the slider on every hover anywhere in the viewer. Restricting reveal to the activation zone avoids constant UI flicker during normal pan/window-level work.

#### Step 3 – Feed navigation state into the overlay

Add a thin viewer-facing API so the existing navigation/display flow can update the overlay without moving navigation ownership into `ImageViewer`.

Example shape:

```python
def set_navigation_slider_state(
    self,
    *,
    visible: bool,
    minimum: int,
    maximum: int,
    value: int,
    mode_label: str,
) -> None:
    ...
```

Populate it from the same place that already knows the currently displayed slice/frame index and total count for each subwindow. For multi-frame content, reuse the display context already being assembled in `DICOMOrganizer.get_multiframe_display_context()` and adjacent UI plumbing instead of duplicating frame-detection logic inside the viewer.

#### Step 4 – Route slider moves back into the existing navigation path

Connect the overlay slider's `valueChanged` / `sliderMoved` signal to the existing per-subwindow navigation flow so dragging the overlay performs the same operation as other slice/frame navigation controls.

The slider should be translated carefully between UI indexing and internal indexing:

- user-facing text and slider values should be 1-based,
- internal slice/frame indices may remain 0-based.

Prefer `sliderMoved` for live scrubbing if current rendering performance is acceptable. If large stacks make that too expensive, fall back to updating on `sliderReleased` and keep the thumb live only.

#### Step 5 – Keep the overlay in sync with wheel/keyboard navigation

Whenever the current slice/frame changes through mouse wheel, keyboard, cine, navigator thumbnail click, or programmatic series assignment, update the overlay value and label.

This must be one-way state sync from the authoritative navigation state into the overlay so the thumb never lags behind the actual image being shown.

#### Step 6 – Hide for unsupported or low-value cases

Do not show the control when:

- there is no image loaded,
- the series has only one slice/frame,
- an operation is active that would materially conflict with the edge interaction,
- or the viewer is too small for the slider to be usable.

For a very small subwindow, prefer hiding the label first and only showing the slider track/thumb.

#### Step 7 – Add a View toggle and config persistence

Add a checkable action such as **Show In-View Slice/Frame Slider** under the View menu and persist it in config. Default can reasonably be `True` once the reveal behavior is quiet enough.

Config additions belong with other display/view preferences in `src/utils/config/display_config.py` or the closest existing mixin that owns viewer display options.

#### Step 8 – Validate against existing interactions

Before considering implementation complete, manually verify:

- wheel slice scrolling still works,
- drag-to-pan and drag-to-window/level do not accidentally trigger the slider,
- context menu near the right edge is still reachable,
- cine playback keeps the slider in sync,
- multi-frame datasets label the control as frame navigation when appropriate.

### Edge Cases / Risks

- Right-edge placement can compete with existing scrollbars if the viewer still exposes Qt scrollbars in some states. Prefer hiding native scrollbars or ensuring the overlay sits inside the image area, not on top of Qt chrome.
- Hover-based reveal can feel noisy if the activation band is too wide or the hide delay is too short. Tune behavior before exposing a config knob.
- Live scrubbing through large series may create too many redraws. If that shows up, debounce or update only on release for the first version.
- Privacy mode should not affect the slider itself, but any text label should remain generic (`Slice`, `Frame`) and not surface protected metadata.

---

## 7. ROI per-channel statistics (RGB) — **ROI_RGB1**

**Priority:** P2  
**TO_DO:** `dev-docs/TO_DO.md` **L99** — *For ROIs, allow computing and displaying stats per color channel (RGB, etc.) (**on by default when RGB data present**, can be enabled in settings).*  
**Orchestration:** milestone **M3** after **CINE1**/**RDSR1** on single-branch default (reduces overlap with export/menu churn on `main_window` — adjust only if **`NEXT_TASK_TOOL_SECOND`** + second worktree is approved).

### Goal and success criteria

- When the **current slice pixel array** is **multi-channel** (e.g. **RGB** color-by-plane, `PhotometricInterpretation` / `SamplesPerPixel` heuristics — confirm in implementation spec), ROI statistics show **per-channel mean/std/min/max** (and optionally **count** shared) **without** extra clicks.
- **Settings:** a **persisted boolean** allows users to **hide** per-channel breakdown and fall back to today’s **single scalar** summary (exact UX strings — **`ux`**).
- **Export / overlay / clipboard:** behavior is defined for PNG/JPG burn-in, **ROI statistics export** (`roi_export_service`, `export_rendering`), and **customizations import/export** so channel stats do not silently disappear.

### Default-on policy (checked-in TO_DO)

- **Default:** **on** when multi-channel / RGB-class data is detected for the slice.
- **Do not** contradict shipped `TO_DO.md` with “off by default” unless **product** updates TO_DO and this plan in the same change.

### Config and UI surfaces

| Item | Proposal |
|------|-----------|
| **Config key** | `roi_show_per_channel_statistics` (bool), default **`True`** — stored via **`src/utils/config/roi_config.py`** (`ROIConfigMixin` + `default_config` / `config_manager` merge pattern used elsewhere). |
| **Settings dialog** | ROI / Statistics section: checkbox **“Show per-channel ROI statistics when available”** (or equivalent). |
| **Statistics panel** | `src/gui/roi_statistics_panel.py` — extra rows or sub-table **R/G/B** when enabled + data is multi-channel. |
| **On-slice overlay** | `src/tools/roi_manager.py` text composition for `statistics` — line-wrap or abbreviated labels to avoid clutter (**`ux`**). |

### Code paths and file ownership

| Area | Likely modules |
|------|----------------|
| **Orchestration / panel** | `src/roi/roi_measurement_controller.py` (owns `ROIStatisticsPanel`), `src/gui/roi_coordinator.py` |
| **Computation** | `src/tools/roi_manager.py` — extend **`calculate_statistics`** (or parallel **`calculate_statistics_per_channel`**) to accept `pixel_array` with shape `(H, W, C)`; handle **C==1** unchanged. |
| **Session / paste** | `src/core/annotation_paste_handler.py`, `src/tools/roi_persistence.py` if new fields must round-trip |
| **Export** | `src/core/roi_export_service.py`, `src/core/export_rendering.py` |
| **Tests** | Synthetic **RGB** `numpy` array + known ROI mask → expected per-channel means |

### Task checklist (**ROI_RGB1**)

- [x] **(RGB1-1)** Detect “RGB / multi-channel present” consistently with DICOM decoding paths (`DICOMProcessor.get_pixel_array`, photometric interpretation).  
  `parallel-safe: no`, `stream: P`, `after: RDSR1` (default phasing) — **done** 2026-04-15 (`pixel_array.ndim == 3` and `shape[2] >= 2` in `roi_manager.calculate_statistics`)
- [x] **(RGB1-2)** Implement per-channel stats in **`roi_manager`** + wire **`roi_coordinator` / `ROIStatisticsPanel`** — **done** 2026-04-15
- [x] **(RGB1-3)** Add **`roi_config`** key + settings UI + **`default_config`** — **done** 2026-04-15 (`roi_show_per_channel_statistics`, Annotation options)
- [x] **(RGB1-4)** Extend **export** + **overlay** text + persistence as needed — **done** 2026-04-15 (ROI statistics export now includes per-channel columns in CSV and per-channel rows in TXT/XLSX; overlay + customizations export/import already complete)
- [x] **(RGB1-5)** Unit tests + **`CHANGELOG.md` [Unreleased] Added** — **done** 2026-04-15 (`tests/test_roi_export_service_multichannel.py` validates multichannel ROI stats + export columns; CHANGELOG updated)

### Risks

- **Palette color** vs **true RGB** — detection may mis-classify; need explicit rules and tests.
- **Performance** on large ROIs — three passes vs one; consider single masked gather.

---

## Cross-Feature Notes

### Suggested Implementation Order

1. **Direction Labels** – largely additive, touches only `dicom_utils.py` and `OverlayManager`. Low risk.
2. **Scale Markers** – additive (new `ScaleRulerWidget`), no changes to existing state.
3. **W/L Per-Series Memory** – touches `ViewStateManager` and `FileSeriesLoadingCoordinator`; focused, well-bounded.
4. **Flip/Rotate** – moderate; refactors `ImageViewer` transform composition, needs careful testing.
5. **ROI Edit Handles** – most complex; adds a new interaction mode, most surface area.

### Quick Sizing

- **Small:** Direction Labels, W/L Per-Series Memory
- **Medium:** Scale Markers
- **Large:** Flip/Rotate, ROI Edit Handles
- **Highest-risk files:** `src/gui/image_viewer.py`, `src/core/view_state_manager.py`, `src/tools/roi_manager.py`

### Shared Infrastructure

- **Config persistence** for show/hide ruler and direction labels should share the `display_config.py` / `overlay_config.py` pattern.
- **Right-click context menu** additions for ruler, direction labels, flip, rotate should all be wired through `src/gui/dialog_coordinator.py` or `roi_coordinator.py` as appropriate, not scattered.
- **Overlay update trigger:** all new overlay-position-dependent items should hook into the existing `update_overlay_positions()` call chain so they automatically correct on resize/zoom.
