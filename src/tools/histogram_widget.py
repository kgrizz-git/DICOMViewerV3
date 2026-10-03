"""
Histogram Widget

This module provides histogram display for whole slices or selected ROIs,
with window width and level indicators overlaid.

Inputs:
    - Pixel array data
    - Optional ROI mask
    - Window/level values
    
Outputs:
    - Histogram plot with window/level indicators
    - ``window_level_dragged(center, width)`` when the user drags a window
      edge of the composed curve (see ``tools.histogram_window_drag``)
    
Requirements:
    - PySide6 for widget
    - matplotlib for plotting
    - numpy for calculations
"""


from typing import Any, ClassVar

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from tools.histogram_window_drag import Edge, dragged_window, edge_near, window_edges


def _paint_lut_input_axis(output_axis: Any, paths: Any) -> Any:
    """Draw the LUT alone on a 0–255 input axis above the stored-value plot.

    Grayscale tables are a line. Color maps are a bar. The window/level ramp
    and the composed curve stay on ``output_axis``.
    """
    if paths.lut_trace is None and paths.lut_colors is None:
        return None
    axis = output_axis.twiny()
    if paths.lut_trace is not None:
        xs = np.arange(paths.lut_trace.shape[0], dtype=np.float64)
        axis.plot(xs, paths.lut_trace, color="#4aa3ff", linewidth=1.5, label=f"LUT {paths.name}")
        # Lower right stays clear of the histogram legend, which is upper right.
        axis.legend(loc="lower right")
    if paths.lut_colors is not None:
        axis.imshow(
            paths.lut_colors.reshape(1, -1, 3),
            aspect="auto",
            extent=(0, 255, 0, 16),
            origin="lower",
            interpolation="nearest",
        )
    axis.set_xlim(0, 255)
    axis.set_xticks(_SCALE_TICKS)
    axis.set_xlabel("LUT input")
    return axis


def _paint_stored_curves(
    axis: Any,
    paths: Any,
    *,
    show_window: bool,
    show_composed: bool,
) -> None:
    """Draw the window/level ramp and composed curve on the stored-value axis.

    When those two coincide, one line is drawn if either checkbox is on.
    """
    if not show_window and not show_composed:
        return
    label = f"{paths.name} ({paths.source})"
    composed_label = f"{label}, inverted" if paths.net_inverted else label
    if paths.collapse and show_window and show_composed:
        axis.plot(paths.xs, paths.composed, color="#ffb000", linewidth=2.0, label=f"W/L, {label}")
    else:
        if show_window:
            axis.plot(
                paths.xs,
                paths.window,
                color="#888888",
                linestyle="--",
                linewidth=1.0,
                label="W/L ramp",
            )
        if show_composed:
            axis.plot(paths.xs, paths.composed, color="#ffb000", linewidth=2.5, label=composed_label)
    axis.legend(loc="upper left")


# Stay inside 0–255. The default locator adds 300, which draws past the figure.
_SCALE_TICKS = (0, 50, 100, 150, 200, 255)


def _set_plot_margins(figure: Figure, *, output_axis: bool, lut_axis: bool) -> None:
    """Leave room for the Output label and the top LUT axis when those exist.

    The plain histogram uses a tight right and top edge. Twin axes draw their
    titles outside that box, so those titles are clipped unless the margins grow.
    """
    figure.subplots_adjust(
        left=0.12,
        right=0.86 if output_axis else 0.98,
        top=0.82 if lut_axis else 0.97,
        bottom=0.18,
    )


def _style_axis(axis: Any, foreground: str, spine_color: str) -> None:
    """Match one axes' ticks, labels, spines, and legend to the Qt theme."""
    axis.tick_params(colors=foreground)
    axis.xaxis.label.set_color(foreground)
    axis.yaxis.label.set_color(foreground)
    for spine in axis.spines.values():
        spine.set_edgecolor(spine_color)
    legend = axis.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_color(foreground)


def _apply_axis_fonts(axis: Any, label_pt: int, tick_pt: int) -> None:
    """Scale one axes' labels, ticks, and legend with the dialog."""
    axis.tick_params(axis="both", labelsize=tick_pt)
    axis.xaxis.get_label().set_fontsize(label_pt)
    axis.yaxis.get_label().set_fontsize(label_pt)
    legend = axis.get_legend()
    if legend is not None:
        legend.get_frame().set_linewidth(0.5)
        for text in legend.get_texts():
            text.set_fontsize(tick_pt)


class HistogramWidget(QWidget):
    """
    Widget for displaying image histograms.
    
    Features:
    - Display histogram for whole slice or ROI
    - Show window/level indicators
    - Update dynamically
    - Drag a window edge of the composed curve to change window/level
    """

    window_level_dragged = Signal(float, float)

    def __init__(self, parent=None):
        """
        Initialize the histogram widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._create_ui()
        self.pixel_array: np.ndarray | None = None
        self.roi_mask: np.ndarray | None = None
        self.window_center: float | None = None
        self.window_width: float | None = None
        self.use_log_scale: bool = False
        # Optional global axis constraints supplied by the dialog
        self.global_frequency_max: float | None = None
        self.global_x_min: float | None = None
        self.global_x_max: float | None = None
        self._overlay_lut: Any = None
        self._overlay_photometric: object = None
        self._overlay_inverted = False
        self._show_window_curve = True
        self._show_lut_curve = True
        self._show_composed_curve = True
        self._transfer_axis: Any = None
        self._lut_input_axis: Any = None
        self._drag_edge: Edge | None = None
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)

    # Font size tiers for responsive scaling (min width threshold -> (title_pt, label_pt, tick_pt))
    # label_pt is clamped to ≥ 11 at medium and larger sizes (C12).
    _FONT_TIERS: ClassVar[list[tuple[int, tuple[int, int, int]]]] = [
        (0,   (7,  7,  6)),   # very small
        (360, (8,  8,  7)),   # small
        (500, (11, 11, 9)),   # medium
        (700, (12, 11, 10)),  # default/large
    ]

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title (stored for font scaling on resize)
        self._title_label = QLabel("Histogram")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self._title_label)

        # Matplotlib figure
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.axes = self.figure.add_subplot(111)
        # Plain histogram. Overlay axes reserve the right and top in _paint_lut_overlay.
        _set_plot_margins(self.figure, output_axis=False, lut_axis=False)
        self.axes.set_xlabel("Pixel Value")
        self.axes.set_ylabel("Frequency")
        self.axes.grid(True, alpha=0.3)

    def set_pixel_array(self, pixel_array: np.ndarray | None) -> None:
        """
        Set the pixel array for histogram calculation.
        
        Args:
            pixel_array: Image pixel array, or None to clear
        """
        self.pixel_array = pixel_array
        self._update_histogram()

    def set_roi_mask(self, roi_mask: np.ndarray | None) -> None:
        """
        Set ROI mask for histogram calculation.
        
        Args:
            roi_mask: Optional binary mask for ROI
        """
        self.roi_mask = roi_mask
        self._update_histogram()

    def set_window_level(self, center: float | None, width: float | None) -> None:
        """
        Set window center and width for indicators.
        
        Args:
            center: Window center value
            width: Window width value
        """
        self.window_center = center
        self.window_width = width
        self._update_histogram()

    def _edge_at(self, event: Any) -> Edge | None:
        """The composed-curve window edge under a press, or None."""
        if not self._show_composed_curve or self._transfer_axis is None:
            return None
        if self.window_center is None or self.window_width is None or self.window_width <= 0:
            return None
        if event.x is None or event.inaxes is None:
            return None
        low, high = window_edges(self.window_center, self.window_width)
        to_px = self.axes.transData.transform
        low_px = float(to_px((low, 0.0))[0])
        high_px = float(to_px((high, 0.0))[0])
        return edge_near(float(event.x), low_px, high_px)

    def _on_press(self, event: Any) -> None:
        """Grab a window edge with the left button."""
        if getattr(event, "button", None) != 1:
            return
        self._drag_edge = self._edge_at(event)

    def _on_motion(self, event: Any) -> None:
        """Move the grabbed edge and report the new window."""
        edge = self._drag_edge
        if edge is None or event.x is None or event.y is None:
            return
        if self.window_center is None or self.window_width is None:
            return
        # Convert through the histogram axes, not ``event.xdata``: the pointer
        # may be over the LUT-input axis, whose x runs 0-255 rather than over
        # stored values.
        x = float(self.axes.transData.inverted().transform((event.x, event.y))[0])
        center, width = dragged_window(edge, x, self.window_center, self.window_width)
        self.window_level_dragged.emit(center, width)

    def _on_release(self, _event: Any) -> None:
        """Drop the grabbed edge."""
        self._drag_edge = None

    def set_log_scale(self, use_log: bool) -> None:
        """
        Set whether to use log scale for y-axis.
        
        Args:
            use_log: True for log scale, False for linear scale
        """
        self.use_log_scale = use_log
        self._update_histogram()

    def set_global_frequency_max(self, max_freq: float | None) -> None:
        """
        Set an optional global maximum frequency for the y-axis.
        
        Args:
            max_freq: Maximum histogram frequency across the series (or None to use per-slice max)
        """
        self.global_frequency_max = max_freq
        self._update_histogram()

    def set_global_pixel_range(self, x_min: float | None, x_max: float | None) -> None:
        """
        Set an optional global pixel value range for the x-axis.

        Args:
            x_min: Minimum pixel value across the series (or None to use per-slice range)
            x_max: Maximum pixel value across the series (or None to use per-slice range)
        """
        self.global_x_min = x_min
        self.global_x_max = x_max
        self._update_histogram()

    def update_font_sizes_for_size(self, width: int, height: int) -> None:
        """
        Update title, axis labels, tick labels, and legend font sizes based on
        the current widget/dialog size so the plot remains readable when resized smaller.
        Uses size tiers with a minimum cap so fonts do not shrink below legibility.
        """
        # Use the smaller dimension to pick tier so narrow or short windows get smaller fonts
        size_key = min(width, height) if width > 0 and height > 0 else 700
        title_pt, label_pt, tick_pt = (12, 10, 9)  # default
        for threshold, (t_pt, l_pt, k_pt) in reversed(self._FONT_TIERS):
            if size_key >= threshold:
                title_pt, label_pt, tick_pt = t_pt, l_pt, k_pt
                break
        self._title_label.setStyleSheet(f"font-weight: bold; font-size: {title_pt}pt;")
        for axis in (self.axes, self._transfer_axis, self._lut_input_axis):
            if axis is not None:
                _apply_axis_fonts(axis, label_pt, tick_pt)
        self.canvas.draw_idle()

    def _is_dark_mode(self) -> bool:
        return self.palette().window().color().lightness() < 128

    def _apply_theme_colors(self) -> None:
        """Apply matplotlib colors to match the current Qt theme (dark / light)."""
        if self._is_dark_mode():
            bg          = "#1a1a1a"
            fg          = "#cccccc"
            spine_color = "#555555"
            grid_color  = "#333333"
        else:
            bg          = "#ffffff"
            fg          = "#000000"
            spine_color = "#cccccc"
            grid_color  = "#e0e0e0"

        self.figure.patch.set_facecolor(bg)
        self.axes.set_facecolor(bg)
        for axis in (self.axes, self._transfer_axis, self._lut_input_axis):
            if axis is not None:
                _style_axis(axis, fg, spine_color)
        self.axes.grid(True, alpha=0.3, color=grid_color)

    def _update_histogram(self) -> None:
        """Update the histogram display."""
        if self.pixel_array is None:
            return

        # Get pixels for histogram
        if self.roi_mask is not None:
            pixels = self.pixel_array[self.roi_mask]
        else:
            pixels = self.pixel_array.flatten()

        if len(pixels) == 0:
            return

        # Clear axes
        self._clear_transfer_axis()
        self.axes.clear()

        # Calculate histogram, optionally using a fixed global x-range
        if (
            self.global_x_min is not None
            and self.global_x_max is not None
            and self.global_x_max > self.global_x_min
        ):
            hist, bins = np.histogram(pixels, bins=256, range=(self.global_x_min, self.global_x_max))
        else:
            hist, bins = np.histogram(pixels, bins=256)
        bin_centers = (bins[:-1] + bins[1:]) / 2.0

        # Determine y-axis limits using optional global max
        local_max = float(hist.max()) if hist.size > 0 else 0.0
        y_max = float(self.global_frequency_max) if (self.global_frequency_max is not None and self.global_frequency_max > 0) else local_max
        if y_max <= 0:
            y_max = 1.0

        # Set y-axis scale and limits before drawing overlays
        if self.use_log_scale:
            self.axes.set_yscale('log')
            # Avoid log(0) issues by setting a positive minimum based on data where possible
            positive = hist[hist > 0]
            if positive.size > 0:
                bottom = max(0.1, float(positive.min()))
            else:
                bottom = 0.1
            self.axes.set_ylim(bottom=bottom, top=y_max)
        else:
            self.axes.set_yscale('linear')
            self.axes.set_ylim(bottom=0.0, top=y_max)

        # Plot histogram
        self.axes.plot(bin_centers, hist, 'b-', linewidth=1.5, label='Histogram')
        self.axes.fill_between(bin_centers, 0, hist, alpha=0.3)

        # Add window/level box overlay (no fill)
        if self.window_center is not None and self.window_width is not None:
            window_min = self.window_center - self.window_width / 2.0

            # Get y-axis limits for box height
            y_min, y_max = self.axes.get_ylim()
            box_height = y_max - y_min

            # Draw box (rectangle with no fill, just outline)
            from matplotlib.patches import Rectangle
            box = Rectangle(
                (window_min, y_min),
                self.window_width,
                box_height,
                linewidth=2,
                edgecolor='red',
                facecolor='none',  # No fill
                linestyle='--',
                label='Window/Level'
            )
            self.axes.add_patch(box)

            # Optional: Add vertical line at center for clarity
            self.axes.axvline(self.window_center, color='r', linestyle=':',
                            linewidth=1, alpha=0.5)

        # Set x-axis limits to global range if provided, otherwise to current data range
        if (
            self.global_x_min is not None
            and self.global_x_max is not None
            and self.global_x_max > self.global_x_min
        ):
            self.axes.set_xlim(self.global_x_min, self.global_x_max)
        elif bin_centers.size > 0:
            self.axes.set_xlim(bin_centers[0], bin_centers[-1])

        self.axes.set_xlabel("Pixel Value")
        if self.use_log_scale:
            self.axes.set_ylabel("Frequency (Log Scale)")
        else:
            self.axes.set_ylabel("Frequency (Linear Scale)")

        self._paint_lut_overlay()
        self.axes.legend(loc='upper right')
        self.axes.grid(True, alpha=0.3)

        # Apply theme colors (dark / light) then font scaling — both call draw_idle internally
        self._apply_theme_colors()
        self.update_font_sizes_for_size(self.size().width(), self.size().height())

    def set_lut_overlay(
        self,
        lut: Any,
        photometric_interpretation: object,
        image_inverted: bool,
        refresh: bool = True,
    ) -> None:
        """Store the pane LUT inputs. Paths are sampled by the transfer widget at draw time."""
        self._overlay_lut = lut
        self._overlay_photometric = photometric_interpretation
        self._overlay_inverted = image_inverted
        if refresh:
            self._update_histogram()

    def set_overlay_curves(self, *, window: bool, lut: bool, composed: bool) -> None:
        """Show or hide the stored-axis ramp, the 0–255 LUT, and the composed curve."""
        self._show_window_curve = window
        self._show_lut_curve = lut
        self._show_composed_curve = composed
        self._update_histogram()

    def _clear_transfer_axis(self) -> None:
        """Drop the previous output and LUT-input axes before the histogram is cleared."""
        for name in ("_lut_input_axis", "_transfer_axis"):
            axis = getattr(self, name, None)
            setattr(self, name, None)
            if axis is not None:
                axis.remove()

    def _paint_lut_overlay(self) -> None:
        """Draw ramp, LUT, and composed result from the shared transfer widget."""
        from gui.widgets.lut_transfer_function_widget import overlay_paths

        x_min, x_max = self.axes.get_xlim()
        paths = overlay_paths(
            self._overlay_lut,
            self.window_center,
            self.window_width,
            self._overlay_photometric,
            self._overlay_inverted,
            float(x_min),
            float(x_max),
        )
        show_window = self._show_window_curve
        show_lut = self._show_lut_curve
        show_composed = self._show_composed_curve
        overlay = paths is not None and (show_window or show_lut or show_composed)
        _set_plot_margins(self.figure, output_axis=overlay, lut_axis=overlay and show_lut)
        if not overlay or paths is None:
            return
        twin = self.axes.twinx()
        self._transfer_axis = twin
        twin.set_ylim(0, 255)
        twin.set_yticks(_SCALE_TICKS)
        twin.set_ylabel("Output")
        _paint_stored_curves(twin, paths, show_window=show_window, show_composed=show_composed)
        if show_lut:
            self._lut_input_axis = _paint_lut_input_axis(twin, paths)

