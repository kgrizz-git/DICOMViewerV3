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
- [ ] Verify matplotlib is in requirements.txt (for colormaps)
- [ ] Review current image display pipeline in `image_viewer.py`
- [ ] Review series management in `series_navigator.py`

### Tasks

#### 1.1 Create Fusion Data Handler
**File**: `src/core/fusion_handler.py`

- [ ] Create `FusionHandler` class to manage fusion state
- [ ] Implement method to check Frame of Reference UID compatibility
- [ ] Implement method to find matching slices between series by SliceLocation
- [ ] Implement slice interpolation for non-matching slice positions
- [ ] Add methods to get/set base and overlay series

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

- [ ] Create `FusionProcessor` class for image blending operations
- [ ] Implement alpha blending with colormap
- [ ] Implement threshold-based overlay
- [ ] Support multiple colormaps (hot, jet, viridis, etc.)
- [ ] Handle window/level for both base and overlay independently

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

- [ ] Create `FusionControlsWidget` class (QWidget)
- [ ] Add enable/disable fusion checkbox
- [ ] Add base series selector (QComboBox)
- [ ] Add overlay series selector (QComboBox)
- [ ] Add opacity slider (0-100%)
- [ ] Add threshold slider (0-100%)
- [ ] Add colormap selector dropdown
- [ ] Add window/level controls for overlay (or link to existing)
- [ ] Emit signals when settings change

#### 1.4 Create Fusion Coordinator
**File**: `src/gui/fusion_coordinator.py`

- [ ] Create `FusionCoordinator` class to manage fusion state and UI
- [ ] Connect fusion controls to image viewer
- [ ] Handle series selection changes
- [ ] Coordinate slice synchronization between base and overlay
- [ ] Manage fusion settings persistence

#### 1.5 Integrate with Image Viewer
**File**: `src/gui/image_viewer.py` (modify)

- [ ] Add `set_fusion_overlay()` method
- [ ] Modify `set_image()` to support fusion mode
- [ ] Handle fusion rendering in paint events
- [ ] Support independent zoom/pan for fused view

#### 1.6 Integrate with Main Window
**File**: `src/main.py` (modify)

- [ ] Add fusion controls to UI (collapsible panel or menu)
- [ ] Connect fusion coordinator to main window
- [ ] Add menu item to enable/disable fusion mode
- [ ] Handle series changes affecting fusion

#### 1.7 Testing
- [ ] Test with same-scanner PET-CT data
- [ ] Test with different slice counts between series
- [ ] Test opacity and threshold controls
- [ ] Test different colormaps
- [ ] Test series switching while fusion is active

---

## Phase 2: Automatic Resampling

### Goal
Handle fusion of series with different pixel spacings, orientations, or slice thicknesses through automatic resampling.

### Prerequisites
- [ ] Phase 1 complete and tested
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
- [ ] Implement DICOM to SimpleITK volume conversion
- [ ] Implement SimpleITK to numpy conversion
- [ ] Implement resampling to reference grid
- [ ] Support different interpolation methods (linear, nearest, cubic)
- [ ] Cache resampled volumes for performance

```python
# Proposed class structure
class ImageResampler:
    def __init__(self):
        self._cache: Dict[str, np.ndarray] = {}
    
    def dicom_series_to_sitk(self, datasets: List[Dataset]) -> sitk.Image: ...
    def sitk_to_numpy(self, sitk_image: sitk.Image) -> np.ndarray: ...
    def resample_to_reference(
        self, 
        moving: sitk.Image, 
        reference: sitk.Image,
        interpolator: str = 'linear'
    ) -> sitk.Image: ...
    def get_resampled_slice(
        self,
        overlay_datasets: List[Dataset],
        reference_datasets: List[Dataset],
        slice_idx: int
    ) -> np.ndarray: ...
```

#### 2.3 Update Fusion Handler
**File**: `src/core/fusion_handler.py` (modify)

- [ ] Add resampling support when grids don't match
- [ ] Detect when resampling is needed (different spacing/orientation)
- [ ] Integrate `ImageResampler` for automatic alignment
- [ ] Add progress callback for long resampling operations

#### 2.4 Update Fusion Controls
**File**: `src/gui/fusion_controls_widget.py` (modify)

- [ ] Add interpolation method selector
- [ ] Add "Resample Now" button for manual trigger
- [ ] Add progress indicator for resampling
- [ ] Show resampling status/warnings

#### 2.5 Performance Optimization
- [ ] Implement background resampling thread
- [ ] Add volume caching to avoid repeated resampling
- [ ] Implement slice-by-slice resampling for memory efficiency
- [ ] Add memory usage warnings for large datasets

#### 2.6 Testing
- [ ] Test with different pixel spacings
- [ ] Test with different slice thicknesses
- [ ] Test with different orientations (axial vs sagittal)
- [ ] Test memory usage with large datasets
- [ ] Test caching effectiveness

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

### Already Present (verify)
```text
matplotlib  # For colormaps
numpy       # For array operations
pydicom     # For DICOM handling
PyQt6       # For UI
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
   - Different pixel spacings
   - Different slice thicknesses

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

