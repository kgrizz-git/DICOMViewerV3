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

## Differentiating Frame # vs. Slice # vs. Instance #

### Background and the Core Problem

DICOM has a strict four-level hierarchy: **Patient → Study → Series → Instance** (each instance = one file, identified by `SOPInstanceUID`). A "multi-frame" instance stores multiple image frames inside one file (`NumberOfFrames`, tag 0028,0008). The two cases that expose the current viewer's limitation are:

- **CCL2 dataset**: All files share the same `SeriesInstanceUID` (one series), but each file is a distinct instance (`InstanceNumber` varies) with `NumberOfFrames > 1`. Each instance is a separate temporal or functional acquisition. The viewer currently lumps them all into one stack, which is misleading.
- **VC192 CT dataset**: All slices share the same `SeriesInstanceUID`. Each file has `NumberOfFrames = 1` and a unique `InstanceNumber` that simply sequences the axial slices. Here, "separate by instance" would produce one thumbnail per slice — clearly undesirable.

The root distinction: in VC192, `InstanceNumber` is a **slice index** (spatial position); in CCL2, `InstanceNumber` separates **functionally independent acquisitions** that each happen to be multi-frame.

### How Other Viewers Handle This

Reviewed viewers: **Weasis**, **OHIF/Cornerstone3D**, and **Horos/OsiriX**.

**Weasis** (open-source Java viewer):
- Groups by `SeriesInstanceUID` as the primary unit.
- Within a series, offers user-selectable sort keys: `InstanceNumber`, `SlicePosition` (computed from `ImagePositionPatient`), `SliceLocation`, `AcquisitionTime`, `ContentTime`, `DiffusionBValue`. Users can cycle through them.
- Multi-frame instances have their frames exposed as individual images during navigation, but the instance-level boundary is not surfaced visually in the thumbnail strip by default.

**OHIF / Cornerstone3D** (web viewer, widely used in radiology research):
- Groups at the `SeriesInstanceUID` level by default.
- Uses "metadata normalization" to detect whether a series contains enhanced multi-frame DICOM (PS3.3 enhanced IODs: Enhanced MR, Enhanced CT, Enhanced PET). For those, per-frame metadata in `PerFrameFunctionalGroupsSequence` (5200,9230) drives correct slice positions, temporal positions, etc.
- For legacy multi-frame formats (NM, US, secondary captures) where frame semantics are opaque, exposes frames sequentially within the series.
- Does **not** automatically split a series into per-instance sub-groups in the thumbnail panel; grouping is by `SeriesInstanceUID` only.

**Horos / OsiriX**:
- Groups by `SeriesInstanceUID`; does not split by instance number by default.
- Provides "Merge" and "Split" options at the series level in the database (right-click) for manual combining or separating of instances.

**Key takeaway**: No mainstream viewer automatically splits one series into per-instance sub-groups in the thumbnail strip without an explicit user action. The standard expectation is that `SeriesInstanceUID` defines one "row" in the navigator. However, good viewers **detect multi-frame instances** and use `NumberOfFrames` plus semantic tags to drive frame-vs-slice navigation distinctions.

### Recommended Approach

#### Tier 1 — Short-term heuristic fix (highest value, lowest risk)

1. **Detect multi-frame instances at load time.** Record `NumberOfFrames` for each loaded file. If `NumberOfFrames > 1`, tag the instance as multi-frame.
2. **Simple series-level detection rule:**
   - If **all** files in a series have `NumberOfFrames <= 1` → treat as a normal slice stack (current behavior, correct for VC192 CT).
   - If **any** file in a series has `NumberOfFrames > 1` → the series contains multi-frame instances and should be handled specially.
3. **Navigator presentation for multi-frame series:**
   - Show a small indicator on the series thumbnail (e.g. a stacked-layers icon, or label "5 inst × 12 fr") so the user understands the structure.
   - Provide a **"Show Instances Separately"** toggle in the navigator right-click context menu and/or the View menu. When on, the series expands into one sub-thumbnail per instance, labeled with `InstanceNumber` (or "Instance 1", "Instance 2", …).
   - Default state: collapsed (single thumbnail), matching current behavior for typical studies. Consider auto-enabling for series where every instance has `NumberOfFrames > 1` (the CCL2 case) as a quality-of-life improvement.
4. **Persist the expanded/collapsed preference** in config, global or per-series-type.
5. **Overlay label**: When viewing a multi-frame instance, show `Inst 2/5 · Frame 4/12` in the overlay (replacing or supplementing the current "Slice N/M" label).

#### Tier 2 — Medium-term semantic detection

Use additional DICOM tags to distinguish *what* the frames represent, and surface this in the UI:

| Detected pattern | Tags used | UI label |
|---|---|---|
| Temporal/dynamic frames | `TemporalPositionIdentifier` (0020,0100), `FrameTime` (0018,1063), `ActualFrameDuration` (0018,1242) | "Frame N/M (time)" |
| Cardiac phases | `TriggerTime` (0018,1060), `CardiacNumberOfImages` (0018,1090) | "Phase N/M" |
| Diffusion b-value | `DiffusionBValue` (0018,9087) | "b=X" per frame |
| Spatial slices within instance | `ImagePositionPatient` (0020,0032) differs across frames | "Slice N/M" |
| Opaque / unknown | None of the above | "Frame N/M" |

This enables specific overlay labels such as `Slice 12/40 · Frame 3/10 (time)` for 4D datasets.

#### Tier 3 — Longer-term: enhanced multi-frame IOD support

For fully correct handling of Enhanced MR, Enhanced CT, Enhanced PET, NM Image:
- Parse `SharedFunctionalGroupsSequence` (5200,9229) and `PerFrameFunctionalGroupsSequence` (5200,9230) to extract per-frame spatial and temporal metadata.
- Reconstruct a 2D dimensional index (slice × time, or slice × b-value) and navigate these independently: scroll → slice axis; Alt+scroll (or dedicated control) → secondary axis.
- This is a significant engineering effort; a dedicated plan document should precede implementation.

### The Instance-vs-Slice Disambiguation Heuristic (CCL2 vs VC192)

The cleanest criterion: **`NumberOfFrames > 1` per instance signals that the instance is self-contained** and warrants its own thumbnail.

Edge cases:
- Ultrasound cine loops: single multi-frame instance with hundreds of frames; should appear distinct from CT slice stacks.
- Old secondary-capture multi-frame (SC IOD) may have many frames but no spatial metadata; treat as "unknown" frame type.
- If `NumberOfFrames` is absent or null, treat as 1.
- If the series has exactly one instance and `NumberOfFrames > 1`, skip the "expand" UI (nothing to expand); just label the frame count.

### UI Option — View Menu / Navigator Context Menu

Suggested menu item wording: **"Show Instances Separately"** (or "Expand Multi-Frame Instances")
- Placement: View menu (global toggle) + right-click context menu on any series thumbnail (per-series override).
- Default: Off for series where all files have `NumberOfFrames <= 1`; configurable for multi-frame series.
- Greyed out when not applicable (series has only one instance, or all instances are single-frame).

### Concerns / Difficulties

- The same `SeriesInstanceUID` sometimes groups heterogeneous data from non-conformant equipment; any heuristic may misfire.
- Expanding instances in the navigator requires the thumbnail strip and series organizer to support more than one level of hierarchy — potentially involves layout and data-model changes.
- Frame semantics vary wildly by modality; a universal solution is complex. Start with the `NumberOfFrames > 1` heuristic and iterate.
- The scroll/navigation model for two independent axes (slice × frame) is a significant UX challenge; keyboard/mouse bindings need careful design to avoid overwhelming users.
- Existing code paths may implicitly assume a single index; refactoring to a multi-dimensional index could be invasive.

### Other Notes

- See the CCL2 and VC192 sample datasets for concrete test cases.
- The DICOM standard's PS3.3 Annex A (enhanced IODs) and PS3.3 Annex C (functional groups) define the authoritative approach for per-frame metadata.
- Weasis's `SortSeriesStack.java` (open-source, GitHub) is a useful reference for sort key options within a series (`InstanceNumber`, `SlicePosition`, `SliceLocation`, `AcquisitionTime`, `ContentTime`, `DiffusionBValue`).

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

## File Association and "Open With" Integration

This covers registering the app so that `.dcm` (and extension-less DICOM) files open in DICOM Viewer V3 by default or appear in OS "Open With" menus.

### Context

DICOM files are commonly `.dcm`, but can also have no extension at all (many PACS exports). The viewer already accepts files via drag-and-drop, but users need OS-level integration to right-click → Open With, or double-click to open directly.

The cleanest implementation is for **packaged executables** — the OS just needs one registry entry (Windows) or `Info.plist` key (macOS) pointing at the `.exe`/`.app`, and it works for any user who installs it. Source/dev installs are messier because the path to `pythonw.exe` is machine-specific.

---

### Windows — Packaged `.exe` (primary target)

The simplest approach for a packaged release is registry entries written by a small bundled helper or the installer itself. No admin rights are needed if keys go under `HKCU`.

**Registry keys required**

```
HKCU\Software\Classes\.dcm
  (Default) = "DICOMViewerV3.dcm"

HKCU\Software\Classes\DICOMViewerV3.dcm
  (Default) = "DICOM Image"

HKCU\Software\Classes\DICOMViewerV3.dcm\DefaultIcon
  (Default) = "C:\path\to\DICOMViewerV3.exe,0"

HKCU\Software\Classes\DICOMViewerV3.dcm\shell\open\command
  (Default) = "\"C:\path\to\DICOMViewerV3.exe\" \"%1\""

HKCU\Software\RegisteredApplications
  DICOMViewerV3 = "Software\Clients\Media\DICOMViewerV3\Capabilities"
```

The `%1` is where Windows substitutes the path of the file the user opened.

**How to apply the registration**

Option 1 — ship a `register.bat` alongside the `.exe` that writes these keys using `reg add`:
```batch
reg add "HKCU\Software\Classes\.dcm" /ve /d "DICOMViewerV3.dcm" /f
reg add "HKCU\Software\Classes\DICOMViewerV3.dcm\shell\open\command" /ve /d "\"<exepath>\" \"%%1\"" /f
ie4uinit.exe -show
```
(Replace `<exepath>` with the actual path at packaging time.)

Option 2 — if using an installer (Inno Setup or NSIS), handle it in the installer script:
- Inno Setup: use the `[Registry]` section (built-in, clean uninstall support).
- NSIS: use `WriteRegStr` in the install section and `DeleteRegKey` in uninstall.

Option 3 — include a small `register_assoc.exe` or call `winreg` from a bundled Python script that detects its own path via `sys.executable`.

**Notifying the shell** after writing: run `ie4uinit.exe -show` (works on Windows 10/11) or call `SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, NULL, NULL)` via `ctypes` — otherwise Explorer may not pick up the change until reboot.

**SmartScreen** will warn users the first time they run an unsigned `.exe`. Code-signing the executable (via a certificate from DigiCert, Sectigo, etc.) eliminates this. Without signing, users click "More info → Run anyway."

**Unregistering**: delete the same keys. If using Inno Setup/NSIS, this happens automatically on uninstall.

---

### Windows — Source/dev install

Works the same way but the command value points to `pythonw.exe` in the venv instead of a standalone `.exe`:

```
"C:\...\venv\Scripts\pythonw.exe" "C:\...\run.py" "%1"
```

Use `pythonw.exe` (not `python.exe`) to suppress the console window. The path is machine-specific, so the registration must be generated dynamically — `scripts/register_windows.py` using Python's `winreg` module can detect `sys.executable` and write the correct path at runtime. A corresponding `scripts/unregister_windows.py` removes them.

The `.bat` launcher could add a menu option ("Register .dcm file association") that calls this script.

---

### macOS — Packaged `.app` (primary target)

macOS file association is declared in `Info.plist` inside the `.app` bundle. PyInstaller generates `Info.plist` from the `.spec` file.

**`Info.plist` additions**

```xml
<key>CFBundleDocumentTypes</key>
<array>
  <dict>
    <key>CFBundleTypeName</key>
    <string>DICOM Image</string>
    <key>CFBundleTypeRole</key>
    <string>Viewer</string>
    <key>LSHandlerRank</key>
    <string>Alternate</string>   <!-- use Owner to claim default -->
    <key>CFBundleTypeExtensions</key>
    <array>
      <string>dcm</string>
    </array>
    <key>LSItemContentTypes</key>
    <array>
      <string>org.nema.dicom</string>
    </array>
    <key>CFBundleTypeIconFile</key>
    <string>AppIcon</string>
  </dict>
</array>
```

**Wiring this into PyInstaller** — in `DICOMViewerV3.spec`, pass an `info_plist` dict to the `BUNDLE()` call:

```python
app = BUNDLE(
    exe,
    name='DICOMViewerV3.app',
    icon='resources/icon.icns',
    bundle_identifier='com.yourname.dicomviewerv3',
    info_plist={
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'DICOM Image',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'CFBundleTypeExtensions': ['dcm'],
                'LSItemContentTypes': ['org.nema.dicom'],
            }
        ],
        'NSHighResolutionCapable': True,
    },
)
```

**Registering with Launch Services** after placing the `.app`: macOS normally registers it automatically when the `.app` is in `/Applications` or opened for the first time. If not, run:
```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f /Applications/DICOMViewerV3.app
```

**`LSHandlerRank`**: `Alternate` = appears in Open With menu but doesn't steal the default from other apps (e.g. OsiriX). Use `Owner` to become the default for `.dcm`.

**App needs to handle the file via `sys.argv[1]` or `QApplication::arguments()`** — see Application-Level Handling below. On macOS, the OS may also send an `NSOpenFiles` / `QFileOpenEvent` instead of (or in addition to) a command-line argument when a file is opened via Finder; Qt forwards these as `QFileOpenEvent` on the `QApplication`. The safest approach is to handle both `sys.argv[1]` and `QFileOpenEvent`.

---

### macOS — Source/dev install

No clean "Open With" registration exists without a `.app` bundle. Options:
- Generate a minimal wrapper `.app` from `launch.command` (shell script + `Info.plist`).
- Use `duti` CLI: `duti -s com.yourname.dicomviewerv3 .dcm all` (requires the bundle to already be registered).

---

### Application-Level Handling (both platforms)

The app needs to respond to a file path provided at launch. Two mechanisms:

**1. `sys.argv[1]` (Windows and macOS CLI)**
```python
# In main.py, after the window is shown:
if len(sys.argv) > 1:
    path = sys.argv[1]
    # call the same load pipeline used by drag-and-drop
```

**2. `QFileOpenEvent` (macOS Finder / dock)**
```python
class App(QApplication):
    def event(self, e):
        if isinstance(e, QFileOpenEvent):
            path = e.file()
            # call load pipeline
            return True
        return super().event(e)
```

The drag-and-drop loading pipeline can be reused for both; the difference is just how the path arrives.

---

### What Needs to Change in `DICOMViewerV3.spec`

**macOS** — one dict added to the existing `info_plist` in `BUNDLE()`:

```python
app = BUNDLE(
    coll,
    name='DICOMViewerV3.app',
    icon='resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.icns',
    bundle_identifier='com.dicomviewer.v3',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': _app_version,
        'CFBundleVersion': _app_version,
        'CFBundleIconFile': 'dvv6ldvv6ldvv6ld_edit-removebg-preview',
        # --- ADD THIS ---
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'DICOM Image',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',      # 'Owner' to claim default
                'CFBundleTypeExtensions': ['dcm'],
                'LSItemContentTypes': ['org.nema.dicom'],
            }
        ],
    },
)
```

`LSHandlerRank: Alternate` means the app appears in "Open With" but does not steal the `.dcm` default from other installed DICOM viewers. No user prompt is needed for this — it is passive registration. The user still has to explicitly choose "Open With → DICOM Viewer V3" or right-click → "Get Info → Open with → Change All" to make it the default.

**Windows** — PyInstaller does **not** write Windows registry entries. The `.spec` file and `EXE()`/`COLLECT()` blocks have no mechanism for file association. The spec itself needs no changes. Association must be done separately — see options below.

---

### Windows: Asking the User and Applying the Association

**This does not exist yet — it needs to be implemented.**

Since there's no installer, the best approach is a **first-run prompt inside the app itself**. On startup, the app would check whether the association exists; if not, it shows a `QMessageBox` once:

```python
# In main.py, after the main window is shown (Windows only):
import sys, winreg
if sys.platform == 'win32':
    _offer_file_association()

def _offer_file_association():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Classes\DICOMViewerV3.dcm'):
            return  # already registered
    except FileNotFoundError:
        pass
    from PySide6.QtWidgets import QMessageBox
    reply = QMessageBox.question(
        None,
        "Associate .dcm files?",
        "Would you like to open DICOM (.dcm) files with DICOM Viewer V3 by default?\n\n"
        "This registers the app for .dcm files on your account only (no admin required).",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )
    if reply == QMessageBox.Yes:
        _register_dcm_association()

def _register_dcm_association():
    import ctypes, winreg
    exe = sys.executable  # path to DICOMViewerV3.exe
    icon = f"{exe},0"
    cmd  = f'"{exe}" "%1"'
    pairs = [
        (r'Software\Classes\.dcm',                              '', 'DICOMViewerV3.dcm'),
        (r'Software\Classes\DICOMViewerV3.dcm',                 '', 'DICOM Image'),
        (r'Software\Classes\DICOMViewerV3.dcm\DefaultIcon',     '', icon),
        (r'Software\Classes\DICOMViewerV3.dcm\shell\open\command', '', cmd),
    ]
    for key, name, value in pairs:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    # Notify Explorer
    SHCNE_ASSOCCHANGED = 0x08000000
    SHCNF_IDLIST = 0x0000
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
```

The prompt only appears once per install (because on subsequent launches the key already exists). The same `_register_dcm_association` function can also be called from a "Register file association" option in the Help or Settings menu.

To unregister, delete the keys:
```python
def _unregister_dcm_association():
    import winreg
    for key in [
        r'Software\Classes\DICOMViewerV3.dcm\shell\open\command',
        r'Software\Classes\DICOMViewerV3.dcm\shell\open',
        r'Software\Classes\DICOMViewerV3.dcm\shell',
        r'Software\Classes\DICOMViewerV3.dcm\DefaultIcon',
        r'Software\Classes\DICOMViewerV3.dcm',
        r'Software\Classes\.dcm',  # only delete if we own it
    ]:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass
```

> **Caution**: deleting `HKCU\Software\Classes\.dcm` will remove the association even if the user had originally set a different app. Consider checking the value first and only deleting if it equals `DICOMViewerV3.dcm`.

---

### Summary

| | Windows `.exe` | macOS `.app` |
|---|---|---|
| **Mechanism** | Registry keys under `HKCU\Software\Classes` | `CFBundleDocumentTypes` in `Info.plist` |
| **Spec change needed?** | None — done at runtime | Yes — add `CFBundleDocumentTypes` to `info_plist` in `BUNDLE()` |
| **User prompt needed?** | Yes — first-run `QMessageBox` in the app | No — passive; user must explicitly pick "Open With" |
| **Admin rights needed?** | No (HKCU) | No |
| **App code change needed?** | Yes — first-run prompt + `winreg` logic + `sys.argv[1]` | Yes — `sys.argv[1]` + `QFileOpenEvent` |
| **Icon needed?** | Yes — `.ico` (already exists in resources) | Yes — `.icns` (already exists in resources) |
| **Undo/unregister** | Delete registry keys (offer in Settings/Help menu) | Trash the `.app`; Launch Services cleans up |

The app-level `sys.argv` / `QFileOpenEvent` handling is the same regardless of packaging method and should be implemented first.

## Product Naming Exploration

- **Suggestions / best approaches**
  - Define naming constraints (clinical tone, uniqueness, pronunciation, domain availability).
  - Generate candidate shortlists and run quick stakeholder/user preference checks.
  - Keep a temporary working name in release artifacts until final decision is stable.
