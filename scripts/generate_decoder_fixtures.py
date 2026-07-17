"""
Generate compressed-DICOM test fixtures by transcoding with GDCM.

Useful for the decoder-replacement spike (DECODER_REPLACEMENT_SPIKE_PLAN): some
transfer syntaxes (e.g. ``.57`` JPEG Lossless Process 14, ``.81`` JPEG-LS
near-lossless) are rare and not offered as ready downloads, but GDCM can encode
them from any readable (typically uncompressed) source dataset.

**Requires** ``python-gdcm`` (``pip install python-gdcm``). It is intentionally
NOT a runtime dependency of the app — run this from a tooling venv (e.g. the
spike's ``.venv-gdcm``).

Example::

    .venv-gdcm/Scripts/python.exe scripts/generate_decoder_fixtures.py \
        path/to/uncompressed.dcm --syntax jpeg_lossless_p14 \
        --out decoder-spike-artifacts/generated/sample_57.dcm

Syntax keywords map to GDCM ``TransferSyntax`` values; see ``SYNTAX_MAP``.
Near-lossless (``.81``) honours ``--jpegls-error`` (the JPEG-LS NEAR parameter).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import gdcm  # type: ignore  # pyright: ignore[reportMissingImports]  # provided by python-gdcm
import pydicom

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

# Friendly keyword -> (GDCM TransferSyntax enum attr, expected DICOM UID).
SYNTAX_MAP: dict[str, tuple[str, str]] = {
    "jpeg_baseline": ("JPEGBaselineProcess1", "1.2.840.10008.1.2.4.50"),
    "jpeg_extended": ("JPEGExtendedProcess2_4", "1.2.840.10008.1.2.4.51"),
    "jpeg_lossless_p14": ("JPEGLosslessProcess14", "1.2.840.10008.1.2.4.57"),
    "jpeg_lossless_sv1": ("JPEGLosslessProcess14_1", "1.2.840.10008.1.2.4.70"),
    "jpegls_lossless": ("JPEGLSLossless", "1.2.840.10008.1.2.4.80"),
    "jpegls_nearlossless": ("JPEGLSNearLossless", "1.2.840.10008.1.2.4.81"),
    "jpeg2000_lossless": ("JPEG2000Lossless", "1.2.840.10008.1.2.4.90"),
    "jpeg2000": ("JPEG2000", "1.2.840.10008.1.2.4.91"),
    "rle": ("RLELossless", "1.2.840.10008.1.2.5"),
}


def transcode(src: str, dst: str, syntax_key: str, jpegls_error: int = 2) -> str:
    """Transcode *src* to *dst* using GDCM at the given *syntax_key*.

    Returns the resulting Transfer Syntax UID (verified by re-reading *dst*).
    Raises ``RuntimeError`` if any GDCM step fails.
    """
    if syntax_key not in SYNTAX_MAP:
        raise ValueError(f"Unknown syntax '{syntax_key}'. Choices: {', '.join(SYNTAX_MAP)}")
    enum_attr, _expected = SYNTAX_MAP[syntax_key]

    reader = gdcm.ImageReader()
    reader.SetFileName(src)
    if not reader.Read():
        raise RuntimeError(f"GDCM could not read source: {src}")

    change = gdcm.ImageChangeTransferSyntax()
    change.SetTransferSyntax(gdcm.TransferSyntax(getattr(gdcm.TransferSyntax, enum_attr)))
    if syntax_key == "jpegls_nearlossless":
        # The NEAR (max per-pixel error) parameter is only settable on the
        # low-level JPEGLSCodec; some python-gdcm builds do not expose it through
        # ImageChangeTransferSyntax. If unavailable, fall back (output may be
        # effectively lossless) — prefer a real downloaded .81 sample instead.
        if hasattr(change, "SetJPEGLSError"):
            change.SetJPEGLSError(jpegls_error)
        else:
            print(
                "  NOTE: this GDCM build cannot set JPEG-LS NEAR via "
                "ImageChangeTransferSyntax; use a downloaded .81 sample for a "
                "true near-lossless fixture."
            )
    change.SetInput(reader.GetImage())
    if not change.Change():
        raise RuntimeError(f"GDCM transcode to {syntax_key} failed")

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    writer = gdcm.ImageWriter()
    writer.SetFileName(dst)
    writer.SetFile(reader.GetFile())
    writer.SetImage(change.GetOutput())
    if not writer.Write():
        raise RuntimeError(f"GDCM could not write output: {dst}")

    chk = pydicom.dcmread(dst, stop_before_pixels=True, force=True)
    return str(chk.file_meta.TransferSyntaxUID)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="Source DICOM (typically uncompressed).")
    parser.add_argument("--syntax", required=True, choices=sorted(SYNTAX_MAP), help="Target transfer syntax keyword.")
    parser.add_argument("--out", required=True, help="Output DICOM path.")
    parser.add_argument("--jpegls-error", type=int, default=2, help="JPEG-LS NEAR value for near-lossless (default 2).")
    args = parser.parse_args()

    uid = transcode(args.source, args.out, args.syntax, args.jpegls_error)
    expected = SYNTAX_MAP[args.syntax][1]
    ok = "OK" if uid == expected else f"WARNING expected {expected}"
    print_redacted(f"Wrote {args.out}  TransferSyntax={uid}  [{ok}]")
    return 0 if uid == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
