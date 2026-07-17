"""Logging boundary that sanitizes records before handlers emit them."""

from __future__ import annotations

import logging

from utils.privacy.redaction import (
    REDACTED,
    redact_diagnostic_value,
    redact_exception,
    redact_text,
)
from utils.privacy.structural_events import StructuralEvent, render_structural_event


class PrivacyLogFilter(logging.Filter):
    """Sanitize messages, formatting arguments, exceptions, and stack details."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, StructuralEvent):
            record.msg = render_structural_event(record.msg)
            record.args = ()
        else:
            self._redact_message(record)

        self._redact_exception_and_extras(record)
        return True

    @staticmethod
    def _redact_message(record: logging.LogRecord) -> None:
        has_format_args = bool(record.args)
        record.msg = redact_text(record.msg) if has_format_args else REDACTED
        if isinstance(record.args, dict):
            record.args = {
                key: redact_diagnostic_value(value, key=key)
                for key, value in record.args.items()
            }
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_diagnostic_value(value) for value in record.args)
        elif record.args:
            record.args = redact_diagnostic_value(record.args)

    @staticmethod
    def _redact_exception_and_extras(record: logging.LogRecord) -> None:
        if record.exc_info:
            exc_type, exc_value, _traceback = record.exc_info
            class_name = exc_type.__name__ if exc_type else "Exception"
            record.msg = f"{record.msg} ({class_name}: [REDACTED EXCEPTION DETAIL])"
            record.exc_info = None
            record.exc_text = None
            if exc_value is not None:
                record.__dict__["privacy_exception"] = redact_exception(exc_value)
        if record.stack_info:
            record.stack_info = "[REDACTED STACK]"

        standard = logging.makeLogRecord({}).__dict__.keys()
        for key, value in tuple(record.__dict__.items()):
            if key in standard or key.startswith("privacy_"):
                continue
            record.__dict__[key] = redact_diagnostic_value(value, key=key)


def install_privacy_filter(logger: logging.Logger | None = None) -> PrivacyLogFilter:
    """Install one privacy filter on a logger and all of its existing handlers."""

    target = logger or logging.getLogger()
    privacy_filter: PrivacyLogFilter | None = None
    for existing in target.filters:
        if isinstance(existing, PrivacyLogFilter):
            privacy_filter = existing
            break
    if privacy_filter is None:
        privacy_filter = PrivacyLogFilter()
        target.addFilter(privacy_filter)
    for handler in target.handlers:
        if not any(isinstance(item, PrivacyLogFilter) for item in handler.filters):
            handler.addFilter(privacy_filter)
    return privacy_filter
