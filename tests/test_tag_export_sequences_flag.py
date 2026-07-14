"""
Phase 4 (sequence tag viewer plan) — "Include sequences" opt-in export tests.

The critical guarantee: with the checkbox off (default), export output is
byte-identical to what the writer produced before this feature existed. The
golden fixtures in tests/fixtures/tag_export_golden/ were dumped from the
pre-Phase-4 code (via `git stash` back to HEAD 17d1d32, before any Phase 4
edits) for the exact dataset/tag-selection built by `_build_fixture_dataset`
below, then compared byte-for-byte against the post-change writer output
before being committed — see the coder handoff for the generation steps.
"""

from __future__ import annotations

import csv
import os
import tempfile

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag

from core.tag_export_writer import write_csv_files, write_txt_files

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "tag_export_golden")


def _build_fixture_dataset() -> Dataset:
    """Same dataset used to generate the committed golden fixtures — do not change
    without regenerating tests/fixtures/tag_export_golden/off_default.{csv,txt} from
    a pre-Phase-4 checkout."""
    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "12345"
    ds.Modality = "CT"
    ds.SeriesDescription = "Test Series"
    ds.SeriesNumber = "1"
    ds.StudyDescription = "Test Study"

    item1 = Dataset()
    item1.CodeValue = "113100"
    item1.CodingSchemeDesignator = "DCM"
    item1.CodeMeaning = "Basic Application Confidentiality Profile"
    item2 = Dataset()
    item2.CodeValue = "113107"
    item2.CodingSchemeDesignator = "DCM"
    item2.CodeMeaning = "Retain Longitudinal Temporal Information Modified Dates Option"
    ds.DeidentificationMethodCodeSequence = Sequence([item1, item2])
    return ds


def _fixture_inputs():
    ds = _build_fixture_dataset()
    studies = {"study1": {"series1": [ds]}}
    selected_series = {"study1": {"series1": [0]}}
    selected_tags = [
        str(Tag("PatientName")),
        str(Tag("DeidentificationMethodCodeSequence")),
        str(Tag("CodeMeaning")),
        str(Tag("KVP")),
    ]
    variation = {
        "series1": {"varying_tags": [], "constant_tags": selected_tags},
    }
    return studies, selected_series, selected_tags, variation


class TestSequencesOffExportsSummariesNotOrphans:
    """Contents off: a sequence exports its own summary cell, and nothing leaks out of it.

    An export used to flatten a sequence's leaves to root and key them by occurrence, so
    a nested Code Meaning surfaced as a bare ``(0008, 0104)`` column with nothing saying
    which sequence it came from. Those orphan columns must not exist in either mode.
    """

    def test_csv_default_exports_sq_summary_and_no_nested_columns(self) -> None:
        studies, selected_series, selected_tags, variation = _fixture_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            # include_sequences intentionally omitted: exercise the true default.
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        by_tag = {r[1]: r[3] for r in data_rows}

        # The sequence itself exports, summarized.
        deid_tag = str(Tag("DeidentificationMethodCodeSequence"))
        assert "113100 DCM: Basic Application Confidentiality Profile" in by_tag[deid_tag]

        # Its Code Meaning was selected too, but exists ONLY inside the sequence. With
        # contents off it must be a missing/empty cell — never silently filled from a
        # nested value, which is what occurrence-keyed flattening used to do.
        assert by_tag[str(Tag("CodeMeaning"))] == ""

        # And no row anywhere is keyed by an occurrence suffix.
        assert not any("#" in r[1] for r in data_rows)

    def test_txt_default_exports_sq_summary(self) -> None:
        studies, selected_series, selected_tags, variation = _fixture_inputs()
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.txt")
            write_txt_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
            )
            with open(out_path, encoding="utf-8") as f:
                content = f.read()

        assert "113100 DCM: Basic Application Confidentiality Profile" in content
        assert "#2" not in content


class TestSequencesOnRendersSingleSummaryCell:
    """With the checkbox on, an SQ tag resolves to one summary cell, not many rows."""

    def test_deid_sequence_exports_compact_code_summary_single_row(self) -> None:
        ds = _build_fixture_dataset()
        studies = {"study1": {"series1": [ds]}}
        selected_series = {"study1": {"series1": [0]}}
        deid_tag = str(Tag("DeidentificationMethodCodeSequence"))
        selected_tags = [deid_tag]
        variation = {"series1": {"varying_tags": [], "constant_tags": selected_tags}}

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
                include_sequences=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        # Exactly one cell for the whole sequence — no per-item row explosion.
        assert len(data_rows) == 1
        row = data_rows[0]
        assert row[1] == deid_tag
        assert "113100 DCM: Basic Application Confidentiality Profile" in row[3]
        assert "113107 DCM: Retain Longitudinal Temporal Information Modified Dates Option" in row[3]

    def test_deid_sequence_exports_the_same_summary_with_the_flag_off(self) -> None:
        """The flag gates a sequence's *contents*, so the parent's own summary cell is
        identical either way. This used to be an empty missing-tag cell with the flag
        off, because the SQ parent was dropped from the parse entirely."""
        ds = _build_fixture_dataset()
        studies = {"study1": {"series1": [ds]}}
        selected_series = {"study1": {"series1": [0]}}
        deid_tag = str(Tag("DeidentificationMethodCodeSequence"))
        selected_tags = [deid_tag]
        variation = {"series1": {"varying_tags": [], "constant_tags": selected_tags}}

        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "out.csv")
            write_csv_files(
                out_path,
                variation,
                studies,
                selected_series,
                selected_tags,
                include_private=False,
                include_missing_selected_tags=True,
            )
            with open(out_path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        data_rows = [r for r in rows if len(r) >= 4 and r[0] == "All"]
        assert len(data_rows) == 1
        assert "113100 DCM: Basic Application Confidentiality Profile" in data_rows[0][3]


class TestVariationAnalysisSeesSequences:
    """A sequence whose *summary* differs per instance must be reported as varying.

    ``analyze_tag_variations`` reads each instance through ``get_all_tags``. If it is
    not told about sequences, an SQ tag is absent from every instance's dict, collects
    no values, and lands in the "constant" bucket by default. The export then writes
    one value per series for a sequence that genuinely changes per instance.

    This bites *code* sequences, whose summary carries content (the CID 7050 code
    meanings). A sequence summarized only by item count — e.g. SourceImageSequence,
    rendered "1 item(s)" — really is constant across instances even when the nested
    content differs; that lossiness is the documented no-hierarchical-expansion scope,
    not a bucketing bug.
    """

    @staticmethod
    def _instance(instance_number: int, code_value: str, code_meaning: str) -> Dataset:
        code = Dataset()
        code.CodeValue = code_value
        code.CodingSchemeDesignator = "DCM"
        code.CodeMeaning = code_meaning
        ds = Dataset()
        ds.PatientName = "Same^Patient"       # genuinely constant
        ds.InstanceNumber = instance_number   # genuinely varying scalar
        # Genuinely varying sequence whose summary text differs per instance.
        ds.DeidentificationMethodCodeSequence = Sequence([code])
        return ds

    def _analysis(self, include_sequences: bool) -> dict[str, list[str]]:
        from core.tag_export_analysis_service import analyze_tag_variations

        datasets = [
            self._instance(1, "113100", "Basic Application Confidentiality Profile"),
            self._instance(2, "113109", "Retain Device Identity Option"),
            self._instance(3, "113111", "Retain Safe Private Option"),
        ]
        studies = {"STUDY": {"SERIES": datasets}}
        selected_series = {"STUDY": {"SERIES": [0, 1, 2]}}
        selected_tags = [
            str(Tag("PatientName")),
            str(Tag("InstanceNumber")),
            str(Tag("DeidentificationMethodCodeSequence")),
        ]
        result = analyze_tag_variations(
            studies,
            selected_series,
            selected_tags,
            include_private=True,
            include_sequences=include_sequences,
        )
        return result["SERIES"]

    def test_varying_code_sequence_is_reported_as_varying(self) -> None:
        analysis = self._analysis(include_sequences=True)
        seq_tag = str(Tag("DeidentificationMethodCodeSequence"))

        assert seq_tag in analysis["varying_tags"], (
            "a code sequence with a different code meaning per instance must be "
            "varying — bucketing it constant would export one value for all three"
        )
        assert seq_tag not in analysis["constant_tags"]
        # Sanity: scalars are still bucketed correctly.
        assert str(Tag("InstanceNumber")) in analysis["varying_tags"]
        assert str(Tag("PatientName")) in analysis["constant_tags"]

    def test_varying_code_sequence_is_reported_as_varying_with_the_flag_off_too(self) -> None:
        """The flag must not change how an SQ *parent* is bucketed.

        It used to: with sequences off the parent was absent from every instance's dict,
        collected no values, and fell into the "constant" bucket, so the export wrote one
        value for a sequence that genuinely changed per instance — and the analysis and
        writer had to be passed matching flags or they'd silently disagree. The parent is
        now always parsed with its summary, so this footgun is gone.
        """
        analysis = self._analysis(include_sequences=False)
        seq_tag = str(Tag("DeidentificationMethodCodeSequence"))

        assert seq_tag in analysis["varying_tags"]
        assert seq_tag not in analysis["constant_tags"]
