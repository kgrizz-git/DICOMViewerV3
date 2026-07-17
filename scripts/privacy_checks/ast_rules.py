"""AST-backed detection of unsafe privacy-sensitive output sinks.

This module intentionally enforces local, syntactic contracts. It is not a
general Python alias, scope, or data-flow analyzer; runtime validation and
redaction at the final output/storage boundary remain authoritative.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Final

from .allowances import reviewed_allowance
from .models import Violation
from .schema_contract import StructuralEventSchema, load_structural_event_schema
from .text_rules import patient_fields

_LOGGER_METHODS: Final[frozenset[str]] = frozenset(
    {"debug", "info", "warning", "error", "critical", "exception", "log"}
)
_DIALOG_METHODS: Final[frozenset[str]] = frozenset(
    {
        "critical",
        "warning",
        "information",
        "setText",
        "setInformativeText",
        "setDetailedText",
    }
)
_SAFE_WRAPPERS: Final[frozenset[str]] = frozenset(
    {
        "redact_exception",
        "redact_text",
        "redact_value",
        "safe_event_fields",
        "sanitize_exception",
        "sanitize_message",
        "sanitize_path",
        "sanitize_value",
    }
)
_STRUCTURAL_WRAPPERS: Final[frozenset[str]] = frozenset(
    {"log_structural_event", "print_structural_event", "structural_event"}
)
_PERFORMANCE_HELPERS: Final[frozenset[str]] = frozenset({"perf_mark", "perf_timer"})
_LICENSE_ADAPTERS: Final[frozenset[str]] = frozenset(
    {
        "print_license_accepted",
        "print_license_obligation",
        "print_license_violation",
    }
)
_ARCHITECTURE_ADAPTERS: Final[frozenset[str]] = frozenset(
    {"print_architecture_baseline_written", "print_architecture_violation"}
)
_ADAPTER_BUILDERS: Final[frozenset[str]] = frozenset(
    {"_architecture_event", "_license_event"}
)
_STRUCTURAL_EVENT_IMPLEMENTATION_PATH: Final = (
    "src/utils/privacy/structural_events.py"
)
_STRUCTURAL_RENDER_PATHS: Final[frozenset[str]] = frozenset(
    {
        "src/utils/privacy/__init__.py",
        "src/utils/privacy/console.py",
        "src/utils/privacy/logging_filter.py",
        "src/utils/privacy/structural_adapters.py",
        _STRUCTURAL_EVENT_IMPLEMENTATION_PATH,
    }
)
_STRUCTURAL_PRIVATE_FIELDS: Final[frozenset[str]] = frozenset(
    {"_integrity", "_parts"}
)
_STRUCTURAL_PRIVATE_SEAL_NAMES: Final[frozenset[str]] = frozenset(
    {"_EVENT_INTEGRITY_KEY", "_parts_integrity", "_seal_event"}
)
_LOW_LEVEL_ALLOCATION_NAMES: Final[frozenset[str]] = frozenset(
    {"object.__new__", "builtins.object.__new__"}
)
_LOW_LEVEL_MUTATION_NAMES: Final[frozenset[str]] = frozenset(
    {"object.__setattr__", "builtins.object.__setattr__"}
)
_SCHEMA_IMPLEMENTATION_PATHS: Final[frozenset[str]] = frozenset(
    {
        "src/utils/privacy/console.py",
        "src/utils/perf_timer.py",
        "src/utils/privacy/structural_adapters.py",
        "src/utils/privacy/structural_events.py",
    }
)
_EXCEPTION_NAMES: Final[frozenset[str]] = frozenset(
    {"e", "err", "error", "exc", "exception", "exception_info", "traceback"}
)
_SENSITIVE_IDENTIFIER_PARTS: Final[frozenset[str]] = frozenset(
    {
        "accession",
        "annotation",
        "birthdate",
        "dob",
        "dir",
        "directory",
        "endpoint",
        "file",
        "filename",
        "filepath",
        "folder",
        "host",
        "hostname",
        "ip",
        "mrn",
        "patient",
        "path",
        "physician",
        "root",
        "seriesuid",
        "sopuid",
        "studyuid",
        "uid",
        "user",
        "username",
    }
)
_SAFE_NAME_IDENTIFIERS: Final[frozenset[str]] = frozenset(
    {
        "class_name",
        "function_name",
        "logger_name",
        "method_name",
        "module_name",
        "operation_name",
        "rule_name",
        "test_name",
        "tool_name",
        "type_name",
    }
)
_SAFE_METRIC_PARTS: Final[frozenset[str]] = frozenset(
    {
        "count",
        "duration",
        "elapsed",
        "index",
        "length",
        "shape",
        "size",
        "timing",
        "total",
    }
)
_COMPACT_SENSITIVE_IDENTIFIERS: Final[frozenset[str]] = frozenset(
    {
        "birthdate",
        "filename",
        "filepath",
        "hostname",
        "seriesuid",
        "sopuid",
        "studyuid",
        "username",
    }
)
_SAFE_STRUCTURED_FIELD_KEYS: Final[frozenset[str]] = frozenset(
    {"operation", "error_class", "count"}
)
_MACHINE_PATH = re.compile(
    r"(?:[A-Za-z]:\\(?:Users|Documents and Settings)\\|/Users/|/home/|\\\\[^\\]+\\)",
    re.IGNORECASE,
)


def _call_name(node: ast.Call) -> str:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        parts = [function.attr]
        value = function.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def _private_structural_field(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and node.attr in _STRUCTURAL_PRIVATE_FIELDS:
        return node.attr
    return None


def _is_static(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(
            node.value, (str, bytes, int, float, complex, bool, type(None))
        )
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_static(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            key is not None and _is_static(key) and _is_static(value)
            for key, value in zip(node.keys, node.values, strict=True)
        )
    return False


def _is_sanitized(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return _call_name(node).rsplit(".", maxsplit=1)[-1] in _SAFE_WRAPPERS


def _is_typed_metric_expression(node: ast.AST) -> bool:
    """Return True for reducers whose result cannot contain their input text."""

    return isinstance(node, ast.Compare) or (
        isinstance(node, ast.Call)
        and _call_name(node).rsplit(".", maxsplit=1)[-1] == "len"
        and len(node.args) == 1
        and not node.keywords
    )


def _is_safe_structured_fields(node: ast.AST) -> bool:
    """Return whether a dict exposes only deliberately non-sensitive fields."""

    if not isinstance(node, ast.Dict) or not node.keys:
        return False
    keys: list[str] = []
    for key in node.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return False
        keys.append(key.value)
    return bool(keys) and set(keys).issubset(_SAFE_STRUCTURED_FIELD_KEYS)


def _walk_unprotected(node: ast.AST) -> Iterable[ast.AST]:
    """Walk an expression without descending into approved redaction boundaries."""

    if _is_sanitized(node) or _is_safe_structured_fields(node):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_unprotected(child)


def _identifier_is_sensitive(identifier: str) -> bool:
    lowered = identifier.lower()
    compact = re.sub(r"[^a-z0-9]", "", lowered)
    if lowered in _SAFE_NAME_IDENTIFIERS:
        return False
    # ``Path.root`` and a local loop variable literally named ``root`` are too
    # common to classify by name alone. Contextual aliases such as
    # ``output_root`` and camel-case ``studyRoot`` remain sensitive below.
    if lowered == "root":
        return False
    parts = {part for part in re.split(r"[^a-z0-9]+", lowered) if part}
    if parts.intersection(_SAFE_METRIC_PARTS):
        return False
    if lowered == "name":
        return True
    if (
        lowered in _SENSITIVE_IDENTIFIER_PARTS
        or compact in _COMPACT_SENSITIVE_IDENTIFIERS
    ):
        return True
    if compact.endswith(("dir", "directory", "root")):
        return True
    contextual_parts = _SENSITIVE_IDENTIFIER_PARTS - {"endpoint", "user"}
    return bool(parts.intersection(contextual_parts))


def _contains_sensitive_reference(node: ast.AST) -> bool:
    if _is_sanitized(node) or _is_safe_structured_fields(node):
        return False
    canonical_fields = {field.lower() for field in patient_fields()}
    for child in _walk_unprotected(node):
        if isinstance(child, ast.Dict):
            for key, value in zip(child.keys, child.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and _identifier_is_sensitive(key.value)
                    and not _is_static(value)
                ):
                    return True
        if isinstance(child, ast.Subscript):
            key = child.slice
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and _identifier_is_sensitive(key.value)
            ):
                return True
    for child in _walk_unprotected(node):
        if isinstance(child, ast.Name) and _identifier_is_sensitive(child.id):
            return True
        if isinstance(child, ast.Attribute):
            attribute = child.attr.lower()
            if attribute in canonical_fields or (
                attribute != "name" and _identifier_is_sensitive(child.attr)
            ):
                return True
        if (
            isinstance(child, ast.keyword)
            and child.arg
            and _identifier_is_sensitive(child.arg)
        ):
            return True
    return _contains_exception_detail(node)


def _contains_sensitive_literal(node: ast.AST) -> bool:
    fields = patient_fields()
    for child in _walk_unprotected(node):
        if not isinstance(child, ast.Constant) or not isinstance(child.value, str):
            continue
        lowered = child.value.lower()
        if _MACHINE_PATH.search(child.value) or any(
            field.lower() in lowered for field in fields
        ):
            return True
    return False


def _contains_exception_detail(node: ast.AST) -> bool:
    for child in _walk_unprotected(node):
        if isinstance(child, ast.Name):
            name = child.id.lower()
            if (
                name in _EXCEPTION_NAMES
                or name.startswith("exc_")
                or name
                in {
                    "error_detail",
                    "error_details",
                    "error_message",
                    "error_msg",
                    "error_text",
                    "error_value",
                }
            ):
                return True
        if isinstance(child, ast.Call):
            name = _call_name(child).lower()
            if name.endswith(("traceback.format_exc", "traceback.format_exception")):
                return True
            if name in {"str", "repr"} and child.args:
                target = child.args[0]
                if (
                    isinstance(target, ast.Name)
                    and target.id.lower() in _EXCEPTION_NAMES
                ):
                    return True
    return False


def _is_logger_call(name: str) -> bool:
    parts = name.split(".")
    if not parts or parts[-1] not in _LOGGER_METHODS:
        return False
    return len(parts) > 1 and (
        parts[-2] in {"logger", "logging", "log", "_log"}
        or parts[-2].endswith(("logger", "_log"))
    )


def _span_selected(node: ast.AST, selected_lines: set[int] | None) -> bool:
    if selected_lines is None:
        return True
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", start)
    return any(line in selected_lines for line in range(start, end + 1))


def _keyword_map(node: ast.Call) -> dict[str, ast.AST] | None:
    result: dict[str, ast.AST] = {}
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg in result:
            return None
        result[keyword.arg] = keyword.value
    return result


def _literal_value(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return _DYNAMIC


_DYNAMIC: Final = object()


class _SinkVisitor(ast.NodeVisitor):
    def __init__(
        self,
        relpath: str,
        source_lines: list[str],
        selected_lines: set[int] | None,
        schema: StructuralEventSchema,
    ) -> None:
        self.relpath = relpath
        self.source_lines = source_lines
        self.selected_lines = selected_lines
        self.schema = schema
        self.violations: list[Violation] = []

    def _add(self, node: ast.AST, rule: str) -> None:
        if not _span_selected(node, self.selected_lines):
            return
        line = getattr(node, "lineno", 1)
        if reviewed_allowance(self.source_lines, line, rule):
            return
        self.violations.append(Violation(rule, self.relpath, line))

    def _check_args(self, node: ast.Call, args: Iterable[ast.AST], rule: str) -> None:
        arguments = tuple(args)
        if any(_contains_sensitive_reference(argument) for argument in arguments):
            self._add(node, rule)
        if any(_contains_sensitive_literal(argument) for argument in arguments):
            self._add(node, rule)
            self._add(node, "sensitive-literal-in-output")

    def _check_structural_wrapper(self, node: ast.Call, method: str) -> None:
        if self.relpath in _SCHEMA_IMPLEMENTATION_PATHS:
            return
        keywords = _keyword_map(node)
        if keywords is None:
            self._add(node, "structural-event-arguments")
            return
        operation_index = 2 if method == "log_structural_event" else 0
        operation_node = (
            node.args[operation_index]
            if len(node.args) > operation_index
            else keywords.get("operation")
        )
        operation = _literal_value(operation_node) if operation_node is not None else _DYNAMIC
        if not isinstance(operation, str) or operation not in self.schema.operations:
            self._add(node, "structural-event-operation")
            return
        operation_schema = self.schema.operations[operation]
        if operation_schema.adapter is not None:
            self._add(node, "structural-event-operation")
            return

        max_positional = 3 if method == "log_structural_event" else 1
        allowed_keywords = {"category", "error", "identifiers", "metrics", "operation"}
        if method == "print_structural_event":
            allowed_keywords.update({"end", "file", "flush", "sep"})
        if len(node.args) > max_positional or set(keywords) - allowed_keywords:
            self._add(node, "structural-event-arguments")

        category_node = keywords.get("category")
        category = None if category_node is None else _literal_value(category_node)
        if operation_schema.performance_kind is not None:
            variant = (
                self.schema.performance_variants.get(category)
                if isinstance(category, str)
                else None
            )
            if variant is None or variant.kind != operation_schema.performance_kind:
                self._add(node, "structural-event-category")
                variant_metrics: Mapping[str, str] | None = None
            else:
                variant_metrics = variant.metrics
        else:
            variant_metrics = None
            if category not in operation_schema.categories:
                self._add(node, "structural-event-category")

        error_node = keywords.get("error")
        if error_node is not None and not operation_schema.allow_error:
            self._add(node, "structural-event-error")
        self._check_schema_mapping(
            node,
            keywords.get("identifiers"),
            operation_schema.identifiers,
            operation_schema.required_identifiers,
            self.schema.validate_identifier,
            "structural-event-identifiers",
        )
        metric_fields = variant_metrics or operation_schema.metrics
        required_metrics = (
            frozenset(metric_fields)
            if variant_metrics is not None
            else operation_schema.required_metrics
        )
        self._check_schema_mapping(
            node,
            keywords.get("metrics"),
            metric_fields,
            required_metrics,
            self.schema.validate_metric,
            "structural-event-metrics",
        )
        for control in ("end", "sep"):
            if control in keywords and not isinstance(_literal_value(keywords[control]), str):
                self._add(node, "structural-event-arguments")
        if "flush" in keywords and not isinstance(
            _literal_value(keywords["flush"]), bool
        ):
            self._add(node, "structural-event-arguments")
        if "file" in keywords and _contains_sensitive_reference(keywords["file"]):
            self._add(node, "structural-event-arguments")

    def _check_schema_mapping(
        self,
        call: ast.Call,
        node: ast.AST | None,
        allowed: Mapping[str, str],
        required: frozenset[str],
        validator: Callable[[str, Any], str | None],
        rule: str,
    ) -> None:
        if node is None:
            if required:
                self._add(call, rule)
            return
        if not isinstance(node, ast.Dict):
            self._add(call, rule)
            return
        fields: dict[str, ast.AST] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            key = _literal_value(key_node) if key_node is not None else _DYNAMIC
            if not isinstance(key, str) or key in fields:
                self._add(call, rule)
                return
            fields[key] = value_node
        if set(fields) - set(allowed) or not required.issubset(fields):
            self._add(call, rule)
        for key, value_node in fields.items():
            validator_name = allowed.get(key)
            if validator_name is None:
                continue
            literal = _literal_value(value_node)
            if literal is not _DYNAMIC:
                if validator(validator_name, literal) is None:
                    self._add(call, rule)
            elif not _is_typed_metric_expression(value_node) and (
                _contains_sensitive_reference(value_node)
                or _contains_sensitive_literal(value_node)
            ):
                self._add(call, rule)

    def _check_performance_helper(self, node: ast.Call, method: str) -> None:
        if not node.args:
            self._add(node, "performance-event-label")
            return
        label = _literal_value(node.args[0])
        variant = (
            self.schema.performance_variants.get(label)
            if isinstance(label, str)
            else None
        )
        expected_kind = "mark" if method == "perf_mark" else "timer"
        if variant is None or variant.kind != expected_kind:
            self._add(node, "performance-event-label")
            return
        keywords = _keyword_map(node)
        if keywords is None or len(node.args) != 1:
            self._add(node, "performance-event-fields")
            return
        expected = set(variant.metrics)
        if expected_kind == "timer":
            expected.discard("elapsed_ms")
        if set(keywords) != expected:
            self._add(node, "performance-event-fields")
        for key, value_node in keywords.items():
            validator_name = variant.metrics.get(key)
            if validator_name is None:
                continue
            literal = _literal_value(value_node)
            if literal is not _DYNAMIC:
                if self.schema.validate_metric(validator_name, literal) is None:
                    self._add(node, "performance-event-fields")
            elif not _is_typed_metric_expression(value_node) and (
                _contains_sensitive_reference(value_node)
                or _contains_sensitive_literal(value_node)
            ):
                self._add(node, "performance-event-fields")

    def _check_structural_adapter(self, node: ast.Call, method: str) -> None:
        if method in _LICENSE_ADAPTERS:
            if self.relpath != "scripts/check_dependency_licenses.py":
                self._add(node, "structural-adapter-scope")
                return
            expected = {"license_name", "package", "source", "version"}
            positional = 0 if method == "print_license_obligation" else 1
            if len(node.args) != positional:
                self._add(node, "structural-event-arguments")
            if positional and (
                not isinstance(_literal_value(node.args[0]), str)
                or _literal_value(node.args[0]) not in {"FORBIDDEN", "UNKNOWN"}
            ):
                self._add(node, "structural-event-category")
        else:
            if self.relpath != "scripts/check_architecture_boundaries.py":
                self._add(node, "structural-adapter-scope")
                return
            if method == "print_architecture_baseline_written":
                expected = {"count"}
                positional = 0
            else:
                expected = {"file", "line", "module", "repository_path"}
                positional = 1
                category = _literal_value(node.args[0]) if node.args else _DYNAMIC
                if category not in {
                    "core-gui",
                    "domain-main",
                    "gui-main",
                    "syntax",
                    "utils-domain",
                }:
                    self._add(node, "structural-event-category")
            if len(node.args) != positional:
                self._add(node, "structural-event-arguments")
        keywords = _keyword_map(node)
        if keywords is None or set(keywords) != expected:
            self._add(node, "structural-event-arguments")

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        lowered = name.lower()
        method = name.rsplit(".", maxsplit=1)[-1]

        if name in _LOW_LEVEL_ALLOCATION_NAMES and (
            self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH
        ):
            self._add(node, "structural-event-low-level-allocation")
        elif self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and (
            name in _LOW_LEVEL_MUTATION_NAMES
            or (
                name in {"setattr", "builtins.setattr"}
                and len(node.args) >= 2
                and _literal_value(node.args[1]) in _STRUCTURAL_PRIVATE_FIELDS
            )
        ):
            self._add(node, "structural-event-private-mutation")
        elif (
            name in {"getattr", "builtins.getattr"}
            and len(node.args) >= 2
            and _literal_value(node.args[1])
            in _STRUCTURAL_PRIVATE_SEAL_NAMES | {"render_structural_event"}
            and self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH
        ):
            rule = (
                "structural-event-direct-render"
                if _literal_value(node.args[1]) == "render_structural_event"
                else "structural-event-private-sealing"
            )
            self._add(node, rule)
        elif (
            method in _STRUCTURAL_PRIVATE_SEAL_NAMES
            and self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH
        ):
            self._add(node, "structural-event-private-sealing")
        elif method == "render_structural_event":
            if self.relpath not in _STRUCTURAL_RENDER_PATHS:
                self._add(node, "structural-event-direct-render")
        elif method == "StructuralEvent":
            self._add(node, "structural-event-direct-construction")
        elif method in _STRUCTURAL_WRAPPERS:
            self._check_structural_wrapper(node, method)
        elif method in _PERFORMANCE_HELPERS:
            self._check_performance_helper(node, method)
        elif method in _ADAPTER_BUILDERS:
            if self.relpath != "src/utils/privacy/structural_adapters.py":
                self._add(node, "structural-adapter-scope")
        elif method in _LICENSE_ADAPTERS | _ARCHITECTURE_ADAPTERS:
            self._check_structural_adapter(node, method)
        elif lowered in {"traceback.print_exc", "traceback.print_stack"}:
            self._add(node, "traceback-output")
        elif _is_logger_call(name):
            if method == "exception":
                self._add(node, "logging-exception")
            else:
                self._check_args(node, node.args, "unsafe-logger-argument")
            if any(
                keyword.arg == "exc_info" and not _is_false(keyword.value)
                for keyword in node.keywords
            ):
                self._add(node, "logging-exc-info")
            dynamic_keywords = (
                keyword.value
                for keyword in node.keywords
                if keyword.arg not in {"exc_info", "stack_info", "stacklevel"}
            )
            self._check_args(node, dynamic_keywords, "unsafe-logger-argument")
        elif name == "print" or name.endswith(".pprint"):
            self._check_args(node, node.args, "unsafe-print-argument")
        elif lowered.endswith(("sys.stdout.write", "sys.stderr.write")):
            self._check_args(node, node.args, "unsafe-stream-write")
        elif method in {"debug_log", "annotation_debug"}:
            self._check_args(node, node.args, "unsafe-debug-log-payload")
            self._check_args(
                node,
                (keyword.value for keyword in node.keywords),
                "unsafe-debug-log-payload",
            )
        elif method in _DIALOG_METHODS and (
            "QMessageBox" in name
            or method.startswith("set")
            or len(name.split(".")) == 2
        ):
            if any(
                _contains_exception_detail(argument) and not _is_sanitized(argument)
                for argument in node.args
            ):
                self._add(node, "dialog-raw-exception")

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and any(
            _private_structural_field(target) for target in node.targets
        ):
            self._add(node, "structural-event-private-mutation")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH
            and _private_structural_field(node.target)
        ):
            self._add(node, "structural-event-private-mutation")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if (
            self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH
            and _private_structural_field(node.target)
        ):
            self._add(node, "structural-event-private-mutation")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and any(
            _private_structural_field(target) for target in node.targets
        ):
            self._add(node, "structural-event-private-mutation")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and (
            node.id in _STRUCTURAL_PRIVATE_SEAL_NAMES
        ):
            self._add(node, "structural-event-private-sealing")
        if (
            self.relpath not in _STRUCTURAL_RENDER_PATHS
            and node.id == "render_structural_event"
        ):
            self._add(node, "structural-event-direct-render")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and (
            node.attr in _STRUCTURAL_PRIVATE_SEAL_NAMES
        ):
            self._add(node, "structural-event-private-sealing")
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and (
            isinstance(node.value, ast.Name)
            and node.value.id in {"builtins", "object"}
            and node.attr == "__new__"
        ):
            self._add(node, "structural-event-low-level-allocation")
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and (
            isinstance(node.value, ast.Name)
            and node.value.id in {"builtins", "object"}
            and node.attr == "__setattr__"
        ):
            self._add(node, "structural-event-private-mutation")
        if (
            self.relpath not in _STRUCTURAL_RENDER_PATHS
            and node.attr == "render_structural_event"
        ):
            self._add(node, "structural-event-direct-render")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.relpath != _STRUCTURAL_EVENT_IMPLEMENTATION_PATH and any(
            item.name in _STRUCTURAL_PRIVATE_SEAL_NAMES for item in node.names
        ):
            self._add(node, "structural-event-private-sealing")
        if self.relpath not in _STRUCTURAL_RENDER_PATHS and any(
            item.name == "render_structural_event" for item in node.names
        ):
            self._add(node, "structural-event-direct-render")


def _is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value in (False, None)


def check_python_ast(
    relpath: str,
    source: str,
    selected_lines: set[int] | None = None,
    *,
    schema: StructuralEventSchema | None = None,
) -> list[Violation]:
    """Inspect privacy-sensitive Python sinks without retaining source values."""

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [Violation("syntax", relpath, error.lineno or 1)]
    visitor = _SinkVisitor(
        relpath,
        source.splitlines(),
        selected_lines,
        schema or load_structural_event_schema(),
    )
    visitor.visit(tree)
    return _deduplicate(visitor.violations)


def _deduplicate(violations: list[Violation]) -> list[Violation]:
    return list(dict.fromkeys(violations))
