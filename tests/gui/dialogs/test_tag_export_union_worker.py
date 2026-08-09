from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset

from gui.dialogs.tag_export_union_worker import TagExportUnionWorker

# Qt signals require a running QApplication — provided by the session-scoped
# qapp fixture from pytest-qt (via conftest.py). Do NOT create a module-level
# QCoreApplication here; doing so prevents upgrading to QApplication later
# and causes a native crash when other test files run in the same process.
pytestmark = pytest.mark.usefixtures("qapp")


def test_worker_initialization():
    worker = TagExportUnionWorker(
        generation=1,
        datasets=[],
        include_private=True,
        supplement_standard_tags=False,
        include_sequences=True,
    )
    assert worker._generation == 1
    assert worker._datasets == []
    assert worker._include_private is True
    assert worker._supplement is False
    assert worker._include_sequences is True


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
def test_worker_run_union_merging_and_param_forwarding(mock_parser_class):
    mock_parser1 = MagicMock()
    mock_parser1.get_all_tags.return_value = {
        "(0010,0010)": "PatientA",
        "(0008,0060)": "CT",
    }
    mock_parser2 = MagicMock()
    mock_parser2.get_all_tags.return_value = {
        "(0010,0010)": "PatientB_Ignored",
        "(0020,000D)": "StudyUID",
    }

    mock_parser_class.side_effect = [mock_parser1, mock_parser2]

    ds1, ds2 = Dataset(), Dataset()
    worker = TagExportUnionWorker(
        generation=42,
        datasets=[ds1, ds2],
        include_private=True,
        supplement_standard_tags=False,
        include_sequences=True,
    )

    ok_emitted = []
    failed_emitted = []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    # Assert signal emissions
    assert len(ok_emitted) == 1
    assert len(failed_emitted) == 0
    gen, merged = ok_emitted[0]
    assert gen == 42
    assert merged == {
        "(0010,0010)": "PatientA",
        "(0008,0060)": "CT",
        "(0020,000D)": "StudyUID",
    }

    # Assert DICOMParser calls and kwarg forwarding
    assert mock_parser_class.call_count == 2
    mock_parser1.get_all_tags.assert_called_once_with(
        include_private=True,
        supplement_standard_tags=False,
        include_sequences=True,
    )
    mock_parser2.get_all_tags.assert_called_once_with(
        include_private=True,
        supplement_standard_tags=False,
        include_sequences=True,
    )


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
def test_worker_run_empty_datasets(mock_parser_class):
    worker = TagExportUnionWorker(1, [], True, False)
    ok_emitted, failed_emitted = [], []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    assert len(ok_emitted) == 1
    assert ok_emitted[0] == (1, {})
    assert len(failed_emitted) == 0
    mock_parser_class.assert_not_called()


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
@patch("gui.dialogs.tag_export_union_worker.supplement_export_tags_dict")
def test_worker_run_with_supplement(mock_supplement, mock_parser_class):
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser
    mock_parser.get_all_tags.return_value = {"tag1": "data1"}

    worker = TagExportUnionWorker(1, [Dataset()], True, True)

    ok_emitted, failed_emitted = [], []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    mock_supplement.assert_called_once_with({"tag1": "data1"})
    assert len(ok_emitted) == 1
    assert ok_emitted[0][1] == mock_supplement.return_value
    assert len(failed_emitted) == 0


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
def test_worker_run_interrupted_before_parsing(mock_parser_class):
    worker = TagExportUnionWorker(1, [Dataset()], True, True)
    worker.isInterruptionRequested = MagicMock(return_value=True)

    ok_emitted, failed_emitted = [], []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    assert len(ok_emitted) == 0
    assert len(failed_emitted) == 0
    mock_parser_class.assert_not_called()


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
def test_worker_run_interrupted_during_merge(mock_parser_class):
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser

    worker = TagExportUnionWorker(1, [Dataset()], True, True)
    state = {"calls": 0}

    def interrupt_checker():
        state["calls"] += 1
        return state["calls"] > 2

    worker.isInterruptionRequested = MagicMock(side_effect=interrupt_checker)

    # TagExportUnionWorker.run checks isInterruptionRequested every
    # _MERGE_INTERRUPT_CHECK_INTERVAL merged tags (n % 4000 == 0); size the
    # dict one past a full interval so more than one check fires.
    _MERGE_INTERRUPT_CHECK_INTERVAL = 4000
    large_dict = {f"tag{i}": i for i in range(_MERGE_INTERRUPT_CHECK_INTERVAL + 1)}
    mock_parser.get_all_tags.return_value = large_dict

    ok_emitted, failed_emitted = [], []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    assert len(ok_emitted) == 0
    assert len(failed_emitted) == 0


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
def test_worker_run_interrupted_after_parsing(mock_parser_class):
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser
    mock_parser.get_all_tags.return_value = {"tag1": "data1"}

    worker = TagExportUnionWorker(1, [Dataset()], True, True)

    state = {"calls": 0}

    def interrupt_checker():
        state["calls"] += 1
        return state["calls"] == 3

    worker.isInterruptionRequested = MagicMock(side_effect=interrupt_checker)

    ok_emitted, failed_emitted = [], []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    assert len(ok_emitted) == 0
    assert len(failed_emitted) == 0


@patch("gui.dialogs.tag_export_union_worker.DICOMParser")
def test_worker_run_exception(mock_parser_class):
    mock_parser_class.side_effect = Exception("Test error")

    worker = TagExportUnionWorker(1, [Dataset()], True, False)

    ok_emitted, failed_emitted = [], []
    worker.finished_ok.connect(lambda gen, merged: ok_emitted.append((gen, merged)))
    worker.failed.connect(lambda gen, msg: failed_emitted.append((gen, msg)))

    worker.run()

    assert len(ok_emitted) == 0
    assert len(failed_emitted) == 1
    assert failed_emitted[0] == (1, "Test error")
