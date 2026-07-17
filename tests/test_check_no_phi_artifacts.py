"""
Tests for scripts/check_no_phi_artifacts.py.

This is a security gate, so the tests that matter are the ones proving it *fails*
on the things it exists to catch -- including a verbatim reconstruction of the real
config capture that was committed in May 2026 and had to be scrubbed from history.
"""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import zipfile
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
    (tmp_path / ".gitignore").write_text(
        "\n".join(sorted(phi.REQUIRED_GITIGNORE_RULES)) + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    return tmp_path


def _stage(repo: Path, relpath: str, content: str) -> None:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-f", relpath], cwd=repo, check=True)


def _stage_bytes(repo: Path, relpath: str, content: bytes) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
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


def _approve_reviewable_asset(repo: Path, path: str) -> None:
    manifest = repo / phi.APPROVED_MEDIA_MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"files": {path: phi._sha256(repo / path)}}), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "path",
    [
        "data/import.csv",
        "decoder-spike-artifacts/report.json",
        "logs/session.txt",
        "resources/screenshots-ignored/view.png",
        "sample-DICOM-gitignored/study.bin",
        "test-DICOM-data/study.bin",
        ".sonar-local/coverage.xml",
        "tmp/output.txt",
    ],
)
def test_blocks_force_added_files_in_protected_local_roots(repo: Path, path: str) -> None:
    _stage(repo, path, "synthetic")

    assert _run(repo) == 1


def test_allows_only_data_gitkeep_placeholder(repo: Path) -> None:
    _stage(repo, "data/.gitkeep", "")
    _approve_reviewable_asset(repo, "data/.gitkeep")

    assert _run(repo) == 0


def test_blocks_staged_removal_of_required_gitignore_rule(repo: Path) -> None:
    gitignore = repo / ".gitignore"
    original = gitignore.read_text(encoding="utf-8")
    gitignore.write_text(original.replace("test-DICOM-data/\n", ""), encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    # Restore the working copy after staging to prove the checker reads the index.
    gitignore.write_text(original, encoding="utf-8")

    assert _run(repo) == 1


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


def test_pdf_requires_hash_bound_manual_review(repo):
    from pypdf import PdfWriter

    path = "reports/synthetic.pdf"
    full_path = repo / path
    full_path.parent.mkdir(parents=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with full_path.open("wb") as stream:
        writer.write(stream)
    subprocess.run(["git", "add", "-f", path], cwd=repo, check=True)

    assert _run(repo) == 1

    _approve_reviewable_asset(repo, path)
    assert _run(repo) == 0


def test_pdf_text_is_scanned_for_private_network_values(repo):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    path = "reports/endpoint.pdf"
    full_path = repo / path
    full_path.parent.mkdir(parents=True)
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)  # pyright: ignore[reportPrivateUsage]
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (endpoint=192.168.1.20) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)  # pyright: ignore[reportPrivateUsage]
    with full_path.open("wb") as output:
        writer.write(output)
    subprocess.run(["git", "add", "-f", path], cwd=repo, check=True)

    assert any(
        "private-network address" in problem for problem in phi._check_pdf(path, repo)
    )
    assert _run(repo) == 1


@pytest.mark.parametrize(
    "path", ["notes/study.tex", "notes/study.ps", "notes/study.eps"]
)
def test_tex_and_postscript_text_are_scanned(repo, path):
    _stage(repo, path, "endpoint=192.168.1.20")
    assert _run(repo) == 1


def test_gzip_payload_is_scanned_for_phi_indicators(repo):
    _stage_bytes(repo, "exports/study.txt.gz", gzip.compress(b"endpoint=192.168.1.20"))

    assert _run(repo) == 1
    assert any(
        "private-network address" in item
        for item in phi._check_container("exports/study.txt.gz", repo)
    )


def test_tar_gz_payload_is_recursively_inspected(repo):
    tar_payload = io.BytesIO()
    contents = b"endpoint=192.168.1.20"
    with tarfile.open(fileobj=tar_payload, mode="w") as archive:
        member = tarfile.TarInfo("study.txt")
        member.size = len(contents)
        archive.addfile(member, io.BytesIO(contents))
    _stage_bytes(repo, "exports/study.tar.gz", gzip.compress(tar_payload.getvalue()))

    assert any(
        "private-network address" in item
        for item in phi._check_container("exports/study.tar.gz", repo)
    )
    assert _run(repo) == 1


def test_archive_recursively_inspects_nested_dicom(repo):
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import (
        ExplicitVRLittleEndian,
        SecondaryCaptureImageStorage,
        generate_uid,
    )

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset(
        "synthetic.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128
    )
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    dataset.PatientName = "Doe^Jane"
    dicom = io.BytesIO()
    pydicom.dcmwrite(dicom, dataset)

    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("study.dcm", dicom.getvalue())
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("nested.zip", inner.getvalue())
    _stage_bytes(repo, "imports/study.zip", outer.getvalue())

    problems = phi._check_container("imports/study.zip", repo)
    assert any("nested DICOM identifier PatientName" in item for item in problems)
    assert _run(repo) == 1


@pytest.mark.parametrize("extension", [".docx", ".odt", ".key", ".numbers", ".pages"])
def test_document_package_scans_text_and_requires_hash_bound_review(repo, extension):
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("word/document.xml", "endpoint=192.168.1.20")
        archive.writestr("word/media/image1.png", b"review-me")
    path = f"reports/review{extension}"
    _stage_bytes(repo, path, package.getvalue())

    assert any(
        "private-network address" in item for item in phi._check_container(path, repo)
    )
    assert _run(repo) == 1

    clean = io.BytesIO()
    with zipfile.ZipFile(clean, "w") as archive:
        archive.writestr("word/document.xml", "synthetic report")
        archive.writestr("word/media/image1.png", b"review-me")
    _stage_bytes(repo, path, clean.getvalue())
    assert _run(repo) == 1  # Embedded images mean a human must approve the package.

    _approve_reviewable_asset(repo, path)
    assert _run(repo) == 0


def test_unsupported_archives_fail_closed_even_when_hash_approved(repo):
    _stage_bytes(repo, "imports/study.7z", b"not-an-inspectable-archive")
    _approve_reviewable_asset(repo, "imports/study.7z")

    assert _run(repo) == 1


def test_empty_repo_passes(repo):
    assert _run(repo) == 0


def test_sensitive_filename_is_blocked_without_echoing_it(repo):
    marker = "patientname-SentinelAlpha-SentinelBeta.txt"
    _stage(repo, f"notes/{marker}", "synthetic")
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT), "--staged", "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert marker not in completed.stderr
    assert "sensitive-looking filename" in completed.stderr


@pytest.mark.parametrize(
    "content",
    [
        r"share=\\private-host\clinical",
        "url=https://account:credential@example.test/resource",
        "CallingAETitle=CLINICAL_AE",
        "endpoint=8.8.8.8",
    ],
)
def test_additional_endpoint_and_network_content_is_blocked(repo, content):
    _stage(repo, "notes/network.txt", content)
    assert _run(repo) == 1


@pytest.mark.parametrize("content", ["127.0.0.1", "::1", "198.51.100.42", "2001:db8::42"])
def test_loopback_and_documentation_addresses_are_allowed(repo, content):
    _stage(repo, "notes/network.txt", content)
    assert _run(repo) == 0


def test_archive_member_name_is_blocked_without_echoing_it(repo):
    marker = "patientname-SentinelAlpha-SentinelBeta.txt"
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(marker, "synthetic")
    _stage_bytes(repo, "imports/review.zip", payload.getvalue())
    problems = phi._check_container("imports/review.zip", repo)
    assert problems
    assert all(marker not in problem for problem in problems)


@pytest.mark.parametrize("target", ["/private/clinical", "../../outside"])
def test_absolute_and_escaping_symlinks_are_blocked(repo, target):
    link = repo / "linked-data"
    link.symlink_to(target)
    subprocess.run(["git", "add", "-f", "linked-data"], cwd=repo, check=True)
    assert phi.check_symlinks(["linked-data"], repo)
    assert _run(repo) == 1


def test_gitmodules_is_blocked(repo):
    _stage(repo, ".gitmodules", '[submodule "x"]\nurl=https://example.test/x.git\n')
    assert _run(repo) == 1


# --- the live repository -----------------------------------------------------


def test_this_repository_is_clean():
    """The real tree must stay clean, or the CI gate is already failing."""
    root = Path(__file__).resolve().parent.parent
    assert phi.check_paths(phi.tracked_files(root)) == []
    assert phi.check_contents(phi.tracked_files(root), root) == []
