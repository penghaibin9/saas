"""教务中心·学籍管理 Tier1 R3：学籍信息更正 · 端到端（真实 DB 模式）。

C1 更正审核通过→主档字段同步+审计留痕；C2 驳回需理由≥5字，驳回后主档不变；
C3 同学生同字段在途重复409；C4 更正字段范围排除学籍状态（单一写入口红线，400）；
C5 无权限角色（辅导员）发起更正403；C6 性别非法取值400。
（HTTP 状态口径对齐 app/core/exceptions.py CODE_HTTP：VALIDATION_ERROR→400，非 422，
 与本仓库 test_aa_course.py/test_aa_calendar_period.py 等既有校验失败用例一致。）
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="AA100", real_name="更正甲", gender="男",
                       id_card_encrypted="110101200001011234", grade="2021", class_id=a.id,
                       current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush()
    ids = {"s": s.id}
    db.commit()
    db.close()
    return ids


def _apply(client, hdr, sid, field_key, new_value, reason="数据录入错误据实更正"):
    return client.post(f"{BASE}/roster/corrections", headers=hdr,
                       json={"studentId": str(sid), "fieldKey": field_key,
                            "newValue": new_value, "reason": reason})


def test_c1_approve_syncs_profile_and_audits(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "REAL_NAME", "更正乙")
    assert r.status_code == 200, r.text
    cid = r.json()["data"]["correctionId"]
    rv = client.post(f"{BASE}/roster/corrections/{cid}/review", headers=hdr,
                     json={"action": "APPROVE"})
    assert rv.status_code == 200, rv.text
    assert rv.json()["data"]["status"] == "APPROVED"
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.real_name == "更正乙"  # 主档已同步
    cnt = db.query(AffairsAuditTrail).filter_by(
        biz_type="AA_STUDENT_CORRECTION", biz_id=int(cid), action="APPROVE").count()
    assert cnt == 1  # 审计留痕
    db.close()


def test_c2_reject_requires_reason_and_keeps_profile(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "GRADE", "2022")
    cid = r.json()["data"]["correctionId"]
    short = client.post(f"{BASE}/roster/corrections/{cid}/review", headers=hdr,
                        json={"action": "REJECT", "note": "太短"})
    assert short.status_code == 400
    ok = client.post(f"{BASE}/roster/corrections/{cid}/review", headers=hdr,
                     json={"action": "REJECT", "note": "材料不足，退回补充证明"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "REJECTED"
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = db.get(StudentProfile, ids["s"])
    assert s.grade == "2021"  # 驳回不改主档
    db.close()


def test_c3_duplicate_pending_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r1 = _apply(client, hdr, ids["s"], "STUDENT_NO", "AA200")
    assert r1.status_code == 200
    r2 = _apply(client, hdr, ids["s"], "STUDENT_NO", "AA201")
    assert r2.status_code == 409


def test_c4_status_field_out_of_scope_400(client, db_mode):
    """学籍状态/组织归属不在更正范围内（必须走「学籍异动」单一入口），杜绝绕过 change_student_status。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "STUDENT_STATUS", "SUSPENDED")
    assert r.status_code == 400


def test_c5_counselor_no_permission_403(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "counselor01")
    r = _apply(client, hdr, ids["s"], "REAL_NAME", "越权改名")
    assert r.status_code == 403


def test_c6_gender_invalid_value_400(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["s"], "GENDER", "other")
    assert r.status_code == 400
