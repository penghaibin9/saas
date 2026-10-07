"""Academic D-W0 graduation decision contract.

The ordinary final path must only consume a formal SYSTEM_PASSED immutable run.
A review note is audit context, never an override authority.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


@pytest.mark.parametrize("raw,expected", [
    (1, 1), ("1", 1), ("db-1", 1),
    ("1000000000000000001", 1000000000000000001),
    (None, None), ("", None), ("u_school_admin01", None),
    ("db-invalid", None), ("db-1-extra", None), ("-1", None),
    ("db-0", None), (0, None),
])
def test_graduation_actor_id_uses_trusted_numeric_identity(raw, expected):
    from app.core.context import get_current_user_ctx, set_current_user
    from app.modules.academic_affairs.services.academic_affairs_graduation_immutable_service import _actor_id

    previous = get_current_user_ctx()
    try:
        set_current_user({"userId": raw, "loginName": "school_admin01"})
        assert _actor_id() == expected
    finally:
        set_current_user(previous)


def _hdr(client, login_name="school_admin01"):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _complete_pass_items():
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy

    required = set(legacy._BLOCKING_UNKNOWN_ITEMS) | {"ARCHIVE"}
    items = [{"item": code, "result": "PASS"} for code in sorted(required)]
    items.extend([
        {"item": "EMPLOYMENT", "result": "UNKNOWN"},
        {"item": "FEE", "result": "UNKNOWN"},
    ])
    return items


def _pass_snapshot(*, evaluated_at: str, fact_version: int = 1, evidence_hashes=None):
    return {
        "evaluatorVersion": "STAGE_C3_V1",
        "evaluatedAt": evaluated_at,
        "studentId": "123",
        "academicFact": {
            "id": "88",
            "versionNo": fact_version,
            "validFrom": "2026-02-01T00:00:00",
            "studentStatus": "REGISTERED",
            "collegeId": "1",
            "majorId": "2",
            "classId": "3",
            "grade": "2023",
        },
        "programId": "9",
        "evidenceHashes": list(evidence_hashes or ["ev-a", "ev-b"]),
    }


def _evaluate_current(db, student):
    from app.core.context import get_tenant, set_tenant
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable

    previous = get_tenant()
    set_tenant(TID)
    try:
        return immutable.evaluate_student(db, student)
    finally:
        set_tenant(previous)


def _seed_formal_result(
    *,
    suffix: str,
    overall: str,
    review_note: str,
    complete_evidence: bool = True,
    result_status: str = "ACADEMIC_REVIEW",
    college_id: int | None = None,
    current_basis: bool = False,
):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaGraduationAuditBatch,
        AaGraduationAuditResult,
        GraduationEvaluationRun,
        StudentProfile,
    )

    db = get_sessionmaker()()
    try:
        from tests.support_graduation_review_identity import seed_graduation_review_identity
        college = seed_graduation_review_identity(db)
        student = StudentProfile(
            tenant_id=TID,
            student_no=f"DW0{suffix}",
            real_name=f"D-W0学生{suffix}",
            college_id=college_id if college_id is not None else college.id,
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
        if overall == "SYSTEM_PASSED" and complete_evidence:
            items = _complete_pass_items()
        else:
            items = [{"item": "STATUS", "result": "PASS" if overall == "SYSTEM_PASSED" else "UNKNOWN"}]
        result = AaGraduationAuditResult(
            tenant_id=TID,
            batch_id=batch.id,
            student_id=student.id,
            item_results_json=json.dumps(items, ensure_ascii=False),
            overall=overall,
            review_note=review_note,
            rerun_count=1,
            status=result_status,
        )
        db.add(result)
        db.flush()
        evaluated = _evaluate_current(db, student) if current_basis else None
        snapshot = evaluated["inputSnapshot"] if evaluated else {"contract": "D-W0", "suffix": suffix}
        run = GraduationEvaluationRun(
            tenant_id=TID,
            batch_id=batch.id,
            result_id=result.id,
            student_id=student.id,
            run_no=1,
            program_id=None,
            input_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
            input_hash=evaluated["inputHash"] if evaluated else (suffix.lower()[0] if suffix else "a") * 64,
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


def _result_status(result_id: int):
    from app.db.session import get_sessionmaker
    from app.models import AaGraduationAuditResult

    db = get_sessionmaker()()
    try:
        return db.get(AaGraduationAuditResult, result_id).status
    finally:
        db.close()


def test_d_w0_only_advisory_unknowns_can_pass_but_archive_unknown_blocks(db_mode):
    """EMPLOYMENT/FEE remain advisory; ARCHIVE UNKNOWN stays Stage C3 fail-closed."""
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable

    items = _complete_pass_items()
    assert immutable._strict_overall(items) == "SYSTEM_PASSED"

    archive_unknown = [
        {**row, "result": "UNKNOWN"} if row["item"] == "ARCHIVE" else row
        for row in items
    ]
    credit_unknown = [
        {**row, "result": "UNKNOWN"} if row["item"] == "CREDIT" else row
        for row in items
    ]
    archive_fail = [
        {**row, "result": "FAIL"} if row["item"] == "ARCHIVE" else row
        for row in items
    ]
    assert immutable._strict_overall(archive_unknown) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(credit_unknown) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(archive_fail) == "SYSTEM_ABNORMAL"
    assert immutable._strict_overall(["malformed-item"]) == "SYSTEM_ABNORMAL"


def test_d_w0_missing_required_evidence_item_cannot_pass(db_mode):
    """A provider omission is UNKNOWN-equivalent; absence must never become SYSTEM_PASSED."""
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable

    complete = _complete_pass_items()
    required = set(legacy._BLOCKING_UNKNOWN_ITEMS) | {"ARCHIVE"}
    assert immutable._strict_overall(complete) == "SYSTEM_PASSED"
    for missing in sorted(required):
        partial = [row for row in complete if row["item"] != missing]
        assert immutable._strict_overall(partial) == "SYSTEM_ABNORMAL", missing


def test_d_w0_approved_run_stability_ignores_clock_but_detects_evidence_change(db_mode):
    """Repeated precheck must not reset approval for time alone; real evidence changes must."""
    from app.modules.academic_affairs.services import academic_affairs_graduation_immutable_service as immutable

    items = _complete_pass_items()
    run = SimpleNamespace(
        overall="SYSTEM_PASSED",
        item_results_json=json.dumps(items, ensure_ascii=False),
        input_snapshot_json=json.dumps(
            _pass_snapshot(evaluated_at="2026-08-16T01:00:00"),
            ensure_ascii=False,
        ),
    )
    result = SimpleNamespace(overall="SYSTEM_PASSED")
    evaluated = {
        "overall": "SYSTEM_PASSED",
        "items": items,
        "inputSnapshot": _pass_snapshot(evaluated_at="2026-08-16T02:00:00"),
    }
    assert immutable._approved_run_is_current(run, result, evaluated) is True

    changed_evidence = {
        **evaluated,
        "inputSnapshot": _pass_snapshot(
            evaluated_at="2026-08-16T02:00:00",
            evidence_hashes=["ev-a", "ev-changed"],
        ),
    }
    assert immutable._approved_run_is_current(run, result, changed_evidence) is False

    changed_fact = {
        **evaluated,
        "inputSnapshot": _pass_snapshot(
            evaluated_at="2026-08-16T02:00:00",
            fact_version=2,
        ),
    }
    assert immutable._approved_run_is_current(run, result, changed_fact) is False


def test_d_w0_abnormal_cannot_advance_to_academic_review(client, db_mode):
    student_id, result_id, _ = _seed_formal_result(
        suffix="E",
        overall="SYSTEM_ABNORMAL",
        review_note="",
        result_status="SYSTEM_ABNORMAL",
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/college-review",
        headers=_hdr(client, "college_admin01"),
        json={"action": "APPROVE", "note": "学院已核验但系统阻断尚未治理"},
    )
    assert resp.status_code == 409, resp.text
    assert _result_status(result_id) == "SYSTEM_ABNORMAL"

    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        assert db.get(StudentProfile, student_id).student_status == "REGISTERED"
    finally:
        db.close()


def test_d_w0_complete_pass_can_advance_to_academic_review(client, db_mode):
    _, result_id, _ = _seed_formal_result(
        suffix="F",
        overall="SYSTEM_PASSED",
        review_note="",
        result_status="SYSTEM_PASSED",
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/college-review",
        headers=_hdr(client, "college_admin01"),
        json={"action": "APPROVE", "note": "学院初审确认通过"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "ACADEMIC_REVIEW"
    assert _result_status(result_id) == "ACADEMIC_REVIEW"


def test_d_w0_incomplete_pass_cannot_advance_to_academic_review(client, db_mode):
    _, result_id, _ = _seed_formal_result(
        suffix="G",
        overall="SYSTEM_PASSED",
        review_note="",
        complete_evidence=False,
        result_status="SYSTEM_PASSED",
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/college-review",
        headers=_hdr(client, "college_admin01"),
        json={"action": "APPROVE", "note": "学院初审确认通过"},
    )
    assert resp.status_code == 409, resp.text
    assert _result_status(result_id) == "SYSTEM_PASSED"


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


def test_d_w0_system_passed_run_with_missing_required_evidence_cannot_graduate(client, db_mode):
    student_id, result_id, _ = _seed_formal_result(
        suffix="D",
        overall="SYSTEM_PASSED",
        review_note="旧正式Run投影为通过但证据集合不完整",
        complete_evidence=False,
    )
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/final",
        headers=_hdr(client),
        json={"conclusion": "GRADUATED", "confirm": True},
    )
    assert resp.status_code == 409, resp.text
    assert "证据" in str(resp.json().get("message") or "")
    assert _decision_rows(result_id) == []

    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        assert db.get(StudentProfile, student_id).student_status == "REGISTERED"
    finally:
        db.close()


@pytest.mark.parametrize("real_actor", [False, True], ids=["http", "db_actor"])
def test_d_w0_system_passed_run_can_form_normal_decision(client, db_mode, monkeypatch, real_actor):
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy
    if real_actor:
        from app.db.session import get_sessionmaker
        from tests.support_grade_review_identity import _ensure_account

        with get_sessionmaker()() as db:
            actor = _ensure_account(db, "school_admin01")
            actor_id = int(actor.id)
            assert actor_id > 0
            db.commit()
    # 隔离跨域供数；身份事实解析、快照比较、真实权限及终态命令均不替换。
    monkeypatch.setattr(legacy, "_run_items", lambda db, student: _complete_pass_items())
    student_id, result_id, run_id = _seed_formal_result(
        suffix="C",
        overall="SYSTEM_PASSED",
        review_note="学院初审通过",
        current_basis=True,
    )
    if real_actor:
        from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
        from app.modules.academic_affairs.services.academic_affairs_graduation_immutable_service import academic_final

        user = {"userId": f"db-{actor_id}", "loginName": "school_admin01", "realName": "陈校",
                "userType": "SCHOOL_ADMIN", "currentRoleCode": "SCHOOL_ADMIN", "tenantId": str(TID)}
        previous_user, previous_tenant = get_current_user_ctx(), get_tenant()
        try:
            set_current_user(user)
            set_tenant(TID)
            result = academic_final(result_id, user, "GRADUATED", confirm=True)
            assert result["conclusion"] == "GRADUATED"
        finally:
            set_current_user(previous_user)
            set_tenant(previous_tenant)
    else:
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
    if real_actor:
        assert decisions[0].decision_by == actor_id
        assert decisions[0].created_by == actor_id

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


def _assert_final_has_no_writes(student_id, result_id):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, StudentProfile

    assert _decision_rows(result_id) == []
    assert _result_status(result_id) == "ACADEMIC_REVIEW"
    with get_sessionmaker()() as db:
        assert db.get(StudentProfile, student_id).student_status == "REGISTERED"
        assert db.query(AffairsAuditTrail).filter(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_id == result_id,
            AffairsAuditTrail.action == "ACADEMIC_FINAL_IMMUTABLE",
        ).count() == 0


def test_d_w0_changed_academic_fact_rejects_final_even_when_still_passed(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import append_student_academic_fact

    monkeypatch.setattr(legacy, "_run_items", lambda db, student: _complete_pass_items())
    student_id, result_id, _ = _seed_formal_result(
        suffix="H", overall="SYSTEM_PASSED", review_note="学院已初审", current_basis=True,
    )
    with get_sessionmaker()() as db:
        append_student_academic_fact(
            db, student_id, grade="2025", source_type="CORRECTION", tenant_id=TID,
        )
        db.commit()
        assert _evaluate_current(db, db.get(StudentProfile, student_id))["overall"] == "SYSTEM_PASSED"
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/final", headers=_hdr(client),
        json={"conclusion": "GRADUATED", "confirm": True},
    )
    assert resp.status_code == 409, resp.text
    assert "重新预审和学院初审" in resp.json()["message"]
    _assert_final_has_no_writes(student_id, result_id)


def test_d_w0_changed_source_evidence_rejects_final_even_when_still_passed(client, db_mode, monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as legacy

    evidence = {"hash": "approved-source-version-1"}
    def provider(db, student):
        return [{**row, "evidenceHash": evidence["hash"]} for row in _complete_pass_items()]

    monkeypatch.setattr(legacy, "_run_items", provider)
    student_id, result_id, _ = _seed_formal_result(
        suffix="I", overall="SYSTEM_PASSED", review_note="学院已初审", current_basis=True,
    )
    evidence["hash"] = "corrected-source-version-2"
    resp = client.post(
        f"{BASE}/graduation-results/{result_id}/final", headers=_hdr(client),
        json={"conclusion": "GRADUATED", "confirm": True},
    )
    assert resp.status_code == 409, resp.text
    assert "重新预审和学院初审" in resp.json()["message"]
    _assert_final_has_no_writes(student_id, result_id)
