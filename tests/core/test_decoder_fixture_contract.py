"""Tests for core.decoder_fixture_contract — synthetic decoder fixture contract."""

from __future__ import annotations

import re

import pytest

from core.decoder_fixture_contract import (
    DECODER_FIXTURE_EXPECTATIONS,
    GDCM_12_BIT_FALLBACK_DIAGNOSTIC,
    DecoderFixtureExpectation,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UID_RE = re.compile(r"^\d+(\.\d+)*$")


def test_expectation_dataclass_frozen():
    exp = DecoderFixtureExpectation("test.dcm", "1.2.3", "a" * 64)
    with pytest.raises(AttributeError):
        exp.filename = "other.dcm"


def test_expectation_default_stderr():
    exp = DecoderFixtureExpectation("test.dcm", "1.2.3", "a" * 64)
    assert exp.allowed_stderr == b""


def test_expectations_nonempty():
    assert len(DECODER_FIXTURE_EXPECTATIONS) == 9


def test_expectations_unique_filenames():
    filenames = [exp.filename for exp in DECODER_FIXTURE_EXPECTATIONS]
    assert len(filenames) == len(set(filenames))


def test_expectations_valid_sha256():
    for exp in DECODER_FIXTURE_EXPECTATIONS:
        assert _SHA256_RE.match(exp.pixel_sha256), exp.filename


def test_expectations_valid_uids():
    for exp in DECODER_FIXTURE_EXPECTATIONS:
        assert _UID_RE.match(exp.transfer_syntax_uid), exp.filename


def test_expectations_have_required_fields():
    for exp in DECODER_FIXTURE_EXPECTATIONS:
        assert isinstance(exp.filename, str) and exp.filename
        assert isinstance(exp.transfer_syntax_uid, str) and exp.transfer_syntax_uid
        assert isinstance(exp.pixel_sha256, str) and exp.pixel_sha256
        assert isinstance(exp.allowed_stderr, bytes)


def test_gdcm_diagnostic_constant():
    assert GDCM_12_BIT_FALLBACK_DIAGNOSTIC == b"Unsupported JPEG data precision 12\n"


def test_gdcm_diagnostic_used_by_fixture():
    jpeg_extended = next(
        exp
        for exp in DECODER_FIXTURE_EXPECTATIONS
        if exp.filename == "synthetic_monochrome_jpeg_extended_12_bit.dcm"
    )
    assert jpeg_extended.allowed_stderr == GDCM_12_BIT_FALLBACK_DIAGNOSTIC
