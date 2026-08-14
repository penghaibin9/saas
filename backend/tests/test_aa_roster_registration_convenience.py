"""D2-U 注册便利性：人类可读候选、零写入预览、previewToken 强确认、canonical 批量注册。"""
from __future__ import annotations

from uuid import uuid4

from app.db.session import get_sessionmaker

TID = 1000000000000000001
OTHER_TID = 1000000000000000099
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name="school_admin01"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_candidates(db_mode):
    from app.models import Major, SchoolClass, StudentProfile

    suffix = uuid4().hex[:8]
    db = get_sessionmaker()()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"软件技术-{suffix}",
        code=f"D2U-{suffix}",
        status="ACTIVE",
    )
    db.add(major)
    db.flush()
    cls = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"软件{suffix}班",
        grade="2026",
        status="ACTIVE",
    )
    db.add(cls)
    db.flush()
    ready = StudentProfile(
        tenant_id=TID,
        student_no=f"D2U-A-{suffix}",
        real_name=f"批量注册甲{suffix}",
        college_id=major.college_id,
        major_id=major.id,
        class_id=cls.id,
        current_stage="ORIENTATION",
        student_status="PENDING_REGISTER",
        status="ACTIVE",
    )
    ineligible = StudentProfile(
        tenant_id=TID,
        student_no=f"D2U-B-{suffix}",
        real_name=f"批量注册乙{suffix}",
        college_id=major.college_id,
        major_id=major.id,
        class_id=cls.id,
        current_stage="ORIENTATION",
        student_status="PENDING_REGISTER",
        status="ACTIVE",
    )
    foreign = StudentProfile(
        tenant_id=OTHER_TID,
        student_no=f"D2U-X-{suffix}",
        real_name=f"别校学生{suffix}",
        current_stage="ORIENTATION",
        student_status="PENDING_REGISTER",
        status="ACTIVE",
    )
    db.add_all([ready, ineligible, foreign])
    db.flush()
    out = {
        "ready": ready.id,
        "ineligible": ineligible.id,
        "foreign": foreign.id,
        "classId": cls.id,
        "className": cls.class_name,
        "majorName": major.major_name,
    }
    db.commit()
    db.close()
    return out


def _open_batch(client, headers):
    suffix = uuid4().hex[:8]
    response = client.post(f"{BASE}/registration-batches", headers=headers, json={
        "batchName": f"D2U批量注册-{suffix}",
        "registerType": "ENROLL",
        "open": True,
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


def test_d2u_candidates_are_human_readable_and_hide_internal_org_ids(client, db_mode):
    ids = _seed_candidates(db_mode)
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)

    response = client.get(
        f"{BASE}/registration-batches/{batch_id}/registration-candidates",
        headers=headers,
        params={"page": 1, "pageSize": 200},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["data"]["items"]
    row = next(x for x in rows if x["studentId"] == str(ids["ready"]))
    assert row["className"] == ids["className"]
    assert row["majorName"] == ids["majorName"]
    assert row["currentStatus"] == "PENDING_REGISTER"
    assert row["currentStatusLabel"]
    assert "资格" in row["eligibilityExplanation"]
    assert "classId" not in row
    assert "majorId" not in row


def test_d2u_preview_zero_write_cross_tenant_fail_closed_and_confirm_requires_preview_token(client, db_mode):
    from app.models import AaRegistration, AaStatusChange, StudentProfile, StudentStageEvent

    ids = _seed_candidates(db_mode)
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)

    verify = client.post(
        f"{BASE}/registration-batches/{batch_id}/eligibility/{ids['ineligible']}/verify",
        headers=headers,
        json={"result": "INELIGIBLE", "note": "材料核验未通过", "exceptionType": "MATERIAL_MISSING"},
    )
    assert verify.status_code == 200, verify.text

    db = get_sessionmaker()()
    before = db.query(AaRegistration).filter_by(
        tenant_id=TID, batch_id=int(batch_id), student_id=ids["ready"]
    ).count()
    db.close()
    assert before == 0

    preview = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=headers,
        json={"studentIds": [ids["ready"], ids["ineligible"], ids["foreign"]]},
    )
    assert preview.status_code == 200, preview.text
    pdata = preview.json()["data"]
    assert pdata["selected"] == 3 and pdata["ready"] == 1 and pdata["blocked"] == 2
    assert pdata["previewToken"] and pdata["previewExpiresIn"] > 0
    by_id = {x["studentId"]: x for x in pdata["items"]}
    assert by_id[str(ids["ready"])]["status"] == "READY"
    assert by_id[str(ids["ineligible"])]["status"] == "BLOCKED"
    assert by_id[str(ids["ineligible"])]["code"] == "INELIGIBLE"
    foreign = by_id[str(ids["foreign"])]
    assert foreign["status"] == "BLOCKED" and foreign["code"] == "NOT_AVAILABLE"
    assert "realName" not in foreign and "studentNo" not in foreign
    assert "别校" not in str(foreign)

    db = get_sessionmaker()()
    after = db.query(AaRegistration).filter_by(
        tenant_id=TID, batch_id=int(batch_id), student_id=ids["ready"]
    ).count()
    db.close()
    assert after == 0, "preview must not create a registration row"

    # 不能绕过 preview：confirm DTO 不再接受 studentIds 作为确认依据。
    bypass = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register",
        headers=headers,
        json={"studentIds": [ids["ready"]]},
    )
    assert bypass.status_code == 400

    applied = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register",
        headers=headers,
        json={"previewToken": pdata["previewToken"]},
    )
    assert applied.status_code == 200, applied.text
    result = applied.json()["data"]
    assert result["selected"] == 3 and result["succeeded"] == 1 and result["failed"] == 2
    final_by_id = {x["studentId"]: x for x in result["items"]}
    assert final_by_id[str(ids["ready"])]["ok"] is True
    assert final_by_id[str(ids["ineligible"])]["ok"] is False
    assert final_by_id[str(ids["ineligible"])]["code"] == "INELIGIBLE"
    assert final_by_id[str(ids["foreign"])]["ok"] is False

    db = get_sessionmaker()()
    student = db.get(StudentProfile, ids["ready"])
    assert student.student_status == "REGISTERED"
    assert db.query(AaRegistration).filter_by(
        tenant_id=TID, batch_id=int(batch_id), student_id=ids["ready"], status="REGISTERED"
    ).count() == 1
    assert db.query(AaStatusChange).filter_by(
        student_id=ids["ready"], to_status="REGISTERED"
    ).count() == 1
    assert db.query(StudentStageEvent).filter_by(
        student_id=ids["ready"], to_stage="REGISTERED", source_module="academic-affairs"
    ).count() == 1
    db.close()

    # 成功写入后事实已变化，同一 previewToken 不得复用。
    reused = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register",
        headers=headers,
        json={"previewToken": pdata["previewToken"]},
    )
    assert reused.status_code == 409


def test_d2u_legacy_single_register_remains_compatible_and_invalidates_old_preview(client, db_mode):
    ids = _seed_candidates(db_mode)
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)

    preview = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=headers,
        json={"studentIds": [ids["ready"]]},
    )
    assert preview.status_code == 200, preview.text
    token = preview.json()["data"]["previewToken"]

    # 历史单笔接口不删除、不改路径，继续复用 canonical 注册链。
    legacy = client.post(
        f"{BASE}/registration-batches/{batch_id}/register",
        headers=headers,
        json={"studentId": str(ids["ready"])},
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["data"]["studentStatus"] == "REGISTERED"

    # preview 后名单事实变化，旧 token fail closed。
    stale = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register",
        headers=headers,
        json={"previewToken": token},
    )
    assert stale.status_code == 409


def test_d2u_eligibility_adds_class_name_but_keeps_class_id_for_api_compat(client, db_mode):
    ids = _seed_candidates(db_mode)
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)

    response = client.get(
        f"{BASE}/registration-batches/{batch_id}/eligibility",
        headers=headers,
        params={"page": 1, "pageSize": 200},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["data"]["items"]
    row = next(x for x in rows if x["studentId"] == str(ids["ready"]))
    assert row["className"] == ids["className"]
    assert row["classId"] == str(ids["classId"])


def test_d2u_bulk_cap_and_student_permission_fail_closed(client, db_mode):
    admin = _hdr(client)
    batch_id = _open_batch(client, admin)

    too_many = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=admin,
        json={"studentIds": list(range(1, 102))},
    )
    assert too_many.status_code == 400

    student = _hdr(client, "student01")
    assert client.get(
        f"{BASE}/registration-batches/{batch_id}/registration-candidates",
        headers=student,
    ).status_code == 403
    assert client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=student,
        json={"studentIds": [1]},
    ).status_code == 403
    assert client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register",
        headers=student,
        json={"previewToken": "x" * 40},
    ).status_code == 403
