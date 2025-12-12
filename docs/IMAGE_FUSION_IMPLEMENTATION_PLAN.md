# Image Fusion Implementation Plan for DICOMViewerV3

This document outlines a detailed implementation plan for adding image fusion capabilities to DICOMViewerV3, allowing users to overlay functional imaging data (like PET or SPECT) on anatomical imaging data (like CT or MR).

## Overview

The implementation is divided into three phases:
1. **Phase 1**: Basic overlay with DICOM-based alignment (same Frame of Reference)
2. **Phase 2**: Automatic resampling for different grid sizes
3. **Phase 3**: Full registration for datasets without matching coordinates

---

## Phase 1: Basic Overlay (DICOM-Based Alignment)

### Goal
Enable fusion of series that share the same Frame of Reference UID (e.g., same-scanner PET-CT) with basic alpha blending and colormap overlay.

### Prerequisites
- [x] Verify matplotlib is in requirements.txt (for colormaps)
- [x] Review current image display pipeline in `image_viewer.py`
- [x] Review series management in `series_navigator.py`

### Tasks

#### 1.1 Create Fusion Data Handler
**File**: `src/core/fusion_handler.py`

- [x] Create `FusionHandler` class to manage fusion state
- [x] Implement method to check Frame of Reference UID compatibility
- [x] Implement method to find matching slices between series by SliceLocation
- [x] Implement slice interpolation for non-matching slice positions
- [x] Add methods to get/set base and overlay series

```python
# Proposed class structure
class FusionHandler:
    def __init__(self):
        self.base_series_uid: Optional[str] = None
        self.overlay_series_uid: Optional[str] = None
        self.base_datasets: List[Dataset] = []
        self.overlay_datasets: List[Dataset] = []
        self.fusion_enabled: bool = False
        self.opacity: float = 0.5
        self.threshold: float = 0.2
        self.colormap: str = 'hot'
    
    def check_frame_of_reference_match(self, series1, series2) -> bool: ...
    def find_matching_slice(self, base_slice_idx) -> Optional[int]: ...
    def get_slice_location(self, dataset) -> Optional[float]: ...
    def interpolate_overlay_slice(self, base_slice_idx) -> Optional[np.ndarray]: ...
```

#### 1.2 Create Fusion Image Processor
**File**: `src/core/fusion_processor.py`

- [x] Create `FusionProcessor` class for image blending operations
- [x] Implement alpha blending with colormap
- [x] Implement threshold-based overlay
- [x] Support multiple colormaps (hot, jet, viridis, etc.)
- [x] Handle window/level for both base and overlay independently

```python
# Proposed class structure
class FusionProcessor:
    @staticmethod
    def create_fusion_image(
        base_array: np.ndarray,
        overlay_array: np.ndarray,
        alpha: float = 0.5,
        colormap: str = 'hot',
        threshold: float = 0.0,
        base_wl: Tuple[float, float] = None,
        overlay_wl: Tuple[float, float] = None
    ) -> np.ndarray: ...
    
    @staticmethod
    def apply_colormap(array: np.ndarray, colormap: str) -> np.ndarray: ...
    
    @staticmethod
    def normalize_array(array: np.ndarray, window: float, level: float) -> np.ndarray: ...
```

#### 1.3 Create Fusion Controls Widget
**File**: `src/gui/fusion_controls_widget.py`

- [x] Create `FusionControlsWidget` class (QWidget)
- [x] Add enable/disable fusion checkbox
- [x] Add base series selector (QComboBox) - *Implemented as read-only display*
- [x] Add overlay series selector (QComboBox)
- [x] Add opacity slider (0-100%)
- [x] Add threshold slider (0-100%)
- [x] Add colormap selector dropdown
- [x] Add window/level controls for overlay (or link to existing)
- [x] Emit signals when settings change

#### 1.4 Create Fusion Coordinator
**File**: `src/gui/fusion_coordinator.py`

- [x] Create `FusionCoordinator` class to manage fusion state and UI
- [x] Connect fusion controls to image viewer
- [x] Handle series selection changes
- [x] Coordinate slice synchronization between base and overlay
- [x] Manage fusion settings persistence

#### 1.5 Integrate with Image Viewer
**File**: `src/gui/image_viewer.py` (modify)

- [x] Add `set_fusion_overlay()` method - *Implemented via SliceDisplayManager calling fusion_coordinator.get_fused_image()*
- [x] Modify `set_image()` to support fusion mode - *Fusion applied in SliceDisplayManager.display_slice() before setting image*
- [x] Handle fusion rendering in paint events - *Fused image is created and passed to set_image()*
- [x] Support independent zoom/pan for fused view - *Zoom/pan works on fused image*

#### 1.6 Integrate with Main Window
**File**: `src/main.py` (modify)

- [x] Add fusion controls to UI (collapsible panel or menu) - *Implemented via fusion_controls_stack*
- [x] Connect fusion coordinator to main window - *Implemented via _attach_fusion_components_to_subwindow()*
- [x] Add menu item to enable/disable fusion mode - *Fusion enabled via checkbox in controls widget*
- [x] Handle series changes affecting fusion - *Implemented via fusion state persistence and restoration*

#### 1.7 Testing
- [x] Test with same-scanner PET-CT data - *Testing performed and passed*
- [x] Test with different slice counts between series - *Testing performed and passed*
- [x] Test opacity and threshold controls - *Testing performed and passed*
- [x] Test different colormaps - *Testing performed and passed*
- [x] Test series switching while fusion is active - *Testing performed and passed*

---

## Phase 2: Automatic Resampling

### Goal
Enhance fusion capabilities to handle series with different pixel spacings, orientations, or slice thicknesses through automatic 3D volume resampling using SimpleITK. This extends Phase 1's basic 2D resizing to handle more complex spatial transformations.

### Current Status & Implementation Approach

**Phase 1 Implementation (Current)**: Phase 1 has implemented a basic 2D resampling approach using PIL that handles:
- Different pixel spacings (resizes overlay to match physical dimensions of base)
- Different array shapes (fallback resize to match base dimensions)
- Translation offsets based on ImagePositionPatient
- **Location**: `src/core/fusion_processor.py` lines 173-207

**Phase 2 Enhancement (Planned)**: This phase adds robust 3D volume resampling with SimpleITK to handle:
- Different slice thicknesses properly (e.g., 1mm CT vs 3mm PET)
- Different orientations (axial vs sagittal vs coronal) via ImageOrientationPatient
- Full 3D spatial transformations with proper coordinate system handling
- Volume caching for performance (avoid re-resampling on slice navigation)
- Multiple interpolation methods (linear, nearest, cubic, B-spline)
- **Decision Point**: When to use 2D PIL resize (fast, current) vs 3D SimpleITK (robust, Phase 2)

### Prerequisites
- [x] Phase 1 complete and tested
- [ ] Add SimpleITK to requirements.txt

### Tasks

#### 2.1 Add SimpleITK Dependency
**File**: `requirements.txt` (modify)

- [ ] Add `SimpleITK>=2.3.0`
- [ ] Test installation on all target platforms
- [ ] Update build documentation if needed

#### 2.2 Create Resampling Module
**File**: `src/core/image_resampler.py`

- [ ] Create `ImageResampler` class
- [ ] Implement DICOM to SimpleITK volume conversion (with proper spatial metadata)
- [ ] Implement SimpleITK to numpy conversion
- [ ] Implement resampling to reference grid (3D volume resampling)
- [ ] Support different interpolation methods (linear, nearest, cubic, B-spline)
- [ ] Cache resampled volumes for performance
- [ ] Handle ImageOrientationPatient for different slice orientations
- [ ] Properly handle slice spacing/thickness differences

```python
# Proposed class structure
class ImageResampler:
    def __init__(self):
        self._cache: Dict[Tuple[str, str], sitk.Image] = {}  # Cache key: (overlay_uid, base_uid)
        self._cache_lock = threading.Lock()  # For thread-safe caching
    
    def dicom_series_to_sitk(self, datasets: List[Dataset]) -> sitk.Image:
        """
        Convert DICOM series to SimpleITK image with proper spatial metadata.
        Handles ImagePositionPatient, ImageOrientationPatient, PixelSpacing, SliceThickness.
        """
        ...
    
    def sitk_to_numpy(self, sitk_image: sitk.Image) -> np.ndarray: ...
    
    def resample_to_reference(
        self, 
        moving: sitk.Image, 
        reference: sitk.Image,
        interpolator: str = 'linear'
    ) -> sitk.Image:
        """
        Resample moving image to match reference image's grid.
        Uses sitk.Resample() with proper transform.
        """
        ...
    
    def get_resampled_slice(
        self,
        overlay_datasets: List[Dataset],
        reference_datasets: List[Dataset],
        slice_idx: int,
        use_cache: bool = True
    ) -> np.ndarray:
        """
        Get resampled slice from overlay volume.
        Caches full volume resampling for performance.
        """
        ...
    
    def needs_resampling(
        self,
        overlay_datasets: List[Dataset],
        reference_datasets: List[Dataset]
    ) -> Tuple[bool, str]:
        """
        Determine if 3D resampling is needed.
        Returns (needs_resampling: bool, reason: str).
        Checks: pixel spacing, slice thickness, orientation differences.
        """
        ...
```

#### 2.3 Update Fusion Handler
**File**: `src/core/fusion_handler.py` (modify)

- [ ] Add resampling support when grids don't match (beyond current 2D PIL resize)
- [ ] Detect when 3D resampling is needed (different spacing/orientation/slice thickness)
- [ ] Integrate `ImageResampler` for automatic 3D volume alignment
- [ ] Add progress callback for long resampling operations
- [ ] Decide when to use 2D PIL resize (current) vs 3D SimpleITK resampling (Phase 2)

#### 2.4 Update Fusion Controls
**File**: `src/gui/fusion_controls_widget.py` (modify)

- [ ] Add interpolation method selector (linear, nearest, cubic, B-spline)
- [ ] Add "Resample Now" button for manual trigger (optional - auto-resample by default)
- [ ] Add progress indicator for resampling operations
- [ ] Show resampling status/warnings (e.g., "Resampling 3D volume...", "Different orientation detected")
- [ ] Add option to use 2D resize (current) vs 3D resampling (Phase 2) for performance tuning

#### 2.5 Performance Optimization
- [ ] Implement background resampling thread (QThread) for non-blocking UI
- [ ] Add volume caching to avoid repeated resampling (cache key: series_uid + reference_series_uid)
- [ ] Implement slice-by-slice resampling for memory efficiency (alternative to full volume)
- [ ] Add memory usage warnings for large datasets (e.g., >2GB volumes)
- [ ] Consider lazy loading: resample only when fusion is enabled
- [ ] Add cache invalidation when series data changes

#### 2.6 Testing
- [ ] Test with different pixel spacings (verify 3D resampling vs current 2D approach)
- [ ] Test with different slice thicknesses (e.g., 1mm CT vs 3mm PET)
- [ ] Test with different orientations (axial vs sagittal vs coronal)
- [ ] Test with rotated images (ImageOrientationPatient differences)
- [ ] Test memory usage with large datasets (e.g., whole-body PET-CT)
- [ ] Test caching effectiveness (verify cache hits/misses)
- [ ] Compare performance: 2D PIL resize (Phase 1) vs 3D SimpleITK resampling (Phase 2)
- [ ] Test edge cases: missing spatial metadata, inconsistent orientations

---

## Phase 3: Full Registration

### Goal
Enable fusion of datasets from different scanners or time points through intensity-based image registration.

### Prerequisites
- [ ] Phase 2 complete and tested
- [ ] Sufficient testing data (multi-scanner datasets)

### Tasks

#### 3.1 Create Registration Module
**File**: `src/core/image_registration.py`

- [ ] Create `ImageRegistration` class
- [ ] Implement rigid registration (6 DOF)
- [ ] Implement affine registration (12 DOF)
- [ ] Use mutual information metric for multi-modal
- [ ] Implement multi-resolution registration
- [ ] Add progress callbacks for registration process
- [ ] Store and apply registration transforms

```python
# Proposed class structure
class ImageRegistration:
    def __init__(self):
        self.transform: Optional[sitk.Transform] = None
        self.registration_type: str = 'rigid'  # 'rigid', 'affine'
    
    def register(
        self,
        fixed_image: sitk.Image,
        moving_image: sitk.Image,
        registration_type: str = 'rigid',
        progress_callback: Optional[Callable] = None
    ) -> Tuple[sitk.Image, sitk.Transform]: ...
    
    def apply_transform(
        self,
        image: sitk.Image,
        reference: sitk.Image
    ) -> sitk.Image: ...
    
    def save_transform(self, filepath: str) -> None: ...
    def load_transform(self, filepath: str) -> None: ...
```

#### 3.2 Create Manual Alignment Tools
**File**: `src/gui/manual_alignment_widget.py`

- [ ] Create `ManualAlignmentWidget` class
- [ ] Add translation controls (X, Y, Z sliders)
- [ ] Add rotation controls (around each axis)
- [ ] Add scale controls (optional)
- [ ] Real-time preview of alignment changes
- [ ] Reset to automatic alignment button

#### 3.3 Create Registration Dialog
**File**: `src/gui/dialogs/registration_dialog.py`

- [ ] Create `RegistrationDialog` class
- [ ] Show registration type selection (rigid/affine)
- [ ] Show progress during registration
- [ ] Display registration quality metrics
- [ ] Allow accept/reject of registration result
- [ ] Provide manual adjustment after auto registration

#### 3.4 Update Fusion Coordinator
**File**: `src/gui/fusion_coordinator.py` (modify)

- [ ] Add registration workflow
- [ ] Store registration transforms per series pair
- [ ] Handle transform persistence (save/load)
- [ ] Add "Register" button to fusion controls

#### 3.5 Update Fusion Controls
**File**: `src/gui/fusion_controls_widget.py` (modify)

- [ ] Add "Auto Register" button
- [ ] Add "Manual Adjust" button
- [ ] Show registration status indicator
- [ ] Add registration type selector

#### 3.6 Visualization Enhancements
- [ ] Add checkerboard view mode
- [ ] Add split view mode (horizontal/vertical)
- [ ] Add difference view mode
- [ ] Add synchronized crosshairs between views

#### 3.7 Testing
- [ ] Test rigid registration with translation offset
- [ ] Test rigid registration with rotation offset
- [ ] Test affine registration
- [ ] Test registration with different modalities (CT-MR)
- [ ] Test manual adjustment tools
- [ ] Test transform save/load

---

## File Structure Summary

### New Files to Create
```
src/
├── core/
│   ├── fusion_handler.py        # Phase 1
│   ├── fusion_processor.py      # Phase 1
│   ├── image_resampler.py       # Phase 2
│   └── image_registration.py    # Phase 3
├── gui/
│   ├── fusion_controls_widget.py    # Phase 1
│   ├── fusion_coordinator.py        # Phase 1
│   ├── manual_alignment_widget.py   # Phase 3
│   └── dialogs/
│       └── registration_dialog.py   # Phase 3
```

### Files to Modify
```
src/
├── main.py              # All phases
├── gui/
│   ├── image_viewer.py      # Phase 1
│   └── series_navigator.py  # Phase 1 (optional)
requirements.txt         # Phase 2
```

---

## UI Design Mockup

### Fusion Controls Panel (Collapsible)
```
┌─ Image Fusion ──────────────────────────────────┐
│ [✓] Enable Fusion                               │
│                                                 │
│ Base Image (Anatomical):                        │
│ [CT Chest 3mm v▼]                               │
│                                                 │
│ Overlay Image (Functional):                     │
│ [PET FDG Whole Body v▼]                         │
│                                                 │
│ Opacity:        [====●=====] 50%                │
│ Threshold:      [==●=======] 20%                │
│                                                 │
│ Color Map:      [Hot v▼]                        │
│                                                 │
│ ┌─ Advanced ──────────────────────────────────┐ │
│ │ [Auto Register] [Manual Adjust]             │ │
│ │ Status: ● Aligned (Frame of Reference)      │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Overlay Window/Level Controls
```
┌─ Overlay Window/Level ──────────────────────────┐
│ Window: [====●=====] 1500                       │
│ Level:  [======●===] 750                        │
│ [Link to Base W/L]  [Reset to Default]          │
└─────────────────────────────────────────────────┘
```

---

## Dependencies

### Required (Phase 2+)
```text
SimpleITK>=2.3.0
```

### Already Present (verified)
```text
matplotlib>=3.8.0  # For colormaps (in requirements.txt)
numpy>=1.24.0      # For array operations (in requirements.txt)
pydicom>=2.4.0     # For DICOM handling (in requirements.txt)
PySide6>=6.6.0     # For UI (in requirements.txt)
Pillow>=10.0.0     # For image processing (used in Phase 1 for 2D resizing)
```

---

## Testing Strategy

### Unit Tests
- [ ] `test_fusion_processor.py` - Test blending algorithms
- [ ] `test_fusion_handler.py` - Test series matching
- [ ] `test_image_resampler.py` - Test resampling functions
- [ ] `test_image_registration.py` - Test registration algorithms

### Integration Tests
- [ ] Test full fusion workflow with sample data
- [ ] Test UI responsiveness during fusion operations
- [ ] Test memory usage with large datasets

### Test Data Requirements
1. **Same-scanner PET-CT** (Phase 1)
   - Matching Frame of Reference UID
   - Same slice positions

2. **Different resolution datasets** (Phase 2)
   - Different pixel spacings (currently handled by Phase 1 2D resize, Phase 2 adds 3D)
   - Different slice thicknesses (requires Phase 2 3D resampling)
   - Different orientations (axial vs sagittal vs coronal) - requires Phase 2

3. **Multi-scanner datasets** (Phase 3)
   - Different Frame of Reference
   - Requires registration

---

## Estimated Timeline

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1 | Basic overlay | 2-3 days |
| Phase 2 | Resampling | 2-3 days |
| Phase 3 | Registration | 3-5 days |
| Testing | All phases | 2-3 days |
| **Total** | | **9-14 days** |

---

## Risk Assessment

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| SimpleITK installation issues | High | Test on all platforms early |
| Memory issues with large datasets | Medium | Implement slice-by-slice processing |
| Registration accuracy | Medium | Provide manual adjustment option |
| Performance during resampling | Medium | Background threading, caching |

### User Experience Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Confusing UI | Medium | Progressive disclosure, tooltips |
| Slow feedback | Medium | Progress indicators, cancellation |
| Unexpected results | Medium | Clear status indicators, warnings |

---

## Success Criteria

### Phase 1 Complete When:
- [x] User can select two series for fusion
- [x] Alpha blending works with configurable opacity
- [x] Colormap selection works
- [x] Threshold control hides low values
- [x] Fusion updates when scrolling through slices

### Phase 2 Complete When:
- [x] Different resolution series can be fused
- [x] Resampling is automatic when needed
- [x] Performance is acceptable (<2s per slice)
- [x] Memory usage is reasonable

### Phase 3 Complete When:
- [x] Automatic registration produces reasonable alignment
- [x] Manual adjustment tools work intuitively
- [x] Registration can be saved and reloaded
- [x] Different modalities (CT-MR) can be registered

---

## Open Questions

1. **UI Location**: Should fusion controls be in the main window sidebar, a floating panel, or a separate dialog?

2. **Default Behavior**: When loading a PET-CT study, should fusion be enabled automatically?

3. **Colormap Presets**: Should we provide modality-specific colormap defaults (e.g., hot for PET)?

4. **Registration Persistence**: Should registration transforms be saved to a file or stored in memory only?

5. **Multi-window Support**: Should fusion work across multiple viewer windows?

---

## Approval

- [ ] Plan reviewed by user
- [ ] Phase 1 scope approved
- [ ] Phase 2 scope approved  
- [ ] Phase 3 scope approved
- [ ] Ready to begin implementation

