# Configuration and preferences

This guide describes **where** to change behavior that is saved between sessions. It complements the **[User guide hub](USER_GUIDE.md)** (workflows and features).

## Edit → Settings…

Open **Edit → Settings…** for cross-cutting preferences that are **not** under the View menu.

The dialog explains that **overlay** density and tag lists live under **View → Overlay Settings** and **View → Overlay Tags Configuration**; **annotation** defaults under **View → Annotation Options**; **privacy** under **View → Privacy Mode**.

### Local study index (encrypted)

The **Local study index (encrypted)** group stores metadata about studies you open so they can be browsed or searched locally (MVP behavior may evolve—see **Advanced** below).

| Control | Meaning |
|--------|---------|
| **Automatically add files to the study index when opened successfully** | When enabled, successfully opened files are recorded in the index. |
| **Database file** | Path to the encrypted SQLite database file. **Browse…** chooses a path; **Use default path** clears the field so the app uses its default (typically next to your app config file). |
| Hint text in the dialog | The database is encrypted with **SQLCipher**. The encryption key is stored in the **OS credential manager**, not in the JSON config file. |

**Privacy:** Indexed metadata reflects what was read from DICOM files; use **Privacy mode** when presenting the UI to others, and treat the database file as **sensitive**—protect backups accordingly.

**Advanced (design / roadmap):** [Local study database and indexing plan](../dev-docs/plans/supporting/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md) — developer-oriented background; not required for day-to-day use.

## Where settings are saved on disk

Preferences are persisted as **JSON** (merged with built-in defaults on startup). The file is named **`dicom_viewer_config.json`** and lives in the application data folder:

- **Windows:** `%APPDATA%\DICOMViewerV3\`
- **macOS / Linux:** `~/.config/DICOMViewerV3/`

Do not edit the JSON by hand unless you know the schema; invalid files fall back to defaults with a console warning.

## View → Overlay Settings…

**View → Overlay Settings…** opens the **Overlay Settings** dialog (window title **Overlay Settings**). Groups include:

- **Overlay Settings** — font size, family, variant, and text color for corner/metadata overlay text.
- **Viewer Overlay Elements** — scale markers and patient direction labels (show/hide, colors, sizes, tick intervals).
- **Slice Position Lines** — how slice-location lines are drawn (mode and width), plus slice-sync strip height where applicable.

Changes apply to the live view (with cancel restoring prior values). These map to keys under the **overlay** and related sections of the JSON config (see `OverlayConfigMixin` and related getters in `src/utils/config_manager.py`).

## View → Overlay Tags Configuration…

**View → Overlay Tags Configuration…** controls which DICOM tags appear in **Simple** vs **Detailed** corner overlays, default overlay density, and **Detailed-only** extras. Persisted keys include **`overlay_mode`**, **`overlay_tags`**, and **`overlay_tags_detailed_extra`**. Full behavior is described in **[USER_GUIDE.md](USER_GUIDE.md)** under **Corner overlays**.

## View → Annotation Options…

**View → Annotation Options…** (**Annotation Options** dialog) groups:

- **ROI Settings** — ROI line/font appearance defaults.
- **ROI Statistics Visibility** — which statistics appear in the panel and exports.
- **Measurement Settings** — measurement line/font defaults.
- **Text Annotation Settings** / **Arrow Annotation Settings** — annotation tool appearance.

These align with **`roi_*`**, **`measurement_*`**, and **`arrow_annotation_*`** keys (see `src/utils/config/` mixins).

## Other persisted domains (no single “Settings” dialog)

The following are saved in the same JSON file but are usually changed from toolbars, menus, or dedicated feature dialogs (not **Edit → Settings…**):

| Area | Examples of keys / UI |
|------|------------------------|
| Paths | **`last_path`**, **`last_export_path`**, **`last_pylinac_output_path`**, **`recent_files`** |
| Display | **`theme`**, **`scroll_wheel_mode`**, **`privacy_view_enabled`**, **`smooth_image_when_zoomed`**, navigator options, histogram projection toggle |
| Layout | **`multi_window_layout`**, **`view_slot_order`** |
| Cine | **`cine_default_speed`**, **`cine_default_loop`** |
| Metadata panel | **`metadata_panel_column_widths`** |
| Tag export | **`tag_export_*`** presets (managed in the tag export UI) |
| Customizations | Bulk **import/export visual customizations** (JSON) |
| Slice sync | **`slice_sync_enabled`**, **`slice_sync_groups`**, slice-location line visibility flags |
| ACR / pylinac | **`acr_mri_low_contrast_*`**, **`acr_qa_vanilla_pylinac`** (options dialogs) |
| MPR | **`mpr_cache_max_mb`** |
| Study index browser | **`study_index_browser_column_order`** (column layout in the index UI when present) |

For key-level detail, developers can inspect **`src/utils/config_manager.py`** (`default_config`) and the mixins under **`src/utils/config/`**.

## View menu and related dialogs

Many visual and interaction options open dedicated dialogs (persisted in config). Use the **View** menu and image **right-click** menus in the running app; narrative documentation is in **[USER_GUIDE.md](USER_GUIDE.md)** (for example corner overlays, themes, layout, scroll-wheel mode).

## In-app documentation URLs (forks and releases)

**Help → Documentation** and links inside **Help → Quick Start Guide** use the GitHub base URL in `src/utils/doc_urls.py` (`USER_DOCS_GITHUB_PREFIX`). Forks or private builds should point that constant at the correct branch or tree. Release-matched doc policy is described in **[RELEASING.md](../dev-docs/RELEASING.md#in-app-user-documentation-urls)**.
