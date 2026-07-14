"""
Shared Window/Level preset menu builder for toolbar and image context menu.

Groups presets by source (DICOM, built-in, custom), unit-aware labels, and tooltips.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QMenu, QPushButton, QWidget

from core.wl_preset_catalog import (
    LegacyWLPreset,
    WindowLevelPreset,
    format_preset_menu_label,
    format_preset_tooltip,
    presets_to_legacy,
)


@dataclass
class WLPresetMenuContext:
    """Data needed to populate a W/L preset menu."""

    preset_objects: list[WindowLevelPreset]
    current_index: int
    unit: str | None = None
    use_rescaled: bool = False
    rescale_slope: float | None = None
    rescale_intercept: float | None = None

    @property
    def legacy_presets(self) -> list[LegacyWLPreset]:
        return presets_to_legacy(self.preset_objects)


def context_from_legacy_presets(
    legacy: list[LegacyWLPreset],
    *,
    current_index: int = 0,
    unit: str | None = None,
    use_rescaled: bool = False,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> WLPresetMenuContext:
    """Build menu context when only legacy tuples exist (fallback)."""
    objects = [
        WindowLevelPreset(wc, ww, ir, name, "builtin", None)
        for wc, ww, ir, name in legacy
    ]
    return WLPresetMenuContext(
        preset_objects=objects,
        current_index=current_index,
        unit=unit,
        use_rescaled=use_rescaled,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
    )


def resolve_wl_preset_menu_context(
    get_context: Callable[[], WLPresetMenuContext] | None,
    get_legacy_presets: Callable[[], list[LegacyWLPreset]] | None = None,
) -> WLPresetMenuContext:
    """
    Build menu context from the modern callback or legacy preset tuples.

    Used by toolbar, View menu, right pane, and Quick W/L dialog so each
    surface shares the same fallback rules.
    """
    if callable(get_context):
        return get_context()
    legacy: list[LegacyWLPreset] = []
    if callable(get_legacy_presets):
        raw = get_legacy_presets()
        legacy = list(raw) if raw else []
    return context_from_legacy_presets(legacy)


def wire_dynamic_wl_preset_menu(
    menu: QMenu,
    *,
    on_select: Callable[[int], None],
    get_context: Callable[[], WLPresetMenuContext] | None = None,
    get_legacy_presets: Callable[[], list[LegacyWLPreset]] | None = None,
    on_manage: Callable[[], None] | None = None,
) -> None:
    """
    Repopulate *menu* on ``aboutToShow`` using ``populate_wl_preset_menu``.

    Args:
        menu: Target menu (cleared on each show).
        on_select: Called with preset index when user picks a preset.
        get_context: Preferred callback (focused pane / VSM state).
        get_legacy_presets: Fallback when only legacy tuples exist.
        on_manage: Opens Manage W/L Presets dialog.
    """

    def _repopulate() -> None:
        menu.clear()
        ctx = resolve_wl_preset_menu_context(get_context, get_legacy_presets)
        populate_wl_preset_menu(
            menu,
            ctx,
            on_select,
            on_manage=on_manage if callable(on_manage) else None,
        )

    menu.aboutToShow.connect(_repopulate)


def create_wl_presets_menu_button(
    parent: QWidget,
    *,
    on_select: Callable[[int], None],
    get_context: Callable[[], WLPresetMenuContext] | None = None,
    get_legacy_presets: Callable[[], list[LegacyWLPreset]] | None = None,
    on_manage: Callable[[], None] | None = None,
    label: str = "Presets…",
    tooltip: str = "Window/Level presets for the focused image pane",
) -> QPushButton:
    """Compact push button with a dropdown preset menu (right pane, dialogs)."""
    btn = QPushButton(label, parent)
    btn.setToolTip(tooltip)
    preset_menu = QMenu(btn)
    wire_dynamic_wl_preset_menu(
        preset_menu,
        on_select=on_select,
        get_context=get_context,
        get_legacy_presets=get_legacy_presets,
        on_manage=on_manage,
    )
    btn.setMenu(preset_menu)
    return btn


def populate_wl_preset_menu(
    menu: QMenu,
    ctx: WLPresetMenuContext,
    on_select: Callable[[int], None],
    *,
    on_manage: Callable[[], None] | None = None,
    include_manage: bool = True,
) -> None:
    """
    Fill *menu* with grouped, checkable preset actions.

    Args:
        menu: Target menu (cleared by caller before invoke).
        ctx: Preset list and viewer state for labels/tooltips.
        on_select: Called with preset index when user picks a preset.
        on_manage: Opens Manage W/L Presets dialog.
        include_manage: Add separator and Manage action at bottom.
    """
    presets = ctx.preset_objects
    if not presets:
        empty = menu.addAction("No presets available")
        empty.setEnabled(False)
        if include_manage and on_manage is not None:
            menu.addSeparator()
            manage_act = menu.addAction("Manage W/L Presets…")
            manage_act.triggered.connect(on_manage)
        return

    groups: list[tuple[str, str]] = [
        ("dicom", "From DICOM"),
        ("builtin", "Built-in"),
        ("user", "Custom"),
    ]
    modality_label: str | None = None
    for p in presets:
        if p.source == "builtin" and p.modality:
            modality_label = p.modality
            break

    any_added = False
    for source_key, title in groups:
        indices = [i for i, p in enumerate(presets) if p.source == source_key]
        if not indices:
            continue
        if any_added:
            menu.addSeparator()
        any_added = True
        group_title = title
        if source_key == "builtin" and modality_label:
            group_title = f"Built-in — {modality_label}"
        sub = menu.addMenu(group_title)
        for idx in indices:
            preset = presets[idx]
            label = format_preset_menu_label(
                preset,
                unit=ctx.unit,
                use_rescaled=ctx.use_rescaled,
                rescale_slope=ctx.rescale_slope,
                rescale_intercept=ctx.rescale_intercept,
            )
            action = sub.addAction(label)
            action.setCheckable(True)
            action.setChecked(idx == ctx.current_index)
            action.setToolTip(
                format_preset_tooltip(
                    preset,
                    unit=ctx.unit,
                    use_rescaled=ctx.use_rescaled,
                    rescale_slope=ctx.rescale_slope,
                    rescale_intercept=ctx.rescale_intercept,
                )
            )
            action.triggered.connect(lambda _checked=False, i=idx: on_select(i))

    if include_manage and on_manage is not None:
        menu.addSeparator()
        manage_act = menu.addAction("Manage W/L Presets…")
        manage_act.triggered.connect(on_manage)
