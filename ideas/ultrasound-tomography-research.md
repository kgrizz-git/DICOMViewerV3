# Ultrasound Tomography Theoretical Research

## Overview

Investigate theoretical and algorithmic advances in ultrasound computed tomography (USCT), informed by the work of James Wiskin and colleagues at Delphinus Medical Technologies and adjacent groups. Goal is to understand the state of the field and identify open theoretical problems worth pursuing.

## Background

James Wiskin's work centers on full-waveform inversion (FWI) applied to breast ultrasound tomography — using the full transmitted and reflected wavefield (not just time-of-flight) to reconstruct quantitative maps of sound speed, attenuation, and density. Key papers/threads to review:

- Wiskin et al. on iterative nonlinear inversion for USCT
- Connections between USCT FWI and seismic FWI (Pratt, Tarantola lineage)
- Numerical methods: FDTD, finite-element, pseudo-spectral forwarders
- Regularization strategies in high-dimensional acoustic inverse problems
- Clinical validation studies (SoftVue, Delphinus)

## Research Directions to Explore

1. **Full-waveform inversion convergence** — local minima, cycle skipping, initialization strategies (similar challenges to seismic FWI)
2. **Multi-physics coupling** — joint reconstruction of speed-of-sound + attenuation + elasticity
3. **Deep learning priors for USCT** — learned regularizers, physics-informed neural networks (PINNs) as forward surrogates
4. **Stochastic/uncertainty quantification** — Bayesian FWI, posterior sampling for clinical confidence intervals
5. **3-D reconstruction efficiency** — reducing compute cost of 3-D forwarder; GPU acceleration strategies
6. **Dual-mode integration** — combining pulse-echo B-mode with transmission USCT for complementary contrast
7. **Quantitative biomarkers** — what tissue properties (beyond sound speed) are clinically actionable?

## Related Work / People

- James Wiskin (Delphinus / University of Utah lineage)
- Neb Duric (Delphinus Medical Technologies)
- Robert Pratt (seismic FWI foundations)
- Cuiping Li (USCT hardware/clinical)
- Groups at ETH Zurich, TU Delft working on acoustic FWI

## Resources to Gather

- [ ] Wiskin's key USCT papers (JASA, Medical Physics, IEEE UFFC)
- [ ] Delphinus SoftVue clinical trial results
- [ ] Seismic FWI review papers for methodological crossover
- [ ] Open-source acoustic forwarder codes (e.g., k-Wave)
- [ ] FDA 510(k) documentation for USCT breast imaging devices

## Open Questions

- What are the hard theoretical barriers (not just engineering) to sub-millimeter USCT resolution in soft tissue?
- Is there a theoretical framework that unifies speed-of-sound and attenuation reconstruction in a single variational problem with provable convergence?
- How do deep-learning-based inverse solvers compare to classical FWI on phantom/clinical data?

## Status

Idea — not yet started. Initial step: systematic literature review of Wiskin's publication record and citing papers.
