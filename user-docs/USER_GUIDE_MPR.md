# User guide — MPR (multi-planar reformation)

MPR lets you build **orthogonal views** (e.g. sagittal / coronal) from an axial stack (or another base orientation), shown inside a viewer pane.

## Opening MPR

1. Load a suitable **3D series** (multiple slices with consistent geometry).
2. Focus the **subwindow** where you want the MPR.
3. **Right-click** the image → **Create MPR View…**  
   (If that pane is already an MPR, you will see **Clear MPR View** instead.)

4. In **Create MPR View**, pick the **series** (defaults to the focused window’s series), **orientation** (axial / coronal / sagittal), and other options shown in the dialog, then confirm.

The pane switches to the MPR for that configuration.

## Clearing MPR

- **Right-click** the MPR pane → **Clear MPR View** to return that pane to normal 2D viewing for its assigned series.

## Tips

- MPR uses the same **window/level** and navigation patterns as other viewers where applicable; exact behavior follows the focused pane.
- For **slice sync** or advanced layout behavior, see the application **View** menu and multi-window layout shortcuts (`1`–`4`).

## Technical and roadmap detail

For implementation notes and planned enhancements, see [SLICE_SYNC_AND_MPR_PLAN.md](../dev-docs/plans/SLICE_SYNC_AND_MPR_PLAN.md) and related plans under `dev-docs/plans/`.
