"""
Decoder corpus inventory & report (DECODER_REPLACEMENT_SPIKE_PLAN Phase 0-2).

Scans one or more roots for DICOM files and, for each, records the spike's
data-capture schema: transfer syntax, modality, pixel geometry, decode
success/failure, the decoded pixel SHA-256 (the "golden" fingerprint used to
detect silent pixel corruption when a decoder is swapped), decode time, and the
error class when decoding fails. Raw paths and exception text are never written
to the report.

It decodes through the *real* application path
(:func:`core.dicom_pixel_array.get_pixel_array`) so the report reflects exactly
what the app would produce, not a separate pydicom call.

Two modes (combinable):

* **Report** (default): write a JSON (and optional CSV) report under an explicit
  private output root outside the source checkout.
  Run once with ``pylibjpeg-libjpeg`` installed to capture the golden baseline,
  then again after removing it and diff with ``--baseline``.
* **Copy corpus** (``--copy-to DIR``): copy up to ``--per-syntax N`` representative
  files per transfer syntax into a (git-ignored) corpus folder, so a small,
  reproducible fixture set can be assembled from large external archives.

Examples
--------
Inventory + baseline over repo data and external archives::

    python scripts/decoder_corpus_report.py \
        "test-DICOM-data" \
        "<external-dicom-root>" \
        --output-root "<private-output-root>" \
        --out decoder_baseline.json --csv decoder_baseline.csv

Assemble a corpus (<=3 files per transfer syntax) into the git-ignored folder::

    python scripts/decoder_corpus_report.py "<external roots...>" \
        --output-root "<private-output-root>" \
        --copy-to decoder-corpus --per-syntax 3

After removing pylibjpeg-libjpeg, compare to the golden run::

    python scripts/decoder_corpus_report.py "test-DICOM-data/decoder-corpus" \
        --output-root "<private-output-root>" \
        --out decoder_pillow_only.json --baseline decoder_baseline.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

try:
    from scripts.privacy_console import print_structural_event
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]

    print_structural_event = privacy_console.print_structural_event

# Make the application package importable so we decode via the real app path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pydicom
from pydicom.errors import InvalidDicomError

from core.dicom_pixel_array import get_pixel_array
from utils.privacy.safe_storage import (
    assert_safe_internal_path,
    atomic_write_private_text,
    ensure_private_directory,
)

# Transfer syntaxes that pylibjpeg-libjpeg (the GPL blocker) currently covers and
# that are therefore most at risk when it is removed.
AT_RISK_SYNTAXES = {
    "1.2.840.10008.1.2.4.50": "JPEG Baseline 8-bit",
    "1.2.840.10008.1.2.4.51": "JPEG Extended 12-bit",
    "1.2.840.10008.1.2.4.57": "JPEG Lossless (process 14)",
    "1.2.840.10008.1.2.4.70": "JPEG Lossless (first-order prediction)",
}

# Decoder-relevant packages whose versions define the decode environment.
_DECODER_PACKAGES = (
    "pydicom",
    "pylibjpeg",
    "pylibjpeg-libjpeg",
    "pylibjpeg-openjpeg",
    "pylibjpeg-rle",
    "pyjpegls",
    "python-gdcm",
    "gdcm",
    "Pillow",
    "numpy",
)


@dataclass
class FileRecord:
    """One row of the data-capture schema for a single DICOM file."""

    path: str
    transfer_syntax_uid: str = ""
    transfer_syntax_name: str = ""
    at_risk: bool = False
    modality: str = ""
    samples_per_pixel: int | None = None
    photometric_interpretation: str = ""
    bits_allocated: int | None = None
    bits_stored: int | None = None
    planar_configuration: int | None = None
    rows: int | None = None
    columns: int | None = None
    number_of_frames: int | None = None
    has_pixel_data: bool = False
    decode_ok: bool = False
    pixel_sha256: str | None = None
    pixel_shape: str | None = None
    pixel_dtype: str | None = None
    decode_seconds: float | None = None
    error: str = ""


def _installed_versions() -> dict[str, str]:
    """Return installed versions for decoder-relevant packages (or 'not installed')."""
    out: dict[str, str] = {}
    for name in _DECODER_PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "not installed"
    return out


def _iter_dicom_files(root: Path) -> list[Path]:
    """Return candidate DICOM files under *root* (recursively).

    Accepts ``*.dcm`` plus extensionless files (common for raw DICOM exports);
    obvious non-DICOM extensions are skipped.
    """
    skip_ext = {".txt", ".md", ".json", ".csv", ".png", ".jpg", ".jpeg", ".pdf",
                ".zip", ".xml", ".db", ".sqlite", ".py", ".gz", ".ini"}
    files: list[Path] = []
    if root.is_file():
        return [root]
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in skip_ext:
            continue
        files.append(p)
    return files


def _read_header(path: Path) -> pydicom.Dataset | None:
    """Read a dataset (stopping before pixels) or return None if not DICOM."""
    try:
        return pydicom.dcmread(str(path), stop_before_pixels=True, force=False)
    except (InvalidDicomError, OSError):
        return None
    except Exception:
        return None


def inspect_file(path: Path, headers_only: bool = False) -> FileRecord | None:
    """Build a :class:`FileRecord` for *path*, decoding via the app path.

    When *headers_only* is True, skip the pixel decode/hash (fast inventory of
    transfer syntaxes over slow/network storage).

    Returns None if the file is not a parseable DICOM object.
    """
    header = _read_header(path)
    if header is None:
        return None

    rec = FileRecord(path=str(path))

    ts = getattr(getattr(header, "file_meta", None), "TransferSyntaxUID", None)
    if ts is not None:
        rec.transfer_syntax_uid = str(ts)
        rec.transfer_syntax_name = getattr(ts, "name", "")
        rec.at_risk = str(ts) in AT_RISK_SYNTAXES

    rec.modality = str(getattr(header, "Modality", ""))
    rec.samples_per_pixel = getattr(header, "SamplesPerPixel", None)
    rec.photometric_interpretation = str(getattr(header, "PhotometricInterpretation", ""))
    rec.bits_allocated = getattr(header, "BitsAllocated", None)
    rec.bits_stored = getattr(header, "BitsStored", None)
    rec.planar_configuration = getattr(header, "PlanarConfiguration", None)
    rec.rows = getattr(header, "Rows", None)
    rec.columns = getattr(header, "Columns", None)
    nframes = getattr(header, "NumberOfFrames", None)
    rec.number_of_frames = int(nframes) if nframes is not None else None

    if headers_only:
        return rec

    # Re-read with pixels for the decode attempt (full dataset).
    try:
        full = pydicom.dcmread(str(path), force=True)
    except Exception as e:
        rec.error = type(e).__name__
        return rec

    rec.has_pixel_data = "PixelData" in full
    if not rec.has_pixel_data:
        return rec

    start = time.perf_counter()
    try:
        arr = get_pixel_array(full)
    except Exception as e:
        rec.error = type(e).__name__
        return rec
    rec.decode_seconds = round(time.perf_counter() - start, 4)

    if arr is None:
        # get_pixel_array returns None on failure; capture the real reason via a raw attempt.
        try:
            _ = full.pixel_array
        except Exception as e:
            rec.error = type(e).__name__
        else:
            rec.error = "PixelDecodeUnavailable"
        return rec

    rec.decode_ok = True
    rec.pixel_sha256 = hashlib.sha256(arr.tobytes()).hexdigest()
    rec.pixel_shape = "x".join(str(d) for d in arr.shape)
    rec.pixel_dtype = str(arr.dtype)
    return rec


def _copy_corpus(records: list[FileRecord], dest: Path, per_syntax: int) -> list[str]:
    """Copy up to *per_syntax* files per transfer syntax into *dest*.

    Files are grouped into ``<dest>/<sanitized-syntax-name>/`` so the corpus is
    self-describing. Returns the list of copied destination paths.
    """
    ensure_private_directory(dest)
    counts: dict[str, int] = {}
    copied: list[str] = []
    # Prioritize at-risk syntaxes, then everything else, for deterministic selection.
    ordered = sorted(records, key=lambda r: (not r.at_risk, r.transfer_syntax_uid, r.path))
    for rec in ordered:
        if not rec.transfer_syntax_uid:
            continue
        key = rec.transfer_syntax_uid
        if counts.get(key, 0) >= per_syntax:
            continue
        label = (rec.transfer_syntax_name or rec.transfer_syntax_uid).replace("/", "-")
        label = "".join(c for c in label if c.isalnum() or c in " ._-").strip().replace(" ", "_")
        sub = dest / f"{label}__{rec.transfer_syntax_uid}"
        ensure_private_directory(sub)
        src = Path(rec.path)
        target = sub / src.name
        if target.exists():
            target = sub / f"{src.stem}_{counts.get(key, 0)}{src.suffix or '.dcm'}"
        try:
            shutil.copy2(src, target)
            try:
                target.chmod(0o600)
            except OSError:
                pass
            copied.append(str(target))
            counts[key] = counts.get(key, 0) + 1
        except OSError as e:
            print_structural_event("decoder.copy_failed", error=e)
    return copied


def _summarize(records: list[FileRecord]) -> dict[str, Any]:
    """Aggregate counts by transfer syntax with decode success rate."""
    by_syntax: dict[str, dict[str, Any]] = {}
    for rec in records:
        key = rec.transfer_syntax_uid or "(none)"
        s = by_syntax.setdefault(
            key,
            {
                "name": rec.transfer_syntax_name or "(unknown)",
                "at_risk": rec.at_risk,
                "total": 0,
                "decoded": 0,
                "failed": 0,
                "modalities": set(),
            },
        )
        s["total"] += 1
        s["decoded" if rec.decode_ok else "failed"] += 1
        if rec.modality:
            s["modalities"].add(rec.modality)
    for s in by_syntax.values():
        s["modalities"] = sorted(s["modalities"])
    return by_syntax


def print_decoder_environment(versions: dict[str, str]) -> None:
    print("Decoder environment:")
    for package, version in versions.items():
        if version == "not installed":
            print_structural_event(
                "decoder.package",
                category="not-installed",
                identifiers={"package": package},
            )
        else:
            print_structural_event(
                "decoder.package",
                identifiers={"package": package, "version": version},
            )
    print()


def print_syntax_summary(summary: dict[str, dict[str, Any]]) -> None:
    print("\n=== Transfer syntax summary (at-risk first) ===")
    for key in sorted(summary, key=lambda item: (not summary[item]["at_risk"], item)):
        values = summary[key]
        transfer_syntax_format = values["name"]
        if values["at_risk"]:
            print_structural_event(
                "decoder.syntax_summary",
                category="at-risk",
                identifiers={"format": transfer_syntax_format},
                metrics={
                    "total_count": values["total"],
                    "decoded_count": values["decoded"],
                    "failed_count": values["failed"],
                    "at_risk": values["at_risk"],
                },
            )
        else:
            print_structural_event(
                "decoder.syntax_summary",
                category="standard",
                identifiers={"format": transfer_syntax_format},
                metrics={
                    "total_count": values["total"],
                    "decoded_count": values["decoded"],
                    "failed_count": values["failed"],
                    "at_risk": values["at_risk"],
                },
            )


def _path_key(path: str | Path) -> str:
    """Return a stable one-way key without persisting a source path or filename."""

    normalized = str(Path(path).expanduser().resolve(strict=False))
    return hashlib.sha256(normalized.encode("utf-8", errors="surrogatepass")).hexdigest()


def _report_record(record: FileRecord) -> dict[str, Any]:
    """Serialize a record without its raw source path."""

    payload = asdict(record)
    payload["path_key"] = _path_key(record.path)
    del payload["path"]
    return payload


def _resolve_private_output(output_root: Path, requested: Path) -> Path:
    """Resolve a relative output below a private root outside the checkout."""

    if requested.is_absolute():
        raise ValueError("output names must be relative to --output-root")
    root = assert_safe_internal_path(output_root, source_root=_REPO_ROOT)
    ensure_private_directory(root)
    target = (root / requested).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("output names must remain below --output-root") from exc
    return target


def _diff_baseline(records: list[FileRecord], baseline_path: Path) -> dict[str, Any]:
    """Compare current decode hashes against a baseline report keyed by path key.

    Reports regressions: hash mismatches (silent corruption risk) and newly
    failing files. Raw paths are used only in memory and never returned.
    """
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))  # NOSONAR - baseline_path is the explicit --baseline CLI arg for this local dev tool, not attacker-controlled input
    base_by_key: dict[str, dict[str, Any]] = {}
    for r in baseline.get("records", []):
        key = r.get("path_key")
        if isinstance(key, str):
            base_by_key[key] = r

    mismatches: list[dict[str, str]] = []
    new_failures: list[str] = []
    matched = 0
    for rec in records:
        path_key = _path_key(rec.path)
        b = base_by_key.get(path_key)
        if b is None:
            continue
        matched += 1
        if b.get("decode_ok") and not rec.decode_ok:
            new_failures.append(path_key)
        elif b.get("decode_ok") and rec.decode_ok:
            if b.get("pixel_sha256") != rec.pixel_sha256:
                mismatches.append(
                    {
                        "file_key": path_key,
                        "syntax": rec.transfer_syntax_uid,
                        "baseline_sha256": b.get("pixel_sha256", ""),
                        "current_sha256": rec.pixel_sha256 or "",
                    }
                )
    return {
        "baseline_supplied": True,
        "matched": matched,
        "hash_mismatches": mismatches,
        "new_failures": new_failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+", help="Files or directories to scan (recursively).")
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Explicit private output root outside the source checkout.",
    )
    parser.add_argument("--out", type=Path, default=Path("decoder_report.json"), help="JSON filename below output root.")
    parser.add_argument("--csv", type=Path, default=None, help="Optional CSV filename below output root.")
    parser.add_argument("--copy-to", type=Path, default=None, help="Optional corpus directory below output root.")
    parser.add_argument("--per-syntax", type=int, default=3, help="Max files per transfer syntax when copying.")
    parser.add_argument("--baseline", type=Path, default=None, help="Baseline JSON to diff decode hashes against.")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N files (0 = no limit; for quick smoke).")
    parser.add_argument("--headers-only", action="store_true", help="Skip pixel decode/hash (fast transfer-syntax inventory).")
    args = parser.parse_args(argv)

    try:
        output_path = _resolve_private_output(args.output_root, args.out)
        csv_path = _resolve_private_output(args.output_root, args.csv) if args.csv else None
        copy_path = _resolve_private_output(args.output_root, args.copy_to) if args.copy_to else None
    except (OSError, ValueError):
        parser.error("outputs require a private --output-root outside the source checkout")

    versions = _installed_versions()
    print_decoder_environment(versions)

    records: list[FileRecord] = []
    scanned = 0
    for root_str in args.roots:
        root = Path(root_str)
        if not root.exists():
            print("SKIP: an input root was not found")
            continue
        print("Scanning an input root")
        for path in _iter_dicom_files(root):
            rec = inspect_file(path, headers_only=args.headers_only)
            scanned += 1
            if rec is not None:
                records.append(rec)
            if args.limit and scanned >= args.limit:
                break
        if args.limit and scanned >= args.limit:
            break

    summary = _summarize(records)

    print_syntax_summary(summary)

    report: dict[str, Any] = {
        "environment": versions,
        "root_count": len(args.roots),
        "file_count": len(records),
        "summary": {
            k: dict(v.items()) for k, v in summary.items()
        },
        "records": [_report_record(r) for r in records],
    }

    if args.baseline:
        diff = _diff_baseline(records, args.baseline)
        report["baseline_diff"] = diff
        print("\n=== Baseline diff ===")
        print(f"  matched files: {diff['matched']}")
        print(f"  hash mismatches (SILENT CORRUPTION RISK): {len(diff['hash_mismatches'])}")
        for _mismatch in diff["hash_mismatches"]:
            print_structural_event("decoder.hash_mismatch")
        print(f"  new failures: {len(diff['new_failures'])}")
        for _failure in diff["new_failures"]:
            print_structural_event("decoder.new_failure")

    atomic_write_private_text(
        output_path,
        json.dumps(report, indent=2),
        source_root=_REPO_ROOT,
    )
    print(f"\nWrote protected JSON report ({len(records)} files)")

    if csv_path:
        csv_buffer = io.StringIO(newline="")
        fieldnames = list(_report_record(FileRecord("")).keys())
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(_report_record(record))
        atomic_write_private_text(csv_path, csv_buffer.getvalue(), source_root=_REPO_ROOT)
        print("Wrote protected CSV report")

    if copy_path:
        copied = _copy_corpus(records, copy_path, args.per_syntax)
        print(f"Copied {len(copied)} files into the protected corpus")

    # Exit non-zero if a baseline diff found regressions (useful as a gate).
    if args.baseline:
        diff = report["baseline_diff"]
        if diff["hash_mismatches"] or diff["new_failures"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
