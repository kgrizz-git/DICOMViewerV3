"""
Targeted regression tests for folder-load filtering and file reveal helpers.

These tests avoid launching the application or system file managers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.dicom_loader import should_skip_path_for_dicom
from utils.file_explorer import reveal_file_in_explorer


def test_folder_loading_skips_known_junk_basenames_without_extension() -> None:
    for name in ("VERSION", "DICOMDIR", "LOCKFILE"):
        assert should_skip_path_for_dicom(Path(r"C:\study") / name)
        assert should_skip_path_for_dicom(Path(r"C:\study") / name.lower())


def test_windows_reveal_uses_single_explorer_command_with_quoted_select_path() -> None:
    calls: list[str] = []

    def fake_run(command: str, check: bool, **_kwargs) -> None:
        calls.append(command)

    with (
        patch("utils.file_explorer.platform.system", return_value="Windows"),
        patch("utils.file_explorer.os.path.abspath", return_value=r"C:\My Study\image 1.dcm"),
        patch("utils.file_explorer.subprocess.run", side_effect=fake_run),
    ):
        assert reveal_file_in_explorer(r"C:\My Study\image 1.dcm")

    assert calls == [r'explorer /select,"C:\My Study\image 1.dcm"']
