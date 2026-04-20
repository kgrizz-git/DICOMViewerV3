"""
Unit tests for scripts/git_hook_privacy_checks.py (staged-file privacy rules).

Uses importlib to load the hook module from the repo scripts/ directory.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "git_hook_privacy_checks.py"


def _load_privacy_module():
    spec = importlib.util.spec_from_file_location("git_hook_privacy_checks", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["git_hook_privacy_checks"] = mod
    spec.loader.exec_module(mod)
    return mod


pc = _load_privacy_module()


def test_parse_added_line_numbers_new_file_hunk() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
new file mode 100644
--- /dev/null
+++ b/src/x.py
@@ -0,0 +1,2 @@
+alpha
+beta
"""
    assert pc.parse_added_line_numbers(diff) == {1, 2}


def test_check_traceback_print_exc_flags_line() -> None:
    bad = "def f():\n    traceback.print_exc()\n"
    vs = pc.check_traceback_print_exc("src/x.py", bad)
    assert len(vs) == 1
    assert vs[0].rule == "no-traceback-print-exc"


def test_check_traceback_print_exc_allow_inline() -> None:
    ok = "traceback.print_exc()  # privacy-hook: allow-print_exc\n"
    assert pc.check_traceback_print_exc("src/x.py", ok) == []


def test_check_dialog_raw_exception() -> None:
    line = 'QMessageBox.critical(self, "E", str(e))'
    vs = pc.check_dialog_raw_exception("src/d.py", line, 10)
    assert len(vs) == 1
    assert vs[0].rule == "dialog-raw-exception"


def test_check_logger_sanitize_ast_fstring_on_added_line() -> None:
    code = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.info(f'x={x}')\n"
    )
    # logger.info is on line 3 of the source string
    vs = pc.check_logger_sanitize_ast("src/t.py", code, {3})
    assert len(vs) == 1
    assert vs[0].rule == "logger-needs-sanitize"


def test_check_logger_sanitize_ast_literal_ok() -> None:
    code = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.info('static message')\n"
    )
    assert pc.check_logger_sanitize_ast("src/t.py", code, {3}) == []


def test_check_logger_sanitize_ast_sanitized_ok() -> None:
    code = (
        "import logging\n"
        "from utils.log_sanitizer import sanitize_message\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.info(sanitize_message(f'x={x}'))\n"
    )
    vs = pc.check_logger_sanitize_ast("src/t.py", code, {4})
    assert vs == []


def test_check_logger_sanitize_ast_not_on_added_line_skipped() -> None:
    code = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.info(f'x={x}')\n"
    )
    # Line 3 is the logger call; added_lines empty -> no violations from AST rule
    assert pc.check_logger_sanitize_ast("src/t.py", code, set()) == []


@pytest.mark.skipif(not (REPO_ROOT / ".git").exists(), reason="needs git checkout for PATIENT_PII_FIELDS import path")
def test_patient_field_in_log_line() -> None:
    pc.reset_patient_fields_cache()
    line = 'logger.info("PatientName=foo")'
    vs = pc.check_patient_fields_in_log_line("src/p.py", line, 1)
    assert len(vs) >= 1
    assert any(v.rule == "patient-field-in-log" for v in vs)
