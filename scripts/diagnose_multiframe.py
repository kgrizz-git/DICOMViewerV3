"""
DICOM Multi-Frame Diagnostic Tool

This script performs deep inspection of multi-frame DICOM files to diagnose
why pydicom might be loading them incorrectly.

Usage:
    python scripts/diagnose_multiframe.py <path_to_dicom_file>
"""

import os
import sys

import pydicom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.log_sanitizer import sanitized_format_exc


def _print_traceback_for_debug(prefix: str = "   ") -> None:
    if os.environ.get("DICOM_DEBUG_TRACEBACKS") == "1":
        import traceback

        traceback.print_exc()
        return

    print(f"{prefix}Sanitized traceback follows. Set DICOM_DEBUG_TRACEBACKS=1 for the raw traceback.")
    print(sanitized_format_exc())


def _print_basic_tags(ds) -> None:
    print("1. Basic Multi-Frame Tags:")
    print(f"   NumberOfFrames: {getattr(ds, 'NumberOfFrames', 'NOT FOUND')}")
    print(f"   Rows: {getattr(ds, 'Rows', 'NOT FOUND')}")
    print(f"   Columns: {getattr(ds, 'Columns', 'NOT FOUND')}")
    print(f"   SamplesPerPixel: {getattr(ds, 'SamplesPerPixel', 'NOT FOUND')}")
    print(f"   BitsAllocated: {getattr(ds, 'BitsAllocated', 'NOT FOUND')}")
    print(f"   BitsStored: {getattr(ds, 'BitsStored', 'NOT FOUND')}")
    print(f"   PixelRepresentation: {getattr(ds, 'PixelRepresentation', 'NOT FOUND')}")
    print(f"   PhotometricInterpretation: {getattr(ds, 'PhotometricInterpretation', 'NOT FOUND')}")


def _print_transfer_syntax(ds) -> None:
    print("\n2. Transfer Syntax:")
    if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID'):
        ts_uid = ds.file_meta.TransferSyntaxUID
        print(f"   UID: {ts_uid}")
        print(f"   Name: {ts_uid.name if hasattr(ts_uid, 'name') else 'Unknown'}")
        print(f"   Is Compressed: {ts_uid.is_compressed if hasattr(ts_uid, 'is_compressed') else 'Unknown'}")
        print(f"   Is Encapsulated: {ts_uid.is_encapsulated if hasattr(ts_uid, 'is_encapsulated') else 'Unknown'}")
    else:
        print("   Transfer Syntax: NOT FOUND")


def _print_per_frame_functional_groups(ds) -> None:
    print("\n3. Per-Frame Functional Groups:")
    if hasattr(ds, 'PerFrameFunctionalGroupsSequence'):
        seq = ds.PerFrameFunctionalGroupsSequence
        print("   Found: YES ✓")
        print(f"   Number of items: {len(seq)}")
        if len(seq) > 0:
            print(f"   First item keys: {list(seq[0].keys())[:5]}")
    else:
        print("   Found: NO")


def _print_shared_functional_groups(ds) -> None:
    print("\n4. Shared Functional Groups:")
    if hasattr(ds, 'SharedFunctionalGroupsSequence'):
        print("   Found: YES ✓")
    else:
        print("   Found: NO")


def _print_pixel_data_characteristics(ds) -> None:
    print("\n5. Pixel Data Characteristics:")
    if not hasattr(ds, 'PixelData'):
        print("   PixelData: NOT FOUND")
        return

    pixel_data_length = len(ds.PixelData)
    print(f"   PixelData length: {pixel_data_length:,} bytes")
    print(f"   PixelData type: {type(ds.PixelData)}")

    rows = int(getattr(ds, 'Rows', 0))
    cols = int(getattr(ds, 'Columns', 0))
    frames = int(getattr(ds, 'NumberOfFrames', 1))
    bits = int(getattr(ds, 'BitsAllocated', 16))
    samples = int(getattr(ds, 'SamplesPerPixel', 1))
    expected = rows * cols * frames * samples * (bits // 8)
    print(f"   Expected size: {expected:,} bytes")
    print(f"   Difference: {pixel_data_length - expected:,} bytes ({(pixel_data_length - expected) / pixel_data_length * 100:.1f}%)")

    if isinstance(ds.PixelData, bytes):
        print("   Format: Native (bytes)")
    else:
        print("   Format: Possibly encapsulated")


def _print_extended_offset_table(ds) -> None:
    print("\n6. Extended Offset Table:")
    if hasattr(ds, 'ExtendedOffsetTable'):
        print("   Found: YES ✓")
    else:
        print("   Found: NO")


def _print_sop_class(ds) -> None:
    print("\n7. SOP Class:")
    if hasattr(ds, 'SOPClassUID'):
        sop_uid = ds.SOPClassUID
        print(f"   UID: {sop_uid}")
        print(f"   Name: {sop_uid.name if hasattr(sop_uid, 'name') else 'Unknown'}")


def _print_pixel_array_loading_test(ds, dicom_path) -> None:
    print("\n8. Pixel Array Loading Test:")
    try:
        print("   Loading full dataset...")
        ds_full = pydicom.dcmread(dicom_path)
        print("   Accessing pixel_array property...")
        pixel_array = ds_full.pixel_array
        print("   ✓ Successfully loaded")
        print(f"   Shape: {pixel_array.shape}")
        print(f"   Dtype: {pixel_array.dtype}")
        print(f"   Size in memory: {pixel_array.nbytes:,} bytes")

        frames = int(getattr(ds, 'NumberOfFrames', 1))
        rows = int(getattr(ds, 'Rows', 0))
        cols = int(getattr(ds, 'Columns', 0))
        print(f"   Expected shape: ({frames}, {rows}, {cols})")

        if len(pixel_array.shape) == 2:
            print("   ⚠️  WARNING: Loaded as 2D instead of 3D!")
            print("   This means pydicom loaded only the FIRST frame.")
            print(f"   The other {frames - 1} frames are not accessible via pixel_array!")
        elif len(pixel_array.shape) == 3:
            if pixel_array.shape[0] != frames:
                print("   ⚠️  WARNING: Frame count mismatch!")
                print(f"   Expected {frames} frames, got {pixel_array.shape[0]}")
            else:
                print("   ✓ Correct 3D shape with all frames")

    except Exception as e:
        print(f"   ❌ FAILED: {type(e).__name__}: {e}")
        _print_traceback_for_debug()


def _print_alternate_loading_methods(ds) -> None:
    print("\n9. Alternate Loading Methods:")

    # Method A: Check if there's a way to get frame data directly
    print("   A. Checking for frame-specific data elements...")
    if hasattr(ds, 'PixelData'):
        try:
            from pydicom.pixel_data_handlers.util import get_expected_length
            expected_len = get_expected_length(ds)
            print(f"      Expected pixel data length: {expected_len:,} bytes")
        except Exception as e:
            print(f"      Could not get expected length: {e}")

    # Method B: Check available pixel data handlers
    print("   B. Available pixel data handlers:")
    try:
        from pydicom.pixel_data_handlers import (
            gdcm_handler,
            numpy_handler,
            pillow_handler,
        )
        handlers = []
        if gdcm_handler.is_available():
            handlers.append("gdcm")
        if pillow_handler.is_available():
            handlers.append("pillow")
        if numpy_handler.is_available():
            handlers.append("numpy")
        print(f"      Installed: {', '.join(handlers) if handlers else 'None'}")
    except Exception as e:
        print(f"      Could not check handlers: {e}")


def diagnose_multiframe(dicom_path):
    """Diagnose multi-frame DICOM file structure."""
    print(f"\n{'='*60}")
    print("DICOM Multi-Frame Diagnostic")
    print(f"{'='*60}")
    print(f"File: {os.path.basename(dicom_path)}")
    print(f"Path: {dicom_path}\n")

    # Load metadata only first
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
    except Exception as e:
        print(f"❌ FAILED to load file: {type(e).__name__}: {e}")
        return

    _print_basic_tags(ds)
    _print_transfer_syntax(ds)
    _print_per_frame_functional_groups(ds)
    _print_shared_functional_groups(ds)
    _print_pixel_data_characteristics(ds)
    _print_extended_offset_table(ds)
    _print_sop_class(ds)
    _print_pixel_array_loading_test(ds, dicom_path)
    _print_alternate_loading_methods(ds)

    print(f"\n{'='*60}")
    print("Diagnostic Complete")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_multiframe.py <dicom_file>")
        print("\nExample:")
        print("  python scripts/diagnose_multiframe.py path/to/mg_breast_tomo.dcm")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    diagnose_multiframe(input_path)
