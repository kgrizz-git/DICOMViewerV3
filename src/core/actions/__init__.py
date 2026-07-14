"""
Application action helpers (dialogs, file open entrypoints, cine export).

These modules hold logic moved from ``main.DICOMViewerApp`` to keep the
composition root smaller. They take the app instance as the first argument and
must not import ``main`` at runtime (use ``TYPE_CHECKING`` only) to avoid cycles.
"""
