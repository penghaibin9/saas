"""D2-U dataScope 封域：点名 STUDENT 范围必须精确到人，不能借班级反推放大。"""
from __future__ import annotations

from uuid import uuid4

from app.db.session import get_sessionmaker

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_same_class(db_mode):
    del db_mode
    from app.models import Major, SchoolClass, StudentProfile

    suffix = uuid4().hex[:8]
    db = get_sessionmaker()()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"点名范围专业-{suffix}",
        code=f"D2S-{suffix}",
        status="ACTIVE",
    )
    db.add(major)
    db.flush()
    klass = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"点名范围{suffix}班",
        grade="2026",
        status="ACTIVE",
    )
    db.add(klass)
    db.flush()
    allowed = StudentProfile(
        tenant_id=TID,
        student_no=f"D2S-A-{suffix}",
        real_name=f"点名学生甲{suffix}",
        college_id=major.college_id,
        major_id=major.id,
        class_id=klass.id,
        current_stage="ORIENTATION",
        student_status="PENDING_REGISTER",
        status="ACTIVE",
    )
    neighbor = StudentProfile(
        tenant_id=TID,
        student_no=f"D2S-B-{suffix}",
        real_name=f"同班未授权乙{suffix}",
        college_id=major.college_id,
        major_id=major.id,
        class_id=klass.id,
        current_stage="ORIENTATION",
        student_status="PENDING_REGISTER",
        status="ACTIVE",
    )
    db.add_all([allowed, neighbor])
    db.flush()
    result = {
        "allowed": allowed.id,
        "neighbor": neighbor.id,
        "neighborNo": neighbor.student_no,
        "classId": klass.id,
    }
    db.commit()
    db.close()
    return result


def _open_batch(client, headers):
    response = client.post(
        f"{BASE}/registration-batches",
        headers=headers,
        json={
            "batchName": f"D2U点名范围-{uuid4().hex[:8]}",
            "registerType": "ENROLL",
            "open": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


class _PointStudentScope:
    scope_type = "STUDENT"

    def __init__(self, student_id, class_id):
        self.student_ids = {int(student_id)}
        self.psychology_student_ids = set()
        self._class_id = int(class_id)

    def allowed_class_ids(self, _db):
        # 统一上下文历史 helper 会把点名学生反推成所在班级；D2-U 不能拿这个结果当精确范围。
        return {self._class_id}


def test_d2u_student_scope_does_not_expand_to_whole_class(client, db_mode, monkeypatch):
    from app.modules.academic_affairs.services import roster_registration_convenience_service as convenience

    ids = _seed_same_class(db_mode)
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)
    point_scope = _PointStudentScope(ids["allowed"], ids["classId"])
    monkeypatch.setattr(convenience, "build_affairs_context", lambda _user, _db=None: point_scope)

    candidates = client.get(
        f"{BASE}/registration-batches/{batch_id}/registration-candidates",
        headers=headers,
        params={"page": 1, "pageSize": 20},
    )
    assert candidates.status_code == 200, candidates.text
    cdata = candidates.json()["data"]
    assert cdata["total"] == 1
    assert [row["studentId"] for row in cdata["items"]] == [str(ids["allowed"])]

    preview = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=headers,
        json={"studentIds": [ids["allowed"], ids["neighbor"]]},
    )
    assert preview.status_code == 200, preview.text
    pdata = preview.json()["data"]
    assert pdata["selected"] == 2
    assert pdata["ready"] == 1
    assert pdata["blocked"] == 1
    by_id = {row["studentId"]: row for row in pdata["items"]}
    assert by_id[str(ids["allowed"])]["status"] == "READY"
    blocked = by_id[str(ids["neighbor"])]
    assert blocked["status"] == "BLOCKED"
    assert blocked["code"] == "NOT_AVAILABLE"
    assert "realName" not in blocked and "studentNo" not in blocked
    assert ids["neighborNo"] not in str(blocked)
