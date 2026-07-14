# Plan: Path-Addressed Editing of Nested Sequence Tags

Last updated: 2026-07-12

Recommended branch: `nested-sequence-tag-editing` (created 2026-07-12).

## Goal and success criteria

Make nested (`depth > 0`) tag rows editable in both tag views. Today they are deliberately **read-only**: the sequence tag viewer (shipped on `sequence-tag-viewer`, see [SEQUENCE_TAG_VIEWER_AND_GROUP_COLLAPSE_PLAN.md](SEQUENCE_TAG_VIEWER_AND_GROUP_COLLAPSE_PLAN.md)) displays nested rows keyed by **path** — `(0012, 0064)[0].(0008, 0104)` — but every write path resolves a tag at the **dataset root**. An edit typed into a nested row would therefore land on a root element of the same tag number, or create one. Read-only is the correct interim behavior; this plan removes the limitation properly.

Success criteria:

- Editing a nested leaf writes to **that** element, inside its own sequence item, and survives save/export.
- Undo and redo of a nested edit restore exactly the element that was changed, at any depth.
- The "edited" highlight (and the stored original value behind it) applies per **path**, so two rows sharing a tag number under different items do not smear onto each other.
- `SQ` parent rows and `Item N` rows stay read-only at every depth — there is no scalar to type into.
- A path that no longer resolves (item index out of range, sequence replaced) **fails closed**: the edit is rejected, nothing is written.
- **Privacy mode still blocks patient tags at any depth** — a `(0010,xxxx)` element nested inside a sequence is as much PHI as one at the root.
- Root-level editing behavior remains compatible except for one deliberate bug fix:
  undo/history must capture the raw pre-edit pydicom value for **all** tag edits,
  not the UI's display-formatted string/list representation.

## Context and links

- Backlog item: `dev-docs/TO_DO.md` → Features (Near-Term), "Path-addressed editing of nested sequence tags".
- Depends on the shipped parser contract: every row carries `depth`, `parent_key`, `item_index`, `row_kind` (`src/core/dicom_parser.py`).
- Current state observed from code:
  - `DICOMEditor.update_tag` (`src/core/dicom_editor.py:111`) calls `get_target_dataset()` — which only unwraps a `FrameDatasetWrapper` — then does `target_dataset[tag].value = ...`. No item path anywhere. Its `parse_tag` **raises** `ValueError` on an unrecognized identifier, so a path key must be handled before it gets there (or caught).
  - `TagEditCommand` (`src/utils/undo_redo_tag_commands.py:35-183`) **does not delegate to the editor**; it reimplements the write in `execute` and `undo`, including a second parallel write into `self.dataset` when a frame wrapper is present. **Eight write sites**, all root-addressed: `execute` and `undo` each have a delete branch and a set/add branch, and each branch writes twice (target dataset + wrapper).
  - `TagEditCommand.__init__` does **not** parse its `tag` argument — it stores whatever the UI passes and relies on it being a `Tag`. `self.tag` is then used for `in target_dataset` membership, `dictionary_VR()`, and `get_tag_string()`, so handing it a path key string breaks all three.
  - `TagEditCommand.get_tag_string()` normalizes to `(GGGG,EEEE)`, and that string is the history-manager key.
  - Both production UI command call sites (`metadata_panel.py:932` and `tag_viewer_dialog.py:678`) pass `old_value = current_value`, where `current_value` comes from `tag_data["value"]`. That parser value is display-normalized (`PersonName`/lists/other non-basic objects are converted before rendering). This is a latent root-level bug too: undo/history can restore display text instead of the original pydicom value. Fix it for every `TagEditCommand`, not just nested paths.
  - The read-only guard is `_is_editable_item` (`src/gui/metadata_panel.py:852-866`, `src/gui/dialogs/tag_viewer_dialog.py:563-577`), which returns `depth == 0 and row_kind == "element"`. Call sites: `metadata_panel.py:816,881` and `tag_viewer_dialog.py:591,608,633`.
  - Sequence items are real `pydicom` `Dataset` objects, so mutating a resolved element in place is reflected on save with no extra plumbing.

### Confirmed already-correct (no work needed)

- **The history manager is key-agnostic.** `store_original_value`, `get_original_value`, `mark_tag_edited`, and `is_tag_edited` all take `tag_str` as an **opaque string**. Keying by path therefore requires **no change to `tag_edit_history.py`** — only `TagEditCommand.get_tag_string()` has to start returning the path key.
- **The edited-highlight lookup is already path-keyed.** `metadata_panel.py:604` and `tag_viewer_dialog.py:469` call `is_tag_edited(dataset, tag_str)` with the *tree key*, which is already the path for nested rows. Once `get_tag_string()` returns the path, the `*` highlight distinguishes same-numbered nested rows for free.
- **`TagEditDialog` does not parse `tag_str`** — it only displays it — so a path key needs no dialog change.

### Explicitly out of scope

- `tag_edit_history.py`'s `EditTagCommand` (line 43) and the manager's own `_get_tag_string` / `_update_edited_tags` / `undo` / `redo` are the **legacy** command path. `EditTagCommand` is constructed **only in `tests/test_tag_edit_history.py`** — no production code uses it; the UI edits through the unified `UndoRedoManager` and `undo_redo_tag_commands.TagEditCommand`. Do not touch it.
- There is **no revert-to-original feature** in either view. `get_original_value` has exactly one caller (`undo_redo_tag_commands.py:105`), used to decide whether the original has been stored yet. Originals are stored, but nothing reads them back to restore a value — undo restores via `old_value` on the command. Revert is therefore not a success criterion here.

## Risk

This is the one area on this feature where a bug **corrupts patient data** rather than looking wrong: a mis-resolved path silently writes a value into the wrong DICOM element. Every phase below is gated on tests, and the resolver is deliberately a pure function so it can be exhaustively tested without Qt.

## Phases

### Phase 1 — Path resolver (pure, no Qt, no editor)

- [x] Add `resolve_tag_path(dataset, path_key) -> tuple[Dataset, BaseTag] | None` to a new `src/core/tag_path.py`: parse `(gggg, eeee)[i].(gggg, eeee)…`, walk each `[i]` into `elem.value[i]`, return the **containing** dataset and the final tag.
- [x] Define the accepted grammar explicitly in tests:
  - Root key: `(0010, 0010)` and no-space/lowercase variants.
  - Nested key: `(0012, 0064)[0].(0008, 0104)` repeated to any supported depth.
  - Final segment must be a tag, not an item node; `(0012, 0064)[0]` returns `None`.
  - Negative indices, empty indices, occurrence suffixes such as `#2`, and synthetic keys such as `.<truncated>` return `None`.
- [x] Return `None` (never raise, never guess) for: unparseable key, missing intermediate tag, non-`SQ` intermediate, item index out of range, non-`Dataset` sequence item.
- [x] Add a shared leaf-tag parser/helper in the same module (`leaf_tag_from_key` or equivalent) so UI parsing and `is_patient_tag` do not each invent their own regex.
- [x] Accept the display key form with a space (`(0012, 0064)`) — that is what the tree emits — while returning a `BaseTag` independent of spacing.
- [x] Tests: root key resolves to the root dataset; one level; three levels; each failure mode returns `None`; a path whose intermediate is a scalar returns `None`; leaf-tag extraction works for root and nested keys.

### Phase 2 — Editor

- [x] `DICOMEditor.update_tag` resolves via `resolve_tag_path` when the identifier is a path key, and falls back to the existing root behavior otherwise.
- [x] Reject a write whose path does not resolve (return `False`), and reject a write to an `SQ` or item node.
- [x] Tests: nested write lands on the right element and leaves the same tag number at root untouched; unresolvable path returns `False` and mutates nothing; existing root tests still pass unchanged.

### Phase 3 — Undo/redo and edit history (the risky one)

- [x] Extend the constructor to `TagEditCommand(dataset, tag, old_value, new_value, vr=None, tag_edit_history_manager=None, ui_refresh_callback=None, path_key: str | None = None)`. `path_key` is appended so every existing positional call site keeps working. When `path_key is None` the command behaves exactly as today.
- [x] **Resolve lazily, at `execute()`/`undo()` time — not in `__init__`.** Each call resolves `path_key` against the dataset it is about to write, so the frame-wrapper parallel write resolves against `self.dataset` *and* `_original_dataset` **independently** (they are different object graphs; a `Dataset` resolved from one must never be written into the other). If resolution returns `None`, **abort the whole command before writing anything** — no partial write across the two datasets.
- [x] Make command failure visible to `UndoRedoManager.execute_command()`. It currently appends a command after `execute()` returns, so an unresolvable path must raise a controlled exception or otherwise prevent stack insertion; a silent no-op would create a bogus undo entry.
- [x] Route **all eight** write sites through the resolver: `execute` and `undo` × (delete branch, set/add branch) × (target dataset, wrapper dataset).
- [x] `get_tag_string()` returns `path_key` verbatim when set, else today's `(GGGG,EEEE)`. This is the *only* change needed to key the history by path — the manager already treats the key as an opaque string (see "Confirmed already-correct").
- [x] **Fix raw old-value capture for every tag edit, root and nested.** On the first successful `execute()`, read and store a detached copy of the existing `DataElement.value` from the resolved target before writing. Do not trust the UI's `tag_data["value"]`; it is display-formatted. Preserve the constructor's `old_value` parameter only as a compatibility fallback for tests/callers where the element cannot be read.
- [x] For frame wrappers, capture and restore old values per object graph when both `self.dataset` and `_original_dataset` are written. If the wrapper copy and original diverged before the edit, undo must restore each to its own prior value rather than copying one old value into both.
- [x] Store the raw captured old value in `tag_edit_history_manager.store_original_value()` for root and nested edits, so the edited marker can clear when a value returns to its true original representation.
- [x] Tests: undo/redo a nested edit at depth 2; two rows with the same tag number under different items are edited and undone independently (this is the test that would have caught the smearing); a nested edit on a frame-wrapped dataset writes the correct nested element in **both** datasets; an unresolvable `path_key` writes nothing to *either* dataset and does not enter the undo stack; undo of both root and nested edits restores the raw original value, not a formatted string; frame-wrapper undo restores distinct pre-edit values in wrapper/original if they differed.

### Phase 4 — UI unlock

- [x] **Replace the inline tag parsing in both views — without this, every nested edit is silently dropped.** `metadata_panel.py:927-930` and `tag_viewer_dialog.py:673-676` both do:

  ```python
  parts = [p.strip() for p in tag_str.strip("()").split(",")]
  if len(parts) != 2:
      return          # <-- a path key lands here and the edit vanishes
  tag = Tag(int(parts[0], 16), int(parts[1], 16))
  ```

  A path key splits into 3+ parts (`(0012, 0064)[0].(0008, 0104)` → `["0012", "0064)[0].(0008", "0104"]`), hits the `return`, and the edit is discarded with no error and no write. Route through a shared helper that detects a path key and yields `(leaf_tag, path_key)`; pass both to `TagEditCommand`. This must land in the same change as the guard removal.
- [x] Make the privacy guard path-aware. `_is_edit_blocked_by_privacy` → `is_patient_tag(tag_str)` (`src/utils/dicom_utils.py:568`) tests `tag_str.startswith("(0010,")`, which is **False** for `(0012, 0064)[0].(0010, 0010)`. Unlocking nested rows without fixing this lets privacy mode be bypassed on nested PHI (e.g. patient tags inside `OriginalAttributesSequence`). Test the **leaf** tag of the path, not the whole key. This also covers `close_active_tag_edit_dialog_due_to_privacy()` in both views because it calls the same helper.
- [x] Relax `_is_editable_item` in both views from `depth == 0 and row_kind == "element"` to `row_kind == "element"` — `SQ` parents and `Item N` rows stay read-only at every depth. Update the docstrings and the stale "Pre-existing bug" comments (`metadata_panel.py:812-815,856-861`, `tag_viewer_dialog.py:567-572`), and the defensive re-check at `tag_viewer_dialog.py:633`.
- [x] The no-undo-manager fallback branch passes `tag_str` straight to `editor.update_tag` — Phase 2 makes that path-aware, but it must also store the raw original value before the direct write when `history_manager` is present; otherwise fallback highlighting/history semantics diverge from the command path. Cover it with a test since it bypasses `TagEditCommand` entirely.
- [x] Tests: a nested leaf row is editable in both views; an `SQ` parent and an `Item N` row reject edits (extend the existing `test_nested_and_sequence_rows_reject_edits` family rather than deleting it — the sequence/item half still holds); a nested `(0010,xxxx)` row is refused in privacy mode; enabling privacy while a nested patient-tag edit dialog is open closes it.

### Phase 5 — Round-trip

- [x] Test: edit a nested leaf → save → reload → the nested element carries the new value and no root-level element of that tag number was created.
- [x] Test: the same round-trip on a **frame-wrapped** dataset, so the parallel-write path is proven to survive save/reload rather than only being checked in memory.
- [ ] Manual smoke: edit a `DeidentificationMethodCodeSequence` code meaning in the running app, save, reopen.

## Completion notes

- 2026-07-12: Automated implementation complete through Phase 5 round-trip tests. Full suite passed: `1931 passed, 18 skipped, 3 subtests passed`. Architecture boundaries, repo harness, user-doc links, and agent smoke passed. Manual running-app smoke remains open.

## Task graph and gates

### Ordering

- Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5. Strictly sequential: each phase is the foundation of the next.
- Phase 4 is the only phase that changes anything a user can see, and it must land **last** among the code phases — the UI stays locked until writes are provably correct.

### Verification gates

- Gate 1 (after Phase 1): resolver tests cover every failure mode and return `None` rather than raising.
- Gate 2 (after Phase 3): a nested edit and its undo are pinned by tests **at depth ≥ 2** and for two same-numbered tags under different items. Root-level undo must also prove raw old-value restoration, because that latent bug is being fixed globally. Do not proceed to Phase 4 without this.
- Gate 3 (during Phase 4): the inline-parse replacement and the privacy-guard fix are both in place. A nested edit that reaches `TagEditCommand` but not the parser fix is a silent no-op; one that skips the privacy fix is a PHI leak. Neither is caught by the Phase 3 tests, because both live above the command layer.
- Gate 4 (after Phase 5): full suite green; round-trip through save/reload verified in the running app.

### File / area ownership

- New: `src/core/tag_path.py`, `tests/test_tag_path.py`.
- Changed: `src/core/dicom_editor.py`, `src/utils/undo_redo_tag_commands.py`, `src/gui/metadata_panel.py`, `src/gui/dialogs/tag_viewer_dialog.py`, `src/utils/dicom_utils.py` (path-aware `is_patient_tag`).
- **Not** changed: `src/core/tag_edit_history.py` — its key is already an opaque string, and its `EditTagCommand` is legacy/test-only.

## Out of scope

- Adding, deleting, or reordering **sequence items** (only editing an existing nested leaf's value).
- Creating a nested element that does not already exist.
- Editing nested rows in the tag **export** picker (that view selects columns; it does not write).

## Pre-implementation decisions

1. Nested delete is out of scope for this feature. `TagEditCommand(new_value=None, path_key=...)` should fail closed for nested paths because no UI exposes or explains nested deletion. Root delete compatibility remains unchanged.
2. File-meta rows (`(0002,eeee)`) remain out of scope. The parser displays file meta at root, while `DICOMEditor.get_target_dataset()` writes to the main dataset; that is a separate multi-container addressing problem.
3. Forward value conversion should be centralized narrowly as part of this work. `TagEditCommand` and `DICOMEditor.update_tag` should share the same current VR conversion behavior, without broad DICOM validation redesign.
4. Future broader scope is tracked separately: [TO_DO.md](../../TO_DO.md) now includes a risk-aware general DICOM tag editor item for making every valid tag editable with warnings where edits can affect PHI, identity, geometry, decoding, or interoperability.
