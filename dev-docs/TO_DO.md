# To-Do Checklist

**Last updated:** 2025-02-14 14:30  
**Changes:** Added time and changes line to header; added to-do for crosshair ROI position verification and documentation.

---

- [ ] Run assessment templates
- [ ] *See dev-docs\plans\EXPORT_ANNOTATIONS_AND_SCREENSHOTS_PLAN.md for updates.* When exporting JPG/PNG with annotations, line thickness and text size are not the same as currently shown on the viewer - seems like they are not rescaled. We should map the settings (set in annotation options) to a percent size of the image (eg, line thickness or text size of 5 maps to 2.5% of average of image width and height in pixels, line thickness/size 10 maps to 5% of that average, etc). 
    - [ ] We should also remove the option for exporting at "current zoom" and instead offer the option to upscale - give the option for exporting at the iamges' native resolution or magnified 1.5x, 2x, or 4x. The user should also have the option to enlarge the line thickness and text size by the same factor or not.
    - [ ] And we can add a separate option for "Export Screenshots" that saves the currently displayed images exactly as they appear (ie, line thickness and text size get scaled so they are the same apparent size in the exported screenshot as they are currently displayed in the viewer). This would only export currently displayed images/frames - the user should be able to select any or all of the currently visible subwindows to screenshot. 
    - [x] How does "apply current zoom" work when exporting images from a series not actively being shown, or if the same series is open in two subwindows with different zoom factors? *It uses the zoom of the focused subwindow when Export was opened.*
    - [ ] RUN SMOKE TESTS - check various export options, magnified, with ROIs and text, without, etc.
- [ ] When the Text annotation mode is selected, "Text" does not get highlighted on the menu bar
- [ ] Enable optional smoothing when displaying magnified images so they appear less "blocky".
- [ ] Add ExposureIndex, DeviationIndex, HelicalPitch to overlay options
- [ ] Make it possible to copy and to export ROI statistics. 
    - [ ] Copy - user should be able to select the ROI statistics in the right pane and copy them
    - [ ] Export - add "Export ROI Statistics" to Tools menu and context menu. Should open a dialog where the user chooses txt, csv, or xlsx format and selects which series to export from (should be able to do multiple series). User should also have option to choose file save location and name but default name should be the Accession number plus "ROI stats". If Accession number is blank use the Patient ID instead. Stats should be grouped by series at the highest level (ie, a clear header row saying the series number and series description), image/slice/frame at the next level (with a row saying the slice/frame number), and ROI at the lowest level (with a heading for, eg, Ellipse ROI 1). Include all stats for ellipse ROIs, rectangle ROIs, and crosshair ROIs. For the crosshair ROIs record the pixel coordinates and the patient coordinates if they were able to be computed.
- [ ] Got error on PET/CT study when I switched to fast mode, scrolled slices, adjusted overlay level, and then tried re-enabling high-accuracy fusion mode: [WARNING] 3D resampling failed, using 2D mode
- [ ] For histograms - calculate max of "frequency" (y-axis on histogram) for whole series and set the y-axis to use that as the maximum regardless of which slice of the series is currently displayed so that the scale is not constantly changing. 
    - [ ] Also make y-axis label say "Frequency (Log Scale)" or "Frequency (Linear Scale)" depending what mode the display is in
- [ ] See if I can make executables smaller especially on Mac
- [ ] Try to make code faster
- [ ] Make double-clicking on a subwindow expand it so it becomes a 1x1 layout but using whatever subwindow was double-clicked, not necessarily subwindow 1

## More minor
- [ ] When an ROI is selected in one subwindow and we click into another subwindow, the ROI disappears from the ROI list in the right pane but the ROI statistics are still there until the user does something else in the new window or goes back to the first one and unselects the ROI. Clicking into a different subwindow should automatically unselect any selected ROI (and the statistics in the right pane should be cleared)
