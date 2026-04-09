"""
ACR CT/MRI pylinac QA flows for DICOMViewerApp.

Hosts preflight, single-run worker, MRI compare batch, result dialogs, and JSON
export logic previously on ``DICOMViewerApp`` in ``main.py``. Signal slots stay
on the app as thin delegates (see ``app_signal_wiring`` for ACR menu actions).

Inputs:
    - ``DICOMViewerApp`` reference: ``main_window``, ``file_dialog``,
      ``config_manager``, ``_prompt_save_path``, ``_resolve_focused_series_ordered_paths``,
      worker/dialog attributes, etc.

Outputs:
    - UI dialogs, JSON/PDF path prompts, worker threads.

Requirements:
    - Same Qt / pydicom / qa package stack as the main application.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMessageBox, QProgressDialog
from pydicom.dataset import Dataset

from gui.dialogs.acr_ct_qa_dialog import prompt_acr_ct_options
from gui.dialogs.acr_mri_qa_dialog import prompt_acr_mri_options
from gui.dialogs.mri_compare_result_dialog import create_mri_compare_result_dialog
from qa.analysis_types import (
    MRIBatchResult,
    MRICompareRequest,
    QARequest,
    QAResult,
    is_physical_scan_extent_failure,
)
from qa.mri_compare_export import build_mri_compare_json_document
from qa.preflight import collect_slice_position_warnings, modality_preflight_warning
from qa.worker import QAAnalysisWorker, QABatchWorker
from version import __version__ as APP_VERSION


class QAAppFacade:
    """Cohesive ACR QA / pylinac entry paths cut from ``DICOMViewerApp``."""

    __slots__ = ("_app",)

    def __init__(self, app: Any) -> None:
        self._app = app

    def build_preflight_warnings(
        self,
        expected_modality: str,
        use_focused: bool,
        folder_path: Optional[str],
        datasets: List[Dataset],
        modality: str,
    ) -> List[str]:
        """Collect Stage 1c preflight warnings (slice order, modality, folder mode)."""
        warnings: List[str] = []
        if folder_path:
            warnings.append(
                "Slice geometry was not verified from DICOM tags (folder input). "
                "Ensure axial stack order matches what pylinac expects."
            )
        elif use_focused and datasets:
            warnings.extend(collect_slice_position_warnings(datasets))
        modality_warn = modality_preflight_warning(modality, expected_modality)
        if modality_warn:
            warnings.append(modality_warn)
        return warnings

    def user_confirms_preflight(self, warnings: List[str]) -> bool:
        """If warnings exist, show them and return True only if the user continues."""
        app = self._app
        if not warnings:
            return True
        text = "Preflight warnings:\n\n- " + "\n- ".join(warnings)
        text += "\n\nContinue with analysis?"
        box = QMessageBox(app.main_window)
        box.setWindowTitle("QA preflight")
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setWindowFlags(box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        box.activateWindow()
        box.raise_()
        return box.exec() == int(QMessageBox.StandardButton.Yes)

    def show_qa_result_dialog(self, title: str, result: QAResult) -> None:
        """Show a compact final status dialog for Stage 1 QA runs."""
        app = self._app
        status_text = "Completed successfully." if result.success else "Analysis failed."
        warning_text = ""
        if result.warnings:
            warning_text = "\nWarnings:\n- " + "\n- ".join(result.warnings[:5])
        error_text = ""
        if result.errors:
            error_text = "\nErrors:\n- " + "\n- ".join(result.errors[:5])
        pdf_text = f"\nPDF: {result.pdf_report_path}" if result.pdf_report_path else "\nPDF: not generated"
        profile = result.pylinac_analysis_profile or {}
        vanilla_note = ""
        if profile:
            vanilla_note = (
                "\nVanilla pylinac (stock classes): "
                + ("yes" if profile.get("vanilla_pylinac") else "no")
            )
        nonvanilla = ""
        if not profile.get("vanilla_equivalent", True):
            nonvanilla = (
                "\nNon-vanilla pylinac path: see JSON field pylinac_analysis_profile."
            )
        summary = (
            f"{status_text}\n"
            f"Study UID: {result.study_uid or '(folder run)'}\n"
            f"Series UID: {result.series_uid or '(folder run)'}\n"
            f"Input images: {result.num_images}\n"
            f"Pylinac: {result.pylinac_version or 'unknown'}"
            f"{vanilla_note}"
            f"{pdf_text}"
            f"{nonvanilla}"
            f"{warning_text}"
            f"{error_text}"
        )
        box = QMessageBox(app.main_window)
        box.setWindowTitle(title)
        box.setText(summary)
        box.setIcon(QMessageBox.Icon.Information if result.success else QMessageBox.Icon.Warning)
        box.setWindowFlags(box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        box.activateWindow()
        box.raise_()
        box.exec()

    def offer_open_single_run_pdf(self, result: QAResult) -> None:
        """
        After a successful single CT/MRI pylinac run, ask whether to open the PDF.

        Compare mode exposes **Open PDF** on the results window; single-run
        flow uses this modal prompt so behavior is consistent when a PDF path
        was chosen before analysis.
        """
        if not result.success:
            return
        path = (result.pdf_report_path or "").strip()
        if not path:
            return
        app = self._app
        box = QMessageBox(app.main_window)
        box.setWindowTitle("Open PDF report")
        box.setText("Open the pylinac PDF report now?")
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        box.setWindowFlags(box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        box.activateWindow()
        box.raise_()
        if box.exec() == int(QMessageBox.StandardButton.Yes):
            self.open_path_in_system_viewer(path)

    def export_qa_json(
        self,
        result: QAResult,
        default_stem: str,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Offer JSON export for a finished Stage 1 QA run."""
        app = self._app
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        json_path = app._prompt_save_path(
            "Save QA Results JSON",
            f"{default_stem}-{timestamp}.json",
            "JSON Files (*.json)",
            remember_pylinac_output_dir=True,
        )
        if not json_path:
            return

        profile = result.pylinac_analysis_profile or {}
        vanilla_run = bool(profile.get("vanilla_pylinac", False))

        payload: Dict[str, Any] = {
            "schema_version": "1.1",
            "run": {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "app_version": APP_VERSION,
                "pylinac_version": result.pylinac_version or "",
                "analysis_type": result.analysis_type,
                "status": "success" if result.success else "failed",
                "vanilla_pylinac": vanilla_run,
            },
            "series": {
                "study_uid": result.study_uid,
                "series_uid": result.series_uid,
                "modality": result.modality,
                "num_images": result.num_images,
            },
            "inputs": inputs or {},
            "pylinac_analysis_profile": result.pylinac_analysis_profile or {},
            "metrics": result.metrics,
            "warnings": result.warnings,
            "errors": result.errors,
            "artifacts": {"pdf_report_path": result.pdf_report_path or ""},
            "raw_pylinac": result.raw_pylinac,
        }
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        app.main_window.update_status(f"Saved QA JSON: {json_path}")

    def offer_extent_retry(
        self,
        request: QARequest,
        json_inputs: Optional[Dict[str, Any]],
        *,
        progress_title: str,
        progress_label: str,
        result_dialog_title: str,
        json_default_stem: str,
    ) -> None:
        """After a strict scan-extent failure, offer a relaxed retry (one tier)."""
        app = self._app
        mb = QMessageBox(app.main_window)
        mb.setWindowTitle("Scan extent")
        mb.setText(
            "Pylinac reported that the DICOM stack does not fully cover the "
            "phantom module positions (strict z-extent check). This sometimes "
            "happens when tags round slightly short of the true range.\n\n"
            "Retry with a small tolerance? This is non-vanilla and is recorded "
            "in the JSON export."
        )
        b_retry = mb.addButton(
            "Retry with 1.0 mm tolerance", QMessageBox.ButtonRole.ActionRole
        )
        b_choose = mb.addButton(
            "Choose tolerance…", QMessageBox.ButtonRole.ActionRole
        )
        mb.addButton(QMessageBox.StandardButton.Close)
        mb.setIcon(QMessageBox.Icon.Question)
        mb.setWindowFlags(mb.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        mb.activateWindow()
        mb.raise_()
        mb.exec()
        clicked = mb.clickedButton()
        tol: Optional[float] = None
        if clicked == b_retry:
            tol = 1.0
        elif clicked == b_choose:
            val, ok = QInputDialog.getDouble(
                app.main_window,
                "Scan extent tolerance",
                "Tolerance (mm):",
                1.0,
                0.5,
                2.0,
                2,
            )
            if ok:
                tol = float(val)
        if tol is None:
            return
        new_req = replace(
            request,
            scan_extent_tolerance_mm=tol,
            vanilla_pylinac=False,
            qa_attempt=request.qa_attempt + 1,
            parent_attempt_outcome="failed_strict_extent",
        )
        merged: Dict[str, Any] = dict(json_inputs or {})
        merged["scan_extent_tolerance_mm"] = tol
        merged["vanilla_pylinac"] = False
        merged["qa_attempt"] = new_req.qa_attempt
        merged["parent_attempt_outcome"] = new_req.parent_attempt_outcome
        self.start_qa_worker(
            new_req,
            progress_title=progress_title,
            progress_label=progress_label,
            result_dialog_title=result_dialog_title,
            json_default_stem=json_default_stem,
            json_inputs=merged,
            allow_extent_retry=False,
        )

    def start_qa_worker(
        self,
        request: QARequest,
        *,
        progress_title: str,
        progress_label: str,
        result_dialog_title: str,
        json_default_stem: str,
        json_inputs: Optional[Dict[str, Any]] = None,
        allow_extent_retry: bool = True,
    ) -> None:
        """Show progress, run QA in a background thread, then summary + JSON export."""
        app = self._app
        progress = QProgressDialog(progress_label, "Cancel", 0, 0, app.main_window)
        progress.setWindowTitle(progress_title)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowFlags(progress.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        progress.show()
        progress.activateWindow()
        progress.raise_()

        state = {"cancelled": False}

        def on_cancel() -> None:
            state["cancelled"] = True
            app.main_window.update_status("QA analysis cancelled (best-effort).")
            progress.close()

        progress.canceled.connect(on_cancel)

        app._qa_worker = QAAnalysisWorker(request)

        def on_result(result: QAResult) -> None:
            if state["cancelled"]:
                app.main_window.update_status("Ignored late QA result after cancellation.")
                return
            progress.close()
            self.show_qa_result_dialog(result_dialog_title, result)
            self.offer_open_single_run_pdf(result)
            self.export_qa_json(result, json_default_stem, json_inputs)
            if (
                allow_extent_retry
                and not result.success
                and is_physical_scan_extent_failure(result.errors)
                and float(request.scan_extent_tolerance_mm or 0) <= 0.0
                and not bool(getattr(request, "vanilla_pylinac", False))
                and request.qa_attempt < 2
            ):
                self.offer_extent_retry(
                    request,
                    json_inputs,
                    progress_title=progress_title,
                    progress_label=progress_label,
                    result_dialog_title=result_dialog_title,
                    json_default_stem=json_default_stem,
                )

        app._qa_worker.result_ready.connect(on_result)
        app._qa_worker.finished.connect(progress.close)
        app._qa_worker.start()

    def open_acr_ct_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR CT (pylinac) analysis flow."""
        app = self._app
        study_uid, series_uid, modality, ordered_paths, datasets = (
            app._resolve_focused_series_ordered_paths()
        )

        use_focused = bool(ordered_paths)
        if use_focused:
            choice = QMessageBox(app.main_window)
            choice.setWindowTitle("ACR CT Analysis Source")
            choice.setText("Use the focused series or choose a folder?")
            choice.addButton("Use Focused Series", QMessageBox.ButtonRole.AcceptRole)
            choice.addButton("Choose Folder", QMessageBox.ButtonRole.ActionRole)
            choice.addButton(QMessageBox.StandardButton.Cancel)
            choice.setWindowFlags(choice.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            choice.activateWindow()
            choice.raise_()
            choice.exec()
            clicked = choice.clickedButton()
            if clicked is None or clicked == choice.button(QMessageBox.StandardButton.Cancel):
                return
            if clicked.text() == "Choose Folder":
                use_focused = False
            elif clicked.text() == "Use Focused Series":
                use_focused = True
            else:
                return

        folder_path = None
        if not use_focused:
            folder_path = app.file_dialog.open_folder(app.main_window)
            if not folder_path:
                return
            study_uid = ""
            series_uid = ""
            modality = modality or "CT"
            ordered_paths = []
            datasets = []

        if use_focused and not ordered_paths:
            QMessageBox.warning(
                app.main_window,
                "ACR CT Analysis",
                "No DICOM file paths could be resolved for the focused series.",
            )
            return

        preflight = self.build_preflight_warnings(
            "CT", use_focused, folder_path, datasets, modality or "CT"
        )
        if not self.user_confirms_preflight(preflight):
            return

        vanilla_def = app.config_manager.get_acr_qa_vanilla_pylinac()
        ct_opts = prompt_acr_ct_options(
            app.main_window, vanilla_pylinac_default=vanilla_def
        )
        if ct_opts is None:
            return
        ct_scan_tol, ct_origin_slice, ct_vanilla = ct_opts
        app.config_manager.set_acr_qa_vanilla_pylinac(ct_vanilla)

        pdf_path = app._prompt_save_path(
            "Optional PDF Report Output",
            f"acr-ct-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf",
            "PDF Files (*.pdf)",
            remember_pylinac_output_dir=True,
        )
        if not pdf_path:
            pdf_path = None

        modality_eff = modality or "CT"
        request = QARequest(
            analysis_type="acr_ct",
            dicom_paths=ordered_paths,
            folder_path=folder_path,
            origin_slice=ct_origin_slice,
            output_pdf_path=pdf_path,
            study_uid=study_uid,
            series_uid=series_uid,
            modality=modality_eff,
            preflight_warnings=preflight,
            scan_extent_tolerance_mm=float(ct_scan_tol),
            vanilla_pylinac=ct_vanilla,
        )
        json_inputs: Dict[str, Any] = {
            "origin_slice_override": ct_origin_slice,
            "scan_extent_tolerance_mm": float(ct_scan_tol),
            "vanilla_pylinac": ct_vanilla,
            "qa_attempt": request.qa_attempt,
            "options": {},
            "preflight_warnings": preflight,
        }
        self.start_qa_worker(
            request,
            progress_title="ACR CT Phantom Analysis",
            progress_label="Running ACR CT analysis...",
            result_dialog_title="ACR CT Phantom Analysis",
            json_default_stem="qa-acr-ct",
            json_inputs=json_inputs,
        )

    def open_acr_mri_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR MRI Large (pylinac) analysis flow."""
        app = self._app
        study_uid, series_uid, modality, ordered_paths, datasets = (
            app._resolve_focused_series_ordered_paths()
        )

        use_focused = bool(ordered_paths)
        if use_focused:
            choice = QMessageBox(app.main_window)
            choice.setWindowTitle("ACR MRI Analysis Source")
            choice.setText("Use the focused series or choose a folder?")
            choice.addButton("Use Focused Series", QMessageBox.ButtonRole.AcceptRole)
            choice.addButton("Choose Folder", QMessageBox.ButtonRole.ActionRole)
            choice.addButton(QMessageBox.StandardButton.Cancel)
            choice.setWindowFlags(choice.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            choice.activateWindow()
            choice.raise_()
            choice.exec()
            clicked = choice.clickedButton()
            if clicked is None or clicked == choice.button(QMessageBox.StandardButton.Cancel):
                return
            if clicked.text() == "Choose Folder":
                use_focused = False
            elif clicked.text() == "Use Focused Series":
                use_focused = True
            else:
                return

        folder_path = None
        if not use_focused:
            folder_path = app.file_dialog.open_folder(app.main_window)
            if not folder_path:
                return
            study_uid = ""
            series_uid = ""
            modality = modality or "MR"
            ordered_paths = []
            datasets = []

        if use_focused and not ordered_paths:
            QMessageBox.warning(
                app.main_window,
                "ACR MRI Analysis",
                "No DICOM file paths could be resolved for the focused series.",
            )
            return

        lc_method_default = app.config_manager.get_acr_mri_low_contrast_method()
        lc_vis_default = (
            app.config_manager.get_acr_mri_low_contrast_visibility_threshold()
        )
        lc_sanity_default = (
            app.config_manager.get_acr_mri_low_contrast_visibility_sanity_multiplier()
        )
        vanilla_def = app.config_manager.get_acr_qa_vanilla_pylinac()
        mri_opts = prompt_acr_mri_options(
            app.main_window,
            low_contrast_method=lc_method_default,
            low_contrast_visibility_threshold=lc_vis_default,
            low_contrast_visibility_sanity_multiplier=lc_sanity_default,
            vanilla_pylinac_default=vanilla_def,
        )
        if mri_opts is None:
            return
        (
            echo_number,
            check_uid,
            origin_slice,
            mri_scan_tol,
            lc_method,
            lc_vis,
            lc_sanity,
            compare_request,
            mri_vanilla,
        ) = mri_opts
        app.config_manager.set_acr_qa_vanilla_pylinac(mri_vanilla)
        app.config_manager.set_acr_mri_low_contrast_method(lc_method)
        app.config_manager.set_acr_mri_low_contrast_visibility_threshold(lc_vis)
        app.config_manager.set_acr_mri_low_contrast_visibility_sanity_multiplier(
            lc_sanity
        )

        preflight = self.build_preflight_warnings(
            "MR", use_focused, folder_path, datasets, modality or "MR"
        )
        if not self.user_confirms_preflight(preflight):
            return

        pdf_path = app._prompt_save_path(
            "Optional PDF Report Output",
            f"acr-mri-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf",
            "PDF Files (*.pdf)",
            remember_pylinac_output_dir=True,
        )
        if not pdf_path:
            pdf_path = None

        modality_eff = modality or "MR"

        request = QARequest(
            analysis_type="acr_mri_large",
            dicom_paths=ordered_paths,
            folder_path=folder_path,
            origin_slice=origin_slice,
            output_pdf_path=pdf_path,
            study_uid=study_uid,
            series_uid=series_uid,
            modality=modality_eff,
            echo_number=echo_number,
            check_uid=check_uid,
            preflight_warnings=preflight,
            scan_extent_tolerance_mm=float(mri_scan_tol),
            vanilla_pylinac=mri_vanilla,
            low_contrast_method=lc_method,
            low_contrast_visibility_threshold=float(lc_vis),
            low_contrast_visibility_sanity_multiplier=float(lc_sanity),
        )
        json_inputs = {
            "origin_slice_override": origin_slice,
            "scan_extent_tolerance_mm": float(mri_scan_tol),
            "vanilla_pylinac": mri_vanilla,
            "low_contrast_method": lc_method,
            "low_contrast_visibility_threshold": float(lc_vis),
            "low_contrast_visibility_sanity_multiplier": float(lc_sanity),
            "qa_attempt": request.qa_attempt,
            "options": {
                "echo_number": echo_number,
                "check_uid": check_uid,
            },
            "preflight_warnings": preflight,
        }

        if compare_request is not None:
            self.start_mri_batch_worker(
                request,
                compare_request,
                json_inputs=json_inputs,
            )
        else:
            self.start_qa_worker(
                request,
                progress_title="ACR MRI Phantom Analysis",
                progress_label="Running ACR MRI Large analysis...",
                result_dialog_title="ACR MRI Phantom Analysis",
                json_default_stem="qa-acr-mri",
                json_inputs=json_inputs,
            )

    def start_mri_batch_worker(
        self,
        base_request: QARequest,
        compare_request: MRICompareRequest,
        *,
        json_inputs: Optional[Dict[str, Any]],
    ) -> None:
        """
        Launch a QABatchWorker for compare-mode MRI analysis.

        Shows a progress dialog, then on completion calls the compare result
        dialog and JSON export.

        Args:
            base_request: Base QARequest carrying shared options (DICOM paths,
                echo, scan-extent, etc.).  The first run's LC config overrides
                the LC fields on this request inside the batch runner.
            compare_request: MRICompareRequest with 1-3 LcRunConfig rows.
            json_inputs: Dict of top-level inputs to embed in the compare JSON.
        """
        app = self._app
        n_runs = len(compare_request.run_configs)
        progress = QProgressDialog(
            f"Running ACR MRI Large compare analysis ({n_runs} run(s))...",
            "Cancel",
            0,
            0,
            app.main_window,
        )
        progress.setWindowTitle("ACR MRI Phantom Analysis — Compare Mode")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowFlags(progress.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        progress.show()
        progress.activateWindow()
        progress.raise_()

        state = {"cancelled": False}

        def on_cancel() -> None:
            state["cancelled"] = True
            app.main_window.update_status("QA batch analysis cancelled (best-effort).")
            progress.close()

        progress.canceled.connect(on_cancel)

        app._qa_batch_worker = QABatchWorker(
            base_request, compare_request, app_version=APP_VERSION
        )

        def on_batch_result(batch: MRIBatchResult) -> None:
            if state["cancelled"]:
                app.main_window.update_status(
                    "Ignored late QA batch result after cancellation."
                )
                return
            progress.close()
            self.show_mri_compare_result_dialog(batch, json_inputs=json_inputs)

        app._qa_batch_worker.batch_result_ready.connect(on_batch_result)
        app._qa_batch_worker.finished.connect(progress.close)
        app._qa_batch_worker.start()

    def note_mri_compare_dialog_closed(self, *_args: Any) -> None:
        """Clear compare-results dialog reference after WA_DeleteOnClose."""
        self._app._mri_compare_result_dialog = None

    def open_path_in_system_viewer(self, path: str) -> None:
        """
        Open a file path with the OS default application (PDF viewer, etc.).

        Uses ``QDesktopServices.openUrl`` on the next event-loop tick (via
        ``QTimer.singleShot``) so the UI stays responsive; falls back to
        ``os.startfile`` / ``xdg-open`` if Qt cannot launch the handler.
        """
        app = self._app
        resolved = os.path.normpath(os.path.abspath(path))
        if not os.path.isfile(resolved):
            QMessageBox.warning(
                app.main_window,
                "Open file",
                f"File not found:\n{resolved}",
            )
            return

        def deferred_open() -> None:
            """Run after the event loop idles — avoids Qt/UI re-entrancy freezes with ShellExecute."""
            if QDesktopServices.openUrl(QUrl.fromLocalFile(resolved)):
                return
            try:
                try:
                    os.startfile(resolved)  # type: ignore[attr-defined]
                except AttributeError:
                    import subprocess

                    subprocess.Popen(["xdg-open", resolved])  # noqa: S603
            except Exception as exc:
                QMessageBox.warning(
                    app.main_window,
                    "Open file",
                    f"Could not open file:\n{exc}",
                )

        QTimer.singleShot(0, deferred_open)

    def show_mri_compare_result_dialog(
        self,
        batch: MRIBatchResult,
        *,
        json_inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Show a non-modal compare summary matching plan section 1.6.

        Presents a table (metrics × runs) including low-contrast score,
        pylinac ``vanilla_equivalent`` (from ``pylinac_analysis_profile``),
        LC parameters, and warning summaries; a details area lists full
        warnings/errors. User saves JSON via **Save comparison JSON**;
        **Open PDF** appears when a combined PDF path exists.

        Args:
            batch: MRIBatchResult from ``QABatchWorker``.
            json_inputs: Top-level inputs dict for optional JSON export.
        """
        app = self._app
        if not batch.run_configs:
            return

        if app._mri_compare_result_dialog is not None:
            app._mri_compare_result_dialog.close()
            app._mri_compare_result_dialog = None

        dialog = create_mri_compare_result_dialog(
            app.main_window,
            batch,
            on_save_json_clicked=lambda: self.export_mri_compare_json(
                batch, json_inputs
            ),
            on_open_pdf=self.open_path_in_system_viewer,
            on_destroyed=self.note_mri_compare_dialog_closed,
        )
        app._mri_compare_result_dialog = dialog
        dialog.activateWindow()
        dialog.raise_()
        dialog.show()

    def export_mri_compare_json(
        self,
        batch: MRIBatchResult,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Offer JSON export for a finished compare-mode MRI batch.

        Produces schema_version '1.2' with compare_mode=true and a 'runs'
        array.  Single-run exports keep schema_version '1.1'.

        Args:
            batch: MRIBatchResult from QABatchWorker.
            inputs: Top-level inputs dict to embed (from json_inputs).
        """
        app = self._app
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        json_path = app._prompt_save_path(
            "Save QA Compare Results JSON",
            f"qa-acr-mri-compare-{timestamp}.json",
            "JSON Files (*.json)",
            remember_pylinac_output_dir=True,
        )
        if not json_path:
            return

        payload = build_mri_compare_json_document(
            batch, inputs, app_version=APP_VERSION
        )
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        app.main_window.update_status(f"Saved QA compare JSON: {json_path}")
