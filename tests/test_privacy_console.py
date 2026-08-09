"""
Unit tests for ``utils.privacy.console`` (fail-closed diagnostic printing).

Verifies that dynamic values are rendered through the redaction layer and never
leak arbitrary strings, exceptions, or structure.
"""

from __future__ import annotations

from utils.privacy.console import (
    _render_console_value,
    print_redacted,
    print_structural_event,
)


class _Capture:
    def __init__(self) -> None:
        self.buffer = ""
        self.flush_calls = 0

    def write(self, s: str) -> int:
        self.buffer += s
        return len(s)

    def flush(self) -> None:
        self.flush_calls += 1
        return None

    def getvalue(self) -> str:
        return self.buffer


class TestRenderConsoleValue:
    def test_basic_types_render(self):
        assert _render_console_value(1) == "1"
        assert _render_console_value(1.5) == "1.5"
        assert _render_console_value(True) == "True"

    def test_none_renders_empty(self):
        assert _render_console_value(None) == ""

    def test_exception_redacted(self):
        out = _render_console_value(ValueError("secret detail"))
        assert "secret detail" not in out

    def test_mapping_keys_redacted_by_index(self):
        # Mapping keys are untrusted data; redact_diagnostic_value relabels them
        # to field_N and recursively redacts values, so nothing sensitive leaks.
        out = _render_console_value({"b": 1, "a": 2})
        assert out == '{"field_0": 1, "field_1": 2}'

    def test_sequence_json(self):
        out = _render_console_value([1, 2, 3])
        assert out == "[1, 2, 3]"

    def test_arbitrary_string_redacted(self):
        out = _render_console_value("some free text")
        assert out == "[REDACTED]"


class TestPrintRedacted:
    def test_writes_rendered_values(self):
        cap = _Capture()
        print_redacted("free text", 42, file=cap)
        assert "[REDACTED]" in cap.getvalue()
        assert "42" in cap.getvalue()

    def test_custom_sep_and_end(self):
        cap = _Capture()
        print_redacted(1, 2, sep="-", end="!", file=cap)
        assert cap.getvalue() == "1-2!"

    def test_flush_called(self):
        cap = _Capture()
        print_redacted(1, file=cap, flush=True)
        # Default end is newline; flush=True must reach the stream exactly once.
        assert cap.getvalue() == "1\n"
        assert cap.flush_calls == 1

    def test_mapping_joined_redacts_keys(self):
        cap = _Capture()
        print_redacted({"x": 1}, file=cap)
        out = cap.getvalue()
        assert '"x"' not in out
        assert '"field_0": 1' in out


class TestPrintStructuralEvent:
    def test_writes_rendered_event(self):
        cap = _Capture()
        print_structural_event("op", category="cat", metrics={"n": 1}, file=cap)
        out = cap.getvalue()
        assert "operation=" in out
        # Unregistered operation / free-text category are not echoed verbatim.
        assert "cat" not in out

    def test_error_redacted(self):
        cap = _Capture()
        print_structural_event("op", error=RuntimeError("boom"), file=cap)
        assert "boom" not in cap.getvalue()

    def test_registered_operation_renders_class_not_detail(self):
        # A registered operation (application.unhandled) renders its operation and
        # the sanitized error class, but never the exception's secret detail.
        cap = _Capture()
        print_structural_event(
            "application.unhandled", error=RuntimeError("boom detail"), file=cap
        )
        out = cap.getvalue()
        assert "application.unhandled" in out
        assert "RuntimeError" in out
        assert "boom detail" not in out

    def test_flush_control(self):
        cap = _Capture()
        print_structural_event("op", file=cap, flush=True)
        assert "operation=" in cap.getvalue()
        assert cap.flush_calls == 1
