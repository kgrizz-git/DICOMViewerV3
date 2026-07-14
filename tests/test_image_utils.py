"""
Unit tests for utils.image_utils (array/PIL image conversions).
"""

import numpy as np
from PIL import Image

from utils.image_utils import array_to_image, image_to_array, resize_image


class TestArrayToImage:
    def test_grayscale_uint8_roundtrips_as_l_mode(self):
        arr = np.array([[0, 128], [255, 64]], dtype=np.uint8)
        img = array_to_image(arr)
        assert img is not None
        assert img.mode == "L"
        assert img.size == (2, 2)

    def test_rgb_uint8_returns_image(self):
        arr = np.zeros((4, 4, 3), dtype=np.uint8)
        arr[..., 0] = 200
        img = array_to_image(arr)
        assert img is not None
        assert img.size == (4, 4)

    def test_non_uint8_array_is_normalized(self):
        arr = np.array([[0, 500], [1000, 250]], dtype=np.uint16)
        img = array_to_image(arr)
        assert img is not None
        assert img.mode == "L"
        # min maps to 0, max maps to 255
        result = np.array(img)
        assert result.min() == 0
        assert result.max() == 255

    def test_constant_array_normalizes_to_zeros(self):
        arr = np.full((3, 3), 42, dtype=np.float32)
        img = array_to_image(arr)
        assert img is not None
        result = np.array(img)
        assert np.all(result == 0)

    def test_invalid_shape_returns_none(self):
        arr = np.zeros((2, 2, 2, 2), dtype=np.uint8)
        assert array_to_image(arr) is None

    def test_exception_path_returns_none(self):
        # A non-ndarray without .dtype triggers AttributeError inside try/except.
        class Bogus:
            pass

        assert array_to_image(Bogus()) is None  # type: ignore[arg-type]


class TestImageToArray:
    def test_converts_image_to_array(self):
        img = Image.new("L", (3, 2), color=17)
        arr = image_to_array(img)
        assert arr.shape == (2, 3)
        assert np.all(arr == 17)


class TestResizeImage:
    def test_keep_aspect_true_shrinks_within_bounds(self):
        img = Image.new("RGB", (200, 100))
        resized = resize_image(img, 50, 50, keep_aspect=True)
        assert resized.width <= 50
        assert resized.height <= 50

    def test_keep_aspect_false_forces_exact_size(self):
        img = Image.new("RGB", (200, 100))
        resized = resize_image(img, 40, 60, keep_aspect=False)
        assert resized.size == (40, 60)
