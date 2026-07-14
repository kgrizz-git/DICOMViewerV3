"""
Backward-compatibility shim — ROI persistence moved to ``utils.roi_persistence``.

Re-exports all public names so existing ``from tools.roi_persistence import ...``
statements continue to work.
"""

from utils.roi_persistence import *  # noqa: F403
