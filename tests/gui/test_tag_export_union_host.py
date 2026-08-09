from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEventLoop

from gui.tag_export_union_host import (
    TagExportUnionHost,
    flatten_studies_for_tag_export_union,
)

# QWidget suites need a QApplication.  Never create a module-level
# QCoreApplication: pytest imports all selected test modules before fixtures run,
# and Qt cannot upgrade a QCoreApplication to QApplication afterwards.
pytestmark = pytest.mark.usefixtures("qapp")


def test_flatten_studies():
    ds1, ds2, ds3 = MagicMock(), MagicMock(), MagicMock()
    studies = {
        "study1": {"series1": [ds1], "series2": [ds2]},
        "study2": {"series3": [ds3]},
    }
    out = flatten_studies_for_tag_export_union(studies)
    assert out == [ds1, ds2, ds3]


def test_host_initialization():
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)
    assert host._app == mock_app
    assert host._generation == 0
    assert host._merged is None
    assert host._worker is None
    assert host.get_snapshot() == (0, None)


def test_host_drain_worker_none():
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)
    host.drain_worker()
    assert host._worker is None


def test_host_drain_worker_not_running():
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = False

    # simulate TypeError when disconnecting unbound signals
    mock_worker.finished_ok.disconnect.side_effect = TypeError
    mock_worker.failed.disconnect.side_effect = TypeError

    host._worker = mock_worker
    host.drain_worker()

    assert host._worker is None
    mock_worker.requestInterruption.assert_not_called()


@patch("gui.tag_export_union_host.QApplication")
def test_host_drain_worker_running_cooperative(mock_qapp):
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)

    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    # Dynamically finish thread on wait()
    mock_worker.wait.side_effect = lambda *args: setattr(
        mock_worker.isRunning, "return_value", False
    )
    host._worker = mock_worker

    mock_app_inst = MagicMock()
    mock_qapp.instance.return_value = mock_app_inst

    host.drain_worker()

    assert host._worker is None
    mock_worker.finished_ok.disconnect.assert_called_once_with(host._on_worker_finished)
    mock_worker.failed.disconnect.assert_called_once_with(host._on_worker_failed)
    mock_worker.requestInterruption.assert_called_once()
    mock_worker.wait.assert_called_once_with(50)
    mock_app_inst.processEvents.assert_called_once_with(
        QEventLoop.ProcessEventsFlag.AllEvents, 50
    )


@patch("gui.tag_export_union_host.QApplication")
def test_host_drain_worker_running_no_app_inst(mock_qapp):
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)

    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    mock_worker.wait.side_effect = lambda *args: setattr(
        mock_worker.isRunning, "return_value", False
    )
    host._worker = mock_worker

    # Simulate no QApplication instance
    mock_qapp.instance.return_value = None

    host.drain_worker()

    assert host._worker is None
    mock_worker.requestInterruption.assert_called_once()
    mock_worker.wait.assert_called_once_with(50)


@patch("gui.tag_export_union_host.QApplication")
@patch("gui.tag_export_union_host.time.monotonic")
def test_host_drain_worker_timeout(mock_monotonic, mock_qapp, capsys):
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)

    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    host._worker = mock_worker

    # 0.0 for setup, 10.0 for loop condition check, 200.0 for next loop condition check
    mock_monotonic.side_effect = [0.0, 10.0, 200.0]

    host.drain_worker(timeout_sec=180.0)

    assert host._worker is None
    mock_worker.requestInterruption.assert_called_once()
    assert mock_worker.wait.call_count == 1

    # Verify stderr warning
    captured = capsys.readouterr()
    assert "TagExportUnionWorker did not finish within 180s" in captured.err


def test_host_schedule_rebuild_empty_studies():
    mock_app = MagicMock()
    mock_app.current_studies = {}
    host = TagExportUnionHost(mock_app)
    host._generation = 1

    host.schedule_rebuild()

    assert host._generation == 2
    assert host._merged is None
    mock_app.tag_export_union_ready.emit.assert_called_once_with(2, {})
    assert host._worker is None


@patch("gui.tag_export_union_host.TagExportUnionWorker")
def test_host_schedule_rebuild_with_studies(mock_worker_class):
    mock_app = MagicMock()
    mock_app.current_studies = {"study1": {"series1": ["ds"]}}

    mock_worker = MagicMock()
    mock_worker_class.return_value = mock_worker

    host = TagExportUnionHost(mock_app)
    host.schedule_rebuild()

    assert host._generation == 1
    assert host._worker == mock_worker
    mock_worker_class.assert_called_once_with(
        1, ["ds"], include_private=True, supplement_standard_tags=True
    )
    mock_worker.finished_ok.connect.assert_called_once_with(host._on_worker_finished)
    mock_worker.failed.connect.assert_called_once_with(host._on_worker_failed)
    mock_worker.start.assert_called_once()


@patch("gui.tag_export_union_host.TagExportUnionWorker")
def test_host_schedule_rebuild_drains_existing(mock_worker_class):
    mock_app = MagicMock()
    mock_app.current_studies = {"study1": {"series1": ["ds"]}}

    mock_worker_new = MagicMock()
    mock_worker_class.return_value = mock_worker_new

    host = TagExportUnionHost(mock_app)

    mock_worker_old = MagicMock()
    mock_worker_old.isRunning.return_value = False
    host._worker = mock_worker_old

    host.schedule_rebuild()

    mock_worker_old.finished_ok.disconnect.assert_called_once_with(
        host._on_worker_finished
    )
    assert host._worker == mock_worker_new


def test_host_on_worker_finished():
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)
    host._generation = 1

    # Wrong generation
    host._on_worker_finished(0, {"wrong": True})
    assert host._merged is None
    mock_app.tag_export_union_ready.emit.assert_not_called()

    # Correct generation
    host._on_worker_finished(1, {"correct": True})
    assert host._merged == {"correct": True}
    mock_app.tag_export_union_ready.emit.assert_called_once_with(1, {"correct": True})
    assert host.get_snapshot() == (1, {"correct": True})


def test_host_on_worker_failed():
    mock_app = MagicMock()
    host = TagExportUnionHost(mock_app)
    host._generation = 1
    host._merged = {"existing": True}

    # Wrong generation
    host._on_worker_failed(0, "error")
    assert host._merged == {"existing": True}
    mock_app.tag_export_union_ready.emit.assert_not_called()

    # Correct generation
    host._on_worker_failed(1, "error")
    assert host._merged is None
    mock_app.tag_export_union_ready.emit.assert_called_once_with(1, {})
