"""Sealed, schema-validated structural events for fail-closed diagnostics."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final, TypeGuard

from utils.privacy.redaction import REDACTED
from utils.privacy.structural_schema import (
    OperationSchema,
    StructuralEventSchema,
    load_structural_event_schema,
)

_LICENSE_ADAPTER: Final = object()
_ARCHITECTURE_ADAPTER: Final = object()
_ADAPTER_CAPABILITIES: Final = {
    "license": _LICENSE_ADAPTER,
    "architecture": _ARCHITECTURE_ADAPTER,
}
_EVENT_INTEGRITY_KEY: Final = secrets.token_bytes(32)
_FALLBACK_PARTS: Final = (("operation", REDACTED),)


@dataclass(frozen=True, slots=True, init=False)
class StructuralEvent:
    """Immutable validated event; direct public construction is prohibited."""

    _parts: tuple[tuple[str, str], ...] = ()
    _integrity: bytes = b""

    def __new__(cls, *_args: Any, **_kwargs: Any) -> StructuralEvent:
        raise TypeError("StructuralEvent objects must be created by the validated factory")

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("StructuralEvent objects must be created by the validated factory")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        _ = kwargs
        raise TypeError("StructuralEvent cannot be subclassed")

    @property
    def parts(self) -> tuple[tuple[str, str], ...]:
        """Return final-boundary-validated immutable render fields."""

        return _validated_event_parts(self)

    def __str__(self) -> str:
        return render_structural_event(self)


@lru_cache(maxsize=1)
def _schema() -> StructuralEventSchema:
    return load_structural_event_schema()


def _seal_event(parts: tuple[tuple[str, str], ...]) -> StructuralEvent:
    event = object.__new__(StructuralEvent)
    object.__setattr__(event, "_parts", parts)
    object.__setattr__(event, "_integrity", _parts_integrity(parts))
    return event


def _parts_integrity(parts: tuple[tuple[str, str], ...]) -> bytes:
    encoded = json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.blake2b(
        encoded,
        key=_EVENT_INTEGRITY_KEY,
        digest_size=32,
    ).digest()


def _redacted_event(operation: str | None = None) -> StructuralEvent:
    parts = (
        (("operation", operation), ("validation", REDACTED))
        if operation is not None
        else (("operation", REDACTED),)
    )
    return _seal_event(parts)


def _event_with_schema(
    operation: str,
    *,
    category: str | None = None,
    error: BaseException | type[BaseException] | None = None,
    identifiers: Mapping[str, Any] | None = None,
    metrics: Mapping[str, Any] | None = None,
    adapter_capability: object | None = None,
) -> StructuralEvent:
    schema = _schema()
    operation_schema = schema.operations.get(operation)
    if operation_schema is None:
        return _redacted_event()
    if operation_schema.adapter is not None and (
        _ADAPTER_CAPABILITIES[operation_schema.adapter] is not adapter_capability
    ):
        return _redacted_event(operation)

    parts: list[tuple[str, str]] = [("operation", operation)]
    variant_metrics: Mapping[str, str] | None = None
    if operation_schema.performance_kind is not None:
        variant = schema.performance_variants.get(category or "")
        if variant is None or variant.kind != operation_schema.performance_kind:
            parts.append(("category", REDACTED))
            return _seal_event(tuple(parts))
        parts.append(("category", category or REDACTED))
        variant_metrics = variant.metrics
    elif category not in operation_schema.categories:
        if category is not None:
            parts.append(("category", REDACTED))
        parts.append(("validation", REDACTED))
        return _seal_event(tuple(parts))
    elif category is not None:
        parts.append(("category", category))

    _append_error(parts, schema, operation_schema, error)
    _append_identifiers(parts, schema, operation_schema, identifiers or {})
    _append_metrics(
        parts,
        schema,
        operation_schema,
        metrics or {},
        variant_metrics=variant_metrics,
    )
    return _seal_event(tuple(parts))


def _append_error(
    parts: list[tuple[str, str]],
    schema: StructuralEventSchema,
    operation: OperationSchema,
    error: BaseException | type[BaseException] | None,
) -> None:
    if error is None:
        return
    if not operation.allow_error:
        parts.append(("error_class", REDACTED))
        return
    parts.append(("error_class", schema.validate_error_class(error) or REDACTED))


def _append_identifiers(
    parts: list[tuple[str, str]],
    schema: StructuralEventSchema,
    operation: OperationSchema,
    identifiers: Mapping[str, Any],
) -> None:
    supplied = set(identifiers)
    for key in sorted(supplied & set(operation.identifiers)):
        validator = operation.identifiers[key]
        value = schema.validate_identifier(validator, identifiers[key])
        parts.append((key, value or REDACTED))
    for key in sorted(operation.required_identifiers - supplied):
        parts.append((key, REDACTED))
    for _key in sorted(supplied - set(operation.identifiers)):
        parts.append(("identifier", REDACTED))


def _append_metrics(
    parts: list[tuple[str, str]],
    schema: StructuralEventSchema,
    operation: OperationSchema,
    metrics: Mapping[str, Any],
    *,
    variant_metrics: Mapping[str, str] | None,
) -> None:
    allowed = variant_metrics if variant_metrics is not None else operation.metrics
    required = set(allowed) if variant_metrics is not None else operation.required_metrics
    supplied = set(metrics)
    for key in sorted(supplied & set(allowed)):
        value = schema.validate_metric(allowed[key], metrics[key])
        parts.append((key, value or REDACTED))
    for key in sorted(required - supplied):
        parts.append((key, REDACTED))
    for _key in sorted(supplied - set(allowed)):
        parts.append(("metric", REDACTED))


def render_structural_event(event: StructuralEvent, *, sep: str = " ") -> str:
    """Render only an intact event freshly validated against the schema."""

    if type(event) is not StructuralEvent:
        return f"operation={REDACTED}"
    parts = _validated_event_parts(event)
    return sep.join(f"{key}={value}" for key, value in parts)


def _validated_event_parts(event: StructuralEvent) -> tuple[tuple[str, str], ...]:
    try:
        parts: object = object.__getattribute__(event, "_parts")
        integrity: object = object.__getattribute__(event, "_integrity")
    except AttributeError:
        return _FALLBACK_PARTS
    if not _parts_are_well_formed(parts) or not isinstance(integrity, bytes):
        return _FALLBACK_PARTS
    if not hmac.compare_digest(integrity, _parts_integrity(parts)):
        return _FALLBACK_PARTS
    if not _parts_match_schema(parts):
        return _FALLBACK_PARTS
    return parts


def _parts_are_well_formed(
    parts: object,
) -> TypeGuard[tuple[tuple[str, str], ...]]:
    return (
        isinstance(parts, tuple)
        and bool(parts)
        and all(
            isinstance(part, tuple)
            and len(part) == 2
            and isinstance(part[0], str)
            and isinstance(part[1], str)
            for part in parts
        )
    )


def _parts_match_schema(parts: tuple[tuple[str, str], ...]) -> bool:
    if parts == _FALLBACK_PARTS:
        return True
    fields = list(parts)
    if fields[0][0] != "operation":
        return False
    operation_name = fields[0][1]
    operation = _schema().operations.get(operation_name)
    if operation is None:
        return False
    if fields == [("operation", operation_name), ("validation", REDACTED)]:
        return operation.adapter is not None

    position = 1
    category: str | None = None
    if position < len(fields) and fields[position][0] == "category":
        category = fields[position][1]
        position += 1
        if category == REDACTED:
            if operation.performance_kind is not None:
                return position == len(fields)
            return fields[position:] == [("validation", REDACTED)]

    if operation.performance_kind is not None:
        variant = _schema().performance_variants.get(category or "")
        if variant is None or variant.kind != operation.performance_kind:
            return False
        allowed_metrics = variant.metrics
        required_metrics = frozenset(allowed_metrics)
    else:
        if category not in operation.categories:
            return False
        allowed_metrics = operation.metrics
        required_metrics = operation.required_metrics

    if position < len(fields) and fields[position][0] == "error_class":
        error_class = fields[position][1]
        position += 1
        if error_class != REDACTED and (
            not operation.allow_error
            or _schema().validate_rendered_error_class(error_class) is None
        ):
            return False

    identifier_fields: dict[str, str] = {}
    generic_identifier_count = 0
    while position < len(fields):
        key, value = fields[position]
        if key in operation.identifiers:
            if key in identifier_fields or generic_identifier_count:
                return False
            identifier_fields[key] = value
            position += 1
            continue
        if key == "identifier" and value == REDACTED:
            generic_identifier_count += 1
            position += 1
            continue
        break
    if not operation.required_identifiers.issubset(identifier_fields):
        return False
    if not _field_order_is_factory_generated(
        list(identifier_fields.items()), operation.required_identifiers
    ):
        return False
    for key, value in identifier_fields.items():
        if value != REDACTED and (
            _schema().validate_identifier(operation.identifiers[key], value) is None
        ):
            return False

    metric_fields: dict[str, str] = {}
    generic_metric_count = 0
    while position < len(fields):
        key, value = fields[position]
        if key in allowed_metrics:
            if key in metric_fields or generic_metric_count:
                return False
            metric_fields[key] = value
            position += 1
            continue
        if key == "metric" and value == REDACTED:
            generic_metric_count += 1
            position += 1
            continue
        return False
    if not required_metrics.issubset(metric_fields):
        return False
    if not _field_order_is_factory_generated(
        list(metric_fields.items()), required_metrics
    ):
        return False
    return all(
        value == REDACTED
        or _schema().validate_rendered_metric(allowed_metrics[key], value) is not None
        for key, value in metric_fields.items()
    )


def _field_order_is_factory_generated(
    fields: list[tuple[str, str]], required: frozenset[str]
) -> bool:
    """Recognize the factory's sorted supplied-fields then missing-fields order."""

    for split in range(len(fields) + 1):
        supplied = fields[:split]
        missing = fields[split:]
        supplied_keys = [key for key, _value in supplied]
        missing_keys = [key for key, _value in missing]
        if (
            supplied_keys == sorted(supplied_keys)
            and missing_keys == sorted(missing_keys)
            and all(value == REDACTED for _key, value in missing)
            and set(missing_keys) == set(required) - set(supplied_keys)
        ):
            return True
    return False


def structural_event(
    operation: str,
    *,
    category: str | None = None,
    error: BaseException | type[BaseException] | None = None,
    identifiers: Mapping[str, Any] | None = None,
    metrics: Mapping[str, Any] | None = None,
) -> StructuralEvent:
    """Create a sealed event; unregistered or adapter-only operations fail closed."""

    return _event_with_schema(
        operation,
        category=category,
        error=error,
        identifiers=identifiers,
        metrics=metrics,
    )


def _license_event(  # pyright: ignore[reportUnusedFunction]
    operation: str,
    *,
    category: str,
    package: Any,
    version: Any,
    license_name: Any,
    source: Any,
) -> StructuralEvent:
    return _event_with_schema(
        operation,
        category=category,
        identifiers={
            "package": package,
            "version": version,
            "license": license_name,
            "source": source,
        },
        adapter_capability=_LICENSE_ADAPTER,
    )


def _architecture_event(  # pyright: ignore[reportUnusedFunction]
    operation: str,
    *,
    category: str | None = None,
    module: Any = None,
    repository_path: Any = None,
    line: Any = None,
    count: Any = None,
) -> StructuralEvent:
    identifiers = {}
    metrics = {}
    if module is not None:
        identifiers["module"] = module
    if repository_path is not None:
        identifiers["repository_path"] = repository_path
    if line is not None:
        metrics["line"] = line
    if count is not None:
        metrics["count"] = count
    return _event_with_schema(
        operation,
        category=category,
        identifiers=identifiers,
        metrics=metrics,
        adapter_capability=_ARCHITECTURE_ADAPTER,
    )


def log_structural_event(
    logger: logging.Logger,
    level: int,
    operation: str,
    **kwargs: Any,
) -> None:
    """Emit a sealed event through standard logging without free-text payloads."""

    logger.log(level, structural_event(operation, **kwargs))
