"""
Stage 1 pylinac runner entrypoints (facade module).

This module re-exports all public functions from the domain-split modules so
existing callers (worker.py, tests) do not need to change import paths.

Domain modules:
    qa.pylinac_acr_ct   -- ACR CT analysis entrypoints and helpers
    qa.pylinac_acr_mri  -- ACR MRI Large analysis (single run + compare batch)
    qa.pylinac_mri_pdf  -- MRI PDF notes builders and compare PDF assembly
    qa.pylinac_nuclear  -- nuclear-medicine QA (PlanarUniformity, ...)

Public functions (all re-exported here for backward compatibility):
    run_acr_ct_analysis(request)          -- single-run ACR CT analysis
    run_acr_mri_large_analysis(request)   -- single-run ACR MRI Large analysis
    run_acr_mri_large_batch(base, configs)-- multi-run compare-mode batch;
                                            produces a combined PDF via pypdf
    build_mri_pdf_notes(result)           -- always-on interpretation notes (List[str])
    build_mri_compare_pdf_notes(batch)    -- comparison table + notes (List[str])
    build_mri_compare_summary_pdf(batch, path) -- viewer-authored summary PDF
    assemble_mri_compare_pdf(summary, runs, out) -- merge summary + run PDFs

Requirements:
    pylinac (optional, graceful fallback when missing)
    pypdf>=4.0.0 (optional, graceful fallback when missing)
    reportlab (transitively installed by pylinac)
    qa.analysis_types.QARequest / QAResult / LcRunConfig / MRIBatchResult
    qa.pylinac_extent_subclasses (ACRCTForViewer, ACRMRILargeForViewer; RelaxedExtent aliases)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Re-exports — all public names remain stable at qa.pylinac_runner.*
# ---------------------------------------------------------------------------
from qa.pylinac_acr_ct import run_acr_ct_analysis
from qa.pylinac_acr_mri import run_acr_mri_large_analysis, run_acr_mri_large_batch
from qa.pylinac_mri_pdf import (
    assemble_mri_compare_pdf,
    build_mri_compare_pdf_notes,
    build_mri_compare_summary_pdf,
    build_mri_pdf_notes,
)
from qa.pylinac_nuclear import (
    NUCLEAR_ANALYSIS_TYPES,
    run_center_of_rotation_analysis,
    run_four_bar_resolution_analysis,
    run_max_count_rate_analysis,
    run_nuclear_analysis,
    run_planar_uniformity_analysis,
    run_quadrant_resolution_analysis,
    run_simple_sensitivity_analysis,
    run_tomographic_contrast_analysis,
    run_tomographic_resolution_analysis,
    run_tomographic_uniformity_analysis,
)

__all__ = [
    "NUCLEAR_ANALYSIS_TYPES",
    "assemble_mri_compare_pdf",
    "build_mri_compare_pdf_notes",
    "build_mri_compare_summary_pdf",
    "build_mri_pdf_notes",
    "run_acr_ct_analysis",
    "run_acr_mri_large_analysis",
    "run_acr_mri_large_batch",
    "run_center_of_rotation_analysis",
    "run_four_bar_resolution_analysis",
    "run_max_count_rate_analysis",
    "run_nuclear_analysis",
    "run_planar_uniformity_analysis",
    "run_quadrant_resolution_analysis",
    "run_simple_sensitivity_analysis",
    "run_tomographic_contrast_analysis",
    "run_tomographic_resolution_analysis",
    "run_tomographic_uniformity_analysis",
]
