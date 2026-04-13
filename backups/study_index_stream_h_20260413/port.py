"""
Abstract port for local (or future PACS-backed) study discovery.

MVP: implemented by :class:`LocalStudyIndexService` using SQLCipher.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StudyIndexPort(Protocol):
    """Minimal query surface for UI and loaders."""

    def search(
        self,
        *,
        patient_name_contains: str = "",
        patient_id_contains: str = "",
        modality: str = "",
        accession_contains: str = "",
        study_description_contains: str = "",
        study_date_from: str = "",
        study_date_to: str = "",
        limit: int = 500,
        privacy_mode: bool = False,
    ) -> list[dict[str, Any]]:
        """Return display-ready rows (mask patient fields when ``privacy_mode``)."""
        ...
