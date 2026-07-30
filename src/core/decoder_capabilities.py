"""Privacy-safe pixel-decoder capability and provenance helpers.

This module is deliberately limited to transfer-syntax UIDs, installed handler
names, and package versions. It never inspects a file path, DICOM identity
attribute, raw exception, or pixels, so callers can use its output in safe
diagnostics and user-facing compressed-decode errors.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from pydicom.pixel_data_handlers import (
    gdcm_handler,
    jpeg_ls_handler,
    pillow_handler,
    pylibjpeg_handler,
    rle_handler,
)
from pydicom.uid import UID

if TYPE_CHECKING:
    from pydicom.dataset import Dataset


_COMPRESSED_TRANSFER_SYNTAX_LABELS = {
    "1.2.840.10008.1.2.5": "RLE Lossless",
    "1.2.840.10008.1.2.4.50": "JPEG Baseline",
    "1.2.840.10008.1.2.4.51": "JPEG Extended",
    "1.2.840.10008.1.2.4.57": "JPEG Lossless",
    "1.2.840.10008.1.2.4.70": "JPEG Lossless",
    "1.2.840.10008.1.2.4.80": "JPEG-LS Lossless",
    "1.2.840.10008.1.2.4.81": "JPEG-LS Lossy",
    "1.2.840.10008.1.2.4.90": "JPEG 2000 Lossless",
    "1.2.840.10008.1.2.4.91": "JPEG 2000",
}

_HANDLERS: tuple[tuple[str, str, Any], ...] = (
    ("GDCM", "python-gdcm", gdcm_handler),
    ("pylibjpeg", "pylibjpeg", pylibjpeg_handler),
    ("JPEG-LS", "pyjpegls", jpeg_ls_handler),
    ("RLE", "pylibjpeg-rle", rle_handler),
    ("Pillow", "Pillow", pillow_handler),
)


def transfer_syntax_uid(dataset: Dataset) -> str | None:
    """Return a dataset's transfer-syntax UID, if its file meta supplies one."""
    file_meta = getattr(dataset, "file_meta", None)
    uid = getattr(file_meta, "TransferSyntaxUID", None)
    return str(uid) if uid else None


def transfer_syntax_label(transfer_syntax: str | None) -> str:
    """Return a stable, non-identifying label for a known compressed syntax."""
    if not transfer_syntax:
        return "compressed DICOM"
    return _COMPRESSED_TRANSFER_SYNTAX_LABELS.get(transfer_syntax, "compressed DICOM")


def is_compressed_transfer_syntax(transfer_syntax: str | None) -> bool:
    """Return whether pydicom identifies a transfer syntax as compressed."""
    if not transfer_syntax:
        return False
    try:
        return UID(transfer_syntax).is_compressed
    except Exception:
        return False


def available_decoder_backends(transfer_syntax: str | None) -> tuple[str, ...]:
    """Return installed pydicom handlers that advertise support for a syntax."""
    if not transfer_syntax:
        return ()

    available: list[str] = []
    for display_name, _package_name, handler in _HANDLERS:
        try:
            if handler.is_available() and handler.supports_transfer_syntax(transfer_syntax):
                available.append(display_name)
        except Exception:
            # A missing optional native library must be reported as unavailable, not exposed.
            continue
    return tuple(available)


def decoder_backend_versions(transfer_syntax: str | None) -> tuple[tuple[str, str], ...]:
    """Return installed handler package versions for safe diagnostics and QA provenance."""
    available = set(available_decoder_backends(transfer_syntax))
    versions: list[tuple[str, str]] = []
    for display_name, package_name, _handler in _HANDLERS:
        if display_name not in available:
            continue
        try:
            versions.append((display_name, version(package_name)))
        except PackageNotFoundError:
            versions.append((display_name, "unknown"))
    return tuple(versions)


def compressed_decode_failure_message(dataset: Dataset) -> str:
    """Describe a compressed-pixel decode failure without raw native error text."""
    transfer_syntax = transfer_syntax_uid(dataset)
    label = transfer_syntax_label(transfer_syntax)
    if transfer_syntax is None:
        return "Compressed DICOM pixel data cannot be decoded (transfer syntax unavailable)."

    installed = available_decoder_backends(transfer_syntax)
    if installed:
        return (
            f"{label} pixel data cannot be decoded (transfer syntax {transfer_syntax}). "
            "A compatible decoder is installed, but the pixel data could not be decoded."
        )
    return (
        f"{label} pixel data cannot be decoded (transfer syntax {transfer_syntax}). "
        "This build has no compatible decoder for that transfer syntax."
    )
