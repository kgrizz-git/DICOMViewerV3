#!/usr/bin/env python3
"""
Block runtime artifacts and PHI-bearing data files from entering the repository.

The existing privacy gate (``git_hook_privacy_checks.py``) inspects *Python source*
for PII in log lines and docs. It has no concept of committed **data files**, which
is how three ``.pytest-tmp-*/dicom_viewer_config_test_signals.json`` files -- each
holding a real ``recent_files`` list with local drive paths and an identifiable
filename -- were committed in May 2026 and survived in history. A .gitignore rule
does not help: it does not untrack what is already in the index.

This checker closes that gap with two independent rules:

  1. **Path denylist.** Runtime artifacts that capture user state (pytest temp dirs,
     the app's own config JSON, generated reports) may never be tracked, wherever
     they appear.
  2. **Content scan.** Data files are searched for PHI/PII indicators: home-directory
     absolute paths, the app config's ``recent_files``/``last_path`` keys, and
     populated DICOM patient tags.

Usage:
    python scripts/check_no_phi_artifacts.py            # scan all tracked files (CI)
    python scripts/check_no_phi_artifacts.py --staged   # scan staged files (pre-commit)

Exit code: 0 clean, 1 if anything is flagged.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import subprocess
import sys
from pathlib import Path

# --- Rule 1: paths that must never be tracked -------------------------------
# Matched with Path.match / prefix semantics against the repo-relative posix path.
FORBIDDEN_PATH_PATTERNS: list[tuple[str, str]] = [
    (r"^\.pytest-tmp", "pytest temp dir: captures live app config (recent_files)"),
    (r"^pytest-of-", "pytest temp dir"),
    (r"(^|/)\.pytest_cache/", "pytest cache"),
    (
        r"(^|/)dicom_viewer_config.*\.json$",
        "app config: contains recent_files / local paths",
    ),
    (r"^pyright-report\.txt$", "generated type-check report (absolute local paths)"),
    (r"^backups/", "local source backups: not for version control"),
    (r"(^|/)\.DS_Store$", "macOS metadata"),
    (r"(^|/)\.cache/", "cache directory"),
]
FORBIDDEN_ARTIFACT_SUFFIXES = {".cache", ".err", ".log", ".out", ".pkl", ".trace"}

# --- Rule 2: PHI/PII indicators inside data files ---------------------------
DATA_SUFFIXES = {
    ".json",
    ".csv",
    ".txt",
    ".log",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".xml",
    ".html",
    ".htm",
    ".ipynb",
    ".md",
    ".rst",
    ".svg",
    ".tsv",
}
SPREADSHEET_SUFFIXES = {".xlsx", ".xlsm"}
DICOM_SUFFIXES = {".dcm", ".dicom", ".ima"}
NOTEBOOK_SUFFIXES = {".ipynb"}
# SVG is text-readable and is also content-scanned above.  The other formats are
# opaque containers, so they need an explicit hash review before admission.
IMAGE_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".ico",
    ".icns",
    ".jpeg",
    ".jpg",
    ".jp2",
    ".jxl",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}
APPROVED_MEDIA_MANIFEST = "security/approved-media-sha256.json"
APPROVED_TEXT_EXCEPTIONS_MANIFEST = "security/approved-phi-text-exceptions.json"

# A file without a suffix can hide a binary export or clinical data.  Existing
# reviewed assets live in the hash manifest; every new one blocks until reviewed.
EXTENSIONLESS_EXEMPT = {".gitignore", ".gitattributes"}

# These DICOM attributes must never hold a real value in a tracked fixture,
# including when nested in a sequence.  ``Dataset.iterall()`` visits sequence
# items recursively.
DICOM_IDENTIFIER_KEYWORDS = {
    "AccessionNumber",
    "InstitutionAddress",
    "InstitutionName",
    "IssuerOfPatientID",
    "OperatorsName",
    "OtherPatientIDs",
    "OtherPatientNames",
    "PatientAddress",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientComments",
    "PatientID",
    "PatientName",
    "PatientSex",
    "PatientTelephoneNumbers",
    "PerformingPhysicianName",
    "ReferringPhysicianName",
    "StationName",
    "StudyID",
}

CONTENT_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r'"(recent_files|last_path|last_export_path|last_pylinac_output_path)"'
        ),
        "app config key that records user file paths",
    ),
    (
        re.compile(r"[A-Za-z]:\\+Users\\+|[A-Za-z]:\\+To\b", re.I),
        "Windows absolute user path",
    ),
    (
        re.compile(r"/(Users|home)/(?!runner\b|user\b)[A-Za-z0-9._-]+/"),
        "POSIX absolute home path",
    ),
    (
        re.compile(r'"Patient(Name|ID|BirthDate)"\s*:\s*"(?!\s*")[^"]+'),
        "populated DICOM patient tag",
    ),
    (re.compile(r"\b(?:dicom|pacs)://[^\s/]+", re.I), "DICOM/PACS endpoint"),
    (
        re.compile(r"\b[a-z0-9][a-z0-9.-]*\.(?:corp|internal|lan|local)\b", re.I),
        "internal hostname",
    ),
]
PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)
IP_ADDRESS_TOKEN = re.compile(
    r"(?<![0-9A-Fa-f:.])(?:[0-9]{1,3}(?:\.[0-9]{1,3}){3}|[0-9A-Fa-f]{0,4}:[0-9A-Fa-f:.]+)(?![0-9A-Fa-f:.])"
)
SAFE_INTERNAL_HOSTNAMES = frozenset({"host.docker.internal"})


def _run(args: list[str], root: Path) -> str:
    return subprocess.run(
        args, cwd=root, capture_output=True, text=True, check=True
    ).stdout


def tracked_files(root: Path) -> list[str]:
    return [p for p in _run(["git", "ls-files"], root).splitlines() if p]


def staged_files(root: Path) -> list[str]:
    out = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], root)
    return [p for p in out.splitlines() if p]


def check_paths(paths: list[str]) -> list[str]:
    """Rule 1: forbidden paths, regardless of content."""
    problems = []
    for path in paths:
        if Path(path).suffix.lower() in FORBIDDEN_ARTIFACT_SUFFIXES:
            problems.append(f"{path}: forbidden runtime artifact")
            continue
        for pattern, why in FORBIDDEN_PATH_PATTERNS:
            if re.search(pattern, path):
                problems.append(f"{path}: forbidden artifact ({why})")
                break
    return problems


def _content_reasons(text: str) -> list[str]:
    """Return PHI/PII rule categories found in one text value, never the value."""
    reasons: list[str] = []
    for pattern, why in CONTENT_RULES:
        match = pattern.search(text)
        if match is None:
            continue
        if (
            why == "internal hostname"
            and match.group().lower() in SAFE_INTERNAL_HOSTNAMES
        ):
            continue
        reasons.append(why)
    for match in IP_ADDRESS_TOKEN.finditer(text):
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if any(address in network for network in PRIVATE_NETWORKS):
            reasons.append("private-network address")
    return list(dict.fromkeys(reasons))


def check_contents(paths: list[str], root: Path) -> list[str]:
    """Rule 2: PHI/PII indicators inside data files."""
    problems = []
    approved = _approved_text_exceptions(root)
    for path in paths:
        if Path(path).suffix.lower() not in DATA_SUFFIXES:
            continue
        full = root / path
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for reason in _content_reasons(line):
                if not _is_approved_text_exception(path, reason, root, approved):
                    problems.append(f"{path}:{lineno}: possible PHI/PII ({reason})")
    return problems


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _approved_text_exceptions(root: Path) -> dict[str, object]:
    """Load reviewed, hash-bound synthetic-text exceptions by repository path."""
    try:
        payload = json.loads(
            (root / APPROVED_TEXT_EXCEPTIONS_MANIFEST).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    files = payload.get("files", {})
    return files if isinstance(files, dict) else {}


def _is_approved_text_exception(
    path: str, reason: str, root: Path, approved: dict[str, object]
) -> bool:
    """Allow only a reviewed rule in an unchanged synthetic text fixture."""
    entry = approved.get(path)
    if not isinstance(entry, dict):
        return False
    expected_hash = entry.get("sha256")
    allowed_rules = entry.get("allowed_rules")
    return (
        isinstance(expected_hash, str)
        and isinstance(allowed_rules, list)
        and reason in allowed_rules
        and (root / path).is_file()
        and _sha256(root / path) == expected_hash
    )


def _approved_media(root: Path) -> dict[str, str]:
    manifest = root / APPROVED_MEDIA_MANIFEST
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = payload.get("files", {})
    return files if isinstance(files, dict) else {}


def _is_approved_media(path: str, root: Path, approved: dict[str, str]) -> bool:
    expected = approved.get(path)
    return (
        isinstance(expected, str)
        and (root / path).is_file()
        and _sha256(root / path) == expected
    )


def _image_tree_sha256(root: Path, directory: str) -> str:
    """Hash the paths and bytes of all tracked reviewable images in a directory."""
    prefix = f"{directory.rstrip('/')}/"
    digest = hashlib.sha256()
    for path in tracked_files(root):
        if (
            not path.startswith(prefix)
            or Path(path).suffix.lower() not in IMAGE_SUFFIXES
        ):
            continue
        full = root / path
        if not full.is_file():
            continue
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(full)))
    return digest.hexdigest()


def _approved_image_trees(manifest: dict[str, object]) -> dict[str, str]:
    """Return approved image-directory hashes from the review manifest."""
    trees = manifest.get("image_trees", {})
    if not isinstance(trees, dict):
        return {}
    return {
        directory.rstrip("/"): expected
        for directory, expected in trees.items()
        if isinstance(directory, str) and isinstance(expected, str)
    }


def _is_approved_image_tree(
    path: str, root: Path, approved_trees: dict[str, str], tree_digests: dict[str, str]
) -> bool:
    """Allow an image only when its entire reviewed directory is unchanged."""
    for directory, expected in approved_trees.items():
        if path.startswith(f"{directory}/"):
            actual = tree_digests.setdefault(
                directory, _image_tree_sha256(root, directory)
            )
            return actual == expected
    return False


def _check_spreadsheet(path: str, root: Path) -> list[str]:
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(root / path, read_only=True, data_only=False)
    except Exception as exc:
        return [f"{path}: spreadsheet could not be inspected ({type(exc).__name__})"]
    problems: list[str] = []
    approved = _approved_text_exceptions(root)
    try:
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                for value in row:
                    if not isinstance(value, str):
                        continue
                    for reason in _content_reasons(value):
                        if not _is_approved_text_exception(
                            path, reason, root, approved
                        ):
                            problems.append(
                                f"{path}: worksheet {sheet.title!r}: possible PHI/PII ({reason})"
                            )
    finally:
        workbook.close()
    return problems


def _check_dicom(path: str, root: Path) -> list[str]:
    try:
        import pydicom

        dataset = pydicom.dcmread(root / path, stop_before_pixels=True, force=False)
    except Exception as exc:
        return [f"{path}: DICOM could not be inspected ({type(exc).__name__})"]
    problems: list[str] = []
    for element in dataset.iterall():
        value = str(element.value).strip()
        if element.tag.is_private and value:
            problems.append(f"{path}: populated private DICOM tag {element.tag}")
        if element.keyword not in DICOM_IDENTIFIER_KEYWORDS:
            continue
        synthetic_fixture = path.startswith("tests/fixtures/dicom_rdsr/") and value in {
            "Synthetic^RDSR",
            "SYN-RDSR-001",
        }
        if value and not synthetic_fixture:
            problems.append(
                f"{path}: populated nested DICOM identifier {element.keyword}"
            )
    return problems


def _has_dicom_preamble(path: Path) -> bool:
    """Recognize standard DICOM files even when their filename hides the type."""
    try:
        with path.open("rb") as stream:
            return stream.read(132)[128:132] == b"DICM"
    except OSError:
        return False


def _check_notebook(path: str, root: Path) -> list[str]:
    """Require notebook outputs to be stripped before a reviewed notebook is admitted."""
    try:
        payload = json.loads((root / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"{path}: notebook could not be inspected"]
    cells = payload.get("cells", []) if isinstance(payload, dict) else []
    if not isinstance(cells, list):
        return [f"{path}: notebook has invalid cell structure"]
    if any(isinstance(cell, dict) and cell.get("outputs") for cell in cells):
        return [f"{path}: notebook outputs must be stripped before review"]
    return []


def check_reviewable_files(paths: list[str], root: Path) -> list[str]:
    """Fail closed for clinical/binary assets that require a human PHI review."""
    problems: list[str] = []
    manifest = root / APPROVED_MEDIA_MANIFEST
    try:
        manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest_payload = {}
    if not isinstance(manifest_payload, dict):
        manifest_payload = {}
    approved = _approved_media(root)
    approved_trees = _approved_image_trees(manifest_payload)
    tree_digests: dict[str, str] = {}
    for path in paths:
        suffix = Path(path).suffix.lower()
        is_extensionless = not suffix and path not in EXTENSIONLESS_EXEMPT
        has_dicom_preamble = _has_dicom_preamble(root / path)
        is_dicom = suffix in DICOM_SUFFIXES or has_dicom_preamble
        requires_review = (
            suffix in IMAGE_SUFFIXES or suffix in NOTEBOOK_SUFFIXES or is_extensionless
        )
        if is_dicom:
            problems.extend(_check_dicom(path, root))
            requires_review = True
        elif suffix in SPREADSHEET_SUFFIXES:
            problems.extend(_check_spreadsheet(path, root))
        elif suffix in NOTEBOOK_SUFFIXES:
            problems.extend(_check_notebook(path, root))
        image_tree_approved = suffix in IMAGE_SUFFIXES and _is_approved_image_tree(
            path, root, approved_trees, tree_digests
        )
        if (
            requires_review
            and not image_tree_approved
            and not _is_approved_media(path, root, approved)
        ):
            asset_kind = (
                "DICOM"
                if is_dicom
                else "notebook"
                if suffix in NOTEBOOK_SUFFIXES
                else "image/extensionless"
            )
            problems.append(
                f"{path}: unapproved {asset_kind} asset; "
                f"perform PHI/burned-in-text review and add its SHA-256 to {APPROVED_MEDIA_MANIFEST}"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged", action="store_true", help="scan staged files only (pre-commit hook)"
    )
    parser.add_argument("--root", default=None, help="repository root")
    args = parser.parse_args()

    root = (
        Path(args.root)
        if args.root
        else Path(_run(["git", "rev-parse", "--show-toplevel"], Path.cwd()).strip())
    )

    paths = staged_files(root) if args.staged else tracked_files(root)
    scope = "staged" if args.staged else "tracked"

    problems = (
        check_paths(paths)
        + check_contents(paths, root)
        + check_reviewable_files(paths, root)
    )

    if problems:
        print(
            f"BLOCKED: {len(problems)} PHI/artifact issue(s) in {scope} files:\n",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "\nThese files must not be committed. Remove them from the index:\n"
            "  git rm --cached <path>\n"
            "and confirm the path is covered by .gitignore.\n"
            "If this is a false positive, add an exemption in "
            "scripts/check_no_phi_artifacts.py.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: no PHI artifacts ({len(paths)} {scope} file(s) scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
