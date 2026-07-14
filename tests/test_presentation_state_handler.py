"""Unit tests for core.presentation_state_handler.PresentationStateHandler."""

from __future__ import annotations

from types import SimpleNamespace

from core.presentation_state_handler import PresentationStateHandler


def _item(**kwargs):
    return SimpleNamespace(**kwargs)


class TestCoerceFloat:
    def test_valid_value_converts(self):
        handler = PresentationStateHandler()
        assert handler._coerce_float("3.5") == 3.5

    def test_invalid_value_returns_default(self):
        handler = PresentationStateHandler()
        assert handler._coerce_float("bad", default=1.0) == 1.0

    def test_none_returns_default(self):
        handler = PresentationStateHandler()
        assert handler._coerce_float(None) == 0.0


class TestParsePresentationState:
    def test_empty_dataset_returns_defaults(self):
        handler = PresentationStateHandler()
        result = handler.parse_presentation_state(SimpleNamespace())
        assert result["annotations"] == []
        assert result["display_settings"] == {}
        assert result["referenced_images"] == {"image_uids": [], "series_uids": []}

    def test_with_graphic_annotation_sequence(self):
        handler = PresentationStateHandler()
        graphic_obj = _item(GraphicType="POINT", GraphicData=[1.0, 2.0])
        annotation_item = _item(GraphicObjectSequence=[graphic_obj])
        dataset = SimpleNamespace(GraphicAnnotationSequence=[annotation_item])
        result = handler.parse_presentation_state(dataset)
        assert len(result["annotations"]) == 1
        assert result["annotations"][0]["type"] == "POINT"


class TestGetReferencedImages:
    def test_no_references_returns_empty_lists(self):
        handler = PresentationStateHandler()
        result = handler.get_referenced_images(SimpleNamespace())
        assert result == {"image_uids": [], "series_uids": []}

    def test_image_level_references(self):
        handler = PresentationStateHandler()
        ref_seq = [_item(ReferencedSOPInstanceUID="1.1"), _item(ReferencedSOPInstanceUID="1.2")]
        dataset = SimpleNamespace(ReferencedImageSequence=ref_seq)
        result = handler.get_referenced_images(dataset)
        assert result["image_uids"] == ["1.1", "1.2"]
        assert result["series_uids"] == []

    def test_series_level_references_dedupe(self):
        handler = PresentationStateHandler()
        ref_seq = [
            _item(SeriesInstanceUID="2.1"),
            _item(SeriesInstanceUID="2.1"),
            _item(SeriesInstanceUID="2.2"),
        ]
        dataset = SimpleNamespace(ReferencedSeriesSequence=ref_seq)
        result = handler.get_referenced_images(dataset)
        assert result["series_uids"] == ["2.1", "2.2"]

    def test_exception_is_swallowed(self):
        handler = PresentationStateHandler()

        class BadDataset:
            @property
            def ReferencedImageSequence(self):
                raise RuntimeError("boom")

        result = handler.get_referenced_images(BadDataset())
        assert result == {"image_uids": [], "series_uids": []}


class TestParseGraphicAnnotations:
    def test_point_annotation(self):
        handler = PresentationStateHandler()
        graphic_obj = _item(GraphicType="POINT", GraphicData=[10.0, 20.0])
        annotation_item = _item(GraphicObjectSequence=[graphic_obj])
        annotations = handler.parse_graphic_annotations([annotation_item])
        assert annotations[0]["type"] == "POINT"
        assert annotations[0]["coordinates"] == [(10.0, 20.0)]
        assert annotations[0]["layer"] == ""
        assert annotations[0]["units"] == "PIXEL"

    def test_layer_and_units_extracted(self):
        handler = PresentationStateHandler()
        graphic_obj = _item(GraphicType="POINT", GraphicData=[1.0, 2.0])
        annotation_item = _item(
            GraphicLayer="LAYER1",
            GraphicAnnotationUnits="DISPLAY",
            GraphicObjectSequence=[graphic_obj],
        )
        annotations = handler.parse_graphic_annotations([annotation_item])
        assert annotations[0]["layer"] == "LAYER1"
        assert annotations[0]["units"] == "DISPLAY"

    def test_text_annotation_uses_unformatted_text_value(self):
        handler = PresentationStateHandler()
        graphic_obj = _item(GraphicType="TEXT", GraphicData=[1.0, 2.0, 3.0, 4.0])
        text_obj = _item(UnformattedTextValue="hello world")
        annotation_item = _item(
            GraphicObjectSequence=[graphic_obj],
            TextObjectSequence=[text_obj],
        )
        annotations = handler.parse_graphic_annotations([annotation_item])
        assert annotations[0]["text"] == "hello world"

    def test_text_annotation_uses_bounding_box_fallback(self):
        handler = PresentationStateHandler()
        graphic_obj = _item(GraphicType="TEXT", GraphicData=[1.0, 2.0])
        text_obj = _item(
            BoundingBoxAnnotationUnits="PIXEL",
            BoundingBoxTopLeftHandCorner=[0.0, 0.0],
            BoundingBoxBottomRightHandCorner=[5.0, 5.0],
        )
        annotation_item = _item(
            GraphicObjectSequence=[graphic_obj],
            TextObjectSequence=[text_obj],
        )
        annotations = handler.parse_graphic_annotations([annotation_item])
        assert annotations[0]["coordinates"] == [(0.0, 0.0), (5.0, 5.0)]

    def test_no_graphic_type_not_added(self):
        handler = PresentationStateHandler()
        graphic_obj = _item(GraphicData=[1.0, 2.0])
        annotation_item = _item(GraphicObjectSequence=[graphic_obj])
        annotations = handler.parse_graphic_annotations([annotation_item])
        assert annotations == []

    def test_no_graphic_object_sequence(self):
        handler = PresentationStateHandler()
        annotation_item = _item(GraphicLayer="L1")
        annotations = handler.parse_graphic_annotations([annotation_item])
        assert annotations == []

    def test_exception_is_swallowed(self):
        handler = PresentationStateHandler()

        class ExplodingSeq:
            def __iter__(self):
                raise TypeError("boom")

        annotations = handler.parse_graphic_annotations(ExplodingSeq())
        assert annotations == []


class TestParseGraphicData:
    def test_non_list_returns_empty(self):
        handler = PresentationStateHandler()
        assert handler._parse_graphic_data("not-a-list", "POINT") == []

    def test_point_needs_two_values(self):
        handler = PresentationStateHandler()
        assert handler._parse_graphic_data([1.0], "POINT") == []
        assert handler._parse_graphic_data([1.0, 2.0], "POINT") == [(1.0, 2.0)]

    def test_circle_needs_four_values(self):
        handler = PresentationStateHandler()
        assert handler._parse_graphic_data([1.0, 2.0], "CIRCLE") == []
        result = handler._parse_graphic_data([1.0, 2.0, 3.0, 4.0], "CIRCLE")
        assert result == [(1.0, 2.0), (3.0, 4.0)]

    def test_ellipse_needs_six_values(self):
        handler = PresentationStateHandler()
        assert handler._parse_graphic_data([1.0, 2.0], "ELLIPSE") == []
        result = handler._parse_graphic_data([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "ELLIPSE")
        assert result == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]

    def test_polyline_pairs_up_coordinates(self):
        handler = PresentationStateHandler()
        result = handler._parse_graphic_data([1.0, 2.0, 3.0, 4.0], "POLYLINE")
        assert result == [(1.0, 2.0), (3.0, 4.0)]

    def test_polyline_odd_length_drops_trailing_value(self):
        handler = PresentationStateHandler()
        result = handler._parse_graphic_data([1.0, 2.0, 3.0], "POLYLINE")
        assert result == [(1.0, 2.0)]

    def test_unknown_graphic_type_returns_empty(self):
        handler = PresentationStateHandler()
        assert handler._parse_graphic_data([1.0, 2.0], "UNKNOWN") == []

    def test_exception_is_swallowed(self):
        handler = PresentationStateHandler()

        class BadList(list):
            def __len__(self):
                raise RuntimeError("boom")

        result = handler._parse_graphic_data(BadList([1.0, 2.0]), "POINT")
        assert result == []


class TestParseBoundingBox:
    def test_both_corners_present(self):
        handler = PresentationStateHandler()
        result = handler._parse_bounding_box([0.0, 0.0], [5.0, 5.0])
        assert result == [(0.0, 0.0), (5.0, 5.0)]

    def test_bottom_right_none(self):
        handler = PresentationStateHandler()
        result = handler._parse_bounding_box([0.0, 0.0], None)
        assert result == [(0.0, 0.0)]

    def test_both_none_returns_empty(self):
        handler = PresentationStateHandler()
        assert handler._parse_bounding_box(None, None) == []

    def test_exception_is_swallowed(self):
        handler = PresentationStateHandler()

        class BadList(list):
            def __len__(self):
                raise RuntimeError("boom")

        result = handler._parse_bounding_box(BadList([0.0, 0.0]), None)
        assert result == []


class TestParseDisplaySettings:
    def test_empty_dataset_returns_empty_dict(self):
        handler = PresentationStateHandler()
        assert handler.parse_display_settings(SimpleNamespace()) == {}

    def test_window_level_extracted(self):
        handler = PresentationStateHandler()
        dataset = SimpleNamespace(WindowCenter=40.0, WindowWidth=400.0)
        settings = handler.parse_display_settings(dataset)
        assert settings["window_center"] == 40.0
        assert settings["window_width"] == 400.0

    def test_displayed_area_pixel_spacing_and_pan(self):
        handler = PresentationStateHandler()
        display_item = _item(
            PresentationPixelSpacing=[0.5, 0.5],
            DisplayedAreaTopLeftHandCorner=[10.0, 20.0],
        )
        dataset = SimpleNamespace(DisplayedAreaSelectionSequence=[display_item])
        settings = handler.parse_display_settings(dataset)
        assert settings["pixel_spacing"] == (0.5, 0.5)
        assert settings["pan"] == (10.0, 20.0)

    def test_empty_displayed_area_sequence_skipped(self):
        handler = PresentationStateHandler()
        dataset = SimpleNamespace(DisplayedAreaSelectionSequence=[])
        settings = handler.parse_display_settings(dataset)
        assert "pixel_spacing" not in settings
        assert "pan" not in settings

    def test_rotation_extracted(self):
        handler = PresentationStateHandler()
        dataset = SimpleNamespace(ImageRotation=90)
        settings = handler.parse_display_settings(dataset)
        assert settings["rotation"] == 90.0

    def test_exception_is_swallowed(self):
        handler = PresentationStateHandler()

        class BadDataset:
            @property
            def WindowCenter(self):
                raise RuntimeError("boom")

            @property
            def WindowWidth(self):
                raise RuntimeError("boom")

        settings = handler.parse_display_settings(BadDataset())
        assert settings == {}

    def test_exception_from_bad_displayed_area_sequence_is_swallowed(self):
        handler = PresentationStateHandler()

        class BadSeq:
            def __len__(self):
                raise RuntimeError("boom")

        dataset = SimpleNamespace(DisplayedAreaSelectionSequence=BadSeq())
        settings = handler.parse_display_settings(dataset)
        assert settings == {}
