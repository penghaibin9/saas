"""Academic D-W0 graduation decision contract.

The ordinary final path must only consume a formal SYSTEM_PASSED immutable run.
A review note is audit context, never an override authority.
"""
from __future__ import annotations

import json

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_formal_result(*, suffix: str, overall: str, review_note: str):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaGraduationAuditBatch,
        AaGraduationAuditResult,
        GraduationEvaluationRun,
        StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TID,
            student_no=f"DW0{suffix}",
            real_name=f"D-W0学生{suffix}",
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        batch = AaGraduationAuditBatch(
            tenant_id=TID,
            batch_name=f"D-W0正式终审合同-{suffix}",
            grade_year="2026",
            status="PRECHECKED",
        )
        db.add(batch)
        db.flush()
        items = [{"item": "STATUS", "result": "PASS" if overall == "SYSTEM_PASSED" else "UNKNOWN"}]
        result = AaGraduationAuditResult(
            tenant_id=TID,
            batch_id=batch.id,
            student_id=student.id,
            item_results_json=json.dumps(items, ensure_ascii=False),
            overall=overall,
            review_note=review_note,
            rerun_count=1,
            status="ACADEMIC_REVIEW",
        )
        db.add(result)
        db.flush()
        run = GraduationEvaluationRun(
            tenant_id=TID,
            batch_id=batch.id,
            result_id=result.id,
            student_id=student.id,
            run_no=1,
            program_id=None,
            input_snapshot_json=json.dumps({"contract": "D-W0", "suffix": suffix}, ensure_ascii=False),
            input_hash=(suffix.lower()[0] if suffix else "a") * 64,
            item_results_json=json.dumps(items, ensure_ascii=False),
            overall=overall,
            evaluator_version="STAGE_C3_V1",
        )
        db.add(run)
        db.commit()
        return student.id, result.id, run.id
    finally:
        db.close()


def _decision_rows(result_id: int):
    from app.db.session import get_sessionmaker
    from app.models import GraduationDecisionFact

    db = get_sessionmaker()()
    try:
        return db.query(GraduationDecisionFact).filter(
            GraduationDecisionFact.tenant_id == TID,
            GraduationDecisionFact.result_id == result_id,
        ).all()
    finally:
        db.close()


def test_d_w0_only_advisory_unknowns_can_pass_but_archive_unknown_blocks(db_mode):
    """EMPLOYMENT/FEE remain advisory; ARCHIVE UNKNOWN stays Stage C3 fail-closed."""
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable

    items = [
        {"item": code, "result": "PASS"}
        for code in sorted(legacy._BLOCKING_UNKNOWN_ITEMS)
    ]
    items.extend([
        {"item": "EMPLOYMENT", "result": "UNKNOWN"},
        {"item": "FEE", "result": "UNKNOWN"},
    ])
    assert immutable._strict_overall(items) == "SYSTEM_PASSED"
    assert immutable._strict_overall(items + [{"item": "ARCHIVE", "result": "UNKNOWN"}]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(items + [{"item": "CREDIT", "result": "UNKNOWN"}]) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(items + [{"item": "ARCHIVE", "result": "FAIL"}]) == "SYSTEM_ABNORMAL"


def test_d_w0_missing_required_evidence_item_cannot_pass(db_mode):
    """A provider omission is UNKNOWN-equivalent; absence must never become SYSTEM_PASSED."""
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable

    required = set(legacy._BLOCKING_UNKNOWN_ITEMS) | {"ARCHIVE"}
    complete = [{"item": code, "result": "PASS"} for code in sorted(required)]
    complete.extend([
        {"item": "EMPLOYMENT", "result": "UNKNOWN"},
        {"item": "FEE", "result": "UNKNOWN"},
    ])
    assert immutable._strict_overall(complete) == "SYSTEM_PASSED"
    for missing in sorted(required):
        partial = [row for row in complete if row["item"] != missing]
        assert immutable._strict_overall(partial) == "SYSTEM_ABNORMAL", missing


def test_d_w0_abnormal_five_char_note_cannot_graduate(client, db_mode):
    student_id, result_id, _ = _seed_formal_result(
        suffix="A",
        overall="SYSTEM_ABNORMAL",
        review_note="人工复核说明足够五个字",
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/final",
        headers=_hdr(client),
        json={"conclusion": "GRADUATED", "confirm": True},
    )
    assert resp.status_code == 409, resp.text
    assert _decision_rows(result_id) == []

    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        assert db.get(StudentProfile, student_id).student_status == "REGISTERED"
    finally:
        db.close()


def test_d_w0_abnormal_500_char_note_still_cannot_graduate(client, db_mode):
    _, result_id, _ = _seed_formal_result(
        suffix="B",
        overall="SYSTEM_ABNORMAL",
        review_note="例外说明" * 125,
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/final",
        headers=_hdr(client),
        json={"conclusion": "GRADUATED", "confirm": True},
    )
    assert resp.status_code == 409, resp.text
    assert _decision_rows(result_id) == []


def test_d_w0_system_passed_run_can_form_normal_decision(client, db_mode):
    student_id, result_id, run_id = _seed_formal_result(
        suffix="C",
        overall="SYSTEM_PASSED",
        review_note="学院初审通过",
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/final",
        headers=_hdr(client),
        json={"conclusion": "GRADUATED", "confirm": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["conclusion"] == "GRADUATED"

    decisions = _decision_rows(result_id)
    assert len(decisions) == 1
    assert decisions[0].evaluation_run_id == run_id

    from app.db.session import get_sessionmaker
    from app.models import GraduationEvaluationRun, StudentProfile
    db = get_sessionmaker()()
    try:
        assert db.get(StudentProfile, student_id).student_status == "GRADUATED"
        run = db.get(GraduationEvaluationRun, run_id)
        assert run.overall == "SYSTEM_PASSED"
        assert run.run_no == 1
    finally:
        db.close()
