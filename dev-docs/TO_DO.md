# To-Do Checklist

**Last updated:** 2025-02-14 14:30  
**Changes:** Added time and changes line to header; added to-do for crosshair ROI position verification and documentation.

---

- [ ] Run assessment templates
- [ ] RUN SMOKE TESTS for exporting - check various export options, magnified, with ROIs and text, without, etc.
- [ ] When the Text annotation mode is selected, "Text" does not get highlighted on the menu bar
- [ ] Could consider more sophisticated smoothing but would need to use PIL rather than Qt (" If you want something “better” (e.g. bicubic or Lanczos), you’d have to do the resize yourself (e.g. with PIL/NumPy) and then hand the result to Qt for display.")
- [ ] Build a technical guide
- [x] Make it possible to copy and to export ROI statistics.
    - [x] Copy - user can select the ROI statistics in the right pane and copy them (Ctrl+C or right-click Copy). Full table or selected rows; units preserved.
    - [x] Export - "Export ROI Statistics..." in Tools menu and image context menu. Dialog: format (TXT, CSV, XLSX), series selection with annotation counts, rescale option, file path. Default filename: Accession number or Patient ID plus " ROI stats". Stats grouped by series → slice → ROI/crosshair. Ellipse/rectangle stats and crosshair pixel + patient coordinates. Implementation complete; see dev-docs/plans/ROI_STATISTICS_COPY_EXPORT_PLAN.md. Manual verification recommended.
- [ ] Double check fusion
    - [ ] Code not very responsive on Parallels with 3D fusion
    - [ ] Check visually accuracy on usual PET/CT study, compare 2D/3D modes
    - [ ] Ask AI agent to estimate difference in registration for some sample points of PET study registered to CT in 2D vs 3D mode and take screenshots (cloud agents)
    - [ ] Check fusion with some other studies
    - [ ] Improve Window/Leveling preset/auto in fusion mode
- [ ] See if I can make executables smaller especially on Mac
- [ ] Try to make code faster
- [ ] Make double-clicking on a subwindow expand it so it becomes a 1x1 layout but using whatever subwindow was double-clicked, not necessarily subwindow 1
- [ ] Allow syncing slices
- [ ] Show line for current slice location on different views (eg axial slice in one window show as line on a coronal view in another window)
- [ ] Differentiate between frame # and slice #?
- [ ] See qi-assessment recommendations

## More minor
- [ ] When an ROI is selected in one subwindow and we click into another subwindow, the ROI disappears from the ROI list in the right pane but the ROI statistics are still there until the user does something else in the new window or goes back to the first one and unselects the ROI. Clicking into a different subwindow should automatically unselect any selected ROI (and the statistics in the right pane should be cleared)
