"""P4 §5.1 · 企业沟通记录：CRUD + 数据范围(导师本人学生) + 跨学生/学生越权 403 + 审计留痕。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship/communications"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER", "tid": "x",
        "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-s", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """企业 + 两学生实习记录（advisor=刘强/王芳）挂同一进行中批次。"""
    from app.db.session import get_sessionmaker
    from app.models import EmpCompany, InternshipBatch, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="沟通测试批次", batch_no="CM-BATCH-01",
            status="RUNNING", planned_count=10,
        )
        db.add(batch); db.flush()
        co = EmpCompany(tenant_id=TID, name="沟通测试企业")
        db.add(co); db.flush()
        ids = {"enterprise_id": co.id, "batch_id": batch.id}
        for no, name, adv, key in [("CM-A", "甲", "刘强", "a"), ("CM-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, batch_id=batch.id, advisor_name=adv,
                                 enterprise_name="沟通测试企业", position_name="实习生", status="ONBOARD")
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
        db.commit()
        return ids
    finally:
        db.close()


def _mk(ids, rec_key="rec_a", summary="电话沟通实习表现", ctype="PHONE"):
    return {"enterpriseId": str(ids["enterprise_id"]), "internshipId": str(ids[rec_key]),
            "communicationType": ctype, "summary": summary}


def _batch_q(ids):
    return {"batchId": str(ids["batch_id"])}


def test_list_requires_batch_id(client, db_mode):
    _seed(db_mode)
    miss = client.get(INT, headers=_admin(client)).json()
    assert miss["code"] != 0
    assert "batchId" in (miss.get("message") or "")


def test_create_requires_internship_id(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(INT, json={
        "enterpriseId": str(ids["enterprise_id"]), "summary": "无学生关联沟通",
    }, headers=_admin(client)).json()
    assert r["code"] != 0
    assert "internshipId" in (r.get("message") or "")


def test_create_and_list(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    r = client.post(INT, json=_mk(ids), headers=a)
    assert r.status_code == 200 and r.json()["data"]["status"] == "NORMAL"
    lst = client.get(INT, headers=a, params=_batch_q(ids)).json()["data"]
    assert lst["total"] == 1 and lst["items"][0]["summary"] == "电话沟通实习表现"


def test_summary_required(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(INT, json={"enterpriseId": str(ids["enterprise_id"]), "summary": "x"}, headers=_admin(client))
    assert r.status_code == 400 or r.json().get("code") not in (0, None)


def test_scope_mentor_sees_own_only(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    client.post(INT, json=_mk(ids, "rec_a", "甲沟通记录"), headers=a)
    client.post(INT, json=_mk(ids, "rec_b", "乙沟通记录"), headers=a)
    liu = client.get(INT, headers=_mentor("刘强"), params=_batch_q(ids)).json()["data"]
    assert liu["total"] == 1 and liu["items"][0]["summary"] == "甲沟通记录"
    assert client.get(INT, headers=a, params=_batch_q(ids)).json()["data"]["total"] == 2


def test_mentor_create_and_void_own(client, db_mode):
    ids = _seed(db_mode)
    liu = _mentor("刘强")
    cid = client.post(INT, json=_mk(ids, "rec_a", "导师本人学生沟通"), headers=liu).json()["data"]["id"]
    assert client.post(f"{INT}/{cid}/void", json={"reason": "x"}, headers=liu).status_code == 400
    v = client.post(f"{INT}/{cid}/void", json={"reason": "记录有误重新登记"}, headers=liu)
    assert v.status_code == 200 and v.json()["data"]["status"] == "VOIDED"


def test_mentor_cross_student_403(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(INT, json=_mk(ids, "rec_b", "跨学生沟通"), headers=_mentor("刘强"))
    assert r.status_code == 403


def test_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    assert client.get(INT, headers=_student(), params=_batch_q(ids)).status_code == 403


def test_detail_and_audit(client, db_mode):
    ids = _seed(db_mode)
    a = _admin(client)
    cid = client.post(INT, json=_mk(ids, "rec_a", "沟通详情测试"), headers=a).json()["data"]["id"]
    d = client.get(f"{INT}/{cid}", headers=a).json()["data"]
    assert d["summary"] == "沟通详情测试"
    assert any(t["action"] == "CREATE" for t in d["auditTrail"])
