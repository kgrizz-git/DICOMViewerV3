"""
Tests for scripts/check_no_phi_artifacts.py.

This is a security gate, so the tests that matter are the ones proving it *fails*
on the things it exists to catch -- including a verbatim reconstruction of the real
config capture that was committed in May 2026 and had to be scrubbed from history.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "check_no_phi_artifacts.py"
)
_spec = importlib.util.spec_from_file_location("check_no_phi_artifacts", _SCRIPT)
assert _spec and _spec.loader
phi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(phi)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _stage(repo: Path, relpath: str, content: str) -> None:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-f", relpath], cwd=repo, check=True)


def _run(repo: Path) -> int:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--staged", "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
    ).returncode


def _approve_synthetic_text_rule(repo: Path, path: str, rule: str) -> None:
    manifest = repo / phi.APPROVED_TEXT_EXCEPTIONS_MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "files": {
                    path: {"sha256": phi._sha256(repo / path), "allowed_rules": [rule]}
                }
            }
        ),
        encoding="utf-8",
    )


# --- the actual historical leak ---------------------------------------------

# Shaped like the real dicom_viewer_config_test_signals.json that was committed, but
# with wholly invented values. Never paste a real capture into a fixture: the point of
# this gate is that such strings do not belong in the repository, history included.
REAL_CAPTURE = json.dumps(
    {
        "last_path": "Y:/Some Folder/Sample DICOM/MG/example_tomo.dcm",
        "recent_files": [
            "\\\\mac\\Home\\Downloads\\DOE_JANE____XX0000000_0000000000",
            "C:\\Users\\someone\\Desktop\\Example-Anon",
        ],
        "theme": "dark",
    },
    indent=4,
)


def test_blocks_the_real_pytest_tmp_config_capture(repo):
    _stage(
        repo,
        ".pytest-tmp-nav-20260527/t/dicom_viewer_config_test_signals.json",
        REAL_CAPTURE,
    )
    assert _run(repo) == 1


def test_blocks_it_on_path_rule_alone_even_if_contents_are_sanitized(repo):
    _stage(repo, ".pytest-tmp-x/t/dicom_viewer_config_test_signals.json", "{}")
    assert _run(repo) == 1


def test_blocks_it_on_content_rule_alone_from_an_innocuous_path(repo):
    """A config capture renamed out of the denylisted path is still caught."""
    _stage(repo, "notes/session.json", REAL_CAPTURE)
    assert _run(repo) == 1


# --- path rule ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".pytest-tmp-nav-20260527/t/x.json",
        "pyright-report.txt",
        "backups/old_export_manager.py",
        "src/gui/.DS_Store",
        "some/dir/dicom_viewer_config.json",
        "diagnostics/session.trace",
        "diagnostics/session.err",
        "diagnostics/session.out",
        "diagnostics/session.pkl",
        "diagnostics/session.cache",
    ],
)
def test_forbidden_paths_are_blocked(repo, path):
    _stage(repo, path, "harmless")
    assert _run(repo) == 1


# --- content rule ------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        '{"recent_files": []}',
        "error at c:\\Users\\someone\\Desktop\\thing.py",
        "trace from /Users/someone/Code/app.py",
        '{"PatientName": "DOE^JANE"}',
        '{"PatientID": "PID-001"}',
        "PACS endpoint: dicom://internal.local",
        "endpoint=192.168.1.20",
        "endpoint=fd00::20",
    ],
)
def test_phi_indicators_in_data_files_are_blocked(repo, content):
    _stage(repo, "dev-docs/report.txt", content)
    assert _run(repo) == 1


@pytest.mark.parametrize(
    "content",
    [
        '{"PatientName": ""}',  # empty tag: a schema, not a capture
        '{"theme": "dark", "font_size": 10}',  # ordinary settings
        "relative/path/to/file.py:12: error",  # no absolute user path
        "/home/runner/work/repo/file.py",  # CI runner path, not a person
        "test endpoint=192.0.2.20",  # RFC 5737 documentation range
        "docker endpoint=host.docker.internal",  # standard non-identifying bridge hostname
    ],
)
def test_clean_data_files_pass(repo, content):
    _stage(repo, "dev-docs/report.txt", content)
    assert _run(repo) == 0


def test_source_code_is_not_content_scanned(repo):
    """Python source is covered by git_hook_privacy_checks.py; do not double-flag."""
    _stage(repo, "src/app.py", 'HOME = "/Users/someone/Code"  # noqa\n')
    assert _run(repo) == 0


def test_synthetic_text_fixture_requires_hash_bound_exception(repo):
    path = "tests/fixtures/sample.json"
    _stage(repo, path, '{"PatientName": "SYNTHETIC^TEST"}')
    assert _run(repo) == 1

    _approve_synthetic_text_rule(repo, path, "populated DICOM patient tag")
    assert _run(repo) == 0

    _stage(repo, path, '{"PatientName": "SYNTHETIC^CHANGED"}')
    assert _run(repo) == 1


def test_blocks_unapproved_extensionless_file(repo):
    _stage(repo, "clinical-export", "opaque export")
    assert _run(repo) == 1


def test_blocks_unapproved_image_file(repo):
    _stage(repo, "resources/new-image.png", "not a reviewed image")
    assert _run(repo) == 1


@pytest.mark.parametrize(
    "path",
    [
        "resources/new-image.svg",
        "resources/new-image.ico",
        "resources/new-image.icns",
    ],
)
def test_blocks_unapproved_vector_and_icon_image_files(repo, path):
    _stage(repo, path, "not a reviewed image")
    assert _run(repo) == 1


def test_blocks_an_added_image_in_an_approved_image_tree(repo):
    _stage(repo, "resources/icons/approved.svg", "<svg />")
    digest = phi._image_tree_sha256(repo, "resources/icons")
    manifest = repo / phi.APPROVED_MEDIA_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"image_trees": {"resources/icons": digest}}), encoding="utf-8"
    )

    assert _run(repo) == 0

    _stage(repo, "resources/icons/unreviewed.svg", "<svg />")
    assert _run(repo) == 1


def test_recursively_blocks_dicom_identifier(repo):
    import pydicom
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.sequence import Sequence

    path = repo / "data" / "study.dcm"
    path.parent.mkdir(parents=True)
    dataset = Dataset()
    dataset.file_meta = FileMetaDataset()
    dataset.is_little_endian = True
    dataset.is_implicit_VR = True
    nested = Dataset()
    nested.PatientName = "Doe^Jane"
    dataset.RequestAttributesSequence = Sequence([nested])
    pydicom.dcmwrite(path, dataset)
    subprocess.run(
        ["git", "add", "-f", str(path.relative_to(repo))], cwd=repo, check=True
    )

    assert _run(repo) == 1


def test_blocks_private_dicom_tag(repo):
    import pydicom
    from pydicom.dataset import Dataset, FileMetaDataset

    path = repo / "data" / "private.dcm"
    path.parent.mkdir(parents=True)
    dataset = Dataset()
    dataset.file_meta = FileMetaDataset()
    dataset.is_little_endian = True
    dataset.is_implicit_VR = True
    dataset.add_new((0x0011, 0x1001), "LO", "private workstation value")
    pydicom.dcmwrite(path, dataset)
    subprocess.run(
        ["git", "add", "-f", str(path.relative_to(repo))], cwd=repo, check=True
    )

    assert _run(repo) == 1


def test_recognizes_dicom_preamble_without_dicom_extension(repo):
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import (
        ExplicitVRLittleEndian,
        SecondaryCaptureImageStorage,
        generate_uid,
    )

    path = repo / "data" / "concealed.bin"
    path.parent.mkdir(parents=True)
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    pydicom.dcmwrite(path, dataset, write_like_original=False)
    subprocess.run(
        ["git", "add", "-f", str(path.relative_to(repo))], cwd=repo, check=True
    )

    assert phi._has_dicom_preamble(path)
    assert _run(repo) == 1


def test_blocks_notebook_outputs(repo):
    path = "analysis.ipynb"
    _stage(
        repo, path, json.dumps({"cells": [{"outputs": [{"text": "sensitive output"}]}]})
    )

    assert phi._check_notebook(path, repo)
    assert _run(repo) == 1


def test_empty_repo_passes(repo):
    assert _run(repo) == 0


# --- the live repository -----------------------------------------------------


def test_this_repository_is_clean():
    """The real tree must stay clean, or the CI gate is already failing."""
    root = Path(__file__).resolve().parent.parent
    assert phi.check_paths(phi.tracked_files(root)) == []
    assert phi.check_contents(phi.tracked_files(root), root) == []
