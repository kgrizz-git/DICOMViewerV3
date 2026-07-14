# Multi-window layouts & navigation

**Last updated:** 2026-06-16

The viewer shows your images in **panes** (subwindows). You can split the viewing area into several panes, put a different series in each, and move between slices and frames. This guide covers the pane layouts, how to fill and focus panes, and the basics of slice/cine navigation.

> Looking for the key bindings only? See the [keyboard-shortcut reference](USER_GUIDE_SHORTCUTS.md). For drawing tools see [Measurements & annotations](USER_GUIDE_ANNOTATIONS.md).

## Choosing a layout

Pick a layout from **View → Layout**, or press the number keys. There are eight arrangements: single, the two side-by-side / stacked splits, four **asymmetric 3-pane** layouts, and the 2×2 grid.

| Layout | Menu (**View → Layout**) | Key |
|--------|--------------------------|-----|
| Single pane | **1×1** | **1** |
| Two side by side | **1×2** | **2** (toggles 1×2 ↔ 2×1) |
| Two stacked | **2×1** | **2** (toggles 1×2 ↔ 2×1) |
| Large left + 2 right | **Large left + 2 right (3)** | **3** (cycles the four 3-pane layouts) |
| 2 left + large right | **2 left + large right** | **3** |
| Large top + 2 bottom | **Large top + 2 bottom** | **3** |
| 2 top + large bottom | **2 top + large bottom** | **3** |
| Four-pane grid | **2×2** | **4** |

Notes on the keys:

- **2** *toggles* between **1×2** (side by side) and **2×1** (stacked) each time you press it.
- **3** *cycles* through the four asymmetric 3-pane layouts. In the 3-pane layouts the large pane takes roughly **two-thirds** of its row or column (a fixed **2:1** ratio); the divisions are not drag-resizable today (see *Limitations* below).
- The number keys are **ignored while you are editing a text annotation**, so typing digits into a text box works normally. Holding **Ctrl/Cmd** also passes the keys through to standard shortcuts.

## Filling panes with series

Each pane can hold its own series:

- **Drag a series** (or instance) from the **series navigator** and drop it onto the pane you want it in.
- The pane you last clicked is the **focused** pane (highlighted border). Loading a new study, or actions that target "the current image," apply to the focused pane.

Switching layouts keeps each pane's assigned series — the 3-pane layouts simply **hide** the fourth pane rather than discarding it, so its series is still there when you return to a four-pane layout.

## Focus, expanding, and swapping

- **Focus:** click a pane to focus it (its border highlights). Slice navigation, window/level, tools, and most single-target actions act on the focused pane.
- **Expand to single pane (double-click):** double-click the image or background of a pane to blow it up to **1×1**. Double-click again to **revert** to the layout you were just in (or 2×2 if there was none). This is a quick way to inspect one pane full-size and jump back.
- **Swap panes:** the image **right-click** menu offers **Swap with View …** to exchange the contents of two panes (their slot positions swap in every layout; focus stays put).
- **Clear This Window:** **right-click** the image background (not on an ROI) → **Clear This Window** removes the series from **that pane only**. Loaded studies and series remain in the navigator.

## Series navigator

- Toggle the series navigator with **N** (or the View menu / toolbar). It lists loaded studies and series; double-click or drag entries to load them into a pane.

## Slice & cine navigation

- **Next / previous slice:** **↑ / ↓** arrow keys, or the **mouse wheel** over the focused pane. (Arrow keys move the cursor instead while you are editing a text annotation.)
- **In-window slice/frame slider:** multi-slice and multi-frame series show a slider you can drag to scrub through the stack.
- **Cine:** play multi-frame series from the left-pane **Cine Playback** group (**Play / Pause**, **Stop**, **Loop**, plus speed and frame slider), or with **Ctrl+Space**. On multi-frame series the image **right-click** menu offers the same play/pause, stop, and loop. See the [hub's *General viewing* section](USER_GUIDE.md#general-viewing-2d) for exporting a cine loop.

## Resetting the view

- **Reset view (focused pane):** **V** or **Shift+V**.
- **Reset all views:** **Shift+A**.

These reset pan/zoom for the pane(s); they do not change which series is assigned.

## Limitations

- **Pane dividers are not drag-resizable.** The split ratios are fixed (equal for 1×2 / 2×1 / 2×2, and a fixed 2:1 for the asymmetric 3-pane layouts). Adjustable dividers are a planned enhancement, not a current feature.

---

See also: [USER_GUIDE.md](USER_GUIDE.md) (hub) · [USER_GUIDE_SHORTCUTS.md](USER_GUIDE_SHORTCUTS.md) · [USER_GUIDE_ANNOTATIONS.md](USER_GUIDE_ANNOTATIONS.md).
