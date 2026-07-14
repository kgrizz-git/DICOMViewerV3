"""
DICOM Tag Export — Qt-free orchestration.

Pure (no Qt) orchestration logic extracted from
``gui/dialogs/tag_export_dialog.py`` (refactor plan
``REFACTOR_TOP3_EXTRACTIONS_PLAN`` Stream A). It owns:

- variation analysis (delegates to :mod:`core.tag_export_analysis_service`),
- default filename generation,
- save-path format resolution (filter/extension → writer + normalized path),
- writer dispatch (CSV/TXT/XLSX) via :mod:`core.tag_export_writer`.

The dialog keeps all Qt concerns: widgets, the variation-review dialog, the
file/message dialogs, and config-manager path handling. Keeping this module
Qt-free makes the export selection model and format/writer routing unit-testable
without a Qt application (and keeps the ``core → gui`` boundary clean).

Inputs:
    - studies: {study_uid: {series_uid: [Dataset]}}
    - selected_series: {study_uid: {series_uid: [instance_indices]}}
    - selected_tags: list of tag strings
    - include_private / include_missing_rows: export options

Outputs:
    - variation analysis dict, default filename, resolved format + path,
      and the list of written file paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydicom.dataset import Dataset

from core.tag_export_analysis_service import analyze_tag_variations
from core.tag_export_writer import (
    generate_default_filename,
    write_csv_files,
    write_excel_file,
    write_txt_files,
)

# Format keys (also the file extensions, sans dot).
FORMAT_XLSX = "xlsx"
FORMAT_CSV = "csv"
FORMAT_TXT = "txt"


def resolve_export_format(file_path: str, selected_filter: str) -> tuple[str, str]:
    """Resolve the export format and normalized path from a save dialog result.

    Mirrors the prior dialog behavior: the selected filter name (or, failing
    that, the path's extension) selects the format; the path then gets the
    matching extension appended if it is missing. XLSX is the default.

    Args:
        file_path: Path returned by the save dialog (may lack an extension).
        selected_filter: The filter string the user chose (e.g. ``"CSV Files (*.csv)"``).

    Returns:
        ``(format_key, normalized_path)`` where ``format_key`` is one of
        :data:`FORMAT_CSV`, :data:`FORMAT_TXT`, :data:`FORMAT_XLSX`.
    """
    lowered = file_path.lower()
    if selected_filter.startswith("CSV") or lowered.endswith(".csv"):
        fmt = FORMAT_CSV
    elif selected_filter.startswith("Text") or lowered.endswith(".txt"):
        fmt = FORMAT_TXT
    else:
        fmt = FORMAT_XLSX

    ext = "." + fmt
    if not file_path.lower().endswith(ext):
        file_path += ext
    return fmt, file_path


@dataclass
class TagExportController:
    """Qt-free orchestration of a single DICOM tag-export run."""

    studies: dict[str, dict[str, list[Dataset]]]
    selected_series: dict[str, dict[str, list[int]]]
    selected_tags: list[str]
    include_private: bool
    include_missing_rows: bool = True
    # Forwarded to the writer. Default off keeps a scalar-oriented export free of
    # the historical scalar-only behavior; on lets a selected SQ tag resolve to
    # its single-cell summary value instead of the missing-tag fallback.
    include_sequences: bool = False

    def analyze_variations(self) -> dict[str, dict[str, list[str]]]:
        """Per-series varying/constant tag analysis for the current selection."""
        return analyze_tag_variations(
            self.studies,
            self.selected_series,
            self.selected_tags,
            self.include_private,
            include_sequences=self.include_sequences,
        )

    def default_filename(self) -> str:
        """Default ``.xlsx`` filename derived from the first selected dataset."""
        return generate_default_filename(self.studies, self.selected_series)

    def export(
        self,
        file_path: str,
        variation_analysis: dict[str, dict[str, list[str]]],
        format_key: str,
    ) -> list[Path]:
        """Write the export in *format_key*; return the created file path(s).

        XLSX writes a single workbook (returns ``[Path(file_path)]``); CSV and
        TXT may produce one file per study (the writer returns that list).

        Raises:
            ValueError: if *format_key* is not a known format.
        """
        if format_key == FORMAT_CSV:
            return write_csv_files(
                file_path,
                variation_analysis,
                self.studies,
                self.selected_series,
                self.selected_tags,
                self.include_private,
                include_missing_selected_tags=self.include_missing_rows,
                include_sequences=self.include_sequences,
            )
        if format_key == FORMAT_TXT:
            return write_txt_files(
                file_path,
                variation_analysis,
                self.studies,
                self.selected_series,
                self.selected_tags,
                self.include_private,
                include_missing_selected_tags=self.include_missing_rows,
                include_sequences=self.include_sequences,
            )
        if format_key == FORMAT_XLSX:
            write_excel_file(
                file_path,
                variation_analysis,
                self.studies,
                self.selected_series,
                self.selected_tags,
                self.include_private,
                include_missing_selected_tags=self.include_missing_rows,
                include_sequences=self.include_sequences,
            )
            return [Path(file_path)]
        raise ValueError(f"Unknown export format: {format_key!r}")
