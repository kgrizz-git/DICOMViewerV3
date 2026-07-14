"""Update overlay_manager.py: extract 3 methods to overlay_text_builder."""
import ast
import pathlib
import re

src_path = pathlib.Path("src/gui/overlay_manager.py")
src = src_path.read_text(encoding="utf-8")

# ── 1. Add imports ──────────────────────────────────────────────────────────
old_import_block = "from utils.bundled_fonts import make_qfont"
new_import_block = (
    "from utils.bundled_fonts import make_qfont\n"
    "from gui.overlay_text_builder import get_corner_text, get_modality, get_overlay_text"
)
assert old_import_block in src, "Import anchor not found"
src = src.replace(old_import_block, new_import_block, 1)

# ── 2. Remove the three method bodies ───────────────────────────────────────
# They live between "    def get_overlay_text" and "    def _create_text_item".
# Use a regex to excise that chunk.
pattern = re.compile(
    r"\n    def get_overlay_text\(self.*?\n    def _create_text_item\(",
    re.DOTALL,
)

def _replacement(m):
    # Keep only the "    def _create_text_item(" opener (last group)
    return "\n    def _create_text_item("

src, count = pattern.subn(_replacement, src)
assert count == 1, f"Expected 1 replacement, got {count}"

# ── 3. Update call sites ─────────────────────────────────────────────────────

# 3a. _get_modality → get_modality (two occurrences)
src = src.replace(
    "modality = self._get_modality(parser)",
    "modality = get_modality(parser)",
)

# 3b. _get_corner_text → get_corner_text (two occurrences, multi-line calls)
# The calls look like:
#   text = self._get_corner_text(parser, tags, total_slices, projection_enabled,
#                               projection_start_slice, projection_end_slice, projection_total_thickness,
#                               projection_type, multiframe_context)
# Replace self._get_corner_text( with get_corner_text(parser, tags, self.privacy_mode,
# then fix the subsequent arguments.

# First occurrence (create_overlay_items - line ~910)
old_call1 = (
    "text = self._get_corner_text(parser, tags, total_slices, projection_enabled,\n"
    "                                            projection_start_slice, projection_end_slice, projection_total_thickness,\n"
    "                                            projection_type, multiframe_context)"
)
new_call1 = (
    "text = get_corner_text(\n"
    "                                    parser, tags, self.privacy_mode, total_slices,\n"
    "                                    projection_enabled, projection_start_slice,\n"
    "                                    projection_end_slice, projection_total_thickness,\n"
    "                                    projection_type, multiframe_context\n"
    "                                )"
)
assert old_call1 in src, f"Call site 1 not found.\nLooking for:\n{old_call1!r}"
src = src.replace(old_call1, new_call1, 1)

# Second occurrence (_create_widget_overlays - line ~1110)
old_call2 = (
    "text = self._get_corner_text(parser, tags, total_slices, projection_enabled,\n"
    "                                            projection_start_slice, projection_end_slice,\n"
    "                                            projection_total_thickness, projection_type,\n"
    "                                            multiframe_context)"
)
new_call2 = (
    "text = get_corner_text(\n"
    "                                    parser, tags, self.privacy_mode, total_slices,\n"
    "                                    projection_enabled, projection_start_slice,\n"
    "                                    projection_end_slice, projection_total_thickness,\n"
    "                                    projection_type, multiframe_context\n"
    "                                )"
)
assert old_call2 in src, f"Call site 2 not found.\nLooking for:\n{old_call2!r}"
src = src.replace(old_call2, new_call2, 1)

# ── 4. Write and verify ──────────────────────────────────────────────────────
src_path.write_text(src, encoding="utf-8")
ast.parse(src)
print("SYNTAX OK")
lines = src.splitlines()
print(f"Lines: {len(lines)}")
