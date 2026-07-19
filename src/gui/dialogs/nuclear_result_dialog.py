"""
Result dialog for nuclear-medicine QC (pylinac.nuclear) runs.

Unlike the ACR summary message box, nuclear output is the on-screen
deliverable (there is no PDF), so this shows the per-frame uniformity metrics
in a table and offers direct Export JSON / Export CSV / Save Figure buttons.
Drops ACR-only concepts (PDF line, stock/vanilla mode). Figure rendering runs
on the main thread (see qa.pylinac_nuclear_plots).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qa.analysis_types import QAResult
from qa.qa_export import (
    build_nuclear_flat_csv,
    build_nuclear_frames_csv,
    build_nuclear_quadrants_csv,
    build_nuclear_spheres_csv,
    build_single_run_document,
)

# (metric key, column header) for the per-frame table, in display order.
_FRAME_FIELDS: tuple[tuple[str, str], ...] = (
    ("ufov_integral_uniformity", "UFOV integral %"),
    ("ufov_differential_uniformity", "UFOV differential %"),
    ("cfov_integral_uniformity", "CFOV integral %"),
    ("cfov_differential_uniformity", "CFOV differential %"),
)

# (metric key, column header) for the per-quadrant table, in display order.
_QUADRANT_FIELDS: tuple[tuple[str, str], ...] = (
    ("mtf", "MTF"),
    ("fwhm", "FWHM"),
    ("lpmm", "lp/mm"),
    ("spacing", "Spacing (mm)"),
)

# (metric key, column header) for the per-sphere table, in display order.
_SPHERE_FIELDS: tuple[tuple[str, str], ...] = (
    ("x", "x"),
    ("y", "y"),
    ("z", "z"),
    ("radius", "Radius"),
    ("mean", "Mean"),
    ("mean_contrast", "Mean contrast"),
    ("max_contrast", "Max contrast"),
)

# Callable[[title, default_name, filter_text, *, remember_pylinac_output_dir], str]
PromptSavePath = Callable[..., str]



_UTC_TIMESTAMP_FMT = "%Y%m%dT%H%M%SZ"

def _sorted_frames(frames: dict[str, Any]) -> list[tuple[str, Any]]:
    """Sort frame entries by trailing frame number ('Frame 1', 'Frame 2', ...)."""

    def _key(item: tuple[str, Any]) -> int:
        digits = "".join(ch for ch in str(item[0]) if ch.isdigit())
        return int(digits) if digits else 0

    return sorted(frames.items(), key=_key)


class NuclearResultDialog(QDialog):
    """Show nuclear QC per-frame metrics (or errors) with export buttons."""

    def __init__(
        self,
        result: QAResult,
        *,
        title: str,
        parent: QWidget | None = None,
        inputs: dict[str, Any] | None = None,
        app_version: str = "",
        default_stem: str = "qa-nuclear",
        prompt_save_path: PromptSavePath | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self._result = result
        self._inputs = inputs or {}
        self._app_version = app_version
        self._default_stem = default_stem
        self._prompt_save_path = prompt_save_path
        self._on_status = on_status

        profile = result.pylinac_analysis_profile or {}
        cls = (
            profile.get("nuclear_analysis_class")
            or result.metrics.get("analysis_class")
            or "Nuclear analysis"
        )
        status = "Completed successfully" if result.success else "Analysis failed"

        layout = QVBoxLayout(self)

        header = QLabel(
            f"{cls} — {status}\nPylinac: {result.pylinac_version or 'unknown'}"
        )
        header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(header)

        params = profile.get("analysis_parameters") or result.metrics.get(
            "analysis_parameters"
        ) or {}
        if params:
            ptxt = ", ".join(f"{k}={v}" for k, v in params.items())
            default_note = (
                "  (pylinac defaults)" if profile.get("vanilla_equivalent") else ""
            )
            layout.addWidget(QLabel(f"Parameters: {ptxt}{default_note}"))

        frames = result.metrics.get("frames")
        flat_results = result.metrics.get("results")
        quadrants = result.metrics.get("quadrants")
        spheres = result.metrics.get("spheres")
        baseline = result.metrics.get("uniformity_baseline")
        if result.success and baseline is not None:
            layout.addWidget(QLabel(f"Uniformity baseline: {self._fmt(baseline)}"))
        has_output = bool(
            result.success and (frames or flat_results or quadrants or spheres)
        )
        if result.success and frames:
            layout.addWidget(self._build_frame_table(frames))
        elif result.success and quadrants:
            layout.addWidget(self._build_quadrant_table(quadrants))
        elif result.success and spheres:
            layout.addWidget(self._build_sphere_table(spheres))
        elif result.success and flat_results:
            layout.addWidget(self._build_kv_table(flat_results))
        elif result.success:
            layout.addWidget(QLabel("No metrics were returned for this run."))
        else:
            errors = result.errors or ["Unknown error."]
            err = QLabel("Errors:\n- " + "\n- ".join(errors))
            err.setWordWrap(True)
            err.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(err)

        if result.warnings:
            warn = QLabel("Warnings:\n- " + "\n- ".join(result.warnings[:8]))
            warn.setWordWrap(True)
            layout.addWidget(warn)

        note = QLabel(
            "Raw pylinac metrics for review — not a clinically validated pass/fail "
            "result."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        self._input_path = (
            profile.get("input_path") or self._inputs.get("input_path") or ""
        )
        self._analysis_class = profile.get("nuclear_analysis_class") or ""
        self._analyze_kwargs = (
            profile.get("analysis_parameters")
            or result.metrics.get("analysis_parameters")
            or {}
        )

        buttons = QDialogButtonBox()
        json_btn = buttons.addButton(
            "Export JSON…", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._csv_btn = buttons.addButton(
            "Export CSV…", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._fig_btn = buttons.addButton(
            "Save Figure (PNG)…", QDialogButtonBox.ButtonRole.ActionRole
        )
        close_btn = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        json_btn.clicked.connect(self._export_json)
        self._csv_btn.clicked.connect(self._export_csv)
        self._fig_btn.clicked.connect(self._export_figure)
        close_btn.clicked.connect(self.accept)
        buttons.rejected.connect(self.accept)
        # CSV / figure need a successful run with metrics (frame-keyed or flat).
        self._csv_btn.setEnabled(has_output)
        # Figure also requires a class that exposes plot() (e.g. SimpleSensitivity
        # does not), so the button is disabled rather than erroring on click.
        from qa.pylinac_nuclear_plots import is_plottable

        self._fig_btn.setEnabled(
            bool(has_output and self._input_path and is_plottable(self._analysis_class))
        )
        layout.addWidget(buttons)

    @staticmethod
    def _fmt(value: Any) -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.3f}"
        if value is None:
            return ""
        return str(value)

    @classmethod
    def _build_frame_table(cls, frames: dict[str, Any]) -> QTableWidget:
        rows = _sorted_frames(frames)
        table = QTableWidget(len(rows), 1 + len(_FRAME_FIELDS))
        table.setHorizontalHeaderLabels(
            ["Frame"] + [label for _key, label in _FRAME_FIELDS]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row, (frame_key, values) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(str(frame_key)))
            for col, (field, _label) in enumerate(_FRAME_FIELDS, start=1):
                table.setItem(row, col, QTableWidgetItem(cls._fmt((values or {}).get(field))))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @classmethod
    def _build_kv_table(cls, results: dict[str, Any]) -> QTableWidget:
        """Two-column Metric/Value table for a flat (non-frame) result."""
        items = list(results.items())
        table = QTableWidget(len(items), 2)
        table.setHorizontalHeaderLabels(["Metric", "Value"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row, (key, value) in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(str(key)))
            table.setItem(row, 1, QTableWidgetItem(cls._fmt(value)))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @classmethod
    def _build_quadrant_table(cls, quadrants: dict[str, Any]) -> QTableWidget:
        """One row per quadrant; columns are MTF/FWHM/lp-mm/spacing."""
        rows = sorted(quadrants.items(), key=lambda kv: str(kv[0]))
        table = QTableWidget(len(rows), 1 + len(_QUADRANT_FIELDS))
        table.setHorizontalHeaderLabels(
            ["Quadrant"] + [label for _key, label in _QUADRANT_FIELDS]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row, (quad_key, values) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(str(quad_key)))
            for col, (field, _label) in enumerate(_QUADRANT_FIELDS, start=1):
                table.setItem(row, col, QTableWidgetItem(cls._fmt((values or {}).get(field))))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @classmethod
    def _build_sphere_table(cls, spheres: dict[str, Any]) -> QTableWidget:
        """One row per sphere; columns are x/y/z/radius/mean/contrast."""
        rows = sorted(spheres.items(), key=lambda kv: str(kv[0]))
        table = QTableWidget(len(rows), 1 + len(_SPHERE_FIELDS))
        table.setHorizontalHeaderLabels(
            ["Sphere"] + [label for _key, label in _SPHERE_FIELDS]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row, (sphere_key, values) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(str(sphere_key)))
            for col, (field, _label) in enumerate(_SPHERE_FIELDS, start=1):
                table.setItem(row, col, QTableWidgetItem(cls._fmt((values or {}).get(field))))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _save_path(self, title: str, default_name: str, filter_text: str) -> str:
        if self._prompt_save_path is not None:
            return self._prompt_save_path(
                title, default_name, filter_text, remember_pylinac_output_dir=True
            )
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, filter_text)
        return path

    def _notify(self, message: str) -> None:
        if self._on_status is not None:
            self._on_status(message)

    def _export_json(self) -> None:
        ts = datetime.now(UTC).strftime(_UTC_TIMESTAMP_FMT)
        path = self._save_path(
            "Save QA Results JSON",
            f"{self._default_stem}-{ts}.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        doc = build_single_run_document(
            self._result, app_version=self._app_version, inputs=self._inputs
        )
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=2)
        self._notify(f"Saved QA JSON: {path}")

    def _export_csv(self) -> None:
        ts = datetime.now(UTC).strftime(_UTC_TIMESTAMP_FMT)
        path = self._save_path(
            "Save QA Results CSV",
            f"{self._default_stem}-{ts}.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        # Pick the CSV layout by result shape.
        if self._result.metrics.get("frames"):
            text = build_nuclear_frames_csv(self._result)
        elif self._result.metrics.get("quadrants"):
            text = build_nuclear_quadrants_csv(self._result)
        elif self._result.metrics.get("spheres"):
            text = build_nuclear_spheres_csv(self._result)
        else:
            text = build_nuclear_flat_csv(self._result)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        self._notify(f"Saved QA CSV: {path}")

    def _export_figure(self) -> None:
        if not self._input_path:
            QMessageBox.warning(
                self, "Save Figure", "The source DICOM path is unknown for this run."
            )
            return
        ts = datetime.now(UTC).strftime(_UTC_TIMESTAMP_FMT)
        path = self._save_path(
            "Save Analyzed Figure (PNG)",
            f"{self._default_stem}-{ts}.png",
            "PNG Files (*.png)",
        )
        if not path:
            return
        # Imported lazily and run on the main thread (Qt-safe figure creation).
        from qa.pylinac_nuclear_plots import render_nuclear_figures

        try:
            saved = render_nuclear_figures(
                self._input_path,
                analysis_class=self._analysis_class,
                analyze_kwargs=self._analyze_kwargs,
                out_path=path,
            )
        except Exception:  # show a safe error, do not crash the dialog
            QMessageBox.warning(
                self,
                "Figure export failed",
                "The figure could not be exported. Details were withheld to protect private data.",
            )
            return
        if not saved:
            return
        if len(saved) == 1:
            self._notify(f"Saved figure: {saved[0]}")
        else:
            self._notify(
                f"Saved {len(saved)} figures to {os.path.dirname(saved[0])}"
            )


def show_nuclear_result_dialog(
    parent: QWidget | None,
    title: str,
    result: QAResult,
    *,
    inputs: dict[str, Any] | None = None,
    app_version: str = "",
    default_stem: str = "qa-nuclear",
    prompt_save_path: PromptSavePath | None = None,
    on_status: Callable[[str], None] | None = None,
) -> None:
    """Show the modal nuclear result dialog with export buttons."""
    dlg = NuclearResultDialog(
        result,
        title=title,
        parent=parent,
        inputs=inputs,
        app_version=app_version,
        default_stem=default_stem,
        prompt_save_path=prompt_save_path,
        on_status=on_status,
    )
    dlg.activateWindow()
    dlg.raise_()
    dlg.exec()
