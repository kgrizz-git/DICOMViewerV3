"""
JSON export tests for nuclear QA (plan T13).

Drives QAAppFacade.export_qa_json with a synthetic nuclear QAResult and a fake
app (no QApplication / no pylinac needed) and asserts the schema fields,
including the self-describing run.nuclear_analysis_class added for nuclear runs.
"""

from __future__ import annotations

import json
from pathlib import Path

from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import (
    PlanarUniformityOptions,
    QARequest,
    QAResult,
    build_nuclear_analysis_profile,
)

_FRAMES = {
    "Frame 1": {
        "ufov_integral_uniformity": 2.38,
        "ufov_differential_uniformity": 1.84,
        "cfov_integral_uniformity": 2.38,
        "cfov_differential_uniformity": 1.73,
    },
    "Frame 2": {
        "ufov_integral_uniformity": 2.55,
        "ufov_differential_uniformity": 1.90,
        "cfov_integral_uniformity": 2.50,
        "cfov_differential_uniformity": 1.80,
    },
}


class _MainWindow:
    def __init__(self):
        self.status: list[str] = []

    def update_status(self, msg: str) -> None:
        self.status.append(msg)


class _FakeApp:
    def __init__(self, out_path: str):
        self.main_window = _MainWindow()
        self._out_path = out_path

    def _prompt_save_path(self, title, default_name, filter_text, *, remember_pylinac_output_dir=False):
        return self._out_path


def _nuclear_result() -> QAResult:
    req = QARequest(
        analysis_type="nuclear_planar_uniformity",
        dicom_paths=["planar.dcm"],
        modality="NM",
        nuclear_options=PlanarUniformityOptions(),
    )
    return QAResult(
        success=True,
        analysis_type="nuclear_planar_uniformity",
        metrics={
            "analysis_class": "PlanarUniformity",
            "frame_count": 2,
            "frames": _FRAMES,
            "analysis_parameters": PlanarUniformityOptions().analyze_kwargs(),
        },
        warnings=["Focused series Modality is 'CT' but this analysis targets NM."],
        errors=[],
        raw_pylinac=_FRAMES,
        modality="NM",
        num_images=1,
        pylinac_version="3.43.2",
        pylinac_analysis_profile=build_nuclear_analysis_profile(
            req, engine="PlanarUniformity"
        ),
    )


def test_nuclear_export_schema_and_fields(tmp_path) -> None:
    json_out = str(tmp_path / "nuclear.json")
    app = _FakeApp(json_out)
    QAAppFacade(app).export_qa_json(
        _nuclear_result(),
        "qa-nuclear-planar-uniformity",
        {"input_path": "planar.dcm", "nuclear_analysis_class": "PlanarUniformity"},
    )

    assert Path(json_out).exists()
    doc = json.loads(Path(json_out).read_text(encoding="utf-8"))

    assert doc["schema_version"] == "1.1"
    assert doc["run"]["analysis_type"] == "nuclear_planar_uniformity"
    assert doc["run"]["status"] == "success"
    # Self-describing nuclear class on the run object.
    assert doc["run"]["nuclear_analysis_class"] == "PlanarUniformity"
    # Per-frame metrics preserved.
    assert doc["metrics"]["frame_count"] == 2
    assert set(doc["metrics"]["frames"]["Frame 1"]) == {
        "ufov_integral_uniformity",
        "ufov_differential_uniformity",
        "cfov_integral_uniformity",
        "cfov_differential_uniformity",
    }
    # Provenance + warnings carried through.
    assert doc["pylinac_analysis_profile"]["module"] == "pylinac.nuclear"
    assert doc["pylinac_analysis_profile"]["nuclear_analysis_class"] == "PlanarUniformity"
    assert any("targets NM" in w for w in doc["warnings"])
    assert "Frame 1" in doc["raw_pylinac"]
    assert app.main_window.status and "Saved QA JSON" in app.main_window.status[-1]


def test_acr_export_has_no_nuclear_class(tmp_path) -> None:
    """ACR exports must not gain the nuclear-only run key."""
    json_out = str(tmp_path / "acr.json")
    app = _FakeApp(json_out)
    acr_result = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={"input_count": 1},
        pylinac_version="3.43.2",
        pylinac_analysis_profile={"engine": "ACRCTForViewer", "vanilla_pylinac": False},
    )
    QAAppFacade(app).export_qa_json(acr_result, "qa-acr-ct", {})
    doc = json.loads(Path(json_out).read_text(encoding="utf-8"))
    assert "nuclear_analysis_class" not in doc["run"]


def _acr_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={"catphan_model": "CatPhan504", "phantom_roll": 0.31, "num_images": 40},
        pylinac_version="3.43.2",
        pylinac_analysis_profile={"engine": "ACRCTForViewer", "vanilla_pylinac": False},
    )


def test_export_qa_results_writes_json_by_extension(tmp_path) -> None:
    out = str(tmp_path / "acr.json")
    app = _FakeApp(out)
    QAAppFacade(app).export_qa_results(_acr_result(), "qa-acr-ct", {})
    doc = json.loads(Path(out).read_text(encoding="utf-8"))
    assert doc["run"]["analysis_type"] == "acr_ct"
    assert app.main_window.status[-1].startswith("Saved QA JSON")


def test_export_qa_results_writes_csv_by_extension(tmp_path) -> None:
    out = str(tmp_path / "acr.csv")
    app = _FakeApp(out)
    QAAppFacade(app).export_qa_results(_acr_result(), "qa-acr-ct", {})
    text = Path(out).read_text(encoding="utf-8")
    assert text.splitlines()[0] == "metric,value"
    assert "catphan_model,CatPhan504" in text
    assert app.main_window.status[-1].startswith("Saved QA CSV")


def test_export_qa_results_appends_json_when_no_extension(tmp_path) -> None:
    out = str(tmp_path / "acr_noext")
    app = _FakeApp(out)
    QAAppFacade(app).export_qa_results(_acr_result(), "qa-acr-ct", {})
    assert Path(out + ".json").exists()
