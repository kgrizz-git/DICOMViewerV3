# Multi-Frame DICOM Research Findings

## Problem Summary
The DICOM viewer crashes silently when loading tomographic mammography (MG) DICOM files that contain multiple frames (14 frames in a single .dcm file). These files are very large (approximately 3000x3000 pixels per frame).

## Research Findings

### 1. Multi-Frame DICOM Structure
- **NumberOfFrames Tag (0028,0008)**: DICOM multi-frame files contain a `NumberOfFrames` tag indicating how many frames are stored in a single instance
- **Pixel Array Structure**: When accessing `dataset.pixel_array` on a multi-frame DICOM, pydicom returns a 3D numpy array with shape `(num_frames, height, width)`
- **Memory Implications**: Loading all frames at once can consume significant memory:
  - Example: 14 frames × 3000 × 3000 × 2 bytes (uint16) = ~504 MB just for pixel data
  - This doesn't include overhead from numpy arrays, Python objects, and processing

### 2. Current Code Issues

#### Issue 1: No Multi-Frame Detection
- The code does not check for the `NumberOfFrames` tag
- Multi-frame files are treated as single-frame files
- The code has basic 3D array handling in `dataset_to_image()` (line 319-322) that takes the first frame, but this is insufficient

#### Issue 2: Memory-Intensive Loading
- `pydicom.dcmread()` loads the entire file into memory immediately
- Accessing `dataset.pixel_array` loads ALL frames at once
- No deferred or lazy loading for large files

#### Issue 3: Incomplete Multi-Frame Handling
- Multi-frame files are not split into individual "slices" for navigation
- The slice navigator expects one dataset per slice, but multi-frame files have multiple frames in one dataset
- The organizer doesn't handle multi-frame files properly

#### Issue 4: Silent Crash
- Exceptions may be caught but not properly displayed
- Memory errors (MemoryError) might cause the application to crash without showing error messages
- No proper error handling for large file loading

### 3. Proprietary Format Considerations
- Some manufacturers (e.g., Hologic) use proprietary formats for tomosynthesis
- These may embed pixel data in private attributes
- However, standard multi-frame DICOM should still be supported

### 4. Best Practices for Multi-Frame DICOM Handling

#### Detection
- Check for `NumberOfFrames` tag (0028,0008) in the dataset
- If present and > 1, treat as multi-frame

#### Processing Options
1. **Split into Individual Frames**: Create separate "virtual" datasets for each frame
2. **Frame-by-Frame Access**: Access frames individually using array indexing: `pixel_array[frame_index]`
3. **Lazy Loading**: Only load frames when needed

#### Memory Management
- Use `pydicom.dcmread()` with `defer_size` parameter for large files
- Consider using `pydicom.dcmread()` with `stop_before_pixels=True` to read metadata first
- Load pixel data only when needed for display

### 5. Recommended Solution Approach

1. **Detect Multi-Frame Files**: Check for `NumberOfFrames` tag during loading
2. **Split Multi-Frame Files**: Create individual frame datasets or wrapper objects
3. **Update Organizer**: Handle multi-frame files in the organization logic
4. **Improve Error Handling**: Add comprehensive error handling with user-visible error messages
5. **Memory Optimization**: Consider deferred pixel loading for very large files

## Technical Details

### DICOM Tags for Multi-Frame
- **NumberOfFrames (0028,0008)**: Number of frames in the multi-frame image
- **Frame Increment Pointer (0028,0009)**: Points to tags that vary per frame
- **Per-Frame Functional Groups Sequence (5200,9230)**: Contains per-frame attributes

### pydicom Behavior
- `dataset.pixel_array` returns numpy array with shape `(frames, rows, columns)` for multi-frame
- Single-frame returns shape `(rows, columns)`
- Accessing pixel_array loads all pixel data into memory immediately

### Memory Calculation Example
For a 14-frame tomographic MG file:
- Dimensions: 14 frames × 3000 × 3000 pixels
- Data type: Typically uint16 (2 bytes per pixel)
- Total pixel data: 14 × 3000 × 3000 × 2 = 252,000,000 bytes ≈ 240 MB
- With numpy overhead and processing: Can easily exceed 500 MB

## References
- DICOM Standard Part 3: Information Object Definitions
- pydicom documentation: Multi-frame image handling
- Various DICOM viewer discussions on multi-frame support issues

