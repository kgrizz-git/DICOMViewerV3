"""Loaded-series listing for the MPR dialog (pure data gathering, no Qt)."""

from __future__ import annotations

from typing import Any


def collect_loaded_series(app: Any) -> dict[str, dict[str, Any]]:
    """
    Build the ``loaded_series`` dict required by MprDialog.

    Returns a mapping of ``series_key → info_dict`` for all currently
    loaded series across all studies.

    Returns:
        Dict with keys: "description", "modality", "n_slices",
        "study_uid", "datasets".
    """
    result: dict[str, dict[str, Any]] = {}
    try:
        current_studies = app.current_studies
    except AttributeError:
        return result

    for study_uid, series_dict in current_studies.items():
        for series_key, datasets in series_dict.items():
            if not datasets:
                continue
            ds0 = datasets[0]
            description = getattr(ds0, "SeriesDescription", "") or ""
            modality = getattr(ds0, "Modality", "") or ""
            result[series_key] = {
                "description": description,
                "modality": modality,
                "n_slices": len(datasets),
                "study_uid": study_uid,
                "datasets": datasets,
            }
    return result


__all__ = ["collect_loaded_series"]
