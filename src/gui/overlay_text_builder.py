"""
Overlay Text Builder

Module-level text-composition functions extracted from OverlayManager.
These are pure data-transformation functions with no Qt widget dependencies.

Inputs:
    - DICOMParser instance with a dataset set
    - Overlay mode, field lists, privacy flag (passed as explicit arguments)

Outputs:
    - Formatted strings for display in image overlay corners
"""

from typing import Any

from core.dicom_parser import DICOMParser
from core.multiframe_handler import get_frame_count, is_multiframe
from utils.dicom_utils import get_patient_tag_keywords

# Keys used for per-corner overlay tag maps in config and UI.
OVERLAY_CORNER_KEYS: tuple[str, ...] = (
    "upper_left",
    "upper_right",
    "lower_left",
    "lower_right",
)


def merge_simple_and_detailed_extra_corner_tags(
    simple: dict[str, list[str]],
    extras: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Build effective corner tag lists for Detailed overlay mode.

    Order: all Simple tags first, then any Extra tags not already in Simple
    (extras keep their relative order).

    Args:
        simple: Per-corner tag keyword lists (minimal / default layout).
        extras: Additional tags per corner shown only in detailed mode.

    Returns:
        New dict with the same four corner keys.
    """
    out: dict[str, list[str]] = {}
    for key in OVERLAY_CORNER_KEYS:
        base = [str(t) for t in (simple.get(key) or [])]
        seen = set(base)
        merged = list(base)
        for tag in extras.get(key) or []:
            s = str(tag)
            if s not in seen:
                merged.append(s)
                seen.add(s)
        out[key] = merged
    return out


def get_overlay_text(
    parser: DICOMParser,
    mode: str,
    minimal_fields: list[str],
    detailed_fields: list[str],
    custom_fields: list[str],
) -> str:
    """Return overlay text for *parser*'s dataset, honouring *mode*.

    Args:
        parser: DICOMParser with a dataset loaded.
        mode: One of ``"minimal"``, ``"detailed"``, or ``"hidden"``.
        minimal_fields: Field keyword list used in minimal mode.
        detailed_fields: Field keyword list used in detailed mode.
        custom_fields: Field keyword list used for any other mode value.

    Returns:
        Newline-joined ``"field: value"`` lines, or ``""`` when hidden.
    """
    if mode == "hidden":
        return ""

    if mode == "minimal":
        fields = minimal_fields
    elif mode == "detailed":
        fields = detailed_fields
    else:
        fields = custom_fields

    lines = []
    for field in fields:
        value = parser.get_tag_by_keyword(field)
        if value is not None and value != "":
            if isinstance(value, (list, tuple)):
                value_str = ", ".join(str(v) for v in value)
            else:
                value_str = str(value)
            lines.append(f"{field}: {value_str}")

    return "\n".join(lines)


def get_modality(parser: DICOMParser) -> str:
    """Return the Modality string from *parser*'s dataset, or ``"default"``."""
    modality = parser.get_tag_by_keyword("Modality")
    if modality is None or modality == "":
        return "default"
    return str(modality).strip()


def format_overlay_numeric_value(value: object) -> str:
    """Format floats without trailing zeros; pass other values through ``str``."""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def multiframe_timing_suffix(context: dict[str, Any]) -> str:
    """Parenthetical timing suffix for cardiac/spatial multiframe labels."""
    trigger_time_ms = context.get("trigger_time_ms")
    if trigger_time_ms is not None:
        return f" ({format_overlay_numeric_value(trigger_time_ms)} ms)"
    nominal = context.get("nominal_cardiac_trigger_time_ms")
    if nominal is not None:
        return f" ({format_overlay_numeric_value(nominal)} ms nominal)"
    return ""


def format_multiframe_corner_label(context: dict[str, Any]) -> str:
    """Build InstanceNumber replacement text from multiframe context."""
    instance_index = context.get("instance_index")
    total_instances = context.get("total_instances")
    frame_index = context.get("frame_index")
    total_frames = context.get("total_frames")
    if frame_index is None or total_frames is None:
        return ""

    frame_type = str(context.get("frame_type", "unknown"))
    if frame_type == "temporal":
        frame_label = f"Frame {frame_index}/{total_frames}"
    elif frame_type == "cardiac":
        frame_label = f"Phase {frame_index}/{total_frames}"
        frame_label += multiframe_timing_suffix(context)
    elif frame_type == "diffusion":
        diffusion_b_value = context.get("diffusion_b_value")
        if diffusion_b_value is not None:
            frame_label = f"b={format_overlay_numeric_value(diffusion_b_value)}"
        else:
            frame_label = f"Frame {frame_index}/{total_frames}"
    elif frame_type == "spatial":
        frame_label = f"Slice {frame_index}/{total_frames}"
        frame_label += multiframe_timing_suffix(context)
    else:
        frame_label = f"Frame {frame_index}/{total_frames}"

    if (
        instance_index is not None
        and total_instances is not None
        and isinstance(total_instances, (int, float))
        and int(total_instances) > 1
    ):
        return f"Instance {instance_index}/{total_instances} · {frame_label}"
    return frame_label


def detect_multiframe_overlay_state(
    parser: DICOMParser,
) -> tuple[bool, int | None, int | None]:
    """
    Detect FrameDatasetWrapper-style multi-frame state on *parser*.

    Returns:
        ``(is_multiframe_dataset, frame_index_0based, total_frames)``.
    """
    dataset = parser.dataset
    if dataset is None:
        return False, None, None
    if not (hasattr(dataset, "_frame_index") and hasattr(dataset, "_original_dataset")):
        return False, None, None
    frame_index = dataset._frame_index  # 0-based
    total_frames = None
    original_dataset = dataset._original_dataset
    if is_multiframe(original_dataset):
        total_frames = get_frame_count(original_dataset)
    return True, frame_index, total_frames


def _projection_range_suffix(
    projection_enabled: bool,
    projection_start_slice: int | None,
    projection_end_slice: int | None,
    projection_type: str | None,
) -> str:
    """Suffix like `` (1-5 MIP)`` when combine-slices projection is active."""
    if not (
        projection_enabled
        and projection_start_slice is not None
        and projection_end_slice is not None
    ):
        return ""
    start_display = projection_start_slice + 1
    end_display = projection_end_slice + 1
    type_map = {"aip": "AIP", "mip": "MIP", "minip": "MinIP"}
    proj_label = (
        type_map.get(projection_type.lower(), projection_type.upper())
        if projection_type
        else ""
    )
    if proj_label:
        return f" ({start_display}-{end_display} {proj_label})"
    return f" ({start_display}-{end_display})"


def format_instance_number_slice_display(
    value_str: str,
    *,
    total_slices: int,
    stack_position: int | None,
    projection_enabled: bool,
    projection_start_slice: int | None,
    projection_end_slice: int | None,
    projection_type: str | None,
    is_multiframe_dataset: bool,
    frame_index: int | None,
    total_frames: int | None,
) -> str | None:
    """
    Format InstanceNumber as Slice X/Y (plus projection/frame suffixes).

    Returns ``None`` when *value_str* is not an int (caller falls back to tag:value).
    """
    try:
        instance_num = int(value_str)
    except (ValueError, TypeError):
        return None

    if stack_position is not None:
        # Numerator is the loaded-stack position so the fraction is always
        # coherent; show DICOM InstanceNumber only when it differs.
        slice_display = f"Slice {stack_position}/{total_slices}"
        if instance_num != stack_position:
            slice_display += f" (Instance {instance_num})"
    elif instance_num > total_slices:
        # Never emit an impossible fraction like "Slice 104/11".
        slice_display = f"Slice {instance_num}"
    else:
        slice_display = f"Slice {instance_num}/{total_slices}"

    slice_display += _projection_range_suffix(
        projection_enabled,
        projection_start_slice,
        projection_end_slice,
        projection_type,
    )

    if is_multiframe_dataset and total_frames is not None and frame_index is not None:
        frame_display = frame_index + 1
        return f"{slice_display} (Frame {frame_display}/{total_frames})"
    return slice_display


def try_format_instance_number_line(
    tag: str,
    value_str: str,
    *,
    total_slices: int | None,
    projection_enabled: bool,
    projection_start_slice: int | None,
    projection_end_slice: int | None,
    projection_type: str | None,
    multiframe_context: dict[str, Any] | None,
    stack_position: int | None,
    is_multiframe_dataset: bool,
    frame_index: int | None,
    total_frames: int | None,
) -> str | None:
    """Format InstanceNumber special cases, or ``None`` when *tag* is not that keyword."""
    if tag != "InstanceNumber":
        return None
    if multiframe_context is not None:
        label = format_multiframe_corner_label(multiframe_context)
        return label if label else f"{tag}: {value_str}"
    if total_slices is None:
        return None
    formatted = format_instance_number_slice_display(
        value_str,
        total_slices=total_slices,
        stack_position=stack_position,
        projection_enabled=projection_enabled,
        projection_start_slice=projection_start_slice,
        projection_end_slice=projection_end_slice,
        projection_type=projection_type,
        is_multiframe_dataset=is_multiframe_dataset,
        frame_index=frame_index,
        total_frames=total_frames,
    )
    return formatted if formatted is not None else f"{tag}: {value_str}"


def try_format_slice_thickness_line(
    tag: str,
    value_str: str,
    *,
    projection_enabled: bool,
    projection_total_thickness: float | None,
) -> str | None:
    """Format projected SliceThickness, or ``None`` when not applicable."""
    if not (
        tag == "SliceThickness"
        and projection_enabled
        and projection_total_thickness is not None
    ):
        return None
    try:
        single_thickness = float(value_str)
        return f"Slice Thickness: {single_thickness} ({projection_total_thickness})"
    except (ValueError, TypeError):
        return f"{tag}: {value_str}"


def try_format_multiframe_timing_line(
    tag: str,
    multiframe_context: dict[str, Any] | None,
) -> str | None:
    """Format TriggerTime / NominalCardiacTriggerTime / ContentTime from context."""
    if multiframe_context is None:
        return None
    if tag == "TriggerTime" and multiframe_context.get("trigger_time_ms") is not None:
        return (
            f"TriggerTime: {format_overlay_numeric_value(multiframe_context['trigger_time_ms'])} ms"
        )
    if (
        tag == "NominalCardiacTriggerTime"
        and multiframe_context.get("nominal_cardiac_trigger_time_ms") is not None
    ):
        return (
            "NominalCardiacTriggerTime: "
            f"{format_overlay_numeric_value(multiframe_context['nominal_cardiac_trigger_time_ms'])} ms"
        )
    if tag == "ContentTime" and multiframe_context.get("content_time"):
        return f"ContentTime: {multiframe_context['content_time']}"
    return None


def format_corner_tag_line(
    tag: str,
    value_str: str,
    *,
    total_slices: int | None,
    projection_enabled: bool,
    projection_start_slice: int | None,
    projection_end_slice: int | None,
    projection_total_thickness: float | None,
    projection_type: str | None,
    multiframe_context: dict[str, Any] | None,
    stack_position: int | None,
    is_multiframe_dataset: bool,
    frame_index: int | None,
    total_frames: int | None,
) -> str:
    """Return one overlay line for a non-empty tag value."""
    instance_line = try_format_instance_number_line(
        tag,
        value_str,
        total_slices=total_slices,
        projection_enabled=projection_enabled,
        projection_start_slice=projection_start_slice,
        projection_end_slice=projection_end_slice,
        projection_type=projection_type,
        multiframe_context=multiframe_context,
        stack_position=stack_position,
        is_multiframe_dataset=is_multiframe_dataset,
        frame_index=frame_index,
        total_frames=total_frames,
    )
    if instance_line is not None:
        return instance_line

    thickness_line = try_format_slice_thickness_line(
        tag,
        value_str,
        projection_enabled=projection_enabled,
        projection_total_thickness=projection_total_thickness,
    )
    if thickness_line is not None:
        return thickness_line

    timing_line = try_format_multiframe_timing_line(tag, multiframe_context)
    if timing_line is not None:
        return timing_line

    return f"{tag}: {value_str}"


def trailing_multiframe_frame_line(
    *,
    tags: list[str],
    is_multiframe_dataset: bool,
    total_frames: int | None,
    multiframe_context: dict[str, Any] | None,
    total_slices: int | None,
    frame_index: int | None,
) -> str | None:
    """Optional trailing ``Frame: x/y`` when InstanceNumber is present without slice total."""
    if not (
        is_multiframe_dataset
        and total_frames is not None
        and multiframe_context is None
        and "InstanceNumber" in tags
        and total_slices is None
        and frame_index is not None
    ):
        return None
    frame_display = frame_index + 1
    return f"Frame: {frame_display}/{total_frames}"


def get_corner_text(
    parser: DICOMParser,
    tags: list[str],
    privacy_mode: bool,
    total_slices: int | None = None,
    projection_enabled: bool = False,
    projection_start_slice: int | None = None,
    projection_end_slice: int | None = None,
    projection_total_thickness: float | None = None,
    projection_type: str | None = None,
    multiframe_context: dict[str, Any] | None = None,
    stack_position: int | None = None,
) -> str:
    """Return formatted overlay text for a single corner.

    Args:
        parser: DICOMParser instance.
        tags: List of DICOM keyword strings to include.
        privacy_mode: When *True*, patient-identifying tags show ``"PRIVACY MODE"``.
        total_slices: Total series slices — used as the denominator when
            formatting ``InstanceNumber`` as ``"Slice X/Y"``.
        stack_position: 1-based position of the current slice in the loaded,
            organized series list. When provided, this (not the raw DICOM
            ``InstanceNumber``) is used as the ``Slice X/Y`` numerator so the
            fraction is always coherent; the DICOM ``InstanceNumber`` is shown
            as a ``(Instance N)`` suffix only when it differs from the stack
            position. Prevents impossible labels like ``"Slice 104/11"``.
        projection_enabled: Whether Combine-Slices projection is active.
        projection_start_slice: Start slice index (0-based) of the projection range.
        projection_end_slice: End slice index (0-based) of the projection range.
        projection_total_thickness: Total thickness (mm) of combined slices.
        projection_type: One of ``"aip"``, ``"mip"``, or ``"minip"``.
        multiframe_context: Frame-level context dict supplied by the multi-frame
            handler; keys include ``"frame_index"``, ``"total_frames"``,
            ``"frame_type"``, ``"trigger_time_ms"``, etc.

    Returns:
        Newline-joined text lines ready for display.
    """
    lines: list[str] = []
    is_multiframe_dataset, frame_index, total_frames = detect_multiframe_overlay_state(parser)

    for tag in tags:
        value = parser.get_tag_by_keyword(tag)
        if value is None or value == "":
            continue

        if isinstance(value, (list, tuple)):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)

        if privacy_mode and tag in get_patient_tag_keywords():
            value_str = "PRIVACY MODE"

        lines.append(
            format_corner_tag_line(
                tag,
                value_str,
                total_slices=total_slices,
                projection_enabled=projection_enabled,
                projection_start_slice=projection_start_slice,
                projection_end_slice=projection_end_slice,
                projection_total_thickness=projection_total_thickness,
                projection_type=projection_type,
                multiframe_context=multiframe_context,
                stack_position=stack_position,
                is_multiframe_dataset=is_multiframe_dataset,
                frame_index=frame_index,
                total_frames=total_frames,
            )
        )

    trailing = trailing_multiframe_frame_line(
        tags=tags,
        is_multiframe_dataset=is_multiframe_dataset,
        total_frames=total_frames,
        multiframe_context=multiframe_context,
        total_slices=total_slices,
        frame_index=frame_index,
    )
    if trailing is not None:
        lines.append(trailing)

    return "\n".join(lines)
