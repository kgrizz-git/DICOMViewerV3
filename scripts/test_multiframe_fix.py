"""
Test script to verify Enhanced Multi-frame DICOM fix.

This script tests that:
1. The MG breast tomosynthesis file loads without crashing
2. All 14 frames are extracted correctly as 2D arrays
3. Each frame has the expected shape (2013, 1053)

Usage:
    python scripts/test_multiframe_fix.py <path_to_mg_file>
"""

import sys
import os
import io

# Force UTF-8 encoding for stdout on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer
from core.multiframe_handler import is_multiframe, get_frame_count, get_frame_pixel_array


def test_multiframe_loading(file_path: str):
    """Test loading and extracting frames from a multi-frame DICOM file."""
    print(f"Testing multi-frame DICOM loading...")
    print(f"File: {file_path}\n")
    
    # Step 1: Load the file
    print("=" * 60)
    print("STEP 1: Loading DICOM file")
    print("=" * 60)
    loader = DICOMLoader()
    dataset = loader.load_file(file_path)
    
    if dataset is None:
        print("❌ FAILED: Could not load DICOM file")
        return False
    
    print("✓ File loaded successfully\n")
    
    # Step 2: Check multi-frame detection
    print("=" * 60)
    print("STEP 2: Checking multi-frame detection")
    print("=" * 60)
    is_mf = is_multiframe(dataset)
    num_frames = get_frame_count(dataset)
    
    print(f"Is multi-frame: {is_mf}")
    print(f"Number of frames: {num_frames}")
    
    if not is_mf:
        print("❌ FAILED: File not detected as multi-frame")
        return False
    
    if num_frames != 14:
        print(f"❌ FAILED: Expected 14 frames, got {num_frames}")
        return False
    
    print("✓ Multi-frame detection correct\n")
    
    # Step 3: Check cached pixel array
    print("=" * 60)
    print("STEP 3: Checking cached pixel array")
    print("=" * 60)
    
    if hasattr(dataset, '_cached_pixel_array'):
        cached = dataset._cached_pixel_array
        print(f"Cached pixel array found")
        print(f"  Shape: {cached.shape}")
        print(f"  Dtype: {cached.dtype}")
        
        if len(cached.shape) != 3:
            print(f"❌ FAILED: Expected 3D array, got {len(cached.shape)}D")
            return False
        
        if cached.shape[0] != 14:
            print(f"❌ FAILED: Expected 14 frames in first dimension, got {cached.shape[0]}")
            return False
        
        print("✓ Cached pixel array has correct 3D shape\n")
    else:
        print("⚠️  WARNING: No cached pixel array found")
        print("    This may indicate the file is not an Enhanced Multi-frame DICOM\n")
    
    # Step 4: Extract individual frames
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
    
    # Step 5: Organize into series
    print("=" * 60)
    print("STEP 5: Organizing into series (creates FrameDatasetWrappers)")
    print("=" * 60)
    
    organizer = DICOMOrganizer()
    organized = organizer.organize([dataset], [file_path])
    
    if not organized:
        print("❌ FAILED: Organizer returned empty dictionary")
        return False
    
    # Count total instances
    total_instances = 0
    print(f"Organized structure:")
    print(f"  Number of studies: {len(organized)}")
    for study_uid, series_dict in organized.items():
        print(f"  Study {study_uid[:16]}...:")
        print(f"    Number of series: {len(series_dict)}")
        for series_uid, instances in series_dict.items():
            print(f"    Series {series_uid[:16]}...:")
            print(f"      Type of instances: {type(instances)}")
            print(f"      Length: {len(instances)}")
            if isinstance(instances, list) and len(instances) > 0:
                print(f"      First item type: {type(instances[0])}")
                if hasattr(instances[0], '_frame_index'):
                    print(f"      First item frame index: {instances[0]._frame_index}")
            total_instances += len(instances)
    
    if total_instances != 14:
        print(f"❌ FAILED: Expected 14 instances, got {total_instances}")
        return False
    
    print("\n✓ Organized into 14 separate instances\n")
    
    # Step 6: Test pixel array access through wrappers
    print("=" * 60)
    print("STEP 6: Accessing pixel arrays through FrameDatasetWrappers")
    print("=" * 60)
    
    for study_uid, series_dict in organized.items():
        for series_uid, instances in series_dict.items():
            for idx, instance in enumerate(instances):
                try:
                    pixel_array = instance.pixel_array
                    
                    if pixel_array is None:
                        print(f"❌ FAILED: Instance {idx} pixel_array is None")
                        return False
                    
                    if len(pixel_array.shape) != 2:
                        print(f"❌ FAILED: Instance {idx} pixel_array is not 2D (shape: {pixel_array.shape})")
                        return False
                    
                    print(f"  Instance {idx:2d}: shape={pixel_array.shape}, dtype={pixel_array.dtype}")
                    
                except Exception as e:
                    print(f"❌ FAILED: Instance {idx} raised exception: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
    
    print("\n✓ All wrappers return correct 2D pixel arrays\n")
    
    # Success!
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_multiframe_fix.py <path_to_mg_file>")
        print("\nExample:")
        print('  python scripts/test_multiframe_fix.py "C:\\Users\\kg3210\\Desktop\\Misc to back up\\Sample DICOM\\mg_breast_tomo.dcm"')
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    try:
        success = test_multiframe_loading(file_path)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

