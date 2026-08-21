"""SP-E02/E04：结构化就业去向提交 + 单节点真实审批 + 原子写回 canonical（MySQL 真库）。

覆盖：
- 学生 PC 提交校验（非法 destinationType 拒绝）与同学生在途提交冲突（409）；
- 提交开出真实 t_workflow_instance/t_workflow_task + UnifiedTodo，受理人按
  EMPLOYMENT_TEACHER 角色候选池解析；
- 走通用审批中心 approve → 同一事务原子写回 EmpStudent（新建 / 更新两条路径），
  不动 verify_status（T5 分层）；
- reject → 提交 REJECTED，EmpStudent 不受影响；
- return → 提交 RETURNED（终态）+ 原因落库，学生可重新提交一条新记录；
- approval_business_context_service 的 EMPLOYMENT_DESTINATION adapter 返回真实字段。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/employment"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _hdr(client, login_name="employment01"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_teacher(login_name="employment01"):
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole
    db = get_sessionmaker()()
    try:
        user = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if user is None:
            user = User(tenant_id=TID, login_name=login_name, real_name="就业老师",
                       password_hash="test-only", user_type="TEACHER", status="ACTIVE")
            db.add(user)
            db.flush()
        role = db.query(Role).filter_by(tenant_id=TID, role_code="EMPLOYMENT_TEACHER").first()
        if role is None:
            role = Role(tenant_id=TID, role_code="EMPLOYMENT_TEACHER", role_name="就业老师",
                       role_type="SYSTEM", status="ACTIVE")
            db.add(role)
            db.flush()
        if not db.query(UserRole).filter_by(tenant_id=TID, user_id=user.id, role_id=role.id).first():
            db.add(UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE"))
        db.commit()
        uid = int(user.id)
    finally:
        db.close()
    return uid


def _seed_student(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    row = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F", grade="2021",
                         current_stage="EMPLOYMENT", student_status="NORMAL", status="ACTIVE")
    db.add(row)
    db.commit()
    sid = int(row.id)
    db.close()
    return sid


def _register(client, no, name, **fields):
    h = _stu_token(name, no)
    body = {"destinationType": "SIGNED", "companyName": "甲公司", **fields}
    return client.post(f"{PORTAL}/destination", headers=h, json=body).json()


def test_submit_rejects_invalid_destination_type(client, db_mode):
    _seed_student("SUB-000", "提交零")
    r = _register(client, "SUB-000", "提交零", destinationType="NOT_A_CODE")
    assert r["code"] != 0, r


def test_submit_and_duplicate_active_conflict(client, db_mode):
    _seed_teacher()
    _seed_student("SUB-001", "提交一")
    ok = _register(client, "SUB-001", "提交一")
    assert ok["code"] == 0, ok
    assert ok["data"]["status"] == "SUBMITTED"
    assert ok["data"]["currentTaskId"]

    dup = _register(client, "SUB-001", "提交一", companyName="乙公司")
    assert dup["code"] != 0, dup


def test_submit_opens_real_workflow_and_todo(client, db_mode):
    teacher_id = _seed_teacher()
    sid = _seed_student("SUB-002", "提交二")
    ok = _register(client, "SUB-002", "提交二")["data"]

    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo, WorkflowInstance, WorkflowTask
    db = get_sessionmaker()()
    try:
        inst = db.query(WorkflowInstance).filter_by(
            tenant_id=TID, source_module="employment", source_biz_type="EMPLOYMENT_DESTINATION",
            source_biz_id=int(ok["submissionId"])).first()
        assert inst is not None
        assert inst.status == "RUNNING"
        task = db.query(WorkflowTask).filter_by(id=int(ok["currentTaskId"])).first()
        assert task is not None
        assert task.assignee_id == teacher_id
        assert task.status == "PENDING"
        todo = db.query(UnifiedTodo).filter_by(
            tenant_id=TID, source_module="employment", source_biz_id=int(ok["submissionId"]),
            todo_type="EMPLOYMENT_DESTINATION_REVIEW").first()
        assert todo is not None
        assert todo.status == "PENDING"
        assert todo.assignee_id == teacher_id
    finally:
        db.close()


def test_approve_creates_emp_student_atomically(client, db_mode):
    _seed_teacher()
    sid = _seed_student("SUB-003", "提交三")
    row = _register(client, "SUB-003", "提交三", jobTitle="后端工程师",
                    city="杭州市", contact="0571-0000")["data"]
    task_id = row["currentTaskId"]

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/approve",
                       json={"comment": "同意", "version": 0}, headers=headers)
    assert resp.status_code == 200, resp.text

    from app.db.session import get_sessionmaker
    from app.models import EmpDestinationSubmission, EmpStudent, UnifiedTodo, WorkflowTask
    db = get_sessionmaker()()
    try:
        sub = db.get(EmpDestinationSubmission, int(row["submissionId"]))
        assert sub.status == "APPROVED"
        assert sub.decision_version == 1
        assert sub.current_task_id is None
        assert sub.emp_student_id is not None

        emp = db.get(EmpStudent, int(sub.emp_student_id))
        assert emp is not None
        assert emp.student_id == sid
        assert emp.destination_type == "SIGNED"
        assert emp.company_name == "甲公司"
        assert emp.job_title == "后端工程师"
        # T5 分层：批准结构化提交不代表去向已核验。
        assert emp.verify_status != "VERIFIED"

        task = db.get(WorkflowTask, int(task_id))
        assert task.status == "APPROVED"

        todo = db.query(UnifiedTodo).filter_by(
            tenant_id=TID, source_module="employment", source_biz_id=sub.id,
            todo_type="EMPLOYMENT_DESTINATION_REVIEW").first()
        assert todo.status == "DONE"
    finally:
        db.close()


def test_approve_updates_existing_emp_student_without_touching_verify_status(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpStudent

    _seed_teacher()
    sid = _seed_student("SUB-004", "提交四")

    db = get_sessionmaker()()
    emp = EmpStudent(tenant_id=TID, student_id=sid, student_no="SUB-004", name="提交四",
                     destination_type="UNEMPLOYED", verify_status="VERIFIED",
                     record_status="ACTIVE")
    db.add(emp)
    db.commit()
    emp_id = int(emp.id)
    old_version = int(emp.version or 0)
    db.close()

    row = _register(client, "SUB-004", "提交四", companyName="新单位")["data"]
    task_id = row["currentTaskId"]

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/approve",
                       json={"comment": "同意", "version": 0}, headers=headers)
    assert resp.status_code == 200, resp.text

    db = get_sessionmaker()()
    try:
        emp2 = db.get(EmpStudent, emp_id)
        assert emp2.destination_type == "SIGNED"
        assert emp2.company_name == "新单位"
        assert int(emp2.version or 0) == old_version + 1
        # 批准去向登记提交不是核验：已有的核验事实不得被这条通道覆盖或重置。
        assert emp2.verify_status == "VERIFIED"
    finally:
        db.close()


def test_reject_leaves_emp_student_untouched(client, db_mode):
    _seed_teacher()
    sid = _seed_student("SUB-005", "提交五")
    row = _register(client, "SUB-005", "提交五")["data"]
    task_id = row["currentTaskId"]

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/reject",
                       json={"reason": "提交材料不属实", "version": 0}, headers=headers)
    assert resp.status_code == 200, resp.text

    from app.db.session import get_sessionmaker
    from app.models import EmpDestinationSubmission, EmpStudent
    db = get_sessionmaker()()
    try:
        sub = db.get(EmpDestinationSubmission, int(row["submissionId"]))
        assert sub.status == "REJECTED"
        assert sub.emp_student_id is None
        emp = db.query(EmpStudent).filter_by(tenant_id=TID, student_id=sid).first()
        assert emp is None
    finally:
        db.close()


def test_return_is_terminal_and_allows_resubmission(client, db_mode):
    _seed_teacher()
    sid = _seed_student("SUB-006", "提交六")
    row = _register(client, "SUB-006", "提交六")["data"]
    task_id = row["currentTaskId"]

    headers = _hdr(client)
    resp = client.post(f"/api/v1/approvals/tasks/{task_id}/return",
                       json={"reason": "请补充三方协议", "version": 0}, headers=headers)
    assert resp.status_code == 200, resp.text

    from app.db.session import get_sessionmaker
    from app.models import EmpDestinationSubmission
    db = get_sessionmaker()()
    try:
        sub = db.get(EmpDestinationSubmission, int(row["submissionId"]))
        assert sub.status == "RETURNED"
        assert sub.return_reason == "请补充三方协议"
    finally:
        db.close()

    # 终态：同一学生可以再提交一条全新记录，不是原地编辑重开。
    row2 = _register(client, "SUB-006", "提交六", companyName="乙公司")["data"]
    assert row2["status"] == "SUBMITTED"
    assert row2["submissionId"] != row["submissionId"]


def test_business_context_adapter_reports_full(client, db_mode):
    _seed_teacher()
    sid = _seed_student("SUB-007", "提交七")
    row = _register(client, "SUB-007", "提交七", jobTitle="工程师",
                    city="上海市", contact="021-0000")["data"]

    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance
    from app.services.approval_business_context_service import resolve_context
    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        inst = db.query(WorkflowInstance).filter_by(
            tenant_id=TID, source_biz_type="EMPLOYMENT_DESTINATION",
            source_biz_id=int(row["submissionId"])).first()
        ctx = resolve_context(db, inst)
    finally:
        db.close()
    assert ctx["completeness"] == "FULL", ctx
    values = {f["label"]: f["value"] for s in ctx["sections"] for f in s["fields"]}
    assert values["单位/去向"] == "甲公司"
    assert values["岗位"] == "工程师"
    assert values["城市"] == "上海市"


def test_my_view_reports_latest_submission_before_approval(client, db_mode):
    """SP-E02/E04：批准前 EmpStudent 尚不存在，`我的就业` 仍须能看到最近一条提交
    及其状态，不能显示"暂无就业记录"。"""
    _seed_teacher()
    _seed_student("SUB-008", "提交八")
    row = _register(client, "SUB-008", "提交八")["data"]

    h = _stu_token("提交八", "SUB-008")
    d = client.get(f"{PORTAL}/my", headers=h).json()["data"]
    assert d["latestSubmission"] is not None
    assert d["latestSubmission"]["submissionId"] == row["submissionId"]
    assert d["latestSubmission"]["status"] == "SUBMITTED"
