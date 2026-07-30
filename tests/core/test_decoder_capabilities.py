"""Regression tests for safe compressed-pixel decoder capability reporting."""

from __future__ import annotations

from pydicom.dataset import Dataset, FileMetaDataset

from core.decoder_capabilities import (
    available_decoder_backends,
    compressed_decode_failure_message,
    decoder_backend_versions,
    is_compressed_transfer_syntax,
    transfer_syntax_label,
    transfer_syntax_uid,
)


def _dataset(transfer_syntax: str | None) -> Dataset:
    dataset = Dataset()
    if transfer_syntax is not None:
        dataset.file_meta = FileMetaDataset()
        dataset.file_meta.TransferSyntaxUID = transfer_syntax
    return dataset


def test_classic_jpeg_capabilities_include_the_selected_gdcm_handler() -> None:
    for transfer_syntax in (
        "1.2.840.10008.1.2.4.50",
        "1.2.840.10008.1.2.4.51",
        "1.2.840.10008.1.2.4.57",
        "1.2.840.10008.1.2.4.70",
    ):
        assert "GDCM" in available_decoder_backends(transfer_syntax)


def test_decoder_provenance_reports_the_selected_gdcm_package_version() -> None:
    versions = dict(decoder_backend_versions("1.2.840.10008.1.2.4.51"))

    assert versions["GDCM"] == "3.2.6"


def test_compressed_decode_failure_message_is_specific_but_non_prescriptive() -> None:
    dataset = _dataset("1.2.840.10008.1.2.4.51")

    assert transfer_syntax_uid(dataset) == "1.2.840.10008.1.2.4.51"
    assert transfer_syntax_label("1.2.840.10008.1.2.4.51") == "JPEG Extended"
    message = compressed_decode_failure_message(dataset)
    assert "JPEG Extended" in message
    assert "1.2.840.10008.1.2.4.51" in message
    assert "compatible decoder is installed" in message
    assert "pip install" not in message
    assert "pylibjpeg-libjpeg" not in message


def test_unknown_compressed_syntax_reports_missing_capability_without_raw_error() -> None:
    message = compressed_decode_failure_message(_dataset("1.2.840.10008.1.2.4.999"))

    assert "1.2.840.10008.1.2.4.999" in message
    assert "no compatible decoder" in message


def test_compression_classification_uses_pydicom_transfer_syntax_metadata() -> None:
    assert is_compressed_transfer_syntax("1.2.840.10008.1.2.4.51")
    assert not is_compressed_transfer_syntax("1.2.840.10008.1.2.1")
    assert not is_compressed_transfer_syntax(None)
