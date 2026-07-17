"""
Test script to verify Enhanced Multi-frame DICOM fix.

This script tests that:
1. The MG breast tomosynthesis file loads without crashing
2. All 14 frames are extracted correctly as 2D arrays
3. Each frame has the expected shape (2013, 1053)

Usage:
    python scripts/test_multiframe_fix.py <path_to_mg_file>
"""
import io
import os
import sys

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

# Force UTF-8 encoding for stdout on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.multiframe_handler import (
    get_frame_count,
    get_frame_pixel_array,
    is_multiframe,
)
from utils.log_sanitizer import sanitized_format_exc


def _print_traceback_for_debug() -> None:
    print("Sanitized traceback follows.")
    print(sanitized_format_exc())


def _step1_load_file(file_path: str):
    """Load the DICOM file. Returns the dataset, or None on failure."""
    print("=" * 60)
    print("STEP 1: Loading DICOM file")
    print("=" * 60)
    loader = DICOMLoader()
    dataset = loader.load_file(file_path)

    if dataset is None:
        print("❌ FAILED: Could not load DICOM file")
        return None

    print("✓ File loaded successfully\n")
    return dataset


def _step2_check_multiframe_detection(dataset):
    """Verify multi-frame detection and frame count. Returns num_frames, or None on failure."""
    print("=" * 60)
    print("STEP 2: Checking multi-frame detection")
    print("=" * 60)
    is_mf = is_multiframe(dataset)
    num_frames = get_frame_count(dataset)

    print(f"Is multi-frame: {is_mf}")
    print(f"Number of frames: {num_frames}")

    if not is_mf:
        print("❌ FAILED: File not detected as multi-frame")
        return None

    if num_frames != 14:
        print(f"❌ FAILED: Expected 14 frames, got {num_frames}")
        return None

    print("✓ Multi-frame detection correct\n")
    return num_frames


def _step3_check_cached_pixel_array(dataset) -> bool:
    """Verify the cached pixel array shape, if present. Returns False only on a shape mismatch."""
    print("=" * 60)
    print("STEP 3: Checking cached pixel array")
    print("=" * 60)

    if not hasattr(dataset, '_cached_pixel_array'):
        print("⚠️  WARNING: No cached pixel array found")
        print("    This may indicate the file is not an Enhanced Multi-frame DICOM\n")
        return True

    cached = dataset._cached_pixel_array
    print("Cached pixel array found")
    print(f"  Shape: {cached.shape}")
    print(f"  Dtype: {cached.dtype}")

    if len(cached.shape) != 3:
        print(f"❌ FAILED: Expected 3D array, got {len(cached.shape)}D")
        return False

    if cached.shape[0] != 14:
        print(f"❌ FAILED: Expected 14 frames in first dimension, got {cached.shape[0]}")
        return False

    print("✓ Cached pixel array has correct 3D shape\n")
    return True


def _step4_extract_frames(dataset, num_frames: int) -> bool:
    """Extract each frame as a 2D array. Returns False on the first bad frame."""
    print("=" * 60)
    print("STEP 4: Extracting individual frames")
    print("=" * 60)

    for frame_idx in range(num_frames):
        frame = get_frame_pixel_array(dataset, frame_idx)

        if frame is None:
            print(f"❌ FAILED: Frame {frame_idx} extraction returned None")
            return False

        if len(frame.shape) != 2:
            print(f"❌ FAILED: Frame {frame_idx} is not 2D (shape: {frame.shape})")
            return False

        print(f"  Frame {frame_idx:2d}: shape={frame.shape}, dtype={frame.dtype}")

    print("\n✓ All frames extracted successfully\n")
    return True


def _step5_organize_into_series(dataset, file_path: str):
    """Organize the dataset into studies/series. Returns the organized dict, or None on failure."""
    print("=" * 60)
    print("STEP 5: Organizing into series (creates FrameDatasetWrappers)")
    print("=" * 60)

    organizer = DICOMOrganizer()
    organized = organizer.organize([dataset], [file_path])

    if not organized:
        print("❌ FAILED: Organizer returned empty dictionary")
        return None

    total_instances = 0
    print("Organized structure:")
    print(f"  Number of studies: {len(organized)}")
    for study_uid, series_dict in organized.items():
        print_redacted(f"  Study {study_uid[:16]}...:")
        print(f"    Number of series: {len(series_dict)}")
        for series_uid, instances in series_dict.items():
            print_redacted(f"    Series {series_uid[:16]}...:")
            print(f"      Type of instances: {type(instances)}")
            print(f"      Length: {len(instances)}")
            if isinstance(instances, list) and len(instances) > 0:
                print(f"      First item type: {type(instances[0])}")
                if hasattr(instances[0], '_frame_index'):
                    print(f"      First item frame index: {instances[0]._frame_index}")
            total_instances += len(instances)

    if total_instances != 14:
        print(f"❌ FAILED: Expected 14 instances, got {total_instances}")
        return None

    print("\n✓ Organized into 14 separate instances\n")
    return organized


def _iter_wrapper_instances(organized):
    """Yield every organized frame wrapper in display order."""
    for series_dict in organized.values():
        for instances in series_dict.values():
            yield from instances


def _wrapper_pixel_array_error(idx: int, pixel_array) -> str | None:
    """Return an error message when a wrapper pixel array is invalid."""
    if pixel_array is None:
        return f"❌ FAILED: Instance {idx} pixel_array is None"
    if len(pixel_array.shape) != 2:
        return f"❌ FAILED: Instance {idx} pixel_array is not 2D (shape: {pixel_array.shape})"
    return None


def _step6_check_wrapper_pixel_arrays(organized) -> bool:
    """Access pixel_array through every FrameDatasetWrapper. Returns False on the first failure."""
    print("=" * 60)
    print("STEP 6: Accessing pixel arrays through FrameDatasetWrappers")
    print("=" * 60)

    for idx, instance in enumerate(_iter_wrapper_instances(organized)):
        try:
            pixel_array = instance.pixel_array
        except Exception as e:
            print_redacted(f"❌ FAILED: Instance {idx} raised exception: {e}")
            _print_traceback_for_debug()
            return False

        error = _wrapper_pixel_array_error(idx, pixel_array)
        if error is not None:
            print_redacted(error)
            return False

        print(f"  Instance {idx:2d}: shape={pixel_array.shape}, dtype={pixel_array.dtype}")

    print("\n✓ All wrappers return correct 2D pixel arrays\n")
    return True


def test_multiframe_loading(file_path: str):
    """Test loading and extracting frames from a multi-frame DICOM file."""
    print("Testing multi-frame DICOM loading...")
    print_redacted(f"File: {file_path}\n")

    dataset = _step1_load_file(file_path)
    if dataset is None:
        return False

    num_frames = _step2_check_multiframe_detection(dataset)
    if num_frames is None:
        return False

    if not _step3_check_cached_pixel_array(dataset):
        return False

    if not _step4_extract_frames(dataset, num_frames):
        return False

    organized = _step5_organize_into_series(dataset, file_path)
    if organized is None:
        return False

    if not _step6_check_wrapper_pixel_arrays(organized):
        return False

    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_multiframe_fix.py <path_to_mg_file>")
        print("\nExample:")
        print('  python scripts/test_multiframe_fix.py "/path/to/mg_breast_tomo.dcm"')
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print_redacted(f"Error: File not found: {file_path}")
        sys.exit(1)

    try:
        success = test_multiframe_loading(file_path)
        sys.exit(0 if success else 1)
    except Exception as e:
        print_redacted(f"\n❌ FATAL ERROR: {e}")
        _print_traceback_for_debug()
        sys.exit(1)
