# To-Do Checklist

**Last updated:** 2025-02-14 14:30  
**Changes:** Added time and changes line to header; added to-do for crosshair ROI position verification and documentation.

---

- [ ] Refactor code files that are larger than ~750 lines - see refactor assessment and refactoring plans
- [ ] When exporting JPG/PNG with annotations, line thickness and text size are not the same as currently shown on the viewer - seems like they are not rescaled. We should scale them to the same fractional size of the image as is currently displayed, or map settings in annotation options to some fractional size of the image (eg, line thickness or text size of 5 maps to 2.5% of average of image width and height matrix size). Maybe add separate option for export screenshot that shows image exactly as it appears but only can apply to currently displayed images. How does "apply current zoom" work when exporting images from a series not actively being shown, or if the same series is open in two subwindows with different zoom factors?
- [ ] When the Text annotation mode is selected, "Text" does not get highlighted on the menu bar
- [ ] Enable optional smoothing when displaying magnified images so they appear less "blocky".
- [ ] DICOM tag viewer (ctrl+T) only showing tag values for first image
- [ ] Got error on PET/CT study when I switched to fast mode, scrolled slices, adjusted overlay level, and then tried re-enabling high-accuracy fusion mode: [WARNING] 3D resampling failed, using 2D mode
- [ ] For histograms - calculate max of "frequency" (y-axis on histogram) for whole series and set the y-axis to use that as the maximum regardless of which slice of the series is currently displayed so that the scale is not constantly changing. 
    - [ ] Also make y-axis label say "Frequency (Log Scale)" or "Frequency (Linear Scale)" depending what mode the display is in
- [ ] See if I can make executables smaller especially on Mac
- [ ] Try to make code faster
- [ ] Reset View menu item and V shortcut not working
- [ ] Make double-clicking on a subwindow expand it so it becomes a 1x1 layout but using whatever subwindow was double-clicked, not necessarily subwindow 1

## More minor
- [ ] When an ROI is selected in one subwindow and we click into another subwindow, the ROI disappears from the ROI list in the right pane but the ROI statistics are still there until the user does something else in the new window or goes back to the first one and unselects the ROI. Clicking into a different subwindow should automatically unselect any selected ROI (and the statistics in the right pane should be cleared)
