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
        if (
            validator.kind == "regex_family"
            and (
                validator.family_pattern is None
                or validator.family_pattern.search(value) is None
            )
        ):
            return None
        return value

    def validate_metric(self, validator_name: str, value: Any) -> str | None:
        """Return a normalized typed metric, or ``None`` when outside its range."""

        validator = self.metric_validators.get(validator_name)
        if validator is None:
            return None
        if validator.kind == "boolean":
            return str(value).lower() if isinstance(value, bool) else None
        if validator.kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                return None
            return str(value) if _in_range(validator, value) else None
        if validator.kind == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None
            numeric = float(value)
            if not math.isfinite(numeric) or not _in_range(validator, numeric):
                return None
            return f"{value:g}"
        if validator.kind == "integer_sequence":
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                return None
            items = list(value)
            if not (
                validator.minimum_items is not None
                and validator.maximum_items is not None
                and validator.minimum_items <= len(items) <= validator.maximum_items
            ):
                return None
            if any(
                not isinstance(item, int)
                or isinstance(item, bool)
                or not _in_range(validator, item)
                for item in items
            ):
                return None
            return "x".join(str(item) for item in items)
        return None

    def validate_rendered_metric(
        self, validator_name: str, value: Any
    ) -> str | None:
        """Revalidate one normalized metric at the final output boundary."""

        validator = self.metric_validators.get(validator_name)
        if validator is None or not isinstance(value, str):
            return None
        if validator.kind == "boolean":
            return value if value in {"false", "true"} else None
        if validator.kind == "integer":
            try:
                parsed = int(value)
            except ValueError:
                return None
            if str(parsed) != value or not _in_range(validator, parsed):
                return None
            return value
        if validator.kind == "number":
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
        if validator.kind == "integer_sequence":
            try:
                items = [int(item) for item in value.split("x")]
            except ValueError:
                return None
            if not (
                validator.minimum_items is not None
                and validator.maximum_items is not None
                and validator.minimum_items <= len(items) <= validator.maximum_items
                and "x".join(str(item) for item in items) == value
                and all(_in_range(validator, item) for item in items)
            ):
                return None
            return value
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

        return value if isinstance(value, str) and _ERROR_CLASS.fullmatch(value) else None


def _in_range(validator: ValueValidator, value: float) -> bool:
    return (
        validator.minimum is not None
        and validator.maximum is not None
        and validator.minimum <= value <= validator.maximum
    )


def default_schema_path() -> Path:
    """Return the runtime schema beside this module, including in frozen builds."""

    return Path(__file__).resolve().with_name(SCHEMA_FILENAME)


def load_structural_event_schema(
    path: Path | None = None,
    *,
    content: str | None = None,
) -> StructuralEventSchema:
    """Load and strictly validate one canonical schema document."""

    if content is None:
        schema_path = path or default_schema_path()
        try:
            content = schema_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise StructuralSchemaError("structural-event schema is unavailable") from exc
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise StructuralSchemaError("structural-event schema is not valid JSON") from exc
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise StructuralSchemaError("structural-event schema has unexpected top-level fields")
    if raw["schema_version"] != EXPECTED_SCHEMA_VERSION:
        raise StructuralSchemaError("unsupported structural-event schema version")

    identifier_validators = _load_validators(
        raw["identifier_validators"], allowed_kinds={"enum", "regex", "regex_family"}
    )
    metric_validators = _load_validators(
        raw["metric_validators"],
        allowed_kinds={"boolean", "integer", "integer_sequence", "number"},
    )
    operations = _load_operations(
        raw["operations"], identifier_validators, metric_validators
    )
    performance_variants = _load_performance_variants(
        raw["performance_variants"], metric_validators
    )
    if len(operations) != EXPECTED_OPERATION_COUNT:
        raise StructuralSchemaError("structural-event operation count is incompatible")
    if len(performance_variants) != EXPECTED_PERFORMANCE_VARIANT_COUNT:
        raise StructuralSchemaError("performance-variant count is incompatible")
    for operation_name, operation in operations.items():
        if operation.performance_kind is None:
            continue
        matching = [
            variant
            for variant in performance_variants.values()
            if variant.kind == operation.performance_kind
        ]
        if not matching or operation_name not in {
            "performance.mark",
            "performance.timer",
        }:
            raise StructuralSchemaError("performance operation binding is incompatible")
    return StructuralEventSchema(
        version=EXPECTED_SCHEMA_VERSION,
        identifier_validators=MappingProxyType(identifier_validators),
        metric_validators=MappingProxyType(metric_validators),
        operations=MappingProxyType(operations),
        performance_variants=MappingProxyType(performance_variants),
    )


def _load_validators(
    raw: Any, *, allowed_kinds: set[str]
) -> dict[str, ValueValidator]:
    if not isinstance(raw, dict) or not raw:
        raise StructuralSchemaError("validator registry must be a non-empty object")
    result: dict[str, ValueValidator] = {}
    for name, definition in raw.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            raise StructuralSchemaError("validator entry is malformed")
        kind = definition.get("kind")
        if kind not in allowed_kinds:
            raise StructuralSchemaError("validator kind is unsupported")
        allowed = {"kind"}
        if kind in {"regex", "regex_family"}:
            allowed.add("pattern")
        if kind == "regex_family":
            allowed.add("family_pattern")
        if kind == "enum":
            allowed.add("values")
        if kind in {"integer", "number", "integer_sequence"}:
            allowed.update({"minimum", "maximum"})
        if kind == "integer_sequence":
            allowed.update({"minimum_items", "maximum_items"})
        if set(definition) != allowed:
            raise StructuralSchemaError("validator fields are incompatible")
        try:
            pattern = (
                re.compile(definition["pattern"])
                if "pattern" in definition
                else None
            )
            family_pattern = (
                re.compile(definition["family_pattern"], re.IGNORECASE)
                if "family_pattern" in definition
                else None
            )
        except (re.error, TypeError) as exc:
            raise StructuralSchemaError("validator pattern is invalid") from exc
        values_raw = definition.get("values", [])
        if not isinstance(values_raw, list) or any(
            not isinstance(item, str) for item in values_raw
        ):
            raise StructuralSchemaError("validator enum is invalid")
        minimum = definition.get("minimum")
        maximum = definition.get("maximum")
        if minimum is not None and (
            not isinstance(minimum, (int, float)) or isinstance(minimum, bool)
        ):
            raise StructuralSchemaError("validator minimum is invalid")
        if maximum is not None and (
            not isinstance(maximum, (int, float)) or isinstance(maximum, bool)
        ):
            raise StructuralSchemaError("validator maximum is invalid")
        minimum_items = definition.get("minimum_items")
        maximum_items = definition.get("maximum_items")
        if minimum_items is not None and (
            not isinstance(minimum_items, int) or isinstance(minimum_items, bool)
        ):
            raise StructuralSchemaError("validator item minimum is invalid")
        if maximum_items is not None and (
            not isinstance(maximum_items, int) or isinstance(maximum_items, bool)
        ):
            raise StructuralSchemaError("validator item maximum is invalid")
        result[name] = ValueValidator(
            kind=kind,
            pattern=pattern,
            family_pattern=family_pattern,
            values=frozenset(values_raw),
            minimum=float(minimum) if minimum is not None else None,
            maximum=float(maximum) if maximum is not None else None,
            minimum_items=minimum_items,
            maximum_items=maximum_items,
        )
    return result


def _load_operations(
    raw: Any,
    identifier_validators: Mapping[str, ValueValidator],
    metric_validators: Mapping[str, ValueValidator],
) -> dict[str, OperationSchema]:
    if not isinstance(raw, dict):
        raise StructuralSchemaError("operation registry must be an object")
    result: dict[str, OperationSchema] = {}
    for name, definition in raw.items():
        if (
            not isinstance(name, str)
            or not isinstance(definition, dict)
            or not set(definition).issubset(_OPERATION_KEYS)
            or set(definition) != (
                _OPERATION_KEYS
                if "performance_kind" in definition
                else _OPERATION_KEYS - {"performance_kind"}
            )
        ):
            raise StructuralSchemaError("operation entry is malformed")
        categories_raw = definition["categories"]
        if not isinstance(categories_raw, list) or any(
            item is not None and not isinstance(item, str) for item in categories_raw
        ):
            raise StructuralSchemaError("operation categories are invalid")
        identifiers = _load_field_map(
            definition["identifiers"], identifier_validators, "identifier"
        )
        metrics = _load_field_map(
            definition["metrics"], metric_validators, "metric"
        )
        required_identifiers = _load_required(
            definition["required_identifiers"], identifiers, "identifier"
        )
        required_metrics = _load_required(
            definition["required_metrics"], metrics, "metric"
        )
        adapter = definition["adapter"]
        if adapter not in {None, "architecture", "license"}:
            raise StructuralSchemaError("operation adapter is invalid")
        allow_error = definition["allow_error"]
        if not isinstance(allow_error, bool):
            raise StructuralSchemaError("operation error policy is invalid")
        performance_kind = definition.get("performance_kind")
        if performance_kind not in {None, "mark", "timer"}:
            raise StructuralSchemaError("performance operation kind is invalid")
        if performance_kind is not None and categories_raw:
            raise StructuralSchemaError("performance categories must come from variants")
        result[name] = OperationSchema(
            adapter=adapter,
            allow_error=allow_error,
            categories=frozenset(categories_raw),
            identifiers=MappingProxyType(identifiers),
            required_identifiers=required_identifiers,
            metrics=MappingProxyType(metrics),
            required_metrics=required_metrics,
            performance_kind=performance_kind,
        )
    return result


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


def _load_required(
    raw: Any, fields: Mapping[str, str], label: str
) -> frozenset[str]:
    if (
        not isinstance(raw, list)
        or any(not isinstance(item, str) for item in raw)
        or not set(raw).issubset(fields)
    ):
        raise StructuralSchemaError(f"required {label} fields are invalid")
    return frozenset(raw)
