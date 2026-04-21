"""Tests for SR document tree builder and RDSR irradiation event extraction."""

from __future__ import annotations

from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import EnhancedXRayRadiationDoseSRStorage, ExplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID, generate_uid

from core.rdsr_irradiation_events import extract_irradiation_events
from core.sr_concept_identity import concept_identity_matches, normalize_coding_scheme_designator
from core.sr_document_tree import build_sr_document_tree, path_to_node_id_map
from core.sr_sop_classes import is_structured_report_dataset, structured_report_storage_label

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dicom_rdsr"


@pytest.fixture(scope="module")
def xray_rdsr_ds() -> Dataset:
    path = _FIXTURE_DIR / "synthetic_ct_dose_xray_rdsr.dcm"
    assert path.is_file()
    return pydicom.dcmread(path)


@pytest.fixture(scope="module")
def enhanced_rdsr_ds() -> Dataset:
    path = _FIXTURE_DIR / "synthetic_enhanced_xray_rdsr.dcm"
    assert path.is_file()
    return pydicom.dcmread(path)


def test_build_sr_document_tree_xray_rdsr(xray_rdsr_ds: Dataset) -> None:
    tree = build_sr_document_tree(xray_rdsr_ds)
    assert tree.total_nodes >= 1
    assert len(tree.roots) == 1
    assert not tree.truncated
    pmap = path_to_node_id_map(tree)
    assert (0,) in pmap


def test_extract_irradiation_events_synthetic_ct(xray_rdsr_ds: Dataset) -> None:
    ex = extract_irradiation_events(xray_rdsr_ds)
    # Synthetic fixture uses two CT irradiation event containers (113819) with no nested children.
    assert len(ex.rows) == 2
    assert all("113819" in r.event_concept for r in ex.rows)


def test_extract_irradiation_events_enhanced_geometry_columns(enhanced_rdsr_ds: Dataset) -> None:
    ex = extract_irradiation_events(enhanced_rdsr_ds)
    assert len(ex.rows) >= 1
    row = ex.rows[0]
    assert row.columns.get("Primary angle (deg)") == "27.5"
    assert row.columns.get("Secondary angle (deg)") == "-5.5"
    assert row.columns.get("Source-to-detector distance (mm)") == "980.0"
    assert row.columns.get("Collimated field area (mm²)") == "1500.0"


def test_extract_irradiation_events_dap_and_dose_rp_unit_columns(enhanced_rdsr_ds: Dataset) -> None:
    """DAP / Dose (RP) numeric columns keep prior behavior; parallel unit columns come from UCUM."""
    ex = extract_irradiation_events(enhanced_rdsr_ds)
    assert len(ex.rows) >= 1
    row = ex.rows[0]
    assert row.columns.get("DAP") == "22.5"
    dap_u = (row.columns.get("DAP units") or "").lower()
    assert "gray" in dap_u or "gy" in dap_u
    # Synthetic X-ray event omits 113738; column exists and is empty when absent.
    assert "Dose (RP) units" in row.columns


def test_extract_irradiation_events_missing_dap_units_emits_note() -> None:
    """NUM 122130 with value but no MeasurementUnitsCodeSequence → capped soft note on extraction."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    def _dap_num_no_ucum() -> Dataset:
        d = Dataset()
        d.ValueType = "NUM"
        d.ConceptNameCodeSequence = DicomSequence([_c("122130", "DCM", "Dose Area Product Total")])
        mv = Dataset()
        mv.NumericValue = "1.0"
        d.MeasuredValueSequence = DicomSequence([mv])
        d.RelationshipType = "CONTAINS"
        return d

    event = Dataset()
    event.ValueType = "CONTAINER"
    event.ContinuityOfContent = "SEPARATE"
    event.ConceptNameCodeSequence = DicomSequence([_c("113706", "DCM", "Irradiation Event X-Ray Data")])
    event.RelationshipType = "CONTAINS"
    event.ContentSequence = DicomSequence([_dap_num_no_ucum()])

    root = Dataset()
    root.ValueType = "CONTAINER"
    root.ContinuityOfContent = "SEPARATE"
    root.ConceptNameCodeSequence = DicomSequence([_c("113701", "DCM", "CT Radiation Dose")])
    root.RelationshipType = "CONTAINS"
    root.ContentSequence = DicomSequence([event])

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.Modality = "SR"
    ds.SOPClassUID = str(EnhancedXRayRadiationDoseSRStorage)
    ds.SOPInstanceUID = generate_uid()
    ds.ContentSequence = DicomSequence([root])
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = fm
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ex = extract_irradiation_events(ds)
    assert len(ex.rows) == 1
    assert ex.rows[0].columns.get("DAP") == "1.0"
    assert not (ex.rows[0].columns.get("DAP units") or "").strip()
    joined = " ".join(ex.notes)
    assert "DAP (DCM 122130)" in joined
    assert "MeasurementUnitsCodeSequence" in joined


def test_extract_irradiation_events_dynamic_private_numeric_column() -> None:
    """Vendor/private NUM leaves under 113706 become extra table columns (Philips-style)."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    def _num_private() -> Dataset:
        d = Dataset()
        d.ValueType = "NUM"
        d.ConceptNameCodeSequence = DicomSequence([_c("023", "99PHI-IXR-XPER", "X side")])
        mv = Dataset()
        mv.NumericValue = "176.0"
        uc = Dataset()
        uc.CodeValue = "mm"
        uc.CodingSchemeDesignator = "UCUM"
        uc.CodeMeaning = "millimeter"
        mv.MeasurementUnitsCodeSequence = DicomSequence([uc])
        d.MeasuredValueSequence = DicomSequence([mv])
        d.RelationshipType = "CONTAINS"
        return d

    event = Dataset()
    event.ValueType = "CONTAINER"
    event.ContinuityOfContent = "SEPARATE"
    event.ConceptNameCodeSequence = DicomSequence([_c("113706", "DCM", "Irradiation Event X-Ray Data")])
    event.RelationshipType = "CONTAINS"
    event.ContentSequence = DicomSequence([_num_private()])

    root = Dataset()
    root.ValueType = "CONTAINER"
    root.ContinuityOfContent = "SEPARATE"
    root.ConceptNameCodeSequence = DicomSequence([_c("113701", "DCM", "CT Radiation Dose")])
    root.RelationshipType = "CONTAINS"
    root.ContentSequence = DicomSequence([event])

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.Modality = "SR"
    ds.SOPClassUID = str(EnhancedXRayRadiationDoseSRStorage)
    ds.SOPInstanceUID = generate_uid()
    ds.ContentSequence = DicomSequence([root])
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = fm
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ex = extract_irradiation_events(ds)
    assert len(ex.rows) == 1
    col = "X side (023, 99PHI-IXR-XPER)"
    assert col in ex.rows[0].columns
    assert "176.0" in ex.rows[0].columns[col]
    assert "millimeter" in ex.rows[0].columns[col]


def _minimal_enhanced_xray_dose_sr_with_event_children(children: list[Dataset]) -> Dataset:
    """Tiny Enhanced X-Ray Radiation Dose SR with one 113706 event and given ``ContentSequence``."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    event = Dataset()
    event.ValueType = "CONTAINER"
    event.ContinuityOfContent = "SEPARATE"
    event.ConceptNameCodeSequence = DicomSequence([_c("113706", "DCM", "Irradiation Event X-Ray Data")])
    event.RelationshipType = "CONTAINS"
    event.ContentSequence = DicomSequence(children)

    root = Dataset()
    root.ValueType = "CONTAINER"
    root.ContinuityOfContent = "SEPARATE"
    root.ConceptNameCodeSequence = DicomSequence([_c("113701", "DCM", "CT Radiation Dose")])
    root.RelationshipType = "CONTAINS"
    root.ContentSequence = DicomSequence([event])

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.Modality = "SR"
    ds.SOPClassUID = str(EnhancedXRayRadiationDoseSRStorage)
    ds.SOPInstanceUID = generate_uid()
    ds.ContentSequence = DicomSequence([root])
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = fm
    ds.is_implicit_VR = False
    ds.is_little_endian = True
    return ds


def test_extract_irradiation_events_final_source_to_detector_meaning_fallback() -> None:
    """Philips-style **Final Distance Source to Detector** fills distance columns when 113750 absent."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    num = Dataset()
    num.ValueType = "NUM"
    num.ConceptNameCodeSequence = DicomSequence(
        [_c("018", "99PHI-IXR-XPER", "Final Distance Source to Detector")]
    )
    num.RelationshipType = "CONTAINS"
    mv = Dataset()
    mv.NumericValue = "1722.0"
    uc = Dataset()
    uc.CodeValue = "mm"
    uc.CodingSchemeDesignator = "UCUM"
    uc.CodeMeaning = "millimeter"
    mv.MeasurementUnitsCodeSequence = DicomSequence([uc])
    num.MeasuredValueSequence = DicomSequence([mv])

    ds = _minimal_enhanced_xray_dose_sr_with_event_children([num])
    ex = extract_irradiation_events(ds)
    assert ex.rows[0].columns.get("Source-to-detector distance (mm)") == "1722.0"
    assert ex.rows[0].columns.get("Final source-to-detector distance (mm)") == "1722.0"


def test_extract_irradiation_events_exposure_time_113735_and_reference_point_code() -> None:
    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    exp = Dataset()
    exp.ValueType = "NUM"
    exp.ConceptNameCodeSequence = DicomSequence([_c("113735", "DCM", "Exposure Time")])
    exp.RelationshipType = "CONTAINS"
    mv = Dataset()
    mv.NumericValue = "147.5"
    uc = Dataset()
    uc.CodeValue = "ms"
    uc.CodingSchemeDesignator = "UCUM"
    uc.CodeMeaning = "millisecond"
    mv.MeasurementUnitsCodeSequence = DicomSequence([uc])
    exp.MeasuredValueSequence = DicomSequence([mv])

    ref = Dataset()
    ref.ValueType = "CODE"
    ref.ConceptNameCodeSequence = DicomSequence([_c("113780", "DCM", "Reference Point Definition")])
    ref.RelationshipType = "CONTAINS"
    ref.ConceptCodeSequence = DicomSequence([_c("111131", "DCM", "15cm from Isocenter")])

    ds = _minimal_enhanced_xray_dose_sr_with_event_children([exp, ref])
    ex = extract_irradiation_events(ds)
    row = ex.rows[0].columns
    assert row.get("Exposure time") == "147.5"
    assert "15cm" in (row.get("Reference point definition") or "") or "111131" in (row.get("Reference point definition") or "")


def test_extract_irradiation_events_patient_orientation_113743() -> None:
    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    ori = Dataset()
    ori.ValueType = "CODE"
    ori.ConceptNameCodeSequence = DicomSequence([_c("113743", "DCM", "Patient Orientation")])
    ori.RelationshipType = "CONTAINS"
    ori.ConceptCodeSequence = DicomSequence([_c("F-10450", "SRT", "recumbent")])

    mod = Dataset()
    mod.ValueType = "CODE"
    mod.ConceptNameCodeSequence = DicomSequence([_c("113744", "DCM", "Patient Orientation Modifier")])
    mod.RelationshipType = "CONTAINS"
    mod.ConceptCodeSequence = DicomSequence([_c("109040", "SRT", "oblique")])

    ds = _minimal_enhanced_xray_dose_sr_with_event_children([ori, mod])
    ex = extract_irradiation_events(ds)
    row = ex.rows[0].columns
    assert "recumbent" in (row.get("Patient orientation") or "")
    assert "oblique" in (row.get("Patient orientation modifier") or "")


def test_extract_irradiation_events_real_sample_geometry_if_available() -> None:
    sample = (
        Path(__file__).resolve().parent.parent
        / "test-DICOM-data"
        / "pyskindose_samples"
        / "siemens_axiom_artis.dcm"
    )
    if not sample.is_file():
        pytest.skip("optional local sample not available")
    ds = pydicom.dcmread(sample, stop_before_pixels=True)
    ex = extract_irradiation_events(ds)
    assert len(ex.rows) > 0
    assert any((r.columns.get("Primary angle (deg)") or "") != "" for r in ex.rows)
    assert any((r.columns.get("Secondary angle (deg)") or "") != "" for r in ex.rows)
    assert any((r.columns.get("Source-to-detector distance (mm)") or "") != "" for r in ex.rows)


def test_truncation_flag_when_max_nodes_tiny(xray_rdsr_ds: Dataset) -> None:
    tree = build_sr_document_tree(xray_rdsr_ds, max_nodes=2, max_depth=24)
    assert tree.truncated is True


def test_sr_concept_identity_designator_fold_and_urn_preserved() -> None:
    assert normalize_coding_scheme_designator("  dcm  ") == "DCM"
    assert normalize_coding_scheme_designator("urn:oid:1.2.3") == "urn:oid:1.2.3"
    assert normalize_coding_scheme_designator("foo:bar") == "foo:bar"


def test_extract_irradiation_events_event_root_long_code_value_lowercase_scheme() -> None:
    """113706 on LongCodeValue + lowercase DCM still matches the X-ray irradiation event root."""

    def _c_long(cv: str | None, scheme: str, meaning: str, *, long_cv: str | None = None) -> Dataset:
        d = Dataset()
        if cv is not None:
            d.CodeValue = cv
        if long_cv is not None:
            d.LongCodeValue = long_cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    event = Dataset()
    event.ValueType = "CONTAINER"
    event.ContinuityOfContent = "SEPARATE"
    event.ConceptNameCodeSequence = DicomSequence(
        [_c_long("", "dcm", "Irradiation Event X-Ray Data", long_cv="113706")]
    )
    event.RelationshipType = "CONTAINS"
    event.ContentSequence = DicomSequence([])

    root = Dataset()
    root.ValueType = "CONTAINER"
    root.ContinuityOfContent = "SEPARATE"
    root.ConceptNameCodeSequence = DicomSequence(
        [_c_long("113701", "DCM", "CT Radiation Dose", long_cv=None)]
    )
    root.RelationshipType = "CONTAINS"
    root.ContentSequence = DicomSequence([event])

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.Modality = "SR"
    ds.SOPClassUID = str(EnhancedXRayRadiationDoseSRStorage)
    ds.SOPInstanceUID = generate_uid()
    ds.ContentSequence = DicomSequence([root])
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = fm
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    assert concept_identity_matches(event, ("113706", "DCM")) is True
    ex = extract_irradiation_events(ds)
    assert len(ex.rows) == 1
    assert "113706" in ex.rows[0].event_concept


def test_extract_irradiation_events_ambiguous_two_113750_notes() -> None:
    """Two Distance Source to Detector NUMs at the same depth produce a note and deterministic pick."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    def _num_113750(val: str) -> Dataset:
        d = Dataset()
        d.ValueType = "NUM"
        d.ConceptNameCodeSequence = DicomSequence([_c("113750", "DCM", "Distance Source to Detector")])
        d.RelationshipType = "CONTAINS"
        mv = Dataset()
        mv.NumericValue = val
        uc = Dataset()
        uc.CodeValue = "mm"
        uc.CodingSchemeDesignator = "UCUM"
        uc.CodeMeaning = "millimeter"
        mv.MeasurementUnitsCodeSequence = DicomSequence([uc])
        d.MeasuredValueSequence = DicomSequence([mv])
        return d

    ds = _minimal_enhanced_xray_dose_sr_with_event_children([_num_113750("900.0"), _num_113750("910.0")])
    ex = extract_irradiation_events(ds)
    assert any("Ambiguous NUM" in n for n in ex.notes)
    assert ex.rows[0].columns.get("Source-to-detector distance (mm)") in ("900.0", "910.0")


def test_extract_irradiation_events_truncated_subtree_flag() -> None:
    """Low max_flat_items yields truncated_subtree and a path note."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    def _num_leaf(label: str, val: float) -> Dataset:
        d = Dataset()
        d.ValueType = "NUM"
        d.ConceptNameCodeSequence = DicomSequence([_c(f"99TST{label}", "99TST", f"Leaf {label}")])
        d.RelationshipType = "CONTAINS"
        mv = Dataset()
        mv.NumericValue = str(val)
        d.MeasuredValueSequence = DicomSequence([mv])
        return d

    children = [_num_leaf(str(i), float(i)) for i in range(8)]
    ds = _minimal_enhanced_xray_dose_sr_with_event_children(children)
    ex = extract_irradiation_events(ds, max_flat_items=3)
    assert ex.truncated_subtree is True
    assert ex.rows[0].subtree_truncated is True
    assert any("flattening hit max_depth" in n or "max_items" in n for n in ex.notes)


def test_extract_irradiation_events_exposure_both_codes_differing_notes() -> None:
    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    def _exp(code: str, val: str) -> Dataset:
        d = Dataset()
        d.ValueType = "NUM"
        d.ConceptNameCodeSequence = DicomSequence([_c(code, "DCM", "Exposure Time")])
        d.RelationshipType = "CONTAINS"
        mv = Dataset()
        mv.NumericValue = val
        d.MeasuredValueSequence = DicomSequence([mv])
        return d

    ds = _minimal_enhanced_xray_dose_sr_with_event_children([_exp("113735", "100.0"), _exp("113824", "200.0")])
    ex = extract_irradiation_events(ds)
    assert ex.rows[0].columns.get("Exposure time") == "100.0"
    assert any("113735" in n and "113824" in n for n in ex.notes)


def test_extract_irradiation_events_irr_event_uid_text_fallback() -> None:
    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    uid_item = Dataset()
    uid_item.ValueType = "TEXT"
    uid_item.ConceptNameCodeSequence = DicomSequence([_c("113769", "DCM", "Irradiation Event UID")])
    uid_item.RelationshipType = "CONTAINS"
    uid_item.TextValue = "1.2.3.4.5"

    ds = _minimal_enhanced_xray_dose_sr_with_event_children([uid_item])
    ex = extract_irradiation_events(ds)
    assert ex.rows[0].columns.get("Irradiation event UID") == "1.2.3.4.5"


def test_is_structured_report_dataset_xray_rdsr(xray_rdsr_ds: Dataset) -> None:
    assert is_structured_report_dataset(xray_rdsr_ds) is True
    label = structured_report_storage_label(str(xray_rdsr_ds.SOPClassUID))
    assert "Radiation Dose" in label or "X-Ray" in label


def test_empty_dataset_no_crash() -> None:
    ds = Dataset()
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    tree = build_sr_document_tree(ds)
    assert tree.roots == []
    assert tree.warnings
