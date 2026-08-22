# pyinstaller_exclude_lists.py
#
# Single source of truth for PyInstaller `Analysis.excludes` entries that are
# easy to get wrong (PIL Tk helpers, matplotlib backends / writers).
# Imported by DICOMViewerV3.spec (scripts/ is on sys.path) and audited by
# tests/test_pyinstaller_exclude_audit.py against src/ (and tests/) imports
# (matplotlib backends, PIL Tk helpers).

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
