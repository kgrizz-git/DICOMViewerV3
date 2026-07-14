"""
Background QThread for building the tag-export union across loaded datasets.

Reads datasets only (no disk cache). Cooperative cancellation via
:meth:`~PySide6.QtCore.QThread.requestInterruption` between instances.

Outputs:
    finished_ok(int generation, dict merged_tags)
    failed(int generation, str message)
"""

from __future__ import annotations

from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QThread, Signal

from core.dicom_parser import DICOMParser
from core.tag_export_catalog import supplement_export_tags_dict


class TagExportUnionWorker(QThread):
    """Compute union_tags equivalent off the GUI thread."""

    finished_ok = Signal(int, object)  # generation, merged dict
    failed = Signal(int, str)

    def __init__(
        self,
        generation: int,
        datasets: list[Dataset],
        include_private: bool,
        supplement_standard_tags: bool,
        include_sequences: bool = False,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._datasets = datasets
        self._include_private = include_private
        self._supplement = supplement_standard_tags
        self._include_sequences = include_sequences

    def run(self) -> None:
        try:
            merged: dict[str, Any] = {}
            for ds in self._datasets:
                if self.isInterruptionRequested():
                    return
                parser = DICOMParser(ds)
                part = parser.get_all_tags(
                    include_private=self._include_private,
                    supplement_standard_tags=False,
                    include_sequences=self._include_sequences,
                )
                for n, (tag_str, tag_data) in enumerate(part.items()):
                    if n % 4000 == 0 and self.isInterruptionRequested():
                        return
                    # Nested item/leaf rows (depth > 0) are kept — Phase 5 lets the
                    # picker offer them as individually selectable export columns.
                    # See core.tag_export_union.union_tags_across_datasets.
                    if tag_str not in merged:
                        merged[tag_str] = tag_data
            if self.isInterruptionRequested():
                return
            if self._supplement:
                supplement_export_tags_dict(merged)
            self.finished_ok.emit(self._generation, merged)
        except Exception as e:
            self.failed.emit(self._generation, str(e))
