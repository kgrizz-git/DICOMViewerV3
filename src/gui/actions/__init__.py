"""
GUI action helpers (dialog entrypoints, cine export).

These modules hold dialog-launching logic that belongs in the GUI layer.
They take the app instance as the first argument and must not import ``main``
at runtime (use ``TYPE_CHECKING`` only) to avoid cycles.
"""
