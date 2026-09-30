"""Ordered, Qt-free ACR CT/MRI headline projection shared by CSV and XLSX."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any

from qa.analysis_types import QAResult
from qa.qa_result_flatten import (
    build_metric_rows,
    build_run_provenance,
    extract_low_contrast_cnr_values,
)


@dataclass(frozen=True)
class HeadlineColumn:
    """One stable CSV key and its human-facing XLSX label."""

    key: str
    label: str
    source: str = ""
    modality: str = "all"
    measurement: bool = True


IDENTITY_COLUMNS = (
    HeadlineColumn("series_run_id", "Series/Run ID", measurement=False),
    HeadlineColumn("analysis_type", "Analysis type", measurement=False),
    HeadlineColumn("analysis_status", "Analysis status", measurement=False),
    HeadlineColumn("warnings", "Warnings", measurement=False),
    HeadlineColumn("errors", "Errors", measurement=False),
)

CT_COLUMNS = (
    HeadlineColumn("acr_ct_cnr", "CT low-contrast CNR (pylinac)", modality="acr_ct"),
    HeadlineColumn(
        "acr_ct_cnr_mean_based", "CT low-contrast CNR (mean-based, viewer)",
        modality="acr_ct",
    ),
    HeadlineColumn(
        "acr_ct_mtf50_lpmm",
        "CT MTF@50% (lp/mm, pylinac)",
        "acr_ct_mtf50_lpmm",
        "acr_ct",
    ),
    *(
        HeadlineColumn(
            f"acr_ct_hu_{name.lower()}",
            f"CT number: {name} (HU)",
            f"ct_module.rois.{name}",
            "acr_ct",
        )
        for name in ("Water", "Air", "Poly", "Acrylic", "Bone")
    ),
    *(
        HeadlineColumn(
            f"acr_ct_uniformity_hu_{name.lower()}",
            f"Uniformity: {name} (HU)",
            f"uniformity_module.rois.{name}",
            "acr_ct",
        )
        for name in ("Center", "Top", "Right", "Bottom", "Left")
    ),
    HeadlineColumn(
        "acr_ct_uniformity_center_std_hu",
        "Uniformity center ROI SD (HU)",
        "uniformity_module.center_roi_stdev",
        "acr_ct",
    ),
    HeadlineColumn(
        "acr_ct_cnr_object_median_hu", "CNR object ROI median (HU)", modality="acr_ct"
    ),
    HeadlineColumn(
        "acr_ct_cnr_background_median_hu", "CNR background median (HU)", modality="acr_ct"
    ),
    HeadlineColumn(
        "acr_ct_cnr_object_mean_hu", "CNR object ROI mean (HU)", modality="acr_ct"
    ),
    HeadlineColumn(
        "acr_ct_cnr_background_mean_hu", "CNR background mean (HU)", modality="acr_ct"
    ),
    HeadlineColumn(
        "acr_ct_cnr_background_std_hu", "CNR background SD (HU)", modality="acr_ct"
    ),
)

MRI_COLUMNS = (
    HeadlineColumn(
        "acr_mri_pylinac_percentile_piu_pct",
        "MRI PIU (%; pylinac percentile method)",
        "uniformity_module.piu",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_psg_pct",
        "MRI percent signal ghosting (%)",
        "uniformity_module.psg",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_low_contrast_spokes",
        "MRI low-contrast complete-spoke score (pylinac)",
        "low_contrast_score",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_row_mtf50_lpmm",
        "MRI row MTF@50% (lp/mm; pylinac proxy)",
        "slice1.row_mtf_50",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_col_mtf50_lpmm",
        "MRI column MTF@50% (lp/mm; pylinac proxy)",
        "slice1.col_mtf_50",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_measured_slice_thickness_mm",
        "MRI measured slice thickness (mm)",
        "slice1.measured_slice_thickness_mm",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_slice1_shift_mm",
        "MRI slice 1 position shift (mm)",
        "slice1.slice_shift_mm",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_slice11_shift_mm",
        "MRI slice 11 position shift (mm)",
        "slice11.slice_shift_mm",
        "acr_mri_large",
    ),
    *(
        HeadlineColumn(
            f"acr_mri_axial_{key.replace(' ', '_')}_mm",
            f"MRI axial {key} (mm)",
            f"geometric_distortion_module.profiles.{key}.width (mm)",
            "acr_mri_large",
        )
        for key in ("horizontal", "vertical", "negative diagonal", "positive diagonal")
    ),
    *(
        HeadlineColumn(
            f"acr_mri_sagittal_roi{idx}_mm",
            f"MRI sagittal ROI{idx} length (mm)",
            f"sagittal_localizer_module.profiles.ROI{idx}.width (mm)",
            "acr_mri_large",
        )
        for idx in range(1, 5)
    ),
    HeadlineColumn(
        "acr_mri_viewer_snr_uncorrected",
        "Viewer MRI SNR (uncorrected)",
        "mri_snr",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_snr_signal_mean",
        "MRI SNR signal mean (stored pixel value)",
        "mri_snr_signal_mean",
        "acr_mri_large",
    ),
    HeadlineColumn(
        "acr_mri_snr_background_noise",
        "MRI SNR background noise (stored pixel value SD)",
        "mri_snr_noise_mean",
        "acr_mri_large",
    ),
)

AUDIT_COLUMNS = (
    HeadlineColumn("success", "Analysis completed", measurement=False),
    HeadlineColumn("label", "Run label", measurement=False),
    HeadlineColumn("pylinac_version", "pylinac version", measurement=False),
    HeadlineColumn("num_images", "Image count", measurement=False),
    HeadlineColumn("study_uid", "Study UID", measurement=False),
    HeadlineColumn("series_uid", "Series UID", measurement=False),
    HeadlineColumn("modality", "DICOM modality", measurement=False),
    HeadlineColumn("analysis_profile_summary", "Analysis profile", measurement=False),
)


def columns_for(results: list[QAResult]) -> tuple[HeadlineColumn, ...]:
    """Return identity, applicable modality, and audit columns.

    With no runs, emit the specified 12-column identity/audit header. The
    profile summary is run-specific, and no modality can be inferred.
    """
    if not results:
        return (*IDENTITY_COLUMNS, *AUDIT_COLUMNS[:-1])
    types = {result.analysis_type for result in results}
    return (
        *IDENTITY_COLUMNS,
        *(CT_COLUMNS if "acr_ct" in types else ()),
        *(MRI_COLUMNS if "acr_mri_large" in types else ()),
        *AUDIT_COLUMNS,
    )


def _finite_number(value: Any) -> int | float | str:
    """Keep only finite numeric measurement scalars; blank everything else."""
    if isinstance(value, bool) or not isinstance(value, Real):
        return ""
    if not math.isfinite(value):
        return ""
    return value if isinstance(value, int) else float(value)


def _profile_summary(profile: dict[str, Any] | None) -> str:
    """Render known analysis choices without serializing a Python dict repr."""
    profile = profile or {}
    parts = [f"engine={profile['engine']}"] if profile.get("engine") else []
    for key in ("vanilla_pylinac", "echo_number", "low_contrast_method"):
        value = profile.get(key)
        if value is not None and value != "":
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def _audit_value(
    result: QAResult,
    column: HeadlineColumn,
    provenance: dict[str, Any],
    flat: dict[str, Any],
    label: str | None,
) -> Any:
    """Render identity and audit fields without measurement coercion."""
    if column.key == "series_run_id":
        return label or result.series_uid or ""
    if column.key == "analysis_status":
        return "success" if result.success else "failed"
    if column.key in ("warnings", "errors"):
        return "; ".join(str(item) for item in provenance[column.key])
    if column.key == "analysis_profile_summary":
        return _profile_summary(result.pylinac_analysis_profile)
    if column.key == "num_images" and "num_images" in flat:
        # Match build_tabular_run's established metric-wins collision rule.
        return flat["num_images"]
    return provenance.get(column.key)


def _mean_based_cnr_value(
    cnr_details: dict[str, Any], obj_mean: Any, bg_mean: Any, bg_std: Any
) -> Any:
    """Use a harvested viewer CNR, or derive it from older run inputs."""
    mean_based_cnr = cnr_details.get("mean_based_cnr")
    if (
        mean_based_cnr is None
        and isinstance(obj_mean, (int, float))
        and isinstance(bg_mean, (int, float))
        and isinstance(bg_std, (int, float))
        and math.isfinite(obj_mean)
        and math.isfinite(bg_mean)
        and math.isfinite(bg_std)
        and bg_std > 0
    ):
        mean_based_cnr = abs(obj_mean - bg_mean) / bg_std
    return mean_based_cnr


def _ct_cnr_values(metrics: dict[str, Any], flat: dict[str, Any]) -> dict[str, Any]:
    """Read curated CNR inputs and derive a mean-based value for older runs."""
    metrics = metrics or {}
    obj_mean, bg_mean, bg_std, cnr = extract_low_contrast_cnr_values(metrics)
    cnr_details = metrics.get("low_contrast_cnr")
    cnr_details = cnr_details if isinstance(cnr_details, dict) else {}
    object_rois = cnr_details.get("object_rois")
    object_roi = (
        object_rois[0]
        if isinstance(object_rois, list) and len(object_rois) == 1
        else {}
    )
    background = cnr_details.get("background")
    background = background if isinstance(background, dict) else {}
    return {
        "acr_ct_cnr": cnr if cnr is not None else flat.get("low_contrast_module.cnr"),
        "acr_ct_cnr_mean_based": _mean_based_cnr_value(
            cnr_details, obj_mean, bg_mean, bg_std
        ),
        "acr_ct_cnr_object_median_hu": (
            object_roi.get("pixel_value") if isinstance(object_roi, dict) else None
        ),
        "acr_ct_cnr_background_median_hu": background.get("pixel_value"),
        "acr_ct_cnr_object_mean_hu": obj_mean,
        "acr_ct_cnr_background_mean_hu": bg_mean,
        "acr_ct_cnr_background_std_hu": bg_std,
    }


def project_headlines(
    result: QAResult,
    columns: tuple[HeadlineColumn, ...],
    *,
    label: str | None = None,
) -> dict[str, Any]:
    """Project one run; leave other-modality and unavailable measurements blank."""
    flat = dict(build_metric_rows(result))
    provenance = build_run_provenance(result, label=label)
    special = {
        **_ct_cnr_values(result.metrics, flat),
        "acr_mri_low_contrast_spokes": (
            flat.get("low_contrast_score")
            if flat.get("low_contrast_score") is not None
            else flat.get("low_contrast_multi_slice_module.score")
        ),
    }
    row: dict[str, Any] = {}
    for column in columns:
        if (column.modality != "all" and column.modality != result.analysis_type) or (
            column.measurement and not result.success
        ):
            row[column.key] = ""
        elif column.measurement:
            row[column.key] = _finite_number(
                special[column.key]
                if column.key in special
                else flat.get(column.source)
            )
        else:
            row[column.key] = _audit_value(result, column, provenance, flat, label)
    return row
