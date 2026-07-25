"""Strict loader for the versioned structural-event privacy contract."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

SCHEMA_FILENAME: Final = "structural_event_schema_v1.json"
SCHEMA_RELATIVE_PATH: Final = f"src/utils/privacy/{SCHEMA_FILENAME}"
EXPECTED_SCHEMA_VERSION: Final = 1
EXPECTED_OPERATION_COUNT: Final = 19
EXPECTED_PERFORMANCE_VARIANT_COUNT: Final = 55

_TOP_LEVEL_KEYS = {
    "schema_version",
    "identifier_validators",
    "metric_validators",
    "operations",
    "performance_variants",
}
_OPERATION_KEYS = {
    "adapter",
    "allow_error",
    "categories",
    "identifiers",
    "required_identifiers",
    "metrics",
    "required_metrics",
    "performance_kind",
}
_PERFORMANCE_KEYS = {"kind", "metrics"}
_SENSITIVE_SUFFIX = re.compile(
    r"\.(?:dcm|dicom|json|csv|xlsx?|pdf|png|jpe?g)$", re.IGNORECASE
)
_ERROR_CLASS = re.compile(r"[A-Z][A-Za-z0-9]{0,63}")


class StructuralSchemaError(ValueError):
    """Raised when the canonical schema is absent, malformed, or incompatible."""


@dataclass(frozen=True, slots=True)
class ValueValidator:
    """One immutable identifier or metric value-domain definition."""

    kind: str
    pattern: re.Pattern[str] | None = None
    family_pattern: re.Pattern[str] | None = None
    values: frozenset[str] = frozenset()
    minimum: float | None = None
    maximum: float | None = None
    minimum_items: int | None = None
    maximum_items: int | None = None


@dataclass(frozen=True, slots=True)
class OperationSchema:
    """Exact category, field, error, and adapter contract for one operation."""

    adapter: str | None
    allow_error: bool
    categories: frozenset[str | None]
    identifiers: Mapping[str, str]
    required_identifiers: frozenset[str]
    metrics: Mapping[str, str]
    required_metrics: frozenset[str]
    performance_kind: str | None


@dataclass(frozen=True, slots=True)
class PerformanceVariantSchema:
    """Exact helper kind and metric fields for one reviewed performance label."""

    kind: str
    metrics: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class StructuralEventSchema:
    """Immutable canonical contract shared by runtime and static analysis."""

    version: int
    identifier_validators: Mapping[str, ValueValidator]
    metric_validators: Mapping[str, ValueValidator]
    operations: Mapping[str, OperationSchema]
    performance_variants: Mapping[str, PerformanceVariantSchema]

    def validate_identifier(self, validator_name: str, value: Any) -> str | None:
        """Return a validated identifier string, or ``None`` when it fails closed."""

        validator = self.identifier_validators.get(validator_name)
        if validator is None or not isinstance(value, str):
            return None
        if _SENSITIVE_SUFFIX.search(value) or value.startswith(("2.25.", "1.2.840.")):
            return None
        if validator.kind == "enum":
            return value if value in validator.values else None
        if validator.pattern is None or validator.pattern.fullmatch(value) is None:
            return None
        if validator.kind == "regex_family" and (
            validator.family_pattern is None
            or validator.family_pattern.search(value) is None
        ):
            return None
        return value

    def validate_metric(self, validator_name: str, value: Any) -> str | None:
        """Return a normalized typed metric, or ``None`` when outside its range."""

        validator = self.metric_validators.get(validator_name)
        if validator is None:
            return None
        if validator.kind == "boolean":
            return _validate_boolean_metric(value)
        if validator.kind == "integer":
            return _validate_integer_metric(validator, value)
        if validator.kind == "number":
            return _validate_number_metric(validator, value)
        if validator.kind == "integer_sequence":
            return _validate_integer_sequence_metric(validator, value)
        return None

    def validate_rendered_metric(self, validator_name: str, value: Any) -> str | None:
        """Revalidate one normalized metric at the final output boundary."""

        validator = self.metric_validators.get(validator_name)
        if validator is None or not isinstance(value, str):
            return None
        if validator.kind == "boolean":
            return _validate_rendered_boolean_metric(value)
        if validator.kind == "integer":
            return _validate_rendered_integer_metric(validator, value)
        if validator.kind == "number":
            return _validate_rendered_number_metric(validator, value)
        if validator.kind == "integer_sequence":
            return _validate_rendered_integer_sequence_metric(validator, value)
        return None

    @staticmethod
    def validate_error_class(value: Any) -> str | None:
        """Return only a class name derived from an exception instance or type."""

        if isinstance(value, type) and issubclass(value, BaseException):
            name = value.__name__
        elif isinstance(value, BaseException):
            name = type(value).__name__
        else:
            return None
        return name if _ERROR_CLASS.fullmatch(name) else None

    @staticmethod
    def validate_rendered_error_class(value: Any) -> str | None:
        """Revalidate a previously normalized exception class name."""

        return (
            value if isinstance(value, str) and _ERROR_CLASS.fullmatch(value) else None
        )


def _in_range(validator: ValueValidator, value: float) -> bool:
    return (
        validator.minimum is not None
        and validator.maximum is not None
        and validator.minimum <= value <= validator.maximum
    )


def _validate_boolean_metric(value: Any) -> str | None:
    return str(value).lower() if isinstance(value, bool) else None


def _validate_integer_metric(validator: ValueValidator, value: Any) -> str | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return str(value) if _in_range(validator, value) else None


def _validate_number_metric(validator: ValueValidator, value: Any) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not _in_range(validator, numeric):
        return None
    return f"{value:g}"


def _has_valid_item_count(validator: ValueValidator, item_count: int) -> bool:
    return (
        validator.minimum_items is not None
        and validator.maximum_items is not None
        and validator.minimum_items <= item_count <= validator.maximum_items
    )


def _validate_integer_sequence_metric(
    validator: ValueValidator, value: Any
) -> str | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    items = list(value)
    if not _has_valid_item_count(validator, len(items)):
        return None
    if any(
        not isinstance(item, int)
        or isinstance(item, bool)
        or not _in_range(validator, item)
        for item in items
    ):
        return None
    return "x".join(str(item) for item in items)


def _validate_rendered_boolean_metric(value: str) -> str | None:
    return value if value in {"false", "true"} else None


def _validate_rendered_integer_metric(
    validator: ValueValidator, value: str
) -> str | None:
    try:
        parsed = int(value)
    except ValueError:
        return None
    if str(parsed) != value or not _in_range(validator, parsed):
        return None
    return value


def _validate_rendered_number_metric(
    validator: ValueValidator, value: str
) -> str | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    if (
        not math.isfinite(parsed)
        or not _in_range(validator, parsed)
        or f"{parsed:g}" != value
    ):
        return None
    return value


def _validate_rendered_integer_sequence_metric(
    validator: ValueValidator, value: str
) -> str | None:
    try:
        items = [int(item) for item in value.split("x")]
    except ValueError:
        return None
    if (
        not _has_valid_item_count(validator, len(items))
        or "x".join(str(item) for item in items) != value
        or not all(_in_range(validator, item) for item in items)
    ):
        return None
    return value


def default_schema_path() -> Path:
    """Return the runtime schema beside this module, including in frozen builds."""

    return Path(__file__).resolve().with_name(SCHEMA_FILENAME)


def load_structural_event_schema(
    path: Path | None = None,
    *,
    content: str | None = None,
) -> StructuralEventSchema:
    """Load and strictly validate one canonical schema document."""

    raw = _parse_schema_content(_read_schema_content(path, content))
    _validate_schema_root(raw)
    identifier_validators, metric_validators = _load_schema_validators(raw)
    operations = _load_operations(
        raw["operations"], identifier_validators, metric_validators
    )
    performance_variants = _load_performance_variants(
        raw["performance_variants"], metric_validators
    )
    _validate_schema_inventory(operations, performance_variants)
    return StructuralEventSchema(
        version=EXPECTED_SCHEMA_VERSION,
        identifier_validators=MappingProxyType(identifier_validators),
        metric_validators=MappingProxyType(metric_validators),
        operations=MappingProxyType(operations),
        performance_variants=MappingProxyType(performance_variants),
    )


def _read_schema_content(path: Path | None, content: str | None) -> str:
    if content is not None:
        return content
    schema_path = path or default_schema_path()
    try:
        return schema_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise StructuralSchemaError("structural-event schema is unavailable") from exc


def _parse_schema_content(content: str) -> Any:
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise StructuralSchemaError(
            "structural-event schema is not valid JSON"
        ) from exc


def _validate_schema_root(raw: Any) -> None:
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise StructuralSchemaError(
            "structural-event schema has unexpected top-level fields"
        )
    if raw["schema_version"] != EXPECTED_SCHEMA_VERSION:
        raise StructuralSchemaError("unsupported structural-event schema version")


def _load_schema_validators(
    raw: Mapping[str, Any],
) -> tuple[dict[str, ValueValidator], dict[str, ValueValidator]]:
    identifier_validators = _load_validators(
        raw["identifier_validators"], allowed_kinds={"enum", "regex", "regex_family"}
    )
    metric_validators = _load_validators(
        raw["metric_validators"],
        allowed_kinds={"boolean", "integer", "integer_sequence", "number"},
    )
    return identifier_validators, metric_validators


def _validate_schema_inventory(
    operations: Mapping[str, OperationSchema],
    performance_variants: Mapping[str, PerformanceVariantSchema],
) -> None:
    if len(operations) != EXPECTED_OPERATION_COUNT:
        raise StructuralSchemaError("structural-event operation count is incompatible")
    if len(performance_variants) != EXPECTED_PERFORMANCE_VARIANT_COUNT:
        raise StructuralSchemaError("performance-variant count is incompatible")
    for operation_name, operation in operations.items():
        _validate_performance_operation_binding(
            operation_name, operation, performance_variants
        )


def _validate_performance_operation_binding(
    operation_name: str,
    operation: OperationSchema,
    performance_variants: Mapping[str, PerformanceVariantSchema],
) -> None:
    if operation.performance_kind is None:
        return
    has_matching_variant = any(
        variant.kind == operation.performance_kind
        for variant in performance_variants.values()
    )
    if not has_matching_variant or operation_name not in {
        "performance.mark",
        "performance.timer",
    }:
        raise StructuralSchemaError("performance operation binding is incompatible")


def _load_validators(raw: Any, *, allowed_kinds: set[str]) -> dict[str, ValueValidator]:
    if not isinstance(raw, dict) or not raw:
        raise StructuralSchemaError("validator registry must be a non-empty object")
    result: dict[str, ValueValidator] = {}
    for name, definition in raw.items():
        result[name] = _load_validator(name, definition, allowed_kinds)
    return result


def _load_validator(
    name: Any, definition: Any, allowed_kinds: set[str]
) -> ValueValidator:
    if not isinstance(name, str) or not isinstance(definition, dict):
        raise StructuralSchemaError("validator entry is malformed")
    kind = definition.get("kind")
    if not isinstance(kind, str) or kind not in allowed_kinds:
        raise StructuralSchemaError("validator kind is unsupported")
    if set(definition) != _validator_fields(kind):
        raise StructuralSchemaError("validator fields are incompatible")
    pattern, family_pattern = _load_validator_patterns(definition)
    values = _load_validator_values(definition)
    return ValueValidator(
        kind=kind,
        pattern=pattern,
        family_pattern=family_pattern,
        values=values,
        minimum=_load_optional_number(definition, "minimum", "validator minimum"),
        maximum=_load_optional_number(definition, "maximum", "validator maximum"),
        minimum_items=_load_optional_item_count(
            definition, "minimum_items", "validator item minimum"
        ),
        maximum_items=_load_optional_item_count(
            definition, "maximum_items", "validator item maximum"
        ),
    )


def _validator_fields(kind: str) -> set[str]:
    fields = {"kind"}
    if kind in {"regex", "regex_family"}:
        fields.add("pattern")
    if kind == "regex_family":
        fields.add("family_pattern")
    if kind == "enum":
        fields.add("values")
    if kind in {"integer", "number", "integer_sequence"}:
        fields.update({"minimum", "maximum"})
    if kind == "integer_sequence":
        fields.update({"minimum_items", "maximum_items"})
    return fields


def _load_validator_patterns(
    definition: Mapping[str, Any],
) -> tuple[re.Pattern[str] | None, re.Pattern[str] | None]:
    try:
        pattern = re.compile(definition["pattern"]) if "pattern" in definition else None
        family_pattern = (
            re.compile(definition["family_pattern"], re.IGNORECASE)
            if "family_pattern" in definition
            else None
        )
    except (re.error, TypeError) as exc:
        raise StructuralSchemaError("validator pattern is invalid") from exc
    return pattern, family_pattern


def _load_validator_values(definition: Mapping[str, Any]) -> frozenset[str]:
    values_raw = definition.get("values", [])
    if not isinstance(values_raw, list) or any(
        not isinstance(item, str) for item in values_raw
    ):
        raise StructuralSchemaError("validator enum is invalid")
    return frozenset(values_raw)


def _load_optional_number(
    definition: Mapping[str, Any], key: str, error_message: str
) -> float | None:
    value = definition.get(key)
    if value is not None and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        raise StructuralSchemaError(f"{error_message} is invalid")
    return float(value) if value is not None else None


def _load_optional_item_count(
    definition: Mapping[str, Any], key: str, error_message: str
) -> int | None:
    value = definition.get(key)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise StructuralSchemaError(f"{error_message} is invalid")
    return value


def _load_operations(
    raw: Any,
    identifier_validators: Mapping[str, ValueValidator],
    metric_validators: Mapping[str, ValueValidator],
) -> dict[str, OperationSchema]:
    if not isinstance(raw, dict):
        raise StructuralSchemaError("operation registry must be an object")
    result: dict[str, OperationSchema] = {}
    for name, definition in raw.items():
        result[name] = _load_operation(
            name, definition, identifier_validators, metric_validators
        )
    return result


def _load_operation(
    name: Any,
    definition: Any,
    identifier_validators: Mapping[str, ValueValidator],
    metric_validators: Mapping[str, ValueValidator],
) -> OperationSchema:
    if not _is_compatible_operation_definition(name, definition):
        raise StructuralSchemaError("operation entry is malformed")
    categories = _load_operation_categories(definition["categories"])
    performance_kind = _load_operation_performance_kind(definition, categories)
    identifiers = _load_field_map(
        definition["identifiers"], identifier_validators, "identifier"
    )
    metrics = _load_field_map(definition["metrics"], metric_validators, "metric")
    required_identifiers = _load_required(
        definition["required_identifiers"], identifiers, "identifier"
    )
    required_metrics = _load_required(definition["required_metrics"], metrics, "metric")
    return OperationSchema(
        adapter=_load_operation_adapter(definition["adapter"]),
        allow_error=_load_operation_error_policy(definition["allow_error"]),
        categories=frozenset(categories),
        identifiers=MappingProxyType(identifiers),
        required_identifiers=required_identifiers,
        metrics=MappingProxyType(metrics),
        required_metrics=required_metrics,
        performance_kind=performance_kind,
    )


def _is_compatible_operation_definition(name: Any, definition: Any) -> bool:
    if not isinstance(name, str) or not isinstance(definition, dict):
        return False
    expected_fields = (
        _OPERATION_KEYS
        if "performance_kind" in definition
        else _OPERATION_KEYS - {"performance_kind"}
    )
    return set(definition) == expected_fields


def _load_operation_categories(raw: Any) -> list[str | None]:
    if not isinstance(raw, list) or any(
        item is not None and not isinstance(item, str) for item in raw
    ):
        raise StructuralSchemaError("operation categories are invalid")
    return raw


def _load_operation_adapter(value: Any) -> str | None:
    if value not in {None, "architecture", "license"}:
        raise StructuralSchemaError("operation adapter is invalid")
    return value


def _load_operation_error_policy(value: Any) -> bool:
    if not isinstance(value, bool):
        raise StructuralSchemaError("operation error policy is invalid")
    return value


def _load_operation_performance_kind(
    definition: Mapping[str, Any], categories: Sequence[str | None]
) -> str | None:
    performance_kind = definition.get("performance_kind")
    if performance_kind not in {None, "mark", "timer"}:
        raise StructuralSchemaError("performance operation kind is invalid")
    if performance_kind is not None and categories:
        raise StructuralSchemaError("performance categories must come from variants")
    return performance_kind


def _load_performance_variants(
    raw: Any, metric_validators: Mapping[str, ValueValidator]
) -> dict[str, PerformanceVariantSchema]:
    if not isinstance(raw, dict):
        raise StructuralSchemaError("performance registry must be an object")
    result: dict[str, PerformanceVariantSchema] = {}
    for label, definition in raw.items():
        if (
            not isinstance(label, str)
            or not label.startswith("first_paint.")
            or not isinstance(definition, dict)
            or set(definition) != _PERFORMANCE_KEYS
            or definition["kind"] not in {"mark", "timer"}
        ):
            raise StructuralSchemaError("performance variant is malformed")
        metrics = _load_field_map(
            definition["metrics"], metric_validators, "performance metric"
        )
        if definition["kind"] == "timer" and set(metrics) != {"elapsed_ms"}:
            raise StructuralSchemaError("timer variant metrics are incompatible")
        result[label] = PerformanceVariantSchema(
            kind=definition["kind"], metrics=MappingProxyType(metrics)
        )
    return result


def _load_field_map(
    raw: Any, validators: Mapping[str, ValueValidator], label: str
) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise StructuralSchemaError(f"{label} map must be an object")
    result: dict[str, str] = {}
    for key, validator_name in raw.items():
        if (
            not isinstance(key, str)
            or not isinstance(validator_name, str)
            or validator_name not in validators
        ):
            raise StructuralSchemaError(f"{label} map is invalid")
        result[key] = validator_name
    return result


def _load_required(raw: Any, fields: Mapping[str, str], label: str) -> frozenset[str]:
    if (
        not isinstance(raw, list)
        or any(not isinstance(item, str) for item in raw)
        or not set(raw).issubset(fields)
    ):
        raise StructuralSchemaError(f"required {label} fields are invalid")
    return frozenset(raw)
