"""Tests for DICOM tag export CSV/Excel writers (missing-tag rows)."""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset
from pydicom.tag import Tag

from core.tag_export_writer import write_csv_files, write_txt_files


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


if __name__ == "__main__":
    unittest.main()
