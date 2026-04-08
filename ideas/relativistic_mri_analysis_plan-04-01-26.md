# Analysis Plan: Finite Speed of Light and Special Relativistic Effects in MRI Signal Detection and Image Reconstruction

**Status:** Plan document — analysis not yet conducted  
**Scope:** In-principle mathematical and physical analysis, from first principles through image reconstruction

---

## Table of Contents

1. [Foundational Framework and Notation](#1-foundational-framework-and-notation)
2. [Part I — In-Principle Analysis](#part-i--in-principle-analysis)
   - 2.1 [Electromagnetic Propagation: Retarded Potentials and Fields](#21-electromagnetic-propagation-retarded-potentials-and-fields)
   - 2.2 [Transmit Side: RF Excitation Propagation and Spin History](#22-transmit-side-rf-excitation-propagation-and-spin-history)
   - 2.3 [Receive Side: Retarded Signal Emission and Coil Detection](#23-receive-side-retarded-signal-emission-and-coil-detection)
   - 2.4 [Propagation Through the Signal Chain to k-Space](#24-propagation-through-the-signal-chain-to-k-space)
   - 2.5 [k-Space Trajectory Dependence](#25-k-space-trajectory-dependence)
   - 2.6 [Sequence-Specific Analysis](#26-sequence-specific-analysis)
   - 2.7 [Fourier Reconstruction and Image Domain Effects](#27-fourier-reconstruction-and-image-domain-effects)
   - 2.8 [Image Quality Metrics](#28-image-quality-metrics)
   - 2.9 [Parallel Imaging Frameworks](#29-parallel-imaging-frameworks)
   - 2.10 [Standard Corrections and Calibrations: Compensability Analysis](#210-standard-corrections-and-calibrations-compensability-analysis)
   - 2.11 [Compressed Sensing and Sparse Sampling](#211-compressed-sensing-and-sparse-sampling)
   - 2.12 [Machine Learning Reconstruction](#212-machine-learning-reconstruction)
3. [Part II — Practical Corrections and Image Quality Improvements](#part-ii--practical-corrections-and-image-quality-improvements)
   - 3.1 [Corrected Forward Models](#31-corrected-forward-models)
   - 3.2 [Field-Strength Dependence and Research Systems](#32-field-strength-dependence-and-research-systems)
   - 3.3 [Expected Gains by Image Quality Metric](#33-expected-gains-by-image-quality-metric)
   - 3.4 [Hardware Considerations and Implementation Practicality](#34-hardware-considerations-and-implementation-practicality)
4. [Part III — Quantum Electrodynamic Modeling in MRI](#part-iii--quantum-electrodynamic-modeling-in-mri)
5. [Reference Equations and Principles](#5-reference-equations-and-principles)
6. [Bibliography and Resources](#6-bibliography-and-resources)

---

## 1. Foundational Framework and Notation

### 1.1 Geometric and Physical Setup

Define:
- Patient/imaging volume **V** ⊂ ℝ³, with characteristic dimension *L* ~ 0.1–0.5 m
- Transmit coil positions **r**_T^(k), receive coil positions **r**_R^(j)
- Voxel center positions **r**_n ∈ **V**
- Static magnetic field **B**₀ = B₀ẑ
- Larmor frequency ω₀ = γB₀ (γ = gyromagnetic ratio for ¹H = 2π × 42.577 MHz/T)
- Speed of light in vacuo *c* = 2.998 × 10⁸ m/s; local phase velocity in tissue *v*_p(**r**) = *c* / Re(√ε*(**r**)) where ε* is the complex permittivity, varying significantly by tissue type
- Propagation delays are path integrals over spatially varying tissue: τ_T(**r**_n) = ∫_Γ dl / v_p(**r**), τ_R(**r**_n, **r**_R) = ∫_Γ dl / v_p(**r**), where Γ is the locally-fastest ray path (Fermat's principle with refraction at tissue interfaces), not necessarily a straight line
- The effective scalar τ = |**r**_n − **r**_coil| / *c*_eff where *c*_eff is a path-weighted average phase velocity is an approximation whose validity is examined in Section 2.1 Step 5
- Pixel dwell time T_dwell; readout bandwidth BW_px = 1/T_dwell; total readout duration T_ro
- The small parameter ε = ω₀ × τ (phase accumulated during propagation delay) — the central expansion parameter throughout

### 1.2 Quasi-Static Baseline

The standard MRI signal equation (quasi-static limit, single receive coil *j*) is:

```
S(t) = ∫_V ρ(r) · C_R(r) · M_⊥(r, t) · e^{iφ(r,t)} d³r
```

where ρ(**r**) is spin density, C_R(**r**) is the coil sensitivity, M_⊥(**r**, t) is transverse magnetization magnitude, and φ(**r**, t) encodes spatial and temporal phase. The analysis plan will derive the corrected form of this equation under retarded-potential physics, then trace the modification through to image space.

### 1.3 Organizing Principle

At each stage of the analysis, corrections will be organized as a formal expansion in the small parameter ε = ω₀ τ, retaining terms to at least first order. This enables quantitative comparison across field strengths and geometries, and identifies which terms are deterministic (correctable) vs. geometry-dependent (variable).

---

## Part I — In-Principle Analysis

---

## 2.1 Electromagnetic Propagation: Retarded Potentials and Fields

### Objective
Establish the correct relativistic electromagnetic framework from which all downstream effects will be derived.

### Plan

**Step 1 — Jefimenko's Equations (general retarded fields)**

The starting point is the exact solution to Maxwell's equations in the Lorenz gauge. The retarded scalar and vector potentials are:

```
Φ(r, t) = (1/4πε₀) ∫ [ρ_e(r', t_ret) / |r − r'|] d³r'

A(r, t) = (μ₀/4π) ∫ [J(r', t_ret) / |r − r'|] d³r'
```

where the retarded time is t_ret = t − |**r** − **r**'| / *c*. These yield Jefimenko's equations for **E** and **B** directly from source distributions, without the quasi-static approximation. Write out fully for the magnetic field (relevant to MRI RF fields):

```
B(r, t) = (μ₀/4π) ∫ { [J(r', t_ret)/|r−r'|³] + [J̇(r', t_ret)/(c|r−r'|²)] } × (r−r') d³r'
```

**Step 2 — Liénard-Wiechert Potentials for Point-Like Magnetic Dipoles**

Individual nuclear spins are magnetic dipoles. For a precessing magnetic dipole **m**(t) = m(x̂ cos ω₀t + ŷ sin ω₀t) at position **r**', the fields at a distant observation point **r** involve retarded time. Expand the Liénard-Wiechert result to first order in v/c (here v ~ ω₀ × r_dipole, negligibly small for nuclear precession — but the *propagation* retardation is the dominant effect):

Derive the retarded magnetic field **B**_ret(**r**, t) received at coil position **r**_R from a spin at **r**_n, and show explicitly the phase offset:

```
φ_ret = ω₀ · |r_R − r_n| / c_t
```

**Step 3 — Dielectric Loading and In-Tissue Propagation**

Tissue is a lossy dielectric medium. The complex permittivity ε*(ω) = ε'(ω) − iε''(ω) modifies both the phase velocity and introduces attenuation. At the Larmor frequency:

- Phase velocity: v_p = c / Re(√ε*) 
- Attenuation: α = (ω/c) · Im(√ε*)
- Effective wavelength: λ_eff = 2π / (ω₀/v_p)

Tabulate ε_r and σ (conductivity) for relevant tissues (brain, muscle, fat, blood) at 1.5T, 3T, 7T, 10.5T frequencies. Derive the spatially varying propagation phase accumulated along a path from transmit coil → voxel → receive coil.

**Step 4 — Distinguish Relativistic Retardation from Dielectric B1 Inhomogeneity**

The key analytical task is to separate:
1. **Geometric retardation**: phase delay due to finite propagation time, ∝ r/c, depends only on geometry
2. **Dielectric standing wave effects**: B1⁺ and B1⁻ field patterns due to tissue dielectric properties, already partially modeled in standard B1 maps

These two effects both produce spatially structured phase and amplitude variations, but with different geometric signatures. Define a decomposition and show what standard B1 calibration captures vs. what it leaves as residual.

**Step 5 — Spatially Varying Phase Velocity: Path-Integral Formulation**

The assumption of a single tissue propagation speed c_t is a severe simplification. RF wavefronts traverse a heterogeneous body consisting of tissues with substantially different dielectric properties. Construct the full path-integral propagation delay and characterize how much variation exists across tissue types.

*5a — Tissue dielectric property survey at MRI frequencies*

Compile ε_r and σ for major tissue types from the IT'IS database and Gabriel et al. (1996) at 64 MHz (1.5T), 128 MHz (3T), 298 MHz (7T), 447 MHz (10.5T). The phase velocity is v_p = c / Re(√ε*) where ε* = ε_r − iσ/(ωε₀). Representative values at 128 MHz:

| Tissue | ε_r | σ (S/m) | v_p / c | v_p (×10⁸ m/s) |
|---|---|---|---|---|
| Fat | ~5.6 | ~0.04 | ~0.42 | ~1.26 |
| Bone (cortical) | ~12.5 | ~0.08 | ~0.28 | ~0.85 |
| White matter | ~43 | ~0.29 | ~0.15 | ~0.46 |
| Gray matter | ~52 | ~0.59 | ~0.14 | ~0.41 |
| Muscle | ~57 | ~0.80 | ~0.13 | ~0.40 |
| Blood | ~61 | ~1.26 | ~0.13 | ~0.38 |
| CSF | ~72 | ~2.14 | ~0.12 | ~0.35 |

Note the ~3.5× range in v_p between fat and CSF, and ~8.5× range between fat and vacuum. Tabulate also the complex contribution: attenuation constant α (Np/m) and its effect on signal amplitude as a function of path length.

*5b — Ray-path geometry and Fermat's principle*

At interfaces between tissue types, the RF wave refracts according to Snell's law applied to electromagnetic waves:

```
sin θ₁ / sin θ₂ = Re(k₂) / Re(k₁) = v_p1 / v_p2
```

For a ray traversing N tissue layers with thicknesses d_i and phase velocities v_i, the total propagation phase is:

```
Φ(r_n, r_coil) = Σ_i ω₀ · d_i / v_p,i = ω₀ · Σ_i d_i · Re(√ε*_i) / c
```

The propagation delay is τ = Φ / ω₀ = Σ_i d_i / v_p,i. Formalize this as a path integral over the ray trajectory:

```
τ(r_n, r_coil) = (1/c) ∫_Γ Re(√ε*(r)) dl
```

where Γ is the ray path determined by Fermat's principle (shortest phase-time path, accounting for refraction).

*5c — Variability of τ across the FOV*

For a realistic head model with layered scalp/skull/CSF/brain structure, compute τ as a function of voxel position **r**_n and coil position **r**_R. The key quantities are:
- The absolute delay τ (determines the absolute retardation phase φ_ret = ω₀τ)
- The spatial gradient ∇τ (determines localization error and PSF broadening)
- The inter-voxel spread δτ = max(τ) − min(τ) across the FOV (determines the range of differential retardation)

Estimate δτ for a head exam at 3T and 7T using the tissue layer model. Compare to the case of homogeneous tissue (single c_t assumption) and quantify the additional error introduced by ignoring tissue heterogeneity.

*5d — Straight-path approximation validity*

The straight-line approximation τ ≈ |**r**_n − **r**_coil| / c_eff is valid when refraction is weak, i.e., when the contrast in Re(√ε*) between adjacent tissues is small. Quantify the angular deviation of the refracted ray from the straight line at each tissue interface. At the skull-brain boundary (ε_r changes from ~12 to ~52), the index ratio is √(52/12) ≈ 2.1, yielding substantial refraction for oblique angles. Derive the maximum positional error in τ from ignoring refraction.

*5e — Differential retardation contribution from tissue heterogeneity vs. geometry*

Decompose the total spatially varying retardation phase into two terms:

```
φ_ret(r_n) = ω₀/c · [∫_Γ Re(√ε*(r)) dl]
           = ω₀/c · [|r_n − r_coil| + ∫_Γ (Re(√ε*(r)) − 1) dl]
```

The first term is the vacuum geometric delay; the second is the excess delay due to the dielectric medium. The dielectric excess term is typically larger than the geometric term for paths traversing high-ε_r tissue, and must be computed from tissue maps, not just geometry. This has implications for the calibration strategy in Part II.

**Key equations to deploy:** Maxwell's equations in covariant form, Lorenz gauge conditions, Green's function for the wave equation G(r,t;r',t') = δ(t−t'−|r−r'|/c) / (4π|r−r'|), Kramers-Kronig relations for ε*(ω), Snell's law in dielectric media, Fermat's principle

---

## 2.2 Transmit Side: RF Excitation Propagation and Spin History

### Objective
Determine how retarded-potential propagation of the RF pulse modifies the excitation received by each voxel, and trace consequences through the Bloch equations to the spin history.

### Plan

**Step 1 — Standard Bloch Equation Baseline**

The Bloch equation in the rotating frame (standard, quasi-static):

```
dM/dt = γ M × B_eff − [M_x/T2, M_y/T2, (M_z − M₀)/T1]
```

where **B**_eff = (ω₀ − ω_RF)ẑ/γ + B₁⁺(t)(x̂ cos φ_RF + ŷ sin φ_RF). Here B₁⁺(**r**, t) is the rotating-frame transmit field. In the quasi-static model, all voxels see the same B₁⁺(t) envelope simultaneously (scaled by coil sensitivity).

**Step 2 — Retarded Bloch Equation**

Under retarded-potential physics, each voxel **r**_n sees the transmit field with a delay τ_T(**r**_n). The modified Bloch equation input is:

```
B₁⁺(r_n, t) → B₁⁺_ret(r_n, t) = B₁⁺(r_n, t − τ_T(r_n))
```

For a shaped RF pulse b(t) with envelope A(t) and carrier ω_RF:

```
B₁⁺_ret(r_n, t) = A(t − τ_T) · e^{i(ω_RF(t − τ_T) + φ_coil(r_n))}
                = A(t − τ_T) · e^{iω_RF·t} · e^{−iω_RF·τ_T(r_n)} · e^{iφ_coil(r_n)}
```

Identify the two distinct effects:
- **Envelope shift**: A(t − τ_T) — voxel sees a time-shifted slice of the pulse envelope
- **Carrier phase shift**: e^{−iω₀·τ_T(**r**_n)} — a spatially dependent phase offset on the effective flip angle

**Step 3 — Perturbative Analysis of Modified Spin Histories**

For a hard (rectangular) pulse of duration T_p and nominal flip angle α = γB₁T_p:

The carrier phase shift alone gives a modified initial transverse magnetization phase:
```
φ_0(r_n) = φ_0,nominal − ω₀ · τ_T(r_n)
```

For a selective sinc pulse, the envelope shift modifies the effective pulse profile seen by off-resonance spins. Perform a first-order perturbation expansion in ε_T = ω₀ τ_T:

```
M_⊥(r_n, after pulse) ≈ M_⊥^(0)(r_n) + ε_T · δM_⊥^(1)(r_n) + O(ε_T²)
```

Derive δM_⊥^(1) in terms of the pulse envelope and its time derivative. Identify its dependence on pulse shape (hard vs. sinc vs. VERSE vs. adiabatic).

**Step 4 — Slice Profile Perturbation**

For a slice-selective pulse with gradient G_ss applied simultaneously, the Fourier relationship between pulse envelope and slice profile is:

```
M_z(Δz) = FT{A(t)} evaluated at Δz · γG_ss
```

The retarded envelope A(t − τ_T) becomes, in frequency (slice) space:

```
FT{A(t − τ_T)} = e^{−i2πf·τ_T} · FT{A(t)}
```

This is a linear phase term in slice-frequency space, corresponding to a **spatial shift of the slice profile** by:

```
δz(r_n) = τ_T(r_n) · (ω₀ / (γ G_ss))
```

Derive this shift quantitatively for typical G_ss values (~10–40 mT/m) and tabulate δz across field strengths.

**Step 5 — Adiabatic Pulse Sensitivity**

Adiabatic pulses (e.g., BIR-4, hyperbolic secant) are commonly used at high field for their B1 insensitivity. Analyze whether the retarded envelope perturbation breaks the adiabatic condition locally, using the adiabaticity parameter:

```
κ(t) = |dα_eff/dt| / |γ B_eff(t)|
```

Determine whether the envelope shift τ_T can push κ above threshold for realistic geometries.

**Step 6 — Multi-transmit (pTx) Systems**

In parallel transmit systems, multiple coils emit independent waveforms b_k(t) with designed phase relationships. Retardation introduces an additional, uncontrolled, geometry-dependent phase offset on each channel:

```
B₁⁺_total(r_n, t) = Σ_k w_k · B₁_k(r_n) · b_k(t − τ_T^(k)(r_n))
```

where w_k are transmit weights. Analyze how retardation corrupts the designed interference pattern, and whether it is within the dynamic range of standard pTx calibration.

---

## 2.3 Receive Side: Retarded Signal Emission and Coil Detection

### Objective
Derive the corrected receive signal model accounting for retarded-potential emission from precessing spins, and determine the resulting phase and amplitude errors in the acquired signal.

### Plan

**Step 1 — Coil Sensitivity in the Quasi-Static Limit (Baseline)**

The reciprocity principle gives the receive sensitivity of coil *j* at position **r** as:

```
C_R^(j)(r) = −iω₀ μ₀ · b₁⁻^(j)(r)
```

where **b**₁⁻^(j)(**r**) is the rotating-frame magnetic field that the coil would produce per unit current at position **r**. This is a quasi-static calculation, typically solved via Biot-Savart or full-wave EM simulation.

**Step 2 — Retarded Receive Sensitivity**

The actual EMF induced in coil *j* by a precessing spin at **r**_n is determined by the retarded magnetic field at the coil loop. Using the retarded vector potential:

```
A_ret(r_R, t) = (μ₀/4π) · [ṁ(t_ret) × (r_R − r_n)] / (c · |r_R − r_n|²)  +  near-field terms
```

The induced EMF (Faraday's law applied to the coil loop) picks up the retardation phase:

```
EMF^(j)(r_n, t) = C_R^(j)(r_n) · M_⊥(r_n) · e^{iω₀t} · e^{−iω₀ τ_R(r_n, r_R^(j))}
```

to first order in ε_R = ω₀ τ_R. Derive this rigorously from the retarded potential, keeping track of the near-field (1/r²) vs. radiation (1/r) contributions. For typical coil-to-voxel distances and MRI frequencies, identify which term dominates.

**Step 3 — Aggregate Signal Model with Retardation**

The total k-space signal including both transmit and receive retardation is:

```
S^(j)(k, t) = ∫_V ρ(r) · C_R^(j)(r) · M_⊥^(0)(r) 
              · e^{i[k·r + φ_T(r) + φ_R(r,j) + φ_relax(r,t) + φ_B0(r,t)]} d³r
```

where:
- φ_T(**r**) = −ω₀ τ_T(**r**) is the transmit retardation phase (from Section 2.2)
- φ_R(**r**, j) = −ω₀ τ_R(**r**, **r**_R^(j)) is the receive retardation phase
- The combined retardation phase: φ_ret(**r**, j) = φ_T(**r**) + φ_R(**r**, j)

**Step 4 — Spatial Structure of φ_ret**

Analyze φ_ret(**r**, j) as a function of position for:
1. Single receive coil at a fixed position (surface coil geometry)
2. Birdcage coil (distributed, symmetric)
3. Phased array with multiple elements at various positions

For a linear array, φ_ret varies across the FOV in a way that is non-linear and geometry-dependent. Show that it **cannot** in general be decomposed as a sum of a global phase offset and a linear gradient term — meaning it cannot be corrected by standard phase correction or global frequency shift. Specifically, decompose:

```
φ_ret(r, j) = φ̄_ret^(j) + ∇φ_ret^(j) · r + δφ_ret^(j)(r)
```

and estimate the magnitude of the nonlinear residual δφ_ret^(j)(**r**) across the FOV.

---

## 2.4 Propagation Through the Signal Chain to k-Space

### Objective
Trace how transmit and receive retardation phase errors propagate through the signal chain (analog filtering, ADC sampling, digital processing) to produce errors in the acquired k-space data.

### Plan

**Step 1 — ADC Sampling and Phase Coherence**

The ADC samples at discrete times t_m = t_0 + m·T_dwell. The retardation phase φ_ret(**r**, j) is a fixed (time-independent) spatial phase for each voxel-coil pair. It therefore appears as a **static phase map** superimposed on the k-space trajectory.

Quantify: at T_dwell = 2 µs and τ_R = 3.3 ns (1 m path), the ratio τ_R / T_dwell ≈ 0.0017, corresponding to a phase error of ω₀ × τ_R. At 3T (127 MHz): φ_ret = 2π × 127 × 10⁶ × 3.3 × 10⁻⁹ ≈ 2.63 radians. Note this is **not** small — it is a fraction of 2π that is geometrically structured.

**Step 2 — Differential Retardation Across FOV**

For imaging volume dimension L and coil at distance d from isocenter, the differential retardation across the FOV:

```
Δφ_ret = ω₀ · (|r_far − r_R| − |r_near − r_R|) / c_t
```

For L = 0.3 m, d = 0.2 m, 3T: estimate Δφ_ret numerically for representative geometries. This differential phase maps onto image space as a spatially varying phase that cannot be removed by any single global phase correction.

**Step 3 — Effect on Magnitude vs. Phase Images**

In magnitude images, a smooth spatially varying phase contributes negligibly to the magnitude (no first-order cancellation unless the phase varies over the voxel scale). In **phase images** (e.g., phase contrast, susceptibility-weighted imaging, B0 mapping), φ_ret contributes a systematic error directly to the measured phase map.

Derive the contamination of phase-based quantitative measures (velocity encoding in PC-MRI, phase-difference maps in SWI, B0 field maps) by the retardation phase.

**Step 4 — Interaction with Demodulation and Reference Phase**

The scanner demodulates the received signal by multiplying by e^{−iω₀t_ref}. Show that if the reference time t_ref is defined at the RF pulse center (standard), then the demodulated signal carries the full φ_ret(**r**, j) as a residual spatial phase. Analyze whether a modified demodulation reference could absorb part of this phase.

---

## 2.5 k-Space Trajectory Dependence

### Objective
Determine whether and how the nature of the retardation-induced errors changes across different k-space sampling strategies.

### Plan

For each trajectory, analyze: (a) the temporal ordering of k-space samples relative to the excitation, (b) how φ_ret enters each k-space sample, (c) whether the error is concentrated in specific k-space regions, and (d) reconstruction sensitivity.

**Trajectories to analyze:**

**2.5.1 Cartesian (spin-warp) with phase encoding**

Standard EPI and FSE/TSE readouts. Phase encoding direction vs. frequency-encoding direction. The retardation phase is the same for all phase-encode lines (static spatial phase), so its Fourier transform contributes a structured artifact in image space. Derive the point spread function (PSF) modification.

**2.5.2 Echo Planar Imaging (EPI)**

EPI acquires all k-space in a single shot. The echo time TE defines the center of k-space. Analyze whether the rapid traversal of k-space means that the retardation phase is essentially constant across the readout (unlike, say, B0 off-resonance which accumulates during EPI readout). Show that for EPI, the retardation contribution is well-approximated as a static phase map — distinct from and additive to the N/2 ghosting and geometric distortion artifacts from off-resonance.

**2.5.3 Radial (projection reconstruction)**

Each spoke acquires a radial line through k-space from a different angle. The retardation phase couples to the projection angle: the effective coil-voxel distance (and hence φ_R) is projection-angle-independent (it is a property of the voxel position), but the *gradient encoding direction* rotates. Analyze how a fixed spatial phase map φ_ret(**r**) manifests in radial k-space and what artifacts it produces post-filtered-back-projection (FBP) vs. iterative reconstruction.

**2.5.4 Spiral Trajectories**

Spiral trajectories interleave k-space coverage with a temporal structure that is sensitive to off-resonance (through the concomitant gradient correction and off-resonance phase accrual). The retardation phase is time-independent, so it enters as a static spatial phase regardless of the temporal sampling pattern. However, the reconstruction (typically gridding + FFT) propagates static phase errors into image blurring in a trajectory-specific way. Analyze the trajectory-dependent PSF modification.

**2.5.5 3D Trajectories (Stack-of-Spirals, Kooshball, Wave-CAIPI)**

Extend the analysis to 3D trajectories where the retardation phase has a full 3D spatial structure. The additional through-plane component of φ_ret(**r**) may interact with the 3D encoding in novel ways.

---

## 2.6 Sequence-Specific Analysis

### Objective
For each major MRI pulse sequence family, analyze how the retardation-induced errors from Sections 2.2 and 2.3 interact with the sequence-specific spin physics, timing structure, and phase evolution to produce sequence-dependent artifacts and biases. The key question for each sequence is: does the sequence's own phase-management architecture (refocusing pulses, steady-state conditions, phase cycling, flow encoding) tend to preserve, cancel, or amplify the retardation phase errors derived in earlier sections?

### Organizing Framework

For each sequence, analyze:
1. **Spin history impact**: how transmit retardation (carrier phase shift + envelope shift) modifies the post-excitation magnetization state
2. **Refocusing behavior**: whether and to what degree spin echo refocusing cancels the transmit retardation phase
3. **Accumulated phase at readout**: total retardation-derived phase error present in the acquired signal
4. **Sequence-specific sensitizing mechanism**: whether the sequence is inherently phase-sensitive (e.g., elastography, diffusion, PC-MRI) vs. magnitude-dominant, and the consequences
5. **Practical artifact form**: what the error looks like in the final image (phase error, geometric distortion, contrast change, SNR reduction, false activation/suppression)

---

### 2.6.1 Gradient Echo (GRE) and Spoiled GRE (SPGR/FLASH)

GRE sequences use a single RF excitation pulse with no refocusing. The transverse magnetization evolves freely under T2* decay, B0 inhomogeneity, and gradient encoding.

**Retardation analysis:**
- The transmit retardation carrier phase φ_T(**r**_n) = −ω₀τ_T(**r**_n) impresses a direct spatial phase offset onto the initial transverse magnetization. No subsequent pulse acts to remove it.
- The receive retardation phase φ_R(**r**_n) adds at readout.
- Total retardation phase in the GRE signal: φ_ret(**r**_n) = φ_T(**r**_n) + φ_R(**r**_n).
- Because GRE is fully phase-preserving with no refocusing, it is the reference case against which other sequences are compared.

**Magnitude images:** Retardation phase is spatially smooth; magnitude contamination arises only from intra-voxel phase dispersion η (Section 2.7, Step 5). For typical voxel sizes and smooth φ_ret, η ≈ 1, so SNR impact is negligible.

**Phase images (susceptibility-weighted imaging, QSM):** φ_ret directly contaminates the measured phase map. SWI and QSM both rely on unwrapped phase as input; a systematic bias φ_ret(**r**) that is spatially smooth but not easily distinguishable from susceptibility-induced phase is a direct error source. Derive the equivalent apparent susceptibility offset induced by φ_ret.

**Spoiler gradient interaction:** In SPGR, RF spoiling and gradient spoiling are applied to drive longitudinal steady state. The retardation-induced phase appears as a position-dependent increment to the RF phase cycling, potentially disrupting the designed spoiling pattern. Analyze whether the retardation phase is large enough to defeat standard RF spoiling at high field.

---

### 2.6.2 Spin Echo (SE) and Fast Spin Echo (FSE/TSE)

The 180° refocusing pulse in spin echo sequences is widely assumed to rephase static field inhomogeneities. The question here is whether it also refocuses the transmit retardation phase.

**Refocusing of transmit retardation — careful analysis:**

Let the 90° excitation pulse arrive at voxel **r**_n with delay τ_T, imparting carrier phase offset −ω₀τ_T. The initial transverse magnetization phase is:

```
φ_init(r_n) = φ_0 − ω₀ τ_T(r_n)
```

At time TE/2, the 180° refocusing pulse arrives — also from the same transmit coil, also with delay τ_T(**r**_n). The 180° rotation about the x'-axis (rotating frame) negates the y'-component of magnetization, which operationally complex-conjugates the phase:

```
φ → −φ  (under ideal 180° about x')
```

So after refocusing, the phase becomes +ω₀τ_T(**r**_n) + accumulated phase during TE/2. But crucially, the 180° pulse itself has a carrier phase offset −ω₀τ_T(**r**_n) applied to the rotating frame reference. The net effect of the 180° pulse on the retardation phase depends on the exact rotation axis and the carrier phase of the refocusing pulse relative to the excitation pulse.

Perform the full Bloch rotation matrix analysis:
- Case A: 90°_x − 180°_x echo (CPMG-like phase cycling): derive net retardation phase at echo
- Case B: 90°_x − 180°_y: derive net retardation phase at echo
- Show that in general φ_ret is **not** fully refocused by the 180° pulse, because the refocusing pulse itself arrives with the same τ_T — the phase contribution from the 180° pulse carrier partially but not completely cancels the contribution from the 90°

**Multi-echo FSE/TSE (RARE):** Each subsequent refocusing pulse in a TSE train adds another partially-uncancelled retardation contribution. Analyze how the residual retardation phase accumulates across the echo train, and what effect this has on the T2 weighting as a function of echo number (pseudo-T2 weighting artifact).

**Receive retardation in SE:** φ_R(**r**_n) adds at readout identically to GRE — it is not affected by the RF pulse history.

---

### 2.6.3 Echo Planar Imaging (EPI)

EPI acquires all of k-space in a single shot following a single excitation (or refocused echo). The sequence is highly sensitive to off-resonance because the slow phase-encode direction accumulates phase over the full readout duration T_ro.

**Retardation analysis specific to EPI:**

- The retardation phase φ_ret(**r**_n) is a static spatial map (no time dependence to first order). Unlike B0 off-resonance, it does not *accrue* during the readout — it is imprinted at excitation (transmit side) and at each receive sample (receive side is instantaneous per sample).
- Key distinction: B0 off-resonance in EPI causes phase accrual ∝ T_ro in the phase-encode direction (geometric distortion). The retardation phase does NOT accrue during readout — it is a fixed spatial offset. Therefore it manifests differently from classical EPI distortion.
- The retardation phase in EPI appears as a **static phase map** modulating the image — a phase error, not a geometric distortion — in the absence of its own k-space-position-dependent effects.

**N/2 ghosting interaction:** EPI alternates readout gradient polarity on odd vs. even echoes, leading to N/2 ghosts if even-odd phase inconsistencies exist. Standard ghost correction uses navigator echoes. Analyze whether the retardation phase produces an even-odd asymmetry (it should not, since it is static), and confirm this analytically.

**Simultaneous Multi-Slice (SMS/MB) EPI:** In SMS, multiple slices are excited simultaneously and unaliased via CAIPIRINHA and coil sensitivity differences. Retardation phases are slice-dependent (different voxel-to-coil distances for different slices). Analyze how retardation phase differences between simultaneously excited slices affect the unaliasing problem.

---

### 2.6.4 Balanced Steady-State Free Precession (bSSFP)

bSSFP (TrueFISP, FIESTA, balanced FFE) maintains a coherent steady state by fully rewinding all gradient moments each TR. The steady-state magnetization is exquisitely sensitive to the net phase accumulated per TR:

```
M_ss = f(α, T1, T2, Δφ_TR)
```

where Δφ_TR is the net phase per TR. The bSSFP frequency response profile has a passband of width ~1/(2TR) Hz and stopbands (signal nulls) at ±1/(2TR) offsets.

**Retardation as an effective off-resonance:**

The retardation phase φ_ret(**r**_n) is acquired on every TR (transmit + receive contribution). Per TR, this is equivalent to an apparent resonance offset:

```
Δf_ret(r_n) = φ_ret(r_n) / (2π · TR)
```

For φ_ret = 0.5 rad and TR = 5 ms: Δf_ret = 0.5/(2π × 0.005) ≈ 16 Hz. The bSSFP passband width is 1/(2×0.005) = 100 Hz, so a 16 Hz apparent off-resonance shifts the operating point along the frequency profile, modifying T1/T2-weighted contrast and potentially moving voxels toward a banding null.

This is a significant effect because it is spatially structured (depends on coil-voxel geometry) and will produce spatial contrast variations that mimic conventional bSSFP banding artifacts but with a characteristic geometric signature tied to coil positions rather than B0 field topology. At 7T where φ_ret is larger and TR may be shorter, the effect is amplified.

**Phase cycling and banding:** Standard bSSFP banding correction uses phase-cycled acquisitions (0°, 90°, 180°, 270° RF phase offsets) combined post-hoc. Since φ_ret(**r**_n) is not under the scanner's control, analyze whether the phase-cycling approach correctly characterizes and removes the retardation-induced apparent off-resonance or whether it conflates it with true B0 inhomogeneity.

---

### 2.6.5 Inversion Recovery (IR, MPRAGE, FLAIR, STIR)

Inversion recovery sequences precede the readout with a 180° inversion pulse at time TI before excitation. The inversion pulse establishes the longitudinal magnetization state at the time of readout; the T1 recovery curve M_z(TI) = M₀(1 − 2e^{−TI/T1}) gives T1 contrast.

**Inversion efficiency and envelope shift:**

The inversion pulse is typically an adiabatic or composite pulse applied over a period T_inv (milliseconds). The retardation envelope shift A(t − τ_T(**r**_n)) modifies the effective inversion pulse seen by each voxel. For an adiabatic inversion pulse (e.g., hyperbolic secant), the inversion efficiency η_inv depends on whether the B1 amplitude exceeds the adiabatic threshold throughout the pulse. A τ_T-induced envelope shift changes the effective B1(t) trajectory seen by the spin.

Derive the first-order perturbation to inversion efficiency δη_inv from envelope shift τ_T, as a function of pulse shape and field strength. Show that for spatially varying τ_T(**r**_n), the inversion is spatially non-uniform beyond what B1 mapping alone predicts.

**T1 quantification bias:** In quantitative T1 mapping (VFA, IR Look-Locker, MP2RAGE), the derived T1 depends on the assumed flip angle or inversion efficiency. A retardation-induced spatial variation in inversion efficiency introduces a systematic spatial T1 bias. Derive this bias as a function of δη_inv and TI.

**MPRAGE/MP2RAGE:** In MP2RAGE, two GRE images at different inversion times are divided to cancel B1⁺ sensitivity. Analyze whether the retardation-induced inversion efficiency error is of the same functional form as B1⁺ variation and therefore cancels in the MP2RAGE ratio, or whether it has a different dependence that survives the division.

---

### 2.6.6 Diffusion-Weighted Imaging (DWI) and Diffusion Tensor Imaging (DTI)

Diffusion sequences encode Brownian motion via large bipolar gradient lobes (Stejskal-Tanner). The signal is:

```
S = S₀ · e^{−b · D}
```

where b = γ² G² δ²(Δ − δ/3) and D is the apparent diffusion coefficient. Diffusion imaging is based on signal magnitude attenuation; retardation-induced phase errors in principle cancel in magnitude, but several subtleties remain.

**Phase navigation in DWI:** DWI at high b-values is very sensitive to phase inconsistencies between measurements (e.g., from motion). Phase navigation methods explicitly track and correct intershot phase variations. The retardation phase φ_ret(**r**_n) is a static spatial phase that appears identical to a shot-to-shot motion-induced phase if coil geometry changes between shots (e.g., from respiration). Analyze whether retardation phase can corrupt phase navigation and thereby introduce ADC errors.

**Diffusion encoding gradient timing:** The diffusion gradient lobes occupy long durations (δ ~ 10–25 ms, Δ ~ 30–80 ms). During these intervals, the spin phase evolves under the applied gradient plus any residual retardation phase. Since φ_ret is a spatial constant per voxel (not time-evolving during readout), it does not directly affect the diffusion-encoding phase integral. However, if tissue position changes during Δ (cardiac pulsation, CSF flow), the retardation delay τ_R changes, modulating φ_ret with a timing governed by the diffusion sequence structure.

**DTI angular dependence:** DTI applies diffusion encoding in ≥6 directions. For each direction, the RF pulse characteristics (transmit coil configuration in multi-transmit systems) may differ, potentially giving direction-dependent retardation errors. Analyze whether this could introduce a spurious anisotropy in apparent diffusion tensors.

---

### 2.6.7 Perfusion Imaging (ASL, DSC, DCE)

**Arterial Spin Labeling (ASL):**
ASL uses an inversion or saturation pulse at a labeling plane (typically ≥10 cm inferior to the imaging slice) to label blood water magnetically. The labeled bolus then flows to the imaging volume where its effect on tissue T1 is measured.

The labeling efficiency η_label depends critically on the B1⁺ field at the labeling plane. The transmit coil-to-labeling plane distance may be large (>20 cm for some configurations), making the retardation-induced envelope shift at the labeling plane potentially larger than at the imaging volume. Derive η_label as a function of τ_T at the labeling plane for PASL (pulsed), CASL (continuous), and pCASL (pseudo-continuous) labeling approaches.

For pCASL specifically, the labeling pulse train consists of many RF pulses timed in synchrony with the gradient waveform. Analyze whether the retardation-induced carrier phase shift on each pulse of the pCASL train disrupts the designed phase coherence of the train, and what this implies for labeling efficiency at different transmit coil positions.

**DSC and DCE MRI:** These are largely T2*/T1-based concentration measurements using exogenous contrast agents, using GRE or EPI readouts. The retardation effects are the same as for standard GRE/EPI (Sections 2.6.1 and 2.6.3). No additional sequence-specific retardation effects; note that quantitative conversion from signal to concentration depends on flip angle accuracy, which carries a small retardation-induced error.

---

### 2.6.8 MR Elastography (MRE)

MRE encodes mechanical wave displacement using motion-sensitizing gradients (MSG) synchronized to an external mechanical actuator. The measured phase image encodes tissue displacement:

```
φ_MRE(r) = γ · ∫_0^{T_enc} G_MSG(t) · u(r, t) dt
```

where **u**(**r**, t) is the mechanical displacement vector.

**MRE is entirely phase-based** — the diagnostic information is extracted from the phase image. Retardation-induced phase φ_ret(**r**_n) is a direct systematic additive contamination of the phase map used to compute stiffness.

**Assessment of relative magnitudes:** The mechanical wave displacement at 60 Hz actuation in brain is typically ~1–5 µm. The MSG-encoded phase per µm displacement is ~1–10 rad/mm (depending on sequence parameters). Thus the mechanical phase amplitude is ~1–50 mrad. The retardation differential phase across the FOV δφ_ret may be on the order of tens to hundreds of milliradians (see Section 2.3, Step 4). Tabulate the ratio |δφ_ret| / |φ_MRE| for typical MRE parameters at 3T and 7T.

**Temporal synchronization and retardation:** MRE uses phase-difference images between actuator phase offsets (typically 4 or 8 phase offsets per cycle) to isolate the mechanical wave. The retardation phase φ_ret(**r**_n) is static across the actuator phase offsets (it does not change between the multiple acquisitions). Therefore, in phase-difference images between actuator offsets, φ_ret cancels to first order. Verify this cancellation analytically and determine whether second-order terms (from tissue motion changing τ_R slightly) survive.

**Residual after phase differencing:** If the coil-tissue geometry changes between actuator phase acquisitions (e.g., due to mechanical coupling between the actuator and the patient position), then τ_R(**r**_n) is slightly different for each phase offset, and the retardation phase does not cancel. Estimate the magnitude of this residual for typical actuator amplitudes.

---

### 2.6.9 Functional MRI (fMRI, BOLD)

fMRI BOLD signal arises from T2* changes linked to deoxyhemoglobin concentration changes. Standard fMRI uses GRE-EPI readout. The BOLD signal change is typically 0.1–5% of baseline signal.

**Static retardation phase in fMRI:** φ_ret(**r**_n) is a static spatial phase that is present in every volume of the time series. In standard complex-valued fMRI, it contributes a fixed phase offset. In magnitude-based fMRI, it has no first-order effect on the baseline signal, and since it is static it contributes no time-series variance.

**Temporal fluctuation of φ_ret from physiological motion:** Cardiac pulsation displaces brain tissue by ~0.1–0.5 mm; respiration causes head motion of ~0.5–2 mm. These displacements change τ_R(**r**_n + δ**r**) relative to the static-body τ_R(**r**_n). Derive the resulting temporal fluctuation in φ_ret and compute its contribution to fMRI time-series noise:

```
δφ_ret(r, t) ≈ ∇τ_R · δr(t) · ω₀
```

where δ**r**(t) is the physiological motion vector. Evaluate whether this constitutes a non-negligible confound in the context of typical fMRI noise levels (~0.1–0.5% signal change from thermal + physiological noise).

**Phase-based fMRI and VASO:** Phase-based fMRI methods and vascular-space-occupancy (VASO) techniques are sensitive to small phase changes over time. These are more likely to be sensitive to temporal φ_ret fluctuations than magnitude BOLD. Analyze this quantitatively.

**High-field fMRI (7T):** At 7T, the BOLD signal is larger, but φ_ret and its temporal fluctuations are also larger (ω₀ is 2.3× higher). Analyze the net effect on fMRI sensitivity (BOLD CNR) and specificity (false-positive rate from retardation noise) at 7T vs. 3T.

---

### 2.6.10 Summary Table: Sequence Sensitivity to Retardation Effects

| Sequence | Transmit φ_ret refocused? | Receive φ_ret in signal? | Phase-sensitive? | Dominant effect | Relative sensitivity |
|---|---|---|---|---|---|
| GRE | No | Yes | Partial | Phase map error, contrast if bSSFP | Moderate |
| SE | Partially | Yes | Partial | Residual phase, slice shift | Moderate |
| FSE/TSE | Partially, accumulates | Yes | Partial | Echo-train-dependent phase | Moderate–High |
| EPI | Depends on SE/GRE base | Yes | Partial | Static phase map, no extra distortion | Moderate |
| bSSFP | Appears as off-resonance | Yes | High | Contrast variation, banding-like | High |
| IR / MPRAGE | Inversion efficiency error | Yes | Moderate | T1 quantification bias | Moderate |
| DWI/DTI | Partial cancellation | Yes | Low (magnitude) | ADC/tensor error via navigation | Low–Moderate |
| ASL | Labeling efficiency error | Yes | High | Perfusion quantification bias | High |
| MRE | Partial (phase difference) | Yes | Very high | Stiffness map error | High–Very High |
| BOLD fMRI | No | Yes | Low (temporal) | Temporal noise, physiological confound | Low–Moderate |

---

## 2.7 Fourier Reconstruction and Image Domain Effects

### Objective
Derive the image-domain consequences of retardation-induced k-space phase errors, quantified in terms of the point spread function (PSF), modulation transfer function (MTF), and image artifact structure.

### Plan

**Step 1 — Modified Signal Equation in k-Space**

Starting from the corrected signal equation (Section 2.3, Step 3), write the k-space data as:

```
S(k) = ∫_V ρ(r) · C_R(r) · e^{ik·r} · e^{iφ_ret(r)} d³r
     = FT{ ρ(r) · C_R(r) · e^{iφ_ret(r)} }(k)
```

The standard reconstruction assumes S(**k**) = FT{ρ(**r**) · C_R(**r**)}(**k**), so the reconstructed image is:

```
ρ̂(r) = IFT{S(k)} = ρ(r) * PSF_ret(r)
```

where * denotes convolution and PSF_ret is the effective point spread function induced by the phase modulation e^{iφ_ret(**r**)}.

**Step 2 — PSF Analysis for Various Phase Structures**

For φ_ret(**r**) = φ̄ + **a**·**r** + Q(**r**) (decomposed into constant, linear, and nonlinear parts):

- Constant φ̄: global image phase rotation — no effect on magnitude, pure phase shift
- Linear **a**·**r**: equivalent to a k-space shift — sub-voxel rigid displacement of the image
- Nonlinear Q(**r**): convolution with a non-delta PSF — broadening, ringing, localization error

Derive the PSF for realistic Q(**r**) (e.g., spherical geometry) and compute the MTF: MTF(k) = |FT{PSF_ret}(k)|.

**Step 3 — Spatial Resolution and Localization Accuracy**

From the PSF, derive:
- Effective spatial resolution degradation (FWHM of PSF_ret vs. ideal)
- Localization bias: the shift of the PSF centroid from true voxel position

Express both in terms of ε = ω₀ τ and the geometric parameters of the coil-voxel configuration.

**Step 4 — 4D / Cine Temporal Accuracy**

For dynamic imaging (cardiac cine, fMRI, real-time MRI), assess whether the retardation-induced phase is truly static (time-independent) or whether it has any temporal variation. Possible sources of temporal variation:
- Respiration / cardiac motion: changes distance between voxel and coil → modulates φ_ret(**r**(t))
- Flowing blood: moving spins have position-dependent τ_R that changes over time

Derive the magnitude of temporal phase fluctuation induced by physiological motion at realistic amplitudes and rates. Determine whether this constitutes a confound for phase-based functional imaging (BOLD, PC-MRI, fMRI).

**Step 5 — Signal-to-Noise Ratio**

The retardation phase does not reduce signal amplitude to first order (|e^{iφ}| = 1). However, if the phase varies within a single voxel (intra-voxel phase dispersion), there is a net signal reduction. Derive the intra-voxel signal reduction factor:

```
η = |∫_voxel e^{iφ_ret(r)} d³r| / V_voxel
```

For voxel size Δx and phase gradient |∇φ_ret| across the voxel:

```
η ≈ sinc(|∇φ_ret| · Δx / 2π)
```

Estimate |∇φ_ret| for realistic coil geometries and voxel sizes, and compute the resulting SNR reduction.

---

## 2.8 Image Quality Metrics

### Objective
Provide a systematic quantitative summary of all retardation-induced degradations in terms of standard image quality metrics.

### Metrics to derive and tabulate:

| Metric | Definition | How φ_ret enters |
|---|---|---|
| Spatial resolution | FWHM of PSF | Nonlinear phase → PSF broadening |
| MTF | FT of PSF | Frequency-dependent contrast reduction |
| Localization accuracy | Centroid shift of PSF | Linear phase component of φ_ret |
| SNR | Signal / noise RMS | Intra-voxel phase dispersion → signal reduction |
| Phase accuracy | RMS error in phase maps | Direct additive contamination |
| Temporal accuracy | Phase stability over time | Motion-induced modulation of τ_R |
| Slice profile fidelity | Realized vs. nominal slice | Envelope delay → slice shift (Section 2.2) |
| Geometric distortion | Positional accuracy | Effectively a localization error |

---

## 2.9 Parallel Imaging Frameworks

### Objective
Determine how retardation errors propagate through parallel imaging reconstruction and whether they amplify or attenuate relative to single-coil imaging.

### Plan

**2.8.1 SENSE (Sensitivity Encoding)**

SENSE reconstruction inverts the coil sensitivity encoding matrix to recover the unaliased image from undersampled k-space. The SENSE reconstruction:

```
ρ̂ = (C^H Ψ^{-1} C)^{-1} C^H Ψ^{-1} s
```

where **C** is the sensitivity matrix, Ψ is the noise covariance, and **s** is the aliased image vector.

If true coil sensitivities include a retardation-dependent phase C_ret^(j)(**r**) = C^(j)(**r**) · e^{iφ_R(r,j)} but the reconstruction uses the quasi-static C^(j)(**r**), analyze:
- Residual aliasing from sensitivity mismatch
- g-factor penalty modification
- Whether the error is correlated or anti-correlated across coil elements

**2.8.2 GRAPPA (Generalized Autocalibrating Partial Parallel Acquisition)**

GRAPPA estimates missing k-space lines via kernel convolution calibrated from an ACS region. The kernel calibration inherits whatever systematic phase structure exists in the calibration data. Analyze whether the retardation phase is absorbed into the learned kernel (effectively a partial self-calibration) or whether it introduces systematic errors in the interpolated k-space lines outside the ACS region.

**2.8.3 Compressed Sensing Parallel Imaging (CS-PI)**

CS-PI combines random undersampling with sparsity constraints. The retardation phase modifies the effective sparsity of the image in transform domains (wavelet, total variation). Analyze whether the spatial structure of φ_ret(**r**) — which is smooth and geometric — increases or decreases sparsity in common transform domains, and consequently whether CS reconstruction is more or less robust than standard SENSE to retardation errors.

**2.8.4 Wave-CAIPI and Blipped-CAIPI**

These techniques use oscillating gradients during readout to spread aliasing more favorably in 3D. The retardation phase interacts with the oscillating gradient-induced modulation in a way that may be trajectory-specific. Outline the analysis framework for this interaction.

---

## 2.10 Standard Corrections and Calibrations: Compensability Analysis

### Objective
For each standard MRI correction or calibration procedure, determine what fraction of the retardation-induced error it absorbs, and what systematic residual remains.

### Corrections to analyze:

**2.9.1 B1⁺ Mapping and Correction**

Standard B1⁺ maps measure the actual flip angle distribution, which conflates dielectric and geometric B1 variations. A retardation-induced flip angle error (from envelope shift, Section 2.2, Step 3) would be partially absorbed into the B1⁺ map — but only if the calibration and imaging sequences have the same retardation behavior. Analyze the self-consistency condition.

**2.9.2 B0 Shimming and Off-Resonance Correction**

B0 maps measure static field inhomogeneity. A spatially varying phase φ_ret(**r**) that is not time-dependent appears as an apparent static frequency offset if measured via phase-difference methods. Derive the apparent B0 error induced by φ_ret:

```
ΔB0_apparent(r) ≈ φ_ret(r) / (γ · TE)
```

This means standard B0 shimming iterates toward a shim that partially counteracts the retardation phase — but only the component detectable as a B0 offset. Analyze the compensability.

**2.9.3 Phase Correction (1D, 2D, 3D)**

Navigator-based and image-based phase correction methods estimate and remove spatially varying phase from the image. These can in principle estimate φ_ret(**r**) directly. Analyze the requirements: what spatial sampling of the phase map is needed to characterize φ_ret at the level of its nonlinear component, and whether standard phase correction methods provide sufficient degrees of freedom.

**2.9.4 Eddy Current Correction**

Eddy currents produce spatially varying k-space phase errors similar in structure to some retardation terms. Analyze whether eddy current correction algorithms could inadvertently absorb retardation-phase residuals.

**2.9.5 EPI Distortion Correction**

EPI distortion correction (via field maps or reverse phase-encode methods) corrects for B0-induced geometric distortion. Since retardation phase mimics a static B0 pattern (Section 2.4, Step 3), analyze the degree to which EPI distortion correction methods remove or modify the retardation artifact.

---

## 2.11 Compressed Sensing and Sparse Sampling

### Objective
Analyze whether the incoherence and sparsity assumptions underlying compressed sensing are affected by retardation-induced phase structure.

### Plan

**Step 1 — Incoherence of Retardation Artifacts**

CS theory requires that aliasing artifacts from undersampling be incoherent (noise-like) in the sparsity domain. The retardation phase φ_ret(**r**) is a smooth, spatially structured function. Determine whether its Fourier transform (its k-space representation) is concentrated at low frequencies or distributed — this determines whether retardation errors alias coherently (structured artifact) or incoherently (noise-like) under random undersampling.

**Step 2 — Sparsity Modification**

The retarded image ρ(**r**) · e^{iφ_ret(**r**)} has a different sparsity structure than ρ(**r**) in transform domains. For smooth φ_ret, the retarded image is approximately the original image phase-modulated by a smooth carrier. Estimate the increase in wavelet coefficients or total variation induced by a smooth phase modulation, and the resulting penalty on CS convergence.

**Step 3 — Interaction of CS with Systematic Errors**

CS reconstructions with L1 penalties are known to be biased when systematic model errors are present. If the forward model omits the retardation phase, the L1 penalty may drive the reconstruction toward a sparse solution that systematically under-represents features in regions of large |∇φ_ret|. Analyze this bias analytically for a simplified 1D model.

---

## 2.12 Machine Learning Reconstruction

### Objective
Determine whether ML-based reconstruction methods are likely to systematically compensate, ignore, or amplify retardation-induced errors, and whether training data curation matters.

### Plan

**Step 1 — Training Data Bias**

If training data is acquired on real scanners, it inherently includes retardation-induced phase errors. A neural network trained to map undersampled k-space to full images will learn a function that implicitly compensates whatever systematic errors are consistent in the training data. This means:
- If retardation errors are consistent across training and test data (same scanner, similar geometries): the network may learn to "correct" them as part of its implicit prior, with no explicit modeling
- If training and test data differ in retardation structure (different field strengths, different coil geometries): the network may hallucinate or suppress features in a geometry-dependent way

**Step 2 — Unrolled Optimization Networks**

Methods like MoDL, E2E-VarNet, and similar unrolled iterative networks explicitly include a data-consistency layer enforcing consistency with the acquired k-space. If the forward model in the data-consistency layer omits the retardation phase, the data-consistency gradient will be computed incorrectly, and the network will be pulled toward solutions that are neither maximally consistent with the data nor maximally sparse. Formalize this as a biased proximal gradient step.

**Step 3 — Domain Generalization**

Analyze the conditions under which a retardation-phase mismatch between training and deployment would constitute a distribution shift sufficient to cause reconstruction failure or artifact generation. Compare the spatial frequency content of retardation errors to the spatial frequency content of common reconstruction errors the network is trained to handle (noise, aliasing, motion).

---

## Part II — Practical Corrections and Image Quality Improvements

---

## 3.1 Corrected Forward Models

### Plan

**Step 1 — Retardation-Corrected Signal Equation**

Rewrite the full k-space signal equation including φ_ret explicitly:

```
S^(j)(k) = ∫_V ρ(r) · C_R^(j)(r) · e^{iφ_ret(r,j)} · e^{ik·r} d³r
```

This is a non-standard Fourier integral with a spatially varying phase weight. Describe an iterative reconstruction algorithm (e.g., conjugate gradient on the normal equations) that uses this corrected forward model as an operator.

**Step 2 — Computational Cost**

Evaluate the computational cost of the corrected forward model vs. standard FFT-based reconstruction. The corrected model cannot in general be computed with an FFT; it requires either: (a) NUFFT with position-dependent phase weights, or (b) precomputed phase maps applied before standard FFT. Characterize the cost and describe optimization strategies (low-rank approximation of e^{iφ_ret}, GPU acceleration).

**Step 3 — Calibration Strategy**

The retardation phase φ_ret(**r**, j) depends on the geometric relationship between each voxel and each coil element, and on the tissue dielectric properties. Describe a calibration procedure to measure or compute φ_ret:
- Geometric computation from known coil positions (deterministic, model-based)
- EM simulation using body model + tissue properties (patient-specific)
- Empirical estimation from calibration acquisitions (data-driven)

---

## 3.2 Field-Strength Dependence and Research Systems

### Plan

Tabulate ω₀, free-space λ, in-tissue λ_eff, τ_R × ω₀, and expected phase errors for:

| Field | ω₀/2π | λ_free | λ_tissue (brain) | φ_ret (1m path) |
|---|---|---|---|---|
| 1.5T | 63.9 MHz | 4.7 m | ~40 cm | ~1.3 rad |
| 3T | 127.7 MHz | 2.35 m | ~20 cm | ~2.7 rad |
| 7T | 297.2 MHz | 1.01 m | ~8 cm | ~6.2 rad |
| 10.5T | 447 MHz | 0.67 m | ~5 cm | ~9.4 rad |
| 14T (research) | 596 MHz | 0.50 m | ~4 cm | ~12.5 rad |

Note: these are absolute retardation phases (not differential). The relevant quantity for image quality is the *differential* retardation across the FOV (Section 2.3, Step 4), which is smaller but still significant at high field.

Discuss: the 7T and 10.5T systems where full-wave EM simulation is already required for B1 modeling — this is the natural context to incorporate retardation corrections at no additional conceptual cost.

---

## 3.3 Expected Gains by Image Quality Metric

For each metric from Section 2.7, estimate:
- The magnitude of the uncorrected error (from Part I analysis)
- The residual error after applying corrected forward model
- The practical significance threshold (what level of error is detectable or clinically meaningful)

For phase-based quantitative imaging (QSM, SWI, PC-MRI velocity), the gains from retardation correction may be most significant because phase errors directly contaminate the measured quantity.

---

## 3.4 Hardware Considerations and Implementation Practicality

- Coil position calibration accuracy requirements (mm precision needed for reliable geometric φ_ret computation)
- Stability of coil geometry during scanning (flex coils, patient motion)
- Required accuracy of body EM model (tissue dielectric properties, patient-specific anatomy)
- Computational time budget per reconstruction
- Whether prospective correction (modified pulse sequences) is feasible vs. retrospective (reconstruction only)

---

## Part III — Quantum Electrodynamic Modeling in MRI

---

## Plan

### 4.1 Classical vs. Quantum Electromagnetic Descriptions of NMR

The quantum mechanical description of NMR starts with the nuclear spin Hamiltonian:

```
Ĥ = −ℏγ B₀ Î_z − ℏγ B₁(t)(Î_x cos ωt + Î_y sin ωt)
```

The thermal ensemble average of the spin operators in the density matrix formalism reproduces the classical Bloch equations exactly in the linear response regime. Quantify the conditions under which quantum corrections to this classical correspondence might become relevant.

### 4.2 QED Corrections to the Electromagnetic Field

QED introduces corrections to classical electromagnetism including:
- **Vacuum polarization**: modifies the photon propagator at high field strengths (Euler-Heisenberg effective Lagrangian). The correction is of order α(ħω/m_e c²)² where α is the fine structure constant. At ω = 2π × 300 MHz: ħω/m_e c² ~ 10⁻⁶. This is utterly negligible.
- **Photon-photon scattering**: relevant only at electromagnetic field intensities orders of magnitude above any MRI scanner
- **Spontaneous emission**: the NMR transition rate via spontaneous emission is negligible compared to relaxation rates (by many orders of magnitude)

### 4.3 Quantum Noise in MRI Detection

The fundamental quantum limit on measurement is set by the uncertainty principle. For RF photons at 300 MHz, the thermal occupation number n̄ = 1/(e^{ħω/kT} − 1) >> 1 at room temperature (n̄ ~ 10⁷), meaning the RF field is in a highly classical (coherent) state. The quantum noise floor is far below thermal Johnson noise in the coil/patient system, which itself is far below practical MRI noise limits.

### 4.4 Quantum Description of Spin Relaxation

T1 and T2 relaxation arise from fluctuating magnetic fields at the Larmor frequency. The Redfield relaxation theory is a quantum perturbation theory description that could in principle be extended with QED corrections to the spectral density of electromagnetic fluctuations. However, the dominant relaxation mechanisms (dipole-dipole coupling, chemical shift anisotropy) are intramolecular and local — QED corrections to the free-space photon propagator are irrelevant at these distances (< 1 nm).

### 4.5 Summary Assessment

Provide a rigorous order-of-magnitude argument for why QED corrections are irrelevant to MRI at any foreseeable field strength and frequency, while acknowledging the exact conditions (field strength, frequency, temperature) that would need to change for this to be reconsidered.

---

## 5. Reference Equations and Principles

### Fundamental Electromagnetic Relations

- Maxwell's equations in covariant form: ∂_μ F^{μν} = μ₀ J^ν; ∂_μ F̃^{μν} = 0
- Lorenz gauge: ∂_μ A^μ = 0 → □A^μ = μ₀ J^μ
- Retarded Green's function: G_ret(x−x') = θ(t−t') δ((x−x')²) / (2π)
- Retarded potentials (Lorenz gauge): A^μ(**r**,t) = (μ₀/4π) ∫ J^μ(**r**', t_ret) / |**r**−**r**'| d³r'
- Jefimenko's equations (full retarded E and B fields)
- Liénard-Wiechert potentials for point particle
- Power radiated by accelerating charge (Larmor formula): P = q²a²/(6πε₀c³)

### NMR / MRI Signal Physics

- Bloch equations (lab frame and rotating frame)
- Rotating wave approximation and its domain of validity
- Reciprocity principle for coil sensitivity: C_R(**r**) ∝ **b**₁⁻(**r**) per unit current
- General k-space signal equation: S(**k**) = ∫ ρ(**r**) e^{i**k**·**r**} d³r
- k-space definition: **k**(t) = γ ∫_0^t **G**(t') dt'
- Phase-encoding / frequency-encoding signal models
- Nyquist–Shannon theorem applied to k-space sampling
- SNR in MRI: SNR ∝ B₀^{7/4} · V_voxel · √(T_acq) (approximate scaling)

### Parallel Imaging

- SENSE: ρ̂ = (C^H Ψ^{-1} C)^{-1} C^H Ψ^{-1} s
- g-factor: g_R = √{[(C^H Ψ^{-1} C)^{-1}]_RR · [(C^H Ψ^{-1} C)]_RR}
- GRAPPA kernel calibration via ACS lines

### Compressed Sensing

- Restricted Isometry Property (RIP) and its role in reconstruction guarantees
- L1 minimization: ρ̂ = argmin ||Ψρ||₁ s.t. ||F_u ρ − s||₂ ≤ ε
- Coherence between sampling and sparsity bases: μ = max |<φ_k, ψ_j>|

### Wave Propagation in Tissue

- Helmholtz equation: ∇²E + k²E = 0, k = ω√(με*)
- Complex permittivity: ε*(ω) = ε₀(ε' − iε'') = ε₀ε_r − iσ/ω
- Effective wavelength: λ_eff = 2π / Re(k)
- Skin depth: δ = 1 / Im(k)

### Perturbation Theory

- Dyson series expansion for time-dependent Hamiltonians
- Magnus expansion for the propagator of the Bloch equation with time-dependent fields

---

## 6. Bibliography and Resources

### Foundational Electromagnetism

- **Jackson, J.D.** (1999). *Classical Electrodynamics*, 3rd ed. Wiley. — Chapters 6 (Maxwell equations, potentials), 9 (radiating systems), 14 (Liénard-Wiechert potentials)
- **Griffiths, D.J.** (2017). *Introduction to Electrodynamics*, 4th ed. Pearson. — Chapter 10 (potentials and fields), Chapter 11 (radiation)
- **Jefimenko, O.D.** (1966). *Electricity and Magnetism*. Appleton-Century-Crofts. — Original derivation of retarded field equations

### MRI Signal Theory and k-Space

- **Haacke, E.M., Brown, R.W., Thompson, M.R., Venkatesan, R.** (1999). *Magnetic Resonance Imaging: Physical Principles and Sequence Design*. Wiley-Liss. — Comprehensive signal equation derivations
- **Bernstein, M.A., King, K.F., Zhou, X.J.** (2004). *Handbook of MRI Pulse Sequences*. Elsevier Academic Press.
- **Nishimura, D.G.** (1996). *Principles of Magnetic Resonance Imaging*. Stanford course notes. — Clear k-space derivation
- **Sodickson, D.K., Manning, W.J.** (1997). "Simultaneous acquisition of spatial harmonics (SMASH)." *Magn Reson Med*, 38(4):591-603. — Foundational parallel imaging
- **Pruessmann, K.P., Weiger, M., Scheidegger, M.B., Boesiger, P.** (1999). "SENSE: Sensitivity encoding for fast MRI." *Magn Reson Med*, 42(5):952-962.
- **Griswold, M.A., et al.** (2002). "Generalized autocalibrating partial parallel acquisition (GRAPPA)." *Magn Reson Med*, 47(6):1202-1210.

### High-Field Electromagnetic Effects in MRI

- **Collins, C.M., et al.** (2005). "Effects of RF coil excitation on field inhomogeneity and signal loss with a head-sized phantom in MRI at 3T." *Magn Reson Imaging*, 23(6):801-802.
- **Vaughan, J.T., et al.** (2001). "7T vs. 4T: RF power, homogeneity, and signal-to-noise comparison in head images." *Magn Reson Med*, 46(1):24-30.
- **Ibrahim, T.S., Lee, R., Abduljalil, A.M., Baertlein, B.A., Robitaille, P.M.** (2001). "Dielectric resonances and B1 field inhomogeneity in UHFMRI." *Magn Reson Imaging*, 19(2):219-226.
- **Ugurbil, K., et al.** (2003). "Ultrahigh field magnetic resonance imaging and spectroscopy." *Magn Reson Imaging*, 21(10):1263-1281.

### Wave Physics and Full-Wave EM Simulation in MRI

- **Lattanzi, R., Sodickson, D.K.** (2012). "Ideal current patterns yielding optimal SNR and SAR in magnetic resonance imaging." *Magn Reson Med*, 68(1):286-304. — Full-wave coil modeling context
- **Christ, A., et al.** (2010). "The Virtual Family—development of surface-based anatomical models of two adults and two children for dosimetric simulations." *Phys Med Biol*, 55(2):N23-38. — Body EM models for high-field simulation
- **Hoult, D.I., Lauterbur, P.C.** (1979). "The sensitivity of the zeugmatographic experiment involving human samples." *J Magn Reson*, 34(2):425-433. — Original reciprocity derivation

### Compressed Sensing and Sparse Reconstruction

- **Candès, E.J., Romberg, J., Tao, T.** (2006). "Robust uncertainty principles: Exact signal reconstruction from highly incomplete frequency information." *IEEE Trans Inf Theory*, 52(2):489-509.
- **Lustig, M., Donoho, D., Pauly, J.M.** (2007). "Sparse MRI: The application of compressed sensing for rapid MR imaging." *Magn Reson Med*, 58(6):1182-1195.
- **Aggarwal, H.K., Mani, M.P., Jacob, M.** (2019). "MoDL: Model-based deep learning architecture for inverse problems." *IEEE Trans Med Imaging*, 38(2):394-405.

### Machine Learning for MRI Reconstruction

- **Knoll, F., et al.** (2020). "fastMRI: A publicly available raw k-space and DICOM dataset of knee images for accelerated MR image reconstruction using machine learning." *Radiology: Artificial Intelligence*, 2(1):e190007.
- **Hammernik, K., et al.** (2018). "Learning a variational network for reconstruction of accelerated MRI data." *Magn Reson Med*, 79(6):3055-3071.
- **Sriram, A., et al.** (2020). "End-to-end variational networks for accelerated MRI reconstruction." MICCAI 2020.

### Tissue Dielectric Properties

- **Gabriel, C., Gabriel, S., Corthout, E.** (1996). "The dielectric properties of biological tissues: I, II, III." *Phys Med Biol*, 41(11):2231-2293. — Comprehensive database of tissue ε*(ω)
- **IT'IS Foundation Tissue Properties Database**: https://itis.swiss/virtual-population/tissue-properties/database/ — Current online database with frequency-dependent values for all major tissue types; essential for Step 5 path-integral calculations

### Sequence-Specific References

**Spin Echo and FSE/TSE**
- **Hennig, J., Nauerth, A., Friedburg, H.** (1986). "RARE imaging: A fast imaging method for clinical MR." *Magn Reson Med*, 3(6):823-833. — Original RARE/FSE description
- **Mulkern, R.V., et al.** (1991). "Multiple-component apparent transverse relaxation in human brain." *Magn Reson Imaging*, 9(4):431-438. — FSE echo-train phase evolution and T2 effects

**bSSFP**
- **Oppelt, A., et al.** (1986). "FISP — A new fast MRI sequence." *Electromedica*, 54:15-18. — Original bSSFP description
- **Scheffler, K., Lehnhardt, S.** (2003). "Principles and applications of balanced SSFP techniques." *Eur Radiol*, 13(11):2409-2418. — Comprehensive review including off-resonance sensitivity
- **Zur, Y., Stokar, S., Bendel, P.** (1988). "An analysis of fast imaging sequences with steady-state transverse magnetization refocusing." *Magn Reson Med*, 6(2):175-193. — Phase-sensitive steady-state analysis

**Diffusion**
- **Stejskal, E.O., Tanner, J.E.** (1965). "Spin diffusion measurements: Spin echoes in the presence of a time-dependent field gradient." *J Chem Phys*, 42(1):288-292. — Foundational diffusion encoding
- **Le Bihan, D., et al.** (2001). "Diffusion tensor imaging: Concepts and applications." *J Magn Reson Imaging*, 13(4):534-546.

**ASL Perfusion**
- **Williams, D.S., Detre, J.A., Leigh, J.S., Koretsky, A.P.** (1992). "Magnetic resonance imaging of perfusion using spin inversion of arterial water." *Proc Natl Acad Sci*, 89(1):212-216. — Original ASL
- **Dai, W., Garcia, D., de Bazelaire, C., Alsop, D.C.** (2008). "Continuous flow-driven inversion for arterial spin labeling using pulsed radio frequency and gradient fields." *Magn Reson Med*, 60(6):1488-1497. — pCASL; labeling efficiency analysis directly relevant to retardation effects
- **Wu, W.C., et al.** (2007). "A theoretical and experimental investigation of the tagging efficiency of pseudocontinuous arterial spin labeling." *Magn Reson Med*, 58(5):1020-1027.

**MR Elastography**
- **Muthupillai, R., et al.** (1995). "Magnetic resonance elastography by direct visualization of propagating acoustic strain waves." *Science*, 269(5232):1854-1857. — Original MRE description
- **Manduca, A., et al.** (2001). "Magnetic resonance elastography: Non-invasive mapping of tissue elasticity." *Med Image Anal*, 5(4):237-254.

**Functional MRI**
- **Ogawa, S., Lee, T.M., Kay, A.R., Tank, D.W.** (1990). "Brain magnetic resonance imaging with contrast dependent on blood oxygenation." *Proc Natl Acad Sci*, 87(24):9868-9872. — Original BOLD fMRI
- **Hutton, C., et al.** (2002). "Image distortion correction in fMRI: A quantitative evaluation." *NeuroImage*, 16(1):217-240. — EPI distortion context

**Inversion Recovery and Quantitative T1**
- **Look, D.C., Locker, D.R.** (1970). "Time saving in measurement of NMR and EPR relaxation times." *Rev Sci Instrum*, 41(2):250-251. — Original Look-Locker
- **Marques, J.P., et al.** (2010). "MP2RAGE, a self bias-field corrected sequence for improved segmentation and T1-mapping at high field." *NeuroImage*, 49(2):1271-1281. — MP2RAGE B1 correction analysis; relevant to retardation inversion efficiency discussion

### Special Relativity and QED (for Part III)

- **Mandl, F., Shaw, G.** (2010). *Quantum Field Theory*, 2nd ed. Wiley.
- **Peskin, M.E., Schroeder, D.V.** (1995). *An Introduction to Quantum Field Theory*. Addison-Wesley. — Chapter 7 (radiative corrections), Chapter 16 (QED)
- **Euler-Heisenberg effective Lagrangian**: L_EH = (2α²/45m_e⁴)[(E²−B²)² + 7(E·B)²] — gives QED correction to vacuum EM propagation

### Relevant Online Resources

- Bloch equation simulator and RF pulse design tools: http://mrsrl.stanford.edu/~brian/blochsim/
- BART (Berkeley Advanced Reconstruction Toolbox): https://mrirecon.github.io/bart/ — open-source reconstruction framework for testing corrected models
- ISMRM MRI Unbound educational resources: https://www.ismrm.org/MRI_Unbound/
- FastMRI dataset and benchmark: https://fastmri.org/

### Key Review Articles

- **Sodickson, D.K., et al.** (2013). "Rapid MRI acceleration techniques." *J Magn Reson Imaging*, 38(2):279-294.
- **Wald, L.L.** (2012). "The future of acquisition speed, coverage, sensitivity, and resolution." *NeuroImage*, 62(2):1221-1229. — High-field SNR and EM effects
- **Ugurbil, K.** (2014). "Magnetic resonance imaging at ultrahigh fields." *IEEE Trans Biomed Eng*, 61(5):1364-1379.
