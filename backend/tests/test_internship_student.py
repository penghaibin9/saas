"""岗位实习中心 · 实习学生测试（MySQL 真库 via db_mode）：建档 + 学生-岗位分配闭环
（allocated_count 收口）+ 满员/黑名单/未上架拒绝 + 调岗/退岗 + 状态机 + 资格 + 去向 + 统计 + 导入。"""
from __future__ import annotations

ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"
IST = "/api/v1/internship/intern-students"
STU = "/api/v1/students"


def _company(client, h, cc, name="实习学生测试企业"):
    cid = client.post(ENT, headers=h, json={"name": name, "creditCode": cc}).json()["data"]["id"]
    client.post(f"{ENT}/{cid}/review", headers=h, json={"action": "APPROVE"})  # → 合作中
    return cid


def _position(client, h, cid, headcount=2, title="前端实习岗位", publish=True):
    pid = client.post(POS, headers=h, json={"companyId": cid, "title": title,
                                            "headcount": headcount}).json()["data"]["id"]
    if publish:
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "SUBMIT"})
        client.post(f"{POS}/{pid}/status", headers=h, json={"action": "PUBLISH"})
    return pid


def _student(client, h, no, name="测试学生"):
    return client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]


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
        assert client.post(f"/api/v1/internship/batches/{batch_id}/activate", headers=h).json()["code"] == 0
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
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers).json()["code"] == 0
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
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers).json()["code"] == 0
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
    pid = _position(client, auth_headers, cid, headcount=2)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-010"))
    a = client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid}).json()
    assert a["code"] == 0
    assert a["data"]["positionId"] == pid and a["data"]["destinationType"] == "ASSIGNED"
    assert a["data"]["enterpriseName"] and a["data"]["positionName"]
    # 岗位库 allocated_count 真实回填 + 已分配学生列表
    pd = client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]
    assert pd["allocatedCount"] == 1 and pd["assignedCount"] == 1
    assert pd["assignedStudents"][0]["studentNo"] == "S-IST-010"


def test_assign_full_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTF001X")
    pid = _position(client, auth_headers, cid, headcount=1)
    r1 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-020"))
    assert client.post(f"{IST}/{r1}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] == 0
    # 岗位满员 → 状态 FULL；第二人分配被拒
    assert client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]["status"] == "FULL"
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-021"))
    assert client.post(f"{IST}/{r2}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] != 0


def test_assign_non_published_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTN001X")
    pid = _position(client, auth_headers, cid, publish=False)  # 草稿
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-030"))
    assert client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] != 0


def test_assign_blacklist_rejected(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTB001X")
    pid = _position(client, auth_headers, cid)
    client.post(f"{ENT}/{cid}/blacklist", headers=auth_headers, json={"on": True, "reason": "多次违规拖欠"})
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-040"))
    assert client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid}).json()["code"] != 0


def test_reassign_moves_allocation(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTR001X")
    p1 = _position(client, auth_headers, cid, title="岗位一")
    p2 = _position(client, auth_headers, cid, title="岗位二")
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-050"))
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": p1})
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": p2})  # 调岗
    assert client.get(f"{POS}/{p1}", headers=auth_headers).json()["data"]["allocatedCount"] == 0
    assert client.get(f"{POS}/{p2}", headers=auth_headers).json()["data"]["allocatedCount"] == 1


def test_unassign_releases(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTU001X")
    pid = _position(client, auth_headers, cid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-060"))
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid})
    u = client.post(f"{IST}/{rid}/unassign", headers=auth_headers, json={"reason": "岗位调整"}).json()
    assert u["code"] == 0 and u["data"]["positionId"] == "" and u["data"]["destinationType"] == "NONE"
    assert client.get(f"{POS}/{pid}", headers=auth_headers).json()["data"]["allocatedCount"] == 0


def test_status_machine(client, auth_headers, db_mode):
    cid = _company(client, auth_headers, "91310000ISTS001X")
    pid = _position(client, auth_headers, cid)
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-070"))
    # 未合格不能待上岗
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "READY"}).json()["code"] != 0
    client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={"status": "QUALIFIED"})
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "READY"}).json()["data"]["status"] == "READY"
    # 未分配岗位不能上岗
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()["code"] != 0
    client.post(f"{IST}/{rid}/assign", headers=auth_headers, json={"positionId": pid})
    # BUG-010：仅「有岗位」不足以上岗——三方协议/保险/指导教师任一缺失都必须拦住
    blocked = client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()
    assert blocked["code"] != 0 and "上岗前置未完成" in blocked["message"]
    # 前置清单接口应如实列出缺什么（供前端在点「上岗」前提示）
    chk = client.get(f"{IST}/{rid}/onboard-checklist", headers=auth_headers).json()["data"]
    assert chk["canOnboard"] is False and "三方协议未生效" in chk["blockers"]
    _satisfy_onboard_prereqs(rid)
    chk2 = client.get(f"{IST}/{rid}/onboard-checklist", headers=auth_headers).json()["data"]
    assert chk2["canOnboard"] is True and chk2["blockers"] == []
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ONBOARD"}).json()["data"]["status"] == "ONBOARD"
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ASSESS"}).json()["data"]["status"] == "ASSESSING"
    assert client.post(f"{IST}/{rid}/status", headers=auth_headers, json={"action": "ARCHIVE"}).json()["data"]["status"] == "ARCHIVED"
    # 已归档不可编辑
    assert client.put(f"{IST}/{rid}", headers=auth_headers, json={"remark": "x"}).json()["code"] != 0


def test_destination(client, auth_headers, db_mode):
    rid = _record(client, auth_headers, _student(client, auth_headers, "S-IST-080"))
    d = client.post(f"{IST}/{rid}/destination", headers=auth_headers, json={"destination": "SELF_ARRANGED"}).json()
    assert d["code"] == 0 and d["data"]["destinationType"] == "SELF_ARRANGED"
    # 已分配岗位则不能直接改去向
    cid = _company(client, auth_headers, "91310000ISTD001X")
    pid = _position(client, auth_headers, cid)
    r2 = _record(client, auth_headers, _student(client, auth_headers, "S-IST-081"))
    client.post(f"{IST}/{r2}/assign", headers=auth_headers, json={"positionId": pid})
    assert client.post(f"{IST}/{r2}/destination", headers=auth_headers, json={"destination": "EXEMPTED"}).json()["code"] != 0


def test_stats_and_export(client, auth_headers, db_mode):
    from uuid import uuid4
    b = client.post("/api/v1/internship/batches", headers=auth_headers, json={
        "batchName": f"统计导出批次-{uuid4().hex[:6]}", "batchNo": f"SE-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 5,
    }).json()
    assert b["code"] == 0
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers).json()["code"] == 0
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
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=auth_headers).json()["code"] == 0
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
