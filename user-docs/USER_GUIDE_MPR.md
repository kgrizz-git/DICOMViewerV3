# User guide — MPR (multi-planar reformation)

**Last updated:** 2026-10-10

MPR lets you build **orthogonal views** (e.g. sagittal / coronal) from an axial stack (or another base orientation), shown inside a viewer pane. Several MPRs can be kept at once, including more than one built from the same series; each built MPR is a **session** with its own admission slot.

## Opening MPR

Use **Tools → Create MPR View…** or the toolbar **MPR** button for the focused window; pick the source series and reconstruction settings in the dialog. The pane switches to the MPR for that configuration. Afterward you can change combine settings from the right pane; window/level stays fixed when you do (same as for a normal 2D series).

Building a new MPR **never discards** an MPR you already have: if the window already shows an MPR, the earlier one is preserved and its space stays accounted for. While an MPR is being built, the status bar shows how many sessions and views you are using; when it finishes you see the same line again (see [Limits and memory](#limits-and-memory)).

## Clearing an MPR

- **Right-click** the MPR pane → **Clear MPR View** removes the MPR and returns the pane to normal 2D viewing for its assigned series. If it was the last view of its session, the MPR is released and its space is freed.
- **Clear This Window** is temporarily unavailable on a pane that shows an MPR — use **Clear MPR View** instead.
- Closing the **source series or study**, **File → Close All**, or opening files with a normal (replace) open removes every MPR built from the closed data. MPR sessions are kept only while the application runs; they are not saved across restarts.

## Limits and memory

You can have up to **8 sessions** by default (counting MPRs still being built). Change the limit in **Edit → Settings… → MPR Limits** (**Maximum MPR sessions**). The change applies to the next MPR you create, with no restart. Lowering a limit never closes anything; it only stops new ones until you are under it.

- At the limit you get a message naming it with the current counts, for example `MPR session limit reached (8/8)`, followed by a usage line.
- The usage line (`MPR: 2/8 sessions, 1/8 views, about 410 MiB (estimate)`) is an **approximate** estimate of the memory the MPRs use, counting shared volumes and slices once. It is there to help you judge; it is **not** a memory limit, nothing is refused because of it, and it does not include the image data you already have loaded. The real memory use of the application is higher.

## Saving MPR as DICOM

When an MPR stack is complete, use **File → Save MPR as DICOM…** to write one
derived DICOM instance per plane. It saves the MPR in the **focused window**. The dialog can apply the same **DICOM metadata
de-identification** settings and presets as the normal DICOM export path.

> **Important:** this setting applies to DICOM metadata, not patient information
> that is already inside the pixels. See
> [Anonymization](USER_GUIDE_ANONYMIZATION.md).
