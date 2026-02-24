# Image Smoothing When Magnified — Research

This document summarizes common approaches DICOM viewers use to smooth images when magnified (zoomed), with emphasis on ease of implementation, speed, and processing cost. It also outlines a strategy for using a simple method during zoom/pan and a more sophisticated method when idle, plus a user option to enable/disable smoothing (context menu and View menu).

---

## 1. Common Interpolation Methods

When a discrete image is displayed at a scale other than 1:1, the display pipeline must decide how to map source pixels to screen pixels. The choice is a trade-off between **quality**, **speed**, and **ease of implementation**.

| Method | Ease of implementation | Speed / CPU | Quality (magnification) | Notes |
|--------|-------------------------|-------------|--------------------------|--------|
| **Nearest neighbor** | Easiest | Fastest | Blocky, aliased | Replicates nearest pixel; no blending. |
| **Bilinear** | Easy | Fast | Smooth, some blur | Averages 4 neighbors; first-order interpolation. |
| **Bicubic** | Moderate | Moderate | Sharper, less blur | Uses ~16 neighbors; higher-order polynomial. |
| **Lanczos** | Moderate (often via library) | Slower | Best detail preservation | Sinc-based kernel; can show ringing. |
| **Cubic B-spline / CubicSpline** | Moderate | Moderate | Very smooth, can look soft | Some DICOM SDKs expose this; configurable in others. |
| **GPU-based** | Harder (GPU path) | Very fast when used | Good | Offloads interpolation to GPU; requires GPU pipeline. |

**Quality vs performance:** In general, the more pixels (and the more complex the kernel) used for each output pixel, the better the visual quality and the higher the computational cost. For **interactive** zoom/pan, many viewers prefer **nearest neighbor** or **bilinear** for responsiveness; when the user **stops** interacting, they switch to **bilinear**, **bicubic**, or **SmoothTransformation** for a nicer static view.

---

## 2. DICOM / Medical Viewer Conventions

- **Default behavior:** Many clinical DICOM viewers apply smoothing mainly when **minimizing** (zoom &lt; 1) so that all pixel data contributes to the display. When **magnifying** (zoom &gt; 1), some keep the default as **no smoothing** (nearest/replicate) to avoid the appearance of “enhancing” the image and to keep the displayed image closer to raw pixel replication. This is a conservative, regulatory‑friendly default.
- **User choice:** Giving the user an explicit option (e.g. “Smooth when zoomed” or “Image smoothing”) is common and aligns with the idea that the viewer is a display tool and the user controls presentation.
- **Fast interaction:** For fast operations (windowing, scrolling, zooming, panning), switching to **Replicate** (nearest) mode improves responsiveness; when interaction stops, switching back to a smooth mode improves static image quality.

So a good fit for this project is:

- **Default:** Configurable (e.g. smooth on by default, or off to match “no enhancement”).
- **During zoom/pan:** Use a **simple** method (e.g. nearest or fast bilinear) for responsiveness.
- **When idle:** Use a **smoother** method (e.g. bilinear or Qt’s smooth transformation).
- **User control:** Toggle via **context menu** (on the image viewer) and **View** menu, with state persisted in config if desired.

---

## 3. Qt / PySide6 (Relevant to This Project)

The application uses **PySide6** and **QGraphicsView** with a **QGraphicsPixmapItem** for the DICOM image. Scaling is done by the **view transform** (zoom) and possibly by the way the pixmap is drawn.

### 3.1 View-level: `QPainter.RenderHint.SmoothPixmapTransform`

- **Current state:** In `image_viewer.py`, the view sets `QPainter.RenderHint.SmoothPixmapTransform` (and `Antialiasing`) on the **QGraphicsView**.
- **Effect:** When the view scales the scene (zoom), the painter can use a smooth transformation for the pixmap instead of nearest-neighbor.
- **Performance:** Smooth transformation is more expensive than fast (nearest-neighbor) transformation. Disabling it during drag/zoom and re-enabling when idle is a documented optimization.

### 3.2 Item-level: `QGraphicsPixmapItem.setTransformationMode()`

- **Current state:** The main DICOM **QGraphicsPixmapItem** is created without `setTransformationMode()`; the overlay pixmap in `annotation_manager.py` uses `Qt.TransformationMode.SmoothTransformation`.
- **Important:** For smooth scaling in **QGraphicsView**, both are often needed:
  - View: `view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)`
  - Item: `pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)`
- **Implementation ease:** Toggling smoothing is then:
  - **On:** set render hint on view + `SmoothTransformation` on the main image item.
  - **Off:** remove render hint + set `FastTransformation` on the main image item.

### 3.3 Qt transformation modes

- **`Qt.FastTransformation`:** Nearest-neighbor style; faster, can look blocky when zoomed.
- **`Qt.SmoothTransformation`:** Uses a smooth scaling algorithm (Qt attributes this to an Imlib2-derived smoothscale in `qimagescale.cpp`). Better quality, higher CPU/GPU cost.

No extra libraries are required; both modes are built into Qt and are very easy to use.

### 3.4 Pre-scaled pixmaps (e.g. for magnifier)

Where the code explicitly scales a **QPixmap** (e.g. in `_extract_image_region` for the magnifier), `QPixmap.scaled(..., Qt.TransformationMode.SmoothTransformation)` is already used. For a “smooth when zoomed” feature, the same choice (Smooth vs Fast) can be applied consistently when generating any pre-scaled pixmaps, based on the user’s “smoothing” setting.

---

## 4. Alternative: PIL/Pillow resize (if rendering from numpy/arrays)

If the pipeline ever draws by first resizing a **PIL Image** or numpy array and then converting to QImage/QPixmap:

- **PIL `Image.resize()`** supports:
  - `Image.NEAREST` — fastest, blocky.
  - `Image.BILINEAR` — good balance.
  - `Image.BICUBIC` — better sharpness, slower.
  - `Image.LANCZOS` — best quality for downscaling; more expensive.
- **Speed order (typical):** NEAREST &lt; BILINEAR &lt; BICUBIC &lt; LANCZOS.
- **Use case:** More relevant if we generate a **raster at display resolution** (e.g. pre-render a zoomed tile) instead of relying only on Qt’s transform. For the current design (single full pixmap + view transform), Qt’s transformation mode is the main lever.

---

## 5. Recommended Approach for This Project

### 5.1 Two-tier behavior (simple while interacting, smoother when idle)

1. **During zoom/pan (or when a short “interaction” timer is active):**
   - Use **fast** transformation:
     - View: do **not** set `SmoothPixmapTransform` (or clear it).
     - Item: `image_item.setTransformationMode(Qt.FastTransformation)`.
   - Optionally: reduce overlay updates or use a lower update rate to keep the UI responsive.

2. **When idle (e.g. 200–400 ms after last zoom/pan/scroll):**
   - If the user has **smoothing enabled**:
     - View: set `SmoothPixmapTransform`.
     - Item: `image_item.setTransformationMode(Qt.SmoothTransformation)`.
   - If the user has **smoothing disabled**, keep Fast transformation.

3. **Implementation notes:**
   - Use a **QTimer** to detect “idle”: reset the timer on each transform/scroll event; when the timer fires, switch to the “idle” mode (smooth or fast according to setting).
   - No new dependencies; only Qt APIs.
   - Same pattern can apply to all subwindows that share the same image view behavior.

### 5.2 User option: “Smooth when zoomed” / “Image smoothing”

- **Storage:** A boolean in **config** (e.g. `smooth_image_when_zoomed` or `image_smoothing_enabled`), default to `True` or `False` depending on product preference (see regulatory note above).
- **Context menu (image viewer):** Add a checkable action, e.g. “Smooth when zoomed”, that toggles the option and refreshes the current transformation mode (and persist config).
- **View menu:** Add the same action (or a shared action) under **View** so it’s discoverable and consistent with “Privacy View”, “Reset View”, etc.
- **Behavior:** When the option is **off**, always use `FastTransformation` (and no SmoothPixmapTransform). When **on**, use the two-tier behavior above (fast while interacting, smooth when idle).

### 5.3 Magnifier and export

- **Magnifier:** The magnifier already uses `SmoothTransformation` in `region.scaled(...)`. Use the **same** user setting: when “Smooth when zoomed” is off, use `FastTransformation` there too for consistency.
- **Export:** Export is a separate path (rasterization at export resolution). Smoothing for export can stay as-is (e.g. high-quality resize for PNG/JPEG) and does not need to be tied to the on-screen “Smooth when zoomed” toggle unless you want one global “prefer smooth scaling” that affects both display and export.

---

## 6. Summary Table

| Aspect | Recommendation |
|--------|----------------|
| **Simple method (zoom/pan)** | `Qt.FastTransformation` + no `SmoothPixmapTransform` |
| **Smoother method (idle)** | `Qt.SmoothTransformation` + `SmoothPixmapTransform` |
| **Implementation** | View render hint + `QGraphicsPixmapItem.setTransformationMode()` + idle timer |
| **User control** | Checkable “Smooth when zoomed” (or “Image smoothing”) in context menu and View menu |
| **Config** | Persist boolean; apply at startup and when toggled |
| **Performance** | Fast path during interaction; smooth path only when idle and option on |
| **Regulatory / default** | Consider defaulting smoothing **off** if the product aims for “no enhancement” by default; document that the user can enable it. |

---

## 7. References and Links

- Qt 6: [Smooth Scaling Algorithm](https://doc.qt.io/qt-6/qtgui-attribution-smooth-scaling-algorithm.html) (Imlib2-derived smoothscale in `qimagescale.cpp`).
- Qt: `QImage::scaled()` / `QImage::transformed()` with `Qt::SmoothTransformation` vs `Qt::FastTransformation`.
- Qt Forum: Image scaling quality with `QGraphicsPixmapItem`; smooth rescaling in `QGraphicsView`; need both view render hints and item transformation mode.
- DICOM: Displayed Area Module (e.g. MAGNIFY, SCALE TO FIT); interpolation is not mandated; user-controlled smoothing is a common pattern.
- PIL/Pillow: `Image.resize()` filters (NEAREST, BILINEAR, BICUBIC, LANCZOS) for any future pre-rendered or export path.

---

*Document created for DICOM Viewer V3 to guide implementation of optional image smoothing when magnified, with simple behavior during zoom/pan and smoother behavior when idle.*
