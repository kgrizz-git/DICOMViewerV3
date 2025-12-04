# Medical Image Fusion Research

This document summarizes research on medical image fusion techniques for combining datasets like PET-CT or MR-CT into a unified visualization.

## Overview

Image fusion (e.g., PET-CT, MR-CT) involves three main steps:
1. **Image Registration** - Aligning datasets to a common coordinate system
2. **Resampling** - Transforming one dataset to match the other's spatial grid
3. **Visualization/Overlay** - Displaying both datasets together with appropriate blending

---

## 1. Image Registration Approaches

### A. Using DICOM Spatial Information (Simplest Case)

When datasets share the same **Frame of Reference UID**, they're already in the same coordinate system. The key DICOM spatial tags are:

| Tag | Description |
|-----|-------------|
| `ImagePositionPatient` | 3D position of the first voxel (x, y, z) |
| `ImageOrientationPatient` | Row/column direction cosines (6 values) |
| `PixelSpacing` | In-plane pixel dimensions (row, column) |
| `SliceThickness` | Nominal slice thickness |
| `SliceLocation` | Relative position of slice |
| `FrameOfReferenceUID` | Identifies common coordinate system |

**For same-scanner PET-CT acquisitions**, these can be used directly to align images without complex registration algorithms.

### B. Intensity-Based Registration (General Case)

For datasets from different scanners or time points, algorithmic registration is needed:

| Algorithm | Type | Best For | Complexity |
|-----------|------|----------|------------|
| **Mutual Information** | Metric | Multi-modal (PET-CT, MR-CT) | Medium |
| **Rigid Registration** | Transform | No deformation (6 DOF) | Low |
| **Affine Registration** | Transform | Scaling/shearing (12 DOF) | Medium |
| **B-Spline/FFD** | Transform | Non-rigid deformation | High |
| **Demons** | Deformable | Large deformations | High |

**Mutual Information** is the gold standard for multi-modal registration because it works with different intensity distributions by measuring statistical dependence between images.

### C. Registration Pipeline

A typical multi-modal registration pipeline:

1. **Preprocessing**
   - Normalize intensities
   - Resample to isotropic voxels (optional)
   - Apply smoothing to reduce noise

2. **Coarse Alignment**
   - Use image centers or centroids
   - Apply rigid transform (translation + rotation)

3. **Fine Alignment**
   - Optimize mutual information metric
   - Use multi-resolution approach (coarse to fine)

4. **Optional: Deformable Registration**
   - Apply B-spline or demons for non-rigid deformation
   - Useful for breathing motion, organ deformation

---

## 2. Python Libraries for Implementation

### SimpleITK (Recommended)

SimpleITK is a simplified wrapper around ITK (Insight Toolkit), ideal for medical image registration.

**Installation:**
```bash
pip install SimpleITK
```

**Basic Registration Example:**

```python
import SimpleITK as sitk
import numpy as np

def register_images(fixed_image, moving_image):
    """
    Register moving_image to fixed_image using mutual information.
    
    Args:
        fixed_image: Reference image (e.g., CT as sitk.Image)
        moving_image: Image to transform (e.g., PET as sitk.Image)
    
    Returns:
        Tuple of (registered_image, transform)
    """
    # Set up registration method
    registration_method = sitk.ImageRegistrationMethod()
    
    # Similarity metric - Mutual Information for multi-modal
    registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
    registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
    registration_method.SetMetricSamplingPercentage(0.01)
    
    # Interpolator
    registration_method.SetInterpolator(sitk.sitkLinear)
    
    # Optimizer - gradient descent
    registration_method.SetOptimizerAsGradientDescent(
        learningRate=1.0,
        numberOfIterations=100,
        convergenceMinimumValue=1e-6,
        convergenceWindowSize=10
    )
    registration_method.SetOptimizerScalesFromPhysicalShift()
    
    # Initial transform - rigid (translation + rotation)
    initial_transform = sitk.CenteredTransformInitializer(
        fixed_image, 
        moving_image, 
        sitk.Euler3DTransform(), 
        sitk.CenteredTransformInitializerFilter.GEOMETRY
    )
    registration_method.SetInitialTransform(initial_transform, inPlace=False)
    
    # Multi-resolution approach for robustness
    registration_method.SetShrinkFactorsPerLevel([4, 2, 1])
    registration_method.SetSmoothingSigmasPerLevel([2, 1, 0])
    registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    
    # Execute registration
    final_transform = registration_method.Execute(fixed_image, moving_image)
    
    # Apply transform to moving image
    registered_image = sitk.Resample(
        moving_image,
        fixed_image,
        final_transform,
        sitk.sitkLinear,
        0.0,  # default pixel value
        moving_image.GetPixelID()
    )
    
    return registered_image, final_transform
```

**DICOM to SimpleITK Conversion:**

```python
def dicom_to_sitk(datasets, pixel_arrays):
    """
    Convert DICOM series to SimpleITK image with proper spatial information.
    
    Args:
        datasets: List of pydicom datasets (sorted by slice position)
        pixel_arrays: List of 2D numpy arrays
    
    Returns:
        sitk.Image with proper origin, spacing, and direction
    """
    # Stack into 3D volume
    volume = np.stack(pixel_arrays, axis=0)
    
    # Create SimpleITK image
    sitk_image = sitk.GetImageFromArray(volume)
    
    # Extract spatial information from first dataset
    ds = datasets[0]
    
    # Origin (ImagePositionPatient)
    if hasattr(ds, 'ImagePositionPatient'):
        origin = [float(x) for x in ds.ImagePositionPatient]
        sitk_image.SetOrigin(origin)
    
    # Pixel spacing
    pixel_spacing = [1.0, 1.0]
    if hasattr(ds, 'PixelSpacing'):
        pixel_spacing = [float(x) for x in ds.PixelSpacing]
    
    # Slice spacing (from consecutive slices or SliceThickness)
    slice_spacing = 1.0
    if len(datasets) > 1 and hasattr(datasets[0], 'ImagePositionPatient'):
        pos1 = np.array([float(x) for x in datasets[0].ImagePositionPatient])
        pos2 = np.array([float(x) for x in datasets[1].ImagePositionPatient])
        slice_spacing = np.linalg.norm(pos2 - pos1)
    elif hasattr(ds, 'SliceThickness'):
        slice_spacing = float(ds.SliceThickness)
    
    # SimpleITK uses (x, y, z) order for spacing
    sitk_image.SetSpacing([pixel_spacing[1], pixel_spacing[0], slice_spacing])
    
    # Direction cosines (ImageOrientationPatient)
    if hasattr(ds, 'ImageOrientationPatient'):
        iop = [float(x) for x in ds.ImageOrientationPatient]
        row_cosines = np.array(iop[0:3])
        col_cosines = np.array(iop[3:6])
        slice_cosines = np.cross(row_cosines, col_cosines)
        
        # Direction matrix (column-major for SimpleITK)
        direction = [
            row_cosines[0], col_cosines[0], slice_cosines[0],
            row_cosines[1], col_cosines[1], slice_cosines[1],
            row_cosines[2], col_cosines[2], slice_cosines[2]
        ]
        sitk_image.SetDirection(direction)
    
    return sitk_image
```

### Alternative Libraries

| Library | Pros | Cons |
|---------|------|------|
| **SimpleITK** | Easy API, well-documented | Large dependency |
| **ITK** | Full control, more algorithms | Complex API |
| **ANTsPy** | State-of-art deformable registration | Less documentation |
| **DIPY** | Good for diffusion MRI | Specialized |
| **scipy.ndimage** | Lightweight, basic transforms | No registration algorithms |

---

## 3. Visualization / Overlay Techniques

### A. Alpha Blending

The most common approach - blend grayscale anatomical with colormap functional:

```python
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

def create_fusion_overlay(ct_array, pet_array, alpha=0.5, colormap='hot'):
    """
    Create a fused display of CT (grayscale) with PET (colormap) overlay.
    
    Args:
        ct_array: 2D numpy array (anatomical - CT/MR)
        pet_array: 2D numpy array (functional - PET/SPECT), same shape as ct_array
        alpha: Transparency of PET overlay (0-1)
        colormap: Matplotlib colormap name for PET
    
    Returns:
        RGB numpy array suitable for display
    """
    # Normalize CT to 0-1 range
    ct_min, ct_max = ct_array.min(), ct_array.max()
    if ct_max > ct_min:
        ct_normalized = (ct_array - ct_min) / (ct_max - ct_min)
    else:
        ct_normalized = np.zeros_like(ct_array, dtype=float)
    
    # Convert CT grayscale to RGB
    ct_rgb = np.stack([ct_normalized] * 3, axis=-1)
    
    # Normalize PET to 0-1
    pet_min, pet_max = pet_array.min(), pet_array.max()
    if pet_max > pet_min:
        pet_normalized = (pet_array - pet_min) / (pet_max - pet_min)
    else:
        pet_normalized = np.zeros_like(pet_array, dtype=float)
    
    # Apply colormap to PET
    cmap = plt.get_cmap(colormap)
    pet_colored = cmap(pet_normalized)[:, :, :3]  # RGB, drop alpha
    
    # Alpha blend: result = (1-alpha)*CT + alpha*PET
    fused = (1 - alpha) * ct_rgb + alpha * pet_colored
    
    # Convert to uint8
    fused_uint8 = (np.clip(fused, 0, 1) * 255).astype(np.uint8)
    
    return fused_uint8
```

### B. Threshold-Based Overlay

Clinical viewers often hide low PET values to reduce noise:

```python
def create_threshold_overlay(ct_array, pet_array, threshold_percent=20, 
                             colormap='hot', alpha=0.7):
    """
    Create overlay where PET only shows above a threshold (like clinical viewers).
    
    Args:
        ct_array: 2D numpy array (anatomical)
        pet_array: 2D numpy array (functional)
        threshold_percent: Percentage of max PET value below which to hide
        colormap: Matplotlib colormap for PET
        alpha: Transparency for PET regions above threshold
    
    Returns:
        RGB numpy array
    """
    # Normalize CT
    ct_norm = (ct_array - ct_array.min()) / (ct_array.max() - ct_array.min() + 1e-8)
    ct_rgb = np.stack([ct_norm] * 3, axis=-1)
    
    # Normalize PET with threshold
    pet_max = pet_array.max()
    threshold = pet_max * (threshold_percent / 100.0)
    pet_norm = np.clip((pet_array - threshold) / (pet_max - threshold + 1e-8), 0, 1)
    
    # Create mask for values above threshold
    mask = pet_array > threshold
    
    # Apply colormap
    cmap = plt.get_cmap(colormap)
    pet_colored = cmap(pet_norm)[:, :, :3]
    
    # Blend only where mask is True
    alpha_channel = np.where(mask, alpha, 0.0)
    
    fused = ct_rgb * (1 - alpha_channel[:, :, np.newaxis]) + \
            pet_colored * alpha_channel[:, :, np.newaxis]
    
    return (np.clip(fused, 0, 1) * 255).astype(np.uint8)
```

### C. Color Maps for Functional Imaging

Common colormaps used clinically:

| Colormap | Description | Best For |
|----------|-------------|----------|
| **hot** | Black → Red → Yellow → White | PET (most common) |
| **jet** | Blue → Cyan → Green → Yellow → Red | Traditional, but has rainbow issues |
| **viridis** | Perceptually uniform purple → yellow | General purpose |
| **inferno** | Similar to hot, perceptually uniform | PET alternative |
| **plasma** | Purple → pink → orange → yellow | Alternative |
| **rainbow** | Standard rainbow spectrum | SPECT |

### D. Checkerboard and Split Views

Alternative visualization modes:

```python
def create_checkerboard_view(image1, image2, grid_size=8):
    """Create checkerboard comparison of two images."""
    h, w = image1.shape[:2]
    result = np.copy(image1)
    
    tile_h = h // grid_size
    tile_w = w // grid_size
    
    for i in range(grid_size):
        for j in range(grid_size):
            if (i + j) % 2 == 1:
                y1, y2 = i * tile_h, min((i + 1) * tile_h, h)
                x1, x2 = j * tile_w, min((j + 1) * tile_w, w)
                result[y1:y2, x1:x2] = image2[y1:y2, x1:x2]
    
    return result

def create_split_view(image1, image2, split_position=0.5, vertical=True):
    """Create split view of two images."""
    h, w = image1.shape[:2]
    result = np.copy(image1)
    
    if vertical:
        split_x = int(w * split_position)
        result[:, split_x:] = image2[:, split_x:]
    else:
        split_y = int(h * split_position)
        result[split_y:, :] = image2[split_y:, :]
    
    return result
```

---

## 4. Resampling Between Different Grids

When images have different resolutions or orientations, resampling is required:

```python
import SimpleITK as sitk

def resample_to_reference(moving_image, reference_image, interpolator=sitk.sitkLinear):
    """
    Resample moving_image to match the spatial properties of reference_image.
    
    Args:
        moving_image: Image to resample (sitk.Image)
        reference_image: Reference image defining output grid (sitk.Image)
        interpolator: Interpolation method
    
    Returns:
        Resampled image matching reference geometry
    """
    resampler = sitk.ResampleImageFilter()
    resampler.SetReferenceImage(reference_image)
    resampler.SetInterpolator(interpolator)
    resampler.SetDefaultPixelValue(0)
    resampler.SetTransform(sitk.Transform())  # Identity transform
    
    return resampler.Execute(moving_image)

def resample_to_isotropic(image, iso_spacing=1.0):
    """
    Resample image to isotropic voxels.
    
    Args:
        image: Input image (sitk.Image)
        iso_spacing: Desired isotropic spacing in mm
    
    Returns:
        Resampled isotropic image
    """
    original_spacing = image.GetSpacing()
    original_size = image.GetSize()
    
    new_spacing = [iso_spacing] * 3
    new_size = [
        int(round(original_size[i] * original_spacing[i] / iso_spacing))
        for i in range(3)
    ]
    
    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(new_spacing)
    resampler.SetSize(new_size)
    resampler.SetOutputDirection(image.GetDirection())
    resampler.SetOutputOrigin(image.GetOrigin())
    resampler.SetInterpolator(sitk.sitkLinear)
    
    return resampler.Execute(image)
```

---

## 5. Commercial and Open Source References

### Software Tools

| Software | Type | Fusion Approach | Notes |
|----------|------|-----------------|-------|
| **3D Slicer** | Open Source | Full registration pipeline | Python scriptable, extensive |
| **OsiriX** | Commercial/Free | DICOM-based alignment | macOS only |
| **RadiAnt** | Commercial | Manual + auto alignment | Simple UI, Windows |
| **Horos** | Open Source | Fork of OsiriX | macOS only |
| **ITK-SNAP** | Open Source | Manual alignment | Primarily segmentation |
| **MeVisLab** | Free/Commercial | Advanced registration | Research-oriented |
| **Elastix** | Open Source | ITK-based CLI tool | Highly configurable |
| **FALCON** | Open Source | PET motion correction | GitHub: ENHANCE-PET/FALCON |

### Research Papers

1. **Mutual Information Registration**
   - "Automated 3-dimensional registration of stand-alone 18F-FDG whole-body PET with CT" (J Nucl Med, 2003)
   - Uses mutual information for elastic 3D registration

2. **Pixel-Feature Hybrid Fusion**
   - "Pixel-feature hybrid fusion for PET/CT images" (J Digit Imaging, 2010)
   - Selective masking of colormap segments

3. **Free-Form Deformations**
   - "PET-CT image registration in the chest using free-form deformations" (IEEE Trans Med Imaging, 2003)
   - B-spline based non-rigid registration

4. **Deep Learning Approaches**
   - "Unsupervised Multi-Modal Medical Image Registration via Discriminator-Free Image-to-Image Translation" (arXiv, 2024)
   - Modern CNN-based registration methods

---

## 6. Key Considerations for Implementation

### Performance

- **Memory**: 3D volumes can be large (512×512×300 = 78M voxels)
- **Speed**: Registration can take seconds to minutes
- **GPU**: Consider GPU acceleration for large datasets

### User Experience

- Provide visual feedback during registration
- Allow manual adjustment after automatic alignment
- Support undo/redo for alignment changes

### Clinical Accuracy

- Validate registration accuracy with landmarks
- Consider respiratory motion artifacts
- Document registration parameters for reproducibility

### DICOM Compliance

- Check Frame of Reference UID for automatic alignment
- Handle different slice orderings
- Support various transfer syntaxes

---

## 7. Dependencies Summary

```text
# Required for image fusion
SimpleITK>=2.3.0        # Registration and resampling
matplotlib>=3.7.0       # Colormaps (likely already present)

# Optional enhancements
scipy>=1.10.0          # Additional transforms
scikit-image>=0.21.0   # Image processing utilities
```

---

## References

- SimpleITK Documentation: https://simpleitk.readthedocs.io/
- ITK Software Guide: https://itk.org/ItkSoftwareGuide.pdf
- 3D Slicer Documentation: https://slicer.readthedocs.io/
- Elastix Manual: https://elastix.lumc.nl/
- DICOM Standard (Part 3 - Spatial): https://dicom.nema.org/

