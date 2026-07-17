"""Regression canaries for fabricated structural-event state at output boundaries."""

from __future__ import annotations

import logging
from io import StringIO

import pytest

from utils.privacy.console import print_redacted
from utils.privacy.logging_filter import PrivacyLogFilter
from utils.privacy.structural_events import (
    StructuralEvent,
    render_structural_event,
    structural_event,
)

_CANARY = "FABRICATIONCANARY71A9"
_FALLBACK = "operation=[REDACTED]"


def _fabricated_event(parts: object) -> StructuralEvent:
    event = object.__new__(StructuralEvent)
    object.__setattr__(event, "_parts", parts)
    return event


def test_injected_private_parts_fail_closed_at_direct_render_boundary() -> None:
    event = _fabricated_event(
        (("operation", "application.startup"), ("identifier", _CANARY))
    )

    output = render_structural_event(event)

    leaked = _CANARY in output
    assert not leaked
    assert output == _FALLBACK


def test_mutated_sealed_event_fails_closed_at_direct_render_boundary() -> None:
    event = structural_event(
        "fusion.load_summary",
        metrics={"instance_count": 2, "series_count": 1},
    )
    object.__setattr__(
        event,
        "_parts",
        (("operation", "fusion.load_summary"), ("metric", _CANARY)),
    )

    output = render_structural_event(event)

    assert _CANARY not in output
    assert output == _FALLBACK


def test_copied_integrity_cannot_authenticate_modified_parts() -> None:
    legitimate = structural_event(
        "fusion.load_summary",
        metrics={"instance_count": 2, "series_count": 1},
    )
    event = _fabricated_event(
        (("operation", "application.startup"), ("identifier", _CANARY))
    )
    object.__setattr__(
        event,
        "_integrity",
        object.__getattribute__(legitimate, "_integrity"),
    )

    output = render_structural_event(event)

    assert _CANARY not in output
    assert output == _FALLBACK


@pytest.mark.parametrize(
    "parts",
    [
        _CANARY,
        (("operation", _CANARY),),
        (("operation", "application.startup"), (_CANARY, "value")),
        (("operation", "application.startup"), ("identifier", object())),
    ],
)
def test_malformed_fabricated_state_fails_closed(parts: object) -> None:
    output = render_structural_event(_fabricated_event(parts))

    assert _CANARY not in output
    assert output == _FALLBACK


def test_injected_private_parts_fail_closed_at_console_boundary() -> None:
    stream = StringIO()
    event = _fabricated_event(
        (("operation", "application.startup"), ("identifier", _CANARY))
    )

    print_redacted(event, file=stream)

    output = stream.getvalue()
    assert _CANARY not in output
    assert output == f"{_FALLBACK}\n"


def test_injected_private_parts_fail_closed_at_logging_boundary() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(PrivacyLogFilter())
    logger = logging.getLogger("privacy.structural.fabrication")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    event = _fabricated_event(
        (("operation", "application.startup"), ("identifier", _CANARY))
    )

    try:
        logger.info(event)
    finally:
        logger.handlers = []
        logger.propagate = True

    output = stream.getvalue()
    assert _CANARY not in output
    assert output == f"{_FALLBACK}\n"


def test_legitimate_sealed_event_preserves_render_console_and_log_semantics() -> None:
    event = structural_event(
        "fusion.load_summary",
        metrics={"instance_count": 2, "series_count": 1},
    )
    expected = (
        "operation=fusion.load_summary|instance_count=2|series_count=1"
    )
    assert render_structural_event(event, sep="|") == expected

    console_stream = StringIO()
    print_redacted(event, file=console_stream)
    assert console_stream.getvalue() == expected.replace("|", " ") + "\n"

    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.addFilter(PrivacyLogFilter())
    logger = logging.getLogger("privacy.structural.legitimate")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        logger.info(event)
    finally:
        logger.handlers = []
        logger.propagate = True
    assert log_stream.getvalue() == expected.replace("|", " ") + "\n"


def test_legitimate_factory_redactions_remain_authenticated_and_renderable() -> None:
    missing_metric = render_structural_event(
        structural_event(
            "fusion.load_summary",
            metrics={"instance_count": 2},
        )
    )
    invalid_category = render_structural_event(
        structural_event(
            "decoder.package",
            category="invalid-category",
            identifiers={"package": "pydicom"},
        )
    )

    assert missing_metric == (
        "operation=fusion.load_summary instance_count=2 "
        "series_count=[REDACTED]"
    )
    assert invalid_category == (
        "operation=decoder.package category=[REDACTED] validation=[REDACTED]"
    )
