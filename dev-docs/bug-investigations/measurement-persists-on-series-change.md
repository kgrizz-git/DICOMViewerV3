# Bug: Completed Measurement Persists After Switching Series

**Reported:** 2026-03-18  
**Symptom:** Draw a measurement (both clicks placed, fully committed) in Window X on Series A. Click a different series thumbnail in the navigator to load Series B into Window X. The old measurement line remains visible on the new series.

---

## How Measurements Are Cleared (The Intended Path)

### Series loading via navigator

1. Navigator thumbnail click emits `series_selected(series_uid)`.
2. Wired to `DICOMViewerApp._on_series_navigator_selected` → `FileSeriesLoadingCoordinator.on_series_navigator_selected(series_uid)` → `assign_series_to_subwindow(focused_subwindow, series_uid, 0)`.
3. `assign_series_to_subwindow` calls `slice_display_manager.display_slice(dataset_B, ...)` on the focused subwindow's manager.
4. Inside `display_slice` (`src/core/slice_display_manager.py`):
   - `is_new_study_series = view_state_manager.is_new_study_or_series(dataset_B)` — compares `"{StudyInstanceUID}_{composite_series_key}"` for the incoming dataset against `view_state_manager.current_series_identifier` (set from the previous series A).
   - If `True`, `view_state_manager.set_current_series_identifier(series_identifier_B)` updates the stored identifier.
   - Later (around line 1095): `measurement_tool.clear_measurements(self.image_viewer.scene)` is called.
   - Still later (around line 1109): `display_measurements_for_slice(dataset_B)` re-displays any measurements stored for the new series (none, since it's brand new).

### `clear_measurements` internals (`src/tools/measurement_tool.py`)

```python
def clear_measurements(self, scene) -> None:
    for measurement_list in self.measurements.values():
        for measurement in measurement_list:
            if measurement.scene() == scene:                   # removes group from scene
                if measurement.text_item is not None and measurement.text_item.scene() == scene:
                    scene.removeItem(measurement.text_item)    # removes label
                measurement.hide_handles()                     # removes handles
                scene.removeItem(measurement)                  # removes group (line)
    self.measurements.clear()                                  # wipes entire dict
```

### Measurement storage

Measurements are stored in `MeasurementTool.measurements` as: `Dict[(study_uid, series_uid, instance_identifier), List[MeasurementItem]]`.  
`text_item` (the distance label) and `MeasurementHandle`s are **separate, independent scene items** — not children of the `QGraphicsItemGroup`. This means three separate `scene.removeItem` calls are needed per measurement.

---

## Why the Clear Should Always Work (and Doesn't)

There is **no obvious functional gap** in the intended path — if `is_new_study_series` is `True` and the measurement is correctly stored under the right key, `clear_measurements` should fully remove it. Therefore the bug is being triggered by one (or more) of the following failure modes.

Two additional code facts narrow the field:

- `ImageViewer` creates its `QGraphicsScene` once during initialization and reuses it; there is no normal series-switch path that swaps in a different scene object.
- `assign_series_to_subwindow()` updates `subwindow_data[idx]` with the new study/series/slice **before** calling `slice_display_manager.display_slice(...)`, so a stale redisplay would have to come from a callback using stale manager/context references rather than from the main assignment path itself.

---

## Hypotheses

### H1 — `is_new_study_series` returns `False` *(most likely first suspect)*

`is_new_study_series` returns `True` only when the computed series identifier string has changed:

```python
# view_state_manager.py
def get_series_identifier(self, dataset):
    study_uid = getattr(dataset, 'StudyInstanceUID', '')
    composite_series_key = get_composite_series_key(dataset)   # SeriesInstanceUID_SeriesNumber or SeriesInstanceUID
    return f"{study_uid}_{composite_series_key}"

def is_new_study_or_series(self, dataset):
    if self.current_series_identifier is None:
        return True
    new_id = self.get_series_identifier(dataset)
    return new_id != self.current_series_identifier
```

**Failure mode:** If Series A and Series B happen to produce the *same* identifier string (same `StudyInstanceUID`, same `SeriesInstanceUID`, same `SeriesNumber`), `is_new_study_series` returns `False` → `clear_measurements` is **never called** → measurement remains.

This can happen with:
- Two series from the same study where the organizer split them but both slices share a `SeriesInstanceUID` (e.g., multi-frame with an overlapping series number).
- Any DICOM where `SeriesNumber` is missing or identical across two series.

Also watch: `view_state_manager.current_series_identifier` is updated **inside** the same `if is_new_study_series:` block (`set_current_series_identifier`), which means a second call to `display_slice` for the same dataset (e.g., redisplays triggered by `store_initial_view_state`) will correctly return `False` and not double-clear. That's correct behaviour. But it also means that if `is_new_study_series` was wrongly `False` on the **first** call, no clearing ever happens.

---

### H2 — scene attachment mismatch prevents removal *(subtle but plausible)*

`clear_measurements` iterates `self.measurements.values()` and for each measurement checks `measurement.scene() == scene`. If `measurement.scene()` is `None`, that check fails silently (None ≠ scene), so the item is *not* removed from the Qt scene, even though `self.measurements.clear()` wipes it from the dict. After `clear_measurements` returns: the dict is empty (correct), **but the item is still visible in the scene** (bug).

How could `measurement.scene()` be `None`? If Qt has already detached the item from the scene between when it was added and when `clear_measurements` runs. A full scene replacement is unlikely here because `ImageViewer` holds a long-lived scene, so the more realistic variant is: the `MeasurementItem` or its separate `text_item` became detached or attached to a different scene object than the one passed into `clear_measurements`.

The `text_item` is an independent scene item. Note the condition is:
```python
if measurement.text_item is not None and measurement.text_item.scene() == scene:
```
If `measurement.scene() == scene` passes but `measurement.text_item.scene()` is `None`, the text label remains visible even if the line group is removed. The user would then see a floating distance label with no line — though the user reports "the measurement line was still shown", so this is probably not solely responsible, but could combine with H2.

---

### H3 — A second `display_measurements_for_slice` call re-adds the old measurement after the clear

If anything triggers a redisplay **after** `clear_measurements` but **before** the subwindow fully settles, and the redisplay somehow uses the *old* series context (stale `current_series_uid`, stale dataset, etc.), `display_measurements_for_slice` could be called with the Series A key and re-add the measurement.

Candidate trigger: `view_state_manager.store_initial_view_state`, which is fired via `QTimer.singleShot(100, ...)` during initial file load and calls `_redisplay_current_slice(preserve_view=True)` when `window_level_defaults_set` is already set for a revisited series. This timer **is not** fired by `assign_series_to_subwindow`, but it **is** fired from `main.py._display_slice` (if `initial_zoom is None`). Whether it fires depends on prior state.

Less likely but possible: `update_roi_statistics`, histogram updates, or any other post-display hook that inadvertently calls a display path. Because `assign_series_to_subwindow()` writes the new series into `subwindow_data` before display, a stale redisplay would most likely come from a callback that is still bound to an older focused subwindow / manager context rather than from the normal assignment state.

---

### H4 — `undo_redo_manager` re-adds the measurement *(very unlikely, included for completeness)*

`handle_measurement_finished` in `MeasurementCoordinator` calls `undo_redo_manager.execute_command(MeasurementCommand("add", ...))` after `finish_measurement`. `execute_command` is synchronous, and `MeasurementCommand.execute()` checks `if measurement_item not in self.measurements[key]` before re-adding, so it correctly skips double-add at creation time. No later timer or queued callback is involved in this add path. This makes H4 weaker than H1/H2/H3 unless some later undo/redo or composite command is unexpectedly firing.

---

### H5 — not an in-progress temporary line

Because you explicitly completed the second click, this is probably **not** the temporary measurement-preview line (`current_line_item` / `current_text_item`) being left behind. The finish path converts the preview into a stored `MeasurementItem` and clears the temporary references:

```python
self.measuring = False
self.start_point = None
self.current_end_point = None
self.current_line_item = None
self.current_text_item = None
```

That does not fully eliminate a finish-path bug, but it means the investigation should focus on the committed-measurement storage/removal path rather than the preview path.

---

## Suggested Debugging

The repo now has a dedicated flag for this investigation: `DEBUG_MEASUREMENT_SERIES` in `src/utils/debug_flags.py`. Turn that on, reproduce once, and inspect the console output.

### Step 1 — Verify whether `is_new_study_series` fires

Add to `slice_display_manager.py`, inside `display_slice`, just before the `if is_new_study_series:` block at ~line 368:

```python
print(f"[DBG-MEAS] display_slice: is_new_study_series={is_new_study_series}")
print(f"[DBG-MEAS]   incoming series_identifier={series_identifier}")
print(f"[DBG-MEAS]   stored  series_identifier={self.view_state_manager.current_series_identifier}")
print(f"[DBG-MEAS]   measurements dict keys: {list(self.measurement_tool.measurements.keys())}")
print(f"[DBG-MEAS]   measurements counts: {[(k, len(v)) for k, v in self.measurement_tool.measurements.items()]}")
```

And just before the `clear_measurements` call at ~line 1095:

```python
print(f"[DBG-MEAS] About to call clear_measurements. Scene id={id(self.image_viewer.scene)}")
print(f"[DBG-MEAS]   measurements to clear: {[(k, len(v)) for k, v in self.measurement_tool.measurements.items()]}")
```

If `is_new_study_series=False` is printed when you switch series, **H1 is strongly favored**. If `is_new_study_series=True` but the dict shows no measurements, the clearing is working but the measurement is coming back (→ H3).

---

### Step 2 — Verify `clear_measurements` actually removes scene items

Add to `MeasurementTool.clear_measurements` in `src/tools/measurement_tool.py`:

```python
def clear_measurements(self, scene) -> None:
    print(f"[DBG-MEAS] clear_measurements called. scene id={id(scene)}")
    for measurement_list in self.measurements.values():
        for measurement in measurement_list:
            m_scene = measurement.scene()
            t_scene = measurement.text_item.scene() if measurement.text_item else None
            print(f"[DBG-MEAS]   item: measurement.scene()={id(m_scene) if m_scene else None}, "
                  f"text.scene()={id(t_scene) if t_scene else None}, "
                  f"target scene={id(scene)}, match={m_scene == scene}")
            if measurement.scene() == scene:
                ...  # existing code
    self.measurements.clear()
    print(f"[DBG-MEAS] clear_measurements done.")
```

If you see `match=False` with `measurement.scene()` being `None` or a different id — **H2 is strongly favored**.

---

### Step 3 — Verify no redisplay occurs after the clear

Add to `SliceDisplayManager.display_measurements_for_slice` at `src/core/slice_display_manager.py`:

```python
def display_measurements_for_slice(self, dataset):
    ...
    import traceback
    print(f"[DBG-MEAS] display_measurements_for_slice called for series={series_uid[:20]}, instance={instance_identifier}")
    print(f"[DBG-MEAS]   measurements in dict for this key: {len(self.measurement_tool.measurements.get((study_uid, series_uid, instance_identifier), []))}")
    # traceback.print_stack(limit=8)  # Uncomment to see call stack
```

If this prints a non-zero count for the *old* series key after switching — **H3 is strongly favored**. Uncomment the traceback to find the caller.

---

### Step 4 — Confirm measurement key matches what `clear_measurements` iterates

Add a check inside `handle_measurement_finished` (`src/gui/measurement_coordinator.py`) after `finish_measurement`:

```python
measurement = self.measurement_tool.finish_measurement(self.image_viewer.scene)
if measurement is not None:
    print(f"[DBG-MEAS] Measurement stored. Tool.current_study_uid={self.measurement_tool.current_study_uid}, "
          f"series_uid={self.measurement_tool.current_series_uid}, "
          f"instance={self.measurement_tool.current_instance_identifier}")
    print(f"[DBG-MEAS]   All keys in measurements dict: {list(self.measurement_tool.measurements.keys())}")
```

This verifies the measurement is stored under the expected key.

---

## Files to Investigate

| File | Lines | What to check |
|---|---|---|
| `src/core/slice_display_manager.py` | ~364–368, ~1082–1101 | `is_new_study_series` detection, `clear_measurements` call |
| `src/tools/measurement_tool.py` | `clear_measurements` (~480) | Per-item `scene()` check |
| `src/core/view_state_manager.py` | `is_new_study_or_series` (201), `get_series_identifier` (185) | Identifier comparison |
| `src/utils/dicom_utils.py` | `get_composite_series_key` (415) | Key construction — could two different series produce the same key? |
| `src/gui/measurement_coordinator.py` | `handle_measurement_finished` (~104) | Storage key used |
| `src/core/file_series_loading_coordinator.py` | `assign_series_to_subwindow` (~593) | Any deferred redisplay calls |

---

## Current Read on Likelihood

1. **H1** is still the first thing to prove or eliminate. It is the cleanest explanation for "old measurement stays visible after switching series" because the clear path is guarded entirely by `is_new_study_series`.
2. **H3** is next if H1 falls over. The bug would then be "clear ran, but a later display path put the old measurement back."
3. **H2** is plausible but narrower than first described because the scene itself is stable; what needs proving is an item attachment mismatch, not a whole-scene replacement.
4. **H4** is low probability.
5. **H5** is mainly ruled out by the fact that the measurement was fully completed.

---

## Confirmed Root Cause From Debug Output

The debug trace narrowed this down precisely:

1. The measurement is stored correctly after the second click:
    - `measurement_finished after finish_measurement ... count=1,attached=1`
2. Series-change detection is also correct:
    - switching from `_563_10` to `_702_21` logs `is_new_study_series=True`
3. Scene removal is correct:
    - `clear_measurements item ... match=True`
    - `scene_measurement_items_after=0`
4. The actual bug is that `clear_measurements()` ends with `self.measurements.clear()`, which wipes the stored per-series dictionary.

That means the old measurement disappears from the new series for the right reason, but it can never come back when returning to the original series because its stored data has already been deleted.

### Fix direction

The correct behavior is:

- On series switch: remove measurement graphics from the current scene.
- Do **not** delete stored measurements for other series/slices.
- When returning to a series, `display_measurements_for_slice()` should reattach that series/slice's stored items.

The implemented fix changes the new-series path in `SliceDisplayManager.display_slice()` to remove only non-current scene items via `clear_measurements_from_other_slices(...)` instead of calling `clear_measurements(...)`.
