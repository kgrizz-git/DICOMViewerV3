"""
DICOM Tag Export Dialog

This module provides a dialog for selecting and exporting DICOM tags to Excel or CSV.
Features multi-series selection and hierarchical tag selection with search.

Inputs:
    - Studies and series data (dict)
    - pydicom.Dataset objects
    
Outputs:
    - Excel, CSV, or UTF-8 text (tab-separated) files with exported tags
    
Requirements:
    - PySide6 for dialog components
    - openpyxl for Excel export
    - csv module (standard library) for CSV and text (TSV) export
    - DICOMParser for tag extraction
"""

import os
from pathlib import Path
from typing import Any, cast

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.dicom_parser import DICOMParser
from core.tag_export_catalog import synthetic_tag_export_tree_entry
from core.tag_export_controller import TagExportController, resolve_export_format
from core.tag_export_union import union_tags_across_datasets
from gui.metadata_table_model import (
    index_metadata_tag_children,
    metadata_row_depth,
    metadata_row_kind,
)
from utils.dicom_utils import canonical_dicom_tag_string
from utils.log_sanitizer import sanitize_message

# Phase 5 (sequence tag viewer plan) large-sequence / large-selection guards.
# Starting values — tune against a real enhanced study if these prove wrong.
LARGE_SEQUENCE_LEAF_THRESHOLD = 200
LARGE_EXPORT_SELECTION_THRESHOLD = 1000



_ITEM_NO_PRESET = "(No preset)"
_TITLE_NO_CONFIG_MANAGER = "No Config Manager"

def _leaf_descendant_counts(
    tags: dict[str, Any],
    children_by_parent: dict[str | None, list[tuple[str, dict[str, Any]]]],
) -> dict[str, int]:
    """
    Count leaf (``row_kind == "element"``) descendant rows for every row, in
    O(n) total.

    ``DICOMParser.get_all_tags`` emits rows depth-first (a parent always
    appears before any of its descendants), so iterating *tags* in **reverse**
    insertion order guarantees every child's count is already known by the time
    its parent is processed — no per-node rescan (that would be the same O(n^2)
    trap the shared ``index_metadata_tag_children`` helper exists to avoid).
    Used to flag oversized sequences in the export picker (large-sequence
    warning) without a second tree walk.
    """
    counts: dict[str, int] = {}
    for tag_str, tag_data in reversed(list(tags.items())):
        if metadata_row_kind(tag_data) == "element":
            counts[tag_str] = 1
        else:
            counts[tag_str] = sum(
                counts.get(child_key, 0)
                for child_key, _ in children_by_parent.get(tag_str, [])
            )
    return counts


def _tag_export_preset_match_keys(preset_tags: list[str]) -> set[str]:
    """
    Build a set of strings that should match tree UserRole tag keys when loading
    a preset (exact + canonical pydicom str(Tag) forms).
    """
    keys: set[str] = set()
    for t in preset_tags:
        if not isinstance(t, str):
            continue
        keys.add(t)
        canonical = canonical_dicom_tag_string(t)
        if canonical:
            keys.add(canonical)
    return keys


def _merged_dict_with_preset_tags(
    base: dict[str, Any] | None,
    preset_tags: list[str],
) -> tuple[dict[str, Any], bool]:
    """
    Return a shallow copy of *base* (or {}) with synthetic rows for any preset
    tag not already present. The second value is True when the dict changed.
    """
    merged: dict[str, Any] = dict(base or {})
    changed = False
    for raw in preset_tags:
        if not isinstance(raw, str):
            continue
        entry = synthetic_tag_export_tree_entry(raw)
        if entry is None:
            continue
        key, meta = entry
        if key not in merged:
            merged[key] = meta
            changed = True
    return merged, changed


class TagExportDialog(QDialog):
    """
    Dialog for exporting DICOM tags to Excel or CSV with series and tag selection.
    
    Features:
    - Multi-series selection grouped by study
    - Hierarchical tag selection (by group)
    - Search/filter tags
    - Export to Excel (one tab per study), CSV (comma-separated), or text (tab-separated, one file per study when multiple studies)
    - Tag selection presets (save/load/delete)
    """

    def __init__(
        self,
        studies: dict[str, dict[str, list[Dataset]]],
        config_manager=None,
        parent=None,
        tag_export_union_host: Any | None = None,
    ):
        """
        Initialize the tag export dialog.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            config_manager: Optional ConfigManager instance for preset storage
            parent: Parent widget
            tag_export_union_host: Optional DICOMViewerApp (or compatible) with
                get_tag_export_union_snapshot() and tag_export_union_ready signal.
        """
        super().__init__(parent)

        self.setWindowTitle("Export DICOM Tags")
        self.setModal(True)
        self.resize(1000, 700)

        self.studies = studies
        self.config_manager = config_manager
        self._tag_union_host = tag_export_union_host
        # Root-level union (scalars + SQ parents as summary rows). Precomputed.
        self._tag_union_merged_full: dict[str, Any] | None = None
        # Nested superset (adds each sequence's Item N / leaf rows), computed lazily on
        # the first "Include sequences" toggle. The root-level union above is exactly
        # this filtered to depth 0, but it is NOT derived that way on purpose: building
        # the nested superset first would make every export dialog pay for a walk that
        # runs to tens of thousands of rows on enhanced multi-frame studies, to show a
        # tree that by default hides all of them.
        self._tag_union_merged_sequences: dict[str, Any] | None = None
        self.selected_series: dict[str, dict[str, list[int]]] = {}  # {study_uid: {series_uid: [instance_indices]}}
        self.selected_tags: list[str] = []  # List of selected tag strings

        self.series_tree = QTreeWidget(self)
        self.tags_tree = QTreeWidget(self)
        self.tag_search = QLineEdit(self)
        self.tag_union_status_label = QLabel(self)
        self.tag_union_status_label.setObjectName("tagExportUnionStatus")
        self.private_tags_checkbox = QCheckBox("Include Private Tags", self)
        self.private_tags_checkbox.setChecked(True)
        self.include_missing_rows_checkbox = QCheckBox(
            "Include empty rows for missing selected tags",
            self,
        )
        self.include_missing_rows_checkbox.setChecked(True)
        self.include_sequences_checkbox = QCheckBox("Include sequences", self)
        self.include_sequences_checkbox.setChecked(False)
        self.preset_combo: QComboBox | None = None

        self._create_ui()
        self._populate_series()
        if self._tag_union_host is not None:
            self._tag_union_host.tag_export_union_ready.connect(
                self._on_tag_export_union_ready,
            )
        self.finished.connect(self._on_dialog_finished)
        self._initial_tag_tree_build()
        self._load_presets_list()

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Main splitter for two panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Series selection
        series_panel = self._create_series_panel()
        splitter.addWidget(series_panel)

        # Right panel: Tag selection
        tag_panel = self._create_tag_panel()
        splitter.addWidget(tag_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        export_button = QPushButton("Export Tags...")
        export_button.clicked.connect(self._export_to_excel)
        button_layout.addWidget(export_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _create_series_panel(self) -> QGroupBox:
        """Create the series selection panel."""
        group = QGroupBox("Select Series")
        layout = QVBoxLayout()

        # Select/Deselect buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_series(True))
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_series(False))
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Series tree
        self.series_tree.setHeaderLabels(["Series"])
        self.series_tree.setColumnWidth(0, 350)
        self.series_tree.itemChanged.connect(self._on_series_selection_changed)
        layout.addWidget(self.series_tree)

        group.setLayout(layout)
        return group

    def _create_tag_panel(self) -> QGroupBox:
        """Create the tag selection panel."""
        group = QGroupBox("Select Tags to Export")
        layout = QVBoxLayout()

        layout.addWidget(self.tag_union_status_label)

        # Preset management section
        if self.config_manager:
            preset_layout = QHBoxLayout()
            preset_label = QLabel("Preset:")
            self.preset_combo = QComboBox()
            self.preset_combo.setEditable(False)
            self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
            preset_layout.addWidget(preset_label)
            preset_layout.addWidget(self.preset_combo)

            save_preset_btn = QPushButton("Save As...")
            save_preset_btn.clicked.connect(self._save_preset)
            preset_layout.addWidget(save_preset_btn)

            load_preset_btn = QPushButton("Load")
            load_preset_btn.clicked.connect(self._load_preset)
            preset_layout.addWidget(load_preset_btn)

            delete_preset_btn = QPushButton("Delete")
            delete_preset_btn.clicked.connect(self._delete_preset)
            preset_layout.addWidget(delete_preset_btn)

            # Export/Import presets buttons (JSON)
            export_presets_btn = QPushButton("Export...")
            export_presets_btn.clicked.connect(self._export_presets)
            preset_layout.addWidget(export_presets_btn)

            import_presets_btn = QPushButton("Import...")
            import_presets_btn.clicked.connect(self._import_presets)
            preset_layout.addWidget(import_presets_btn)

            preset_layout.addStretch()
            layout.addLayout(preset_layout)

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Filter:")
        self.tag_search.setPlaceholderText("Search tags...")
        self.tag_search.textChanged.connect(self._filter_tags)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.tag_search)
        layout.addLayout(search_layout)

        # Select/Deselect buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_tags(True))
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_tags(False))
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()

        # Show private tags checkbox
        self.private_tags_checkbox.setChecked(True)
        self.private_tags_checkbox.toggled.connect(self._on_private_tags_toggled)
        button_layout.addWidget(self.private_tags_checkbox)
        button_layout.addWidget(self.include_missing_rows_checkbox)
        # Opt-in sequences checkbox — off by default so existing exports and
        # a scalar-oriented export isn't flooded with nested rows it didn't ask for.
        self.include_sequences_checkbox.toggled.connect(self._on_include_sequences_toggled)
        button_layout.addWidget(self.include_sequences_checkbox)

        layout.addLayout(button_layout)

        # Tags tree
        self.tags_tree.setHeaderLabels(["Tag", "Name"])
        self.tags_tree.setColumnWidth(0, 120)
        self.tags_tree.setColumnWidth(1, 300)
        self.tags_tree.itemChanged.connect(self._on_tag_selection_changed)
        self.tags_tree.itemExpanded.connect(self._on_tag_tree_item_expanded)
        layout.addWidget(self.tags_tree)

        group.setLayout(layout)
        return group

    def _populate_series(self) -> None:
        """Populate the series tree with available series and instances."""
        self.series_tree.clear()
        self.series_tree.blockSignals(True)

        for study_uid, series_dict in self.studies.items():
            # Get first dataset to extract study info
            first_series_uid = next(iter(series_dict))
            first_dataset = series_dict[first_series_uid][0]

            study_desc = getattr(first_dataset, 'StudyDescription', 'Unknown Study')
            study_date = getattr(first_dataset, 'StudyDate', '')
            if study_date:
                study_date = f" ({study_date})"

            # Create study item
            study_item = QTreeWidgetItem(self.series_tree)
            study_item.setText(0, f"{study_desc}{study_date}")
            study_item.setData(0, Qt.ItemDataRole.UserRole, study_uid)
            study_item.setFlags(study_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            study_item.setCheckState(0, Qt.CheckState.Unchecked)
            study_item.setExpanded(True)

            # Add series items
            for series_uid, datasets in series_dict.items():
                first_ds = datasets[0]
                series_num = getattr(first_ds, 'SeriesNumber', '')
                series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown Series')
                modality = getattr(first_ds, 'Modality', '')

                series_item = QTreeWidgetItem(study_item)
                series_text = f"Series {series_num}: {series_desc} ({modality}) - {len(datasets)} images"
                series_item.setText(0, series_text)
                series_item.setData(0, Qt.ItemDataRole.UserRole, series_uid)
                series_item.setData(0, Qt.ItemDataRole.UserRole + 1, study_uid)
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                series_item.setCheckState(0, Qt.CheckState.Unchecked)
                series_item.setExpanded(True)

                # Add instance/slice items
                for idx, dataset in enumerate(datasets):
                    instance_num = getattr(dataset, 'InstanceNumber', None)
                    slice_location = getattr(dataset, 'SliceLocation', None)

                    if instance_num is not None:
                        instance_text = f"Instance {instance_num}"
                        if slice_location is not None:
                            instance_text += f" (Slice: {slice_location:.2f})"
                    else:
                        instance_text = f"Instance {idx + 1}"
                        if slice_location is not None:
                            instance_text += f" (Slice: {slice_location:.2f})"

                    instance_item = QTreeWidgetItem(series_item)
                    instance_item.setText(0, instance_text)
                    instance_item.setData(0, Qt.ItemDataRole.UserRole, idx)  # Store instance index
                    instance_item.setData(0, Qt.ItemDataRole.UserRole + 1, series_uid)
                    instance_item.setData(0, Qt.ItemDataRole.UserRole + 2, study_uid)
                    instance_item.setFlags(instance_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    instance_item.setCheckState(0, Qt.CheckState.Unchecked)

        self.series_tree.blockSignals(False)

    def _all_loaded_datasets(self) -> list[Dataset]:
        """Flatten every instance dataset in the dialog's studies map (stable order)."""
        out: list[Dataset] = []
        for _study_uid, series_dict in self.studies.items():
            for _series_uid, datasets in series_dict.items():
                out.extend(datasets)
        return out

    def _on_dialog_finished(self) -> None:
        if self._tag_union_host is None:
            return
        try:
            self._tag_union_host.tag_export_union_ready.disconnect(
                self._on_tag_export_union_ready
            )
        except TypeError:
            pass

    def _on_tag_export_union_ready(self, gen: int, merged: object) -> None:
        if self._tag_union_host is None:
            return
        snap_gen, _ = self._tag_union_host.get_tag_export_union_snapshot()
        if gen != snap_gen:
            return
        self._tag_union_merged_full = cast(dict[str, Any], merged) if merged else {}
        self._refresh_tag_tree()

    def _initial_tag_tree_build(self) -> None:
        if not self.studies:
            self._tag_union_merged_full = {}
            self._refresh_tag_tree()
            return
        if self._tag_union_host is not None:
            _gen, merged = self._tag_union_host.get_tag_export_union_snapshot()
            if merged is not None:
                self._tag_union_merged_full = merged
                self._refresh_tag_tree()
                self.tag_union_status_label.setText("")
            else:
                self.tag_union_status_label.setText("Updating tag list…")
                self.tags_tree.setEnabled(False)
        else:
            self._populate_tags_sync()

    def _on_private_tags_toggled(self, _checked: bool) -> None:
        self._refresh_tag_tree()

    def _on_include_sequences_toggled(self, _checked: bool) -> None:
        """
        Rebuild the tag tree with (or without) each sequence's nested rows.

        Switches which merged union the tree is built from rather than filtering in
        place: the nested union is a superset that has to be walked for, and it is
        computed lazily so an export that never touches sequences never pays for it.
        """
        self._refresh_tag_tree()

    def _refresh_tag_tree(self) -> None:
        """Rebuild the visible tag tree for the current private/sequences checkboxes."""
        if self.include_sequences_checkbox.isChecked():
            self._render_tag_tree(self._ensure_sequences_union())
            return
        if self._tag_union_merged_full is not None:
            self._render_tag_tree(self._tag_union_merged_full)
        elif self._tag_union_host is None:
            self._populate_tags_sync()
        # else: host snapshot still pending — _on_tag_export_union_ready will
        # populate once the background union finishes.

    def _ensure_sequences_union(self) -> dict[str, Any] | None:
        """Lazily compute (and cache) the nested union for the currently loaded datasets."""
        if self._tag_union_merged_sequences is None:
            datasets = self._all_loaded_datasets()
            if not datasets:
                self._tag_union_merged_sequences = {}
            else:
                self._tag_union_merged_sequences = union_tags_across_datasets(
                    datasets,
                    include_private=True,
                    supplement_standard_tags=True,
                    include_sequences=True,
                )
        return self._tag_union_merged_sequences

    def _populate_tags_sync(self) -> None:
        """
        Synchronous union (tests or when no app scheduler).

        Both caches hold the *superset* — private tags included — because private rows are
        filtered per-render by :meth:`_render_tag_tree`. Merging with the checkbox's
        current value instead would bake "no private tags" into the cache, and ticking
        Include private afterwards would re-render from that same private-less dict and
        show nothing new.
        """
        self.tags_tree.clear()
        self.tags_tree.blockSignals(True)
        self.tag_union_status_label.setText("")

        if not self.studies:
            self.tags_tree.blockSignals(False)
            return

        datasets = self._all_loaded_datasets()
        include_sequences = self.include_sequences_checkbox.isChecked()
        tags = union_tags_across_datasets(
            datasets,
            include_private=True,
            supplement_standard_tags=True,
            include_sequences=include_sequences,
        )
        if include_sequences:
            self._tag_union_merged_sequences = tags
        else:
            self._tag_union_merged_full = tags
        self.tags_tree.blockSignals(False)
        self._render_tag_tree(tags)

    def _render_tag_tree(self, merged: dict[str, Any] | None) -> None:
        """Filter *merged* by the private-tags checkbox and rebuild the visible tree."""
        self.tags_tree.clear()
        self.tags_tree.blockSignals(True)
        if not merged:
            self.tags_tree.blockSignals(False)
            self.tags_tree.setEnabled(True)
            self.tag_union_status_label.setText("")
            return
        include_private = self.private_tags_checkbox.isChecked()
        filtered: dict[str, Any] = {}
        for tag_str, tag_data in merged.items():
            if not include_private and tag_data.get("is_private"):
                continue
            filtered[tag_str] = tag_data
        self._build_tag_tree_from_items(filtered)
        self.tags_tree.blockSignals(False)
        self.tags_tree.setEnabled(True)
        self.tag_union_status_label.setText("")

    def _build_tag_tree_from_items(self, tags: dict[str, Any]) -> None:
        """
        Build the tags tree, including the nested shape (sequence parent
        -> ``Item N`` -> leaves) when *tags* carries ``depth``/``parent_key``/
        ``row_kind`` fields (Include sequences on).

        Only depth-0 rows get their own group bucket; nested rows hang off their
        sequence parent via :meth:`_build_export_tag_tree_item`, mirroring the
        Phase 2 tree shape (``tag_viewer_dialog._build_tag_tree_item``). The
        child index is built ONCE via :func:`index_metadata_tag_children` and
        threaded down the recursion — a per-parent rescan is O(n^2) and cost
        ~19s on a 24k-row enhanced multi-frame study (see the plan's PERF FINDING).
        """
        sorted_tags = sorted(tags.items(), key=lambda x: x[0])
        groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for tag_str, tag_data in sorted_tags:
            if metadata_row_depth(tag_data) != 0:
                continue
            group = tag_str[:6]
            if group not in groups:
                groups[group] = []
            groups[group].append((tag_str, tag_data))

        children_by_parent = index_metadata_tag_children(tags)
        leaf_counts = _leaf_descendant_counts(tags, children_by_parent)

        for group, tag_list in sorted(groups.items()):
            group_item = QTreeWidgetItem(self.tags_tree)
            group_item.setText(0, f"Group {group[1:5]}")
            group_item.setText(1, f"{len(tag_list)} tags")
            group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            group_item.setCheckState(0, Qt.CheckState.Unchecked)
            group_item.setExpanded(False)

            for tag_str, tag_data in tag_list:
                self._build_export_tag_tree_item(
                    group_item, tag_str, tag_data, children_by_parent, leaf_counts
                )

    def _build_export_tag_tree_item(
        self,
        parent_item: QTreeWidgetItem,
        tag_str: str,
        tag_data: dict[str, Any],
        children_by_parent: dict[str | None, list[tuple[str, dict[str, Any]]]],
        leaf_counts: dict[str, int],
    ) -> QTreeWidgetItem:
        """
        Create one checkable row and recursively attach its children
        (via ``parent_key``): a sequence parent holds ``Item N`` nodes, which
        hold their own leaves (and possibly nested sequences).

        Every level is independently checkable — a checked leaf becomes its
        own export column keyed by its path; a checked SQ parent still
        exports its single summary cell regardless of what is checked beneath
        it. Sequence nodes default collapsed. A sequence whose leaf-descendant
        count exceeds :data:`LARGE_SEQUENCE_LEAF_THRESHOLD` also shows that
        count on the node and triggers a warning on expand (see
        ``_on_tag_tree_item_expanded``).
        """
        tag_item = QTreeWidgetItem(parent_item)
        tag_item.setText(0, tag_str)
        tag_item.setText(1, tag_data.get("name", ""))
        tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
        tag_item.setFlags(tag_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        tag_item.setCheckState(0, Qt.CheckState.Unchecked)

        kind = metadata_row_kind(tag_data)
        if kind == "sequence":
            leaf_count = leaf_counts.get(tag_str, 0)
            if leaf_count > LARGE_SEQUENCE_LEAF_THRESHOLD:
                name = tag_data.get("name", "")
                count_text = f"{leaf_count:,} tags"
                tag_item.setText(1, f"{name} — {count_text}" if name else count_text)
                # Marks this node for the expand-warning handler; absent/None
                # for every other row (including small sequences).
                tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, leaf_count)
            tag_item.setExpanded(False)
        elif kind == "item":
            tag_item.setExpanded(True)

        for child_key, child_data in children_by_parent.get(tag_str, []):
            self._build_export_tag_tree_item(
                tag_item, child_key, child_data, children_by_parent, leaf_counts
            )

        return tag_item

    def _on_tag_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """
        Warn when the user expands a sequence node flagged as large (plan's
        large-sequence warning). Eager population is already fast (Phase 2 perf
        finding), so this is a UX guard against browsing/over-selecting a huge
        subtree unintentionally, not a performance mitigation.
        """
        leaf_count = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(leaf_count, int):
            return
        tag_str = item.data(0, Qt.ItemDataRole.UserRole)
        QMessageBox.warning(
            self,
            "Large Sequence",
            f"{tag_str} contains {leaf_count:,} nested tags across its items.\n\n"
            "Expanding and selecting individual leaves may be slow to browse. "
            "Use the filter box to narrow down, or check the sequence row itself "
            "to export a single summary column instead.",
        )

    def _toggle_all_series(self, checked: bool) -> None:
        """Toggle all series and instance selection."""
        self.series_tree.blockSignals(True)
        root = self.series_tree.invisibleRootItem()
        for i in range(root.childCount()):
            study_item = root.child(i)
            study_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            for j in range(study_item.childCount()):
                series_item = study_item.child(j)
                series_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                for k in range(series_item.childCount()):
                    instance_item = series_item.child(k)
                    instance_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.series_tree.blockSignals(False)
        self._update_selected_series()

    def _toggle_all_tags(self, checked: bool) -> None:
        """Toggle all tag selection, recursively (every depth, not just group -> tag)."""
        self.tags_tree.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        root = self.tags_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            if not group_item.isHidden():
                group_item.setCheckState(0, state)
                self._set_descendants_check_state(group_item, state)
        self.tags_tree.blockSignals(False)
        self._update_selected_tags()

    def _iter_all_tag_items(self, item: QTreeWidgetItem):
        """
        Yield every descendant ``QTreeWidgetItem`` of *item* in the tags tree,
        recursively, at any depth.

        Replaces the old fixed two-level (group -> tag) walks that predate the
        Phase 5 nested tree (group -> SQ parent -> Item N -> leaf -> possibly a
        nested SQ). Group headers carry no tag string in ``UserRole``, so
        callers can filter those out generically instead of relying on nesting
        depth.
        """
        for i in range(item.childCount()):
            child = item.child(i)
            yield child
            yield from self._iter_all_tag_items(child)

    def _set_descendants_check_state(
        self, item: QTreeWidgetItem, state: Qt.CheckState
    ) -> None:
        """Recursively apply *state* to every visible descendant of *item*."""
        for i in range(item.childCount()):
            child = item.child(i)
            if child.isHidden():
                continue
            child.setCheckState(0, state)
            self._set_descendants_check_state(child, state)

    def _update_ancestors_check_state(self, item: QTreeWidgetItem | None) -> None:
        """
        Recompute tri-state check state from *item* up to the tree root, based
        on each ancestor's visible children (any depth, not just one level).
        """
        while item is not None:
            any_visible_child = False
            all_checked = True
            any_checked = False
            for i in range(item.childCount()):
                child = item.child(i)
                if child.isHidden():
                    continue
                any_visible_child = True
                child_state = child.checkState(0)
                if child_state == Qt.CheckState.Checked:
                    any_checked = True
                elif child_state == Qt.CheckState.PartiallyChecked:
                    any_checked = True
                    all_checked = False
                else:
                    all_checked = False

            if any_visible_child:
                if all_checked:
                    item.setCheckState(0, Qt.CheckState.Checked)
                elif any_checked:
                    item.setCheckState(0, Qt.CheckState.PartiallyChecked)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
            item = item.parent()

    def _filter_tags(self, search_text: str) -> None:
        """
        Filter tags based on search text, recursively: a node stays visible if
        its own text matches or any descendant matches, so a matching nested
        leaf keeps its sequence/item ancestors reachable (and visible).
        """
        search_lower = search_text.lower()
        root = self.tags_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            self._apply_tag_filter_recursive(group_item, search_lower, search_text)

    def _apply_tag_filter_recursive(
        self, item: QTreeWidgetItem, search_lower: str, search_text: str
    ) -> bool:
        """Hide/show *item* and its subtree; return whether it stayed visible."""
        own_text = (item.text(0) + " " + item.text(1)).lower()
        own_match = not search_text or search_lower in own_text

        any_child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            if self._apply_tag_filter_recursive(child, search_lower, search_text):
                any_child_visible = True

        visible = own_match or any_child_visible
        item.setHidden(not visible)
        if search_text and any_child_visible:
            # A descendant matched — expand so the match is reachable without
            # an extra click (sequence nodes otherwise default collapsed).
            item.setExpanded(True)
        return visible

    def _on_series_selection_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle series and instance selection changes."""
        # Block signals to prevent recursive calls
        self.series_tree.blockSignals(True)

        parent = item.parent()

        # If this is a study item, update all series and instances under it
        if parent is None:
            check_state = item.checkState(0)
            for i in range(item.childCount()):
                series_item = item.child(i)
                series_item.setCheckState(0, check_state)
                for j in range(series_item.childCount()):
                    instance_item = series_item.child(j)
                    instance_item.setCheckState(0, check_state)
        # If this is a series item, update all instances under it and parent study
        elif parent.parent() is None:
            check_state = item.checkState(0)
            for i in range(item.childCount()):
                instance_item = item.child(i)
                instance_item.setCheckState(0, check_state)

            # Update parent study's check state
            study_item = parent
            all_checked = True
            any_checked = False
            for i in range(study_item.childCount()):
                series_item = study_item.child(i)
                series_state = series_item.checkState(0)
                if series_state == Qt.CheckState.Unchecked:
                    all_checked = False
                else:
                    any_checked = True

            if all_checked:
                study_item.setCheckState(0, Qt.CheckState.Checked)
            elif any_checked:
                study_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                study_item.setCheckState(0, Qt.CheckState.Unchecked)
        # If this is an instance item, update parent series and study
        else:
            check_state = item.checkState(0)

            # Update parent series's check state
            series_item = parent
            all_checked = True
            any_checked = False
            for i in range(series_item.childCount()):
                instance_state = series_item.child(i).checkState(0)
                if instance_state == Qt.CheckState.Unchecked:
                    all_checked = False
                else:
                    any_checked = True

            if all_checked:
                series_item.setCheckState(0, Qt.CheckState.Checked)
            elif any_checked:
                series_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                series_item.setCheckState(0, Qt.CheckState.Unchecked)

            # Update parent study's check state
            study_item = series_item.parent()
            all_checked = True
            any_checked = False
            for i in range(study_item.childCount()):
                series_state = study_item.child(i).checkState(0)
                if series_state == Qt.CheckState.Unchecked:
                    all_checked = False
                else:
                    any_checked = True

            if all_checked:
                study_item.setCheckState(0, Qt.CheckState.Checked)
            elif any_checked:
                study_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                study_item.setCheckState(0, Qt.CheckState.Unchecked)

        self.series_tree.blockSignals(False)
        self._update_selected_series()

    def _on_tag_selection_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Handle tag selection changes, recursively: checking/unchecking any node
        (group header, SQ parent, ``Item N``, or leaf) propagates that state to
        every descendant, and every ancestor's tri-state is recomputed up to
        the root — not just one level in either direction.
        """
        self.tags_tree.blockSignals(True)
        check_state = item.checkState(0)
        if check_state != Qt.CheckState.PartiallyChecked:
            self._set_descendants_check_state(item, check_state)
        self._update_ancestors_check_state(item.parent())
        self.tags_tree.blockSignals(False)
        self._update_selected_tags()

    def _update_selected_series(self) -> None:
        """Update the list of selected series and instances."""
        self.selected_series = {}
        root = self.series_tree.invisibleRootItem()

        for i in range(root.childCount()):
            study_item = root.child(i)
            study_uid = study_item.data(0, Qt.ItemDataRole.UserRole)

            series_dict = {}
            for j in range(study_item.childCount()):
                series_item = study_item.child(j)
                series_uid = series_item.data(0, Qt.ItemDataRole.UserRole)

                instance_list = []
                for k in range(series_item.childCount()):
                    instance_item = series_item.child(k)
                    if instance_item.checkState(0) == Qt.CheckState.Checked:
                        instance_idx = instance_item.data(0, Qt.ItemDataRole.UserRole)
                        instance_list.append(instance_idx)

                if instance_list:
                    series_dict[series_uid] = instance_list

            if series_dict:
                self.selected_series[study_uid] = series_dict

    def _update_selected_tags(self) -> None:
        """
        Update the list of selected tags, walking the tree at any depth
        (group -> SQ parent -> Item N -> leaf -> possibly nested SQ). Every
        checked node with a tag string becomes its own export column — a
        checked SQ parent exports its summary cell, a checked nested leaf
        exports that leaf's value, independently of each other.
        """
        self.selected_tags = []
        root = self.tags_tree.invisibleRootItem()

        # Include all checked tags regardless of visibility (filter state).
        for tag_item in self._iter_all_tag_items(root):
            tag_str = tag_item.data(0, Qt.ItemDataRole.UserRole)
            if tag_str is None:
                continue
            if tag_item.checkState(0) == Qt.CheckState.Checked:
                self.selected_tags.append(tag_str)

    def _export_to_excel(self) -> None:
        """Export selected tags to Excel, CSV, or UTF-8 text (tab-separated)."""
        # Update selected tags and series to ensure they're current
        self._update_selected_tags()
        self._update_selected_series()

        # Validate selections
        if not self.selected_series:
            QMessageBox.warning(self, "No Series Selected",
                              "Please select at least one series to export.")
            return

        if not self.selected_tags:
            QMessageBox.warning(self, "No Tags Selected",
                              "Please select at least one tag to export.")
            return

        if len(self.selected_tags) > LARGE_EXPORT_SELECTION_THRESHOLD:
            reply = QMessageBox.question(
                self,
                "Large Column Selection",
                f"You have selected {len(self.selected_tags):,} tag columns. "
                "Exporting this many columns will produce a very wide "
                "spreadsheet. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Qt-free orchestration (analysis, filename, format, writer dispatch).
        controller = TagExportController(
            studies=self.studies,
            selected_series=self.selected_series,
            selected_tags=self.selected_tags,
            include_private=self.private_tags_checkbox.isChecked(),
            include_missing_rows=self.include_missing_rows_checkbox.isChecked(),
            include_sequences=self.include_sequences_checkbox.isChecked(),
        )

        # Analyze tag variations
        variation_analysis = controller.analyze_variations()

        # Show variation analysis dialog
        if not self._show_variation_analysis_dialog(variation_analysis):
            return  # User cancelled

        # Generate default filename
        default_filename = controller.default_filename()

        # Get last export path if available
        if self.config_manager:
            last_path = self.config_manager.get_last_export_path()
            if last_path:
                # last_path is a directory, use it as the initial directory
                last_path_obj = Path(last_path)
                if last_path_obj.is_dir():
                    default_filename = str(last_path_obj / Path(default_filename).name)
                else:
                    # If it's a file, use its parent directory
                    default_filename = str(last_path_obj.parent / Path(default_filename).name)

        # Show file save dialog
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save DICOM Tag Export",
            default_filename,
            "Excel Files (*.xlsx);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return

        # Determine format and ensure correct extension (Qt-free helper)
        format_key, file_path = resolve_export_format(file_path, selected_filter)

        # Save export location
        if self.config_manager:
            export_dir = str(Path(file_path).parent)
            self.config_manager.set_last_export_path(export_dir)

        # Perform export
        try:
            exported_files = controller.export(file_path, variation_analysis, format_key)
            if len(exported_files) > 1:
                file_list = "\n".join(str(f) for f in exported_files)
                QMessageBox.information(self, "Export Complete",
                                      f"Tags exported successfully to {len(exported_files)} files:\n{file_list}")
            else:
                QMessageBox.information(self, "Export Complete",
                                      f"Tags exported successfully to:\n{exported_files[0]}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export tags:\n{sanitize_message(str(e), redact_paths=True)}")

    def _show_variation_analysis_dialog(self, variation_analysis: dict[str, dict[str, list[str]]]) -> bool:
        """
        Show dialog displaying tag variation analysis.
        
        Args:
            variation_analysis: Dictionary from _analyze_tag_variations()
            
        Returns:
            True if user confirms export, False if cancelled
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Tag Variation Analysis")
        dialog.setModal(True)
        dialog.resize(700, 500)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(
            "Tags varying by instance will be exported per-instance.\n"
            "Constant tags will be exported once per series."
        )
        layout.addWidget(info_label)

        # Tree widget to show analysis
        tree = QTreeWidget()
        tree.setHeaderLabels(["Series/Tag", "Status"])
        tree.setColumnWidth(0, 400)
        tree.setColumnWidth(1, 200)
        layout.addWidget(tree)

        # Populate tree
        for study_uid, series_dict in self.selected_series.items():
            for series_uid, instance_indices in series_dict.items():
                if series_uid not in variation_analysis:
                    continue

                # Get series info
                datasets = self.studies[study_uid][series_uid]
                first_ds = datasets[0] if datasets else None
                if not first_ds:
                    continue

                series_num = getattr(first_ds, 'SeriesNumber', '')
                series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown Series')
                series_text = f"Series {series_num}: {series_desc} ({len(instance_indices)} instances selected)"

                series_item = QTreeWidgetItem(tree)
                series_item.setText(0, series_text)
                series_item.setExpanded(True)

                analysis = variation_analysis[series_uid]
                varying_tags = analysis['varying_tags']
                constant_tags = analysis['constant_tags']

                # Varying tags
                if varying_tags:
                    varying_item = QTreeWidgetItem(series_item)
                    varying_item.setText(0, f"Varying Tags ({len(varying_tags)})")
                    varying_item.setText(1, "Per-instance export")

                    parser = DICOMParser(first_ds)
                    all_tags = parser.get_all_tags(
                        include_private=self.private_tags_checkbox.isChecked(),
                        supplement_standard_tags=True,
                        include_sequences=self.include_sequences_checkbox.isChecked(),
                    )

                    for tag_str in sorted(varying_tags):
                        tag_item = QTreeWidgetItem(varying_item)
                        if tag_str in all_tags:
                            tag_data = all_tags[tag_str]
                            tag_name = tag_data.get('name', tag_str)
                            tag_item.setText(0, f"{tag_str} - {tag_name}")
                        else:
                            tag_item.setText(0, tag_str)

                # Constant tags
                if constant_tags:
                    constant_item = QTreeWidgetItem(series_item)
                    constant_item.setText(0, f"Constant Tags ({len(constant_tags)})")
                    constant_item.setText(1, "Per-series export")

                    parser = DICOMParser(first_ds)
                    all_tags = parser.get_all_tags(
                        include_private=self.private_tags_checkbox.isChecked(),
                        supplement_standard_tags=True,
                        include_sequences=self.include_sequences_checkbox.isChecked(),
                    )

                    for tag_str in sorted(constant_tags):
                        tag_item = QTreeWidgetItem(constant_item)
                        if tag_str in all_tags:
                            tag_data = all_tags[tag_str]
                            tag_name = tag_data.get('name', tag_str)
                            tag_item.setText(0, f"{tag_str} - {tag_name}")
                        else:
                            tag_item.setText(0, tag_str)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        export_btn = QPushButton("Continue Export")
        export_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(export_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _load_presets_list(self) -> None:
        """Load list of presets into combo box."""
        if not self.config_manager or self.preset_combo is None:
            return

        self.preset_combo.clear()
        presets = self.config_manager.get_tag_export_presets()
        if presets:
            self.preset_combo.addItems(sorted(presets.keys()))
        self.preset_combo.addItem(_ITEM_NO_PRESET)
        self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)

    def _on_preset_selected(self, preset_name: str) -> None:
        """Handle preset selection (for future use, e.g., auto-load on selection)."""
        pass

    def _save_preset(self) -> None:
        """Save current tag selections as a preset."""
        if not self.config_manager:
            QMessageBox.warning(self, _TITLE_NO_CONFIG_MANAGER,
                              "Preset saving is not available.")
            return

        # Update selected tags first
        self._update_selected_tags()

        if not self.selected_tags:
            QMessageBox.warning(self, "No Tags Selected",
                              "Please select at least one tag to save as a preset.")
            return

        # Get preset name from user
        from PySide6.QtWidgets import QInputDialog
        preset_name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text=""
        )

        if not ok or not preset_name.strip():
            return

        preset_name = preset_name.strip()

        # Save preset
        self.config_manager.save_tag_export_preset(preset_name, self.selected_tags)
        self._load_presets_list()

        # Select the newly saved preset
        if self.preset_combo is None:
            return
        index = self.preset_combo.findText(preset_name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

        QMessageBox.information(self, "Preset Saved",
                               f"Preset '{preset_name}' saved successfully.")

    def _load_preset(self) -> None:
        """Load a preset and apply tag selections."""
        if not self.config_manager:
            QMessageBox.warning(self, _TITLE_NO_CONFIG_MANAGER,
                              "Preset loading is not available.")
            return
        if self.preset_combo is None:
            return

        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name == _ITEM_NO_PRESET:
            QMessageBox.warning(self, "No Preset Selected",
                              "Please select a preset to load.")
            return

        # Get preset tags
        presets = self.config_manager.get_tag_export_presets()
        if preset_name not in presets:
            QMessageBox.warning(self, "Preset Not Found",
                              f"Preset '{preset_name}' not found.")
            return

        preset_tags = presets[preset_name]
        # Add the preset's missing tags to whichever union is on screen. Always merging
        # into the flat one would drop a preset tag from view while Include sequences is
        # ticked, since that renders from the nested union instead.
        sequences_on = self.include_sequences_checkbox.isChecked()
        active_union = (
            self._ensure_sequences_union() if sequences_on else self._tag_union_merged_full
        )
        merged, preset_added = _merged_dict_with_preset_tags(active_union, preset_tags)
        if preset_added:
            if sequences_on:
                self._tag_union_merged_sequences = merged
            else:
                self._tag_union_merged_full = merged
            self._refresh_tag_tree()
        match_keys = _tag_export_preset_match_keys(preset_tags)

        # Apply preset to tag tree (tree is fresh if we rebuilt above; otherwise
        # uncheck everything first, at any depth).
        self.tags_tree.blockSignals(True)
        root = self.tags_tree.invisibleRootItem()

        if not preset_added:
            for item in self._iter_all_tag_items(root):
                item.setCheckState(0, Qt.CheckState.Unchecked)

        # Check tags that are in the preset (may be a nested path key if
        # the preset was saved with "Include sequences" on), then recompute
        # every ancestor's tri-state up to the root.
        checked_items: list[QTreeWidgetItem] = []
        for tag_item in self._iter_all_tag_items(root):
            tag_str = tag_item.data(0, Qt.ItemDataRole.UserRole)
            if tag_str is not None and tag_str in match_keys:
                tag_item.setCheckState(0, Qt.CheckState.Checked)
                checked_items.append(tag_item)

        for tag_item in checked_items:
            self._update_ancestors_check_state(tag_item.parent())

        self.tags_tree.blockSignals(False)
        self._filter_tags(self.tag_search.text())
        self._update_selected_tags()

        QMessageBox.information(self, "Preset Loaded",
                               f"Preset '{preset_name}' loaded successfully.")

    def _delete_preset(self) -> None:
        """Delete the selected preset."""
        if not self.config_manager:
            QMessageBox.warning(self, _TITLE_NO_CONFIG_MANAGER,
                              "Preset deletion is not available.")
            return
        if self.preset_combo is None:
            return

        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name == _ITEM_NO_PRESET:
            QMessageBox.warning(self, "No Preset Selected",
                              "Please select a preset to delete.")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_tag_export_preset(preset_name)
            self._load_presets_list()
            QMessageBox.information(self, "Preset Deleted",
                                   f"Preset '{preset_name}' deleted successfully.")

    def _export_presets(self) -> None:
        """Export all tag export presets to a JSON file."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset export is not available."
            )
            return

        presets = self.config_manager.get_tag_export_presets()
        if not presets:
            QMessageBox.information(
                self,
                "No Tag Presets",
                "There are no tag export presets to export."
            )
            return

        # Determine initial directory (reuse last export path behaviour)
        last_export_path = self.config_manager.get_last_export_path()
        if not last_export_path or not os.path.exists(last_export_path):
            last_export_path = os.getcwd()

        if os.path.isfile(last_export_path):
            last_export_path = os.path.dirname(last_export_path)

        default_filename = str(Path(last_export_path) / "tag_export_presets.json")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tag Presets",
            default_filename,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        if not file_path.endswith(".json"):
            file_path += ".json"

        if self.config_manager.export_tag_export_presets(file_path):
            # Remember export directory
            self.config_manager.set_last_export_path(str(Path(file_path).parent))
            QMessageBox.information(
                self,
                "Export Successful",
                f"Tag export presets exported successfully to:\n{file_path}"
            )
        else:
            QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export tag export presets to:\n{file_path}\n\n"
                "Please check file permissions and try again."
            )

    def _import_presets(self) -> None:
        """Import tag export presets from a JSON file."""
        if not self.config_manager:
            QMessageBox.warning(
                self,
                _TITLE_NO_CONFIG_MANAGER,
                "Preset import is not available."
            )
            return

        # Use last path if available for initial directory
        last_path = self.config_manager.get_last_path()
        if not last_path or not os.path.exists(last_path):
            last_path = os.getcwd()

        if os.path.isfile(last_path):
            last_path = os.path.dirname(last_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Tag Presets",
            last_path,
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        result = self.config_manager.import_tag_export_presets(file_path)
        if result is None:
            QMessageBox.critical(
                self,
                "Import Failed",
                "Failed to import tag export presets.\n\n"
                "Please verify that the file is a valid DICOM Viewer V3 tag presets file."
            )
            return

        imported = result.get("imported", 0)
        skipped = result.get("skipped_conflicts", 0)

        # Refresh presets list in combo box
        self._load_presets_list()

        if imported == 0 and skipped == 0:
            QMessageBox.information(
                self,
                "No Presets Imported",
                "The selected file did not contain any tag export presets."
            )
        else:
            details_lines = [f"Presets imported: {imported}"]
            if skipped > 0:
                details_lines.append(
                    f"Presets skipped (already exist and were not overwritten): {skipped}"
                )
            details = "\n".join(details_lines)
            QMessageBox.information(
                self,
                "Import Complete",
                f"Tag export presets import completed.\n\n{details}"
            )

