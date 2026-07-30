"""Tests for the frozen GDCM asset inventory helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "report_gdcm_bundle_inventory.py"
_SPEC = importlib.util.spec_from_file_location("report_gdcm_bundle_inventory", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_build_inventory_uses_relative_paths_and_distinguishes_plugin_names(tmp_path: Path) -> None:
    gdcm = tmp_path / "Contents" / "Frameworks" / "libgdcmMSFF.3.2.dylib"
    gdcm.parent.mkdir(parents=True)
    gdcm.write_bytes(b"gdcm")
    gdcm_data = tmp_path / "Contents" / "Resources" / "_gdcm" / "Part3.xml"
    gdcm_data.parent.mkdir(parents=True)
    gdcm_data.write_bytes(b"<part3/>")
    pillow = tmp_path / "Contents" / "Frameworks" / "PIL" / "libjpeg.62.dylib"
    pillow.parent.mkdir(parents=True)
    pillow.write_bytes(b"pillow")
    old_plugin = tmp_path / "Contents" / "Resources" / "pylibjpeg_libjpeg" / "plugin.dylib"
    old_plugin.parent.mkdir(parents=True)
    old_plugin.write_bytes(b"old")

    inventory = _MODULE.build_inventory(tmp_path)

    assert inventory["gdcm_assets"] == [
        {
            "path": "Contents/Frameworks/libgdcmMSFF.3.2.dylib",
            "sha256": "ff5b0a73f432ff58559e545d46d7e2e7a9a7b79e6aa7af9951a03e5a08d24407",
        },
        {
            "path": "Contents/Resources/_gdcm/Part3.xml",
            "sha256": "fda6cd0ad1d2b07a030aa7316c5295c84c524470c60ef058c88c09c79570ddc8",
        },
    ]
    assert inventory["pylibjpeg_libjpeg_paths"] == [
        "Contents/Resources/pylibjpeg_libjpeg/plugin.dylib"
    ]
    assert inventory["other_libjpeg_paths_requiring_component_review"] == [
        "Contents/Frameworks/PIL/libjpeg.62.dylib"
    ]
