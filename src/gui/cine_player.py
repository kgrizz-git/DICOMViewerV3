"""
Cine Player

This module provides cine loop playback functionality for multi-frame DICOM sequences.

Inputs:
    - DICOM datasets with timing information
    - Playback control requests (play, pause, stop)
    - Speed and loop settings
    
Outputs:
    - Automatic frame advancement signals
    - Playback state changes
    
Requirements:
    - PySide6 for QTimer and signals
    - pydicom for DICOM dataset access
    - core.dicom_parser for frame rate extraction
    - core.multiframe_handler for multi-frame detection
"""

from PySide6.QtCore import QObject, QTimer, Signal
from typing import Optional, Dict
from pydicom.dataset import Dataset
from core.dicom_parser import get_frame_rate_from_dicom
from core.multiframe_handler import is_multiframe, get_frame_count


class CinePlayer(QObject):
    """
    Handles cine loop playback for multi-frame DICOM sequences.
    
    Features:
    - Automatic frame advancement using QTimer
    - Frame rate extraction from DICOM tags
    - Play/pause/stop functionality
    - Speed adjustment (0.25x, 0.5x, 1x, 2x, 4x)
    - Loop toggle
    - Support for both multi-frame files and sequential single-frame series
    """
    
    # Signals
    frame_advance_requested = Signal(int)  # Request to advance to next frame index
    playback_state_changed = Signal(bool)  # Emitted when play/pause state changes (True = playing)
    
    def __init__(self, slice_navigator, get_total_slices_callback, get_current_slice_callback):
        """
        Initialize the cine player.
        
        Args:
            slice_navigator: SliceNavigator instance for frame navigation
            get_total_slices_callback: Callback to get total number of slices
            get_current_slice_callback: Callback to get current slice index
        """
        super().__init__()
        
        self.slice_navigator = slice_navigator
        self.get_total_slices = get_total_slices_callback
        self.get_current_slice = get_current_slice_callback
        
        # Playback state
        self.is_playing = False
        self.is_paused = False
        self.current_frame_rate = 10.0  # Default 10 FPS
        self.speed_multiplier = 1.0  # 1.0 = normal speed
        self.loop_enabled = False
        
        # Timer for frame advancement
        self.timer = QTimer()
        self.timer.timeout.connect(self._advance_frame)
        self.timer.setSingleShot(False)
        
        # Flag to track if frame advance is from cine player (to distinguish from manual navigation)
        self._is_cine_advancing = False
        
        # Current series context
        self.current_studies: Optional[Dict] = None
        self.current_study_uid: Optional[str] = None
        self.current_series_uid: Optional[str] = None
    
    def set_series_context(self, studies: Optional[Dict], study_uid: Optional[str], series_uid: Optional[str]) -> None:
        """
        Update the current series context.
        
        Args:
            studies: Dictionary of studies
            study_uid: Current study UID
            series_uid: Current series UID
        """
        self.current_studies = studies
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        
        # Stop playback if series changes
        if self.is_playing:
            self.stop_playback()
    
    def is_cine_capable(self, studies: Optional[Dict], study_uid: Optional[str], series_uid: Optional[str]) -> bool:
        """
        Check if a series can be played as cine.
        
        Args:
            studies: Dictionary of studies
            study_uid: Study UID
            series_uid: Series UID
            
        Returns:
            True if series is cine-capable (has multiple frames/slices), False otherwise
        """
        if not studies or not study_uid or not series_uid:
            return False
        
        try:
            if study_uid not in studies or series_uid not in studies[study_uid]:
                return False
            
            datasets = studies[study_uid][series_uid]
            if not datasets or len(datasets) < 2:
                return False
            
            # Check if it's a multi-frame file or sequential single-frames
            # For multi-frame, check first dataset
            first_dataset = datasets[0]
            if is_multiframe(first_dataset):
                num_frames = get_frame_count(first_dataset)
                return num_frames > 1
            
            # For sequential single-frames, check if we have multiple slices
            return len(datasets) >= 2
            
        except Exception:
            return False
    
    def get_frame_rate_from_dicom(self, dataset: Dataset) -> Optional[float]:
        """
        Extract frame rate from DICOM dataset.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Frame rate in FPS, or None if not found
        """
        return get_frame_rate_from_dicom(dataset)
    
    def start_playback(self, frame_rate: Optional[float] = None, dataset: Optional[Dataset] = None) -> bool:
        """
        Start cine playback.
        
        Args:
            frame_rate: Optional frame rate in FPS. If None, will try to extract from dataset.
            dataset: Optional dataset to extract frame rate from if frame_rate is None.
            
        Returns:
            True if playback started successfully, False otherwise
        """
        # Check if series is cine-capable
        if not self.is_cine_capable(self.current_studies, self.current_study_uid, self.current_series_uid):
            return False
        
        # Determine frame rate
        if frame_rate is not None and frame_rate > 0:
            self.current_frame_rate = frame_rate
        elif dataset is not None:
            extracted_rate = self.get_frame_rate_from_dicom(dataset)
            if extracted_rate is not None and extracted_rate > 0:
                self.current_frame_rate = extracted_rate
            # Otherwise keep current frame_rate (default 10 FPS)
        # If neither provided, use current frame_rate
        
        # Calculate interval in milliseconds based on speed
        effective_fps = self.current_frame_rate * self.speed_multiplier
        interval_ms = int(1000.0 / effective_fps) if effective_fps > 0 else 100
        
        # Start timer
        self.timer.start(interval_ms)
        self.is_playing = True
        self.is_paused = False
        self.playback_state_changed.emit(True)
        
        return True
    
    def pause_playback(self) -> None:
        """Pause cine playback."""
        if self.is_playing:
            self.timer.stop()
            self.is_paused = True
            self.is_playing = False
            self.playback_state_changed.emit(False)
    
    def resume_playback(self) -> None:
        """Resume paused playback."""
        if self.is_paused:
            # Restart with current settings
            self.start_playback(self.current_frame_rate)
    
    def stop_playback(self) -> None:
        """Stop cine playback and reset to first frame."""
        self.timer.stop()
        self.is_playing = False
        self.is_paused = False
        self.playback_state_changed.emit(False)
        
        # Reset to first frame
        total_slices = self.get_total_slices()
        if total_slices > 0:
            self.frame_advance_requested.emit(0)
    
    def set_speed(self, speed_multiplier: float) -> None:
        """
        Set playback speed multiplier.
        
        Args:
            speed_multiplier: Speed multiplier (0.25, 0.5, 1.0, 2.0, 4.0, etc.)
        """
        if speed_multiplier <= 0:
            return
        
        self.speed_multiplier = speed_multiplier
        
        # Update timer interval if currently playing
        if self.is_playing:
            effective_fps = self.current_frame_rate * self.speed_multiplier
            interval_ms = int(1000.0 / effective_fps) if effective_fps > 0 else 100
            self.timer.setInterval(interval_ms)
    
    def set_loop(self, enabled: bool) -> None:
        """
        Enable or disable looping.
        
        Args:
            enabled: True to enable looping, False to disable
        """
        self.loop_enabled = enabled
    
    def _advance_frame(self) -> None:
        """Internal method to advance to next frame (called by timer)."""
        total_slices = self.get_total_slices()
        if total_slices == 0:
            self.stop_playback()
            return
        
        current_slice = self.get_current_slice()
        next_slice = current_slice + 1
        
        # Check if we've reached the end
        if next_slice >= total_slices:
            if self.loop_enabled:
                # Loop back to beginning
                next_slice = 0
            else:
                # Stop at last frame
                self.stop_playback()
                return
        
        # Set flag to indicate this is a cine player advance
        self._is_cine_advancing = True
        # Request frame advancement
        self.frame_advance_requested.emit(next_slice)
        # Reset flag after a short delay (frame change should happen immediately)
        # We'll reset it in the frame advance handler
    
    def is_cine_advancing(self) -> bool:
        """
        Check if current frame advance is from cine player.
        
        Returns:
            True if cine player is advancing, False otherwise
        """
        return self._is_cine_advancing
    
    def reset_cine_advancing_flag(self) -> None:
        """Reset the cine advancing flag (called after frame advance completes)."""
        self._is_cine_advancing = False
    
    def get_current_frame_rate(self) -> float:
        """
        Get current frame rate.
        
        Returns:
            Current frame rate in FPS
        """
        return self.current_frame_rate
    
    def get_effective_frame_rate(self) -> float:
        """
        Get effective frame rate (considering speed multiplier).
        
        Returns:
            Effective frame rate in FPS
        """
        return self.current_frame_rate * self.speed_multiplier
    
    def is_playback_active(self) -> bool:
        """
        Check if playback is currently active.
        
        Returns:
            True if playing, False otherwise
        """
        return self.is_playing

