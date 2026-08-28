"""U7 production regressions for dirty-data filing and school-scale batch previews."""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import event

TID = 1000000000000000001


def _set_ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "1", "tenantId": str(TID), "realName": "U7归档管理员",
        "currentRoleCode": "SCHOOL_ADMIN", "userType": "TEACHER", "activeContextId": "ctx",
    })


def _clear_ctx():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def _new_batch(db, label: str, planned_count: int):
    from app.models import GraduationBatch
    from app.modules.graduation.materials.rule_service import initialize_default_rule_in_session

    suffix = uuid.uuid4().hex[:10]
    row = GraduationBatch(
        tenant_id=TID, batch_name=f"U7 {label}-{suffix}", batch_no=f"U7-{label.upper()}-{suffix}",
        academic_year="2026-2027", grade_year="2027届", planned_count=planned_count, status="RUNNING",
    )
    db.add(row)
    db.flush()
    initialize_default_rule_in_session(db, int(row.id))
    return row


def _count_selects(engine, fn):
    count = 0

    def before_cursor_execute(_conn, _cursor, statement, *_args, **_kwargs):
        nonlocal count
        if statement.lstrip().upper().startswith("SELECT"):
            count += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        return fn(), count
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_u7_batch_file_dirty_row_is_non_executable_even_when_other_checks_are_clean():
    from app.modules.graduation.services.graduation_archive_batch_scale import row_block_reasons

    row = {
        "dataAnomaly": True, "anomalyReasons": ["学生姓名缺失"], "missing": [],
        "openRisks": 0, "archiveStatus": "SUBMITTED",
    }
    assert row_block_reasons(row, "FILE") == ["dirty_data"]


def test_u7_public_v2_writer_consumes_signed_dirty_marker_contract():
    root = Path(__file__).resolve().parents[2]
    snapshot = (root / "backend/app/modules/graduation/services/graduation_archive_batch_scale.py").read_text(encoding="utf-8")
    compat = (root / "backend/app/modules/graduation/services/graduation_archive_batch_consistency.py").read_text(encoding="utf-8")
    manifest = (root / "backend/app/modules/graduation/materials/manifest_service.py").read_text(encoding="utf-8")

    assert "readonly_missing_markers(student)" in snapshot
    assert 'reasons.append("dirty_data")' in snapshot
    assert "row_block_reasons(snap, \"FILE\")" in compat
    assert 'snapshot = verify_batch_file_preview(int(batch_id), str(preview_token))' in manifest
    assert 'if row.get("missing") or int(row.get("openRisks") or 0) > 0:' in manifest


def test_u7_required_proposal_defense_uses_approved_pass_business_source():
    from app.modules.graduation.services.graduation_archive_v2_preview import _source_ready

    assert _source_ready("PROPOSAL_DEFENSE", {}, 101, set(), {}, {101}) is True
    assert _source_ready("PROPOSAL_DEFENSE", {}, 101, set(), {}, {202}) is False


def test_u7_archive_v2_preview_guard_binds_rule_required_sources_and_fileversions():
    root = Path(__file__).resolve().parents[2]
    bridge = (root / "backend/app/modules/graduation/services/graduation_archive_v2_preview.py").read_text(encoding="utf-8")
    api = (root / "frontend/src/modules/graduation/api/graduation-risk-archive.api.js").read_text(encoding="utf-8")

    assert '"PROPOSAL_DEFENSE"' in bridge
    assert 'GraduationProposal.defense_result == "PASS"' in bridge
    assert 'code == "PROPOSAL_DEFENSE"' in bridge
    assert '"GUIDANCE_RECORD"' in bridge
    assert '"PLAGIARISM_REPORT"' in bridge
    assert 'row["v2RuleHash"]' in bridge
    assert 'row["v2PreservedHash"]' in bridge
    assert 'current_full != expected.get("fullHash")' in bridge
    assert "verify_batch_file_preview(int(batch_id), str(preview_token))" in bridge
    assert "snapshot_service.prepare_all(sid, user)" in bridge

    generate_execute = api.split("async batchGenerateArchive", 1)[1].split("async previewBatchFile", 1)[0]
    file_execute = api.split("async batchFileArchive", 1)[1].split("generateArchive", 1)[0]
    assert "/batch-generate/preview" not in generate_execute
    assert "/batch-file/preview" not in file_execute
    assert "consumePreview('GENERATE'" in generate_execute
    assert "consumePreview('FILE'" in file_execute
    assert "data?.failed" in file_execute
    assert "timeoutMs: 15000" not in file_execute
    assert "BATCH_FILE_TIMEOUT_MS = 8 * 60 * 1000" in api
    assert "timeoutMs: BATCH_FILE_TIMEOUT_MS" in file_execute
    assert "isUncertainBatchWrite(e)" in file_execute
    assert "reconcileBatchFile(" in file_execute


def test_u7_mysql_compat_batch_file_never_files_dirty_snapshot(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord, GraduationStudent
    from app.modules.graduation.services import graduation_archive_consistency as consistency
    from app.modules.graduation.services import graduation_archive_batch_consistency as batch

    _set_ctx()
    db = get_sessionmaker()()
    try:
        batch_row = _new_batch(db, "dirty-file", 1)
        dirty_no = f"U7DIRTY{uuid.uuid4().hex[:6].upper()}"
        student = GraduationStudent(
            tenant_id=TID, batch_id=batch_row.id, student_no=dirty_no, name="",
            class_name="软件01班", stage="FINAL_CHECK", record_status="ACTIVE",
        )
        db.add(student)
        db.flush()
        archive = GraduationArchiveRecord(
            tenant_id=TID, gd_student_id=student.id, status="SUBMITTED", checklist_json=[], missing_items=[],
        )
        db.add(archive)
        db.commit()
        batch_id, student_id, archive_id = int(batch_row.id), int(student.id), int(archive.id)
    finally:
        db.close()

    synthetic = {
        "mode": "FILE", "batchId": str(batch_id),
        "rows": [{
            "studentId": str(student_id), "studentVersion": 0,
            "archiveId": str(archive_id), "archiveVersion": 0, "archiveStatus": "SUBMITTED",
            "checklist": [], "missing": [], "dataAnomaly": True,
            "anomalyReasons": ["学生姓名缺失"], "openRisks": 0, "manifestHash": "clean-other-evidence",
        }],
    }
    monkeypatch.setattr(consistency, "_snapshot", lambda _db, _batch, _mode, lock=False: {
        "mode": synthetic["mode"], "batchId": synthetic["batchId"],
        "rows": [dict(synthetic["rows"][0])],
    })

    preview = batch.preview_batch_file(batch_id=batch_id, archive_batch_no="GDARCH-U7-DIRTY")
    assert preview["executableCount"] == 0
    assert {row["reason"] for row in preview["skipReasons"]} == {"dirty_data"}
    result = batch.batch_file(
        archive_batch_no="GDARCH-U7-DIRTY", batch_id=batch_id, preview_token=preview["previewToken"],
    )
    assert result["filed"] == 0
    assert result["dirtySkipped"] == 1

    verify = get_sessionmaker()()
    try:
        archive = verify.get(GraduationArchiveRecord, archive_id)
        student = verify.get(GraduationStudent, student_id)
        assert archive.status == "SUBMITTED"
        assert student.stage != "ARCHIVED"
    finally:
        verify.close()
        _clear_ctx()


def test_u7_mysql_batch_preview_600_students_has_constant_select_budget(db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import GraduationBatch, GraduationStudent
    from app.modules.graduation.services.graduation_archive_batch_scale import build_snapshot

    _set_ctx()
    db = get_sessionmaker()()
    try:
        batch = _new_batch(db, "scale", 600)
        prefix = uuid.uuid4().hex[:6].upper()
        db.add_all([
            GraduationStudent(
                tenant_id=TID, batch_id=batch.id, student_no=f"U7{prefix}{idx:04d}", name=f"U7规模学生{idx:04d}",
                college_id="U7-COL-A" if idx <= 300 else "U7-COL-B",
                class_name=f"软件{(idx - 1) // 50 + 1:02d}班", stage="FINAL_CHECK", record_status="ACTIVE",
            ) for idx in range(1, 601)
        ])
        db.commit()
        batch_id = int(batch.id)
    finally:
        db.close()

    check = get_sessionmaker()()
    try:
        batch = check.get(GraduationBatch, batch_id)
        snapshot, selects = _count_selects(
            get_engine(), lambda: build_snapshot(check, batch, "GENERATE", lock=False),
        )
        assert len(snapshot["rows"]) == 600
        assert selects <= 17, f"batch preview SELECTs={selects}; must remain O(1) with V2 evidence"
    finally:
        check.close()
        _clear_ctx()


def test_u7_scale_snapshot_uses_sql_scope_not_full_tenant_materialization():
    root = Path(__file__).resolve().parents[2]
    text = (root / "backend/app/modules/graduation/services/graduation_archive_batch_scale.py").read_text(encoding="utf-8")
    assert "student_scope_select" in text
    assert "accessible_student_ids" not in text
    assert ".id.in_(scope)" in text
