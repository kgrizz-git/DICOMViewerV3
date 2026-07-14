# DICOM tag viewer & editor

**Last updated:** 2026-07-12

The **DICOM Tag Viewer/Editor** is a separate, resizable window that lists every tag in the current image, lets you search tags and values, copy them, and edit individual tag values (with undo/redo). To **export** tags to a file instead, see the [export guide](USER_GUIDE_EXPORT.md#other-export-paths).

## Opening it

- **Tools → View/Edit DICOM Tags…** (**Ctrl+T**).
- Also reachable from the **Structured Report** browser via **Raw tags → Open DICOM Tag Viewer**.

The window is **non-modal** — it stays open while you work, and it **follows the focused image**: switch the series or instance shown in the focused pane and the tag list updates to match. Your search filter is kept when the dataset changes.

## Reading the list

Tags are grouped by DICOM **group** number and shown in four columns:

| Column | Meaning |
|--------|---------|
| **Tag** | The `(group,element)` number, e.g. `(0010,0010)`. |
| **Name** | The tag's standard name/keyword. |
| **VR** | Value Representation (data type), e.g. `PN`, `DA`, `US`. |
| **Value** | The full value — values are **not** truncated; the row scrolls horizontally if needed. |

Columns are resizable; rows alternate shading for readability.

## Searching

Type in the **Search** box to filter the list. The match is case-insensitive and looks across the **tag number, name, keyword, and value**, so you can find a tag by any of those (e.g. `0010`, `PatientName`, or a value fragment). Filtering is debounced briefly as you type. Clear the box to show everything again.

- **Show Private Tags** (checked by default) includes vendor/private tags; uncheck to hide them.

## Copying

Right-click a tag row for copy options:

- **Copy Tag**, **Copy Name**, **Copy VR**, **Copy Value** — copy a single field.
- **Copy All** — copies the whole row, tab-separated (Tag · Name · VR · Value).

**Ctrl+C** copies the currently focused column (or the whole row if no column is active).

## Editing a tag

You can edit a single tag's value in three ways:

- **Double-click** the **Value** cell, or
- select a tag and click **Edit Selected Tag**, or
- **right-click → Edit Tag**.

This opens an editor for that tag's value. After you confirm:

- The edited tag is flagged with an **asterisk (`*`)** after its name and its row is **highlighted** (an accent-tinted background) so changes are easy to spot.
- The change is recorded in the app's **unified undo/redo**: press **Ctrl+Z** to undo and **Ctrl+Y / Ctrl+Shift+Z** to redo (also available from the row's right-click menu). Undo/redo here stays in sync with the rest of the app.
- Nested leaf rows inside DICOM sequences can be edited the same way. Sequence parent rows (`SQ`) and `Item N` container rows are structural and stay read-only.

> Editing changes the tags **in the loaded study in memory**. To persist edited tags, export the dataset (DICOM) via **File → Export…**; see the [export guide](USER_GUIDE_EXPORT.md).

## Privacy Mode

When **Privacy Mode** is on (**Ctrl+P**), the tag viewer follows the same masking rules as the rest of the app:

- **Patient-identifying tags are masked** in the list.
- **Patient tags cannot be edited** while Privacy Mode is on — attempting to edit one shows a notice, and enabling Privacy Mode will close an open patient-tag edit.

Non-patient tags remain visible and editable. Turning Privacy Mode off restores the real values.

---

See also: [USER_GUIDE.md](USER_GUIDE.md) (hub) · [USER_GUIDE_EXPORT.md](USER_GUIDE_EXPORT.md) · [USER_GUIDE_ANONYMIZATION.md](USER_GUIDE_ANONYMIZATION.md) · [USER_GUIDE_SHORTCUTS.md](USER_GUIDE_SHORTCUTS.md).
