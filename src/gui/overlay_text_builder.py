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

from typing import Any, Dict, List, Optional

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
    simple: Dict[str, List[str]],
    extras: Dict[str, List[str]],
) -> Dict[str, List[str]]:
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
    out: Dict[str, List[str]] = {}
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
    minimal_fields: List[str],
    detailed_fields: List[str],
    custom_fields: List[str],
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


def get_corner_text(
    parser: DICOMParser,
    tags: List[str],
    privacy_mode: bool,
    total_slices: Optional[int] = None,
    projection_enabled: bool = False,
    projection_start_slice: Optional[int] = None,
    projection_end_slice: Optional[int] = None,
    projection_total_thickness: Optional[float] = None,
    projection_type: Optional[str] = None,
    multiframe_context: Optional[dict[str, Any]] = None,
) -> str:
    """Return formatted overlay text for a single corner.

    Args:
        parser: DICOMParser instance.
        tags: List of DICOM keyword strings to include.
        privacy_mode: When *True*, patient-identifying tags show ``"PRIVACY MODE"``.
        total_slices: Total series slices — used to format ``InstanceNumber`` as
            ``"Slice X/Y"``.
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
    lines: List[str] = []

    # ── Inner helpers ───────────────────────────────────────────────────────

    def format_numeric_value(value: object) -> str:
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:.3f}".rstrip("0").rstrip(".")
        return str(value)

    def get_timing_suffix(context: dict[str, Any]) -> str:
        trigger_time_ms = context.get("trigger_time_ms")
        if trigger_time_ms is not None:
            return f" ({format_numeric_value(trigger_time_ms)} ms)"
        nominal = context.get("nominal_cardiac_trigger_time_ms")
        if nominal is not None:
            return f" ({format_numeric_value(nominal)} ms nominal)"
        return ""

    def format_multiframe_label(context: dict[str, Any]) -> str:
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
            frame_label += get_timing_suffix(context)
        elif frame_type == "diffusion":
            diffusion_b_value = context.get("diffusion_b_value")
            if diffusion_b_value is not None:
                frame_label = f"b={format_numeric_value(diffusion_b_value)}"
            else:
                frame_label = f"Frame {frame_index}/{total_frames}"
        elif frame_type == "spatial":
            frame_label = f"Slice {frame_index}/{total_frames}"
            frame_label += get_timing_suffix(context)
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

    # ── Multi-frame detection ───────────────────────────────────────────────

    dataset = parser.dataset
    frame_index = None
    total_frames = None
    is_multiframe_dataset = False

    if dataset is not None:
        if hasattr(dataset, "_frame_index") and hasattr(dataset, "_original_dataset"):
            is_multiframe_dataset = True
            frame_index = dataset._frame_index  # 0-based
            original_dataset = dataset._original_dataset
            if is_multiframe(original_dataset):
                total_frames = get_frame_count(original_dataset)

    # ── Build lines ─────────────────────────────────────────────────────────

    for tag in tags:
        value = parser.get_tag_by_keyword(tag)
        if value is None or value == "":
            continue

        if isinstance(value, (list, tuple)):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)

        # Privacy masking
        if privacy_mode and tag in get_patient_tag_keywords():
            value_str = "PRIVACY MODE"

        # ── InstanceNumber ──────────────────────────────────────────────
        if tag == "InstanceNumber" and multiframe_context is not None:
            label = format_multiframe_label(multiframe_context)
            lines.append(label if label else f"{tag}: {value_str}")

        elif tag == "InstanceNumber" and total_slices is not None:
            try:
                instance_num = int(value_str)
                slice_display = f"Slice {instance_num}/{total_slices}"

                if (
                    projection_enabled
                    and projection_start_slice is not None
                    and projection_end_slice is not None
                ):
                    start_display = projection_start_slice + 1
                    end_display = projection_end_slice + 1
                    type_map = {"aip": "AIP", "mip": "MIP", "minip": "MinIP"}
                    proj_label = (
                        type_map.get(projection_type.lower(), projection_type.upper())
                        if projection_type
                        else ""
                    )
                    if proj_label:
                        slice_display += f" ({start_display}-{end_display} {proj_label})"
                    else:
                        slice_display += f" ({start_display}-{end_display})"

                if is_multiframe_dataset and total_frames is not None and frame_index is not None:
                    frame_display = frame_index + 1
                    lines.append(f"{slice_display} (Frame {frame_display}/{total_frames})")
                else:
                    lines.append(slice_display)
            except (ValueError, TypeError):
                lines.append(f"{tag}: {value_str}")

        # ── SliceThickness ──────────────────────────────────────────────
        elif (
            tag == "SliceThickness"
            and projection_enabled
            and projection_total_thickness is not None
        ):
            try:
                single_thickness = float(value_str)
                lines.append(
                    f"Slice Thickness: {single_thickness} ({projection_total_thickness})"
                )
            except (ValueError, TypeError):
                lines.append(f"{tag}: {value_str}")

        # ── Timing tags from multi-frame context ────────────────────────
        elif (
            tag == "TriggerTime"
            and multiframe_context is not None
            and multiframe_context.get("trigger_time_ms") is not None
        ):
            lines.append(
                f"TriggerTime: {format_numeric_value(multiframe_context['trigger_time_ms'])} ms"
            )

        elif (
            tag == "NominalCardiacTriggerTime"
            and multiframe_context is not None
            and multiframe_context.get("nominal_cardiac_trigger_time_ms") is not None
        ):
            lines.append(
                f"NominalCardiacTriggerTime: "
                f"{format_numeric_value(multiframe_context['nominal_cardiac_trigger_time_ms'])} ms"
            )

        elif (
            tag == "ContentTime"
            and multiframe_context is not None
            and multiframe_context.get("content_time")
        ):
            lines.append(f"ContentTime: {multiframe_context['content_time']}")

        else:
            lines.append(f"{tag}: {value_str}")

    # ── Append frame info if InstanceNumber is not in this corner ────────
    if (
        is_multiframe_dataset
        and total_frames is not None
        and multiframe_context is None
        and "InstanceNumber" in tags
        and total_slices is None
    ):
        if frame_index is not None:
            frame_display = frame_index + 1
            lines.append(f"Frame: {frame_display}/{total_frames}")

    return "\n".join(lines)
