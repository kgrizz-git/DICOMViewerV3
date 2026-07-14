# Sequence Tag Viewer + Group Collapse Plan

**Branch:** `sequence-tag-viewer` (already current — no new branch needed)
**Created:** 2026-07-11
**Status:** proposed

## Goal

Let the user inspect **everything** in a DICOM dataset — including SQ parent tags and nested
sequence items — with the noise controlled by UI affordances (hierarchy, collapse, filter)
rather than by silently dropping data in the parser.

Three surfaces, three different defaults:

| Surface | Behavior |
| --- | --- |
| Tag viewer dialog (`tag_viewer_dialog.py`) | Full hierarchy: SQ parents + nested items, expand/collapse, filter |
| Metadata panel / left pane (`metadata_panel.py`) | Same tag data + group collapse/expand like the export dialog |
| Tag export (`tag_export_*`) | Scalar rows by default; **opt-in** "Include sequences" checkbox, not a silent drop |

## Key finding (changes the shape of the work)

`DICOMParser.get_all_tags()` (`src/core/dicom_parser.py:123`) walks `Dataset.iterall()`, which
**already recurses into sequence items**. Nested children are therefore already present in the
returned dict today — de-duplicated by an occurrence suffix (`(0008,0100)#2`) when the same tag
repeats across items. The only thing being dropped is the **SQ parent element itself**
(`if elem.VR == "SQ": return`).

So "show everything" is not a new tree walk. It is:
1. Stop dropping SQ parents.
2. Record `depth` / `parent_key` / `item_index` per row so the UI can re-nest rows that the flat
   dict already contains.

This also means the current flat rows are **misleading today**: a nested `CodeMeaning` appears at
top level with no indication of which sequence it came from. Fixing parentage is a correctness win
independent of the viewer feature.

### Worked example (2026-07-11)

`ResearchDeID/ANONYMIZED/18951113-UNKNOWN_STUDY/23-UNKNOWN_SERIES/Instance_0001.dcm` has four
sequences — `(0008,1140)`, `(0008,2112)`, `(0012,0064)` (3 items), `(0018,9346)` (1 item).

On `main`, the left panel shows **no `(0012,0064)`** — the SQ drop removes it. But its children are
still emitted flat, and so are the children of the *other* code sequence, interleaved by occurrence
suffix in Group 0008:

```
(0008, 0104)     Code Meaning  'Basic Application Confidentiality Profile'   ← deid seq, item 1
(0008, 0104)#2   Code Meaning  'Retain Longitudinal Temporal Information …'  ← deid seq, item 2
(0008, 0104)#3   Code Meaning  'Retain Device Identity Option'               ← deid seq, item 3
(0008, 0104)#4   Code Meaning  'IEC Body Dosimetry Phantom'                  ← CTDI phantom seq (!)
```

`#4` belongs to `CTDIPhantomTypeCodeSequence`, not de-identification, and nothing in the UI says so.
This is the concrete case the plan fixes. **With the uncommitted working-tree diff applied, the
parser already returns `(0012,0064)` for this file** with the compact summary — so the reported
absence is `main`'s behavior, not a bug in the diff.

## Superseding the working-tree diff

The uncommitted diff on this branch adds a one-tag allowlist
(`DEIDENTIFICATION_METHOD_CODE_SEQUENCE_TAG`) plus `_EXPORTABLE_SEQUENCE_TAGS` in the catalog, so
that `DeidentificationMethodCodeSequence` survives the SQ drop and renders as a compact
`113100 DCM: Basic Application Confidentiality Profile; …` string.

That allowlist is the right *value rendering* and the wrong *mechanism* — it doesn't generalize, and
it's exactly the "silently hide useful conformance tags" problem it was working around. The plan
keeps the compact CID 7050 renderer (as the **summary text** for an SQ row) and replaces the
allowlist with the structural fix. The existing tests for the de-identification behavior should keep
passing, since the tag still appears with VR `SQ` and the same summary value.

## The data contract (decide this first — everything downstream depends on it)

`get_all_tags()` gains one parameter and operates in **two modes**. The modes have **different key
schemes**, and that is deliberate.

### Mode A — `include_sequences=False` (default; unchanged behavior)

Exactly what `main` returns today, including flat nested children keyed by the global occurrence
counter (`(0008, 0104)#4`). Ugly, but ten callers depend on it. **Do not touch this output.** The
only delta from `main` is that the working-diff de-identification special case goes away — with
sequences off, `(0012,0064)` is simply absent again, as on `main`.

Mode A rows carry **no** `depth` / `parent_key` / `item_index` / `row_kind` fields. Every consumer of
the new fields must therefore treat *absent* as "depth 0, no parent" — the shared helpers in Phase 2
run against both modes (the viewer's "Show Sequences" toggle flips between them at runtime) and must
not `KeyError` on a Mode A dict.

### Mode B — `include_sequences=True` (new)

SQ parents are emitted, and nested rows are keyed by **path**, not by occurrence counter:

```
(0012, 0064)                          ← SQ parent,  depth 0
(0012, 0064)[0]                       ← item node,  depth 1
(0012, 0064)[0].(0008, 0104)          ← leaf,       depth 2
(0012, 0064)[1].(0008, 0104)          ← leaf,       depth 2
(0018, 9346)[0].(0008, 0104)          ← leaf under a *different* sequence — now unambiguous
```

Grammar: `<root tag>` then zero or more `[<item index>].<tag>` segments; item nodes are the prefix
ending in `]`. Path keys kill the `#N` ambiguity outright — that is the whole point of Mode B, and
it is why the two modes may not share a key scheme.

**Row schema in Mode B** — every existing field (`tag`, `keyword`, `VR`, `value`, `is_private`,
`name`) plus:

| Field | Type | Meaning |
| --- | --- | --- |
| `depth` | `int` | 0 = root element |
| `parent_key` | `str \| None` | map key of the owning SQ or item row; `None` at root |
| `item_index` | `int \| None` | index within the parent sequence; `None` for non-item rows |
| `row_kind` | `"element" \| "sequence" \| "item"` | drives tree building and edit gating |

Use `row_kind`, not `VR == "SQ"` — item nodes have no VR. Dict insertion order must be
**depth-first**, so a consumer that ignores the new fields still renders something sane.

**SQ parent `value`:** `"3 item(s)"`, except sequences whose items carry `CodeValue`/`CodeMeaning`,
which use the CID 7050 summary (see Phase 1). **Item node `value`:** empty; `name` is `"Item 1"`
(1-based for display, while `item_index` stays 0-based).

## Phase 1 — Parser: sequence-aware tag walk

`src/core/dicom_parser.py`

- [x] Add `include_sequences: bool = False` to `get_all_tags()`; add it to the `_tag_cache` cache key
      alongside `include_private` / `privacy_mode` / `supplement_standard_tags`.
- [x] Replace `Dataset.iterall()` with an explicit recursive walk (`_walk(ds, depth, parent_key)`) so
      parentage is knowable. Mode A keeps emitting the flat `#N` keys from the same walk — the walk
      changes, the Mode A output does not.
- [x] Emit SQ parent + item rows only when `include_sequences=True`, per the contract above.
- [x] Generalize `_format_deidentification_method_code_sequence` → `_format_code_sequence_summary`,
      applied to any sequence whose items carry `CodeValue`/`CodeMeaning` (covers
      `DeidentificationMethodCodeSequence`, `ProcedureCodeSequence`, SR content items, …). Keep the
      current output format verbatim so the existing assertions hold.
- [x] Delete `DEIDENTIFICATION_METHOD_CODE_SEQUENCE_TAG` and its special case in `_consume_elem`.
- [x] Cap recursion at depth 16. On hitting the cap, emit one `row_kind="element"` row named
      `"<truncated: max depth reached>"` under the offending parent and stop descending — never
      recurse unbounded on a malformed dataset.

**Compatibility gate (blocking).** With `include_sequences=False`, output must be identical to `main`
for every file in `test-DICOM-data/`.

**Note (2026-07-11):** `test-DICOM-data/` is gitignored and not present in this checkout. The gate
was run against the checked-in fixtures in `tests/fixtures/dicom_rdsr/*.dcm` instead (the only real
`.dcm` files available) — snapshots dumped from `HEAD` (pre-walk-change) parser output live under
`tests/fixtures/mode_a_snapshot/`. If `test-DICOM-data/` is available in another environment, rerun
the same before/after dump there before merging.

Mechanism, in order — do this **before** editing `dicom_parser.py`, since step 1 must run against
unmodified code: (1) from a clean `main` checkout, dump `get_all_tags()` for each test file to a JSON
fixture under `tests/fixtures/mode_a_snapshot/`; (2) commit the fixture; (3) write the test that
re-runs the parser and asserts equality against it. If the fixture is generated *after* the parser
change, the gate proves nothing.

The ten callers this protects: `tag_export_writer`, `tag_export_union`, `tag_export_catalog`,
`tag_export_analysis_service`, `tag_export_dialog`, `tag_export_union_worker`,
`series_navigator_model`, `metadata_panel`, `tag_viewer_dialog`, `utils/dicom_utils`.

**Performance gate.** Time `get_all_tags(include_sequences=True)` on the largest enhanced/multi-frame
file available (check `test-DICOM-data/`; if none has deep functional groups, synthesize one with
~5k nested elements). If it exceeds **250 ms**, stop and report — Phase 2 then needs lazy population
(children built on first expand) rather than eager tree building, which is a materially bigger job.

## Phase 2 — Shared tree building + tag viewer dialog

### Tree shape (resolves the group-header question — both views use this)

Group headers **stay**. Nesting is added *below* them. Only **root-level** tags are bucketed into
groups; nested rows hang off their sequence parent and are **not** given a group bucket of their own
(a `Code Meaning` inside `(0012,0064)` appears under that sequence, not under Group 0008):

```
Group 0012                                  ← group header (depth-0 tags only)
  (0012, 0062)  Patient Identity Removed
  (0012, 0064)  De-identification Method Code Sequence   [SQ, collapsed by default]
      Item 1
        (0008, 0104)  Code Meaning  'Basic Application Confidentiality Profile'
      Item 2
        (0008, 0104)  Code Meaning  'Retain Longitudinal …'
```

### Shared helpers

`src/gui/metadata_table_model.py` — both views group and filter through this module, so the tree
logic belongs here, not duplicated in two widgets.

- [x] `group_metadata_tags_sorted` currently buckets **every** row by `tag_str[:5]`, which would
      bucket nested rows by their own group number. Change it to bucket **only `depth == 0`** rows,
      and add a helper that returns each row's ordered children from `parent_key`.
      (`get_metadata_tag_children` in `metadata_table_model.py`.)
- [x] `filter_metadata_tags_by_search` currently returns a filtered dict, which orphans a matching
      child whose sequence parent doesn't match. Change it to **retain the full ancestor chain** of
      every match (walk `parent_key` up, re-adding parents), so matches stay reachable.
- [x] Unit-test both helpers directly — they are pure functions and are the cheapest place to pin
      this behavior. (`tests/test_metadata_table_model.py`.)

### Dialog

`src/gui/dialogs/tag_viewer_dialog.py`

- [x] Call `get_all_tags(include_sequences=self.show_sequences)`.
- [x] Add a **"Show Sequences"** checkbox next to "Show Private Tags", **default on**; unchecking it
      restores today's flat Mode A view (the escape hatch for a huge dataset). It invalidates
      `_cached_tags` exactly like `_on_private_tags_toggled` does, and must join the `need_reload`
      condition in `_populate_tags` alongside `_cached_include_private` / `_cached_privacy_mode`.
- [x] Build nested `QTreeWidgetItem`s from `parent_key`, per the tree shape above.
- [x] Add "Expand All" / "Collapse All" buttons beside "Edit Selected Tag". Groups default expanded;
      **sequence parents default collapsed**. On an active filter, auto-expand ancestors of matches.
- [x] Edit gating: `_edit_tag_item` / `_on_item_double_clicked` currently reject non-editable rows by
      testing `parent() is None`, which no longer identifies them. Replace with an explicit allow-list
      — a row is editable **only if** `row_kind == "element"` **and** `depth == 0`. Everything else
      (group headers, SQ parents, `Item N` nodes, all nested rows) is read-only.
      `TagEditDialog.READ_ONLY_VR_TYPES` already contains `SQ`, so the dialog side is covered; the
      tree side is not.

  **PERF FINDING (2026-07-11) — resolved; Qt was never the bottleneck.**
  First measurement on the synthetic 2000-frame dataset (24,001 Mode B rows) put tree
  construction at **~19.7 s**, which looked like an inherent `QTreeWidgetItem` cost and
  pointed at a lazy-population redesign. It wasn't. Profiling showed the cost was
  `get_metadata_tag_children` **rescanning the entire tag dict once per parent** — O(n²),
  ~200M comparisons at 24k rows. Column resizing and `is_tag_edited` were both ruled out.

  Fixed by indexing children by `parent_key` in a single pass
  (`index_metadata_tag_children`) and threading that index through the recursive builder:
  **19.02 s → 0.24 s** for the same 24,001-row tree, a ~79x improvement.

  **Consequences:** eager population is fine — no lazy child construction, no row cap, and
  Phase 3 inherits the fix for free via the shared helpers. Pinned (not `xfail`) as
  `tests/test_tag_viewer_dialog.py::test_widget_population_perf_gate_enhanced_multiframe`
  with a 1 s budget. **Any future tree walker must use the index, not per-parent lookup** —
  `get_metadata_tag_children` remains for single lookups and carries a docstring warning.

### Pre-existing bug this plan must not inherit

`DICOMEditor.update_tag` (`src/core/dicom_editor.py:111`) resolves against
`self.get_target_dataset()[tag]` — a **root-level** lookup with no item path. Nested children are
already shown in both tag views today and are already double-click editable. So editing a nested-only
tag (e.g. `(0008,0104)` `Code Meaning`, which exists *only* inside a sequence in the file above)
does not edit the sequence item — it **writes a brand-new top-level element into the dataset**.
Occurrence-suffixed rows (`…#2`) fail `parse_tag` and silently return `False`, so only the first
occurrence corrupts, which is why this has gone unnoticed.

- [ ] Make nested rows read-only in **both** `tag_viewer_dialog` and `metadata_panel` (guard on
      `depth > 0`). This is a behavior *removal* — nested rows are editable today — so call it out in
      the CHANGELOG as a data-integrity fix, not a regression.
- [ ] Regression test: editing a nested-only tag (e.g. `(0008,0104)`, present only inside a sequence)
      must **not** add a root-level element to the dataset.
- [ ] Follow-up, separate work: path-addressed `update_tag` (the Mode B path keys make this
      tractable — `(0012, 0064)[0].(0008, 0104)` is exactly the address it needs) to make nested
      edits actually work.

## Phase 3 — Left pane: group collapse/hide

`src/gui/metadata_panel.py`. Groups are already collapsible `QTreeWidgetItem`s and the panel already
routes through the Phase 2 helpers, so it inherits nesting for free; what's missing is the controls,
the counts, and the defaults — mirroring `tag_export_dialog._create_tag_panel`.

- [x] Sequences **on** here too (same `get_all_tags(include_sequences=True)`), sequence parents
      collapsed by default. No "Show Sequences" checkbox in the side panel — the collapse controls
      are the noise management, and the panel is space-constrained.
- [x] Add "Expand All" / "Collapse All" buttons under the existing filter box (`metadata_panel.py`
      `_create_ui`, after `self.search_edit`).
- [x] Show a per-group child count on the group header (`Group 0008` → `Group 0008 — 24 tags`), as
      the export dialog does at `tag_export_dialog.py:464`. Count depth-0 rows only.
- [x] Hide groups with no visible children while a filter is active. **Note:** no port of
      `tag_export_dialog.py:514-527` was needed. That dialog hides pre-built rows; here
      `filter_metadata_tags_by_search` removes non-matching rows *before* the tree is built, so a group
      with no match (and no matching descendant) is never created. Pinned by
      `test_filter_leaves_no_empty_groups`.
- [x] Expand/collapse state is **session-scoped, not persisted to disk** (decided 2026-07-11):
      - Groups start **collapsed** on a fresh app launch. (This is a change — the left pane currently
        defaults every group expanded — and it matches the tag export dialog's existing behavior.)
      - Within a session, per-group state is remembered **across image and series switches**: collapse
        `Group 0028`, change series, and it stays collapsed.
      - Nothing is written to `ConfigManager`; closing and reopening the app returns to all-collapsed.
      - Hold the state in an instance dict on the panel keyed by group number
        (e.g. `self._group_expanded: dict[str, bool]`), applied in `_populate_tags` after the tree is
        rebuilt. Sequence-parent expansion is **not** remembered — SQ parents always start collapsed.

## Phase 4 — Tag export: opt-in sequences

- [x] Add an "Include sequences" checkbox to the export dialog tag panel (default **off**), beside
      the existing `include_missing_rows_checkbox`.
- [x] Thread the flag through `tag_export_union.py` → `tag_export_union_worker.py` →
      `tag_export_writer.py`. Default off keeps every current export byte-identical.
      (Also threaded through `tag_export_controller.py` and the dialog's variation-analysis
      preview, since those sit between the dialog and the writer in the actual call chain — not
      named individually in this bullet but required for the flag to reach the writer at all.)
- [x] When on, SQ parent columns export the summary string (item count / code summary) — one cell,
      no row explosion. Full hierarchical expansion into many rows is **out of scope**; note it as a
      follow-up if users ask. (Enforced at the union level: `union_tags_across_datasets` and
      `TagExportUnionWorker` drop any row with `depth != 0` when `include_sequences=True`, so nested
      item/leaf path-keyed rows never reach the tag picker — only root-level scalar tags and SQ
      parents are selectable.)
- [x] Remove `_EXPORTABLE_SEQUENCE_TAGS` from `tag_export_catalog.py`. Keep
      `DeidentificationMethodCodeSequence` (+ `PatientIdentityRemoved`, `DeidentificationMethod`) in
      `_CATALOG_KEYWORDS` — they stay valuable PS3.15 conformance rows — and let the SQ filter in
      `_resolve_catalog` consult the same `include_sequences` flag.
- [x] Update the module docstring, which currently asserts sequences are omitted.

## Phase 5 — Selectable sequence leaves in the export picker

**Why (decided 2026-07-11, user).** Phase 4 exports an SQ parent as one summary cell and drops
nested rows from the union entirely. For a *code* sequence the summary carries content; for every
other sequence it is `"1 item(s)"` — which looks like data while telling you nothing. Exporting only
code sequences meaningfully is not defensible, and the answer is not to widen the summary but to let
the user pick exactly the leaves they want. **The user's selection is the bound**, so there is no
explosion to design around — only a picker that must stay usable when a sequence is huge.

**Design.** In the export dialog's tag picker, a sequence parent becomes an expandable node holding
its `Item N` nodes and their leaves (the Phase 2 tree shape, which the picker does not yet render).
Every level is checkable. Sequence nodes are **collapsed by default**. A checked leaf becomes its
own export column, keyed by its Mode B path (`(0008, 2112)[0].(0008, 1155)`); the SQ parent stays
checkable on its own and still exports the summary cell.

- [x] Stop dropping `depth > 0` rows from the union — `src/core/tag_export_union.py:76` and
      `src/gui/dialogs/tag_export_union_worker.py:59`. They were dropped precisely to prevent the
      explosion that user-selection now prevents instead.
- [x] Render the nested tree in the picker (`_render_tag_tree`), sequence nodes collapsed by default,
      built through `index_metadata_tag_children` (no per-parent rescan).
- [x] Recursive checkbox propagation: check down to every descendant, tri-state up from any depth.
- [x] **Large-sequence warning** (`LARGE_SEQUENCE_LEAF_THRESHOLD = 200`): count stamped on the node,
      warning on expand.
- [x] **Wide-selection confirmation** (`LARGE_EXPORT_SELECTION_THRESHOLD = 1000`) in
      `_export_to_excel`, defaulting to No and aborting on decline. **Verified by inspection only —
      not covered by a test.** An end-to-end test that drives `_export_to_excel` hangs under pytest
      (something in that path blocks even with the file dialog stubbed and Qt offscreen, including in
      the branch that returns *before* the file dialog — likely a worker thread that never joins). A
      hanging test is worse than none, so it was removed rather than left in. **Follow-up: find what
      blocks `_export_to_excel` under test and cover this guard** — it is the only thing standing
      between a mis-click and a 24,000-column spreadsheet.
- [x] Writer/analysis needed **no path resolver** — they look tags up by key against the Mode B dict,
      as predicted. **But the writer did need a fix:** it wrote `tag_data['tag']` (the *canonical*
      tag) to the "Tag Number" column, which for a nested leaf discards the path — two leaves under
      different sequences both exported as `(0008, 0104)`, re-creating in the export the exact
      ambiguity Mode B exists to remove. `_tag_number_for_export` now emits the path key for
      `depth > 0` rows; Mode A rows carry no `depth` and are untouched, so sequences-off stays
      byte-identical.
- [ ] Instances whose item counts differ will legitimately lack some path keys (e.g. `[3]` on a
      2-item instance). That is the existing missing-tag case — confirm `include_missing_rows`
      handles it and does not emit a bogus blank vs. a real empty value.

**Verification**
- [ ] Selecting a nested leaf exports a column with that instance's real value, not `"N item(s)"`.
- [ ] `SourceImageSequence[0].ReferencedSOPInstanceUID` differing per instance is bucketed
      **varying** (this is the case that exposed the Phase 4 gap).
- [ ] Sequences **off** (default) is still byte-identical to `main` — the Phase 4 goldens must not move.
- [ ] Picker populates a 24k-leaf study without hanging; the warning fires.
- [ ] Instances with unequal item counts export without a spurious column or crash.

## Verification

Each phase must be green before the next starts — Phase 1's compatibility gate in particular is what
makes Phases 2–4 safe to write.

**Phase 1 — `tests/test_dicom_parser.py`**
- [x] Existing de-identification tests pass with `include_sequences=True` (they assert VR `SQ` + the
      compact summary; that output is preserved by design).
- [x] Mode A snapshot equality vs `main` across `test-DICOM-data/` — the blocking compat gate. (Run
      against `tests/fixtures/dicom_rdsr/*.dcm` in this checkout; see note above.)
- [x] Mode B on a worked-example-equivalent synthetic dataset (real `ResearchDeID` file not present
      in this checkout): a code sequence with multiple items is keyed by path and carries the right
      `parent_key` / `depth` / `item_index`; a second sequence's `Code Meaning` resolves under its
      own parent, not the first sequence's.
- [x] Recursion cap emits the truncation row on a synthetic 20-deep dataset rather than blowing the
      stack.
- [x] Perf gate: Mode B under 250 ms on the largest available fixture.

**Phase 2 — `tests/test_metadata_table_model.py` (new or extended) + viewer**
- [x] `group_metadata_tags_sorted` buckets only depth-0 rows.
- [x] `filter_metadata_tags_by_search` retains ancestors: searching `"Retain Device Identity"` keeps
      `(0012,0064)` and its `Item 3` in the result.
- [x] Nested rows and SQ/item rows reject edits; the nested-only-tag regression test above passes.
- [x] Perf gate: eager widget population of the 24k-row synthetic tree is **0.24 s**, inside the 1 s
      budget, after fixing the O(n²) child lookup — see the PERF FINDING note above.

**Phase 3 — `tests/test_metadata_panel.py`** (9 tests, all green)
- [x] Group counts (depth-0 only), Expand/Collapse All, no-empty-groups-on-filter.
- [x] Session expansion memory: survives a `set_dataset` series switch; a fresh panel starts
      all-collapsed; an untouched group stays collapsed (distinguishes real memory from expand-all).
- [x] Nested/SQ/item rows reject edits; a root-level scalar is still editable.
- [x] Perf gate: **287 ms** to populate the 24k-row synthetic tree — the shared child index carried
      over, no O(n²) regression.

**Phase 4**
- [x] Export with "Include sequences" **off** is byte-identical to `main` for a saved preset.
      Verified via `tests/test_tag_export_sequences_flag.py`: CSV/TXT golden fixtures under
      `tests/fixtures/tag_export_golden/` were dumped from a `git stash`-clean pre-Phase-4 checkout
      (HEAD `17d1d32`) for a fixed dataset + tag selection (a scalar tag, the
      `DeidentificationMethodCodeSequence` SQ tag, a flattened nested `CodeMeaning` leaf, and a
      missing tag), then compared byte-for-byte against the post-change writer output — identical.
      XLSX cell values (not raw bytes, since openpyxl embeds a fresh `docProps/core.xml` timestamp
      per save) were also confirmed identical between the two runs.

**Whole slice**
- [x] Full `pytest` from `.venv`: **1877 passed, 18 skipped**, 0 failed, 0 xfail (baseline was 1866
      passed / 18 skipped before this Phase 4 pass; +11 net new tests, no regressions).
- [ ] Manual smoke per `dev-docs/orchestration/AGENT_SMOKE.md`: load an enhanced multi-frame study
      (functional groups) and an SR from `test-DICOM-data/pyskindose_samples/`; confirm the viewer
      opens without a stall, sequences expand, the filter reaches nested values, and a root-level
      scalar edit still round-trips.
- [ ] `CHANGELOG.md` + `src/version.py` patch bump — note the nested-edit read-only change as a
      data-integrity fix.

## Open questions

1. ~~**Export default.**~~ **Resolved 2026-07-11: off by default.** "Include sequences" stays opt-in
   in the export dialog, keeping existing exports and saved presets byte-identical. The *viewer*
   shows everything; the *export* is the deliberate exception.
2. ~~**Nested tag editing.**~~ **Resolved 2026-07-11: no.** `update_tag` is root-level only. Nested
   rows go read-only this pass, and the existing corruption path gets a regression test. See
   "Pre-existing bug" in Phase 2.
3. ~~**Row cap / eager vs lazy.**~~ **Resolved 2026-07-11 — eager, no row cap, no lazy population.**
   Mode B parses 24,001 rows in 85 ms, and the tag tree builds in 0.24 s once the O(n²) child lookup
   is indexed (see the PERF FINDING in Phase 2). Both are inside budget, so nothing is deferred and
   nothing is capped. The one standing rule: **tree walkers must use `index_metadata_tag_children`,
   never per-parent rescans.**

## Not doing

- No new branch: `sequence-tag-viewer` is already checked out and is the right name for this work.
- `launch.command`: already committed executable (`100755`, commit 7c6f2b3). No action.
