# User guide — 3D volume rendering

**Last updated:** 2026-10-08

The viewer can open a **GPU-accelerated 3D volume render** of the **focused** 2D subwindow’s series. This is a **separate** non-modal dialog; it does not replace the multi-pane 2D layout.

## Requirements

- **VTK** (`vtk>=9.3.0` in `requirements.txt`). If VTK is not installed, the app shows an install hint when you use **3D View**.
- A **multi-slice** series in the focused pane (at least **3** instances with consistent geometry). Single-slice or empty panes show an informational message instead of opening the dialog.

## Where to find it

| Location | Action |
|----------|--------|
| **Toolbar** | **3D View** (cube icon; after **MPR** on the main toolbar) |
| **Tools** | **3D Volume Render…** |
| **File** | **Save 3D View…** saves an open 3D window (see [Saving the 3D view](#saving-the-3d-view)) |

Both use the **currently focused** image subwindow’s series.

## How it works

1. The app builds a **3D volume** from the same DICOM stack used for MPR (`MprVolume` / SimpleITK): slice order, spacing, and orientation from DICOM geometry tags.
2. The volume is converted for **VTK** and drawn with **volume ray casting** (not surface meshes). What you see is a blend of all voxels along each view ray, controlled by a **transfer function** (opacity and color vs. intensity/HU).
3. **Built-in presets** define typical opacity ramps (e.g. CT Bone, CT Soft Tissue, MR Default). **Window / Level** and **Threshold** scale and shift where tissue becomes visible without editing the curve by hand.
4. **Opacity** scales the whole volume up or down, with a **perceptual** slider that puts most of its travel in the low-opacity range where small changes are visible. **Contrast depth** reshapes the opacity curve independently of overall opacity.
5. Volume construction runs in a **background thread** while the dialog shows progress. VTK interaction and drawing run on the main thread after load completes; the first visible image is a fast preview and may refine automatically on capable hardware.

> **Scalar values are shown honestly.** When complete, valid DICOM rescale metadata is available, the 3D path uses calibrated values (for example, CT HU). Otherwise it uses raw stored pixel values. The control panel identifies the active scalar domain, so threshold/window values can be interpreted correctly.

You can keep **multiple** 3D dialogs open (one per series key). Opening the same series again **focuses** the existing dialog instead of creating a duplicate.

## Mouse interaction (viewport)

| Action | Control |
|--------|---------|
| **Rotate** | Left-drag |
| **Zoom** | Right-drag or scroll wheel |
| **Pan** | Middle-drag |

Use **Reset Camera** to return to the default anterior view with the patient’s head toward the top of the screen.

## Control panel

| Control | What it does |
|---------|----------------|
| **Preset** | Built-in transfer functions (CT Bone, CT Soft Tissue, CT Lung, MR presets, etc.). **MR** series default to **MR Default**; **CT** defaults to **CT Bone**. Saved custom presets appear below the built-ins. |
| **Save Preset…** | Saves the **current** base preset plus **opacity**, **window**, **level**, and **threshold** under a name you choose. Stored in your user config and listed in the preset dropdown. Overwrites if the name already exists. |
| **Opacity** | Overall transparency. The slider uses a **perceptual** response so the low-opacity range (where faint structures matter) gets fine control; the **Opacity %** spinbox shows the resolved percent and accepts direct entry (sub-percent steps below 10%). |
| **Window** | **Scales the transfer-function width** in scalar units. Narrower = sharper contrast over a smaller range; wider spreads the curve out. Setting it back to the preset’s natural width reproduces the preset. |
| **Level** | Recenters the transfer function. Shifts which intensities appear brightest. When you change a built-in preset, Window/Level reset to that preset’s natural range. |
| **Threshold** | Shifts opacity onset along the intensity axis (−500 to +500). **Positive** hides more low-density material; **negative** reveals more. Resets to 0 when you pick a new built-in preset. |
| **Contrast depth** | Reshapes the opacity curve independently of overall opacity. Center is neutral; lower reveals faint material, higher deepens contrast so dense/internal structures stand out. |
| **Detail / Auto** | Detail controls ray-sampling quality. Auto selects detail from the preset and limits it for large volumes; the viewer starts with a Fast preview and refines only when the preview is responsive. Select High or Ultra manually when you want more detail and accept a potentially slower render. |
| **Background** | Viewport background colour: Black, Dark Gray, Light Gray, or White. |
| **Reset Camera** | Default 3D view orientation and framing. |
| **Save Image…** | Saves the current 3D view as PNG, JPG, or DICOM Secondary Capture (shortcut **Ctrl+S**). Available once the first frame is drawn. |
| **Help…** | Opens this guide in your web browser (requires network for GitHub-hosted docs in release builds). |

## Tips

- If 2D viewing looks wrong (spacing, orientation), fix or reload the series before relying on 3D — the 3D volume uses the same geometry as MPR.
- **Fusion**, **MPR panes**, and **3D** are independent: 3D always uses the **underlying DICOM series** in the focused 2D pane, not a fused composite or MPR slab.
- For **PET/CT fusion** or **MPR** workflows, see [IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md](IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md) and [USER_GUIDE_MPR.md](USER_GUIDE_MPR.md).
- Large volumes may be slow on integrated GPUs; VTK may use a CPU ray-cast path on some systems.
- If the viewer keeps a Fast preview and says higher detail may be slow, it avoided an automatic render likely to make the window unresponsive. You can still select a higher Detail level manually.

## Window controls

- **Minimize and maximize:** the 3D window has standard minimize and maximize buttons.
- **View → Keep 3D Viewer in Front** (on by default) keeps 3D windows above the main viewer while you use the app. They drop behind other applications when you switch away, and they never cover the viewer's own dialogs. The setting is remembered. On Windows it has no effect yet; full keep-in-front is still being verified there.
- **View → Show 3D Viewer** hides or shows the 3D window you used most recently. Hiding keeps the volume loaded, so showing it again is instant. Opening **3D View** again for the same series also brings back a hidden or minimized window instead of rebuilding it.

## Saving the 3D view

You can save the current 3D view in three ways:

- Click **Save Image…** in the 3D window's control panel.
- Press **Ctrl+S** while the 3D window is active.
- Choose **File → Save 3D View…** in the main window. It is available while a 3D window is open. With several 3D windows open, it saves the one you used most recently.

Saving is unavailable until the first frame is drawn. You can save the view as an image (PNG or JPG) or as a DICOM Secondary Capture.

1. Choose a **Format**: **PNG**, **JPG**, or **DICOM (Secondary Capture)**.
2. For PNG or JPG, you can tick **Burn in overlay text**. This draws the top-left overlay (preset, opacity, detail, blend mode) onto the image. It never adds patient or study text. It is off by default.
3. For DICOM, **De-identify** is on by default. It removes patient identity from the saved file. Turn it off only when the file stays inside your organisation.
4. Choose where to save. The suggested name uses the preset and the time, for example `3D_CT_Bone_20261007-142501.png`. It never contains patient details.

The viewer remembers your format and option choices. The save captures the current viewport at its rendered resolution. That is the viewport's device-pixel size, so it is larger than the on-screen size on high-DPI displays.

Preset names you saved yourself are never written into filenames, burned-in text, or DICOM files. They appear as **Custom preset** instead. Built-in preset names are kept.

A DICOM file is a single-frame RGB **Secondary Capture** in a new series. It copies the patient, study, and equipment details of the source series unless you de-identify it. Its series number is the source series number plus 700, or 701 when the source has no series number. It records the preset and blend mode as its derivation, and it carries no 3D geometry.

## Roadmap / limitations

- No **fusion overlay** in the 3D view.
- No full **transfer-function curve editor** in the UI yet (saved presets store control values, not arbitrary curves).
- Saving captures the current viewport at its rendered (device-pixel) resolution. A separate higher-resolution re-render is not available yet.
- Large volumes may need a future memory warning or optional downsampling.

## Technical detail

A transfer-function curve editor is tracked as a roadmap item above. See the in-repo user documentation set
for the current feature list; implementation-plan and design notes are maintained
separately from these user docs.

Secondary Capture background for the DICOM save option. Online contributor notes (requires network): [DICOM GSPS / KO / Secondary Capture](https://github.com/kgrizz-git/DICOMViewerV3/blob/main/dev-docs/info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md).
