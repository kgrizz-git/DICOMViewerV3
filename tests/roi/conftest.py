"""
Conftest for ROI measurement controller tests.

Ensures src/ is on sys.path so that `from roi.roi_measurement_controller import …`
resolves to src/roi/ rather than this test directory.
"""
import sys
import os

_src = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
_src = os.path.normpath(_src)
if _src not in sys.path:
    sys.path.insert(0, _src)
