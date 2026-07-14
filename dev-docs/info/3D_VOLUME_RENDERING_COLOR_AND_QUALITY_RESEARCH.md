# 3D Volume Rendering — Color, Appearance, and Graininess Research

**Created:** 2026-05-31  
**Related plan:** [THREE_D_VIEWER_APPEARANCE_OPTIONS_CONTROLS_PLAN.md](../plans/supporting/THREE_D_VIEWER_APPEARANCE_OPTIONS_CONTROLS_PLAN.md)  
**Related TO_DO:** 3D visualization cluster in [TO_DO.md](../TO_DO.md)

---

## 1. How color currently works in VTK volume rendering

The renderer uses **two separate transfer functions** that are both applied:

- **Scalar opacity** (`vtkPiecewiseFunction`): maps a scalar/HU value → opacity (0–1)
- **Color** (`vtkColorTransferFunction`): maps a scalar/HU value → RGB

Both are defined in every built-in preset. For example, CT Bone assigns warm cream tones to HU 200–400 and near-white to HU 1000+. This is **not** grayscale-with-opacity; color is applied at every voxel along each ray.

However, in practice the rendered images can appear nearly white/grey because:

1. **The color ramps converge toward white.** Clinical presets are designed to be anatomically plausible — bone looks bone-colored (cream → white), soft tissue looks pinkish-tan. Everything visible ends up in a small cream-to-white hue band. This is intentional for diagnostic use, but makes the output look nearly monochrome.

2. **Volume compositing washes out saturation.** VTK's ray-casting algorithm composites colors and opacities along each view ray. When multiple semi-transparent bone voxels stack, the accumulated result saturates toward white even if each voxel was cream. High-opacity presets amplify this effect.

3. **Raw pixel values are not calibrated HU.** Our 3D path feeds VTK the raw stored pixel values (rescale slope/intercept is not applied in `mpr_volume.py`). CT presets positioned as HU ramps are therefore slightly mis-positioned against actual pixel values, which can cause tissue classes to fall outside their intended color bands.

---

## 2. Why smooth 2D CT scans look grainy/speckled in 3D

This is a fundamental physics mismatch, not a renderer bug.

### The cause

**2D viewing benefits from implicit averaging.** Each 2D pixel integrates X-ray attenuation over a finite detector element and slice thickness (typically 2–10 mm for standard CT). The resulting image has spatial noise that is fine-grained relative to the displayed pixel, and the human eye further averages it across a large grey region.

**3D volume rendering exposes the raw noise distribution.** When the ray-caster samples through the volume, it sees individual voxels that may differ by ±20–40 HU due to quantum noise. If the opacity transfer function has a **steep slope** in that noise range — which is common at tissue boundaries (e.g., the 0–100 HU range where soft tissue lives) — then noise swings of ±20 HU produce large opacity swings. The result is that a region that looks uniformly grey in 2D appears as a scattered "salt-and-pepper" cloud of bright and dark voxels in 3D.

### Why thin-slice CT is worse

High-resolution thin-slice CT (0.5–1 mm slices) is noisier per voxel than thick-slice reconstructions because each voxel integrates less signal. 3D rendering of thin-slice data therefore shows more speckle than 2D viewing of the same data.

### Why the graininess looks different from 2D noise

In 2D you scroll through the volume and your eye perceives motion parallax as continuity. In 3D, the ray caster integrates all that noise into a single projected image, and opacity-amplified noise becomes visually prominent in regions that should look smooth.

---

## 3. Addressing graininess — options and tradeoffs

All options below are **display-only** and must not modify source DICOM data or cached raw volume arrays.

### Option A — Smooth anatomy preset (already implemented)

`PRESET_CT_SMOOTH_ANATOMY` uses a gentler, wider opacity ramp that avoids the steep-slope region where noise is most amplified. At soft-tissue HU values (~0–200) the ramp rises slowly, so ±20 HU noise produces smaller opacity changes. This is the cheapest fix and requires no computation, but it visibly changes the look of the render (less sharp surface-like edges, more translucent anatomy).

**Tradeoff:** smoothness vs. surface sharpness.

### Option B — Pre-render Gaussian smoothing (proposed control, not yet implemented)

Apply a 3D Gaussian blur to the `vtkImageData` before attaching it to the mapper, using `vtkImageGaussianSmooth`. This directly reduces voxel-to-voxel noise variance, so steep opacity ramps no longer produce speckle because adjacent voxels now have similar values.

**Implementation note:** this must run in the background thread (in `_VolumeBuilderWorker` or a second async step) because it is O(N) over the entire volume. The smoothed `vtkImageData` is a display-only derived copy; the raw numpy array in `VolumeData` is not touched. A sigma of 0.5–1.0 voxels gives visible improvement without blurring tissue boundaries significantly; sigma > 2.0 turns cortical bone into a smooth blob.

**Control:** a "Display smoothing" spinbox (sigma 0.0–2.0) or presets ("Off / Mild / Moderate"). Labeling must explicitly say "visualization smoothing only — does not modify source data."

**Tradeoff:** reduces graininess, but blurs fine structures (small vessels, thin cortex) and takes additional time proportional to volume size.

### Option C — Gradient opacity (already implemented as a toggle)

Gradient opacity suppresses voxels with low gradient magnitude (uniform, noisy, interior regions) and shows only voxels at tissue boundaries. This hides the noise-filled interior while preserving surface-like rendering.

The "Gradient opacity" checkbox in the Advanced panel enables the preset's gradient-opacity curve. Works well for bone (sharp boundary) but can make soft tissue disappear almost entirely (soft tissue has low gradients even at real boundaries).

**Tradeoff:** effective for bone/surface rendering, poor for soft tissue volumetrics.

### Option D — Quality / sample distance (already implemented)

Finer sample distance (High quality mode) samples more ray steps, reducing aliasing-style noise from insufficient sampling. Does not reduce the underlying voxel noise, but can reduce the appearance of staircase/aliasing artifacts that compound with noise.

### Option E — Smooth/Detailed interpolation (already implemented)

Linear interpolation (the default) averages neighboring voxels during ray sampling, which implicitly smooths the noise a little compared to nearest-neighbour. Keeping linear interpolation on is already the default.

### Option F — Wider opacity ramps in transfer function

The 1D TF editor (now in Advanced) lets users manually widen the opacity transition at any HU range. A wider ramp at the noisy tissue boundary reduces opacity sensitivity to noise, at the cost of reduced contrast between tissue types.

---

## 4. False-color anatomy presets

This is the most visually distinctive coloring option and is a standard feature in 3D Slicer, OsiriX, Horos, and clinical workstations (Vitrea, IntelliSpace, Syngo.via).

### Concept

Instead of mapping every tissue class to a shade of cream/white, assign **distinct hues** to different HU (or intensity) ranges. The human eye distinguishes color much more easily than shades of grey, so tissue classes that look nearly identical in white-light volume rendering become clearly differentiated in false-color rendering.

### Typical false-color assignments for CT (calibrated HU)

| Tissue class    | HU range     | Color convention           |
|-----------------|-------------|---------------------------|
| Air             | < -900       | Transparent                |
| Lung            | -900 to -400 | Blue-grey (semi-transparent)|
| Fat             | -200 to -50  | Yellow / golden            |
| Soft tissue     | -50 to 80    | Pink / salmon              |
| Blood / contrast| 40 to 200    | Bright red                 |
| Bone (trabecular)| 200 to 700  | Cream / tan                |
| Cortical bone   | 700 to 3000  | Bright white               |

### Caveats for our current pipeline

**Raw pixel values, not calibrated HU.** Since `mpr_volume.py` does not apply rescale slope/intercept, the actual pixel values fed to VTK may differ from HU. False-color presets intended to map "fat = yellow" at HU -100 would need either:
- Calibration applied before rendering (a future pipeline change), OR
- The preset labeled as "approximate" with a note that the bands are approximate for typical raw-vs-HU offsets.

### Examples from other viewers

**3D Slicer** ([slicer.readthedocs.io/en/latest/user_guide/modules/volumerendering.html](https://slicer.readthedocs.io/en/latest/user_guide/modules/volumerendering.html)):
- CT-Bone: cream bone, transparent tissue
- CT-Coronary-Arteries: vivid red for contrast-enhanced arteries, transparent soft tissue, cream bone
- CT-Cardiac: deep red heart muscle, lighter vessels, nearly transparent ribs
- CT-Chest: differentiated lung (blue-grey) from vessels (red) from bone (white)
- MR-Default: greyscale, similar to current implementation
- These presets use dramatically saturated hues and are available as JSON files in the Slicer source: `https://github.com/Slicer/Slicer/tree/main/Modules/Loadable/VolumeRendering/Resources/presets`

**OsiriX / Horos:**
- "Body" preset: fat vivid yellow, muscle dark red, bone white — one of the most commonly cited examples of false-color CT anatomy in the medical imaging community
- These are stored as XML plist files

**Vitrea / IntelliSpace / Syngo.via:**
- Vendor-tuned false-color presets per clinical protocol (CT Pulmonary Angiography, CT Abdomen Contrast, etc.)
- Not open-source but their results are widely published in clinical imaging literature

### VTK implementation

A false-color preset is just a `TransferFunctionPreset` with a color TF that uses saturated hues instead of cream/white tones. No new VTK API is needed. Example skeleton for a CT Anatomy Colors preset:

```python
PRESET_CT_ANATOMY_COLORS = TransferFunctionPreset(
    name="CT Anatomy (false color)",
    scalar_opacity=[
        (-1000, 0.0), (-900, 0.0), (-400, 0.08),
        (-50, 0.15), (80, 0.20), (200, 0.0),
        (700, 0.6), (3000, 0.85),
    ],
    color=[
        (-1000, 0.0, 0.0, 0.0),     # transparent
        (-900, 0.05, 0.10, 0.25),   # dark blue (air)
        (-400, 0.15, 0.25, 0.55),   # blue-grey (lung)
        (-50,  0.90, 0.75, 0.10),   # yellow (fat)
        (0,    0.85, 0.40, 0.35),   # salmon (soft tissue)
        (80,   0.80, 0.15, 0.15),   # red (blood/contrast)
        (200,  0.85, 0.75, 0.55),   # cream (trabecular bone)
        (700,  1.00, 1.00, 0.95),   # near-white (cortical bone)
        (3000, 1.00, 1.00, 1.00),   # white (metal)
    ],
)
```

HU-band positions would need adjustment once/if rescale is applied in the pipeline.

---

## 5. Maximum Intensity Projection (MIP)

MIP is a fundamentally different rendering mode: instead of compositing opacity along the ray, the brightest voxel wins. The result looks like a 2D X-ray — no volume, no depth, but very fast and useful for vascular (angiographic) CT and MIP-based lung nodule review.

VTK supports MIP via `vtkSmartVolumeMapper.SetBlendModeToMaximumIntensity()`. The current code uses the default `CompositeBlend` mode.

A blend-mode combo (Composite / MIP / MinIP) would be a natural addition to the Quick controls or the Appearance group.

---

## 6. Recommended implementation priorities

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| High | False-color anatomy presets (CT) | Low — just new preset data | High — dramatically more informative |
| High | Display-only Gaussian smoothing control | Medium — async VTK filter | High — directly fixes the graininess complaint |
| Medium | MIP blend mode toggle | Low — one API call | Medium — useful for vascular CT |
| Low | Calibrated HU pipeline (apply rescale) | High — changes mpr_volume + all presets | High if done right, risky |

The Gaussian smoothing control is the direct answer to the graininess issue and should be implemented as T21 in the appearance plan. False-color presets require no pipeline change and can be added as new `TransferFunctionPreset` entries.

---

## 7. Wood-grain / Moiré ring artifacts

Distinct from salt-and-pepper voxel noise (§2), the concentric "wood-grain" rings and contour-like banding seen on smooth curved surfaces (e.g. the skull/scalp) are a **sampling-rate aliasing** artifact: the ray-caster steps through the volume at a fixed sample distance, and when the opacity transfer function changes *steeply* along the ray, the regular sample spacing beats against the roughly spherical iso-opacity surfaces, producing rings (a Nyquist violation).

**Why some presets are far worse:** narrow, peaked opacity ramps (e.g. CT Fat, whose tissue band is ~50 HU wide) are steep, so they alias strongly; broad gentle ramps (CT Soft Tissue, CT Smooth Anatomy) change slowly along the ray and show few rings. The artifact is also accentuated by gradient-based specular/diffuse shading and is more visible on the CPU ray-cast path (no GPU jitter).

**Levers (CPU path):**
- **Sample distance** is the only real anti-alias knob — finer steps = fewer rings, but slower. This is the same physical knob as the "Quality" modes.
- **Display smoothing** (§3 option B) softens rings by removing high-frequency content.
- **Flat lighting** removes the shading that makes bands visually pop.
- **Wider window / gentler preset** flattens the ramp.

**Design decision (2026-06-02):** rather than expose "Quality", "oversampling", and "auto-fine-for-steep-presets" as three overlapping controls (all are the same sample-distance knob), **merge them into a single "Detail" control** with an "Auto" default driven by a per-preset *steepness metric* (`max(Δopacity · window / Δscalar)` across opacity control points; steep presets auto-select a finer Detail level). Display smoothing and interpolation remain separate because they are genuinely different mechanisms.

**GPU jittering (`SetUseJittering`)** randomizes ray-start offsets so banding becomes fine noise instead of rings — the best fix on native GPUs, but **GPU-only** (no effect on the Parallels CPU-fallback path). Tracked as a separate GPU-path backlog item.

**Larger transfer-function LUT:** evaluated and **deprioritized** — LUT quantization produces flat value-keyed color bands, not the spatial concentric rings seen here, so a bigger LUT would not meaningfully reduce this artifact.
