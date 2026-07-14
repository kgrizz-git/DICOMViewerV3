"""
Gate B end-to-end smoke for the nuclear QC flow (plan Gate B).

Drives the REAL QAAppFacade.open_nuclear_qc_analysis path: real options ->
real QAAnalysisWorker thread -> real pylinac.nuclear -> real JSON export, on a
real IAEA NMQC image. Only the modal prompts are auto-answered (the options
dialog is stubbed; the result message box is recorded instead of shown), which
is exactly what a manual tester would click through.

Gated on DICOMVIEWER_NMQC_SAMPLE_PATH (skips in CI; no data committed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import gui.qa_app_facade as facade_mod
from gui.qa_app_facade import QAAppFacade
from qa.analysis_types import PlanarUniformityOptions, QAResult

pytestmark = pytest.mark.qt

_SAMPLE_ROOT = os.environ.get("DICOMVIEWER_NMQC_SAMPLE_PATH")

_skip = pytest.mark.skipif(
    not _SAMPLE_ROOT or not Path(_SAMPLE_ROOT).exists(),
    reason="DICOMVIEWER_NMQC_SAMPLE_PATH not set to an existing NMQC sample folder",
)

_UNIFORMITY = "Uniformity/UNIFORMIDAD_1_Ok.dcm"


def _make_main_window():
    """A real QWidget so it can parent QMessageBox/QProgressDialog."""
    from PySide6.QtWidgets import QWidget

    class _MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.status: list[str] = []

        def update_status(self, msg: str) -> None:
            self.status.append(msg)

    return _MainWindow()


class _FileDialog:
    def __init__(self, path: str):
        self._path = path

    def open_files(self, parent=None):
        return [self._path]


class _FakeApp:
    def __init__(self, sample_path: str, json_out: str):
        self.main_window = _make_main_window()
        self.file_dialog = _FileDialog(sample_path)
        self._json_out = json_out
        self._qa_worker = None

    def _resolve_focused_series_ordered_paths(self):
        # No focused series -> facade falls through to the file picker.
        return "", "", "", [], []

    def _prompt_save_path(self, title, default_name, filter_text, *, remember_pylinac_output_dir=False):
        return self._json_out


@_skip
def test_nuclear_qc_end_to_end_real_app_path(qapp, tmp_path, monkeypatch) -> None:
    import time

    from PySide6.QtWidgets import QApplication

    sample = Path(_SAMPLE_ROOT) / _UNIFORMITY
    if not sample.exists():
        pytest.skip(f"sample not present: {_UNIFORMITY}")

    json_out = str(tmp_path / "nuclear_e2e.json")
    app = _FakeApp(str(sample), json_out)
    fac = QAAppFacade(app)

    # Auto-answer the options dialog (manual tester clicks OK with defaults).
    monkeypatch.setattr(
        facade_mod, "prompt_nuclear_options", lambda parent=None: PlanarUniformityOptions()
    )

    # The facade imports show_nuclear_result_dialog locally from the dialog
    # module; stub it there. Instead of exec()-ing the modal, build the REAL
    # dialog and drive its real Export JSON handler (manual tester clicks it).
    import gui.dialogs.nuclear_result_dialog as nrd

    captured: dict[str, QAResult] = {}

    def _fake_show(parent, title, result, **kwargs):
        captured["result"] = result
        dlg = nrd.NuclearResultDialog(result, title=title, parent=parent, **kwargs)
        dlg._export_json()
        dlg.deleteLater()

    monkeypatch.setattr(nrd, "show_nuclear_result_dialog", _fake_show)

    fac.open_nuclear_qc_analysis()

    # Pump events until the queued cross-thread result is delivered (or time out).
    # Polling avoids a race where a fast worker finishes before we'd start a loop.
    worker = app._qa_worker
    assert worker is not None, "worker was not started"
    deadline = time.time() + 30
    while "result" not in captured and time.time() < deadline:
        QApplication.processEvents()
        worker.wait(20)  # block up to 20 ms for thread completion (not a sleep)
    QApplication.processEvents()

    # Result captured and successful.
    result = captured.get("result")
    assert result is not None, "no result reached the result dialog"
    assert result.success is True, result.errors
    assert result.metrics["frame_count"] >= 1
    assert result.pylinac_analysis_profile["module"] == "pylinac.nuclear"

    # JSON export was written with the nuclear payload.
    assert Path(json_out).exists(), "JSON export was not written"
    with open(json_out, encoding="utf-8") as handle:
        doc = json.load(handle)
    assert doc["run"]["analysis_type"] == "nuclear_planar_uniformity"
    assert doc["run"]["status"] == "success"
    assert doc["pylinac_analysis_profile"]["nuclear_analysis_class"] == "PlanarUniformity"
    assert "Frame 1" in doc["raw_pylinac"]
    assert doc["inputs"]["nuclear_analysis_class"] == "PlanarUniformity"

    app.main_window.deleteLater()
