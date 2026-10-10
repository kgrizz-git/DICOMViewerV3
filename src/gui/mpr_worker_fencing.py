"""MPR background-build fencing for ``MprController``.

Worker identity plus pane and source generations decide whether a build
callback still owns its pane. Cancellation retires the native worker:
request stop, close its dialog, keep it alive until it actually terminates
(a fixed wait is not proof), and invalidate its callbacks. A GUI-owned
``QTimer`` poller (parented to the controller) sweeps terminated workers;
unknown termination state never counts as terminated.

``app`` and ``controller`` are duck-typed; helpers never raise for missing
workers or widgets.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from gui.mpr_controller_sessions import release_pane_reservation
from utils.debug_flags import DEBUG_MPR
from utils.dicom_utils import get_composite_series_key


def _fence_log(message: str) -> None:
    """Print an MPR fencing debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")



# ---------------------------------------------------------------------------
# Build fencing: worker identity plus pane and source generations
# ---------------------------------------------------------------------------


def bump_pane_generation(controller: Any, idx: int) -> int:
    """Invalidate every in-flight callback for *idx*; return the new generation."""
    generations = controller._build_generations
    generations[idx] = generations.get(idx, 0) + 1
    return generations[idx]


def bump_source_generation(controller: Any, study_uid: str, series_uid: str) -> int:
    """Invalidate every in-flight callback built from one source."""
    key = (study_uid, series_uid)
    generations = controller._source_generations
    generations[key] = generations.get(key, 0) + 1
    return generations[key]


def dataset_source_key(datasets: Any) -> tuple[str, str]:
    """``(study_uid, composite series key)`` of the first dataset, else ``("", "")``.

    Uses the composite series key, matching the ``close_series`` API and
    pane ``current_series_uid``.
    """
    try:
        first = datasets[0]
        return (
            str(getattr(first, "StudyInstanceUID", "") or ""),
            str(get_composite_series_key(first) or ""),
        )
    except Exception:
        return ("", "")


def volume_source_key(volume: Any) -> tuple[str, str]:
    """Authoritative source key of a build volume's resolved datasets."""
    return dataset_source_key(getattr(volume, "source_datasets", []) or [])


def is_current_pane_build(
    controller: Any,
    idx: int,
    worker: Any,
    pane_generation: int,
    source_key: tuple[str, str],
    source_generation: int,
) -> bool:
    """True only when a callback still owns its pane: same registered worker,
    unchanged pane generation, and unchanged source generation."""
    if controller._workers.get(idx) is not worker:
        return False
    if controller._build_generations.get(idx, 0) != pane_generation:
        return False
    return controller._source_generations.get(source_key, 0) == source_generation


def _worker_finished(worker: Any) -> bool:
    """True only when the native thread actually terminated.

    An unknown state (``isFinished`` missing or raising) never counts as
    terminated: the worker is retained and re-polled.
    """
    try:
        return bool(worker.isFinished())
    except Exception:
        return False


def truly_terminated(worker: Any) -> bool:
    """Public alias for termination polling (tests and sweeps)."""
    return _worker_finished(worker)


def ensure_retire_poller(controller: Any, interval_ms: int = 500) -> None:
    """Start the GUI-owned cleanup poller while retired workers remain.

    The poller is a ``QTimer`` parented to the controller, so Qt owns its
    lifetime. It stops itself once the retiring list drains.
    """
    if not controller._retiring_builds:
        return
    poller = controller._retire_poller
    if poller is None:
        poller = QTimer(controller)
        poller.setInterval(interval_ms)
        poller.timeout.connect(lambda: sweep_retired_builds(controller))
        controller._retire_poller = poller
    if not poller.isActive():
        poller.start()


def sweep_retired_builds(controller: Any) -> None:
    """Drop retired workers whose native threads actually terminated.

    A zero-timeout join confirms cleanup for real ``QThread`` semantics
    without blocking: it joins an already-finished thread and returns
    immediately otherwise.
    """
    live: list[Any] = []
    for worker in controller._retiring_builds:
        if truly_terminated(worker):
            _join_terminated_worker(worker)
        else:
            live.append(worker)
    controller._retiring_builds = live
    poller = controller._retire_poller
    if poller is not None and not controller._retiring_builds and poller.isActive():
        poller.stop()


def _join_terminated_worker(worker: Any) -> None:
    """Join an already-terminated worker to confirm native cleanup."""
    waiter = getattr(worker, "wait", None)
    if not callable(waiter):
        return
    try:
        waiter(0)
    except Exception:
        pass


def retain_build_worker(controller: Any, worker: Any) -> None:
    """Keep a worker (active, completed, or errored) until true termination.

    Connects the worker's completion signal as a backup sweep trigger. The
    custom ``finished`` signal carries the build result payload and fires
    before the native thread returns, so the callback must NOT drop the
    worker directly — it sweeps, keeping anything still running.
    Unknown termination state retains (see ``_worker_finished``).
    """
    if worker is None or truly_terminated(worker):
        return
    if not any(w is worker for w in controller._retiring_builds):
        controller._retiring_builds.append(worker)
    try:
        worker.finished.connect(lambda _result=None: sweep_retired_builds(controller))
    except Exception:
        pass
    ensure_retire_poller(controller)


def retire_pane_worker(controller: Any, idx: int) -> bool:
    """Retire any in-progress build for *idx* without blocking the GUI.

    Requests the native worker to stop, closes its progress dialog, keeps it
    alive until it actually terminates (a fixed wait is not proof), and
    invalidates its callbacks via the pane generation. Also releases the
    pane's pending admission reservation (idempotent), so cancel, source
    closure, close-all and replacement all free the slot exactly once.
    Returns True when a worker was retired. Safe to call with no worker
    registered.
    """
    bump_pane_generation(controller, idx)
    release_pane_reservation(controller, idx)
    worker = controller._workers.pop(idx, None)
    controller._build_sources.pop(idx, None)
    _close_build_dialog(controller, idx)
    if worker is None:
        return False
    try:
        worker.cancel()
    except Exception:
        pass
    try:
        worker.quit()
    except Exception:
        pass
    retain_build_worker(controller, worker)
    return True


def _close_build_dialog(controller: Any, idx: int) -> None:
    """Close and forget the progress dialog for *idx*, if any."""
    dialog = controller._build_progress.pop(idx, None)
    if dialog is None:
        return
    try:
        dialog.close()
    except Exception:
        pass


def note_build_started(
    controller: Any, idx: int, source_key: tuple[str, str]
) -> tuple[int, int]:
    """Fence a new build: bump the pane generation, register the authoritative
    build source, and return ``(pane_generation, source_generation)``."""
    pane_generation = bump_pane_generation(controller, idx)
    controller._build_sources[idx] = source_key
    source_generation = controller._source_generations.setdefault(source_key, 0)
    return pane_generation, source_generation


def drop_build_registration(controller: Any, idx: int) -> None:
    """Forget a finished/errored build's worker slot, source, and dialog."""
    controller._workers.pop(idx, None)
    controller._build_sources.pop(idx, None)
    _close_build_dialog(controller, idx)




__all__ = [
    "bump_pane_generation",
    "bump_source_generation",
    "dataset_source_key",
    "drop_build_registration",
    "ensure_retire_poller",
    "is_current_pane_build",
    "note_build_started",
    "retain_build_worker",
    "retire_pane_worker",
    "sweep_retired_builds",
    "truly_terminated",
    "volume_source_key",
]
