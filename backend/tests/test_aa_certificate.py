"""毕业/结业证书管理（/academic-affairs/graduation-certificates*）端点测试。

覆盖：按终审结论批量生成（GRADUATED→毕业证/COMPLETED→结业证/DELAYED 不生成）、
编号规则（前缀+年份+5位流水连续且唯一）、幂等重跑跳过、发放登记、作废（原因≥5字、编号不回收）、
学生越权 403。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """审核批次 + 3 个终审结论：甲 GRADUATED / 乙 COMPLETED / 丙 DELAYED。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaGraduationAuditBatch, AaGraduationAuditResult, College, Major,
                            SchoolClass, StudentProfile)
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2201", grade="2022", status="ACTIVE")
    db.add(klass); db.flush()
    b = AaGraduationAuditBatch(tenant_id=TID, batch_name="2022届终审", grade_year="2022", status="FINALIZED")
    db.add(b); db.flush()
    sids = {}
    for no, name, concl in (("ZS2201", "证甲", "GRADUATED"), ("ZS2202", "证乙", "COMPLETED"),
                            ("ZS2203", "证丙", "DELAYED")):
        p = StudentProfile(tenant_id=TID, student_no=no, real_name=name, college_id=col.id,
                           major_id=major.id, class_id=klass.id, grade="2022",
                           student_status="NORMAL", status="ACTIVE")
        db.add(p); db.flush()
        db.add(AaGraduationAuditResult(tenant_id=TID, batch_id=b.id, student_id=p.id,
                                       overall="SYSTEM_PASSED", conclusion=concl, status="GRADUATED"))
        sids[no] = p.id
    db.commit()
    ids = {"batch": b.id, "sids": sids}
    db.close()
    return ids


_GEN = {"prefix": "13899", "year": "2025", "eRegPrefix": "E", "issueDate": "2025-06-30"}


def test_generate_by_conclusion(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate",
                    headers=admin, json=_GEN)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["created"] == 2, "DELAYED 不得生成证书"
    d = client.get(f"{BASE}/graduation-certificates", headers=admin).json()["data"]
    assert d["total"] == 2
    by = {c["studentNo"]: c for c in d["items"]}
    assert by["ZS2201"]["certType"] == "GRADUATION"
    assert by["ZS2202"]["certType"] == "COMPLETION"
    nos = sorted(c["certNo"] for c in d["items"])
    assert nos == ["13899202500001", "13899202500002"], f"编号必须前缀+年份+5位连续流水: {nos}"
    assert all(c["eRegNo"] == "E" + c["certNo"] for c in d["items"])


def test_generate_idempotent(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate", headers=admin, json=_GEN)
    r2 = client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate",
                     headers=admin, json=_GEN).json()["data"]
    assert r2["created"] == 0 and r2["skipped"] == 2, "重跑不得重复发证"


def test_issue_and_void_no_number_recycle(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate", headers=admin, json=_GEN)
    items = client.get(f"{BASE}/graduation-certificates", headers=admin).json()["data"]["items"]
    cid = items[0]["certificateId"]
    assert client.post(f"{BASE}/graduation-certificates/{cid}/issue", headers=admin).status_code == 200
    # 已发放再发放 → 409
    assert client.post(f"{BASE}/graduation-certificates/{cid}/issue", headers=admin).status_code == 409
    # 作废：原因太短 400；合规通过
    assert client.post(f"{BASE}/graduation-certificates/{cid}/void", headers=admin,
                       json={"reason": "短"}).status_code in (400, 422)
    assert client.post(f"{BASE}/graduation-certificates/{cid}/void", headers=admin,
                       json={"reason": "证书打印信息有误需补发"}).status_code == 200
    # 作废后重新生成：该生补发新证，编号续号不回收
    r = client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate",
                    headers=admin, json=_GEN).json()["data"]
    assert r["created"] == 1
    d = client.get(f"{BASE}/graduation-certificates", headers=admin).json()["data"]
    all_nos = [c["certNo"] for c in d["items"]]
    assert len(all_nos) == len(set(all_nos)) == 3, "编号绝不重号、绝不回收"
    assert "13899202500003" in all_nos


def test_missing_prefix_rejected(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate",
                    headers=admin, json={"prefix": "", "year": "2025"})
    assert r.status_code in (400, 422), r.text


def test_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(f"{BASE}/graduation-batches/{ids['batch']}/certificates/generate",
                    headers=_stu_token("证甲", "ZS2201"), json=_GEN)
    assert r.status_code == 403, r.text
