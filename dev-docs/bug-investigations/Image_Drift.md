### Image drift during slice navigation – debug notes

This document summarizes what was observed in the runtime debug logs for the “image seems to pan up or left while scrolling slices” issue, plus hypotheses and follow‑up debugging ideas.

---

### 1. What the logs showed

- **Initial series load behavior**
  - When a new series is first displayed, `SliceDisplayManager.display_slice` logs show:
    - `preserve_view: false`, `is_new_study_series: true`
    - After `set_image` and `fit_to_view(center_image=True)`, zoom changes (e.g. `1.0 → 1.52` or `1.0 → 0.60`) and scrollbars move from `(0, 0)` to some non‑zero values.
  - This is expected: `fit_to_view` is supposed to pick an initial zoom and center the image.

- **Arrow‑key (Up/Down) navigation – early runs**
  - For many Up‑arrow presses in the earlier part of the log:
    - `image_viewer.keyPressEvent:Key_Up` entries (H3) show `zoom` and scrollbars (`h_scroll`, `v_scroll`) that stay stable over long stretches.
    - Matching `display_slice:before_set_image` / `display_slice:after_set_image` (H1) entries for successive `current_slice_index` values show the same `h_scroll`/`v_scroll` before and after each `set_image` call.
  - In those sequences, the viewport center was effectively stable while slices changed, so the apparent motion was mostly anatomical difference between slices.

- **Later reproduction – confirmed horizontal drift**
  - In the later section of the log (the large reproduction run), the pattern changes:
    - Vertical values stay fixed:
      - `saved_scene_center_y` is almost constant (≈ `13.0946` in the tail section).
      - `v_scroll` is constant at `-139`.
    - Horizontal values drift steadily:
      - `saved_scene_center_x` in H4 logs increases monotonically (e.g. from ≈ `391` up past `500`).
      - `h_scroll` also climbs step‑by‑step (e.g. `107 → 200+` over many slice changes).
    - This happens while:
      - `zoom` is constant at `0.763671875`.
      - Events are a mix of:
        - `image_viewer.keyPressEvent:Key_Up` (H3; arrow‑key slice navigation),
        - `image_viewer.wheelEvent` with `scroll_wheel_mode: "slice"` (H2; wheel‑based slice navigation),
        - Paired `set_image:before_preserve_view` / `set_image:after_preserve_view` (H4; preserve‑view logic),
        - `display_slice:before_set_image` / `display_slice:after_set_image` (H1).
  - Conclusion from this region:
    - The viewport is **actually drifting horizontally** (scrollbar and scene‑center values move) while the user scrolls slices, even though zoom does not change and `preserve_view` is `True`.
    - Vertical pan is stable; the bug is predominantly horizontal drift.

---

### 2. Suspected root cause (most likely)

**High‑level summary:**

- `ImageViewer.set_image(..., preserve_view=True)` saves a **scene‑space center point** (`saved_scene_center`) before rebuilding the scene, then re‑centers on that same numeric point after changing the scene rect and margins.
- `set_image` recomputes `sceneRect` on **every slice** based on:
  - The new image’s bounding rect (size/position),
  - The viewport size,
  - Extra margins to build an “expanded” scene rect.
- Because this recomputation can change the origin and width of the scene rectangle from slice to slice, the *same* `saved_scene_center_x` value no longer corresponds to the same visual point in the image on the next slice.
- When `centerOn(saved_scene_center)` is called with the stale scene coordinate:
  - Qt adjusts scrollbars so that the requested scene point appears in the center of the viewport,
  - But that point has effectively slid to the right within the new scene rectangle,
  - So the scrollbars—and the apparent pan—gradually walk rightward over many slices.

In short: **we’re preserving an absolute scene X coordinate while repeatedly reshaping the scene’s horizontal extent**, so the view “drifts” even though we intend to preserve pan.

The logs in the tail clearly match this story:

- `saved_scene_center_y` and `v_scroll` are constant → vertical coordinate system is effectively stable for the region where the user is scrolling.
- `saved_scene_center_x` and `h_scroll` both increase monotonically, even though `zoom` is fixed and the user is just scrolling slices → the horizontal coordinate system is being “stretched/shifted” each slice, and the preserved center ends up sliding.

---

### 3. Concrete hypotheses to validate

**H1 – Scene rect / margin recomputation causes horizontal re‑centering**

- Hypothesis:
  - The logic in `ImageViewer.set_image` that:
    - Computes `image_rect = image_item.boundingRect()`,
    - Calculates `scene_width` / `scene_height` based on image width vs. viewport width,
    - Chooses margins and sets `scene.setSceneRect(expanded_rect)`,
  - Produces **slightly different horizontal margins or rect origins** per slice (e.g., due to small differences in image size, rounding, or how the image is positioned in the scene).
  - When we then call `centerOn(saved_scene_center)` using a point computed in the *previous* scene configuration, the viewer is forced to adjust scrollbars, which manifests as horizontal drift.

- How to check (additional debugging):
  - Add logging in `set_image` around the scene‑rect / margin calculation, keyed by slice index:
    - `image_rect.x()`, `image_rect.width()`
    - `expanded_rect.x()`, `expanded_rect.width()`
    - `viewport.width()`
    - Computed `margin_x`
  - Correlate changes in:
    - `margin_x`, `expanded_rect.x()`, and
    - `saved_scene_center_x`, `h_scroll`
  - If we see:
    - `margin_x` or `expanded_rect.x()` shifting slightly to the left each slice, and
    - `h_scroll` increasing correspondingly,
    - then H1 is strongly confirmed.

**H2 – Saved center is anchored to old scene rect rather than the image**

- Hypothesis:
  - `saved_scene_center` is computed in scene coordinates using:
    - `saved_scene_center = mapToScene(viewport_center)`,
  - Then reused after a different `expanded_rect` has been applied,
  - Without re‑projecting it into coordinates tied to:
    - The current `image_rect`, or
    - A normalized horizontal fraction within the image.
  - As the scene rect grows or shifts, the “same” scene X coordinate falls over a different part of the expanded rect, so the camera must move to keep it centered.

- How to check:
  - For a specific slice index `k`, log:
    - `saved_scene_center_x` and `image_rect` **before** the change to `sceneRect`,
    - `image_rect` for the **next** slice,
    - `saved_scene_center_x - image_rect.center().x()` (Δ to image center) or the normalized fraction:
      - `u = (saved_scene_center_x - image_rect.left()) / image_rect.width()`.
  - If we see that:
    - Δ or `u` drifts over slices even when user doesn’t pan horizontally,
    - while `current_zoom` stays constant,
    - then we’ve shown that we’re not preserving a consistent location in image space; we’re preserving a location in a changing scene space.

**H3 – Series‑wide vs per‑slice scene rect**

- Hypothesis:
  - We might be over‑fitting the scene rect to each slice’s bounding rect. If there are tiny per‑slice differences (e.g. due to resampling, windowing, or subtle ROI overlays), the scene rect may “breathe” horizontally even though all slices are notionally the same size.
  - If the scene rect were fixed once per series, `saved_scene_center` would be far more stable.

- How to check:
  - Log:
    - `image_rect.width()` and `image_rect.height()` for each slice index,
    - Alongside `expanded_rect.x()` and `expanded_rect.width()`.
  - If there are small but non‑zero differences in width or in `expanded_rect.x()` between slices where no user pan is happening, that would explain why `h_scroll` must creep to keep the same scene coordinate centered.

---

### 4. Ideas for future debug instrumentation

If we want to capture one more high‑signal run before changing code, the following logs would help pin it down:

- **In `ImageViewer.set_image` (preserve_view branch):**
  - Slice index (via a callback from `SliceDisplayManager` or current dataset).
  - Before scene rect change:
    - `saved_scene_center_x/y`
    - `image_rect` of the *current* image item (`x`, `width`, `center().x()`).
  - After new image is set and new `expanded_rect` is computed:
    - New `image_rect`,
    - `expanded_rect.x()` and `expanded_rect.width()`,
    - `margin_x`,
  - After `centerOn(...)`:
    - `h_scroll`, `v_scroll`,
    - Recomputed `saved_scene_center_x/y` from `mapToScene(viewport_center)`.

- **In `SliceDisplayManager.handle_slice_changed`:**
  - Log `slice_index` together with:
    - The same `h_scroll`/`v_scroll`,
    - A flag for whether this slice change came from:
      - Arrow key,
      - Wheel event,
      - Cine, etc. (if relevant in the future).

With that additional data, we can:

- Verify exactly how `expanded_rect` differs slice‑to‑slice,
- See whether the drift is proportional to the accumulated change in margins/scene origin,
- And confirm whether preserving a relative image position (instead of an absolute scene X) stabilizes the view.

---

### 4b. Additional hypotheses (agent review, 2026-03-16)

This section was added after reviewing the actual code in `ImageViewer.set_image`.

---

**Comments on H1 / H2 / H3 as written**

H1, H2, and H3 are really three views of the same mechanism. It is worth narrowing the scope:

- For a normal DICOM series, all slices have the same pixel dimensions, so `image_rect.width()` and `image_rect.height()` should be identical on every slice. That means `scene_width` and `scene_height`—and therefore `margin_x`, `margin_y`, and `expanded_rect`—will only change if `viewport_width_pixels` or `viewport_height_pixels` changes between calls. H3 ("per‑slice scene rect breathing") should therefore be a non‑event for normal DICOM slices. The suggested debug log for H3 (comparing `image_rect.width()` per slice) is still cheap to add and useful to rule out definitively.

- H1 and H2 become operative only when `viewport_width_pixels` (or height) changes between consecutive `set_image` calls. The most likely cause of that change is a scrollbar appearing or disappearing (see H6 below).

---

**H4 – `resetTransform()` + `scale()` intermediate state**

- Hypothesis:
  - The restore sequence inside `set_image` is:
    ```
    self.resetTransform()
    self.scale(saved_zoom, saved_zoom)   # AnchorViewCenter
    self.centerOn(saved_scene_center)
    ```
  - `resetTransform()` resets the transform matrix to identity (zoom → 1.0) but does **not** reset the scrollbar positions. The scrollbars remain at their "before-reset" integer values.
  - After `resetTransform()`, the viewport center in scene coordinates is **not** `saved_scene_center`; it is whatever scene point the old scrollbar values now map to at zoom = 1.0 (i.e., a point far from where the user was looking, because the scale has changed but scrollbars haven't moved yet).
  - `scale(saved_zoom, saved_zoom)` with `AnchorViewCenter` then re‑scales the view so that ***this wrong intermediate scene point*** stays at the viewport center. Scrollbars are adjusted by Qt to satisfy the anchor.
  - `centerOn(saved_scene_center)` then must correct the position a second time, setting scrollbars to new integer values.
  - The round‑trip introduces two floating‑point → integer conversions instead of one, and any systematic rounding error is compounded.
  - **By contrast, calling `self.setTransform(QTransform.fromScale(saved_zoom, saved_zoom))` directly would skip the intermediate zoom‑1.0 state and leave scrollbars at their current position, after which a single `centerOn()` call completes the restore. This should be at least as stable as the current code, and likely more so.**

- How to check:
  - Replace the `resetTransform()` + `scale()` pair with `self.setTransform(QTransform.fromScale(saved_zoom, saved_zoom))` on a debug build and repeat the long-scroll reproduction. If drift disappears or is significantly reduced, H4 is confirmed.

---

**H5 – `centerOn()` integer scrollbar quantization accumulates**

- Hypothesis:
  - Qt's `centerOn(QPointF)` internally converts the scene coordinate to a scrollbar integer value. The conversion is approximately:
    ```
    h_scroll_value = round(scene_x * h_scale) − viewport_width/2
    ```
    where `h_scale` is the horizontal scale factor (zoom × device pixel ratio).
  - With `zoom = 0.763671875` (the value observed in the logs—a factor that arises from discrete zoom steps), `scene_x × 0.763671875` is almost never an exact integer. Qt rounds to the nearest integer.
  - If the rounding error is consistently biassed in one direction (e.g., scene_x × zoom always lands at `n + 0.4`, always rounded down), the restored scrollbar is consistently 1 pixel low, and the ***next*** `mapToScene(viewport_center)` captures a scene center that is slightly to the right of where the user was. On the next slice, this slightly‑shifted center becomes the new `saved_scene_center`, and the offset grows by 1/zoom ≈ 1.3 scene units per slice.
  - Crucially, the biasing direction depends on the fractional part of `scene_x × zoom`. Because the scene is typically centred on an integer pixel count and the zoom is a power‑of‑two–aligned fraction, the fractional part can be nearly constant across all slices for a given pan position, causing a consistent (not random) rounding direction—and hence accumulation.
  - This mechanism can produce slow, monotonic drift that is proportional to the number of slices scrolled, even when the scene rect is perfectly stable.

- Why vertical is immune:
  - In the reproduction logs, `v_scroll` and `saved_scene_center_y` are effectively constant, while the horizontal values drift. This is consistent with H5: the vertical scene coordinate at the pan position happens to have a fractional part near 0 or 0.5 after multiplication by zoom (so rounding alternates +0/−0 and averages out), while the horizontal fractional part is consistently biassed.

- How to check:
  - Log `(saved_scene_center_x * zoom) % 1.0` (the fractional part of the raw scrollbar calculation) for a long run. If it is consistently above or below 0.5, this confirms the systematic bias.
  - As a direct fix candidate: replace `centerOn(saved_scene_center)` with explicit scrollbar value save/restore:
    ```python
    # Save before scene change:
    saved_h = self.horizontalScrollBar().value()
    saved_v = self.verticalScrollBar().value()
    # ...scene and transform changes...
    self.horizontalScrollBar().setValue(saved_h)
    self.verticalScrollBar().setValue(saved_v)
    ```
    This bypasses the float→int conversion entirely. It is valid **only** when the scene rect and zoom are guaranteed to be the same before and after (which is the normal case for same‑series slice scrolling), so add a guard or comment to that effect.

---

**H6 – `ScrollBarAsNeeded` vertical scrollbar appearance/disappearance changes `viewport_width_pixels`**

- Hypothesis:
  - The viewer uses `ScrollBarPolicy.ScrollBarAsNeeded` for both axes. This means a scrollbar can appear or disappear between two consecutive `set_image` calls whenever the pan position or scene rect changes enough to require/not require scrolling.
  - If the **vertical** scrollbar appears between slice N and slice N+1, `self.viewport().width()` shrinks by the scrollbar width (~15–20 px on most platforms).
  - In `set_image`, `viewport_width_pixels = self.viewport().width()` is read **before** `scene.setSceneRect()`. At that moment, the new vertical scrollbar is visible (Qt may already have done this layout pass when the new pixmap was added to the scene), so the narrower width is read.
  - The scene‑width formula for images smaller than the viewport is:
    ```
    scene_width = 3 * image_width + 2 * viewport_width_pixels
    ```
    With `viewport_width_pixels` 15 pixels smaller, `scene_width` shrinks by 30, `margin_x` shrinks by 15, and `expanded_rect.x()` moves 15 pixels to the **right** (less negative).
  - `centerOn(saved_scene_center_x)` now needs the scrollbar to move to the right to put the same scene X at the viewport center, because the scene rect's left edge has moved right. This causes a single step increase in `h_scroll`.
  - If this happens on many slices (the vertical scrollbar toggles frequently near its appearance threshold), `h_scroll` accumulates with each toggle, matching the observed pattern.
  - The formula is **asymmetric**: if the vertical scrollbar disappears (viewport width grows), h_scroll would decrease. But if the scrollbar predominantly appears (user is panning down), drift could be one-sided.

- How to check:
  - Log `self.verticalScrollBar().isVisible()` (or its range) at the start of `set_image` alongside `viewport().width()`. Look for changes in scrollbar visibility that correlate with jumps in `h_scroll`.
  - Quickest isolation test: temporarily set both scroll bar policies to `ScrollBarAlwaysOff`. If all horizontal drift disappears, H6 is directly confirmed.
  - A second test: set both policies to `ScrollBarAlwaysOn`. If drift goes away (or changes character), the viewport‑size feedback is proven; the visible scrollbars are "always on" so their presence/absence no longer changes the viewport dimensions.

---

**H7 – `scene.invalidate()` / `viewport.update()` before `viewport.width()` is read**

- Hypothesis:
  - In `set_image`, the code calls `self.scene.invalidate(...)` and `self.viewport().update()` **before** reading `viewport().width()`. These calls queue deferred Qt repaints, but they may also trigger an immediate layout pass on some platforms/versions (especially when the scene rect is changing due to the new image size).
  - If Qt flushes pending resize/layout events during `viewport().update()`, the scrollbar visibility might change before `viewport_width_pixels` is read, causing it to read a different width than was "intended." This is closely related to H6 but is a distinct timing path.

- How to check:
  - Move the `viewport_width_pixels = self.viewport().width()` read to **before** the `scene.invalidate()` and `viewport.update()` calls (i.e., immediately after saving the view state). If drift changes, the deferred-event timing is involved.

---

### 5. Why the bug is rare and hard to reproduce

The hypotheses above each require specific conditions to trigger visible drift:

- H5 (quantization): The rounding bias is consistent only at certain pan positions. Near the image center the rounding typically averages out; near an edge, it may be consistently biassed. The user must be panned off-center AND scrolling many slices in one continuous run.
- H6 (scrollbar toggle): The vertical scrollbar must be near its appearance threshold. This depends on the exact pan position, zoom level, and window height. Resizing the window slightly, changing the zoom, or panning vertically past the threshold locks or unlocks the scrollbar and changes the drift behavior.
- H4 (resetTransform intermediate state): The extra rounding from the two-step restore only matters at non-trivial fractional zoom values and only accumulates with many slice changes.

The combination of rare conditions explains why the bug is intermittent and hard to reproduce in short sessions.

---

### 6. Suggested troubleshooting steps (in priority order)

1. **Add a single log line** in `set_image` (preserve‑view branch) logging `self.viewport().width()` at the moment it is read, alongside `self.verticalScrollBar().isVisible()`. Collect this during a normal long‑scroll session. If `viewport().width()` ever changes between two consecutive calls, H6 is the primary cause.

2. **Quick isolation test – scrollbar policies**: Temporarily change both scrollbar policies to `ScrollBarAlwaysOff` (or `ScrollBarAlwaysOn`) and do a long slice scroll. If drift disappears entirely, H6 is confirmed. This is a low‑risk, two‑line change that can be reverted immediately.

3. **Quick isolation test – remove `resetTransform()`**: Replace:
   ```python
   self.resetTransform()
   self.scale(saved_zoom, saved_zoom)
   ```
   with:
   ```python
   self.setTransform(QTransform.fromScale(saved_zoom, saved_zoom))
   ```
   and repeat a long scroll. Fewer moving parts, and avoids the intermediate zoom‑1.0 state. If drift decreases, H4 is confirmed.

4. **Direct fix candidate – save/restore scrollbar integers**: Instead of `mapToScene` + `centerOn`, save and restore scrollbar integer values directly. This eliminates the float→int quantization. Implement with a guard (check that `expanded_rect` is equal to its previous value before restoring, to avoid restoring into a different coordinate system).

5. **Normalize pan to image‑relative coordinates**: Convert `saved_scene_center` to a fractional offset within the image before scene changes:
   ```python
   img_rect = self.image_item.boundingRect()
   rel_x = (saved_scene_center.x() - img_rect.left()) / img_rect.width()
   rel_y = (saved_scene_center.y() - img_rect.top()) / img_rect.height()
   ```
   Then after loading the new image:
   ```python
   new_img = self.image_item.boundingRect()
   restore_pt = QPointF(new_img.left() + rel_x * new_img.width(),
                        new_img.top() + rel_y * new_img.height())
   self.centerOn(restore_pt)
   ```
   This decouples the preserved pan entirely from the scene rect and makes the restore fully image‑space–relative. For same‑dimension slices this is equivalent to the current approach, but it removes any scene‑rect dependency and makes the intent explicit.

6. **Log the fractional quantization residual**: Log `(saved_scene_center.x() * saved_zoom) % 1.0` for each slice. If it is consistently above or below 0.5, H5 is confirmed and the systematic bias is measurable.

---

### 5. Summary

- **Observed:** Vertical pan is stable during long slice‑scrolling runs, but horizontal pan (scrollbar X and scene center X) drifts significantly, despite constant zoom and `preserve_view=True`.
- **Most likely cause:** `set_image`'s preserve‑view logic stores an absolute scene‑space center and then re‑centers on it after changing the scene rect/margins every slice. Changing the coordinate system makes the same numeric X value map to different visual locations, so the viewport appears to pan sideways.
- **Additional causes to investigate (see §4b):** (a) `centerOn()` integer scrollbar quantization that accumulates when the rounding direction is consistently biassed (H5); (b) the `resetTransform()` → `scale()` two-step introducing an extraneous scrollbar adjustment before `centerOn()` corrects it (H4); (c) `ScrollBarAsNeeded` causing the vertical scrollbar to appear/disappear between slices, changing `viewport().width()` and therefore shifting `expanded_rect.x()` (H6).
- **Why it's rare:** The drift requires a specific pan position (near a rounding threshold OR near the scrollbar‑visibility boundary) combined with many slice changes in a single continuous scroll. The conditions are fragile; a small window resize or pan in a different direction resets the accumulation.
- **Recommended first steps:** (1) Log `viewport().width()` and `verticalScrollBar().isVisible()` during a long scroll to determine if H6 is active. (2) Test with `ScrollBarAlwaysOff` as a canary. (3) Replace `resetTransform() + scale()` with `setTransform()` as a low-risk correctness improvement regardless of root cause.

