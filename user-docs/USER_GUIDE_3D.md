# User guide — 3D volume rendering

**Last updated:** 2026-05-31

The viewer can open a **GPU-accelerated 3D volume render** of the **focused** 2D subwindow’s series. This is a **separate** non-modal dialog; it does not replace the multi-pane 2D layout.

## Requirements

- **VTK** (`vtk>=9.3.0` in `requirements.txt`). If VTK is not installed, the app shows an install hint when you use **3D View**.
- A **multi-slice** series in the focused pane (at least **3** instances with consistent geometry). Single-slice or empty panes show an informational message instead of opening the dialog.

## Where to find it

| Location | Action |
|----------|--------|
| **Toolbar** | **3D View** (cube icon; after **MPR** on the main toolbar) |
| **Tools** | **3D Volume Render…** |

Both use the **currently focused** image subwindow’s series.

## How it works

1. The app builds a **3D volume** from the same DICOM stack used for MPR (`MprVolume` / SimpleITK): slice order, spacing, and orientation from DICOM geometry tags.
2. The volume is converted for **VTK** and drawn with **volume ray casting** (not surface meshes). What you see is a blend of all voxels along each view ray, controlled by a **transfer function** (opacity and color vs. intensity/HU).
3. **Built-in presets** define typical opacity ramps (e.g. CT Bone, CT Soft Tissue, MR Default). **Window / Level** and **Threshold** scale and shift where tissue becomes visible without editing the curve by hand.
4. **Opacity** scales the whole volume up or down, with a **perceptual** slider that puts most of its travel in the low-opacity range where small changes are visible. **Contrast depth** reshapes the opacity curve independently of overall opacity.
5. Rendering runs in a **background thread** while the dialog shows progress; VTK interaction runs on the main thread after load completes.

> **Scalar values are raw, not calibrated.** The 3D path feeds VTK the **raw stored pixel values** from the series (rescale slope/intercept is **not** applied), so CT thresholds are **not** true Hounsfield units. The control panel shows the active scalar domain under the preset (e.g. *“CT — raw pixel values (not calibrated HU)”*) so threshold/window numbers are read honestly.

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
| **Background** | Viewport background colour: Black, Dark Gray, Light Gray, or White. |
| **Reset Camera** | Default 3D view orientation and framing. |
| **Help…** | Opens this guide in your web browser (requires network for GitHub-hosted docs in release builds). |

## Tips

- If 2D viewing looks wrong (spacing, orientation), fix or reload the series before relying on 3D — the 3D volume uses the same geometry as MPR.
- **Fusion**, **MPR panes**, and **3D** are independent: 3D always uses the **underlying DICOM series** in the focused 2D pane, not a fused composite or MPR slab.
- For **PET/CT fusion** or **MPR** workflows, see [IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md](IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md) and [USER_GUIDE_MPR.md](USER_GUIDE_MPR.md).
- Large volumes may be slow on integrated GPUs; VTK may use a CPU ray-cast path on some systems.

## Export (not yet available)

Saving the current 3D view as a **PNG/JPG image** or as a **Secondary Capture (SC) DICOM** series is planned; see [dev-docs/TO_DO.md](../dev-docs/TO_DO.md) under **3D visualization**. Until then, use your OS screenshot tools for a quick capture of the viewport.

## Roadmap / limitations

- No **fusion overlay** in the 3D view.
- No full **transfer-function curve editor** in the UI yet (saved presets store control values, not arbitrary curves).
- No in-app **export** of the 3D render to image or DICOM yet.
- Large volumes may need a future memory warning or optional downsampling.

## Technical detail

Implementation plan and checklist: [3D_VOLUME_RENDERING_PLAN.md](../dev-docs/plans/3D_VOLUME_RENDERING_PLAN.md).

Secondary Capture background (for planned DICOM export): [DICOM_GSPS_KO_SECONDARY_CAPTURE.md](../dev-docs/info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md).
