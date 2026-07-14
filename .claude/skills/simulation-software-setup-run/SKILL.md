---
name: simulation-software-setup-run
description: "Setup and execution workflow for engineering and physics simulation software, including FDTD, FEM, Monte Carlo, multiphysics, radiation transport, and medical-physics studies. Use when configuring environments, building models, choosing solver settings, and running reproducible simulation campaigns."
---

# Simulation software setup and run

## Scope

Use this skill for simulation lifecycle work before interpretation: problem framing, tool selection, environment setup, model discretization, solver configuration, run orchestration, and reproducibility capture.

Common solver families:
- FDTD tools (electromagnetics and wave propagation)
- FEM tools (structural, thermal, fluid, EM, multiphysics)
- Monte Carlo tools (radiation transport, stochastic transport, uncertainty propagation)
- Domain-specific packages for medical physics, dosimetry, and treatment-planning research

## Use for

- Selecting solver family from objective and physics regime
- Installing and validating toolchains (local or cluster)
- Defining geometry, materials, mesh/grid, and boundary/initial conditions
- Choosing timestep, solver tolerances, and convergence criteria
- Configuring parameter sweeps and batch runs
- Logging inputs, versions, random seeds, and compute environment details

## Setup protocol

1. Frame the simulation question
- Identify target observables and acceptable error.
- Define what quantity must be predicted versus calibrated.

2. Select method class
- Use FDTD for time-domain wave propagation where explicit field evolution matters.
- Use FEM for complex geometry, coupled PDEs, and boundary-value formulations.
- Use Monte Carlo when stochastic transport, rare events, or particle interactions dominate.

3. Define model and discretization
- Build explicit geometry and material assumptions.
- Define mesh/grid resolution strategy and expected resolution-induced error.
- State boundary and initial conditions with units.

4. Configure numerics
- Set timestep and stability constraints (for example CFL-like constraints in explicit schemes).
- Set nonlinear/linear solver tolerances and max iterations.
- Define stopping criteria and convergence diagnostics.

5. Plan execution
- Smoke test with a reduced case.
- Run baseline then parameter sweeps.
- For stochastic solvers, set seed policy and replicate strategy.

6. Record reproducibility metadata
- Solver version and plugin/module versions.
- Full input deck or config snapshot.
- Hardware profile and runtime flags.

## Medical-physics and radiation notes

- Track phantoms, material libraries, and detector or tally definitions explicitly.
- Separate physical-model uncertainty from numerical uncertainty.
- Do not present simulation output as clinical recommendation without external validated workflow.

## Failure modes to catch early

- Unstable timestepping or divergence hidden by automatic damping.
- Mesh too coarse for gradients or interfaces.
- Incorrect boundary conditions producing non-physical reflection or leakage.
- Silent unit mismatch between geometry, source, and material files.

## Deliverables

- Reproducible run plan with setup steps.
- Parameter table (mesh, timestep, tolerances, seeds).
- Execution log summary with pass/fail for smoke and production runs.
- Known setup limitations and next-run improvements.
