---
name: radiation-transport-simulation
description: "Workflow guidance for Monte Carlo and deterministic radiation transport simulations (EM and particle transport), from geometry setup to validation and uncertainty reporting."
---

# Radiation transport simulation

## Scope

Use this skill when work involves numerical simulation of radiation or EM-related transport phenomena, including Monte Carlo particle transport and coupled source-term studies.

Typical tools and ecosystems:
- OpenMC
- MCNP
- Geant4
- FLUKA
- Serpent
- PHITS
- Deterministic solvers used for cross-checks (when available)

## Use for

- Problem setup for radiation transport studies (source, geometry, materials, tallies)
- EM or radiation dose/deposition studies where transport assumptions matter
- Uncertainty quantification for Monte Carlo outputs
- Variance reduction strategy selection and documentation
- Convergence diagnostics and statistical quality checks
- Benchmarking against reference problems or published validation cases
- Reproducible simulation workflows (inputs, seeds, versions, metadata)

## Do not use for

- Pure symbolic particle-physics matrix-element generation (use HEP workflow skills)
- Generic cloud deployment unless transport workflows are the core focus
- Regulatory or clinical claims without external domain review and approved protocols

## Standard workflow

1. Define objective and observable:
- Primary question (for example dose, flux, heating, detector response)
- Acceptance criterion and required precision

2. Define model assumptions:
- Geometry fidelity level and simplifications
- Material compositions, densities, temperature where relevant
- Physics models and energy cutoffs

3. Define source and boundary conditions:
- Source type, spectrum, angular distribution, normalization
- Time dependence (steady-state vs transient approximation)

4. Plan tallies and diagnostics:
- Tally regions and mesh resolution
- Relative error targets and confidence requirements
- Figure-of-merit targets where available

5. Execute in staged runs:
- Pilot run for sanity checks
- Production runs with explicit random seed strategy
- Optional independent replicate runs for robustness

6. Verify and validate:
- Conservation checks (energy/particle balance)
- Sensitivity checks to key assumptions
- Comparison to benchmark or analytic limits

7. Report with uncertainty:
- Mean, variance, confidence intervals
- Dominant uncertainty sources (statistical vs model)
- Reproducibility metadata (tool version, inputs, seed policy)

## Quality checklist

- Units are consistent and explicitly documented
- Geometry/material definitions are versioned and reviewable
- Physics list/cross-section library is recorded
- Statistical uncertainty is reported with each key metric
- Variance reduction methods are justified and documented
- Any non-convergence is surfaced, not hidden

## Deliverables

- Reproducible input set and run configuration
- Short methods note (assumptions, solver settings, validation checks)
- Results table with uncertainty and confidence reporting
- Follow-up list for model risks and sensitivity gaps
