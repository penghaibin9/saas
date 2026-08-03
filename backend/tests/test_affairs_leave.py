"""13A-P2 请假销假闭环 · 端到端（真实 DB 模式）。

L1 申请建流；L2 多级审批；L3 短假单节点；L4 驳回(原因校验)；L5 销假→CLOSED进360；
L6 续假改期；L7 逾期扫描幂等；L8 重复提交409；越权跨班403；双状态列一致 + 旧端点下线合同。
"""
from __future__ import annotations

TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )
    db = get_sessionmaker()()

    def ensure_user(login_name, real_name):
        row = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if row is None:
            row = User(
                tenant_id=TID, login_name=login_name, real_name=real_name,
                password_hash="test-hash", user_type="TEACHER", status="ACTIVE",
            )
            db.add(row)
            db.flush()
        else:
            row.status = "ACTIVE"
            row.is_deleted = False
        return row

    def ensure_role(role_code, role_name):
        row = db.query(Role).filter_by(tenant_id=TID, role_code=role_code).first()
        if row is None:
            row = Role(
                tenant_id=TID, role_code=role_code, role_name=role_name,
                role_type="SYSTEM", status="ACTIVE",
            )
            db.add(row)
            db.flush()
        else:
            row.status = "ACTIVE"
            row.is_deleted = False
        return row

    def bind(user, role):
        row = db.query(UserRole).filter_by(
            tenant_id=TID, user_id=user.id, role_id=role.id,
        ).first()
        if row is None:
            db.add(UserRole(
                tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE",
            ))
        else:
            row.status = "ACTIVE"
            row.is_deleted = False

    counselor = ensure_user("counselor01", "王莉")
    college_reviewer = ensure_user("leave_college01", "学院学工受理人")
    sa_reviewer = ensure_user("leave_sa01", "学工处受理人")
    bind(counselor, ensure_role("COUNSELOR", "辅导员"))
    bind(college_reviewer, ensure_role("COLLEGE_ADMIN", "学院管理员"))
    bind(sa_reviewer, ensure_role("STUDENT_AFFAIRS_ADMIN", "学工处管理员"))

    college = College(
        tenant_id=TID, college_name="请假测试学院", code="LEAVE-COLLEGE", status="ACTIVE",
    )
    db.add(college)
    db.flush()
    major = Major(
        tenant_id=TID, college_id=college.id, major_name="请假测试专业",
        code="LEAVE-MAJOR", status="ACTIVE",
    )
    db.add(major)
    db.flush()
    a = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="A班", grade="2024",
        counselor_id=counselor.id, status="ACTIVE",
    )
    b = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="B班", grade="2024",
        counselor_id=counselor.id, status="ACTIVE",
    )
    db.add_all([a, b])
    db.flush()
    sa = StudentProfile(
        tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
        college_id=college.id, gender="M", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    sb = StudentProfile(
        tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
        college_id=college.id, gender="F", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    db.add_all([sa, sb])
    db.flush()
    effective = datetime.utcnow() - timedelta(days=1)
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=a.id, user_id=counselor.id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=effective,
        ),
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=b.id, user_id=counselor.id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=effective,
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="A班", status="ACTIVE",
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key=college_reviewer.login_name,
            teacher_name=college_reviewer.real_name, role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE", ref_value=college.college_name, status="ACTIVE",
        ),
    ])
    db.commit()
    ids = {"a": a.id, "b": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids

def _apply(client, hdr, sid, start, end, ltype="PERSONAL"):
    return client.post("/api/v1/student-affairs/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": ltype, "startTime": start, "endTime": end,
        "reason": "回家处理家庭事务"})



def _leave_detail(client, hdr, lid):
    response = client.get(f"/api/v1/student-affairs/leave/{lid}", headers=hdr)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _version(client, hdr, lid):
    return int(_leave_detail(client, hdr, lid)["version"])


def _leave_action(client, hdr, lid, action, body=None):
    """模拟真实页面：先读取当前记录版本，再显式提交本次写操作。"""
    payload = dict(body or {})
    if action == "extension-approve":
        payload.setdefault("action", "APPROVE")
    if action == "cancel-confirm":
        payload.setdefault("action", "CONFIRM")
    payload.setdefault("version", _version(client, hdr, lid))
    return client.post(
        f"/api/v1/student-affairs/leave/{lid}/{action}",
        headers=hdr,
        json=payload,
    )


def test_l1_apply_creates_workflow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()  # 1 天 → 单节点
    assert r["code"] == 0
    d = r["data"]
    assert d["affairsStatus"] == "COUNSELOR_REVIEW"
    assert d["legacyStatus"] == "PENDING_REVIEW"  # 双状态列投影
    assert d["workflowInstanceId"]
    # workflow 实例 + 任务 + 待办均已建
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    db = get_sessionmaker()()
    assert db.query(WorkflowInstance).filter_by(
        source_biz_id=int(d["id"]), source_module="student-affairs").count() == 1
    assert db.query(WorkflowTask).count() >= 1
    assert db.query(UnifiedTodo).filter_by(source_biz_id=int(d["id"]), todo_type="LEAVE_APPROVAL").count() == 1
    db.close()


def test_l2_multilevel_approve(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-06").json()["data"]["id"]  # 5 天 → LONG 两级
    r1 = _leave_action(client, hdr, lid, "approve").json()
    assert r1["data"]["affairsStatus"] == "COLLEGE_REVIEW"  # 推进到第二级
    r2 = _leave_action(client, hdr, lid, "approve").json()
    assert r2["data"]["affairsStatus"] == "APPROVED"
    assert r2["data"]["legacyStatus"] == "APPROVED"


def test_l3_short_leave_single_node(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    r = _leave_action(client, hdr, lid, "approve").json()
    assert r["data"]["affairsStatus"] == "APPROVED"
    # 已通过再审 → 409
    r2 = _leave_action(client, hdr, lid, "approve")
    assert r2.status_code == 409


def test_l4_reject_reason_required(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    # 原因 <5 字 → 422
    assert _leave_action(client, hdr, lid, "reject", {"reason": "不行"}).status_code == 400
    r = _leave_action(client, hdr, lid, "reject", {"reason": "材料不齐请补充"}).json()
    assert r["data"]["affairsStatus"] == "REJECTED"
    assert r["data"]["legacyStatus"] == "RETURNED"
    assert r["data"].get("returnReason") == "材料不齐请补充"
    d = client.get(f"/api/v1/student-affairs/leave/{lid}", headers=hdr).json()["data"]
    assert d.get("returnReason") == "材料不齐请补充"


def test_l5_cancel_closes_and_hits_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    _leave_action(client, hdr, lid, "approve")
    _leave_action(client, hdr, lid, "cancel", {"proofNote": "已返校"})
    r = _leave_action(client, hdr, lid, "cancel-confirm", {"note": "确认返校"}).json()
    assert r["data"]["affairsStatus"] == "CLOSED"
    # 进 360：学生时间线出现 LEAVE_CLOSED 事件
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    db = get_sessionmaker()()
    ev = db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="LEAVE_CLOSED").count()
    db.close()
    assert ev == 1


def test_l6_extension(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    _leave_action(client, hdr, lid, "approve")
    _leave_action(client, hdr, lid, "extension", {"newEnd": "2026-03-05", "reason": "因病延后返校"})
    r = _leave_action(client, hdr, lid, "extension-approve").json()
    assert r["data"]["affairsStatus"] == "APPROVED"
    assert r["data"]["endTime"].startswith("2026-03-05")


def test_l7_overdue_scan_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 结束时间在过去 → 通过后即逾期
    lid = _apply(client, hdr, ids["sa"], "2020-01-01", "2020-01-02").json()["data"]["id"]
    _leave_action(client, hdr, lid, "approve")
    r = client.post("/api/v1/student-affairs/leave/scan-overdue", headers=hdr).json()
    assert r["data"]["count"] == 1
    # 幂等：再扫不重复
    r2 = client.post("/api/v1/student-affairs/leave/scan-overdue", headers=hdr).json()
    assert r2["data"]["count"] == 0
    d = client.get(f"/api/v1/student-affairs/leave/{lid}", headers=hdr).json()["data"]
    assert d["affairsStatus"] == "OVERDUE"


def test_l8_duplicate_overlap_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-04")
    # 时间重叠 → 409
    assert _apply(client, hdr, ids["sa"], "2026-03-03", "2026-03-05").status_code == 409
    # 不重叠 → 放行
    assert _apply(client, hdr, ids["sa"], "2026-04-01", "2026-04-02").status_code == 200


def test_cross_class_leave_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # 学工处给 B 班学生建请假
    lid = _apply(client, admin, ids["sb"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    # 辅导员(范围=A班)访问 B 班请假 → 403
    r = client.get(f"/api/v1/student-affairs/leave/{lid}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_legacy_campus_leave_routes_retired(client, db_mode):
    """旧在校服务请假列表与审批接口已退出，只允许新学工请假链路。"""
    _seed(db_mode)
    legacy = "/api/v1/campus-service/" + "leaves"
    hdr = _hdr(client, "school_admin01")
    assert client.get(legacy, headers=hdr).status_code == 404
    assert client.post(f"{legacy}/1/approve", headers=hdr,
                       json={"comment": "同意", "version": 0}).status_code == 404


# ═══════════ 本轮新增：销假退回 / 续假驳回 / 逾期处置 / 代登记销假 / 台账 / 统计 / 导出 ═══════════

def _approved_leave(client, hdr, sid, start="2026-03-01", end="2026-03-02"):
    lid = _apply(client, hdr, sid, start, end).json()["data"]["id"]
    _leave_action(client, hdr, lid, "approve")
    return lid


def test_l9_proxy_cancel_then_return(client, db_mode):
    """代登记销假→WAIT_CANCEL_LEAVE；销假退回(RETURN)→回到 APPROVED，可重新销假。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _approved_leave(client, hdr, ids["sa"])
    # 代登记销假（辅导员填实际返校时间）
    r = _leave_action(client, hdr, lid, "proxy-cancel", {"actualReturnAt": "2026-03-02 10:00:00", "note": "本人已返校"}).json()
    assert r["data"]["affairsStatus"] == "WAIT_CANCEL_LEAVE"
    # 重复代登记 → 409（已有进行中销假）
    assert _leave_action(client, hdr, lid, "proxy-cancel", {"actualReturnAt": "2026-03-02 10:00:00"}).status_code == 409
    # 销假退回：原因<5字 → 400
    assert _leave_action(client, hdr, lid, "cancel-confirm", {"action": "RETURN", "reason": "不符"}).status_code == 400
    # 销假退回成功 → 回到 APPROVED
    r2 = _leave_action(client, hdr, lid, "cancel-confirm", {"action": "RETURN", "reason": "返校证明与实际不符，请重新上传"}).json()
    assert r2["data"]["affairsStatus"] == "APPROVED"


def test_l10_proxy_cancel_validations(client, db_mode):
    """代登记销假实际返校时间校验：未来时间/早于开始时间 → 400。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _approved_leave(client, hdr, ids["sa"])
    # 未来时间 → 400
    assert _leave_action(client, hdr, lid, "proxy-cancel", {"actualReturnAt": "2099-01-01"}).status_code == 400
    # 早于开始时间 → 400
    assert _leave_action(client, hdr, lid, "proxy-cancel", {"actualReturnAt": "2026-02-01"}).status_code == 400


def test_l11_extension_reject_keeps_original(client, db_mode):
    """续假驳回(REJECT)→维持原假期与原到期日（不改 endTime）。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _approved_leave(client, hdr, ids["sa"])
    _leave_action(client, hdr, lid, "extension", {"newEnd": "2026-03-05", "reason": "因病延后返校"})
    # 驳回原因<5字 → 400
    assert _leave_action(client, hdr, lid, "extension-approve", {"action": "REJECT", "reason": "no"}).status_code == 400
    r = _leave_action(client, hdr, lid, "extension-approve", {"action": "REJECT", "reason": "无正当理由，不予续假"}).json()
    assert r["data"]["affairsStatus"] == "APPROVED"
    assert r["data"]["endTime"].startswith("2026-03-02")  # 原到期日不变


def test_l12_overdue_handle(client, db_mode):
    """逾期处置：CONTACT 留痕不改状态；CLOSE→CLOSED 进360。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2020-01-01", "2020-01-02").json()["data"]["id"]
    _leave_action(client, hdr, lid, "approve")
    client.post("/api/v1/student-affairs/leave/scan-overdue", headers=hdr)
    # 说明<5字 → 400
    assert _leave_action(client, hdr, lid, "overdue-handle", {"handleType": "CONTACT", "note": "已联"}).status_code == 400
    # CONTACT：仍 OVERDUE
    r1 = _leave_action(client, hdr, lid, "overdue-handle", {"handleType": "CONTACT", "note": "已电话联系，学生称明日返校"}).json()
    assert r1["data"]["affairsStatus"] == "OVERDUE"
    # CLOSE：→ CLOSED + 进360
    r2 = _leave_action(client, hdr, lid, "overdue-handle", {"handleType": "CLOSE", "note": "学生已返校，逾期处置完毕"}).json()
    assert r2["data"]["affairsStatus"] == "CLOSED"
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    db = get_sessionmaker()()
    assert db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="LEAVE_CLOSED").count() == 1
    db.close()


def test_l13_ledger_list_and_filters(client, db_mode):
    """请假台账：全状态列表 + 状态/关键词筛选 + followupOnly。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _approved_leave(client, hdr, ids["sa"], "2026-03-01", "2026-03-02")   # A 班 APPROVED
    _apply(client, hdr, ids["sb"], "2026-03-01", "2026-03-02")            # B 班 待审
    # 全量台账
    all_r = client.get("/api/v1/student-affairs/leave", headers=hdr).json()
    assert all_r["code"] == 0 and all_r["data"]["total"] == 2
    # 状态筛选 APPROVED
    ap = client.get("/api/v1/student-affairs/leave?status=APPROVED", headers=hdr).json()
    assert ap["data"]["total"] == 1
    # followupOnly：只取后续处理活动态（APPROVED 在内，COUNSELOR_REVIEW 不在）
    fo = client.get("/api/v1/student-affairs/leave?followupOnly=true", headers=hdr).json()
    assert fo["data"]["total"] == 1
    # 关键词
    kw = client.get("/api/v1/student-affairs/leave?keyword=甲一", headers=hdr).json()
    assert kw["data"]["total"] == 1
    # 台账行含学号/班级名/类型标签
    row = all_r["data"]["items"][0]
    assert "studentNo" in row and row["className"] and "affairsStatusLabel" in row


def test_l14_ledger_scope_403_and_stats(client, db_mode):
    """台账数据范围裁剪：辅导员只见本班；统计 metrics + breakdown。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    _approved_leave(client, admin, ids["sa"])   # A 班
    _apply(client, admin, ids["sb"], "2026-03-01", "2026-03-02")  # B 班
    # 辅导员(范围=A班) 台账只见 1 条
    couns = _hdr(client, "counselor01")
    r = client.get("/api/v1/student-affairs/leave", headers=couns).json()
    assert r["data"]["total"] == 1
    # 统计 by CLASS
    s = client.get("/api/v1/student-affairs/leave/stats?groupBy=CLASS", headers=admin).json()
    assert s["code"] == 0
    metrics = {m["key"]: m["value"] for m in s["data"]["metrics"]}
    assert metrics["leaveStudentCount"] == 2
    assert len(s["data"]["breakdown"]) >= 1


def test_l15_ledger_export(client, db_mode):
    """请假大导出必须异步：请求只建任务，worker 分页生成，再用一次性票据下载。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    _approved_leave(client, hdr, ids["sa"])
    response = client.post("/api/v1/student-affairs/leave/export", headers=hdr)
    assert response.status_code == 200
    d = response.json()["data"]
    assert d["status"] == "CREATED" and d["queued"] is True
    assert d["rowCount"] == 1 and d["jobId"]
    assert "contentBase64" not in d

    from app.core.context import set_tenant
    from app.services import affairs_leave_export_service as export_svc
    set_tenant({"tenantId": str(TID)})
    try:
        result = export_svc.run_pending(limit=2, worker_id="pytest-leave-export")
    finally:
        set_tenant(None)
    assert result == {"claimed": 1, "succeeded": 1, "failed": 0}

    detail = client.get(
        f"/api/v1/student-affairs/leave/export-jobs/{d['jobId']}", headers=hdr,
    ).json()["data"]
    assert detail["status"] == "SUCCEEDED" and detail["downloadable"] is True
    ticket = client.post(
        f"/api/v1/student-affairs/leave/export-jobs/{d['jobId']}/download-ticket",
        headers=hdr, json={"expectedVersion": detail["version"]},
    ).json()["data"]
    file_response = client.get(ticket["downloadUrl"], headers=hdr)
    assert file_response.status_code == 200
    assert file_response.content[:2] == b"PK"

    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    db = get_sessionmaker()()
    try:
        assert db.query(AffairsAuditTrail).filter_by(
            biz_type="LEAVE", action="EXPORT_REQUESTED",
        ).count() >= 1
    finally:
        db.close()


def test_l16_proxy_cancel_cross_class_403(client, db_mode):
    """越权：辅导员(范围=A班)对 B 班请假代登记销假 → 403 NO_DATA_SCOPE。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    lid = _approved_leave(client, admin, ids["sb"])  # B 班 APPROVED
    version = _version(client, admin, lid)
    r = client.post(f"/api/v1/student-affairs/leave/{lid}/proxy-cancel",
                    headers=_hdr(client, "counselor01"),
                    json={"actualReturnAt": "2026-03-02", "version": version})
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_l17_counselor_cannot_skip_college_review_node(client, db_mode):
    """节点越权修复回归：辅导员(范围=A班)在 COUNSELOR_REVIEW 节点可正常审批（本人职责范围）；
    推进到 COLLEGE_REVIEW 后，同一辅导员不可再审批/驳回——此前 _scope_or_403 只校验学生是否在
    调用者班级范围内，不校验当前节点是否轮到调用者审批，导致辅导员可越级把学院/学工处环节的
    请假直接批了，跳过上级审批。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    couns = _hdr(client, "counselor01")
    lid = _apply(client, admin, ids["sa"], "2026-03-01", "2026-03-06").json()["data"]["id"]  # 5天→LONG两级
    r1 = _leave_action(client, couns, lid, "approve").json()
    assert r1["code"] == 0 and r1["data"]["affairsStatus"] == "COLLEGE_REVIEW"
    r2 = _leave_action(client, couns, lid, "approve")
    assert r2.status_code == 403 and r2.json()["bizCode"] == "NO_PERMISSION"
    r3 = _leave_action(client, couns, lid, "reject", {"reason": "越权测试驳回原因"})
    assert r3.status_code == 403 and r3.json()["bizCode"] == "NO_PERMISSION"
    r4 = _leave_action(client, couns, lid, "return", {"reason": "越权测试退回原因"})
    assert r4.status_code == 403 and r4.json()["bizCode"] == "NO_PERMISSION"
    # 校级管理员（TENANT_ALL）不受节点限制，仍可正常推进到终态
    r5 = _leave_action(client, admin, lid, "approve").json()
    assert r5["code"] == 0 and r5["data"]["affairsStatus"] == "APPROVED"


def test_l19_apply_non_digit_student_400_not_500(client, db_mode):
    """历史欠账收口：辅导员代发起请假若 studentId 非数字，此前 int() 抛 ValueError→500，现应 400。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.post("/api/v1/student-affairs/leave", headers=admin, json={
        "studentId": "abc", "leaveType": "PERSONAL",
        "startTime": "2026-03-01", "endTime": "2026-03-02", "reason": "回家处理家庭事务"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_l18_pending_list_hides_node_not_yours(client, db_mode):
    """待审批列表节点过滤配套：请假推进到 COLLEGE_REVIEW 后，辅导员的待办列表里不应再出现该条
    （避免误导性展示——辅导员看得到但审批不了的数据不应出现在"待我审批"队列里）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    couns = _hdr(client, "counselor01")
    lid = _apply(client, admin, ids["sa"], "2026-03-01", "2026-03-06").json()["data"]["id"]  # LONG两级
    p1 = client.get("/api/v1/student-affairs/leave/pending", headers=couns).json()
    assert any(x["id"] == lid for x in p1["data"]["items"])
    _leave_action(client, couns, lid, "approve")  # 推进到 COLLEGE_REVIEW
    p2 = client.get("/api/v1/student-affairs/leave/pending", headers=couns).json()
    assert not any(x["id"] == lid for x in p2["data"]["items"])
