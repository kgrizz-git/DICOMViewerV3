"""
LUT Config Mixin

Reads and writes ``custom_luts.json`` next to the main config file, and
persists the pane LUT label toggle and the per-modality default LUTs in the
main config. The file
holds user-made LUTs only. This mixin moves the raw JSON document; turning it
into ``LookUpTable`` objects is ``core.lut_persistence``'s job, so ``utils``
never imports ``core``.

Mixin contract:
    Expects ``self.config_dir`` (``Path``), ``self.config`` (dict), and
    ``self.save_config()`` from the concrete ConfigManager.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

from utils.privacy.safe_storage import atomic_write_private_text

CUSTOM_LUTS_FILENAME = "custom_luts.json"
_SOURCE_ROOT = Path(__file__).resolve().parents[3]
_logger = logging.getLogger(__name__)


class LutConfigMixin:
    """Load and save the custom LUT document."""

    def get_show_lut_label(self) -> bool:
        """Whether panes name a non-Linear LUT in a corner label. On by default."""
        config = cast(dict[str, Any], getattr(self, "config"))
        return bool(config.get("show_lut_pane_label", True))

    def set_show_lut_label(self, enabled: bool) -> None:
        """Persist the pane LUT label toggle."""
        config = cast(dict[str, Any], getattr(self, "config"))
        config["show_lut_pane_label"] = bool(enabled)
        save = getattr(self, "save_config", None)
        if callable(save):
            save()

    def get_lut_defaults(self) -> dict[str, Any]:
        """Default LUT entries keyed by DICOM Modality (see ``core.lut_defaults``)."""
        config = cast(dict[str, Any], getattr(self, "config"))
        found = config.get("lut_defaults_by_modality", {})
        return dict(found) if isinstance(found, dict) else {}

    def set_lut_default(self, modality: str, entry: dict[str, Any] | None) -> None:
        """Set or clear (``None``) the default for ``modality`` and save."""
        config = cast(dict[str, Any], getattr(self, "config"))
        defaults = self.get_lut_defaults()
        if entry is None:
            defaults.pop(modality, None)
        else:
            defaults[modality] = entry
        config["lut_defaults_by_modality"] = defaults
        save = getattr(self, "save_config", None)
        if callable(save):
            save()

    def custom_luts_path(self) -> Path:
        """Location of ``custom_luts.json``."""
        return cast(Path, getattr(self, "config_dir")) / CUSTOM_LUTS_FILENAME

    def load_custom_luts_document(self) -> Any:
        """The decoded document, or ``None`` when missing or unreadable."""
        path = self.custom_luts_path()
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError) as error:
            _logger.warning(
                "Custom LUT file could not be read",
                extra={"operation": "lut.load", "error_class": type(error).__name__},
            )
            return None

    def save_custom_luts_document(self, document: dict[str, Any]) -> bool:
        """Atomically write the document. Returns False when the write fails."""
        try:
            atomic_write_private_text(
                self.custom_luts_path(),
                json.dumps(document, indent=2, ensure_ascii=False),
                source_root=_SOURCE_ROOT,
            )
            return True
        except (OSError, ValueError) as error:
            _logger.error(  # NOSONAR (python:S8572): raw logging.exception is prohibited by the PHI/PII sink gate.
                "Custom LUT file could not be saved",
                extra={"operation": "lut.save", "error_class": type(error).__name__},
            )
            return False
