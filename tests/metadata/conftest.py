"""
Conftest for metadata controller tests.

Ensures src/ is on sys.path so that `from metadata.metadata_controller import …`
resolves to src/metadata/ rather than this test directory.
"""
import sys
import os

_src = os.path.join(os.path.dirname(__file__), '..', '..', 'src')
_src = os.path.normpath(_src)
if _src not in sys.path:
    sys.path.insert(0, _src)
