## Plan: Privacy-Locked Tag Editing

**Status:** **Shipped and archived** (`metadata_panel.py`, `tag_viewer_dialog.py`, `PrivacyController` / dialog coordinator wiring).

Implement privacy-safe tag editing so patient tags cannot be edited while Privacy Mode is ON, and any already-open patient-tag edit popup is force-closed with a short user notice when Privacy Mode is enabled. Reuse existing privacy propagation and patient-tag detection instead of duplicating anonymization logic.

**Steps**
1. Phase 1 - Lock edit entry points for patient tags while Privacy Mode is ON.
2. Add a shared guard helper in metadata and tag viewer edit paths that checks privacy_mode + patient-tag identity using is_patient_tag(tag_str).
3. In MetadataPanel, gate edit launch in _on_item_double_clicked before opening TagEditDialog; when blocked, show a concise information message.
4. In TagViewerDialog, gate edit launch in _edit_tag_item so both double-click and context-menu edit routes are protected through one path. Depends on step 2.
5. Optionally disable the Edit context-menu action in TagViewerDialog when selected item is a patient tag and privacy_mode is ON (UX polish, not required for correctness).

**Steps**
1. Phase 2 - Handle already-open edit popups on privacy toggle.
2. Track active TagEditDialog instances in MetadataPanel and TagViewerDialog (single current reference per surface is sufficient because dialogs are modal).
3. Add a method on each surface (for example close_active_tag_edit_dialog_due_to_privacy()) that closes active patient-tag dialogs and returns whether a dialog was closed.
4. In each surface set_privacy_mode(enabled), when enabled=True call that close method before repopulating tags; if closed, show a short user notification message indicating editing was closed due to Privacy Mode. Depends on step 2.
5. Ensure dialog-reference cleanup occurs on dialog close/accept/reject to avoid stale pointers.

**Steps**
1. Phase 3 - Wire persistent tag viewer refresh and close behavior through coordinator/controller.
2. Add a dialog-coordinator privacy fan-out method that applies privacy to the open Tag Viewer dialog and triggers close of any active edit popup there.
3. Extend PrivacyController to invoke the dialog-coordinator privacy method during apply_privacy(enabled), preserving existing metadata/overlay/image refresh order. Depends on Phase 1 and 2.
4. Update DICOMViewerApp privacy-controller initialization to pass dialog coordinator to PrivacyController.

**Steps**
1. Phase 4 - Verification and regression checks.
2. Add targeted tests for: blocked edit-open under privacy mode, forced close of active patient-tag popup on privacy enable, and unchanged edit behavior for non-patient tags.
3. Run venv-based tests with focus filter first, then broader suite if needed.
4. Execute manual QA scenarios for metadata panel and tag viewer paths.

**Relevant files**
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/gui/metadata_panel.py - Add privacy edit guard, active edit-dialog tracking, and forced-close-on-privacy helper.
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/gui/dialogs/tag_viewer_dialog.py - Add privacy edit guard in _edit_tag_item, active dialog tracking, and forced-close helper.
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/gui/dialogs/tag_edit_dialog.py - No required behavior change; keep as generic editor unless a tiny API hook is needed for robust cleanup callbacks.
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/gui/dialog_coordinator.py - Add privacy update fan-out for open tag viewer/editor dialog state.
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/core/privacy_controller.py - Include dialog coordinator in privacy propagation sequence.
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/main.py - Pass dialog coordinator dependency into PrivacyController construction.
- c:/Mac/Home/Documents/MyCodes-ForWindows/DICOMViewerV3/DICOMViewerV3/src/utils/dicom_utils.py - Reuse is_patient_tag(tag_str) helper for lock decisions.

**Verification**
1. Activate venv, then run focused tests: python -m pytest tests/ -v -k "privacy or metadata or tag".
2. Run project regression command if focused tests are sparse: python tests/run_tests.py.
3. Manual scenario 1: Privacy OFF, open patient-tag edit popup, toggle Privacy ON, confirm popup closes immediately and info message appears.
4. Manual scenario 2: Privacy ON, attempt to edit patient tag from metadata panel and tag viewer, confirm edit is blocked and message appears.
5. Manual scenario 3: Privacy ON, edit non-patient tag, confirm edit remains allowed.
6. Manual scenario 4: Privacy OFF after being ON, confirm patient-tag editing is re-enabled and no stale lock remains.

**Decisions**
- Included scope: lock patient-tag editing while privacy is ON across metadata panel and tag viewer.
- Included scope: force-close already-open patient-tag edit popup when Privacy Mode is enabled, with a brief user notice.
- Excluded scope: keeping popup open in read-only mode (not selected).
- Reuse decision: enforce via existing privacy state and is_patient_tag helper instead of adding separate anonymization-state tracking.

**Further Considerations**
1. Recommendation: keep the user notice lightweight and non-blocking where possible to avoid interrupting rapid toggles.
2. Recommendation: centralize user-facing message text to keep wording consistent across metadata panel and tag viewer.
3. Recommendation: add at least one regression test around privacy toggle + active modal dialog lifecycle to prevent future breaks.
