"""
Temp-dir lifecycle for per-module image directories (P2-I3).

``QAAppFacade`` stays the public slot owner; this module owns the
``TemporaryDirectory`` creation / cleanup wiring so the facade does not grow
past its grandfathered line cap.

Inputs:
    - ``QARequest`` with ``embed_module_images_in_xlsx`` (default True).
    - An optional *existing* composite image temp dir (CT single) whose
      lifetime already covers the post-run export; the module-images dir can
      be nested under it so a single cleanup covers both.

Outputs:
    - ``request.module_images_out_dir`` set to a live temp dir when embed is
      on; a callable that dir-owning code invokes to release the dir.

Requirements:
    - When embed is off, ``module_images_out_dir`` is left unset (callers may
      still use the composite ``analyzed_image_out_path`` as today).
    - When embed is on, the dir is held open until after ``workbook.save()`` /
      result dialog closes -- same cleanup sites as the composite temp dir.
    - Never leaks temp dirs on cancel or exception (``finally`` / callbacks).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable

from qa.analysis_types import QARequest


def assign_module_images_out_dir(
    request: QARequest,
    *,
    composite_image_temp_dir: tempfile.TemporaryDirectory[str] | None = None,
) -> Callable[[], None] | None:
    """
    Set ``request.module_images_out_dir`` when embed is on.

    Creates a module-images temp dir for the run. When a composite image temp
    dir is provided (CT single), the module dir is nested under it so the
    composite dir's existing cleanup covers both. Otherwise a standalone
    ``TemporaryDirectory`` is created and returned as a cleanup callable.

    Args:
        request: Run request with ``embed_module_images_in_xlsx`` and a
            writable ``module_images_out_dir`` attribute.
        composite_image_temp_dir: When given, nest the module dir under this
            dir (its cleanup already covers the post-run export window).

    Returns:
        A zero-arg cleanup callable when a standalone temp dir was created
        (caller must invoke it), or ``None`` when the dir nests under
        ``composite_image_temp_dir`` (the composite cleanup covers it).
    """
    if not getattr(request, "embed_module_images_in_xlsx", True):
        return None

    if composite_image_temp_dir is not None:
        # Nested under the composite dir: a single cleanup covers both.
        module_dir = os.path.join(composite_image_temp_dir.name, "modules")
        os.makedirs(module_dir, exist_ok=True)
        request.module_images_out_dir = module_dir
        return None

    # Standalone temp dir (MRI single): caller owns cleanup.
    temp_dir = tempfile.TemporaryDirectory(prefix="qa-mri-module-images-")
    request.module_images_out_dir = temp_dir.name
    return temp_dir.cleanup
