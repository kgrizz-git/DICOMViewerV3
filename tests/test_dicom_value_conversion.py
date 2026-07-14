from core.dicom_value_conversion import convert_dicom_value as core_convert_dicom_value
from utils.dicom_value_conversion import convert_dicom_value


def test_core_compatibility_export_uses_shared_converter():
    assert core_convert_dicom_value is convert_dicom_value


def test_convert_returns_value_when_vr_missing():
    marker = object()

    assert convert_dicom_value(marker, None) is marker


def test_convert_float_vr():
    assert convert_dicom_value("3.25", "FD") == 3.25
    assert convert_dicom_value("not-float", "FL") == "not-float"


def test_convert_integer_vr():
    assert convert_dicom_value("42", "US") == 42
    assert convert_dicom_value("not-int", "SL") == "not-int"


def test_convert_text_vr():
    assert convert_dicom_value(123, "LO") == "123"
    assert convert_dicom_value(None, "PN") == ""


def test_convert_unknown_vr_returns_value():
    marker = object()

    assert convert_dicom_value(marker, "OB") is marker
