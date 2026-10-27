from datetime import datetime, timedelta

import pytest


@pytest.mark.parametrize("history_conflict", [False, True])
def test_handoff_moves_only_counselor_work_and_protects_history_files(client, db_mode, history_conflict):
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user, role_headers
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (AffairsCounselorAssignment, AffairsRiskRecord, CsLeave, DormTransfer, FundingApplication,
        Role, RoleAssignmentScope, SchoolClass, StudentAccountLink, StudentProfile, UnifiedTodo, User, UserRole,
        WorkflowInstance, WorkflowTask)
    from app.services.saas_role_service import ensure_builtin_roles
    from test_affairs_counselor_assignment import TID, BASE, _seed, _assign, _hdr
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr

    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    original = _assign(client, admin, ids["a"], ids["u1"]).json()["data"]
    manager = ensure_role_user("STUDENT_AFFAIRS_ADMIN", login_name="handoff_manager", real_name="交接负责人")
    ensure_role_user("FUNDING_TEACHER", login_name="ca_counselor_1", real_name="兼岗原辅导员")
    with get_sessionmaker()() as db:
        ensure_builtin_roles(db, TID)
        roles = {r.role_code: r.id for r in db.scalars(select(Role).where(Role.tenant_id == TID)).all()}
        student = db.scalar(select(StudentProfile).where(StudentProfile.tenant_id == TID, StudentProfile.student_no == "CA001"))
        student_id = student.id
        password = hash_password(TEST_LOGIN_PASSWORD)
        for uid in (ids["u1"], ids["u2"], manager):
            account = db.get(User, uid); account.password_hash = password; account.must_change_password = False
        student_user = User(tenant_id=TID, login_name="handoff_student", real_name=student.real_name,
            user_type="STUDENT", password_hash=password, must_change_password=False, status="ACTIVE")
        db.add(student_user); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=student_user.id, role_id=roles["STUDENT"], status="ACTIVE"))
        db.add(StudentAccountLink(tenant_id=TID, user_id=student_user.id, student_id=student_id, link_status="ACTIVE", source="MANUAL"))
        for role_code, scope_type, scope_id in (("COUNSELOR", "CLASS", ids["a"]),
                ("COUNSELOR", "CLASS", ids["b"]), ("FUNDING_TEACHER", "SCHOOL", 0)):
            member = db.scalar(select(UserRole).where(UserRole.tenant_id == TID,
                UserRole.user_id == ids["u1"], UserRole.role_id == roles[role_code]))
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=ids["u1"], user_role_id=member.id,
                role_code=role_code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
                effective_at=datetime.utcnow() - timedelta(days=1)))
        new_member = db.scalar(select(UserRole).where(UserRole.tenant_id == TID,
            UserRole.user_id == ids["u2"], UserRole.role_id == roles["COUNSELOR"]))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=ids["u2"], user_role_id=new_member.id,
            role_code="COUNSELOR", scope_type="CLASS", scope_id=ids["b"], status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        db.commit()

    def staff(login, code):
        header = _real_hdr(client, login, client_type="TEACHER_MINI")
        response = client.post("/api/v1/auth/switch-role", headers=header,
            json={"contextId": f"role:{roles[code]}", "clientType": "TEACHER_MINI"})
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}

    student_header = _real_hdr(client, "handoff_student", client_type="STUDENT_MINI")
    uploaded = client.post("/api/v1/files", headers=student_header, data={"bizType": "AFFAIRS_LEAVE"},
        files={"file": ("handoff-proof.txt", b"history bytes must remain unchanged", "text/plain")})
    assert uploaded.status_code == 200, uploaded.text
    file_id = uploaded.json()["data"]["fileId"]
    applied = client.post("/api/v1/mobile/affairs/leave", headers=student_header, json={
        "leaveType": "PERSONAL", "startTime": "2026-11-02", "endTime": "2026-11-02",
        "reason": "交接前正常学生申请及材料", "fileIds": [file_id]})
    assert applied.status_code == 200, applied.text
    leave = applied.json()["data"]; leave_id = int(leave["id"])
    with get_sessionmaker()() as db:
        flow_id = int(db.get(CsLeave, leave_id).workflow_instance_id)
        task_id = db.scalar(select(WorkflowTask.id).where(WorkflowTask.instance_id == flow_id))
        # 明确构造历史在办专项，不冒充这些专项已经通过任何评审。
        funding = FundingApplication(tenant_id=TID, batch_id=1, student_id=student_id,
            project_type="SCHOLARSHIP", status="SCHOOL_REVIEW", amount=3000, requested_amount=3000)
        transfer = DormTransfer(tenant_id=TID, student_id=student_id, from_bed_id=1, to_bed_id=2,
            status="DORM_MANAGER_REVIEW", current_node="DORM_MANAGER_REVIEW", reason="历史宿管待办")
        db.add_all([funding, transfer]); db.flush()
        special_flow = WorkflowInstance(tenant_id=TID, workflow_code="AFFAIRS_SCHOLARSHIP", source_module="student-affairs",
            source_biz_type="FUNDING", source_biz_id=funding.id, applicant_id=student_user.id,
            status="RUNNING", current_node="SCHOOL_REVIEW")
        db.add(special_flow); db.flush(); funding.workflow_instance_id = special_flow.id
        school_task = WorkflowTask(tenant_id=TID, instance_id=special_flow.id, node_code="SCHOOL_REVIEW",
                                  assignee_id=ids["u1"], status="PENDING")
        db.add(school_task)
        other_student = db.scalar(select(StudentProfile).where(StudentProfile.tenant_id == TID,
                                                              StudentProfile.student_no == "CB001"))
        risk_ids = []
        for sid, owner in ((student_id, ids["u1"]), (other_student.id, ids["u2"])):
            risk = AffairsRiskRecord(tenant_id=TID, student_id=sid, source="MANUAL", source_ref_id=sid,
                risk_level="LOW", title="交接风险回归", owner_id=owner, status="ASSIGNED")
            db.add(risk); db.flush(); risk_ids.append(risk.id)
            db.add(UnifiedTodo(tenant_id=TID, source_module="student-affairs", source_biz_type="RISK",
                source_biz_id=risk.id, todo_type="RISK_HANDLE", assignee_id=owner, student_id=sid,
                title="已有风险待办", status="PENDING"))
        specials = []
        for module, biz_type, biz_id, kind in (("student-affairs", "FUNDING", funding.id, "FUNDING_APPROVAL"),
                ("student-affairs", "DORM_TRANSFER", transfer.id, "DORM_TRANSFER"),
                ("academic", "OTHER", 99001, "OTHER")):
            todo = UnifiedTodo(tenant_id=TID, source_module=module, source_biz_type=biz_type,
                source_biz_id=biz_id, todo_type=kind, assignee_id=ids["u1"], student_id=student_id,
                title="不能随辅导员交接迁走的专项", status="PENDING")
            db.add(todo); db.flush(); specials.append(todo.id)
        if history_conflict:
            done = UnifiedTodo(tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
                source_biz_id=leave_id, todo_type="LEAVE_APPROVAL", assignee_id=ids["u2"], student_id=student_id,
                title="接任者原有已办历史", status="DONE", completed_at=(datetime.utcnow() - timedelta(days=1)).replace(microsecond=0))
            db.add(done); db.flush(); completed = done.completed_at; done_id = done.id
        db.commit(); school_task_id = school_task.id

    old_header = staff("ca_counselor_1", "COUNSELOR")
    # 普通辅导员不能利用日常班级创建权限自行改变任职。
    route = f"{BASE}/classes/{ids['a']}/counselor-handover"
    payload = {"fromUserId": ids["u1"], "toUserId": ids["u2"], "reason": "正式岗位交接核验", "version": original["version"]}
    assert client.post(route, headers=old_header, json=payload).status_code == 403
    result = client.post(route, headers=staff("handoff_manager", "STUDENT_AFFAIRS_ADMIN"), json=payload)
    if history_conflict:
        assert result.status_code == 409, result.text
        with get_sessionmaker()() as db:
            assert db.get(AffairsCounselorAssignment, int(original["id"])).status == "ACTIVE"
            assert db.get(SchoolClass, ids["a"]).counselor_id == ids["u1"]
            assert db.get(UnifiedTodo, done_id).status == "DONE"
            assert db.get(UnifiedTodo, done_id).completed_at == completed
            assert db.get(WorkflowTask, task_id).assignee_id == ids["u1"]
            assert db.get(CsLeave, leave_id).version == leave["version"]
        return
    assert result.status_code == 200, result.text
    assert result.json()["data"]["handoverWork"]["retained"] == 2
    with get_sessionmaker()() as db:
        assert db.get(WorkflowTask, task_id).assignee_id == ids["u2"]
        assert db.get(WorkflowTask, task_id).instance_id == flow_id
        assert db.get(CsLeave, leave_id).affairs_status == "COUNSELOR_REVIEW"
        assert db.get(CsLeave, leave_id).version == leave["version"] + 1
        assert db.get(WorkflowTask, school_task_id).assignee_id == ids["u1"]
        assert all(db.get(UnifiedTodo, key).assignee_id == ids["u1"] for key in specials)
        assert db.get(AffairsRiskRecord, risk_ids[0]).owner_id == ids["u2"]
        risk_todo = db.scalar(select(UnifiedTodo).where(UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_biz_type == "RISK", UnifiedTodo.source_biz_id == risk_ids[0],
            UnifiedTodo.status == "PENDING"))
        assert risk_todo.assignee_id == ids["u2"]
    new_header = staff("ca_counselor_2", "COUNSELOR")
    old_header = staff("ca_counselor_1", "COUNSELOR")
    old_action = client.post(f"{BASE}/leave/{leave_id}/approve", headers=old_header,
                            json={"version": leave["version"]})
    assert old_action.status_code == 403, old_action.text
    stale_action = client.post(f"{BASE}/leave/{leave_id}/approve", headers=new_header,
                              json={"version": leave["version"]})
    assert stale_action.status_code == 409, stale_action.text
    with get_sessionmaker()() as db:
        assert db.get(CsLeave, leave_id).version == leave["version"] + 1
        assert db.get(CsLeave, leave_id).affairs_status == "COUNSELOR_REVIEW"
    detail = client.get(f"{BASE}/leave/{leave_id}", headers=new_header)
    assert detail.status_code == 200, detail.text
    event = next(row for row in detail.json()["data"]["auditTrail"] if row["action"] == "COUNSELOR_HANDOVER")
    assert event["operator"] == "交接负责人"
    assert event["detail"] == "正式岗位交接核验"
    student_detail = client.get(f"/api/v1/mobile/affairs/leave/{leave_id}/detail", headers=student_header)
    assert student_detail.status_code == 200, student_detail.text
    event = next(row for row in student_detail.json()["data"]["timeline"] if row["action"] == "COUNSELOR_HANDOVER")
    assert event["operator"] == "交接负责人" and "detail" not in event
    pending_risks = client.get("/api/v1/mobile/teacher/affairs/risk/pending", headers=new_header)
    assert pending_risks.status_code == 200, pending_risks.text
    assert {row["riskId"] for row in pending_risks.json()["data"]["list"]} == {str(key) for key in risk_ids}
    response = client.get("/api/v1/teacher-mobile/students", headers=old_header)
    assert response.status_code == 200, response.text
    mine = response.json()["data"]["items"]
    assert {row["studentNo"] for row in mine} == {"CB001"}
    assert client.get(f"/api/v1/files/download/{file_id}", headers=old_header).status_code in (403, 404)
    file_response = client.get(f"/api/v1/files/download/{file_id}", headers=new_header)
    assert file_response.status_code == 200 and file_response.content == b"history bytes must remain unchanged"
    assert client.get(f"/api/v1/files/download/{file_id}", headers=staff("ca_counselor_1", "FUNDING_TEACHER")).status_code in (403, 404)
    assert client.get(f"/api/v1/files/download/{file_id}", headers=student_header).content == b"history bytes must remain unchanged"
