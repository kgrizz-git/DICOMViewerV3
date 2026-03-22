"""
Transformation script: update tag_export_dialog.py to delegate to the new
tag_export_analysis_service and tag_export_writer modules.

Changes:
  1. Add imports for the two new modules after the existing DICOMParser import.
  2. Replace four self.* call sites in _export_to_excel with module-level calls.
  3. Remove the four extracted methods: _analyze_tag_variations,
     _generate_default_filename, _write_excel_file, _write_csv_files.
"""

import re
import ast

TARGET = 'src/gui/dialogs/tag_export_dialog.py'

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Insert new imports after `from core.dicom_parser import DICOMParser` ──
NEW_IMPORTS = (
    '\nfrom core.tag_export_analysis_service import analyze_tag_variations'
    '\nfrom core.tag_export_writer import generate_default_filename, write_excel_file, write_csv_files'
)
ANCHOR = 'from core.dicom_parser import DICOMParser'
assert ANCHOR in content, 'Anchor import not found'
content = content.replace(ANCHOR, ANCHOR + NEW_IMPORTS, 1)

# ── 2. Update call sites inside _export_to_excel ──────────────────────────────

# variation_analysis = self._analyze_tag_variations()
content = content.replace(
    '        variation_analysis = self._analyze_tag_variations()',
    '        variation_analysis = analyze_tag_variations(\n'
    '            self.studies, self.selected_series, self.selected_tags,\n'
    '            self.private_tags_checkbox.isChecked())',
    1,
)

# default_filename = self._generate_default_filename()
content = content.replace(
    '        default_filename = self._generate_default_filename()',
    '        default_filename = generate_default_filename(self.studies, self.selected_series)',
    1,
)

# exported_files = self._write_csv_files(file_path, variation_analysis)
content = content.replace(
    '                exported_files = self._write_csv_files(file_path, variation_analysis)',
    '                exported_files = write_csv_files(\n'
    '                    file_path, variation_analysis, self.studies,\n'
    '                    self.selected_series, self.selected_tags,\n'
    '                    self.private_tags_checkbox.isChecked())',
    1,
)

# self._write_excel_file(file_path, variation_analysis)
content = content.replace(
    '                self._write_excel_file(file_path, variation_analysis)',
    '                write_excel_file(\n'
    '                    file_path, variation_analysis, self.studies,\n'
    '                    self.selected_series, self.selected_tags,\n'
    '                    self.private_tags_checkbox.isChecked())',
    1,
)

# ── 3. Remove extracted methods ───────────────────────────────────────────────

# _analyze_tag_variations: ends just before _show_variation_analysis_dialog
content = re.sub(
    r'\n    def _analyze_tag_variations\(self\).*?(?=\n    def _show_variation_analysis_dialog)',
    '',
    content,
    count=1,
    flags=re.DOTALL,
)

# _generate_default_filename: ends just before _write_excel_file
content = re.sub(
    r'\n    def _generate_default_filename\(self\).*?(?=\n    def _write_excel_file)',
    '',
    content,
    count=1,
    flags=re.DOTALL,
)

# _write_excel_file: ends just before _write_csv_files
content = re.sub(
    r'\n    def _write_excel_file\(self,.*?(?=\n    def _write_csv_files)',
    '',
    content,
    count=1,
    flags=re.DOTALL,
)

# _write_csv_files: ends just before _load_presets_list
content = re.sub(
    r'\n    def _write_csv_files\(self,.*?(?=\n    def _load_presets_list)',
    '',
    content,
    count=1,
    flags=re.DOTALL,
)

# ── 4. Write and verify ───────────────────────────────────────────────────────
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(content)

try:
    ast.parse(content)
    total_lines = content.count('\n') + 1
    print(f'SYNTAX OK\nLines: {total_lines}')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
