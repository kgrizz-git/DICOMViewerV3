"""Local metadata plus Tesseract/Presidio media review adapter."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

from .common import (
    PrivacyToolResult,
    ToolStatus,
    protected_workspace,
    resolve_executable,
    run_command,
)

_TECHNICAL_METADATA = {
    "bitdepth",
    "colorspace",
    "colortype",
    "compression",
    "directory",
    "exifbyteorder",
    "exifimageheight",
    "exifimagewidth",
    "exiftoolversion",
    "fileaccessdate",
    "fileinodechangedate",
    "filemodifydate",
    "filename",
    "filepermissions",
    "filesize",
    "filetype",
    "filetypeextension",
    "filter",
    "imageheight",
    "imagesize",
    "imagewidth",
    "megapixels",
    "mimetype",
    "orientation",
    "pixelsperunitx",
    "pixelsperunity",
    "pixelunits",
    "resolutionunit",
    "sourcefile",
    "srgbrendering",
    "xresolution",
    "yresolution",
}


def run_media_review(path: Path, *, timeout: float = 300) -> PrivacyToolResult:
    """Review embedded metadata and OCR locally; retain no text or image crops."""
    # Commands execute inside a protected temporary working directory. Resolve
    # caller-supplied relative paths before changing cwd so the scanner sees the
    # intended file rather than a nonexistent path below that workspace.
    path = path.resolve()
    exiftool = resolve_executable("exiftool")
    tesseract = resolve_executable("tesseract")
    if exiftool is None and tesseract is None:
        return PrivacyToolResult(
            "media-review", ToolStatus.SKIP, reason="tools-missing"
        )
    categories: dict[str, int] = {}
    errors = 0
    with protected_workspace("dvv-media-") as workspace:
        if exiftool is not None:
            metadata = run_command([exiftool, "-json", str(path)], timeout=timeout)
            if metadata.timed_out:
                return PrivacyToolResult(
                    "media-review", ToolStatus.ERROR, reason="timeout"
                )
            try:
                payload = json.loads(metadata.stdout)
                record = payload[0]
                metadata_count = sum(
                    1
                    for key in record
                    if key.lower().replace(" ", "") not in _TECHNICAL_METADATA
                )
                if metadata_count:
                    categories["embedded-metadata"] = metadata_count
            except (json.JSONDecodeError, IndexError, TypeError):
                errors += 1
        if tesseract is not None:
            ocr = run_command(
                [tesseract, str(path), "stdout", "tsv"], timeout=timeout, cwd=workspace
            )
            if ocr.timed_out:
                return PrivacyToolResult(
                    "media-review", ToolStatus.ERROR, reason="timeout"
                )
            if ocr.returncode != 0:
                errors += 1
            else:
                text_rows = [
                    row
                    for row in ocr.stdout.splitlines()[1:]
                    if row.split("\t")[-1].strip()
                ]
                if text_rows:
                    categories["ocr-text"] = len(text_rows)
                    try:
                        analyzer_class = import_module(
                            "presidio_analyzer"
                        ).AnalyzerEngine
                        text = " ".join(row.split("\t")[-1] for row in text_rows)
                        entities = analyzer_class().analyze(text=text, language="en")
                        if entities:
                            categories["presidio-entity"] = len(entities)
                    except (ImportError, OSError, RuntimeError, ValueError):
                        categories["presidio-unavailable"] = 1
    if errors:
        return PrivacyToolResult(
            "media-review", ToolStatus.ERROR, reason="tool-error", scanned_count=1
        )
    count = sum(
        value for key, value in categories.items() if key != "presidio-unavailable"
    )
    return PrivacyToolResult(
        "media-review",
        ToolStatus.FINDINGS if count else ToolStatus.CLEAN,
        count,
        categories,
        scanned_count=1,
    )
