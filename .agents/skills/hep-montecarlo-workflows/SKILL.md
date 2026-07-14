---
name: hep-montecarlo-workflows
description: "Workflow guidance for high-energy-physics Monte Carlo generation and analysis, including Pythia, MadGraph, and Feynman-diagram-driven studies."
---

# HEP Monte Carlo workflows

## Scope

Use this skill for high-energy-physics event generation and analysis pipelines that depend on matrix elements, parton showering, hadronization, and detector-level handoffs.

Typical tools and ecosystems:
- MadGraph5_aMC@NLO
- Pythia8
- Delphes (fast detector simulation)
- ROOT-based analysis pipelines
- Diagram-level sanity checks with Feynman tooling

## Use for

- End-to-end event-generation planning (process to analysis-ready outputs)
- Process definition and cuts in MadGraph-style workflows
- Matching and merging strategy selection (LO/NLO context)
- Pythia tuning, shower/hadronization configuration, and seed control
- Cross-section normalization and event-weight handling
- Validation against reference distributions and known baselines
- Reproducible HEP simulation metadata and run cards

## Do not use for

- Full detector transport studies requiring Geant4-grade transport fidelity
- Non-HEP numerical simulation domains without event-generator workflows
- Physics claims without uncertainty/systematic accounting and review

## Standard workflow

1. Define physics question:
- Target process and observables
- Required precision and phase-space region

2. Set generation strategy:
- LO vs NLO setup and matching/merging method
- PDF set and scale choices (renormalization/factorization)
- Generator-level cuts to control efficiency and bias

3. Configure generators:
- MadGraph process cards and run cards
- Pythia shower and hadronization settings
- Random seed and reproducibility policy

4. Produce and track outputs:
- Event files (for example LHE, HepMC)
- Weight bookkeeping (nominal plus variations)
- Version pinning for tools and tune selections

5. Validate physically:
- Cross-section sanity checks against references
- Kinematic distribution checks before and after showering
- Negative-weight fractions and stability checks when relevant

6. Analyze with uncertainty:
- Statistical uncertainty from finite samples
- Systematic envelopes from scale/PDF/tune variations
- Clear separation of generator-level and detector-level effects

## Feynman diagram usage guidance

- Use diagrams for process sanity checking and communication, not as sole validation.
- Confirm that generated subprocess content matches intended topologies.
- Document approximation level (effective theory, neglected channels, interference assumptions).

## Quality checklist

- Process definition and cuts are explicitly versioned
- PDF and scale choices are documented with rationale
- Seed strategy is deterministic and recorded
- Weight conventions are consistent through analysis
- Validation plots include reference overlays and uncertainty bands
- Known limitations are listed with impact assessment

## Deliverables

- Generator configs (cards, steering files, seed policy)
- Minimal reproducible run instructions
- Validation plot set and summary table
- Uncertainty summary and open systematic risks
