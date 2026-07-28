"""
Unit tests for Feature 1 — CNR intermediate extraction.

Exercises ``_extract_low_contrast_cnr_details`` against lightweight fake
analyzers that mimic pylinac 3.43.2 shapes:

  - ``low_contrast_module.rois`` / ``.background_rois`` are
    ``dict[str, LowContrastDiskROI]`` (single ``"ROI"`` key for ACR CT), not
    lists — extraction must iterate ``.values()``.
  - ``low_contrast_module.cnr`` is a **method**, not a property.

Also covers the numpy-scalar hardening of ``_jsonable`` (np.float32 / np.int64
do not subclass Python float/int on numpy 2.x).
"""

from __future__ import annotations

import types

from qa.pylinac_acr_ct import _extract_low_contrast_cnr_details, _jsonable


class _FakeROI:
    def __init__(self, mean, std, pixel_value=None, contrast_to_noise=None) -> None:
        self.mean = mean
        self.std = std
        self.pixel_value = pixel_value if pixel_value is not None else mean
        self.contrast_to_noise = (
            contrast_to_noise if contrast_to_noise is not None else 1.0
        )


def _analyzer(rois=None, background_rois=None, cnr=None, has_module=True):
    if not has_module:
        return types.SimpleNamespace(low_contrast_module=None)
    lcm = types.SimpleNamespace()
    lcm.rois = rois if rois is not None else {}
    lcm.background_rois = background_rois if background_rois is not None else {}
    if cnr is not None:
        lcm.cnr = lambda: cnr  # method, not property
    return types.SimpleNamespace(low_contrast_module=lcm)


def test_full_extraction() -> None:
    analyzer = _analyzer(
        rois={"ROI": _FakeROI(mean=100.0, std=5.0, pixel_value=100.0, contrast_to_noise=3.0)},
        background_rois={"ROI": _FakeROI(mean=10.0, std=2.0)},
        cnr=4.5,
    )
    out = _extract_low_contrast_cnr_details(analyzer)
    assert out["cnr"] == 4.5
    assert out["object_rois"] == [
        {"mean": 100.0, "pixel_value": 100.0, "contrast_to_noise": 3.0}
    ]
    assert out["background"]["mean"] == 10.0
    assert out["background"]["std"] == 2.0
    assert out["background"]["means"] == [10.0]
    assert out["background"]["stds"] == [2.0]


def test_missing_module_returns_empty() -> None:
    assert _extract_low_contrast_cnr_details(_analyzer(has_module=False)) == {}
    assert _extract_low_contrast_cnr_details(types.SimpleNamespace()) == {}


def test_partial_no_background() -> None:
    analyzer = _analyzer(
        rois={"ROI": _FakeROI(mean=50.0, std=1.0)},
        background_rois={},
        cnr=2.0,
    )
    out = _extract_low_contrast_cnr_details(analyzer)
    assert out["cnr"] == 2.0
    assert "object_rois" in out
    assert "background" not in out


def test_cnr_method_failure_degrades() -> None:
    lcm = types.SimpleNamespace(rois={}, background_rois={})

    def _boom():
        raise RuntimeError("cnr blew up")

    lcm.cnr = _boom
    out = _extract_low_contrast_cnr_details(types.SimpleNamespace(low_contrast_module=lcm))
    assert out == {}  # nothing harvestable, but no exception


def test_bad_roi_attributes_are_skipped() -> None:
    good = _FakeROI(mean=100.0, std=5.0)
    bad = types.SimpleNamespace()  # no .mean/.std -> AttributeError, skipped
    analyzer = _analyzer(
        rois={"ROI": good, "BAD": bad},
        background_rois={"ROI": good, "BAD": bad},
        cnr=1.0,
    )
    out = _extract_low_contrast_cnr_details(analyzer)
    assert len(out["object_rois"]) == 1
    assert out["background"]["means"] == [100.0]


def test_multiple_background_rois_average() -> None:
    analyzer = _analyzer(
        background_rois={
            "A": _FakeROI(mean=10.0, std=2.0),
            "B": _FakeROI(mean=20.0, std=4.0),
        },
    )
    out = _extract_low_contrast_cnr_details(analyzer)
    assert out["background"]["mean"] == 15.0
    assert out["background"]["std"] == 3.0


def test_jsonable_numpy_scalars() -> None:
    np = __import__("numpy")
    converted = _jsonable(
        {
            "f32": np.float32(1.5),
            "f64": np.float64(2.5),
            "i64": np.int64(7),
            "i32": np.int32(3),
        }
    )
    assert converted["f32"] == 1.5 and isinstance(converted["f32"], float)
    assert converted["f64"] == 2.5 and isinstance(converted["f64"], float)
    assert converted["i64"] == 7 and isinstance(converted["i64"], int)
    assert converted["i32"] == 3 and isinstance(converted["i32"], int)
