# Measurements & annotations

**Last updated:** 2026-06-16

The viewer provides ROIs, measurements, and annotations you draw directly on an image, plus per-ROI statistics. Tools are on the **main toolbar**; each has a single-key shortcut and they are **mutually exclusive** — picking one leaves the others off until you switch back to **Pan** or **Select**.

## Tools and shortcuts

| Tool | Key | What it does |
|------|-----|--------------|
| **Pan / scroll** | **P** | Default mode: drag to pan, wheel to scroll slices. |
| **Select** | **S** | Click an annotation/ROI to select it (see *Editing* below). |
| **Ellipse ROI** | **E** | Drag to draw an elliptical region of interest. |
| **Rectangle ROI** | **R** | Drag to draw a rectangular region of interest. |
| **Linear measurement** | **M** | Click two points; reports distance (mm when pixel spacing is known, else pixels). |
| **Angle measurement** | **Shift+M** | Three clicks — the **middle** click is the vertex; reports the angle between the two segments. |
| **Text annotation** | **T** | Click to place a text label; type your text. |
| **Arrow annotation** | **A** | Drag to place an arrow. |
| **Crosshair** | **H** | Place a crosshair marker (reports the pixel value/position). |
| **Zoom** | **Z** | Drag to zoom the image. |
| **Magnifier** | **G** | Hover a movable magnifier loupe over the image. |
| **Window/Level from ROI** | **W** | Drag a region; the viewer auto-sets window/level from the pixels inside it. |

ROIs, measurements, and annotations are tracked **per slice/frame** and persist as you scroll back to that image.

## Editing

- **Select an item:** switch to **Select (S)** and click it. (You can also double-click an ROI in the **ROI list** on the left pane.)
- **Resize an ROI:** selecting a **rectangle or ellipse** ROI automatically shows corner/edge **resize handles** — drag them to reshape. Click elsewhere or change tools to leave edit mode.
- **Move a measurement:** drag either endpoint to reposition it.
- **Edit text:** **double-click** a text annotation to edit it inline.
- **Delete:** select an item and press **Delete**, or **right-click → Delete …**. **Delete all ROIs on the current slice** is **D**.

### Copy / cut / paste

Under the **Edit** menu (standard shortcuts):

- **Copy Annotation** — **Ctrl+C**
- **Cut Annotation** — **Ctrl+X** (copies, then deletes the selection)
- **Paste Annotation** — **Ctrl+V**

This works across slices and panes, so you can replicate an ROI or measurement onto another image.

## ROI statistics

Each ROI can show statistics as a **draggable on-image overlay** and in the **right-hand statistics panel**. Choose which metrics appear in two ways:

- **Per-ROI:** right-click an ROI → toggle **Show statistics overlay** and the individual metrics — **Mean, Std Dev, Min, Max, Pixels, Area**.
- **Defaults for new ROIs:** **View → Annotation Options…** has a *Statistics* group with the same checkboxes, plus **per-channel statistics** for multi-channel images (per-channel mean/std/min/max). For three-channel images, channel titles follow `PhotometricInterpretation` (R/G/B, Y/Cb/Cr, …), otherwise `Ch0/Ch1/Ch2`.

Units follow the viewer's **Raw / Rescaled** mode and the dataset's `RescaleType` (e.g. HU, SUV) where available.

**Export:** **Tools → Export ROI Statistics** writes ROIs, crosshairs, and distance/angle measurements per slice (TXT and XLSX sections; CSV adds trailing measurement columns). See the [hub guide](USER_GUIDE.md#general-viewing-2d) for the full export note.

## Appearance

**View → Annotation Options…** sets default **font size, line thickness, and color** independently for **ROIs**, **measurements**, and **text annotations**. Defaults are intentionally compact (line thickness ~3, font ~12) and your changes are remembered.

> Annotations are app-native overlays. They are **not** written into exported DICOM pixel data and are **not** exported as DICOM GSPS yet (GSPS export is planned). Use **Export Screenshots** or **Export ROI Statistics** to capture them.

---

See also: [USER_GUIDE.md](USER_GUIDE.md) (hub) · [USER_GUIDE_MPR.md](USER_GUIDE_MPR.md) · [CONFIGURATION.md](CONFIGURATION.md).
