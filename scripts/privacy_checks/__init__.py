"""Modular static privacy checks used by the repository Git hook."""

from .ast_rules import check_python_ast
from .git_paths import (
    all_python_scan_paths,
    git_diff_cached,
    git_show_staged,
    parse_added_line_numbers,
    staged_absolute_path_check_paths,
    staged_doc_like_paths,
    staged_python_scan_paths,
)
from .models import Violation, critical_violations, format_violations
from .text_rules import (
    check_absolute_path_in_doc_line,
    check_dialog_raw_exception,
    check_path_literal_in_logger_line,
    check_patient_fields_in_log_line,
    check_traceback_print_exc,
    patient_fields,
    reset_patient_fields_cache,
)

__all__ = [
    "Violation",
    "all_python_scan_paths",
    "check_absolute_path_in_doc_line",
    "check_dialog_raw_exception",
    "check_path_literal_in_logger_line",
    "check_patient_fields_in_log_line",
    "check_python_ast",
    "check_traceback_print_exc",
    "critical_violations",
    "format_violations",
    "git_diff_cached",
    "git_show_staged",
    "parse_added_line_numbers",
    "patient_fields",
    "reset_patient_fields_cache",
    "staged_absolute_path_check_paths",
    "staged_doc_like_paths",
    "staged_python_scan_paths",
]
