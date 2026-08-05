from pydicom.dataset import Dataset

from core.dataset_cache_utils import clear_cached_pixel_array


def test_clear_cached_pixel_array_removes_transient_attr_safely():
    ds = Dataset()
    ds._cached_pixel_array = object()

    clear_cached_pixel_array(ds)

    assert "_cached_pixel_array" not in ds.__dict__
    clear_cached_pixel_array(ds)
