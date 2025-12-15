"""
Fusion Technical Documentation Dialog

This module provides a dialog displaying the technical documentation for image fusion,
including algorithms, options, and error analysis.

Inputs:
    - User opens Help menu and selects Fusion Technical Documentation
    
Outputs:
    - Displayed technical documentation with table of contents navigation
    
Requirements:
    - PySide6 for dialog components
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QLineEdit, QLabel, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt
from typing import Optional

from utils.config_manager import ConfigManager


class FusionTechnicalDocDialog(QDialog):
    """
    Technical documentation dialog for image fusion.
    
    Provides:
    - Detailed algorithm descriptions
    - Error analysis and accuracy estimates
    - Performance considerations
    - Table of contents navigation
    """
    
    # Class-level cache for HTML content by theme
    _content_cache: dict = {}  # {theme: html_content}
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QDialog] = None):
        """
        Initialize the Fusion Technical Documentation dialog.
        
        Args:
            config_manager: ConfigManager instance for theme detection
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        
        self.setWindowTitle("Image Fusion Technical Documentation")
        self.setModal(True)
        self.resize(900, 700)
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Apply theme-based styling to dialog
        theme = self.config_manager.get_theme()
        if theme == "dark":
            # Set dark grey background for dark theme
            self.setStyleSheet("QDialog { background-color: #2b2b2b; }")
        else:
            # Light theme - use default or white
            self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        # Search bar with Prev/Next buttons
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search in documentation...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        # Prevent Enter key from closing dialog (it triggers default button)
        self.search_edit.returnPressed.connect(lambda: None)  # Do nothing on Enter
        
        # Prev/Next buttons
        self.prev_button = QPushButton("◀ Prev")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_match)
        
        self.next_button = QPushButton("Next ▶")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._on_next_match)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.prev_button)
        search_layout.addWidget(self.next_button)
        layout.addLayout(search_layout)
        
        # Text edit for documentation content - use QTextBrowser for anchor link support
        self.text_edit = QTextBrowser()
        self.text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
        self.text_edit.setReadOnly(True)
        # Set QTextBrowser background to match metadata panel in dark theme
        if theme == "dark":
            self.text_edit.setStyleSheet("QTextBrowser { background-color: #1e1e1e; }")
        
        # Store full content and set initial content
        self._full_content = self._get_doc_content()
        self.text_edit.setHtml(self._full_content)
        
        # Search navigation state
        self._search_match_positions = []  # List of cursor positions for matches
        self._current_match_index = -1  # Current match index (-1 = no match selected)
        layout.addWidget(self.text_edit)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)  # Close button triggers accept
        layout.addWidget(button_box)
    
    def _get_doc_content(self) -> str:
        """
        Get the formatted HTML content for the technical documentation.
        
        Colors adapt to the application theme for better contrast and consistency.
        Content is cached per theme to improve load time.
        
        Returns:
            HTML formatted string with documentation content
        """
        # Get current theme
        theme = self.config_manager.get_theme()
        
        # Return cached content if available
        if theme in FusionTechnicalDocDialog._content_cache:
            return FusionTechnicalDocDialog._content_cache[theme]
        
        # Generate content for this theme
        # Define colors based on theme
        if theme == "dark":
            # Dark theme: light text on dark grey background
            bg_color = "#1e1e1e"
            h1_color = "#ffffff"
            h2_color = "#e0e0e0"
            h3_color = "#d0d0d0"
            text_color = "#ffffff"
            strong_color = "#4a9eff"  # Light blue for better visibility on dark
            code_bg = "#2b2b2b"  # Darker grey for code blocks
            code_text = "#ffffff"
            table_border = "#555555"
            table_header_bg = "#333333"
        else:
            # Light theme: dark text on light background
            bg_color = "#ffffff"
            h1_color = "#000000"
            h2_color = "#1a1a1a"
            h3_color = "#2a2a2a"
            text_color = "#000000"
            strong_color = "#2980b9"  # Blue for emphasis
            code_bg = "#ecf0f1"  # Light grey for code blocks
            code_text = "#000000"
            table_border = "#cccccc"
            table_header_bg = "#e8e8e8"
        
        content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; background-color: {bg_color}; color: {text_color}; padding: 10px; }}
                h1 {{ color: {h1_color}; font-size: 20px; margin-top: 20px; margin-bottom: 15px; border-bottom: 2px solid {strong_color}; padding-bottom: 5px; }}
                h2 {{ color: {h2_color}; font-size: 18px; margin-top: 20px; margin-bottom: 10px; }}
                h3 {{ color: {h3_color}; font-size: 16px; margin-top: 15px; margin-bottom: 8px; }}
                h4 {{ color: {h3_color}; font-size: 14px; margin-top: 12px; margin-bottom: 6px; }}
                p {{ margin: 8px 0; }}
                ul, ol {{ margin: 8px 0; padding-left: 25px; }}
                li {{ margin: 4px 0; }}
                strong {{ color: {strong_color}; }}
                code {{ background-color: {code_bg}; color: {code_text}; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }}
                pre {{ background-color: {code_bg}; color: {code_text}; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                th, td {{ border: 1px solid {table_border}; padding: 8px; text-align: left; }}
                th {{ background-color: {table_header_bg}; font-weight: bold; }}
                a {{ color: {strong_color}; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>Image Fusion Technical Documentation</h1>
            
            <h2>Table of Contents</h2>
            <ul>
                <li><a href="#overview">Overview</a></li>
                <li><a href="#architecture">Architecture Overview</a></li>
                <li><a href="#options">Fusion Options and Parameters</a></li>
                <li><a href="#2d-algorithm">2D Fusion Algorithm</a></li>
                <li><a href="#3d-algorithm">3D Fusion Algorithm</a></li>
                <li><a href="#spatial-alignment">Spatial Alignment</a></li>
                <li><a href="#error-analysis">Error Sources and Accuracy Analysis</a></li>
                <li><a href="#performance">Performance Considerations</a></li>
            </ul>
            
            <h2 id="overview">Overview</h2>
            <p>The DICOM Viewer V3 image fusion feature allows overlaying functional imaging (PET/SPECT) on anatomical imaging (CT/MR) from different series within the same study. This document provides detailed technical information about the fusion algorithms, options, error sources, and accuracy estimates.</p>
            
            <h2 id="architecture">Architecture Overview</h2>
            <p>The fusion system consists of three main components:</p>
            <ol>
                <li><strong>FusionHandler</strong>: Manages fusion state, slice matching, and spatial metadata extraction</li>
                <li><strong>FusionProcessor</strong>: Performs image blending, colormap application, and pixel-level operations</li>
                <li><strong>ImageResampler</strong>: Handles 3D volume resampling using SimpleITK for complex spatial transformations</li>
            </ol>
            
            <h3>Data Flow</h3>
            <pre>User Selection → FusionHandler → Slice Matching → Resampling Decision
                                                      ↓
                                             2D or 3D Resampling
                                                      ↓
                                            FusionProcessor
                                                      ↓
                                            Blended RGB Image</pre>
            
            <h2 id="options">Fusion Options and Parameters</h2>
            
            <h3>Core Parameters</h3>
            <ol>
                <li><strong>Opacity (α)</strong>: 0.0 to 1.0 (0-100% in UI)
                    <ul>
                        <li>Controls transparency of overlay on base image</li>
                        <li>Formula: <code>fused = base × (1 - α×mask) + overlay × (α×mask)</code></li>
                        <li>Default: 0.5 (50%)</li>
                    </ul>
                </li>
                <li><strong>Threshold</strong>: 0.0 to 1.0 (0-100% in UI, normalized space)
                    <ul>
                        <li>Minimum overlay value to display</li>
                        <li>Creates binary mask: <code>mask = (overlay_normalized >= threshold)</code></li>
                        <li>Default: 0.2 (20% of normalized range)</li>
                    </ul>
                </li>
                <li><strong>Colormap</strong>: Visualization scheme for overlay
                    <ul>
                        <li>Available: hot, jet, viridis, plasma, inferno, rainbow, cool, spring</li>
                        <li>Applied to normalized overlay values (0-1 range)</li>
                        <li>Default: 'hot' (red-yellow, good for PET)</li>
                    </ul>
                </li>
                <li><strong>Overlay Window/Level</strong>: Independent window width and center for overlay series
                    <ul>
                        <li>Normalizes overlay pixel values before colormap application</li>
                        <li>Formula: <code>normalized = clip((value - (level - window/2)) / window, 0, 1)</code></li>
                        <li>Default: Window=1000, Level=500</li>
                    </ul>
                </li>
            </ol>
            
            <h3>Resampling Modes</h3>
            <ol>
                <li><strong>Fast Mode (2D)</strong>:
                    <ul>
                        <li>Uses 2D image resize (PIL bilinear interpolation)</li>
                        <li>Suitable for series with same ImageOrientationPatient, similar slice thickness, and same or similar pixel spacing</li>
                        <li>Faster processing, lower memory usage</li>
                        <li>Limited to 2D transformations (scaling, translation)</li>
                    </ul>
                </li>
                <li><strong>High Accuracy Mode (3D)</strong>:
                    <ul>
                        <li>Uses 3D volume resampling (SimpleITK)</li>
                        <li>Handles different orientations, slice thicknesses, pixel spacings, and complex spatial relationships</li>
                        <li>Slower processing, higher memory usage</li>
                        <li>Full 3D spatial transformation</li>
                    </ul>
                </li>
            </ol>
            
            <h3>Interpolation Methods (3D Mode Only)</h3>
            <ul>
                <li><strong>Linear</strong> (default): Smooth interpolation, good balance of quality and speed</li>
                <li><strong>Nearest Neighbor</strong>: Fastest, preserves original pixel values, may produce blocky artifacts</li>
                <li><strong>Cubic/B-Spline</strong>: Higher quality, smoother results, more computationally expensive</li>
            </ul>
            
            <h2 id="2d-algorithm">2D Fusion Algorithm</h2>
            
            <h3>Algorithm Steps</h3>
            <p>In 2D mode, the fusion system works one slice at a time. For each anatomical <em>base</em> slice, it locates the best matching functional <em>overlay</em> slice (or pair of slices) that represents the same physical position in the patient. It then scales and shifts that overlay slice so that it lines up with the base slice in pixel space before blending them together.</p>
            <ol>
                <li><strong>Slice Matching</strong>:
                    <ul>
                        <li>Extract slice location from base slice (SliceLocation or ImagePositionPatient[2])</li>
                        <li>Find matching overlay slice(s) with tolerance < 0.01 mm for exact match</li>
                        <li>If no match found within series bounds, return None</li>
                    </ul>
                </li>
                <li><strong>2D Interpolation (if needed)</strong>:
                    <ul>
                        <li>If an exact match is found, the overlay slice is used directly.</li>
                        <li>If the base slice lies between two overlay slices, the system performs linear interpolation along the slice (through‑plane) direction to synthesize an overlay slice at the correct physical location.</li>
                        <li>It first finds the two adjacent overlay slices that bracket the base slice, then computes a continuous weight: <code>weight = (base_location - loc1) / (loc2 - loc1)</code>.</li>
                        <li>The interpolated slice is computed as <code>overlay = array1 × (1 - weight) + array2 × weight</code>, so the overlay values change smoothly as the base position moves between those two overlay slices.</li>
                    </ul>
                </li>
                <li><strong>Pixel Spacing Scaling</strong>:
                    <ul>
                        <li>Calculate scaling factors from pixel spacing ratios</li>
                        <li>Resize overlay to match physical dimensions using PIL bilinear resampling</li>
                    </ul>
                </li>
                <li><strong>Translation Offset</strong>:
                    <ul>
                        <li>Calculate from ImagePositionPatient difference</li>
                        <li>Convert to pixels using base pixel spacing</li>
                        <li>Apply translation by placing overlay on base-sized canvas</li>
                    </ul>
                </li>
                <li><strong>Normalization and Blending</strong>:
                    <ul>
                        <li>Normalize base and overlay using window/level</li>
                        <li>Apply colormap to overlay</li>
                        <li>Apply threshold mask</li>
                        <li>Alpha blend: <code>fused = base × (1 - α×mask) + overlay × (α×mask)</code></li>
                    </ul>
                </li>
            </ol>
            
            <h3>Error Sources (2D Mode)</h3>
            <p>There are two broad classes of error sources in 2D fusion: (1) <strong>algorithm‑intrinsic</strong> errors from interpolation, resampling, and rounding even when DICOM metadata is correct, and (2) <strong>metadata/input errors</strong> when tags like <code>SliceLocation</code>, <code>ImagePositionPatient</code>, or <code>ImageOrientationPatient</code> are wrong or missing.</p>
            <table>
                <tr>
                    <th>Error Source</th>
                    <th>Error Magnitude (pixels/voxels and mm)</th>
                    <th>Impact / Origin</th>
                </tr>
                <tr>
                    <td>Slice Location Extraction</td>
                    <td>Unbounded (can be many slices/voxels off)</td>
                    <td>Metadata: wrong/missing <code>SliceLocation</code>/<code>ImagePositionPatient</code> can cause the wrong overlay slice to be matched to the base slice, regardless of algorithm accuracy</td>
                </tr>
                <tr>
                    <td>2D Interpolation</td>
                    <td>≈±0.5 overlay slices (±0.5 voxels in Z); ≈±0.5 mm at 1 mm slice spacing, ≈±1.5 mm at 3 mm slice spacing</td>
                    <td>Algorithmic: minor through‑plane blurring when interpolating between slices; in‑plane position remains aligned</td>
                </tr>
                <tr>
                    <td>Pixel Spacing Scaling</td>
                    <td>≈±0.5 pixels in x/y; ≈±0.5 mm at 1 mm pixels, ≈±0.25 mm at 0.5 mm pixels</td>
                    <td>Algorithmic: slight blurring/softening at edges from 2D resampling; geometry stays on the base pixel grid</td>
                </tr>
                <tr>
                    <td>Translation Offset</td>
                    <td>±0.5 pixels in x/y (rounding); ≈±0.5 mm at 1 mm pixels, ≈±0.25 mm at 0.5 mm pixels</td>
                    <td>Algorithmic: sub‑pixel misalignment from rounding mm offsets to integer pixel indices</td>
                </tr>
                <tr>
                    <td>Orientation Mismatch</td>
                    <td>Can be many pixels (or entire FOV) off; several mm to cm in physical space</td>
                    <td>Metadata: different <code>ImageOrientationPatient</code> (e.g., axial vs sagittal) cannot be corrected by 2D scaling/translation alone; 3D resampling is required for accurate alignment</td>
                </tr>
            </table>
            
            <h3>Accuracy Estimates (2D Mode)</h3>
            <p>The ranges below assume that DICOM spatial metadata is correct and internally consistent. Under that assumption, only the algorithm‑intrinsic interpolation and rounding errors described above contribute to misalignment.</p>
            <ul>
                <li><strong>Best Case</strong> (same orientation, same pixel spacing, no interpolation needed):
                    <ul>
                        <li>Spatial accuracy (native): ≈±0.5 pixels in x/y from scaling and translation rounding, ≈0 voxels in Z.</li>
                        <li>Physical equivalent: ≈±0.5 mm at 1 mm spacing, ≈±0.25 mm at 0.5 mm spacing.</li>
                        <li><strong>Total algorithmic error:</strong> on the order of ±0.5–1.0 pixels (≈±0.5–1.0 mm at 1 mm spacing).</li>
                    </ul>
                </li>
                <li><strong>Typical Case</strong> (same orientation, different pixel spacing, interpolation between reasonably spaced slices):
                    <ul>
                        <li>Spatial accuracy (native): ≈±0.5–1.0 pixels in x/y and up to ±0.5 overlay slices in Z.</li>
                        <li>Physical equivalent: ≈±0.5–1.5 mm total, depending on slice spacing (e.g., ±1.5 mm at 3 mm slices).</li>
                        <li><strong>Total algorithmic error:</strong> typically ±1.0–2.5 mm.</li>
                    </ul>
                </li>
                <li><strong>Worst Case (algorithm‑only)</strong> (still assuming correct metadata, but with very thick/sparse slices where 2D is used instead of 3D):
                    <ul>
                        <li>Spatial accuracy: several pixels of combined in‑ and through‑plane interpolation error.</li>
                        <li>Physical equivalent: several millimetres, especially with thick slices.</li>
                        <li><strong>Total algorithmic error:</strong> may be large enough that 3D resampling is strongly recommended.</li>
                    </ul>
                </li>
            </ul>
            <p><em>Metadata error scenarios</em> (e.g., wrong <code>SliceLocation</code> or <code>ImageOrientationPatient</code>) are not bounded by these ranges; in those cases, pixel‑level misalignment can be arbitrarily large, and the fusion result should be regarded as qualitatively wrong regardless of the algorithm&rsquo;s nominal accuracy.</p>
            
            <h2 id="3d-algorithm">3D Fusion Algorithm</h2>
            
            <h3>Algorithm Steps</h3>
            <p>In 3D mode, the system first builds full 3D volumes for both the base and overlay series and then resamples the entire overlay volume into the base volume&rsquo;s coordinate system. Only after that resampling step does it extract individual slices for display. This captures differences in slice spacing, orientation, and position more accurately than the 2D slice‑by‑slice method.</p>
            <ol>
                <li><strong>DICOM Series to SimpleITK Conversion</strong>:
                    <ul>
                        <li>Sort datasets by slice location</li>
                        <li>Extract pixel arrays and stack into 3D volume (z, y, x)</li>
                        <li>Set spatial metadata: Origin, Spacing, Direction matrix</li>
                    </ul>
                </li>
                <li><strong>Slice Spacing Calculation</strong>:
                    <ul>
                        <li>Primary method: Component along slice normal from ImageOrientationPatient</li>
                        <li>Fallback: 3D Euclidean distance between consecutive slices</li>
                        <li>Fallback: SliceThickness tag (if only one slice)</li>
                    </ul>
                </li>
                <li><strong>3D Volume Resampling</strong>:
                    <ul>
                        <li>Convert overlay and base series to SimpleITK images.</li>
                        <li>Use SimpleITK <code>Resample()</code> with an identity (no‑movement) transform.</li>
                        <li>This assumes that the base and overlay series share the same DICOM <code>FrameOfReferenceUID</code> (see the Frame of Reference Assumption in the error section below).</li>
                        <li>The overlay volume is resampled so that it shares the same origin, spacing, and direction matrix as the base volume, meaning every overlay voxel is mapped directly into the base image&rsquo;s 3D grid.</li>
                    </ul>
                </li>
                <li><strong>Slice Extraction</strong>:
                    <ul>
                        <li>Extract requested slice from resampled volume</li>
                        <li>Map unsorted slice index to sorted index</li>
                        <li>Apply rescale slope/intercept if present</li>
                    </ul>
                </li>
                <li><strong>Normalization and Blending</strong>:
                    <ul>
                        <li>Same as 2D mode (normalize, colormap, threshold, alpha blend)</li>
                        <li>Skip 2D resize and translation (already handled by 3D interpolation/resampling on the full volume)</li>
                    </ul>
                </li>
            </ol>
            
            <h3>Error Sources (3D Mode)</h3>
            <p>As with 2D mode, 3D fusion errors come from both <strong>algorithm‑intrinsic</strong> effects (e.g., interpolation) and <strong>metadata/input</strong> problems (e.g., incorrect Positions or FrameOfReferenceUIDs). The table below summarizes typical magnitudes for each category.</p>
            <table>
                <tr>
                    <th>Error Source</th>
                    <th>Error Magnitude (voxels and mm)</th>
                    <th>Impact / Origin</th>
                </tr>
                <tr>
                    <td>3D Resampling Interpolation (Linear)</td>
                    <td>≈±0.5 voxels per axis; ≈±0.87 voxels in 3D magnitude (≈±0.5–0.9 mm at 1 mm voxels)</td>
                    <td>Algorithmic: sub‑voxel smoothing/blurring when mapping overlay into the base grid</td>
                </tr>
                <tr>
                    <td>3D Resampling Interpolation (Cubic/B-spline)</td>
                    <td>≈±0.3–0.4 voxels per axis; ≈±0.5–0.7 voxels total (≈±0.5–0.7 mm at 1 mm voxels)</td>
                    <td>Algorithmic: higher‑order interpolation with reduced artifacts and smaller voxel‑scale error</td>
                </tr>
                <tr>
                    <td>Slice Location Sorting</td>
                    <td>Unbounded; slices without valid locations may be dropped, mis‑ordered, or unevenly spaced</td>
                    <td>Metadata: missing/incorrect <code>SliceLocation</code>/<code>ImagePositionPatient</code> can distort or truncate the 3D volume</td>
                </tr>
                <tr>
                    <td>Slice Spacing Calculation</td>
                    <td>Typically ±0.1–0.5 mm with good metadata; can be overestimated by 10–30% or more with oblique slices and poor metadata</td>
                    <td>Metadata: errors in position/orientation or reliance on simple 3D distances change apparent slice spacing</td>
                </tr>
                <tr>
                    <td>Direction Matrix Construction</td>
                    <td>Orientation errors usually &lt;0.1° for well‑formed DICOM (<0.001 differences in direction cosines)</td>
                    <td>Metadata: minor rounding/non‑orthogonality in <code>ImageOrientationPatient</code>; geometric impact is typically negligible</td>
                </tr>
                <tr>
                    <td>Frame of Reference Assumption</td>
                    <td>Can be many voxels off in x/y/z; several millimetres to centimetres in physical space</td>
                    <td>Metadata: if <code>FrameOfReferenceUID</code> differs, the identity transform is wrong and the fusion can be grossly misregistered; the status label warns when UIDs differ, fusion remains allowed but should be treated as potentially inaccurate</td>
                </tr>
            </table>
            
            <h3>Accuracy Estimates (3D Mode)</h3>
            <p>These ranges assume that all spatial DICOM metadata (FrameOfReferenceUID, ImageOrientationPatient, ImagePositionPatient, PixelSpacing, SliceThickness) is correct and consistent. Under that assumption, 3D interpolation and numerical effects dominate the residual geometric error.</p>
            <ul>
                <li><strong>Best Case</strong> (accurate spatial metadata, linear interpolation, same Frame of Reference):
                    <ul>
                        <li>Spatial accuracy (native): sub‑voxel in all three dimensions, typically ≈±0.5–0.87 voxels total.</li>
                        <li>Physical equivalent (1 mm isotropic voxels): ≈±0.6–1.0 mm total positional error.</li>
                    </ul>
                </li>
                <li><strong>Typical Case</strong> (good spatial metadata, linear interpolation):
                    <ul>
                        <li>Spatial accuracy: ≈±0.87 voxels from interpolation plus small spacing/orientation uncertainties.</li>
                        <li>Physical equivalent: ≈±1.0–1.5 mm for most CT/PET volumes.</li>
                    </ul>
                </li>
                <li><strong>Worst Case (algorithm‑only)</strong> (still assuming correct metadata, but aggressive resampling between very different grids/orientations):
                    <ul>
                        <li>Spatial accuracy: a few voxels of total 3D error in extreme edge cases.</li>
                        <li>Physical equivalent: several millimetres, particularly with very thick slices.</li>
                    </ul>
                </li>
            </ul>
            <p><em>Metadata error scenarios</em> (e.g., mismatched FrameOfReferenceUIDs, mis‑encoded positions or spacings) are not bounded by these values. In those cases, voxel‑level misalignment can be arbitrarily large and the fused images should be interpreted with extreme caution unless the metadata has been corrected or explicit registration has been applied.</p>
            
            <h2 id="spatial-alignment">Spatial Alignment</h2>
            
            <h3>Automatic Alignment</h3>
            <p>The system automatically calculates spatial alignment using DICOM metadata:</p>
            <ul>
                <li><strong>Scaling Factors</strong>: Calculated from pixel spacing ratios</li>
                <li><strong>Translation Offset</strong>: Calculated from ImagePositionPatient difference, converted to pixels</li>
            </ul>
            
            <h3>Manual Adjustment</h3>
            <p>Users can manually adjust translation offset:</p>
            <ul>
                <li>Range: -500 to +500 pixels</li>
                <li>Step: 1 pixel</li>
                <li>Reset to calculated offset available</li>
                <li>Useful for fine-tuning when automatic alignment is slightly off</li>
            </ul>
            
            <h3>Alignment Accuracy</h3>
            <ul>
                <li><strong>Automatic alignment error</strong>:
                    <ul>
                        <li>Depends on ImagePositionPatient accuracy</li>
                        <li>Typical DICOM accuracy: ±0.1-0.5 mm</li>
                        <li>For 1 mm pixel spacing: ±0.1-0.5 pixels</li>
                        <li><strong>Total alignment error: ±0.1-0.5 mm (best case) to ±1-2 mm (typical)</strong></li>
                    </ul>
                </li>
                <li><strong>Manual adjustment precision</strong>:
                    <ul>
                        <li>Limited to integer pixels</li>
                        <li>For 1 mm pixel spacing: ±0.5 mm precision</li>
                        <li>For 0.5 mm pixel spacing: ±0.25 mm precision</li>
                    </ul>
                </li>
            </ul>
            
            <h2 id="error-analysis">Error Sources and Accuracy Analysis</h2>
            
            <h3>Summary of Error Sources</h3>
            <p>The tables below summarize key error sources across 2D and 3D fusion, grouped into algorithm‑intrinsic effects and DICOM metadata/input‑driven effects.</p>
            <h4>Algorithm‑intrinsic error sources (with correct metadata)</h4>
            <table>
                <tr>
                    <th>Error Source</th>
                    <th>2D Mode Error (pixels/voxels &amp; mm)</th>
                    <th>3D Mode Error (voxels &amp; mm)</th>
                    <th>Notes</th>
                </tr>
                <tr>
                    <td>Slice interpolation</td>
                    <td>≈±0.5 overlay slices (±0.5 voxels in Z); ≈±0.5 mm at 1 mm spacing, ≈±1.5 mm at 3 mm spacing</td>
                    <td>N/A (effect is handled by 3D interpolation/resampling instead of explicit 2D per‑slice interpolation)</td>
                    <td>Through‑plane interpolation when the base slice lies between overlay slices</td>
                </tr>
                <tr>
                    <td>Pixel spacing scaling</td>
                    <td>≈±0.5 pixels in x/y; ≈±0.5 mm at 1 mm pixels, ≈±0.25 mm at 0.5 mm pixels</td>
                    <td>N/A (3D resampling handles in‑plane scaling)</td>
                    <td>2D resize of overlay to match base field of view; slight blurring at edges</td>
                </tr>
                <tr>
                    <td>Translation offset (rounding)</td>
                    <td>±0.5 pixels in x/y; ≈±0.5 mm at 1 mm pixels, ≈±0.25 mm at 0.5 mm pixels</td>
                    <td>N/A (3D translation handled in world coordinates)</td>
                    <td>Rounding mm offsets to integer pixel indices in 2D mode</td>
                </tr>
                <tr>
                    <td>3D resampling interpolation</td>
                    <td>N/A</td>
                    <td>≈±0.5–0.87 voxels (linear); ≈±0.3–0.7 voxels (cubic/B‑spline); ≈±0.5–0.9 mm at 1 mm voxels</td>
                    <td>Unavoidable sub‑voxel error from mapping overlay into the base volume grid</td>
                </tr>
            </table>
            <h4>Metadata / input‑driven error sources</h4>
            <table>
                <tr>
                    <th>Error Source</th>
                    <th>2D Mode Error (pixels/voxels &amp; mm)</th>
                    <th>3D Mode Error (voxels &amp; mm)</th>
                    <th>Notes</th>
                </tr>
                <tr>
                    <td>Slice location extraction</td>
                    <td>Unbounded; can mis‑match slices by many indices (tens of voxels) if tags are wrong</td>
                    <td>Same: mis‑ordering/dropping slices can distort the volume</td>
                    <td>Incorrect/missing <code>SliceLocation</code>/<code>ImagePositionPatient</code> affects which slices are fused, not the interpolation math</td>
                </tr>
                <tr>
                    <td>Orientation mismatch</td>
                    <td>Can be many pixels (or entire FOV) off; several mm–cm in physical space</td>
                    <td>Reduced to sub‑voxel interpolation error if metadata is correct and 3D resampling is used</td>
                    <td>Different <code>ImageOrientationPatient</code>; 2D mode cannot fully correct this, 3D mode relies on accurate direction cosines</td>
                </tr>
                <tr>
                    <td>Slice spacing calculation</td>
                    <td>N/A</td>
                    <td>Typically ±0.1–0.5 mm with good metadata; larger % errors if derived from oblique positions</td>
                    <td>Depends on positions and thickness; algorithm follows reported geometry</td>
                </tr>
                <tr>
                    <td>Frame of Reference mismatch</td>
                    <td>Can be very large (entire organs shifted)</td>
                    <td>Same: misregistration can be many voxels; several mm–cm physically</td>
                    <td>Wrong/different <code>FrameOfReferenceUID</code>; identity transform is wrong, and fusion is only qualitatively valid unless separate registration is applied</td>
                </tr>
                <tr>
                    <td>Rescale parameter inconsistency</td>
                    <td>Low (intensity only)</td>
                    <td>Low (intensity only)</td>
                    <td>Per‑slice differences in rescale slope/intercept cause value, not geometric, errors if a single global pair is used</td>
                </tr>
            </table>
            
            <h3>Overall Accuracy Estimates</h3>
            <p><strong>2D Mode:</strong></p>
            <ul>
                <li>Best case: ±0.5-1.0 mm</li>
                <li>Typical case: ±1.0-2.5 mm</li>
                <li>Worst case (orientation mismatch): Unpredictable, may be unusable</li>
            </ul>
            
            <p><strong>3D Mode:</strong></p>
            <ul>
                <li>Best case: ±0.6-1.0 mm</li>
                <li>Typical case: ±1.0-1.5 mm</li>
                <li>Worst case (Frame of Reference mismatch): Unpredictable, may be unusable</li>
            </ul>
            
            <h3>Recommendations</h3>
            <ol>
                <li><strong>Use 3D mode</strong> when:
                    <ul>
                        <li>Series have different orientations</li>
                        <li>Slice thickness ratio > 2:1 or < 0.5:1</li>
                        <li>Maximum accuracy is required</li>
                    </ul>
                </li>
                <li><strong>Use 2D mode</strong> when:
                    <ul>
                        <li>Series have same orientation</li>
                        <li>Similar slice thicknesses</li>
                        <li>Speed is prioritized</li>
                    </ul>
                </li>
                <li><strong>Verify Frame of Reference</strong>:
                    <ul>
                        <li>Check status indicator for warnings</li>
                        <li>If Frame of Reference differs, verify alignment manually</li>
                    </ul>
                </li>
                <li><strong>Fine-tune alignment</strong>:
                    <ul>
                        <li>Use manual translation offset adjustment if automatic alignment is slightly off</li>
                        <li>Adjust in 1-pixel increments for sub-pixel precision</li>
                    </ul>
                </li>
            </ol>
            
            <h2 id="performance">Performance Considerations</h2>
            
            <h3>Memory Usage</h3>
            <ul>
                <li><strong>2D Mode</strong>:
                    <ul>
                        <li>Processes one slice at a time</li>
                        <li>Memory: ~2-4× single slice size</li>
                        <li>Typical: 10-50 MB per slice</li>
                    </ul>
                </li>
                <li><strong>3D Mode</strong>:
                    <ul>
                        <li>Caches full resampled volume</li>
                        <li>Memory: ~2× volume size</li>
                        <li>Typical: 100-500 MB for typical CT/PET volumes</li>
                        <li>Cache persists until series changes</li>
                    </ul>
                </li>
            </ul>
            
            <h3>Processing Time</h3>
            <ul>
                <li><strong>2D Mode</strong>:
                    <ul>
                        <li>Slice matching: < 1 ms</li>
                        <li>2D resize: 10-50 ms per slice</li>
                        <li>Blending: 5-20 ms per slice</li>
                        <li><strong>Total: 15-70 ms per slice</strong></li>
                    </ul>
                </li>
                <li><strong>3D Mode</strong>:
                    <ul>
                        <li>Volume conversion: 100-500 ms (one-time)</li>
                        <li>3D resampling: 500-2000 ms (one-time, cached)</li>
                        <li>Slice extraction: < 1 ms (from cached volume)</li>
                        <li>Blending: 5-20 ms per slice</li>
                        <li><strong>Total: 600-2500 ms first slice, 5-20 ms subsequent slices</strong></li>
                    </ul>
                </li>
            </ul>
            
            <h3>Optimization Strategies</h3>
            <ul>
                <li><strong>Caching</strong>: 3D mode caches resampled volumes to avoid repeated resampling</li>
                <li><strong>Lazy evaluation</strong>: Resampling only occurs when fusion is enabled</li>
                <li><strong>Thread-safe caching</strong>: Uses locks for multi-threaded access</li>
                <li><strong>Cache invalidation</strong>: Clears cache when series changes</li>
            </ul>
            
            <hr>
            <p><em>For detailed usage instructions, see the Quick Start Guide in the application Help menu.</em></p>
        </body>
        </html>
        """
        
        # Cache the content for this theme
        FusionTechnicalDocDialog._content_cache[theme] = content
        return content
    
    def _on_search_text_changed(self, text: str) -> None:
        """
        Handle search text changes and filter documentation content.
        
        Args:
            text: Search text entered by user
        """
        if not text.strip():
            # If search is empty, show full content
            self.text_edit.setHtml(self._full_content)
            # Scroll to top
            self.text_edit.moveCursor(self.text_edit.textCursor().Start)
            self._search_match_positions = []
            self._current_match_index = -1
            self._update_navigation_buttons()
            return
        
        # Use QTextEdit's find functionality to search and highlight
        # First, set the full content
        self.text_edit.setHtml(self._full_content)
        
        # Find and highlight all occurrences (case-insensitive)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        
        # Clear previous selection
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)
        
        # Find all matches and store positions
        self._search_match_positions = []
        while self.text_edit.find(text):
            match_cursor = self.text_edit.textCursor()
            # Store the start position of each match
            self._search_match_positions.append(match_cursor.selectionStart())
        
        # If matches found, go to first match
        if self._search_match_positions:
            self._current_match_index = 0
            cursor.setPosition(self._search_match_positions[0])
            self.text_edit.setTextCursor(cursor)
            # Highlight the first match
            cursor.setPosition(self._search_match_positions[0])
            cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(text))
            self.text_edit.setTextCursor(cursor)
        else:
            # No matches found, scroll to top
            cursor.movePosition(cursor.MoveOperation.Start)
            self.text_edit.setTextCursor(cursor)
            self._current_match_index = -1
        
        self._update_navigation_buttons()
    
    def _on_prev_match(self) -> None:
        """Navigate to previous search match."""
        if not self._search_match_positions or self._current_match_index <= 0:
            return
        
        self._current_match_index -= 1
        cursor = self.text_edit.textCursor()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        self.text_edit.setTextCursor(cursor)
        # Highlight the match
        search_text = self.search_edit.text()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(search_text))
        self.text_edit.setTextCursor(cursor)
        self._update_navigation_buttons()
    
    def _on_next_match(self) -> None:
        """Navigate to next search match."""
        if not self._search_match_positions:
            return
        
        if self._current_match_index < len(self._search_match_positions) - 1:
            self._current_match_index += 1
        else:
            # Wrap around to first match
            self._current_match_index = 0
        
        cursor = self.text_edit.textCursor()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        self.text_edit.setTextCursor(cursor)
        # Highlight the match
        search_text = self.search_edit.text()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(search_text))
        self.text_edit.setTextCursor(cursor)
        self._update_navigation_buttons()
    
    def _update_navigation_buttons(self) -> None:
        """Update Prev/Next button states based on current match."""
        has_matches = len(self._search_match_positions) > 0
        self.prev_button.setEnabled(has_matches and self._current_match_index > 0)
        self.next_button.setEnabled(has_matches)
