# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for DICOM Viewer V3
#
# This file configures how PyInstaller builds the executable for the DICOM Viewer application.
# 
# Usage:
#   pyinstaller DICOMViewerV3.spec
#
# The executable will be created in the dist/ directory.
#
# For detailed build instructions, see docs/BUILDING_EXECUTABLES.md

import os
from pathlib import Path

block_cipher = None

# Construct absolute path to main.py
# PyInstaller is run from the project root directory
# Use os.getcwd() to get the current working directory (project root)
cwd = os.getcwd()
project_root = Path(cwd).resolve()

# Build absolute paths
src_dir = project_root / 'src'
main_py = src_dir / 'main.py'

# Convert to absolute path strings
main_py_abs = str(main_py.resolve())
src_dir_abs = str(src_dir.resolve())

a = Analysis(
    [main_py_abs],
    pathex=[src_dir_abs],
    binaries=[],
    datas=[
        ('resources', 'resources'),  # Include resources directory (images, etc.)
    ],
    hiddenimports=[
        # Application modules - explicitly include all submodules
        'gui',
        'gui.main_window',
        'gui.dialogs',
        'gui.dialogs.file_dialog',
        'gui.dialogs.settings_dialog',
        'gui.dialogs.tag_viewer_dialog',
        'gui.dialogs.overlay_config_dialog',
        'gui.dialogs.annotation_options_dialog',
        'gui.dialogs.export_dialog',
        'gui.dialogs.tag_export_dialog',
        'gui.dialogs.tag_edit_dialog',
        'gui.dialogs.histogram_dialog',
        'gui.dialogs.about_this_file_dialog',
        'gui.dialogs.disclaimer_dialog',
        'gui.dialogs.edit_recent_list_dialog',
        'gui.dialogs.overlay_settings_dialog',
        'gui.dialogs.quick_start_guide_dialog',
        'gui.image_viewer',
        'gui.multi_window_layout',
        'gui.sub_window_container',
        'gui.metadata_panel',
        'gui.window_level_controls',
        'gui.roi_statistics_panel',
        'gui.roi_list_panel',
        'gui.slice_navigator',
        'gui.series_navigator',
        'gui.zoom_display_widget',
        'gui.cine_player',
        'gui.cine_controls_widget',
        'gui.intensity_projection_controls_widget',
        'gui.overlay_manager',
        'gui.overlay_coordinator',
        'gui.roi_coordinator',
        'gui.measurement_coordinator',
        'gui.crosshair_coordinator',
        'gui.dialog_coordinator',
        'gui.mouse_mode_handler',
        'gui.keyboard_event_handler',
        'gui.magnifier_widget',
        'core',
        'core.dicom_loader',
        'core.dicom_organizer',
        'core.dicom_parser',
        'core.dicom_processor',
        'core.dicom_editor',
        'core.tag_edit_history',
        'core.view_state_manager',
        'core.file_operations_handler',
        'core.slice_display_manager',
        'core.slice_grouping',
        'core.multiframe_handler',
        'core.key_object_handler',
        'core.presentation_state_handler',
        'tools',
        'tools.roi_manager',
        'tools.measurement_tool',
        'tools.crosshair_manager',
        'tools.annotation_manager',
        'tools.histogram_widget',
        'utils',
        'utils.config_manager',
        'utils.dicom_utils',
        'utils.dicom_anonymizer',
        'utils.image_utils',
        'utils.undo_redo',
        # Core DICOM libraries
        'pydicom',
        'pydicom.encoders',
        'pydicom.tag',
        'pydicom.datadict',
        'pydicom.dataelem',
        'pydicom.uid',
        'pydicom.multival',
        'pydicom.pixels',
        'pydicom.errors',
        'pydicom.dataset',
        # Note: pydicom.decoders doesn't exist as a separate module
        # Note: pydicom.encoders.gdcm requires GDCM system libraries (not installed)
        # Note: pydicom.encoders.pylibjpeg doesn't exist - pylibjpeg is used via pydicom's plugin system
        # Image processing
        'numpy',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        # Plotting
        'matplotlib',
        'matplotlib.backends.backend_qt5agg',
        # Excel export
        'openpyxl',
        # Compressed DICOM support - these are plugins used by pydicom
        'pylibjpeg',
        'openjpeg',  # JPEG 2000 support (from pylibjpeg-openjpeg)
        'rle',  # RLE support (from pylibjpeg-rle)
        'libjpeg',  # JPEG support (from pylibjpeg-libjpeg)
        'jpeg_ls',  # JPEG-LS codec (from pyjpegls)
        '_CharLS',  # JPEG-LS C extension (from pyjpegls)
        # Qt/PySide6 modules
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test modules to reduce size
        'matplotlib.tests',
        'numpy.tests',
        'PIL.tests',
        'pydicom.tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Don't bundle binaries in the exe (needed for .app bundle on macOS)
    name='DICOMViewerV3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression (requires UPX to be installed)
    console=False,  # Set to True for debugging (shows console window), False for windowed app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.ico',  # Windows icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DICOMViewerV3',
)

# For macOS, create a proper .app bundle
# This will create DICOMViewerV3.app on macOS
# On Windows/Linux, this step is ignored and the COLLECT output is used
app = BUNDLE(
    coll,
    name='DICOMViewerV3.app',
    icon='resources/icons/dvv6ldvv6ldvv6ld_edit-removebg-preview.icns',  # macOS icon
    bundle_identifier='com.dicomviewer.v3',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '3.0.0',
        'CFBundleVersion': '3.0.0',
        'CFBundleIconFile': 'dvv6ldvv6ldvv6ld_edit-removebg-preview',  # Icon name without .icns extension
    },
)
