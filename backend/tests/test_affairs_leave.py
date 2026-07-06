"""13A-P2 请假销假闭环 · 端到端（真实 DB 模式）。

L1 申请建流；L2 多级审批；L3 短假单节点；L4 驳回(原因校验)；L5 销假→CLOSED进360；
L6 续假改期；L7 逾期扫描幂等；L8 重复提交409；越权跨班403；双状态列一致 + 老端点回归。
"""
from __future__ import annotations

TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """2 班 + 学生（含 counselor 范围限定 A 班），返回学生/班级 id。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _apply(client, hdr, sid, start, end, ltype="PERSONAL"):
    return client.post("/api/v1/student-affairs/leave", headers=hdr, json={
        "studentId": str(sid), "leaveType": ltype, "startTime": start, "endTime": end,
        "reason": "回家有事"})


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
    r1 = client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr).json()
    assert r1["data"]["affairsStatus"] == "COLLEGE_REVIEW"  # 推进到第二级
    r2 = client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr).json()
    assert r2["data"]["affairsStatus"] == "APPROVED"
    assert r2["data"]["legacyStatus"] == "APPROVED"


def test_l3_short_leave_single_node(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    r = client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr).json()
    assert r["data"]["affairsStatus"] == "APPROVED"
    # 已通过再审 → 409
    r2 = client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr)
    assert r2.status_code == 409


def test_l4_reject_reason_required(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    # 原因 <5 字 → 422
    assert client.post(f"/api/v1/student-affairs/leave/{lid}/reject",
                       headers=hdr, json={"reason": "不行"}).status_code == 400
    r = client.post(f"/api/v1/student-affairs/leave/{lid}/reject",
                    headers=hdr, json={"reason": "材料不齐请补充"}).json()
    assert r["data"]["affairsStatus"] == "REJECTED"
    assert r["data"]["legacyStatus"] == "RETURNED"


def test_l5_cancel_closes_and_hits_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    lid = _apply(client, hdr, ids["sa"], "2026-03-01", "2026-03-02").json()["data"]["id"]
    client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr)
    client.post(f"/api/v1/student-affairs/leave/{lid}/cancel", headers=hdr, json={"proofNote": "已返校"})
    r = client.post(f"/api/v1/student-affairs/leave/{lid}/cancel-confirm", headers=hdr,
                    json={"note": "确认返校"}).json()
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
    client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr)
    client.post(f"/api/v1/student-affairs/leave/{lid}/extension", headers=hdr,
                json={"newEnd": "2026-03-05", "reason": "延后返校"})
    r = client.post(f"/api/v1/student-affairs/leave/{lid}/extension-approve", headers=hdr).json()
    assert r["data"]["affairsStatus"] == "APPROVED"
    assert r["data"]["endTime"].startswith("2026-03-05")


def test_l7_overdue_scan_idempotent(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 结束时间在过去 → 通过后即逾期
    lid = _apply(client, hdr, ids["sa"], "2020-01-01", "2020-01-02").json()["data"]["id"]
    client.post(f"/api/v1/student-affairs/leave/{lid}/approve", headers=hdr)
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


def test_legacy_campus_leave_endpoints_unaffected(client, db_mode):
    """老 campus-service 请假读端点回归绿（双状态列不破坏旧链路）。"""
    _seed(db_mode)
    r = client.get("/api/v1/campus-service/leaves", headers=_hdr(client, "school_admin01"))
    assert r.status_code == 200 and r.json()["code"] == 0
