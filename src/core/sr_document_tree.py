"""
SR document tree — generic walk of DICOM Structured Report ``ContentSequence``.

**Purpose:** Build an in-memory tree of SR content items (Value Type, Concept Name, Relationship,
measured values, nested children) for full-fidelity display—not a template-specific dose summary.

**Inputs:** ``pydicom.dataset.Dataset`` with optional ``ContentSequence`` (0040,A730).

**Outputs:** :class:`SrDocumentTree` with root :class:`SrContentNode` items and optional warnings.

**Requirements:** ``pydicom`` only. Recursion is **bounded** by ``max_depth`` and ``max_nodes``
(defaults align with ``rdsr_dose_sr`` caps).

See ``dev-docs/plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`` §6 Phase 1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final, cast

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence

_DEFAULT_MAX_DEPTH: Final[int] = 48
_DEFAULT_MAX_NODES: Final[int] = 12000


def _concept_tuple(item: Dataset) -> tuple[str | None, str | None]:
    cseq = getattr(item, "ConceptNameCodeSequence", None)
    if not cseq:
        return (None, None)
    seq = cast(DicomSequence, cseq)
    if len(seq) == 0:
        return (None, None)
    c0 = seq[0]
    cv = getattr(c0, "CodeValue", None)
    scheme = getattr(c0, "CodingSchemeDesignator", None)
    return (str(cv) if cv is not None else None, str(scheme) if scheme is not None else None)


def _concept_display(item: Dataset) -> str:
    cv, scheme = _concept_tuple(item)
    cseq = getattr(item, "ConceptNameCodeSequence", None)
    if cseq and len(cast(DicomSequence, cseq)) > 0:
        c0 = cast(DicomSequence, cseq)[0]
        meaning = getattr(c0, "CodeMeaning", None)
        if meaning:
            base = str(meaning).strip()
            if cv and scheme:
                return f"{base} ({cv}, {scheme})"
            return base
    if cv and scheme:
        return f"{cv}, {scheme}"
    if cv or scheme:
        return f"{cv or '?'}, {scheme or '?'}"
    return "(no concept name)"


def _relationship_str(item: Dataset) -> str:
    r = getattr(item, "RelationshipType", None)
    return str(r).strip() if r is not None else ""


def _value_type_str(item: Dataset) -> str:
    vt = getattr(item, "ValueType", None)
    return str(vt).strip() if vt is not None else ""


def _format_num(item: Dataset) -> str:
    mseq = getattr(item, "MeasuredValueSequence", None)
    if not mseq or len(cast(DicomSequence, mseq)) == 0:
        return ""
    mv = cast(DicomSequence, mseq)[0]
    parts: list[str] = []
    nv = getattr(mv, "NumericValue", None)
    if nv is not None:
        parts.append(str(nv))
    fv = getattr(mv, "FloatingPointValue", None)
    if fv is not None:
        parts.append(str(fv))
    uc = getattr(mv, "MeasurementUnitsCodeSequence", None)
    if uc and len(cast(DicomSequence, uc)) > 0:
        u0 = cast(DicomSequence, uc)[0]
        um = getattr(u0, "CodeMeaning", None) or getattr(u0, "CodeValue", None)
        if um:
            parts.append(str(um))
    return " ".join(parts).strip()


def _format_code(item: Dataset) -> str:
    cseq = getattr(item, "ConceptCodeSequence", None)
    if not cseq and hasattr(item, "ReferencedContentItemIdentifier"):
        # Some templates use different sequences; try first child CODE pattern
        pass
    if not cseq or len(cast(DicomSequence, cseq)) == 0:
        return ""
    c0 = cast(DicomSequence, cseq)[0]
    meaning = getattr(c0, "CodeMeaning", None)
    cv = getattr(c0, "CodeValue", None)
    scheme = getattr(c0, "CodingSchemeDesignator", None)
    bits = [str(x) for x in (meaning, cv, scheme) if x]
    return " — ".join(bits) if bits else ""


def _format_text(item: Dataset) -> str:
    tv = getattr(item, "TextValue", None)
    if tv is not None:
        return str(tv).strip()
    return ""


def _format_pname(item: Dataset) -> str:
    pn = getattr(item, "PersonName", None)
    if pn is not None:
        return str(pn).strip()
    return ""


def _format_datetime_like(item: Dataset) -> str:
    for attr in ("DateTime", "TemporalRangeType", "TimeRange", "Date", "Time"):
        v = getattr(item, attr, None)
        if v is not None:
            return f"{attr}={v}"
    return ""


def _format_uid_reference(item: Dataset) -> str:
    parts: list[str] = []
    for label, attr in (
        ("Study", "ReferencedStudyInstanceUID"),
        ("Series", "ReferencedSeriesInstanceUID"),
        ("SOP", "ReferencedSOPInstanceUID"),
    ):
        u = getattr(item, attr, None)
        if u:
            parts.append(f"{label}={u}")
    return "; ".join(parts)


def _format_image_ref(item: Dataset) -> str:
    return _format_uid_reference(item)


def _format_composite_ref(item: Dataset) -> str:
    return _format_uid_reference(item)


def _format_waveform(item: Dataset) -> str:
    nch = getattr(item, "NumberOfChannels", None)
    ns = getattr(item, "NumberOfWaveformSamples", None)
    bits = []
    if nch is not None:
        bits.append(f"channels={nch}")
    if ns is not None:
        bits.append(f"samples={ns}")
    ref = _format_uid_reference(item)
    if ref:
        bits.append(ref)
    return ", ".join(bits) if bits else "(waveform)"


def _format_sc_coord(item: Dataset) -> str:
    g = getattr(item, "GraphicData", None)
    n = 0
    if g is not None:
        if hasattr(g, "__len__"):
            n = len(g)  # type: ignore[arg-type]
    gt = getattr(item, "GraphicType", None)
    return f"type={gt or '?'}, values={n}"


def _format_container(item: Dataset) -> str:
    cflag = getattr(item, "ContinuityOfContent", None)
    tmpl = getattr(item, "ContentTemplateSequence", None)
    bits: list[str] = []
    if cflag:
        bits.append(f"continuity={cflag}")
    if tmpl and len(cast(DicomSequence, tmpl)) > 0:
        t0 = cast(DicomSequence, tmpl)[0]
        tid = getattr(t0, "MappingResource", None)
        tvr = getattr(t0, "TemplateIdentifier", None)
        if tid or tvr:
            bits.append(f"template={tid or ''}:{tvr or ''}")
    return "; ".join(bits) if bits else ""


def _value_and_reference(item: Dataset) -> tuple[str, str]:
    vt = _value_type_str(item).upper()
    if vt == "CONTAINER":
        return _format_container(item), ""
    if vt == "TEXT":
        return _format_text(item), ""
    if vt == "NUM":
        return _format_num(item), ""
    if vt == "CODE":
        return _format_code(item), ""
    if vt == "PNAME":
        return _format_pname(item), ""
    if vt in ("DATETIME", "DATE", "TIME"):
        return _format_datetime_like(item), ""
    if vt == "UIDREF":
        u = getattr(item, "UID", None)
        return (str(u) if u else "", "")
    if vt == "IMAGE":
        return "", _format_image_ref(item)
    if vt == "COMPOSITE":
        return "", _format_composite_ref(item)
    if vt == "WAVEFORM":
        return _format_waveform(item), ""
    if vt in ("SCOORD", "SCOORD3D"):
        return _format_sc_coord(item), ""
    if vt == "TCOORD":
        return "(temporal coordinates)", ""
    # Fallback: show a few common attributes
    for attr in (
        "NumericValue",
        "StringValue",
        "DateTime",
    ):
        v = getattr(item, attr, None)
        if v is not None:
            return str(v), ""
    return "", ""


@dataclass
class SrContentNode:
    """One SR content item and its nested children."""

    node_id: int
    depth: int
    concept_label: str
    relationship: str
    value_type: str
    value_text: str
    reference_text: str
    path_indices: tuple[int, ...]
    parent: SrContentNode | None = None
    children: list[SrContentNode] = field(default_factory=list)


@dataclass
class SrDocumentTree:
    """Result of walking ``ContentSequence`` for an SR document."""

    roots: list[SrContentNode]
    warnings: list[str]
    truncated: bool
    total_nodes: int
    node_by_id: dict[int, SrContentNode]


def _walk_children(
    items: Sequence[Dataset],
    *,
    path_prefix: tuple[int, ...],
    depth: int,
    max_depth: int,
    counters: dict[str, int],
    trunc: list[bool],
    warnings: list[str],
    node_by_id: dict[int, SrContentNode],
    parent_node: SrContentNode | None,
) -> list[SrContentNode]:
    out: list[SrContentNode] = []
    for idx, item in enumerate(items):
        if counters["nodes"] >= counters["max_nodes"]:
            trunc[0] = True
            break
        path = path_prefix + (idx,)
        concept = _concept_display(item)
        rel = _relationship_str(item)
        vt = _value_type_str(item)
        val, ref = _value_and_reference(item)
        nid = counters["next_id"]
        counters["next_id"] += 1
        counters["nodes"] += 1
        node = SrContentNode(
            node_id=nid,
            depth=depth,
            concept_label=concept,
            relationship=rel,
            value_type=vt,
            value_text=val,
            reference_text=ref,
            path_indices=path,
            parent=None,
            children=[],
        )
        node_by_id[nid] = node
        node.parent = parent_node
        nested = getattr(item, "ContentSequence", None)
        if nested and depth < max_depth:
            children = cast(DicomSequence, nested)
            node.children = _walk_children(
                list(children),
                path_prefix=path,
                depth=depth + 1,
                max_depth=max_depth,
                counters=counters,
                trunc=trunc,
                warnings=warnings,
                node_by_id=node_by_id,
                parent_node=node,
            )
        elif nested and depth >= max_depth:
            trunc[0] = True
        out.append(node)
    return out


def build_sr_document_tree(
    ds: Dataset,
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    max_nodes: int = _DEFAULT_MAX_NODES,
) -> SrDocumentTree:
    """
    Walk ``ds.ContentSequence`` and return a tree of :class:`SrContentNode`.

    Missing or empty ``ContentSequence`` yields empty ``roots`` and an explanatory warning.
    """
    warnings: list[str] = []
    root_seq = getattr(ds, "ContentSequence", None)
    if not root_seq:
        warnings.append("Dataset has no ContentSequence (0040,A730); nothing to display.")
        return SrDocumentTree(roots=[], warnings=warnings, truncated=False, total_nodes=0, node_by_id={})

    root_items = cast(DicomSequence, root_seq)
    if len(root_items) == 0:
        warnings.append("ContentSequence is empty.")
        return SrDocumentTree(roots=[], warnings=warnings, truncated=False, total_nodes=0, node_by_id={})

    counters: dict[str, int] = {"next_id": 0, "nodes": 0, "max_nodes": max_nodes}
    trunc: list[bool] = [False]
    node_by_id: dict[int, SrContentNode] = {}
    roots = _walk_children(
        list(root_items),
        path_prefix=(),
        depth=0,
        max_depth=max_depth,
        counters=counters,
        trunc=trunc,
        warnings=warnings,
        node_by_id=node_by_id,
        parent_node=None,
    )
    if trunc[0]:
        warnings.append(
            f"Tree truncated (max_depth={max_depth}, max_nodes={max_nodes}). Expand caps to see more."
        )
    return SrDocumentTree(
        roots=roots,
        warnings=warnings,
        truncated=trunc[0],
        total_nodes=counters["nodes"],
        node_by_id=node_by_id,
    )


def path_to_node_id_map(tree: SrDocumentTree) -> dict[tuple[int, ...], int]:
    """Map ``path_indices`` (from root ``ContentSequence``) to ``SrContentNode.node_id``."""

    out: dict[tuple[int, ...], int] = {}

    def visit(n: SrContentNode) -> None:
        out[n.path_indices] = n.node_id
        for c in n.children:
            visit(c)

    for r in tree.roots:
        visit(r)
    return out


def sr_tree_to_json_dict(tree: SrDocumentTree) -> dict[str, Any]:
    """Serialize ``tree`` to a JSON-friendly nested dict (export)."""

    def node_dict(n: SrContentNode) -> dict[str, Any]:
        return {
            "node_id": n.node_id,
            "concept": n.concept_label,
            "relationship": n.relationship,
            "value_type": n.value_type,
            "value": n.value_text,
            "reference": n.reference_text,
            "path_indices": list(n.path_indices),
            "children": [node_dict(c) for c in n.children],
        }

    return {
        "truncated": tree.truncated,
        "total_nodes": tree.total_nodes,
        "warnings": list(tree.warnings),
        "roots": [node_dict(r) for r in tree.roots],
    }
