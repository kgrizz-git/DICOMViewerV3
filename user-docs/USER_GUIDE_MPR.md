# User guide — MPR (multi-planar reformation)

**Last updated:** 2026-08-31

MPR lets you build **orthogonal views** (e.g. sagittal / coronal) from an axial stack (or another base orientation), shown inside a viewer pane.

## Opening MPR

1. Load a suitable **3D series** (multiple slices with consistent geometry).
2. Focus the **subwindow** where you want the MPR.
3. **Right-click** the image → **Create MPR View…**  
   (If that pane is already an MPR, you will see **Clear MPR View** instead.)

4. In **Create MPR View**, pick the **series** (defaults to the focused window’s series), **orientation** (axial / coronal / sagittal), **output spacing/thickness**, and optional **Combine Slices** (projection type and number of planes—same choices as the right pane, with approximate slab extent in mm shown in parentheses), then confirm.

The pane switches to the MPR for that configuration. Afterward you can change combine settings from the right pane; window/level stays fixed when you do (same as for a normal 2D series).

## Clearing MPR

- **Right-click** the MPR pane → **Clear MPR View** to return that pane to normal 2D viewing for its assigned series.

## Saving MPR as DICOM

When an MPR stack is complete, use **File → Save MPR as DICOM…** to write one
derived DICOM instance per plane. The dialog can apply the same **DICOM metadata
de-identification** settings and presets as the normal DICOM export path.

> **Important:** this setting applies to DICOM metadata, not patient information
> burned into image pixels. Review the detailed [de-identified export guide](USER_GUIDE_ANONYMIZATION.md)
> and your organization's required process before sharing an MPR export.

## Tips

- MPR uses the same **window/level** and navigation patterns as other viewers where applicable; exact behavior follows the focused pane.
- **Direction labels** (if enabled under **View**) follow the **reformatted MPR plane** (patient LPS, from the output row/column directions), not the original series orientation. On strongly **oblique** planes, a side may show **two letters** (e.g. anterior and right) when the in-plane direction lines up between two anatomical axes.
- For **slice sync** or advanced layout behavior, see the application **View** menu and multi-window layout shortcuts (`1`–`4`).

## Technical and roadmap detail

Implementation notes and planned enhancements for slice sync and MPR are tracked in the project's developer documentation, maintained separately from these user guides.
