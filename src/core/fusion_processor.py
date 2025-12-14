"""
Fusion Processor

This module performs image blending operations for image fusion, combining
anatomical and functional imaging with colormap overlays.

Inputs:
    - Base image array (anatomical)
    - Overlay image array (functional)
    - Fusion parameters (alpha, colormap, threshold)
    
Outputs:
    - Fused RGB image array
    
Requirements:
    - numpy for array operations
    - matplotlib for colormaps
    - PIL for image conversion
"""

import numpy as np
from typing import Optional, Tuple
from PIL import Image
import matplotlib.cm as cm


class FusionProcessor:
    """
    Performs image blending and colormap operations for fusion display.
    
    Static methods for:
    - Applying colormaps to grayscale arrays
    - Normalizing arrays with window/level
    - Alpha blending base and overlay images
    - Threshold masking
    """
    
    # Available colormaps for overlay visualization
    AVAILABLE_COLORMAPS = [
        'hot',      # Red-yellow, good for PET
        'jet',      # Rainbow, classic
        'viridis',  # Perceptually uniform
        'plasma',   # Perceptually uniform, purple-yellow
        'inferno',  # Perceptually uniform, dark purple-yellow
        'rainbow',  # Full spectrum
        'cool',     # Cyan-magenta
        'spring',   # Magenta-yellow
    ]
    
    @staticmethod
    def normalize_array(
        array: np.ndarray,
        window: float,
        level: float
    ) -> np.ndarray:
        """
        Normalize array to 0-1 range using window/level.
        
        Args:
            array: Input array (any bit depth)
            window: Window width
            level: Window center/level
            
        Returns:
            Normalized array in range 0-1
        """
        # Calculate min and max values from window/level
        min_val = level - window / 2.0
        max_val = level + window / 2.0
        
        # Normalize to 0-1
        normalized = (array - min_val) / (max_val - min_val)
        normalized = np.clip(normalized, 0.0, 1.0)
        
        return normalized
    
    @staticmethod
    def apply_threshold(
        array: np.ndarray,
        threshold: float
    ) -> np.ndarray:
        """
        Create binary mask where array values are above threshold.
        
        Args:
            array: Input array (0-1 range expected)
            threshold: Threshold value (0-1)
            
        Returns:
            Binary mask array (0 or 1)
        """
        mask = (array >= threshold).astype(np.float32)
        return mask
    
    @staticmethod
    def apply_colormap(
        array: np.ndarray,
        colormap_name: str = 'hot'
    ) -> np.ndarray:
        """
        Apply matplotlib colormap to grayscale array.
        
        Args:
            array: Normalized array (0-1 range)
            colormap_name: Name of matplotlib colormap
            
        Returns:
            RGB array (0-1 range, shape [..., 3])
        """
        # Get colormap
        try:
            cmap = cm.get_cmap(colormap_name)
        except ValueError:
            print(f"Warning: Colormap '{colormap_name}' not found, using 'hot'")
            cmap = cm.get_cmap('hot')
        
        # Apply colormap (returns RGBA)
        colored = cmap(array)
        
        # Extract RGB channels only (drop alpha)
        if colored.shape[-1] == 4:
            colored = colored[..., :3]
        
        return colored
    
    @staticmethod
    def create_fusion_image(
        base_array: np.ndarray,
        overlay_array: np.ndarray,
        alpha: float = 0.5,
        colormap: str = 'hot',
        threshold: float = 0.0,
        base_wl: Optional[Tuple[float, float]] = None,
        overlay_wl: Optional[Tuple[float, float]] = None,
        base_pixel_spacing: Optional[Tuple[float, float]] = None,
        overlay_pixel_spacing: Optional[Tuple[float, float]] = None,
        translation_offset: Optional[Tuple[float, float]] = None,
        skip_2d_resize: bool = False
    ) -> np.ndarray:
        """
        Create fused image by blending base and overlay with colormap.
        
        Args:
            base_array: Base (anatomical) image array
            overlay_array: Overlay (functional) image array
            alpha: Opacity of overlay (0-1)
            colormap: Name of matplotlib colormap for overlay
            threshold: Threshold for overlay visibility (0-1, in normalized space)
            base_wl: Optional (window, level) tuple for base image
            overlay_wl: Optional (window, level) tuple for overlay image
            base_pixel_spacing: Optional (row_spacing, col_spacing) in mm for base image
            overlay_pixel_spacing: Optional (row_spacing, col_spacing) in mm for overlay image
            translation_offset: Optional (x_offset, y_offset) in pixels for overlay positioning
            skip_2d_resize: If True, skip 2D resize (overlay already resampled via 3D, e.g., SimpleITK)
            
        Returns:
            Fused RGB array (0-255, uint8)
        """
        # Ensure arrays are float32 for processing
        base_array = base_array.astype(np.float32)
        overlay_array = overlay_array.astype(np.float32)
        
        # DEBUG
        print(f"\n[FUSION DEBUG] create_fusion_image called")
        print(f"  base_array shape: {base_array.shape}, dtype: {base_array.dtype}")
        print(f"  base_array range: [{np.min(base_array):.2f}, {np.max(base_array):.2f}]")
        print(f"  overlay_array shape: {overlay_array.shape}, dtype: {overlay_array.dtype}")
        print(f"  overlay_array range: [{np.min(overlay_array):.2f}, {np.max(overlay_array):.2f}]")
        print(f"  alpha: {alpha}, threshold: {threshold}, colormap: {colormap}")
        print(f"  base_pixel_spacing: {base_pixel_spacing}")
        print(f"  overlay_pixel_spacing: {overlay_pixel_spacing}")
        print(f"  translation_offset: {translation_offset}")
        print(f"  overlay_wl: {overlay_wl}")
        print(f"  skip_2d_resize: {skip_2d_resize}")
        
<<<<<<< Updated upstream
        # Apply pixel spacing-based scaling if both spacings are provided
        if base_pixel_spacing is not None and overlay_pixel_spacing is not None:
            # Calculate scaling factors
            # scale_x is for columns (width), scale_y is for rows (height)
            scale_x = overlay_pixel_spacing[1] / base_pixel_spacing[1]  # column spacing ratio
            scale_y = overlay_pixel_spacing[0] / base_pixel_spacing[0]  # row spacing ratio
            
            # Calculate new dimensions to match physical size
            # If overlay pixels are larger (scale > 1), we need MORE pixels to cover the same physical distance
            new_width = int(overlay_array.shape[1] * scale_x)
            new_height = int(overlay_array.shape[0] * scale_y)
            
            # Resize overlay to match physical dimensions
            from PIL import Image as PILImage
            overlay_pil = PILImage.fromarray(overlay_array)
            overlay_pil = overlay_pil.resize(
                (new_width, new_height),
                PILImage.Resampling.BILINEAR
            )
            overlay_array = np.array(overlay_pil, dtype=np.float32)
            
            # DEBUG - commented out
            # print(f"  [SCALING] scale_x: {scale_x:.4f}, scale_y: {scale_y:.4f}")
            # print(f"  [SCALING] new dimensions: {new_width} x {new_height}")
            # print(f"  [SCALING] overlay_array after resize shape: {overlay_array.shape}")
            # print(f"  [SCALING] overlay_array after resize range: [{np.min(overlay_array):.2f}, {np.max(overlay_array):.2f}]")
        elif base_array.shape != overlay_array.shape:
            # Fallback: simple resize to match base dimensions if no spacing info
            from PIL import Image as PILImage
            overlay_pil = PILImage.fromarray(overlay_array)
            overlay_pil = overlay_pil.resize(
                (base_array.shape[1], base_array.shape[0]),
                PILImage.Resampling.BILINEAR
            )
            overlay_array = np.array(overlay_pil, dtype=np.float32)
=======
        # Phase 2: Skip 2D resize if 3D resampling was already applied
        if not skip_2d_resize:
            # Apply pixel spacing-based scaling if both spacings are provided
            if base_pixel_spacing is not None and overlay_pixel_spacing is not None:
                # Calculate scaling factors
                # scale_x is for columns (width), scale_y is for rows (height)
                scale_x = overlay_pixel_spacing[1] / base_pixel_spacing[1]  # column spacing ratio
                scale_y = overlay_pixel_spacing[0] / base_pixel_spacing[0]  # row spacing ratio
                
                # Calculate new dimensions to match physical size
                # If overlay pixels are larger (scale > 1), we need MORE pixels to cover the same physical distance
                new_width = int(overlay_array.shape[1] * scale_x)
                new_height = int(overlay_array.shape[0] * scale_y)
                
                # Resize overlay to match physical dimensions
                from PIL import Image as PILImage
                overlay_pil = PILImage.fromarray(overlay_array)
                overlay_pil = overlay_pil.resize(
                    (new_width, new_height),
                    PILImage.Resampling.BILINEAR
                )
                overlay_array = np.array(overlay_pil, dtype=np.float32)
                
                # DEBUG
                print(f"  [SCALING] scale_x: {scale_x:.4f}, scale_y: {scale_y:.4f}")
                print(f"  [SCALING] new dimensions: {new_width} x {new_height}")
                print(f"  [SCALING] overlay_array after resize shape: {overlay_array.shape}")
                print(f"  [SCALING] overlay_array after resize range: [{np.min(overlay_array):.2f}, {np.max(overlay_array):.2f}]")
            elif base_array.shape != overlay_array.shape:
                # Fallback: simple resize to match base dimensions if no spacing info
                from PIL import Image as PILImage
                overlay_pil = PILImage.fromarray(overlay_array)
                overlay_pil = overlay_pil.resize(
                    (base_array.shape[1], base_array.shape[0]),
                    PILImage.Resampling.BILINEAR
                )
                overlay_array = np.array(overlay_pil, dtype=np.float32)
        else:
            # Phase 2: 3D resampling was used, overlay should already match base dimensions
            # Just verify shapes match
            if overlay_array.shape[:2] != base_array.shape[:2]:
                print(f"Warning: 3D resampled overlay shape {overlay_array.shape[:2]} doesn't match base {base_array.shape[:2]}")
                # Fallback: resize to match
                from PIL import Image as PILImage
                overlay_pil = PILImage.fromarray(overlay_array)
                overlay_pil = overlay_pil.resize(
                    (base_array.shape[1], base_array.shape[0]),
                    PILImage.Resampling.BILINEAR
                )
                overlay_array = np.array(overlay_pil, dtype=np.float32)
>>>>>>> Stashed changes
        
        # Apply translation offset if provided (ONLY for 2D mode)
        # 3D resampling handles spatial alignment automatically through the resampling grid
        # For 3D mode, translation_offset should be None
        if translation_offset is not None:
            offset_x, offset_y = translation_offset
            overlay_array = FusionProcessor._apply_translation_offset(
                overlay_array, offset_x, offset_y, base_array.shape
            )
            
<<<<<<< Updated upstream
            # DEBUG - commented out
            # print(f"  [TRANSLATION] offset applied: ({offset_x:.2f}, {offset_y:.2f})")
            # print(f"  [TRANSLATION] overlay_array after translation shape: {overlay_array.shape}")
            # print(f"  [TRANSLATION] overlay_array after translation range: [{np.min(overlay_array):.2f}, {np.max(overlay_array):.2f}]")
            # print(f"  [TRANSLATION] non-zero pixels: {np.count_nonzero(overlay_array)}")
=======
            # DEBUG
            print(f"  [TRANSLATION] offset applied (2D mode): ({offset_x:.2f}, {offset_y:.2f})")
            print(f"  [TRANSLATION] overlay_array after translation shape: {overlay_array.shape}")
            print(f"  [TRANSLATION] overlay_array after translation range: [{np.min(overlay_array):.2f}, {np.max(overlay_array):.2f}]")
            print(f"  [TRANSLATION] non-zero pixels: {np.count_nonzero(overlay_array)}")
>>>>>>> Stashed changes
        
        # Normalize base image
        if base_wl is not None:
            window, level = base_wl
            base_normalized = FusionProcessor.normalize_array(
                base_array, window, level
            )
        else:
            # Auto-normalize to full range
            base_min = np.min(base_array)
            base_max = np.max(base_array)
            if base_max > base_min:
                base_normalized = (base_array - base_min) / (base_max - base_min)
            else:
                base_normalized = np.zeros_like(base_array)
        
        # Convert base to RGB (grayscale to RGB)
        base_rgb = np.stack([base_normalized] * 3, axis=-1)
        
        # Normalize overlay image
        if overlay_wl is not None:
            window, level = overlay_wl
            overlay_normalized = FusionProcessor.normalize_array(
                overlay_array, window, level
            )
        else:
            # Auto-normalize to full range
            overlay_min = np.min(overlay_array)
            overlay_max = np.max(overlay_array)
            if overlay_max > overlay_min:
                overlay_normalized = (overlay_array - overlay_min) / (overlay_max - overlay_min)
            else:
                overlay_normalized = np.zeros_like(overlay_array)
        
        # DEBUG
        if overlay_wl is not None:
            window, level = overlay_wl
            print(f"  [OVERLAY W/L] window: {window}, level: {level}")
        print(f"  overlay_normalized range: [{np.min(overlay_normalized):.4f}, {np.max(overlay_normalized):.4f}]")
        print(f"  overlay_normalized non-zero: {np.count_nonzero(overlay_normalized)}")
        
        # Apply colormap to overlay
        overlay_rgb = FusionProcessor.apply_colormap(overlay_normalized, colormap)
        
        # Apply threshold to create mask
        overlay_mask = FusionProcessor.apply_threshold(overlay_normalized, threshold)
        
        # Expand mask to 3 channels
        overlay_mask_3d = np.stack([overlay_mask] * 3, axis=-1)
        
        # Alpha blend: fused = base * (1 - alpha*mask) + overlay * (alpha*mask)
        alpha_mask = alpha * overlay_mask_3d
        fused = base_rgb * (1.0 - alpha_mask) + overlay_rgb * alpha_mask
        
        # Clip to valid range and convert to uint8
        fused = np.clip(fused * 255.0, 0, 255).astype(np.uint8)
        
        return fused
    
    @staticmethod
    def _apply_translation_offset(
        overlay_array: np.ndarray,
        offset_x: float,
        offset_y: float,
        base_shape: Tuple[int, int]
    ) -> np.ndarray:
        """
        Apply translation offset to overlay array.
        
        Creates a canvas matching base image size and places overlay at the offset position.
        Handles bounds checking to avoid extending beyond image boundaries.
        
        Args:
            overlay_array: Overlay image array
            offset_x: X offset in pixels (positive = right)
            offset_y: Y offset in pixels (positive = down)
            base_shape: Shape of base image (height, width)
            
        Returns:
            Translated overlay array matching base shape
        """
        base_height, base_width = base_shape
        overlay_height, overlay_width = overlay_array.shape[:2]
        
        # Create canvas matching base size, filled with zeros
        translated = np.zeros((base_height, base_width), dtype=overlay_array.dtype)
        
        # Round offsets to integers for array indexing
        offset_x_int = int(round(offset_x))
        offset_y_int = int(round(offset_y))
        
        # Calculate source and destination bounds with clipping
        # Source bounds (from overlay)
        src_x_start = max(0, -offset_x_int)
        src_y_start = max(0, -offset_y_int)
        src_x_end = min(overlay_width, base_width - offset_x_int)
        src_y_end = min(overlay_height, base_height - offset_y_int)
        
        # Destination bounds (in translated canvas)
        dst_x_start = max(0, offset_x_int)
        dst_y_start = max(0, offset_y_int)
        dst_x_end = dst_x_start + (src_x_end - src_x_start)
        dst_y_end = dst_y_start + (src_y_end - src_y_start)
        
        # Only copy if there's a valid overlap region
        if (src_x_end > src_x_start and src_y_end > src_y_start and
            dst_x_end > dst_x_start and dst_y_end > dst_y_start):
            translated[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = \
                overlay_array[src_y_start:src_y_end, src_x_start:src_x_end]
        
        return translated
    
    @staticmethod
    def convert_array_to_pil_image(array: np.ndarray) -> Image.Image:
        """
        Convert numpy array to PIL Image.
        
        Args:
            array: Numpy array (uint8, either 2D grayscale or 3D RGB)
            
        Returns:
            PIL Image
        """
        if len(array.shape) == 2:
            # Grayscale
            return Image.fromarray(array, mode='L')
        elif len(array.shape) == 3 and array.shape[2] == 3:
            # RGB
            return Image.fromarray(array, mode='RGB')
        else:
            raise ValueError(f"Unsupported array shape for PIL conversion: {array.shape}")

