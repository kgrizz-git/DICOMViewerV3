"""Exact contract tests for the versioned structural-event schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.privacy.structural_adapters import (
    print_architecture_baseline_written,
    print_architecture_violation,
    print_license_accepted,
    print_license_obligation,
    print_license_violation,
)
from utils.privacy.structural_events import (
    StructuralEvent,
    render_structural_event,
    structural_event,
)
from utils.privacy.structural_schema import (
    EXPECTED_OPERATION_COUNT,
    EXPECTED_PERFORMANCE_VARIANT_COUNT,
    StructuralSchemaError,
    default_schema_path,
    load_structural_event_schema,
)


def test_canonical_schema_has_exact_versioned_inventory() -> None:
    schema = load_structural_event_schema()

    assert schema.version == 1
    assert len(schema.operations) == EXPECTED_OPERATION_COUNT == 19
    assert len(schema.performance_variants) == EXPECTED_PERFORMANCE_VARIANT_COUNT == 55
    assert sum(item.kind == "mark" for item in schema.performance_variants.values()) == 19
    assert sum(item.kind == "timer" for item in schema.performance_variants.values()) == 36


def test_pyinstaller_spec_bundles_canonical_schema() -> None:
    spec = (Path(__file__).resolve().parents[1] / "DICOMViewerV3.spec").read_text(
        encoding="utf-8"
    )

    assert "src/utils/privacy/structural_event_schema_v1.json" in spec
    assert "'utils/privacy'" in spec


def test_loader_rejects_incompatible_operation_and_variant_counts() -> None:
    raw = json.loads(default_schema_path().read_text(encoding="utf-8"))
    raw["operations"].pop("decoder.hash_mismatch")
    with pytest.raises(StructuralSchemaError, match="operation count"):
        load_structural_event_schema(content=json.dumps(raw))

    raw = json.loads(default_schema_path().read_text(encoding="utf-8"))
    raw["performance_variants"].pop("first_paint.event_loop_returned")
    with pytest.raises(StructuralSchemaError, match="variant count"):
        load_structural_event_schema(content=json.dumps(raw))


def test_unknown_and_valid_namespace_marker_operations_fail_closed() -> None:
    marker = "SCHEMACANARY71A9"
    unknown = render_structural_event(structural_event("unknown.operation"))
    approved_namespace = render_structural_event(
        structural_event(f"application.{marker}", identifiers={"package": marker})
    )

    assert marker not in unknown + approved_namespace
    assert unknown == "operation=[REDACTED]"
    assert approved_namespace == "operation=[REDACTED]"


def test_direct_construction_is_sealed() -> None:
    with pytest.raises(TypeError, match="validated factory"):
        StructuralEvent(operation="application.startup")  # type: ignore[call-arg]

    fabricated = object.__new__(StructuralEvent)
    assert render_structural_event(fabricated) == "operation=[REDACTED]"


def test_adapter_only_operation_fails_closed_through_generic_factory() -> None:
    marker = "SCHEMACANARY71A9"
    output = render_structural_event(
        structural_event(
            "license.obligation",
            category="OBLIGATION",
            identifiers={
                "package": marker,
                "version": "1.0",
                "license": "MIT",
                "source": "classifier",
            },
        )
    )

    assert marker not in output
    assert output == "operation=license.obligation validation=[REDACTED]"


def test_valid_operation_namespace_identifier_and_performance_markers_are_absent() -> None:
    marker = "SCHEMACANARY71A9"
    outputs = [
        render_structural_event(
            structural_event(
                "decoder.package",
                identifiers={"package": "pydicom", "version": marker},
            )
        ),
        render_structural_event(
            structural_event(
                "fusion.input",
                category=marker,
            )
        ),
        render_structural_event(
            structural_event(
                "performance.mark",
                category=f"first_paint.{marker}",
            )
        ),
        render_structural_event(
            structural_event(
                "performance.mark",
                category="first_paint.display_slice.returned",
                metrics={"image_item_present": True, marker: marker},
            )
        ),
    ]

    assert all(marker not in output for output in outputs)
    assert all("[REDACTED]" in output for output in outputs)


def test_event_is_immutable_from_caller_mapping_mutation() -> None:
    metrics: dict[str, object] = {
        "instance_count": 3,
        "series_count": 2,
    }
    event = structural_event("fusion.load_summary", metrics=metrics)
    metrics["instance_count"] = "SCHEMACANARY71A9"

    output = render_structural_event(event)
    assert "instance_count=3" in output
    assert "SCHEMACANARY71A9" not in output


def test_all_19_registered_operations_have_positive_runtime_coverage(capsys) -> None:
    events = [
        structural_event("application.startup", error=RuntimeError()),
        structural_event("application.unhandled", error=RuntimeError),
        structural_event("decoder.copy_failed", error=OSError()),
        structural_event("decoder.hash_mismatch"),
        structural_event("decoder.new_failure"),
        structural_event(
            "decoder.package",
            identifiers={"package": "pydicom", "version": "3.0.1"},
        ),
        structural_event(
            "decoder.syntax_summary",
            category="at-risk",
            identifiers={"format": "JPEG Baseline 8-bit"},
            metrics={
                "at_risk": True,
                "decoded_count": 3,
                "failed_count": 1,
                "total_count": 4,
            },
        ),
        structural_event(
            "fusion.group_summary",
            metrics={"duration_ms": 1.5, "group_count": 2},
        ),
        structural_event("fusion.input", category="protected"),
        structural_event(
            "fusion.load_summary",
            metrics={"instance_count": 3, "series_count": 2},
        ),
        structural_event(
            "fusion.series_summary",
            category="ct",
            metrics={
                "columns": 512,
                "pixel_spacing_mm": 0.75,
                "rows": 512,
                "slice_count": 24,
            },
        ),
        structural_event(
            "performance.mark",
            category="first_paint.event_loop_returned",
        ),
        structural_event(
            "performance.startup",
            metrics={"app_init_ms": 2.0, "import_ms": 1.0, "total_ms": 3.0},
        ),
        structural_event(
            "performance.timer",
            category="first_paint.display_slice",
            metrics={"elapsed_ms": 1.25},
        ),
    ]
    rendered = [render_structural_event(event) for event in events]
    assert all("[REDACTED]" not in output for output in rendered)

    print_architecture_baseline_written(count=0)
    print_architecture_violation(
        "core-gui",
        module="gui.main_window",
        repository_path="src/core/example.py",
        line=1,
    )
    print_license_obligation(
        package="example-obligation",
        version="1.0.0",
        license_name="MPL-2.0",
        source="expression",
    )
    print_license_accepted(
        "FORBIDDEN",
        package="example-accepted",
        version="1.0.0",
        license_name="GPL-3.0",
        source="classifier",
    )
    print_license_violation(
        "UNKNOWN",
        package="example-unknown",
        version="1.0.0",
        license_name="UNKNOWN",
        source="none",
    )
    adapter_output = capsys.readouterr().out
    for operation in (
        "architecture.baseline_written",
        "architecture.violation",
        "license.accepted",
        "license.obligation",
        "license.violation",
    ):
        assert f"operation={operation}" in adapter_output
    assert "[REDACTED]" not in adapter_output

    covered = {
        output.split(" ", maxsplit=1)[0].removeprefix("operation=")
        for output in rendered
    }
    covered.update(
        {
            "architecture.baseline_written",
            "architecture.violation",
            "license.accepted",
            "license.obligation",
            "license.violation",
        }
    )
    assert covered == set(load_structural_event_schema().operations)


def _runtime_metric_value(validator_name: str) -> object:
    return {
        "boolean": True,
        "count": 2,
        "duration_ms": 1.5,
        "index": 0,
        "megabytes": 2.5,
    }[validator_name]


def test_all_55_performance_variants_render_without_redaction() -> None:
    schema = load_structural_event_schema()
    for label, variant in schema.performance_variants.items():
        metrics = {
            key: _runtime_metric_value(validator)
            for key, validator in variant.metrics.items()
        }
        operation = "performance.mark" if variant.kind == "mark" else "performance.timer"
        output = render_structural_event(
            structural_event(operation, category=label, metrics=metrics)
        )
        assert "[REDACTED]" not in output
        assert f"category={label}" in output


@pytest.mark.parametrize("value", [-1, 9007199254740992, True, "7"])
def test_count_validator_rejects_out_of_domain_values(value: object) -> None:
    output = render_structural_event(
        structural_event(
            "fusion.load_summary",
            metrics={"instance_count": value, "series_count": 1},
        )
    )

    assert "instance_count=[REDACTED]" in output
