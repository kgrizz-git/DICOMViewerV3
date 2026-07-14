# pyinstaller_exclude_lists.py
#
# Single source of truth for PyInstaller `Analysis.excludes` entries that are
# easy to get wrong (PIL Tk helpers, matplotlib backends / writers, macOS-only PySide6 trims).
# Imported by DICOMViewerV3.spec (scripts/ is on sys.path) and audited by
# tests/test_pyinstaller_exclude_audit.py against src/ (and tests/) imports
# (matplotlib backends, macOS PySide6 trims, PIL Tk helpers).

"""Shared PyInstaller exclude module name lists for DICOMViewerV3.spec."""

# Pillow: Qt UI only; no Tk PhotoImage. Excluding these modules keeps tkinter out of the
# bundle without touching PIL.Image / codecs (verified no tk/ImageTk/_tkinter/tkagg in src/ or tests/).
PIL_TK_RELATED_EXCLUDES: tuple[str, ...] = (
    "PIL.ImageTk",
    "PIL._tkinter_finder",
)

# Matplotlib: app uses FigureCanvasQTAgg / backend_qtagg only (histogram_widget).
# Excluding other Qt/cairo backends and file writers is safe only while no code
# calls savefig to pdf/svg/ps/etc. or forces a different backend.
MATPLOTLIB_BACKEND_AND_WRITER_EXCLUDES: tuple[str, ...] = (
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_wxagg",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_gtk4agg",
    "matplotlib.backends.backend_webagg",
    "matplotlib.backends.backend_webagg_core",
    "matplotlib.backends.backend_nbagg",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_qt4agg",
    "matplotlib.backends.backend_qtcairo",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_svg",
    "matplotlib.backends.backend_ps",
    "matplotlib.backends.backend_pgf",
    "matplotlib.backends.backend_cairo",
)

# macOS-only (when DICOMViewerV3.spec sets PYINSTALLER_MACOS_SLIM): large PySide6 wheels not
# referenced in application source. Default builds omit these excludes for compatibility.
# If you add a feature that needs one of these, remove it from this tuple or turn slim off.
MACOS_PYSIDE6_MODULE_EXCLUDES: tuple[str, ...] = (
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSql",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtQuickWidgets",
)
