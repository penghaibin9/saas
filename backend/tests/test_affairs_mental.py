"""13A-D 心理关注闭环 · 端到端（真实 DB 模式，强敏感红线）。

M1 转介→回访→关闭闭环；M2 危机升级接风险中枢+幂等；M3 列表仅摘要（明细遮蔽）；
M4 明细须原因+SENSITIVE_VIEW 审计；M5 SEC-1 mental-records 权限门禁(403/401)；
M6 SEC-2 学工处管理员无专项授权→拒绝；M7 PSY_STUDENT 逐生授权范围；M8 无自动诊断(事由人工必填)。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
CAMPUS = "/api/v1/campus-service"


def _hdr(client, login):
    d = client.post("/api/v1/auth/mock-login", json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="P001", real_name="心一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="P002", real_name="心二", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    # 心理老师 psych01 逐生授权 P001（不授权 P002）
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="psych01", teacher_name="心理·孙",
                               role_code="PSYCHOLOGY_TEACHER", scope_type="PSY_STUDENT",
                               ref_value="P001", status="ACTIVE"))
    db.commit()
    ids = {"sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _refer(client, hdr, sid, level="FOCUS", summary="学生近期情绪波动明显需持续关注"):
    return client.post(f"{BASE}/mental/referrals", headers=hdr, json={
        "studentId": str(sid), "level": level, "channel": "校内咨询",
        "reasonSummary": summary, "note": "涉密明细内容XYZ"})


def test_m1_referral_close_loop(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    ref = _refer(client, admin, ids["sa"]).json()["data"]
    assert ref["status"] == "REFERRED" and ref["level"] == "FOCUS"
    rid, ver = ref["referralId"], ref["version"]
    r2 = client.post(f"{BASE}/mental/referrals/{rid}/follow", headers=admin,
                     json={"content": "已电话回访，情绪稳定", "version": ver}).json()["data"]
    assert r2["status"] == "FOLLOWING" and r2["lastFollowTime"]
    r3 = client.post(f"{BASE}/mental/referrals/{rid}/close", headers=admin,
                     json={"conclusion": "评估稳定，结案观察", "version": r2["version"]}).json()["data"]
    assert r3["status"] == "CLOSED"


def test_m2_crisis_escalate_to_risk_hub_idempotent(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    ref = _refer(client, admin, ids["sa"]).json()["data"]
    rid, ver = ref["referralId"], ref["version"]
    r = client.post(f"{BASE}/mental/referrals/{rid}/escalate", headers=admin,
                    json={"content": "出现危机信号，立即升级", "version": ver}).json()["data"]
    assert r["status"] == "ESCALATED" and r["level"] == "CRISIS" and r["riskId"]
    risk_id = r["riskId"]
    # 幂等：再升级返回同一 riskId（不重复建风险）；仍须带 version
    r2 = client.post(f"{BASE}/mental/referrals/{rid}/escalate", headers=admin,
                     json={"content": "重复升级请求确认", "version": r["version"]}).json()["data"]
    assert r2["riskId"] == risk_id
    # 风险中枢已建 source=MENTAL·CRITICAL 记录
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord
    db = get_sessionmaker()()
    x = db.get(AffairsRiskRecord, int(risk_id))
    assert x and x.source == "MENTAL" and x.risk_level == "CRITICAL"
    db.close()


def test_m9_attention_level_crisis_overrides_focus(client, db_mode):
    """关注等级顺序 GENERAL < FOCUS < CRISIS，禁止字符串 max。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _refer(client, admin, ids["sa"], level="FOCUS")
    _refer(client, admin, ids["sa"], level="CRISIS", summary="出现危机信号需立即干预处置")
    _refer(client, admin, ids["sa"], level="GENERAL", summary="一般关注观察即可")
    s = client.get(f"{BASE}/mental/students/{ids['sa']}/summary", headers=admin).json()["data"]
    assert s["attentionLevel"] == "CRISIS"
    assert s["needAttention"] is True
    assert s["openReferralCount"] >= 3


def test_m3_list_summary_only_masked(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _refer(client, admin, ids["sa"])
    items = client.get(f"{BASE}/mental/list", headers=admin).json()["data"]["items"]
    assert items and all(it["noteMasked"] is True for it in items)
    assert all("涉密明细内容XYZ" not in it["note"] for it in items)


def test_m4_detail_reason_sensitive_view_audit(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _refer(client, admin, ids["sa"]).json()["data"]["referralId"]
    # 无原因 → 遮蔽
    d0 = client.get(f"{BASE}/mental/referrals/{rid}", headers=admin).json()["data"]
    assert d0["noteMasked"] is True and "涉密明细内容XYZ" not in d0["note"]
    # 原因≥5字 → 明文 + SENSITIVE_VIEW
    d1 = client.get(f"{BASE}/mental/referrals/{rid}", params={"reason": "危机干预需核对记录"},
                    headers=admin).json()["data"]
    assert d1["note"] == "涉密明细内容XYZ" and d1["noteMasked"] is False
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    db = get_sessionmaker()()
    assert db.query(SecurityAuditLog).filter_by(action="SENSITIVE_VIEW").count() >= 1
    db.close()


def test_m5_sec1_mental_records_permission(client, db_mode):
    _seed(db_mode)
    # SEC-1：就业老师无 psyDetail.view → 403（不再零门禁 get_current_user）
    r = client.get(f"{CAMPUS}/mental-records", headers=_hdr(client, "employment01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION"
    # 未登录 → 401
    assert client.get(f"{CAMPUS}/mental-records").status_code == 401


def test_m6_sec2_student_affairs_admin_denied(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    rid = _refer(client, admin, ids["sa"]).json()["data"]["referralId"]
    # SEC-2：学工处管理员无 PSY_STUDENT 专项授权 → 心理明细数据范围拒绝（403 NO_DATA_SCOPE）
    sa = _hdr(client, "sa_admin01")
    r = client.get(f"{BASE}/mental/referrals/{rid}", params={"reason": "学工处例行检查"}, headers=sa)
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_m7_psy_student_scope(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _refer(client, admin, ids["sa"])  # P001 已授权 psych01
    _refer(client, admin, ids["sb"])  # P002 未授权
    psych = _hdr(client, "psych01")
    items = client.get(f"{BASE}/mental/list", headers=psych).json()["data"]["items"]
    sids = {it["studentId"] for it in items}
    assert str(ids["sa"]) in sids and str(ids["sb"]) not in sids  # 仅授权学生可见


def test_m8_no_auto_diagnosis_reason_required(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 无自动诊断：事由摘要人工必填(≥5字)，缺失 → 400
    r = client.post(f"{BASE}/mental/referrals", headers=admin, json={
        "studentId": str(ids["sa"]), "level": "FOCUS", "reasonSummary": "短"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"
    # 摘要按人工原文存储（非系统生成诊断）
    ref = _refer(client, admin, ids["sa"], summary="辅导员反馈近两周缺勤且回避交流").json()["data"]
    assert ref["reasonSummary"] == "辅导员反馈近两周缺勤且回避交流"
