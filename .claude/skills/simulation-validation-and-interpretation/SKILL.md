---
name: simulation-validation-and-interpretation
description: "Validation, verification, and interpretation workflow for simulation results in physics and engineering. Use when assessing convergence, uncertainty, physical plausibility, and decision relevance for FDTD, FEM, Monte Carlo, radiation transport, and medical-physics simulations."
---

# Simulation validation and interpretation

## Scope

Use this skill after runs complete to determine whether simulation results are trustworthy, explainable, and actionable.

## Use for

- Verification of numerical correctness and convergence
- Validation against references, benchmarks, or experimental ranges
- Uncertainty decomposition and sensitivity analysis
- Physical interpretation of outputs and limitations
- Communicating whether conclusions are supported by evidence

## V and V protocol

1. Verification (did we solve the equations right?)
- Check residual behavior and solver convergence.
- Run mesh or timestep refinement studies.
- Confirm conservation properties and invariants where applicable.

2. Validation (did we solve the right equations?)
- Compare against analytic limits, benchmark cases, or measured data.
- Quantify discrepancy metrics, not just qualitative overlap.
- Report where the model fails and plausible causes.

3. Uncertainty analysis
- Separate numerical, parametric, and model-form uncertainty.
- For stochastic methods, report confidence intervals and effective sample quality.
- For deterministic solvers, report discretization and solver tolerance effects.

4. Sensitivity and robustness
- Identify high-impact parameters and interactions.
- Test robustness to plausible perturbations in assumptions.
- Flag brittle conclusions that change under minor parameter shifts.

5. Interpretation and decisions
- State what is strongly supported, weakly supported, and unknown.
- Tie conclusions directly to validated metrics and uncertainty bounds.
- Provide next experiments or simulations needed to reduce key uncertainty.

## Domain notes

- FDTD: include numerical dispersion and boundary absorber quality checks.
- FEM: include element-quality checks, conditioning concerns, and BC sensitivity.
- Monte Carlo and transport: include variance convergence, bias controls, and seed reproducibility.
- Medical physics: separate research interpretation from clinical decision support unless externally validated.

## Reporting template

- Objective and modeled quantity.
- Verification evidence.
- Validation evidence.
- Uncertainty table with dominant contributors.
- Interpretation with confidence level.
- Actionable next steps.

## Red flags

- No mesh or timestep study but strong quantitative claims.
- Benchmark mismatch explained only qualitatively.
- Uncertainty omitted from key decision plots/tables.
- Conclusions presented outside validated domain of the model.
