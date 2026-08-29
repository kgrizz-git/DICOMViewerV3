"""Unit tests for ACR-style MRI SNR harvest (mocked uniformity module)."""

from __future__ import annotations

from types import SimpleNamespace

from qa.analysis_types import QAResult
from qa.pylinac_mri_snr import (
    extract_mri_snr_acr_style,
    frequency_encode_ghost_roi_names,
    overlay_mri_snr_metrics,
    phase_encoding_direction_from_analyzer,
)
from qa.qa_result_flatten import build_metric_rows


def _roi(*, mean: float, std: float) -> SimpleNamespace:
    return SimpleNamespace(pixel_value=mean, mean=mean, std=std)


def _analyzer(
    *,
    phase: str | None = "ROW",
    center: float = 100.0,
    left_std: float = 2.0,
    right_std: float = 4.0,
    top_std: float = 20.0,
    bottom_std: float = 20.0,
) -> SimpleNamespace:
    metadata = SimpleNamespace()
    if phase is not None:
        metadata.InPlanePhaseEncodingDirection = phase
    return SimpleNamespace(
        dicom_stack=SimpleNamespace(metadata=metadata),
        uniformity_module=SimpleNamespace(
            rois={"Center": _roi(mean=center, std=1.0)},
            ghost_rois={
                "Top": _roi(mean=1.0, std=top_std),
                "Bottom": _roi(mean=1.0, std=bottom_std),
                "Left": _roi(mean=1.0, std=left_std),
                "Right": _roi(mean=1.0, std=right_std),
            },
        ),
    )


def test_frequency_encode_pair_follows_phase_direction() -> None:
    """pylinac ghost_rois are spatial: ghosts lie on the phase-encode axis."""
    assert frequency_encode_ghost_roi_names("ROW") == ("Left", "Right")
    assert frequency_encode_ghost_roi_names("COL") == ("Top", "Bottom")


def test_missing_phase_tag_falls_back_to_row() -> None:
    analyzer = SimpleNamespace(dicom_stack=SimpleNamespace(metadata=SimpleNamespace()))
    phase, used_fallback = phase_encoding_direction_from_analyzer(analyzer)
    assert phase == "ROW"
    assert used_fallback is True


def test_snr_uses_left_right_when_phase_is_row() -> None:
    harvested = extract_mri_snr_acr_style(_analyzer(phase="ROW", center=100.0))
    assert harvested is not None
    assert harvested["mri_snr"] == 100.0 / 3.0
    assert harvested["mri_snr_signal_mean"] == 100.0
    assert harvested["mri_snr_noise_mean"] == 3.0
    assert harvested["mri_snr_noise_roi_pair"] == "Left/Right"
    assert harvested["mri_snr_phase_encoding_direction"] == "ROW"
    assert harvested["mri_snr_phase_encoding_fallback"] is False


def test_snr_uses_top_bottom_when_phase_is_col() -> None:
    harvested = extract_mri_snr_acr_style(
        _analyzer(phase="COL", center=80.0, top_std=4.0, bottom_std=6.0)
    )
    assert harvested is not None
    assert harvested["mri_snr"] == 80.0 / 5.0
    assert harvested["mri_snr_noise_roi_pair"] == "Top/Bottom"


def test_snr_does_not_apply_nema_rayleigh_factor() -> None:
    harvested = extract_mri_snr_acr_style(_analyzer(phase="ROW", center=100.0))
    assert harvested is not None
    # 0.655 × 100/3 would be ~21.83; uncorrected is 100/3.
    assert harvested["mri_snr"] == 100.0 / 3.0


def test_snr_returns_none_when_noise_is_zero() -> None:
    harvested = extract_mri_snr_acr_style(
        _analyzer(phase="ROW", left_std=0.0, right_std=0.0)
    )
    assert harvested is None


def test_snr_returns_none_without_uniformity_module() -> None:
    assert extract_mri_snr_acr_style(SimpleNamespace()) is None


def test_overlay_warns_when_snr_cannot_be_computed() -> None:
    metrics: dict[str, object] = {}
    warnings: list[str] = []
    overlay_mri_snr_metrics(metrics, SimpleNamespace(), warnings=warnings)
    assert "mri_snr" not in metrics
    assert len(warnings) == 1
    assert "MRI SNR not computed" in warnings[0]


def test_flatten_overlays_top_level_mri_snr() -> None:
    result = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"mri_snr": 42.5, "mri_snr_signal_mean": 85.0},
        raw_pylinac={"uniformity_module": {"piu": 99.0}},
    )
    rows = dict(build_metric_rows(result))
    assert rows["mri_snr"] == 42.5
    assert rows["mri_snr_signal_mean"] == 85.0
    assert rows["uniformity_module.piu"] == 99.0
