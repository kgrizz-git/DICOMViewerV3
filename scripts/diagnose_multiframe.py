"""
DICOM Multi-Frame Diagnostic Tool

This script performs deep inspection of multi-frame DICOM files to diagnose
why pydicom might be loading them incorrectly.

Usage:
    python scripts/diagnose_multiframe.py <path_to_dicom_file>
"""

import pydicom
import sys
import os

def diagnose_multiframe(file_path):
    """Diagnose multi-frame DICOM file structure."""
    print(f"\n{'='*60}")
    print(f"DICOM Multi-Frame Diagnostic")
    print(f"{'='*60}")
    print(f"File: {os.path.basename(file_path)}")
    print(f"Path: {file_path}\n")
    
    # Load metadata only first
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
    except Exception as e:
        print(f"❌ FAILED to load file: {type(e).__name__}: {e}")
        return
    
    # Check basic multi-frame tags
    print("1. Basic Multi-Frame Tags:")
    print(f"   NumberOfFrames: {getattr(ds, 'NumberOfFrames', 'NOT FOUND')}")
    print(f"   Rows: {getattr(ds, 'Rows', 'NOT FOUND')}")
    print(f"   Columns: {getattr(ds, 'Columns', 'NOT FOUND')}")
    print(f"   SamplesPerPixel: {getattr(ds, 'SamplesPerPixel', 'NOT FOUND')}")
    print(f"   BitsAllocated: {getattr(ds, 'BitsAllocated', 'NOT FOUND')}")
    print(f"   BitsStored: {getattr(ds, 'BitsStored', 'NOT FOUND')}")
    print(f"   PixelRepresentation: {getattr(ds, 'PixelRepresentation', 'NOT FOUND')}")
    print(f"   PhotometricInterpretation: {getattr(ds, 'PhotometricInterpretation', 'NOT FOUND')}")
    
    # Check transfer syntax
    print(f"\n2. Transfer Syntax:")
    if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID'):
        ts_uid = ds.file_meta.TransferSyntaxUID
        print(f"   UID: {ts_uid}")
        print(f"   Name: {ts_uid.name if hasattr(ts_uid, 'name') else 'Unknown'}")
        print(f"   Is Compressed: {ts_uid.is_compressed if hasattr(ts_uid, 'is_compressed') else 'Unknown'}")
        print(f"   Is Encapsulated: {ts_uid.is_encapsulated if hasattr(ts_uid, 'is_encapsulated') else 'Unknown'}")
    else:
        print(f"   Transfer Syntax: NOT FOUND")
    
    # Check Per-frame Functional Groups Sequence
    print(f"\n3. Per-Frame Functional Groups:")
    if hasattr(ds, 'PerFrameFunctionalGroupsSequence'):
        seq = ds.PerFrameFunctionalGroupsSequence
        print(f"   Found: YES ✓")
        print(f"   Number of items: {len(seq)}")
        if len(seq) > 0:
            print(f"   First item keys: {list(seq[0].keys())[:5]}")
    else:
        print(f"   Found: NO")
    
    # Check Shared Functional Groups Sequence
    print(f"\n4. Shared Functional Groups:")
    if hasattr(ds, 'SharedFunctionalGroupsSequence'):
        print(f"   Found: YES ✓")
    else:
        print(f"   Found: NO")
    
    # Check pixel data characteristics
    print(f"\n5. Pixel Data Characteristics:")
    if hasattr(ds, 'PixelData'):
        pixel_data_length = len(ds.PixelData)
        print(f"   PixelData length: {pixel_data_length:,} bytes")
        print(f"   PixelData type: {type(ds.PixelData)}")
        
        # Calculate expected size
        rows = int(getattr(ds, 'Rows', 0))
        cols = int(getattr(ds, 'Columns', 0))
        frames = int(getattr(ds, 'NumberOfFrames', 1))
        bits = int(getattr(ds, 'BitsAllocated', 16))
        samples = int(getattr(ds, 'SamplesPerPixel', 1))
        expected = rows * cols * frames * samples * (bits // 8)
        print(f"   Expected size: {expected:,} bytes")
        print(f"   Difference: {pixel_data_length - expected:,} bytes ({(pixel_data_length - expected) / pixel_data_length * 100:.1f}%)")
        
        # Check if it's bytes (native) or something else (encapsulated)
        if isinstance(ds.PixelData, bytes):
            print(f"   Format: Native (bytes)")
        else:
            print(f"   Format: Possibly encapsulated")
    else:
        print(f"   PixelData: NOT FOUND")
    
    # Check for extended offset table
    print(f"\n6. Extended Offset Table:")
    if hasattr(ds, 'ExtendedOffsetTable'):
        print(f"   Found: YES ✓")
    else:
        print(f"   Found: NO")
    
    # Check SOPClassUID
    print(f"\n7. SOP Class:")
    if hasattr(ds, 'SOPClassUID'):
        sop_uid = ds.SOPClassUID
        print(f"   UID: {sop_uid}")
        print(f"   Name: {sop_uid.name if hasattr(sop_uid, 'name') else 'Unknown'}")
    
    # Try loading pixel array and check shape
    print(f"\n8. Pixel Array Loading Test:")
    try:
        print(f"   Loading full dataset...")
        ds_full = pydicom.dcmread(file_path)
        print(f"   Accessing pixel_array property...")
        pixel_array = ds_full.pixel_array
        print(f"   ✓ Successfully loaded")
        print(f"   Shape: {pixel_array.shape}")
        print(f"   Dtype: {pixel_array.dtype}")
        print(f"   Size in memory: {pixel_array.nbytes:,} bytes")
        
        frames = int(getattr(ds, 'NumberOfFrames', 1))
        rows = int(getattr(ds, 'Rows', 0))
        cols = int(getattr(ds, 'Columns', 0))
        print(f"   Expected shape: ({frames}, {rows}, {cols})")
        
        if len(pixel_array.shape) == 2:
            print(f"   ⚠️  WARNING: Loaded as 2D instead of 3D!")
            print(f"   This means pydicom loaded only the FIRST frame.")
            print(f"   The other {frames - 1} frames are not accessible via pixel_array!")
        elif len(pixel_array.shape) == 3:
            if pixel_array.shape[0] != frames:
                print(f"   ⚠️  WARNING: Frame count mismatch!")
                print(f"   Expected {frames} frames, got {pixel_array.shape[0]}")
            else:
                print(f"   ✓ Correct 3D shape with all frames")
        
    except Exception as e:
        print(f"   ❌ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Try alternate loading methods
    print(f"\n9. Alternate Loading Methods:")
    
    # Method A: Check if there's a way to get frame data directly
    print(f"   A. Checking for frame-specific data elements...")
    if hasattr(ds, 'PixelData'):
        # Try to see if pydicom has decompress method
        try:
            from pydicom.pixel_data_handlers.util import get_expected_length
            expected_len = get_expected_length(ds)
            print(f"      Expected pixel data length: {expected_len:,} bytes")
        except Exception as e:
            print(f"      Could not get expected length: {e}")
    
    # Method B: Check available pixel data handlers
    print(f"   B. Available pixel data handlers:")
    try:
        from pydicom.pixel_data_handlers import gdcm_handler, pillow_handler, numpy_handler
        handlers = []
        if gdcm_handler.is_available():
            handlers.append("gdcm")
        if pillow_handler.is_available():
            handlers.append("pillow")
        if numpy_handler.is_available():
            handlers.append("numpy")
        print(f"      Installed: {', '.join(handlers) if handlers else 'None'}")
    except:
        print(f"      Could not check handlers")
    
    print(f"\n{'='*60}")
    print(f"Diagnostic Complete")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_multiframe.py <dicom_file>")
        print("\nExample:")
        print("  python scripts/diagnose_multiframe.py path/to/mg_breast_tomo.dcm")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    diagnose_multiframe(file_path)

