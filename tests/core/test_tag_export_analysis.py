"""Tests for core.tag_export_analysis_service — tag variation analysis."""

from __future__ import annotations

from unittest.mock import patch

from core.tag_export_analysis_service import analyze_tag_variations


def test_analyze_tag_variations_empty_series():
    studies = {"study1": {"series1": ["ds1", "ds2"]}}
    selected_series = {}
    result = analyze_tag_variations(studies, selected_series, ["0010,0010"], False)
    assert result == {}


def test_analyze_tag_variations_single_instance_constant():
    studies = {"study1": {"series1": ["ds1"]}}
    selected_series = {"study1": {"series1": [0]}}
    with patch('core.tag_export_analysis_service.DICOMParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_all_tags.return_value = {'0010,0010': {'value': 'Smith^John'}}
        result = analyze_tag_variations(studies, selected_series, ["0010,0010"], False)
        assert "series1" in result
        assert result["series1"]["constant_tags"] == ["0010,0010"]
        assert result["series1"]["varying_tags"] == []


def test_analyze_tag_variations_varying_tags():
    studies = {"study1": {"series1": ["ds1", "ds2"]}}
    selected_series = {"study1": {"series1": [0, 1]}}
    with patch('core.tag_export_analysis_service.DICOMParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_all_tags.side_effect = [
            {'0010,0010': {'value': 'Smith^John'}},
            {'0010,0010': {'value': 'Smith^Jane'}},
        ]
        result = analyze_tag_variations(studies, selected_series, ["0010,0010"], False)
        assert "series1" in result
        assert result["series1"]["constant_tags"] == []
        assert result["series1"]["varying_tags"] == ["0010,0010"]


def test_analyze_tag_variations_constant_tags():
    studies = {"study1": {"series1": ["ds1", "ds2"]}}
    selected_series = {"study1": {"series1": [0, 1]}}
    with patch('core.tag_export_analysis_service.DICOMParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_all_tags.return_value = {'0010,0010': {'value': 'Smith^John'}}
        result = analyze_tag_variations(studies, selected_series, ["0010,0010"], False)
        assert "series1" in result
        assert result["series1"]["constant_tags"] == ["0010,0010"]
        assert result["series1"]["varying_tags"] == []


def test_analyze_tag_variations_tag_not_present():
    studies = {"study1": {"series1": ["ds1", "ds2"]}}
    selected_series = {"study1": {"series1": [0, 1]}}
    with patch('core.tag_export_analysis_service.DICOMParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_all_tags.return_value = {}
        result = analyze_tag_variations(studies, selected_series, ["0010,0010"], False)
        assert "series1" in result
        assert result["series1"]["constant_tags"] == ["0010,0010"]
        assert result["series1"]["varying_tags"] == []


def test_analyze_tag_variations_out_of_bounds_index():
    studies = {"study1": {"series1": ["ds1"]}}
    selected_series = {"study1": {"series1": [0, 1]}}
    with patch('core.tag_export_analysis_service.DICOMParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_all_tags.return_value = {'0010,0010': {'value': 'Smith^John'}}
        result = analyze_tag_variations(studies, selected_series, ["0010,0010"], False)
        assert "series1" in result
        assert result["series1"]["constant_tags"] == ["0010,0010"]
        assert result["series1"]["varying_tags"] == []


def test_analyze_tag_variations_private_and_sequences_flags():
    studies = {"study1": {"series1": ["ds1"]}}
    selected_series = {"study1": {"series1": [0]}}
    with patch('core.tag_export_analysis_service.DICOMParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_all_tags.return_value = {}
        analyze_tag_variations(studies, selected_series, ["0010,0010"], True, True)
        mock_instance.get_all_tags.assert_called_once_with(
            include_private=True,
            include_sequences=True,
        )
