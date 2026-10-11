# User guide — MPR (multi-planar reformation)

**Last updated:** 2026-10-10

MPR lets you build **orthogonal views** (e.g. sagittal / coronal) from an axial stack (or another base orientation), shown inside a viewer pane. Several MPRs can be kept at once, including more than one built from the same series; each built MPR is a **session** with its own admission slot.

## Opening MPR

1. Load a suitable **3D series** (multiple slices with consistent geometry).
2. Focus the **subwindow** where you want the MPR.
3. **Right-click** the image → **Create MPR View…**  
   (If that pane is already an MPR, you will see **Clear MPR View** instead.)

4. In **Create MPR View**, pick the **series** (defaults to the focused window’s series), **orientation** (axial / coronal / sagittal), **output spacing/thickness**, and optional **Combine Slices** (projection type and number of planes—same choices as the right pane, with approximate slab extent in mm shown in parentheses), then confirm.

The pane switches to the MPR for that configuration. Afterward you can change combine settings from the right pane; window/level stays fixed when you do (same as for a normal 2D series).

Building a new MPR **never discards** an MPR you already have: if the window already shows an MPR, the earlier result stays in the session registry and keeps its admission slot until its source data is closed or the app restarts; its window is taken over by the new MPR. While an MPR is being built, the status bar shows how many sessions and views you are using; when it finishes you see the same line again (see [Limits and memory](#limits-and-memory)).

## Clearing MPR

- **Right-click** the MPR pane → **Clear MPR View** to return that pane to normal 2D viewing for its assigned series. If it was the last view of its session, the MPR is released and its space is freed.
- **Clear This Window** is temporarily unavailable on a pane that shows an MPR — use **Clear MPR View** instead.
- Closing the **source series or study**, **File → Close All**, or opening files with a normal (replace) open removes every MPR built from the closed data. MPR sessions are kept only while the application runs; they are not saved across restarts.

## Limits and memory

You can have up to **8 sessions** by default (counting MPRs still being built); each session's window and any kept displaced result count as **views** against the **Maximum MPR views** limit (default **16**, never below the session limit). Change both in **Edit → Settings… → MPR Limits**. The change applies to the next MPR you create, with no restart. Lowering a limit never closes anything; it only stops new ones until you are under it.

- Building a new MPR needs one free session. At the limit you get a message naming it with the current counts, for example `MPR session limit reached (8/8)`, followed by a usage line.
- The usage line (`MPR: 2/8 sessions, 2/16 views, about 410 MiB (estimate)`) shows the approximate memory the MPR sessions use, counting shared volumes and slices once. It is there to help you judge; it is **not** a memory limit, nothing is refused because of it, and it does not include the image data you already have loaded. The real memory use of the application is higher.

## Saving MPR as DICOM

When an MPR stack is complete, use **File → Save MPR as DICOM…** to write one
derived DICOM instance per plane. It saves the MPR in the **focused window**.
The dialog can apply the same **DICOM metadata de-identification** settings and
presets as the normal DICOM export path.

> **Important:** this setting applies to DICOM metadata, not patient information
> burned into image pixels. Review the detailed [de-identified export guide](USER_GUIDE_ANONYMIZATION.md)
> and your organization's required process before sharing an MPR export.

## Tips

- MPR uses the same **window/level** and navigation patterns as other viewers where applicable; exact behavior follows the focused pane.
- **Direction labels** (if enabled under **View**) follow the **reformatted MPR plane** (patient LPS, from the output row/column directions), not the original series orientation. On strongly **oblique** planes, a side may show **two letters** (e.g. anterior and right) when the in-plane direction lines up between two anatomical axes.
- For **slice sync**, **cine loop bounds**, **side panes**, and navigator options, see [USER_GUIDE_LAYOUTS.md](USER_GUIDE_LAYOUTS.md) (and the application **View** menu). Multi-window layout shortcuts remain `1`–`4`.

## Technical and roadmap detail

Implementation notes and planned enhancements for slice sync and MPR are tracked in the project's developer documentation, maintained separately from these user guides.
