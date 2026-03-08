# To-Do Checklist

**Last updated:** 2025-02-14 14:30  
**Changes:** Added time and changes line to header; added to-do for crosshair ROI position verification and documentation.

---

## Main List

** See some further notes on some of these below. 

- [ ] Run assessment templates
- [ ] RUN SMOKE TESTS for exporting - check various export options, magnified, with ROIs and text, without, etc.
- [ ] See if I can make executables smaller especially on Mac
- [ ] Try to make code faster, especially initial load, loading files, fusion, but also anywhere else
- [ ] make window map thumbnail in navigator interactive? so clicking on a square sets focus and makes it visible if not already
- [ ] make show/hide left pane, right pane and toolbar an option from the view menu
- [ ] sometimes when navigating slices an image seems to drift up (or the window is panning down)
- [ ] Allow syncing slices when orientations not orthogonal (or maybe within 45 deg?) so that scrolling slices on one also causes the synced one to change slices accordingly - based on ImagePositionPatient
- [ ] Show line for current slice location on different views (eg axial slice in one window show as line on a coronal view in another window) - use ImagePositionPatient and orientation
- [ ] Integrate pylinac and other automated QC analysis tools, and consider writing our own
- [ ] Make it possible to open files/folder without closing currently open ones, including with drag and drop onto running app
- [ ] Differentiate between frame # and slice #?
- [ ] When an ROI is selected in one subwindow and we click into another subwindow, the ROI disappears from the ROI list in the right pane but the ROI statistics are still there until the user does something else in the new window or goes back to the first one and unselects the ROI. Clicking into a different subwindow should automatically unselect any selected ROI (and the statistics in the right pane should be cleared)
- [ ] See qi-assessment recommendations
- [ ] Eventually add MPRs, oblique reconstructions
- [ ] Add basic image processing for creating new DICOMs - applying kernels, smoothing, edge enhancing, sharpening, custom kernels (drawn or using matrix of numbers)
** See below for some info on many of these **
- [ ] Build a technical guide
- [ ] Double check fusion
    - [ ] Code not very responsive on Parallels with 3D fusion
    - [ ] Check visually accuracy on usual PET/CT study, compare 2D/3D modes
    - [ ] Ask AI agent to estimate difference in registration for some sample points of PET study registered to CT in 2D vs 3D mode and take screenshots (cloud agents)
    - [ ] Check fusion with some other studies
    - [ ] Improve Window/Leveling preset/auto in fusion mode
- [ ] make it possible to move the layout map thumbnail when opened from context menu
- [ ] when loading PET CT study there is a ~10 second lag before the loading progress window pops up - what is happening then?
- [ ] make default histogram plot and window smaller and allow resizing much smaller
- [ ] make toolbar customizable
- [ ] make it possible to window/level by holding W and dragging mouse or by holding middle mouse button and dragging or something
- [ ] make it possible to zoom in/out with pinch on trackpad
- [ ] Put same little colored dot on layout map thumbnails that is on series thumbnails in navigator?
- [ ] Make highlight border for focused window match color of dot on navigator series thumbnail
  - [ ] and make color of highlight in layout thumbnail for focused window match
- [ ] make the min/max window width/level based on the min/max pixel value (raw or rescaled) based on bit depth and rescaling equation?

## More to consider
- [ ] make right pane minimum width before collapsing 250 instead of 200?
- [ ] Could consider more sophisticated smoothing but would need to use PIL/numpy rather than Qt (" If you want something “better” (e.g. bicubic or Lanczos), you’d have to do the resize yourself (e.g. with PIL/NumPy) and then hand the result to Qt for display.")

---

## Ideas and Notes for Selected To-Do Items

### Executable Size (Especially on macOS)

- **Suggestions / best approaches**
  - Use tools like `pyinstaller` analysis output or `macholib`-based inspectors to identify which libraries contribute most to bundle size, then aggressively exclude unused backends, plugins, and test data (e.g. matplotlib pillow plugins, Qt image formats you never use, etc.).
  - Prefer dynamic loading / optional imports for rarely used features so that packaging tools can more easily exclude entire dependency trees when those features are off by default.
  - Use a “core viewer” vs. “full-feature” build profile where the core bundle includes only essential features; keep niche tools (e.g. certain export formats, experimental views) in a separate optional plugin/extension package.
  - Audit embedded data files (icons, default LUTs, sample DICOMs, fonts) and move non-essential assets outside the executable, loading them from a user or application data directory instead of baking everything into the binary.
  - On macOS, minimize the number of Python frameworks and Qt plugins packaged into the `.app` by configuring the spec file / build script to include only the Qt modules actually used (e.g. avoid shipping web engine if not needed).
- **Concerns / difficulties**
  - Too-aggressive exclusion rules can lead to subtle runtime failures that only appear on certain platforms or when less common code paths are hit.
  - Dependency trees (ITK, VTK, gdcm, etc., if used) can bring in large native libraries that are not easy to trim without rebuilding from source.
  - Maintaining separate “core” and “full” build configurations adds complexity to the CI / release process and has to be documented carefully.
- **Other notes**
  - It may be worth creating a separate `dev-docs` plan specifically for packaging optimization to document the current build pipeline (for each OS), measured bundle sizes, and experiments with different exclude rules.
  - Continuous monitoring of bundle size across releases can catch regressions early (e.g. a small script that logs sizes into a CSV or markdown table).

### Performance: Initial Load, File Loading, Fusion, and General Responsiveness

- **Suggestions / best approaches**
  - Profile startup to separate Python import time, configuration loading, and UI initialization; lazy-load heavy modules (e.g. DICOM handling, advanced processing) only when first needed rather than at app start.
  - For file loading, perform disk I/O and DICOM parsing in worker threads or background tasks, with progress indicators in the UI to avoid blocking the main thread.
  - Cache derived data (e.g. rescaled volumes, pre-computed LUT mappings, fusion intermediates) so that repeated viewing or re-opening of the same series is faster.
  - In fusion, avoid recomputing expensive operations for each frame if geometry and registration parameters have not changed; reuse registration transforms and pre-resampled volumes as much as possible.
  - Use efficient data structures (NumPy arrays, memoryviews) and vectorized operations instead of Python loops for pixel-wise transforms and window/level computations.
- **Concerns / difficulties**
  - Profiling GUI applications can be noisy; it’s easy to optimize the wrong hotspot if you don’t have representative datasets and workflows.
  - Moving work off the main thread requires careful synchronization with the Qt event loop to avoid race conditions or crashes.
  - Heavy caching can increase memory footprint significantly, particularly for large multi-series or 4D studies.
- **Other notes**
  - It may be useful to maintain a small benchmark suite (e.g. representative studies with timing scripts) to track the impact of performance changes over time.

### Interactive Window Map Thumbnail in Navigator

- **Suggestions / best approaches**
  - Treat the thumbnail as a lightweight overlay view whose cells represent subwindows; clicking a cell updates the focused subwindow index and ensures that the corresponding pane is scrolled into view and visible in the current layout.
  - Use simple hit-testing (mapping click coordinates to grid indices) without adding heavy graphics objects; rely on Qt’s existing painting for the thumbnail rectangles.
  - Provide clear visual feedback in the thumbnail (e.g. highlight the focused window, different color or border for hidden/occluded panes).
  - Consider tooltips or status bar hints when hovering over cells to indicate which series/study is in that slot.
- **Concerns / difficulties**
  - Keeping the thumbnail fully in sync with complex layouts (1x1, 1x2, 2x1, 2x2, swaps) can be tricky; the mapping logic should be centralized and re-used from the main layout code to avoid divergence.
  - Need to ensure that clicks on the thumbnail do not accidentally interfere with other navigation controls or keyboard focus behavior.
- **Other notes**
  - This feature can also serve as a compact “mini-map” when many panes are present but only some are visible due to layout; documenting expected behavior across layouts will avoid user confusion.

### View Menu Options: Show/Hide Left Pane, Right Pane, Toolbar

- **Suggestions / best approaches**
  - Expose each UI region (left pane, right pane, toolbar) as a checkable `QAction` in the View menu that toggles visibility and persists the state in the configuration.
  - Keep a single source of truth for layout state so that toggling from the menu, keyboard shortcuts, or context menus all go through the same code path.
  - When hiding panes, ensure central widgets resize intelligently and maintain minimum sizes to avoid awkward layouts.
- **Concerns / difficulties**
  - Interactions with the existing multi-window layout system may be complex; hiding a pane should not inadvertently reset window layouts or lose track of focused subwindow.
  - Need to ensure that restore-on-startup uses the persisted visibility flags consistently across platforms and screen DPIs.
- **Other notes**
  - It may be helpful to show shortcuts next to the menu items and consider adding a “Reset layout” action that restores defaults if the user gets into an odd state.

### Slice Navigation Drift (Apparent Image Drift Up/Down)

- **Suggestions / best approaches**
  - Carefully separate the concepts of slice index and pan/zoom transform so that slice changes do not unintentionally alter pan offsets.
  - When scrolling slices, use a stable reference point (e.g. image center or crosshair position) and maintain that point under the cursor or at a fixed viewport position across slices.
  - Compare behavior using image-space coordinates vs. viewport-space coordinates to ensure rounding or interpolation is not accumulating small offsets over many scroll steps.
  - Add diagnostic overlays or logging that prints the current pan/zoom and slice index when navigating, to reproduce and understand the drift conditions.
- **Concerns / difficulties**
  - Different interpolation modes, zoom levels, and aspect ratios can cause subtle half-pixel shifts that are visually noticeable even if mathematically small.
  - Multi-monitor or high-DPI configurations can introduce additional rounding behavior, making it harder to reproduce the issue consistently.
- **Other notes**
  - Once root cause is identified, it may be worth adding a regression test (e.g. simulated scroll steps) that asserts pan offsets remain within tolerance across many slice changes.

### Syncing Slices for Non-Orthogonal Orientations (Using ImagePositionPatient)

- **Suggestions / best approaches**
  - Use `ImagePositionPatient` and `ImageOrientationPatient` (plus `PixelSpacing` and `SliceThickness` / spacing between slices) to map from slice index to a physical 3D plane in patient coordinates.
  - To sync slices, compute the intersection of the primary view’s plane with the secondary view’s slice stack and choose the nearest slice based on distance along the normal of the secondary orientation.
  - Implement a small tolerance (e.g. within a few mm or degrees) when matching slices so that minor inconsistencies in DICOM metadata don’t prevent sync.
  - Allow sync to be optional or mode-based (e.g. “strict orthogonal only” vs. “angled within 45°”) to avoid confusing users when stacks are very oblique.
- **Concerns / difficulties**
  - DICOM metadata can be noisy or inconsistent, especially in older or vendor-specific acquisitions; relying purely on `ImagePositionPatient` may produce surprising results.
  - For very oblique or helical acquisitions, mapping between stacks may not be one-to-one, and “closest slice” logic must be clearly defined.
- **Other notes**
  - This feature overlaps conceptually with multi-planar reconstruction (MPR); long term it might make sense to converge on a unified geometric model that also supports full MPR views.

### Slice Location Line Across Views

- **Suggestions / best approaches**
  - For each view, use the 3D plane equation derived from `ImagePositionPatient` and `ImageOrientationPatient` to compute the intersection line with other views’ planes, then project that line into the secondary view’s 2D coordinates.
  - Use distinct colors or styles for the cross-view slice lines (e.g. axial slice line on coronal view) and include a legend or tooltip to clarify which line corresponds to which view.
  - Allow users to toggle these lines on/off per view to avoid clutter when many windows are open.
- **Concerns / difficulties**
  - Numerical stability and rounding in the intersection math can cause jittering of the line when scrolling quickly or at extreme zoom levels.
  - Handling cases where planes are nearly parallel (or coincide) requires special care to avoid degenerate or misleading lines.
- **Other notes**
  - This feature pairs naturally with synchronized slice scrolling and could share the same underlying geometry utilities.

### Differentiating Frame # vs. Slice #

- **Suggestions / best approaches**
  - Clearly separate concepts in the data model: “slice index” for spatial position vs. “frame index” for temporal, phase, or other non-spatial dimension (e.g. dynamic PET, cardiac phases).
  - Reflect this distinction in the UI labels and tooltips (e.g. “Slice 12 / 40 (axial)” vs. “Frame 3 / 10 (time)”).
  - When both dimensions exist, consider a small combined indicator (e.g. `Slice 12/40 | Frame 3/10`) and keyboard/mouse bindings that make it obvious whether the user is changing slice or frame.
- **Concerns / difficulties**
  - Some DICOM series encode frame-related information in non-obvious ways (e.g. enhanced multi-frame) which may require additional parsing logic.
  - Existing code paths may implicitly assume a single index; refactoring to a multi-dimensional index could be invasive and must be done carefully.
- **Other notes**
  - Documentation and training materials should point out the distinction so that users understand how navigation behaves for dynamic or multi-phase studies.

### ROI Selection Behavior Across Subwindows

- **Suggestions / best approaches**
  - Treat ROI selection as scoped to the currently focused subwindow/view; when focus moves to another subwindow, automatically clear the ROI selection and update the right-pane statistics accordingly.
  - Centralize focus-change handling so that all UI elements (ROI list, statistics pane, overlays) react consistently to focus updates.
  - Optionally, consider an “all windows” or “linked ROI” mode in the future, but keep the default behavior simple: one focused window, zero or more ROIs, and stats corresponding only to that window.
- **Concerns / difficulties**
  - Need to ensure that keyboard navigation, mouse clicks, and programmatic focus changes all go through the same code path so that ROI state is not left in an inconsistent state.
  - Users might be relying (even unintentionally) on the current behavior for certain workflows, so behavior changes should be clearly documented in release notes.
- **Other notes**
  - Adding small UI cues (e.g. highlighting the focused window more strongly, showing “No ROI selected” in the statistics pane when focus changes) can make the behavior more intuitive and discoverable.

### Multi-Planar Reconstructions (MPRs) and Oblique Reconstructions

- **Suggestions / best approaches**
  - Build or reuse a consistent 3D volume representation in patient space using `ImagePositionPatient`, `ImageOrientationPatient`, and spacing, and drive all MPR views from that common volume rather than from independent slice stacks.
  - Implement orthogonal MPR first (axial/coronal/sagittal) using resampling onto regularly spaced planes; once stable, extend to arbitrary oblique planes by parameterizing the plane normal and in-plane axes.
  - Use high-performance resampling (NumPy/scipy or specialized libraries) with interpolation options (nearest, linear, potentially higher-order) while keeping interactive performance acceptable via caching and limiting resolution when the user is actively dragging/rotating.
  - Provide intuitive UI controls for defining oblique planes (e.g. draggable crosshairs/lines in existing views, rotation handles, numeric angle controls) with visual feedback.
- **Concerns / difficulties**
  - Accurate handling of anisotropic voxels and non-axis-aligned acquisitions is non-trivial; naïve resampling can produce distorted anatomy or misleading distances.
  - Real-time oblique recon requires careful optimization and possibly GPU acceleration if volumes are large or users expect very smooth interaction.
  - MPR integration with existing tools (window/level, overlays, ROIs, fusion) can significantly increase complexity, especially for synchronized navigation.
- **Other notes**
  - It may be useful to treat MPR as a distinct “mode” with its own set of expectations and controls, documented in a dedicated plan and user-facing guide before implementation.

### Basic Image Processing and Creating New DICOMs

- **Suggestions / best approaches**
  - Implement processing operations (smoothing, sharpening, edge enhancement, custom kernels) on NumPy arrays, using convolution-based approaches where appropriate, and keep the core algorithms independent of any UI code.
  - Allow users to define custom kernels via either a small GUI matrix editor or a simple text-based format, with validation to avoid obviously unstable or extreme filters.
  - When writing new DICOMs, copy essential metadata from the source but clearly mark derived images (e.g. `DERIVED`/`SECONDARY` tags, new `SeriesInstanceUID`, updated descriptions) to avoid confusion with the original clinical data.
  - Provide an option to export processed data as non-DICOM (e.g. NIfTI, PNG stacks) for research workflows, while keeping clinical-safety defaults conservative for DICOM outputs.
- **Concerns / difficulties**
  - DICOM compliance is subtle: derived images must be correctly identified, and some tags should not simply be duplicated from the source (e.g. UIDs, acquisition parameters that no longer strictly apply).
  - Heavy processing on large 3D or 4D datasets can be slow and memory-intensive; background processing and progress reporting will likely be necessary.
  - Users may expect reversible workflows; once new DICOMs are created and stored, “undo” in the filesystem sense is not straightforward.
- **Other notes**
  - A dedicated `dev-docs` plan for processing and DICOM output could spell out which operations are supported, how they are validated, and what guarantees the tool makes about metadata and clinical appropriateness.

### Integrating Pylinac and Other Automated QC Tools

- **Suggestions / best approaches**
  - Start with a clearly scoped subset of QC tasks (e.g. basic imaging QA tests that pylinac already supports well) and expose them as optional tools within the viewer rather than tightly coupling them to the core workflow.
  - Design a generic “QC engine” interface in your codebase that can wrap pylinac and other libraries, so that adding/removing tools or swapping implementations does not ripple through the UI or data model.
  - Provide simple, guided UIs for each QC task (file/series selection, parameter inputs, run button, results summary with clear pass/fail indicators and key metrics) and allow exporting of structured reports (PDF/CSV/JSON).
  - Where existing tools fall short, prototype your own algorithms in a separate module that follows the same QC interface, enabling side‑by‑side comparison with pylinac or others on the same datasets.
- **Concerns / difficulties**
  - Version compatibility and dependencies (e.g. pylinac’s reliance on specific NumPy/Matplotlib versions) can complicate packaging and distribution, especially for standalone executables.
  - Automatic QC in a clinical context carries expectations around validation and regulatory awareness; any in‑house tools should be clearly labeled as research/QA aids and not diagnostic devices unless formally validated.
  - DICOM handling expectations for QC (phantom recognition, geometry assumptions, field sizes) may differ from your viewer’s general‑purpose handling and may need specialized loading paths.
- **Other notes**
  - A separate `dev-docs` plan for QC integration could list targeted tests, required phantoms, validation datasets, and acceptance thresholds, as well as how QC results integrate with logs or external systems (e.g. exporting to a QA archive).