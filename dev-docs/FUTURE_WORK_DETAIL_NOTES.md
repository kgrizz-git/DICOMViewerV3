# Future Work Detail Notes

This file contains implementation notes, technical considerations, tradeoffs, and design guidance for items tracked in [TO_DO.md](TO_DO.md).

---

## Executable Size (Especially on macOS)

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

## Performance: Initial Load, File Loading, Fusion, and General Responsiveness

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

## View Menu Options: Show/Hide Left Pane, Right Pane, Toolbar

- **Suggestions / best approaches**
  - Expose each UI region (left pane, right pane, toolbar) as a checkable `QAction` in the View menu that toggles visibility and persists the state in the configuration.
  - Keep a single source of truth for layout state so that toggling from the menu, keyboard shortcuts, or context menus all go through the same code path.
  - When hiding panes, ensure central widgets resize intelligently and maintain minimum sizes to avoid awkward layouts.
- **Concerns / difficulties**
  - Interactions with the existing multi-window layout system may be complex; hiding a pane should not inadvertently reset window layouts or lose track of focused subwindow.
  - Need to ensure that restore-on-startup uses the persisted visibility flags consistently across platforms and screen DPIs.
- **Other notes**
  - It may be helpful to show shortcuts next to the menu items and consider adding a “Reset layout” action that restores defaults if the user gets into an odd state.

## Slice Navigation Drift (Apparent Image Drift Up/Down)

- **Suggestions / best approaches**
  - Carefully separate the concepts of slice index and pan/zoom transform so that slice changes do not unintentionally alter pan offsets.
  - When scrolling slices, use a stable reference point (e.g. image center or crosshair position) and maintain that point under the cursor or at a fixed viewport position across slices.
  - Compare behavior using image-space coordinates vs. viewport-space coordinates to ensure rounding or interpolation is not accumulating small offsets over many scroll steps.
  - Add diagnostic overlays or logging that prints the current pan/zoom and slice index when navigating, to reproduce and understand the drift conditions.
  - Use a debug pass to capture both viewport-space and scene-space information for a long scroll sequence, including `saved_scene_center`, scrollbars, and scene rect; store findings in a dedicated doc.
  - See `dev-docs/Image_Drift.md` for a detailed summary of the most recent debug session, including concrete log evidence of horizontal drift, suspected interactions between `set_image` preserve-view logic and `sceneRect` recomputation, and proposed hypotheses (H1–H3) for further validation.
- **Concerns / difficulties**
  - Different interpolation modes, zoom levels, and aspect ratios can cause subtle half-pixel shifts that are visually noticeable even if mathematically small.
  - Multi-monitor or high-DPI configurations can introduce additional rounding behavior, making it harder to reproduce the issue consistently.
- **Other notes**
  - Once root cause is identified, it may be worth adding a regression test (e.g. simulated scroll steps) that asserts pan offsets remain within tolerance across many slice changes.

## Differentiating Frame # vs. Slice #

- **Suggestions / best approaches**
  - Clearly separate concepts in the data model: “slice index” for spatial position vs. “frame index” for temporal, phase, or other non-spatial dimension (e.g. dynamic PET, cardiac phases).
  - Reflect this distinction in the UI labels and tooltips (e.g. “Slice 12 / 40 (axial)” vs. “Frame 3 / 10 (time)”).
  - When both dimensions exist, consider a small combined indicator (e.g. `Slice 12/40 | Frame 3/10`) and keyboard/mouse bindings that make it obvious whether the user is changing slice or frame.
- **Concerns / difficulties**
  - Some DICOM series encode frame-related information in non-obvious ways (e.g. enhanced multi-frame) which may require additional parsing logic.
  - Existing code paths may implicitly assume a single index; refactoring to a multi-dimensional index could be invasive and must be done carefully.
- **Other notes**
  - Documentation and training materials should point out the distinction so that users understand how navigation behaves for dynamic or multi-phase studies.

## ROI Selection Behavior Across Subwindows

- **Suggestions / best approaches**
  - Treat ROI selection as scoped to the currently focused subwindow/view; when focus moves to another subwindow, automatically clear the ROI selection and update the right-pane statistics accordingly.
  - Centralize focus-change handling so that all UI elements (ROI list, statistics pane, overlays) react consistently to focus updates.
  - Optionally, consider an “all windows” or “linked ROI” mode in the future, but keep the default behavior simple: one focused window, zero or more ROIs, and stats corresponding only to that window.
- **Concerns / difficulties**
  - Need to ensure that keyboard navigation, mouse clicks, and programmatic focus changes all go through the same code path so that ROI state is not left in an inconsistent state.
  - Users might be relying (even unintentionally) on the current behavior for certain workflows, so behavior changes should be clearly documented in release notes.
- **Other notes**
  - Adding small UI cues (e.g. highlighting the focused window more strongly, showing “No ROI selected” in the statistics pane when focus changes) can make the behavior more intuitive and discoverable.

## Multi-Planar Reconstructions (MPRs) and Oblique Reconstructions

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

## Basic Image Processing and Creating New DICOMs

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

## Integrating Pylinac and Other Automated QC Tools

- **Suggestions / best approaches**
  - Start with a clearly scoped subset of QC tasks (e.g. basic imaging QA tests that pylinac already supports well) and expose them as optional tools within the viewer rather than tightly coupling them to the core workflow.
  - Design a generic “QC engine” interface in your codebase that can wrap pylinac and other libraries, so that adding/removing tools or swapping implementations does not ripple through the UI or data model.
  - Provide simple, guided UIs for each QC task (file/series selection, parameter inputs, run button, results summary with clear pass/fail indicators and key metrics) and allow exporting of structured reports (PDF/CSV/JSON).
  - Where existing tools fall short, prototype your own algorithms in a separate module that follows the same QC interface, enabling side‑by‑side comparison with pylinac or others on the same datasets.
- **Concerns / difficulties**
  - Version compatibility and dependencies (e.g. pylinac’s reliance on specific NumPy/Matplotlib versions) can complicate packaging and distribution, especially for standalone executables.
  - Automatic QC in a clinical context carries expectations around validation and regulatory awareness; any in‑house tools should be clearly labeled as research/QA aids and not diagnostic devices unless formally validated.
  - DICOM handling expectations for QC (phantom recognition, geometry assumptions, field sizes) may differ from your viewer’s general-purpose handling and may need specialized loading paths.
- **Other notes**
  - A separate `dev-docs` plan for QC integration could list targeted tests, required phantoms, validation datasets, and acceptance thresholds, as well as how QC results integrate with logs or external systems (e.g. exporting to a QA archive).

## Interactive Oblique Rotation on MPR

- **Suggestions / best approaches**
  - Add direct manipulation controls (crosshair handles, angle handles, or rotation gizmo) with immediate visual feedback in all linked MPR views.
  - Use low-resolution preview while dragging and full-resolution resampling on mouse release to keep interaction smooth.
  - Keep a simple lock mode for orthogonal planes and an advanced mode for oblique editing.
- **Concerns / difficulties**
  - Maintaining smooth interaction on large, anisotropic datasets can require aggressive caching.
  - Interactive updates must stay synchronized with slice index/position indicators to avoid confusion.

## Measurements and ROI Tools on MPR

- **Suggestions / best approaches**
  - Store measurements and ROIs in patient/world space, then render them in each MPR view via transform projection.
  - Define measurement output semantics explicitly (distance/area in output plane vs. original acquisition plane).
  - Reuse existing tools where possible, but isolate geometry conversion behind a common adapter layer.
- **Concerns / difficulties**
  - Distorted/anisotropic sampling can produce misleading measurements unless interpolation and spacing are handled correctly.
  - Editing the same ROI across multiple planes needs clear ownership/conflict rules.

## Combine Slices on MPR (MIP/MinIP/AIP)

- **Suggestions / best approaches**
  - Support slab thickness + mode (`MIP`, `MinIP`, `AIP`) as part of MPR view state.
  - Compute slabs in volume space before final plane rendering for consistency with orientation changes.
  - Add quick presets (thin/medium/thick slab) and keep a per-view setting.
- **Concerns / difficulties**
  - Thick slab rendering can become expensive during continuous interaction.
  - Users need clear UI labeling to avoid confusing slab thickness with zoom.

## Fusion on MPR

- **Suggestions / best approaches**
  - Prefer one shared registration/transformation pipeline in 3D, then resample to MPR output planes.
  - Expose fusion blend/opacity/colormap controls consistently between standard views and MPR views.
  - Cache pre-registered intermediate volumes where feasible.
- **Concerns / difficulties**
  - Memory pressure rises quickly when caching multiple fused intermediates.
  - Misregistration artifacts can be more obvious on oblique slices and need clear QA workflow.

## Advanced ROI and Contouring

- **Suggestions / best approaches**
  - Treat contouring and 3D ROI as a staged roadmap: manual contouring first, then assisted segmentation, then cross-view editing.
  - Use a common data model for ROI/contour entities so future tools (auto-detect, interpolation, 3D ops) build on the same foundation.
  - Define import/export compatibility targets early (e.g. RTSTRUCT or internal JSON interchange) before implementation expands.
- **Concerns / difficulties**
  - Cross-view contour editing can be complex for users without robust snapping/constraint support.
  - Auto-detection quality depends heavily on modality and acquisition quality.

## PACS-like Query and Archive Integration

- **Suggestions / best approaches**
  - Start with read-only query/retrieve workflows and clear server profile management.
  - Keep PACS/network logic decoupled from viewer UI so offline use remains unaffected.
  - Add robust audit logging for query/retrieve actions.
- **Concerns / difficulties**
  - Network/security requirements vary by site and can increase setup complexity.
  - Clinical workflow expectations may require additional compliance and validation controls.

## Local Study Database and Indexing

- **Suggestions / best approaches**
  - Implement metadata indexing with background scanners and incremental refresh.
  - Support both “index in place” and “managed copy” modes with clear user-visible storage policy.
  - Add fast search facets (patient, modality, date, accession, study description).
- **Concerns / difficulties**
  - Large libraries need careful indexing strategy to avoid startup slowdowns.
  - Moving/copying files can create duplicate study identity unless UID handling is strict.

## Multi-Workspace / Multi-Tab Study Sessions

- **Suggestions / best approaches**
  - Start with independent tabs/workspaces with isolated state (layout, active tools, loaded studies).
  - Add explicit “clone layout” and “move study to new tab” actions for predictable workflow.
  - Ensure memory management and unload behavior are explicit per tab.
- **Concerns / difficulties**
  - Multi-tab GPU/CPU usage can degrade responsiveness if all tabs stay fully active.
  - Cross-tab drag/drop and synchronization can introduce state bugs if not constrained.

## Technical Guide Scope

- **Suggestions / best approaches**
  - Define target audience first (end users, technical admins, developers), then structure sections accordingly.
  - Include reproducible workflows for common tasks and troubleshooting paths.
  - Keep architecture notes high level and link to code-level docs where needed.

## Product Naming Exploration

- **Suggestions / best approaches**
  - Define naming constraints (clinical tone, uniqueness, pronunciation, domain availability).
  - Generate candidate shortlists and run quick stakeholder/user preference checks.
  - Keep a temporary working name in release artifacts until final decision is stable.
