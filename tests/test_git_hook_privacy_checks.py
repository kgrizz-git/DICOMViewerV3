"""
Unit tests for scripts/git_hook_privacy_checks.py (staged-file privacy rules).

Uses importlib to load the hook module from the repo scripts/ directory.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "git_hook_privacy_checks.py"


def _load_privacy_module():
    spec = importlib.util.spec_from_file_location(
        "git_hook_privacy_checks", SCRIPT_PATH
    )
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


def test_check_traceback_print_exc_ignored_in_docstring() -> None:
    """Mentioning the API in a triple-quoted docstring must not fail the hook."""
    src = '''"""
    Prefer traceback.print_exc() for nothing — documentation only.
    """
x = 1
'''
    assert pc.check_traceback_print_exc("src/x.py", src) == []


def test_check_traceback_print_exc_ignored_in_string_literal() -> None:
    src = 'hint = "do not call traceback.print_exc() in production"\n'
    assert pc.check_traceback_print_exc("src/x.py", src) == []


def test_check_traceback_print_exc_ignored_in_end_of_line_comment() -> None:
    src = "import traceback  # see traceback.print_exc() — banned\n"
    assert pc.check_traceback_print_exc("src/x.py", src) == []


def test_check_dialog_raw_exception() -> None:
    line = 'QMessageBox.critical(self, "E", str(e))'
    vs = pc.check_dialog_raw_exception("src/d.py", line, 10)
    assert len(vs) == 1
    assert vs[0].rule == "dialog-raw-exception"


def test_check_logger_sanitize_ast_fstring_on_added_line() -> None:
    code = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.info(f'patient={patient_name}')\n"
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
        "logger.info(f'patient={patient_name}')\n"
    )
    # Line 3 is the logger call; added_lines empty -> no violations from AST rule
    assert pc.check_logger_sanitize_ast("src/t.py", code, set()) == []


@pytest.mark.skipif(
    not (REPO_ROOT / ".git").exists(),
    reason="needs git checkout for PATIENT_PII_FIELDS import path",
)
def test_patient_field_in_log_line() -> None:
    pc.reset_patient_fields_cache()
    line = 'logger.info("PatientName=foo")'
    vs = pc.check_patient_fields_in_log_line("src/p.py", line, 1)
    assert len(vs) >= 1
    assert any(v.rule == "patient-field-in-log" for v in vs)


def test_check_absolute_path_in_doc_line_flags_machine_specific_windows_path() -> None:
    line = '- Example: "C:\\Users\\alice\\Desktop\\scan.md"'
    vs = pc.check_absolute_path_in_doc_line("dev-docs/x.md", line, 12)
    assert len(vs) == 1
    assert vs[0].rule == "machine-specific-absolute-path"


def test_check_absolute_path_in_doc_line_flags_machine_specific_unix_path() -> None:
    line = "- Example: /Users/alice/Documents/report.md"
    vs = pc.check_absolute_path_in_doc_line("README.md", line, 4)
    assert len(vs) == 1
    assert vs[0].rule == "machine-specific-absolute-path"


def test_check_absolute_path_in_doc_line_flags_unc_path() -> None:
    line = r'root = "\\fileserver\patient-data\study"'
    vs = pc.check_absolute_path_in_doc_line("scripts/inventory.py", line, 4)
    assert len(vs) == 1
    assert vs[0].rule == "machine-specific-absolute-path"


def test_check_absolute_path_in_doc_line_allows_repo_relative_path() -> None:
    line = "`dev-docs/templates-generalized/safety-scan-template.md`"
    assert pc.check_absolute_path_in_doc_line("dev-docs/x.md", line, 8) == []


def test_check_absolute_path_in_doc_line_allows_allow_comment() -> None:
    line = "Path: C:\\Users\\alice\\Desktop\\scan.md <!-- privacy-hook: allow -->"
    assert pc.check_absolute_path_in_doc_line("dev-docs/x.md", line, 9) == []


def test_check_absolute_path_in_doc_line_allows_file_scheme_examples() -> None:
    line = "Use file:///tmp/report.html for offline docs."
    assert pc.check_absolute_path_in_doc_line("dev-docs/x.md", line, 10) == []


def test_check_absolute_path_in_doc_line_flags_machine_specific_path_in_script() -> (
    None
):
    line = 'target = "/Users/alice/Documents/private-study.dcm"'
    vs = pc.check_absolute_path_in_doc_line("scripts/benchmark.py", line, 3)
    assert len(vs) == 1
    assert vs[0].rule == "machine-specific-absolute-path"


def test_staged_absolute_path_check_paths_includes_scripts_and_excludes_tests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Result:
        stdout = (
            "scripts/benchmark.py\ndev-docs/note.md\ntests/test_path.py\nsrc/main.py\n"
        )

    monkeypatch.setattr(pc.subprocess, "run", lambda *args, **kwargs: Result())

    assert pc.staged_absolute_path_check_paths(tmp_path) == [
        "dev-docs/note.md",
        "scripts/benchmark.py",
        "src/main.py",
    ]


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        ("logger.info('loaded %s', patient_name)\n", "unsafe-logger-argument"),
        ("print(patient_name)\n", "unsafe-print-argument"),
        ("sys.stderr.write(patient_name)\n", "unsafe-stream-write"),
        (
            "debug_log('module:1', 'event', {'annotation': annotation})\n",
            "unsafe-debug-log-payload",
        ),
        ("QMessageBox.critical(self, 'Error', str(exc))\n", "dialog-raw-exception"),
        ("traceback.print_stack()\n", "traceback-output"),
        ("logging.exception('operation failed')\n", "logging-exception"),
        ("logger.error('operation failed', exc_info=True)\n", "logging-exc-info"),
    ],
)
def test_ast_sink_categories(source: str, rule: str) -> None:
    violations = pc.check_python_ast("src/sink.py", source)
    assert rule in {violation.rule for violation in violations}


def test_ast_logger_checks_every_formatting_argument() -> None:
    source = "logger.info('operation=%s count=%s', safe_event, patient_name)\n"
    violations = pc.check_python_ast("src/sink.py", source)
    assert any(violation.rule == "unsafe-logger-argument" for violation in violations)


def test_ast_allows_numeric_and_tool_summary_output() -> None:
    source = (
        "print(f'count={count} shape={array.shape} elapsed={elapsed:.3f}')\n"
        "logger.info('processed %d rows in %.2f seconds', count, elapsed)\n"
        "sys.stderr.write(status_summary)\n"
        "debug_log('module:1', 'timing', {'count': count, 'elapsed': elapsed})\n"
    )
    assert pc.check_python_ast("scripts/benchmark.py", source) == []


@pytest.mark.parametrize(
    "source",
    [
        "print(input_path)\n",
        "print(dataset.PatientName)\n",
        "logger.info('uid=%s', study_uid)\n",
        "logger.info('loaded', extra={'filename': filename})\n",
        "debug_log('module:1', 'event', {'annotation': annotation_text})\n",
        "sys.stderr.write(hostname)\n",
    ],
)
def test_ast_high_signal_privacy_references_still_fail(source: str) -> None:
    assert pc.check_python_ast("src/sink.py", source)


@pytest.mark.parametrize(
    "identifier",
    ["pair_dir", "outputDirectory", "study_root", "protected_output_root"],
)
def test_ast_classifies_directory_and_contextual_root_aliases(identifier: str) -> None:
    source = f"print(f'Output: {{{identifier}}}')\n"
    violations = pc.check_python_ast("tests/fusion_audit.py", source)
    assert {item.rule for item in violations} == {"unsafe-print-argument"}


def test_ast_does_not_classify_bare_root_or_root_count_as_path_aliases() -> None:
    source = "print(root)\nprint(f'roots={root_count}')\n"
    assert pc.check_python_ast("scripts/tree_metrics.py", source) == []


def test_ast_accepts_central_redaction_wrappers() -> None:
    source = (
        "logger.info(redact_text(message))\n"
        "print(sanitize_message(message))\n"
        "sys.stderr.write(redact_exception(exc))\n"
        "QMessageBox.critical(self, 'Error', sanitize_exception(exc))\n"
        "print_structural_event('fusion.load_summary', "
        "metrics={'instance_count': count, 'series_count': 1})\n"
        "log_structural_event(logger, 20, 'application.startup', error=exc)\n"
    )
    assert pc.check_python_ast("src/safe_sink.py", source) == []


def test_ast_accepts_redaction_inside_sink_expression_subtree() -> None:
    source = (
        "QMessageBox.critical(self, 'Error', f'Failed: {sanitize_message(str(e), redact_paths=True)}')\n"
        "logger.error('Failed: ' + redact_exception(exc))\n"
        "print(f'Input: {redact_text(input_path)}')\n"
    )
    assert pc.check_python_ast("src/safe_nested_sink.py", source) == []


def test_ast_accepts_structural_safe_logger_extras() -> None:
    source = (
        "logger.error('Load failed', extra={'operation': operation, 'error_class': type(exc).__name__})\n"
        "logger.info('Loaded', extra={'operation': 'load', 'count': count})\n"
        "logger.error('Load failed', extra=safe_event_fields('load', error=exc))\n"
    )
    assert pc.check_python_ast("src/safe_extra.py", source) == []


def test_ast_structural_extra_rejects_sensitive_additional_field() -> None:
    source = "logger.info('Loaded', extra={'operation': 'load', 'patient_name': patient_name})\n"
    assert pc.check_python_ast("src/unsafe_extra.py", source)


def test_generic_attribute_name_is_safe_but_patient_name_is_not() -> None:
    assert pc.check_python_ast("src/safe_name.py", "print(enum_value.name)\n") == []
    assert pc.check_python_ast("src/patient.py", "print(patient_name)\n")
    assert pc.check_python_ast("src/patient.py", "print(dataset.PatientName)\n")


def test_ast_inline_allowance_must_name_rule_and_review() -> None:
    reviewed = "print(patient_name)  # privacy-check: allow[unsafe-print-argument] review=PRIV-42\n"
    unnamed = "print(patient_name)  # privacy-hook: allow\n"
    wrong_rule = "print(patient_name)  # privacy-check: allow[unsafe-stream-write] review=PRIV-42\n"
    assert pc.check_python_ast("scripts/reviewed.py", reviewed) == []
    assert pc.check_python_ast("scripts/unnamed.py", unnamed)
    assert pc.check_python_ast("scripts/wrong.py", wrong_rule)


def test_violation_output_never_contains_source_canary() -> None:
    canary = "SYNTHETIC-CANARY-SHOULD-NOT-ECHO"
    source = f"print({canary!r} + patient_name)\n"
    violations = pc.check_python_ast("src/canary.py", source)
    output = pc.format_violations(violations)
    assert violations
    assert output == "src/canary.py:1: [unsafe-print-argument]"
    assert canary not in output
    assert all(not hasattr(violation, "message") for violation in violations)


def test_main_all_mode_output_is_redacted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    canary = "SYNTHETIC-CLI-CANARY-SHOULD-NOT-ECHO"
    monkeypatch.setattr(pc, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        pc,
        "scan_all",
        lambda _root: [pc.Violation("unsafe-print-argument", "src/canary.py", 7)],
    )
    monkeypatch.delenv("DICOMVIEWER_PRIVACY_HOOK", raising=False)

    assert pc.main(["--all"]) == 1
    output = capsys.readouterr().err
    assert "src/canary.py:7: [unsafe-print-argument]" in output
    assert canary not in output


def test_main_all_critical_filters_print_debug_and_never_echoes_canary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    canary = "SYNTHETIC-CRITICAL-CANARY-SHOULD-NOT-ECHO"
    findings = [
        pc.Violation("unsafe-print-argument", "src/print_sink.py", 3),
        pc.Violation("unsafe-debug-log-payload", "src/debug_sink.py", 4),
        pc.Violation("dialog-raw-exception", "src/dialog.py", 5),
        pc.Violation("unsafe-logger-argument", "src/logger.py", 6),
    ]
    monkeypatch.setattr(pc, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(pc, "scan_all", lambda _root: findings)
    monkeypatch.delenv("DICOMVIEWER_PRIVACY_HOOK", raising=False)

    assert pc.main(["--all", "--critical"]) == 1
    output = capsys.readouterr().err
    assert "src/dialog.py:5: [dialog-raw-exception]" in output
    assert "src/logger.py:6: [unsafe-logger-argument]" in output
    assert "print_sink.py" not in output
    assert "debug_sink.py" not in output
    assert canary not in output


def test_main_all_critical_succeeds_when_only_audit_findings_remain(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(pc, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        pc,
        "scan_all",
        lambda _root: [
            pc.Violation("unsafe-print-argument", "src/print_sink.py", 3),
            pc.Violation("unsafe-debug-log-payload", "src/debug_sink.py", 4),
        ],
    )

    assert pc.main(["--all", "--critical"]) == 0
    assert capsys.readouterr().err == ""


def test_explicit_staged_and_default_both_use_staged_scan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(pc, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(pc, "scan_staged", lambda _root: calls.append("staged") or [])
    monkeypatch.setattr(pc, "scan_all", lambda _root: calls.append("all") or [])

    assert pc.main([]) == 0
    assert pc.main(["--staged"]) == 0
    assert calls == ["staged", "staged"]


def test_all_mode_scope_includes_sources_scripts_and_external_data_tests(
    tmp_path: Path,
) -> None:
    included = [
        "src/app.py",
        "scripts/audit.py",
        "tests/fusion_audit_example.py",
        "tests/fusion_blind_verification.py",
        "tests/scripts/generate_rdsr_dose_sr_fixtures.py",
    ]
    excluded = ["tests/test_regular_unit.py", "src/backups/old.py"]
    for relpath in included + excluded:
        path = tmp_path / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n", encoding="utf-8")

    from scripts.privacy_checks.git_paths import all_python_scan_paths

    assert all_python_scan_paths(tmp_path) == sorted(included)


def test_current_tree_advisory_sink_inventory_is_closed() -> None:
    from scripts.privacy_checks.scanner import scan_all

    assert scan_all(REPO_ROOT) == []


@pytest.mark.parametrize(
    ("source", "rule"),
    [
        (
            "print_structural_event('application.SCHEMACANARY71A9')\n",
            "structural-event-operation",
        ),
        ("print_structural_event(operation)\n", "structural-event-operation"),
        (
            "print_structural_event('fusion.series_summary', category=category, "
            "metrics={'slice_count': 1, 'rows': 1, 'columns': 1, "
            "'pixel_spacing_mm': 1.0})\n",
            "structural-event-category",
        ),
        (
            "print_structural_event('decoder.package', identifiers=fields)\n",
            "structural-event-identifiers",
        ),
        (
            "print_structural_event('fusion.load_summary', metrics=fields)\n",
            "structural-event-metrics",
        ),
        (
            "print_structural_event('fusion.load_summary', "
            "metrics={metric_key: 1, 'series_count': 1})\n",
            "structural-event-metrics",
        ),
        (
            "print_structural_event('fusion.load_summary', "
            "metrics={'instance_count': 1, 'series_count': 1, 'marker': 1})\n",
            "structural-event-metrics",
        ),
        (
            "print_structural_event('decoder.package', identifiers={"
            "'package': 'pydicom', 'version': 'SCHEMACANARY71A9'})\n",
            "structural-event-identifiers",
        ),
        (
            "print_structural_event('fusion.load_summary', metrics={"
            "'instance_count': 'SCHEMACANARY71A9', 'series_count': 1})\n",
            "structural-event-metrics",
        ),
        (
            "StructuralEvent(operation='application.startup')\n",
            "structural-event-direct-construction",
        ),
        (
            "event = object.__new__(StructuralEvent)\n",
            "structural-event-low-level-allocation",
        ),
        (
            "allocate = object.__new__\nevent = allocate(EventAlias)\n",
            "structural-event-low-level-allocation",
        ),
        (
            "object.__setattr__(event, '_parts', parts)\n",
            "structural-event-private-mutation",
        ),
        (
            "mutate = object.__setattr__\nmutate(event, field, value)\n",
            "structural-event-private-mutation",
        ),
        (
            "setattr(event, '_integrity', digest)\n",
            "structural-event-private-mutation",
        ),
        (
            "event._integrity = digest\n",
            "structural-event-private-mutation",
        ),
        (
            "del event._parts\n",
            "structural-event-private-mutation",
        ),
        (
            "event = _seal_event(parts)\n",
            "structural-event-private-sealing",
        ),
        (
            "digest = _parts_integrity(parts)\n",
            "structural-event-private-sealing",
        ),
        (
            "digest = structural_events._EVENT_INTEGRITY_KEY\n",
            "structural-event-private-sealing",
        ),
        (
            "from utils.privacy.structural_events import _seal_event as seal\n",
            "structural-event-private-sealing",
        ),
        (
            "render_structural_event(event)\n",
            "structural-event-direct-render",
        ),
        (
            "from utils.privacy.structural_events import "
            "render_structural_event as render\n",
            "structural-event-direct-render",
        ),
        (
            "perf_mark('first_paint.SCHEMACANARY71A9')\n",
            "performance-event-label",
        ),
        ("perf_timer(performance_label)\n", "performance-event-label"),
        (
            "perf_mark('first_paint.display_slice.returned')\n",
            "performance-event-fields",
        ),
        (
            "perf_mark('first_paint.display_slice.returned', "
            "image_item_present=True, marker=1)\n",
            "performance-event-fields",
        ),
        (
            "print_license_obligation(package='example', version='1.0', "
            "license_name='MIT', source='classifier')\n",
            "structural-adapter-scope",
        ),
        (
            "_license_event('license.obligation', category='OBLIGATION', "
            "package='example', version='1.0', license_name='MIT', "
            "source='classifier')\n",
            "structural-adapter-scope",
        ),
    ],
)
def test_ast_structural_schema_negative_canary_matrix(source: str, rule: str) -> None:
    violations = pc.check_python_ast("src/schema_canary.py", source)
    assert rule in {item.rule for item in violations}


def test_ast_accepts_exact_structural_wrapper_contract() -> None:
    source = (
        "print_structural_event('fusion.load_summary', "
        "metrics={'instance_count': len(file_paths), 'series_count': 2}, "
        "sep='|', end='!', file=sys.stderr, flush=True)\n"
        "log_structural_event(logger, logging.CRITICAL, "
        "'application.startup', error=exc)\n"
    )
    assert pc.check_python_ast("src/exact_structural.py", source) == []


def test_ast_allows_structural_allocation_and_sealing_only_in_implementation() -> None:
    source = (
        "event = object.__new__(StructuralEvent)\n"
        "object.__setattr__(event, '_parts', parts)\n"
        "object.__setattr__(event, '_integrity', _parts_integrity(parts))\n"
        "event = _seal_event(parts)\n"
        "render_structural_event(event)\n"
    )
    violations = pc.check_python_ast(
        "src/utils/privacy/structural_events.py", source
    )
    fabrication_rules = {
        "structural-event-direct-render",
        "structural-event-low-level-allocation",
        "structural-event-private-mutation",
        "structural-event-private-sealing",
    }

    assert fabrication_rules.isdisjoint(item.rule for item in violations)


def test_structural_fabrication_rules_are_critical() -> None:
    from scripts.privacy_checks.models import CRITICAL_RULES

    assert {
        "structural-event-direct-render",
        "structural-event-low-level-allocation",
        "structural-event-private-mutation",
        "structural-event-private-sealing",
    }.issubset(CRITICAL_RULES)


def test_ast_accepts_narrow_adapters_only_in_reviewed_modules() -> None:
    license_source = (
        "print_license_obligation(package=row.get('name'), "
        "version=row.get('version'), license_name=row.get('license'), "
        "source=row.get('source'))\n"
    )
    architecture_source = (
        "print_architecture_violation('core-gui', module=module_name, "
        "repository_path=repository_path, line=line_number, file=sys.stderr)\n"
    )

    assert (
        pc.check_python_ast("scripts/check_dependency_licenses.py", license_source)
        == []
    )
    assert (
        pc.check_python_ast(
            "scripts/check_architecture_boundaries.py", architecture_source
        )
        == []
    )


def _metric_literal(validator_name: str) -> str:
    return {
        "boolean": "True",
        "count": "2",
        "duration_ms": "1.5",
        "index": "0",
        "megabytes": "2.5",
    }[validator_name]


def test_ast_accepts_all_55_reviewed_performance_variants() -> None:
    from utils.privacy.structural_schema import load_structural_event_schema

    schema = load_structural_event_schema()
    assert len(schema.performance_variants) == 55
    sources: list[str] = []
    for label, variant in schema.performance_variants.items():
        if variant.kind == "timer":
            sources.append(f"with perf_timer({label!r}):\n    pass\n")
            continue
        fields = ", ".join(
            f"{key}={_metric_literal(validator)}"
            for key, validator in variant.metrics.items()
        )
        separator = ", " if fields else ""
        sources.append(f"perf_mark({label!r}{separator}{fields})\n")

    assert pc.check_python_ast("src/all_performance_variants.py", "".join(sources)) == []


def test_staged_loader_uses_candidate_index_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.privacy_checks import scanner
    from utils.privacy.structural_schema import default_schema_path

    content = default_schema_path().read_text(encoding="utf-8")
    monkeypatch.setattr(
        scanner,
        "git_show_staged",
        lambda _root, relpath: content
        if relpath.endswith("structural_event_schema_v1.json")
        else None,
    )

    schema = scanner.load_scan_schema(tmp_path, staged=True)
    assert len(schema.operations) == 19
    assert len(schema.performance_variants) == 55


def test_staged_schema_change_forces_full_candidate_compatibility_scan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.privacy_checks import scanner
    from utils.privacy.structural_schema import (
        SCHEMA_RELATIVE_PATH,
        default_schema_path,
    )

    schema_content = default_schema_path().read_text(encoding="utf-8")
    source = "perf_mark('first_paint.SCHEMACANARY71A9')\n"
    monkeypatch.setattr(
        scanner,
        "git_show_staged",
        lambda _root, relpath: schema_content
        if relpath == SCHEMA_RELATIVE_PATH
        else source,
    )
    monkeypatch.setattr(
        scanner,
        "git_diff_cached",
        lambda _root, relpath: "schema changed"
        if relpath == SCHEMA_RELATIVE_PATH
        else "",
    )
    monkeypatch.setattr(scanner, "all_python_scan_paths", lambda _root: ["src/app.py"])
    monkeypatch.setattr(scanner, "staged_python_scan_paths", lambda _root: [])
    monkeypatch.setattr(scanner, "staged_absolute_path_check_paths", lambda _root: [])

    violations = scanner.scan_staged(tmp_path)
    assert {item.rule for item in violations} == {"performance-event-label"}
    assert all("SCHEMACANARY71A9" not in item.path for item in violations)


def test_staged_invalid_schema_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from scripts.privacy_checks import scanner
    from utils.privacy.structural_schema import (
        SCHEMA_RELATIVE_PATH,
        default_schema_path,
    )

    raw = json.loads(default_schema_path().read_text(encoding="utf-8"))
    raw["schema_version"] = 2
    monkeypatch.setattr(
        scanner,
        "git_show_staged",
        lambda _root, relpath: json.dumps(raw)
        if relpath == SCHEMA_RELATIVE_PATH
        else None,
    )

    assert scanner.scan_staged(tmp_path) == [
        pc.Violation("structural-schema", SCHEMA_RELATIVE_PATH, 0)
    ]
