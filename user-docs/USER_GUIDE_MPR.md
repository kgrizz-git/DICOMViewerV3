# User guide — MPR (multi-planar reformation)

**Last updated:** 2026-10-09

MPR lets you build **orthogonal views** (e.g. sagittal / coronal) from an axial stack (or another base orientation), shown inside a viewer pane. You can keep **several MPRs at once**, park them as **navigator tiles** while you work on something else, show the same MPR in more than one window, and optionally **link** those windows so they scroll together.

In this guide a **session** is one MPR you built, and a **view** is one window or tile showing it. Duplicating an MPR makes another view of the same session; it does not rebuild or copy the volume.

## Opening MPR

1. Load a suitable **3D series** (multiple slices with consistent geometry).
2. Focus the **subwindow** where you want the MPR.
3. **Right-click** the image → **Create MPR View…**  
   (If that pane is already an MPR, you will see **Clear MPR View** instead.)

4. In **Create MPR View**, pick the **series** (defaults to the focused window’s series), **orientation** (axial / coronal / sagittal), **output spacing/thickness**, and optional **Combine Slices** (projection type and number of planes—same choices as the right pane, with approximate slab extent in mm shown in parentheses), then confirm.

The pane switches to the MPR for that configuration. Afterward you can change combine settings from the right pane; window/level stays fixed when you do (same as for a normal 2D series).

**Tools → Create MPR View…** and the toolbar **MPR** button use the focused window. Building a new MPR **never discards** an MPR you already have: if the window already shows an MPR, that one moves to the navigator as a tile, and an MPR built from the same series stays alongside the new one as its own session.

While an MPR is being built, the status bar shows how many sessions and views you are using. When it finishes you see the same line again, for example `MPR: 2/8 sessions, 3/16 views, about 410 MiB (estimate)`. See [Limits and memory](#limits-and-memory).

## Clearing, detaching, and removing MPR

- **Right-click** the MPR pane's image background (not on an ROI) → **Clear This Window** **detaches** the MPR: the window returns to what it showed before the MPR (or goes empty), and the MPR stays in the series navigator as a tile with its slice, combine, window/level, inversion and look-up table preserved. Use this to park an MPR.
- **Right-click** the MPR pane → **Clear MPR View** (or **Clear MPR** on its navigator tile) **removes** that view for good and returns the window to normal 2D viewing for its assigned series. If it was the last view of its session, the MPR is released.
- Closing the **source series or study**, **File → Close All**, or opening files with a normal (replace) open removes every MPR built from the closed data, including detached tiles. Detached MPRs are kept only while the application runs; they are not saved across restarts.
- A window showing an MPR cannot be assigned a series by drag or double-click. The app asks you to clear the MPR first, so nothing is overwritten.

## MPR tiles in the series navigator

Every MPR view, attached or detached, has a tile in the series navigator, placed after the series it was built from, in the order the views were created.

| On the tile | Meaning |
|-------------|---------|
| **MPR** badge | An MPR tile |
| Digit, top right | The window currently showing it (no digit while detached) |
| Number, bottom left | Slices in the MPR (follows **View → Show Slice/Frame Count on Navigator Thumbnails**) |
| Tag, bottom right | `S2` = session 2. `S2.1`, `S2.2` = first and second view of a shared session. A trailing `L` (`S2.1L`) means the view is linked |

Hover a tile for a description: orientation, session and view number, whether it is linked, and where it is. For a detached tile the tooltip also shows its position in the stack (for example `slice 9 of 40`). Tile text never contains patient information.

- **Click** a tile to focus the window showing it. A detached tile has no window, so a click does nothing.
- **Drag** a tile onto a window to **move** it there (an attached MPR moves; a detached one attaches). If the target window already shows an MPR, that MPR is **kept as a detached tile**, not discarded; a window showing an ordinary series is restored when you later clear the MPR. The MPR is fitted to its new window. If a drop cannot complete (for example the display fails), both the MPR and the target window are left exactly as they were.
- **Right-click** a tile for **Duplicate into Window…**, **Duplicate Linked into Window…**, **Unlink View** (enabled only while the view is linked) and **Clear MPR**. Each acts on exactly the tile you clicked.

## Duplicating an MPR

**Duplicate into Window…** shows a menu of the windows that are currently visible in your layout (windows hidden by the layout, such as the fourth window in a three-pane layout, are not listed). The window already showing that MPR is listed but disabled. Choose a window and the MPR appears there as a new view that:

- shares the original's volume and slices (no copy, no extra volume memory);
- starts at the original's slice, with the original's combine setting, window/level, inversion and look-up table, and then keeps its own from then on;
- can be a duplicate of an attached **or detached** tile; a detached original stays detached.

If you choose a window that already shows an MPR, that MPR is kept as a detached tile. A duplicate counts as one **view**, not a new session. If the duplicate cannot be shown, nothing changes and no space is used. If you are at the view limit, you are told which limit and the current counts.

## Linked scrolling

**Duplicate Linked into Window…** works like Duplicate, and also **links** the two views (or adds the new one to the group the original already belongs to). Linked views scroll **together**: the mouse wheel, **↑/↓** keys, the in-window slice slider and **cine** playback on any of them move all of them to the same slice, in either direction. Everything else stays separate for each view: window/level, inversion, look-up table, combine settings, and zoom/pan.

- Linking only ever joins views of the **same MPR**. It does not depend on **View → Slice Sync**, which can be on or off.
- If a linked view is **detached**, it still follows the group silently; its tooltip shows its slice, and when you attach it again it shows the group's current slice.
- **Unlink View** on a tile removes that view from its group (when only two were linked, both become independent). Clearing one of two linked views also unlinks the other. Moving or detaching a view keeps it linked.
- Playing cine moves the linked group. There is still one cine player, and it follows whichever window is focused. A manual step pauses playback as usual.

### With Slice Sync

If a linked MPR is also in a **View → Slice Sync** group with other panes, a linked group acts as **one scrolling unit**:

- scrolling an MPR in the group moves its linked partners and the other panes in the sync group;
- scrolling a different pane in that sync group moves the whole linked group once (not once per member);
- a linked partner that belongs to a **different** sync group follows its partner but does **not** drag that other group along.

As elsewhere, Slice Sync only updates a pane when the matching position lies inside that series' coverage.

## Limits and memory

You can have up to **8 sessions** and **16 views** by default, counting attached views, detached tiles and MPRs still being built. Change them in **Edit → Settings… → MPR Limits** (**Maximum MPR sessions**, **Maximum MPR views**; the view limit cannot be lower than the session limit). The change applies to the next MPR you create, with no restart. Lowering a limit never closes anything; it only stops new ones until you are under it.

- Building a new MPR needs one free session **and** one free view (even over a window that shows an MPR, because the old one is kept). A duplicate needs one free view. Moving, detaching and attaching need nothing.
- At a limit you get a message naming it with the current counts, for example `MPR session limit reached (8/8)`, followed by a usage line. Clear a view or a session you no longer need and try again.
- The usage line (`MPR: 2/8 sessions, 3/16 views, about 410 MiB (estimate)`) is an **approximate** estimate of the memory the MPRs use, counting shared volumes and slices once. It is there to help you judge; it is **not** a memory limit, nothing is refused because of it, and it does not include the image data you already have loaded. The real memory use of the application is higher.

## Saving MPR as DICOM

When an MPR stack is complete, use **File → Save MPR as DICOM…** to write one
derived DICOM instance per plane. It saves the MPR in the **focused window**, so attach a detached tile to a window first. The dialog can apply the same **DICOM metadata
de-identification** settings and presets as the normal DICOM export path.

> **Important:** this setting applies to DICOM metadata, not patient information
> burned into image pixels. Review the detailed [de-identified export guide](USER_GUIDE_ANONYMIZATION.md)
> and your organization's required process before sharing an MPR export.

## Tips

- MPR uses the same **window/level** and navigation patterns as other viewers where applicable; exact behavior follows the focused pane.
- **Direction labels** (if enabled under **View**) follow the **reformatted MPR plane** (patient LPS, from the output row/column directions), not the original series orientation. On strongly **oblique** planes, a side may show **two letters** (e.g. anterior and right) when the in-plane direction lines up between two anatomical axes.
- For **slice sync**, **cine loop bounds**, **side panes**, and navigator options, see [USER_GUIDE_LAYOUTS.md](USER_GUIDE_LAYOUTS.md) (and the application **View** menu). Multi-window layout shortcuts remain `1`–`4`.

## Technical and roadmap detail

Implementation notes and planned enhancements for slice sync and MPR are tracked in the project's developer documentation, maintained separately from these user guides.
