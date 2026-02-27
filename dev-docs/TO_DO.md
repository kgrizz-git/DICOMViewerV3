# To-Do Checklist

**Last updated:** 2025-02-14 14:30  
**Changes:** Added time and changes line to header; added to-do for crosshair ROI position verification and documentation.

---

- [ ] Run assessment templates
- [ ] RUN SMOKE TESTS for exporting - check various export options, magnified, with ROIs and text, without, etc.
- [ ] When the Text annotation mode is selected, "Text" does not get highlighted on the menu bar
- [ ] Could consider more sophisticated smoothing but would need to use PIL rather than Qt (" If you want something “better” (e.g. bicubic or Lanczos), you’d have to do the resize yourself (e.g. with PIL/NumPy) and then hand the result to Qt for display.")
- [ ] Build a technical guide
- [ ] Make it possible to copy and to export ROI statistics. 
    - [ ] Copy - user should be able to select the ROI statistics in the right pane and copy them
    - [ ] Export - add "Export ROI Statistics" to Tools menu and context menu. Should open a dialog where the user chooses txt, csv, or xlsx format and selects which series to export from (should be able to do multiple series). User should also have option to choose file save location and name but default name should be the Accession number plus "ROI stats". If Accession number is blank use the Patient ID instead. Stats should be grouped by series at the highest level (ie, a clear header row saying the series number and series description), image/slice/frame at the next level (with a row saying the slice/frame number), and ROI at the lowest level (with a heading for, eg, Ellipse ROI 1). Include all stats for ellipse ROIs, rectangle ROIs, and crosshair ROIs. For the crosshair ROIs record the pixel coordinates and the patient coordinates if they were able to be computed.
- [ ] Double check fusion
    - [ ] Code not very responsive on Parallels with 3D fusion
    - [ ] Check visually accuracy on usual PET/CT study, compare 2D/3D modes
    - [ ] Ask AI agent to estimate difference in registration for some sample points of PET study registered to CT in 2D vs 3D mode and take screenshots (cloud agents)
    - [ ] Check fusion with some other studies
    - [ ] Improve Window/Leveling preset/auto in fusion mode
- [ ] Frame number slider bar not causing slice/frame to increment when moved
- [ ] For histograms - calculate max of "frequency" (y-axis on histogram) for whole series and set the y-axis to use that as the maximum regardless of which slice of the series is currently displayed so that the scale is not constantly changing. 
    - [ ] Also make y-axis label say "Frequency (Log Scale)" or "Frequency (Linear Scale)" depending what mode the display is in
- [ ] See if I can make executables smaller especially on Mac
- [ ] Try to make code faster
- [ ] Make double-clicking on a subwindow expand it so it becomes a 1x1 layout but using whatever subwindow was double-clicked, not necessarily subwindow 1
- [ ] Allow syncing slices
- [ ] Show line for current slice location on different views (eg axial slice in one window show as line on a coronal view in another window)
- [ ] Differentiate between frame # and slice #?
- [ ] See qi-assessment recommendations

## More minor
- [ ] When an ROI is selected in one subwindow and we click into another subwindow, the ROI disappears from the ROI list in the right pane but the ROI statistics are still there until the user does something else in the new window or goes back to the first one and unselects the ROI. Clicking into a different subwindow should automatically unselect any selected ROI (and the statistics in the right pane should be cleared)
