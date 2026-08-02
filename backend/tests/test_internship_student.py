"""岗位实习中心 · 实习学生测试（MySQL 真库 via db_mode）：建档 + 学生-岗位分配闭环
（allocated_count 收口）+ 满员/黑名单/未上架拒绝 + 调岗/退岗 + 状态机 + 资格 + 去向 + 统计 + 导入。"""
from __future__ import annotations

ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"
TID = 1000000000000000001

# 上架前必须录全的劳动权益事实，见 tests/test_internship_position.py::_RIGHTS_FACTS
_RIGHTS_FACTS = {
    "workContent": "参与前端页面开发与联调", "dailyHours": 8, "weeklyHours": 40,
    "nightShift": False, "overtimeAllowed": False, "restDaysPerWeek": 2,
    "remunerationType": "MONTHLY", "accommodationProvided": True,
    "mealProvided": True, "hazardousFlag": False,
    "remunerationAmount": 2000, "remunerationCycle": "MONTHLY",
}


def _company(client, h, cc, name="实习学生测试企业"):
    cid = client.post(ENT, headers=h, json={"name": name, "creditCode": cc}).json()["data"]["id"]
    client.post(f"{ENT}/{cid}/review", headers=h, json={"action": "APPROVE"})  # → 合作中
    return cid


def _mk_batch(client, h, *, compliance=None, rules=None):
    from uuid import uuid4
    body = {
        "batchName": f"岗位测试批次-{uuid4().hex[:6]}", "batchNo": f"POSB-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 10}
    if rules is not None:
        body["rules"] = rules
    elif compliance is not None:
        body["rules"] = {"compliance": compliance}
    b = client.post("/api/v1/internship/batches", headers=h, json=body).json()
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=h,
                       json={"expectedVersion": 0}).json()["code"] == 0
    return bid


def _position(client, h, cid, headcount=2, title="前端实习岗位", publish=True, batch_id=None):
    # 上架前必须挂在一个真实批次上（合规规则 BATCH_UNKNOWN）
    if batch_id is None:
        batch_id = _mk_batch(client, h)
    body = {"companyId": cid, "title": title, "headcount": headcount, "batchId": str(batch_id), **_RIGHTS_FACTS}
    pid = client.post(POS, headers=h, json=body).json()["data"]["id"]
    if publish:
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "SUBMIT"})
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "PUBLISH"})
    return pid


def _org_class():
    """建档必须挂真实学院/专业/班级，见 tests/test_student.py::org_class。"""
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=TID, college_name=f"学院-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=TID, college_id=col.id, major_name=f"专业-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=TID, major_id=maj.id, class_name=f"班级-{uuid4().hex[:6]}",
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        cid = cls.id
        db.commit()
        return str(cid)
    finally:
        db.close()


def _student(client, h, no, name="测试学生"):
    return client.post(STU, headers=h, json={"studentNo": no, "realName": name,
                                             "classId": _org_class()}).json()["data"]["id"]


def _record(client, h, sid, batch_id=None):
    if batch_id is None:
        from uuid import uuid4
        b = client.post("/api/v1/internship/batches", headers=h, json={
            "batchName": f"学生测试批次-{uuid4().hex[:6]}",
            "batchNo": f"STU-{uuid4().hex[:8]}",
            "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
        }).json()
        assert b["code"] == 0, b
        batch_id = b["data"]["id"]
        assert client.post(f"/api/v1/internship/batches/{batch_id}/activate", headers=h, json={"expectedVersion": 0}).json()["code"] == 0
    return client.post(IST, headers=h, json={"studentId": sid, "batchId": batch_id}).json()["data"]["id"]


def _satisfy_onboard_prereqs(rid):
    """补齐上岗前置（BUG-010）：三方协议生效 + 保险核验通过 + 校内指导教师。

    这三项在真实业务里分别由协议、保险、指导教师分配三个模块产生；本用例只验状态机，
    故直接写库造前置，不绕过 set_status 本身的校验。"""
    from app.db.session import get_sessionmaker
    from app.models import InternshipAgreement, InternshipInsurance, InternshipRecord
    db = get_sessionmaker()()
    try:
        rec = db.get(InternshipRecord, int(rid))
        rec.advisor_name = "张指导"
        db.add(InternshipAgreement(tenant_id=rec.tenant_id, internship_id=rec.id,
                                   student_id=rec.student_id, status="EFFECTIVE"))
        db.add(InternshipInsurance(tenant_id=rec.tenant_id, internship_id=rec.id,
                                   student_id=rec.student_id, status="VERIFIED"))
        db.commit()
    finally:
        db.close()


def test_create_and_list(client, auth_headers, db_mode):
    from uuid import uuid4
    b = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": f"列表批次-{uuid4().hex[:6]}", "batchNo": f"LST-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert b["code"] == 0
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers, json={"expectedVersion": 0}).json()["code"] == 0
    sid = _student(client, auth_headers, "S-IST-001")
    r = client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["status"] == "PREPARING" and d["eligibilityStatus"] == "PENDING"
    assert d["destinationType"] == "NONE" and d["positionId"] == ""
    assert d["batchId"] == str(bid)
    lst = client.get(IST, headers=auth_headers, params={"batchId": bid}).json()
    assert lst["code"] == 0 and lst["data"]["total"] >= 1
    # 同学生重复建档(同批次)拒绝
    assert client.post(IST, headers=auth_headers, json={"studentId": sid, "batchId": bid}).json()["code"] != 0
    # 缺 batchId 拒绝
    assert client.post(IST, headers=auth_headers, json={"studentId": sid}).json()["code"] != 0


def test_advisor_assignment_binds_active_teacher_and_audits(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipAuditTrail, Role, User, UserRole
    db = get_sessionmaker()()
    try:
        teacher = User(tenant_id=1000000000000000001, login_name="intern-advisor-01",
                       real_name="实习指导老师", password_hash="test", user_type="TEACHER", status="ACTIVE")
        replacement = User(tenant_id=1000000000000000001, login_name="intern-advisor-02",
                           real_name="新实习指导老师", password_hash="test", user_type="TEACHER", status="ACTIVE")
        role = Role(tenant_id=1000000000000000001, role_code="INTERN_MENTOR",
                    role_name="岗位实习指导教师", role_type="SYSTEM", status="ACTIVE")
        db.add_all((teacher, replacement, role)); db.flush()
        db.add_all((
            UserRole(tenant_id=1000000000000000001, user_id=teacher.id,
                     role_id=role.id, status="ACTIVE"),
            UserRole(tenant_id=1000000000000000001, user_id=replacement.id,
                     role_id=role.id, status="ACTIVE"),
        ))
        db.commit(); teacher_id, replacement_id = str(teacher.id), str(replacement.id)
    finally:
        db.close()
    sid = _student(client, auth_headers, "S-IST-ADVISOR")
    from uuid import uuid4
    b = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": f"指导批次-{uuid4().hex[:6]}", "batchNo": f"ADV-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert b["code"] == 0
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers, json={"expectedVersion": 0}).json()["code"] == 0
    created = client.post(IST, headers=auth_headers,
                          json={"studentId": sid, "batchId": bid, "advisorUserId": teacher_id}).json()
    assert created["code"] == 0 and created["data"]["advisorUserId"] == teacher_id
    record_id = created["data"]["id"]
    advisors = client.get(f"{IST}/advisors", headers=auth_headers).json()["data"]
    assert any(a["id"] == teacher_id for a in advisors)
    changed = client.post(f"{IST}/{record_id}/advisor", headers=auth_headers,
                          json={"advisorUserId": replacement_id, "reason": "重新分配"})
    assert changed.status_code == 200 and changed.json()["data"]["advisorUserId"] == replacement_id
    db = get_sessionmaker()()
    try:
        trails = db.query(InternshipAuditTrail).filter_by(target_type="INTERN_STUDENT", target_id=int(record_id)).all()
        assert any(t.action == "CREATE" and t.detail_json.get("advisorUserId") == teacher_id for t in trails)
        assert any(t.action == "ASSIGN_ADVISOR" and t.detail_json.get("toUserId") == replacement_id for t in trails)
    finally:
        db.close()


def test_assign_updates_allocated_count(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTA001X")
    bid = _mk_batch(client, auth_headers)
    pid = _position(client, auth_headers, cid, headcount=2, batch_id=bid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-010"), batch_id=bid)
    a = client.post(f"{IST}/{rid}/assign", headers=auth_headers,
                    json={"positionId": pid, "expectedVersion": 0}).json()
    assert a["code"] == 0
    assert a["data"]["positionId"] == pid and a["data"]["destinationType"] == "ASSIGNED"
    assert a["data"]["enterpriseName"] and a["data"]["positionName"]
    # 岗位库 allocated_count 真实回填 + 已分配学生列表
    pd = client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]
    assert pd["allocatedCount"] == 1 and pd["assignedCount"] == 1
    assert pd["assignedStudents"][0]["studentNo"] == "S-IST-010"


def test_assign_full_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTF001X")
    bid = _mk_batch(client, auth_headers)
    pid = _position(client, auth_headers, cid, headcount=1, batch_id=bid)
    r1 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-020"), batch_id=bid)
    assert client.post(f"{IST}/{r1}/assign", headers=auth_headers,
                       json={"positionId": pid, "expectedVersion": 0}).json()["code"] == 0
    # 岗位满员 → 状态 FULL；第二人分配被拒
    assert client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]["status"] == "FULL"
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-021"), batch_id=bid)
    assert client.post(f"{IST}/{r2}/assign", headers=auth_headers,
                       json={"positionId": pid, "expectedVersion": 0}).json()["code"] != 0


def test_assign_non_published_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTN001X")
    pid = _position(client, auth_headers, cid, publish=False)  # 草稿
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-030"))
    assert client.post(f"{IST}/{rid}/assign", headers=auth_headers,
                       json={"positionId": pid, "expectedVersion": 0}).json()["code"] != 0


def test_assign_blacklist_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTB001X")
    pid = _position(client, auth_headers, cid)
    client.post(f"{ENT}/{cid}/blacklist", headers=auth_headers, json={"on": True, "reason": "多次违规拖欠"})
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-040"))
    assert client.post(f"{IST}/{rid}/assign", headers=auth_headers,
                       json={"positionId": pid, "expectedVersion": 0}).json()["code"] != 0


def test_reassign_moves_allocation(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTR001X")
    bid = _mk_batch(client, auth_headers)
    p1 = _position(client, auth_headers, cid, title="岗位一", batch_id=bid)
    p2 = _position(client, auth_headers, cid, title="岗位二", batch_id=bid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-050"), batch_id=bid)
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": p1, "expectedVersion": 0})
    # 第一次分配已把 version 从 0 推进到 1
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": p2, "expectedVersion": 1})  # 调岗
    assert client.get(f"{POS}/{p1}", headers=auth_headers).json()["data"]["allocatedCount"] == 0
    assert client.get(f"{POS}/{p2}", headers=auth_headers).json()["data"]["allocatedCount"] == 1


def test_unassign_releases(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTU001X")
    bid = _mk_batch(client, auth_headers)
    pid = _position(client, auth_headers, cid, batch_id=bid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-060"), batch_id=bid)
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid, "expectedVersion": 0})
    u = client.post(f"{IST}/{rid}/unassign", headers=auth_headers,
                    json={"reason": "岗位调整", "expectedVersion": 1}).json()
    assert u["code"] == 0 and u["data"]["positionId"] == "" and u["data"]["destinationType"] == "NONE"
    assert client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]["allocatedCount"] == 0


def test_status_machine(client, auth_headers, db_mode):
    from datetime import date
    cid = _company(client, auth_headers, "91310000ISTS001X")
    # StudentProfile 没有 birth_date 字段，监护人知情确认在 requireGuardianConsentForMinor=True
    # 时永远卡在"出生日期待核实"（真实产品缺口，见报告）；本用例只关心状态机，批次显式关闭该项。
    # ASSESS 还会核算周报/打卡/巡访/指导"应有数量"（按 intern_start_date~batch.end_date 的自然
    # 日历推算，非规则配置项可清零——weeklyReport/checkin 无法通过 rules 关掉）。批次结束日设为
    # 今天，让考核所需的周报/打卡最少化为 1 条，巡访/指导用规则清零，随后精确补 1 条周报 + 1 条打卡。
    today = date.today().isoformat()
    bid = _mk_batch(client, auth_headers, rules={
        "compliance": {"studentConsent": {"requireGuardianConsentForMinor": False}},
        "guidance": {"minVisitsPerTerm": 0, "minCommunicationsPerMonth": 0},
    })
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch
    db = get_sessionmaker()()
    try:
        b = db.get(InternshipBatch, bid)
        b.end_date = date.today()
        db.commit()
    finally:
        db.close()
    pid = _position(client, auth_headers, cid, batch_id=bid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-070"), batch_id=bid)
    # 未合格不能待上岗
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "READY"}).json()["code"] != 0
    client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={"status": "QUALIFIED"})
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "READY"}).json()["data"]["status"] == "READY"
    # 未分配岗位不能上岗
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()["code"] != 0
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid, "expectedVersion": 0})
    # BUG-010：仅「有岗位」不足以上岗——三方协议/保险/指导教师任一缺失都必须拦住
    blocked = client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()
    assert blocked["code"] != 0 and "上岗前置未完成" in blocked["message"]
    # 前置清单接口应如实列出缺什么（供前端在点「上岗」前提示）
    chk = client.get(f"{IST}/{rid}/onboard-checklist", headers=auth_headers).json()["data"]
    # 前置项清单现按类别加了前缀标签（如"三方协议："），语义不变，改为子串匹配
    assert chk["canOnboard"] is False
    assert any("三方协议未生效" in b for b in chk["blockers"])
    _satisfy_onboard_prereqs(rid)
    chk2 = client.get(f"{IST}/{rid}/onboard-checklist", headers=auth_headers).json()["data"]
    assert chk2["canOnboard"] is True and chk2["blockers"] == []
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()["data"]["status"] == "ONBOARD"
    # 批次结束日=今天 → 应有周报/打卡各最少化为 1 条；补齐即可通过考核前置数量核算
    from app.models import InternshipCheckin, WeeklyReport
    db = get_sessionmaker()()
    try:
        db.add(WeeklyReport(tenant_id=TID, internship_id=int(rid), week_number=1,
                            word_count=800, status="APPROVED"))
        db.add(InternshipCheckin(tenant_id=TID, internship_id=int(rid), checkin_date=today,
                                 result="NORMAL"))
        db.commit()
    finally:
        db.close()
    assess = client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ASSESS"}).json()
    assert assess.get("data") and assess["data"]["status"] == "ASSESSING", assess
    # 归档不再走 /status（其 action 校验只放行 READY/ONBOARD/ASSESS），须走正式归档接口；
    # 本用例未凑齐企业评价/学生自评/成绩发布等归档合规材料，走 force 强制归档
    import io
    up = client.post("/api/v1/files", headers=auth_headers,
                     files={"file": ("evidence.txt", io.BytesIO(b"force-archive-evidence"), "text/plain")},
                     data={"bizType": "ATTACHMENT"})
    fid = up.json()["data"]["fileId"]
    arc = client.post(f"/api/v1/internship/archive/{rid}/archive", headers=auth_headers, json={
        "force": True, "forceReason": "状态机用例仅验证流转，材料另有专项测试覆盖",
        "evidenceFileIds": [fid], "expectedVersion": 1,
    }).json()
    assert arc.get("data") and arc["data"]["archived"] is True, arc
    assert client.get(f"{IST}/{rid}", headers=auth_headers).json()["data"]["status"] == "ARCHIVED"
    # 已归档不可编辑
    assert client.put(f"{IST}/{rid}", headers=auth_headers, json={"remark": "x"}).json()["code"] != 0


def test_destination(client, auth_headers, db_mode):
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-080"))
    d = client.post(f"{IST}/{rid}/destination", headers=auth_headers, json={"destination": "SELF_ARRANGED"}).json()
    assert d["code"] == 0 and d["data"]["destinationType"] == "SELF_ARRANGED"
    # 已分配岗位则不能直接改去向
    cid = _company(client, auth_headers, "91310000ISTD001X")
    bid = _mk_batch(client, auth_headers)
    pid = _position(client, auth_headers, cid, batch_id=bid)
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-081"), batch_id=bid)
    assert client.post(f"{IST}/{r2}/assign", headers=auth_headers,
                       json={"positionId": pid, "expectedVersion": 0}).json()["code"] == 0
    assert client.post(f"{IST}/{r2}/destination", headers=auth_headers, json={"destination": "EXEMPTED"}).json()["code"] != 0


def test_stats_and_export(client, auth_headers, db_mode):
    from uuid import uuid4
    b = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": f"统计导出批次-{uuid4().hex[:6]}", "batchNo": f"SE-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert b["code"] == 0
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers, json={"expectedVersion": 0}).json()["code"] == 0
    _record(client, auth_headers, _student(client, auth_headers, "S-IST-090"), batch_id=bid)
    s = client.get(f"{IST}/stats", headers=auth_headers, params={"batchId": bid}).json()
    assert s["code"] == 0 and s["data"]["total"] >= 1
    assert any(x["status"] == "PREPARING" for x in s["data"]["byStatus"])
    # P0-E：导出已由 CSV 升级为正式 Excel(.xlsx)（base64 + xlsx mediaType）
    ex = client.post(f"{IST}/export", headers=auth_headers, params={"batchId": bid}).json()
    assert ex["code"] == 0 and ex["data"]["rowCount"] >= 1
    assert ex["data"]["filename"].endswith(".xlsx") and "spreadsheetml.sheet" in ex["data"]["mediaType"]
    assert ex["data"].get("contentBase64")
    assert ex["data"].get("batchId") == str(bid)


def test_import(client, auth_headers, db_mode):
    from uuid import uuid4
    b = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": f"导入批次-{uuid4().hex[:6]}", "batchNo": f"IMP-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert b["code"] == 0
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers, json={"expectedVersion": 0}).json()["code"] == 0
    _student(client, auth_headers, "S-IST-100", "导入学生甲")
    rows = [{"studentNo": "S-IST-100"}, {"studentNo": ""}, {"studentNo": "S-NOEXIST"}]
    dry = client.post(f"{IST}/import/dry-run", headers=auth_headers,
                      json={"rows": rows, "batchId": bid}).json()
    assert dry["code"] == 0 and dry["data"]["validRows"] == 1 and dry["data"]["invalidRows"] == 2
    assert client.post(f"{IST}/import/confirm", headers=auth_headers,
                       json={"rows": rows, "batchId": bid}).json()["code"] != 0
    ok = client.post(f"{IST}/import/confirm", headers=auth_headers,
                     json={"rows": [rows[0]], "batchId": bid}).json()
    assert ok["code"] == 0 and ok["data"]["created"] == 1
    assert ok["data"].get("batchId") == str(bid)
