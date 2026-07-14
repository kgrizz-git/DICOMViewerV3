"""
Decoder corpus inventory & report (DECODER_REPLACEMENT_SPIKE_PLAN Phase 0-2).

Scans one or more roots for DICOM files and, for each, records the spike's
data-capture schema: transfer syntax, modality, pixel geometry, decode
success/failure, the decoded pixel SHA-256 (the "golden" fingerprint used to
detect silent pixel corruption when a decoder is swapped), decode time, and any
error text.

It decodes through the *real* application path
(:func:`core.dicom_pixel_array.get_pixel_array`) so the report reflects exactly
what the app would produce, not a separate pydicom call.

Two modes (combinable):

* **Report** (default): write a JSON (and optional CSV) report of every file.
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
        --out decoder_baseline.json --csv decoder_baseline.csv

Assemble a corpus (<=3 files per transfer syntax) into the git-ignored folder::

    python scripts/decoder_corpus_report.py "<external roots...>" \
        --copy-to test-DICOM-data/decoder-corpus --per-syntax 3

After removing pylibjpeg-libjpeg, compare to the golden run::

    python scripts/decoder_corpus_report.py "test-DICOM-data/decoder-corpus" \
        --out decoder_pillow_only.json --baseline decoder_baseline.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

# Make the application package importable so we decode via the real app path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

import pydicom
from pydicom.errors import InvalidDicomError

from core.dicom_pixel_array import get_pixel_array

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
        rec.error = f"read-with-pixels failed: {type(e).__name__}: {e}"[:300]
        return rec

    rec.has_pixel_data = "PixelData" in full
    if not rec.has_pixel_data:
        return rec

    start = time.perf_counter()
    try:
        arr = get_pixel_array(full)
    except Exception as e:
        rec.error = f"{type(e).__name__}: {e}"[:300]
        return rec
    rec.decode_seconds = round(time.perf_counter() - start, 4)

    if arr is None:
        # get_pixel_array returns None on failure; capture the real reason via a raw attempt.
        reason = getattr(full, "_no_pixel_reason", "")
        if reason:
            rec.error = f"no-pixel: {reason}"
        else:
            try:
                _ = full.pixel_array
            except Exception as e:
                rec.error = f"{type(e).__name__}: {e}"[:300]
            else:
                rec.error = "get_pixel_array returned None (unknown reason)"
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
    dest.mkdir(parents=True, exist_ok=True)  # NOSONAR - dest is the explicit --copy-to CLI arg for this local dev tool, not attacker-controlled input
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
        sub.mkdir(parents=True, exist_ok=True)
        src = Path(rec.path)
        target = sub / src.name
        if target.exists():
            target = sub / f"{src.stem}_{counts.get(key, 0)}{src.suffix or '.dcm'}"
        try:
            shutil.copy2(src, target)
            copied.append(str(target))
            counts[key] = counts.get(key, 0) + 1
        except OSError as e:
            print(f"  WARN copy failed {src}: {e}")
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


def _diff_baseline(records: list[FileRecord], baseline_path: Path) -> dict[str, Any]:
    """Compare current decode hashes against a baseline report keyed by file name.

    Matching is by file *name* (corpus files keep their names across runs).
    Reports regressions: hash mismatches (silent corruption risk) and newly
    failing files.
    """
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))  # NOSONAR - baseline_path is the explicit --baseline CLI arg for this local dev tool, not attacker-controlled input
    base_by_name: dict[str, dict[str, Any]] = {}
    for r in baseline.get("records", []):
        base_by_name[Path(r["path"]).name] = r

    mismatches: list[dict[str, str]] = []
    new_failures: list[str] = []
    matched = 0
    for rec in records:
        b = base_by_name.get(Path(rec.path).name)
        if b is None:
            continue
        matched += 1
        if b.get("decode_ok") and not rec.decode_ok:
            new_failures.append(rec.path)
        elif b.get("decode_ok") and rec.decode_ok:
            if b.get("pixel_sha256") != rec.pixel_sha256:
                mismatches.append(
                    {
                        "file": rec.path,
                        "syntax": rec.transfer_syntax_uid,
                        "baseline_sha256": b.get("pixel_sha256", ""),
                        "current_sha256": rec.pixel_sha256 or "",
                    }
                )
    return {
        "baseline": str(baseline_path),
        "matched": matched,
        "hash_mismatches": mismatches,
        "new_failures": new_failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+", help="Files or directories to scan (recursively).")
    parser.add_argument("--out", type=Path, default=Path("decoder_report.json"), help="JSON report output path.")
    parser.add_argument("--csv", type=Path, default=None, help="Optional CSV output path.")
    parser.add_argument("--copy-to", type=Path, default=None, help="Copy representative files per syntax into this dir.")
    parser.add_argument("--per-syntax", type=int, default=3, help="Max files per transfer syntax when copying.")
    parser.add_argument("--baseline", type=Path, default=None, help="Baseline JSON to diff decode hashes against.")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N files (0 = no limit; for quick smoke).")
    parser.add_argument("--headers-only", action="store_true", help="Skip pixel decode/hash (fast transfer-syntax inventory).")
    args = parser.parse_args(argv)

    versions = _installed_versions()
    print("Decoder environment:")
    for k, v in versions.items():
        print(f"  {k}: {v}")
    print()

    records: list[FileRecord] = []
    scanned = 0
    for root_str in args.roots:
        root = Path(root_str)
        if not root.exists():
            print(f"SKIP (not found): {root}")
            continue
        print(f"Scanning: {root}")
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

    # Console summary, at-risk syntaxes first.
    print("\n=== Transfer syntax summary (at-risk first) ===")
    for key in sorted(summary, key=lambda k: (not summary[k]["at_risk"], k)):
        s = summary[key]
        flag = "  <-- AT RISK" if s["at_risk"] else ""
        print(
            f"  {key} {s['name']}: total={s['total']} decoded={s['decoded']} "
            f"failed={s['failed']} modalities={','.join(s['modalities'])}{flag}"
        )

    report: dict[str, Any] = {
        "environment": versions,
        "roots": [str(r) for r in args.roots],
        "file_count": len(records),
        "summary": {
            k: dict(v.items()) for k, v in summary.items()
        },
        "records": [asdict(r) for r in records],
    }

    if args.baseline:
        diff = _diff_baseline(records, args.baseline)
        report["baseline_diff"] = diff
        print("\n=== Baseline diff ===")
        print(f"  matched files: {diff['matched']}")
        print(f"  hash mismatches (SILENT CORRUPTION RISK): {len(diff['hash_mismatches'])}")
        for m in diff["hash_mismatches"]:
            print(f"    ! {m['file']}  ({m['syntax']})")
        print(f"  new failures: {len(diff['new_failures'])}")
        for f in diff["new_failures"]:
            print(f"    x {f}")

    if args.out.parent and not args.out.parent.exists():
        args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")  # NOSONAR - args.out is the explicit --out CLI arg for this local dev tool, not attacker-controlled input
    print(f"\nWrote JSON report: {args.out}  ({len(records)} files)")

    if args.csv:
        import csv as _csv

        if args.csv.parent and not args.csv.parent.exists():
            args.csv.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(FileRecord("").__dict__.keys())
        with args.csv.open("w", newline="", encoding="utf-8") as f:  # NOSONAR - args.csv is the explicit --csv CLI arg for this local dev tool, not attacker-controlled input
            w = _csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in records:
                w.writerow(asdict(r))
        print(f"Wrote CSV report: {args.csv}")

    if args.copy_to:
        copied = _copy_corpus(records, args.copy_to, args.per_syntax)
        print(f"Copied {len(copied)} files into corpus: {args.copy_to}")

    # Exit non-zero if a baseline diff found regressions (useful as a gate).
    if args.baseline:
        diff = report["baseline_diff"]
        if diff["hash_mismatches"] or diff["new_failures"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
