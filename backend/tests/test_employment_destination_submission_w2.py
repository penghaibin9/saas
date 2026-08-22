"""PR190 W2：就业去向 RETURN 终态 + active submission 并发互斥（真实 MySQL）。

这不是只测表约束：
- RETURN 走正式 `/api/v1/approvals/tasks/{id}/return`，证明通用审批与就业域策略组合后
  不会留下 APPLICANT_RESUBMIT 僵尸待办/可点击消息，实例真实终结且不可 resubmit；
- 并发从 `employment_destination_submission_service.submit()` 真实服务入口发起两个事务，
  证明 per-student StudentProfile 行锁把“active-check + workflow/todo 创建”串行化。

HTTP 链路的学生 token 直接由生产 auth_service_db 生成；不固定 User 主键，避免全量回归
共享 MySQL 时与其它测试碰撞。RETURN 也先读取审批详情取得 sourceVersion 快照再提交。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.employment.services import employment_destination_submission_service as svc

TID = 1000000000000000001
PORTAL = "/api/v1/portal/employment"


def _seed_teacher(login_name="employment01") -> int:
    from app.models import Role, User, UserRole

    db = get_sessionmaker()()
    try:
        user = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if user is None:
            user = User(
                tenant_id=TID,
                login_name=login_name,
                real_name="W2就业老师",
                password_hash="test-only",
                user_type="TEACHER",
                status="ACTIVE",
            )
            db.add(user)
            db.flush()
        role = db.query(Role).filter_by(
            tenant_id=TID, role_code="EMPLOYMENT_TEACHER"
        ).first()
        if role is None:
            role = Role(
                tenant_id=TID,
                role_code="EMPLOYMENT_TEACHER",
                role_name="就业老师",
                role_type="SYSTEM",
                status="ACTIVE",
            )
            db.add(role)
            db.flush()
        if not db.query(UserRole).filter_by(
            tenant_id=TID, user_id=user.id, role_id=role.id
        ).first():
            db.add(UserRole(
                tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE"
            ))
        db.commit()
        return int(user.id)
    finally:
        db.close()


def _ensure_student_role(db, user) -> None:
    from app.models import Role, UserRole

    role = db.query(Role).filter_by(tenant_id=TID, role_code="STUDENT").first()
    if role is None:
        role = Role(
            tenant_id=TID,
            role_code="STUDENT",
            role_name="学生",
            role_type="SYSTEM",
            status="ACTIVE",
        )
        db.add(role)
        db.flush()
    relation = db.query(UserRole).filter_by(
        tenant_id=TID, user_id=user.id, role_id=role.id
    ).first()
    if relation is None:
        db.add(UserRole(
            tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE"
        ))
    else:
        relation.status = "ACTIVE"
        relation.is_deleted = False
    db.flush()


def _seed_student(no: str, name: str) -> tuple[int, int]:
    from app.models import StudentProfile, User
    from app.services import student_account_link_service as link_svc

    db = get_sessionmaker()()
    try:
        user = User(
            tenant_id=TID,
            login_name=no,
            real_name=name,
            password_hash="test-only",
            user_type="STUDENT",
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
        _ensure_student_role(db, user)
        student = StudentProfile(
            tenant_id=TID,
            student_no=no,
            real_name=name,
            gender="F",
            grade="2021",
            current_stage="EMPLOYMENT",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        link_svc.bind_in_session(
            db,
            tenant_id=TID,
            student_id=int(student.id),
            user_id=int(user.id),
            source="IDENTITY_IMPORT",
            login_name=no,
            student_no=no,
            remark="PR190 W2 identity",
        )
        db.commit()
        return int(student.id), int(user.id)
    finally:
        db.close()


def _student_ctx(no: str, name: str, sid: int, uid: int) -> dict:
    return {
        "userId": f"db-{uid}",
        "loginName": no,
        "studentId": str(sid),
        "studentNo": no,
        "realName": name,
        "userType": "STUDENT",
        "tenantId": str(TID),
        "currentRoleCode": "STUDENT",
        "clientType": "PC",
    }


def _activate_student(no: str, name: str, sid: int, uid: int) -> dict:
    ctx = _student_ctx(no, name, sid, uid)
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    set_current_user(ctx)
    return ctx


def _student_headers(no: str) -> dict:
    from app.models import User
    from app.services import auth_service_db

    db = get_sessionmaker()()
    try:
        user = db.query(User).filter_by(tenant_id=TID, login_name=no).first()
        assert user is not None
        token = auth_service_db.build_login_result(db, user, client_type="PC")["accessToken"]
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def _teacher_headers(client, login_name="employment01") -> dict:
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _return_body(client, task_id: str, headers: dict) -> dict:
    detail = client.get(f"/api/v1/approvals/tasks/{task_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    return {
        "reason": "请补充正式三方协议",
        "version": int(data.get("version") or 0),
        "expectedSourceVersion": data["businessContext"]["sourceVersion"],
    }


@pytest.mark.usefixtures("db_mode")
def test_two_concurrent_submits_create_exactly_one_active_workflow():
    """W2/P1：两事务同时提交同一学生，必须 1 success + 1 DATA_CONFLICT。"""
    _seed_teacher()
    sid, uid = _seed_student("W2-CON-001", "并发就业一")
    assert sid != uid
    barrier = Barrier(2)

    def submit(index: int):
        _activate_student("W2-CON-001", "并发就业一", sid, uid)
        barrier.wait()
        try:
            row = svc.submit(
                student_id=sid,
                student_name="并发就业一",
                destination_type="SIGNED",
                company_name=f"并发单位{index}",
                job_title="工程师",
            )
            return "ok", row["submissionId"]
        except AppException as exc:
            return f"rejected:{exc.code}", None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))

    labels = [x[0] for x in results]
    assert labels.count("ok") == 1, results
    assert labels.count("rejected:DATA_CONFLICT") == 1, results

    from app.models import EmpDestinationSubmission, UnifiedTodo, WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        submissions = db.query(EmpDestinationSubmission).filter(
            EmpDestinationSubmission.tenant_id == TID,
            EmpDestinationSubmission.student_id == sid,
            EmpDestinationSubmission.status == "SUBMITTED",
            EmpDestinationSubmission.is_deleted.is_(False),
        ).all()
        assert len(submissions) == 1
        sub = submissions[0]
        instances = db.query(WorkflowInstance).filter(
            WorkflowInstance.tenant_id == TID,
            WorkflowInstance.source_module == "employment",
            WorkflowInstance.source_biz_type == "EMPLOYMENT_DESTINATION",
            WorkflowInstance.source_biz_id == sub.id,
            WorkflowInstance.is_deleted.is_(False),
        ).all()
        assert len(instances) == 1
        assert db.query(WorkflowTask).filter(
            WorkflowTask.tenant_id == TID,
            WorkflowTask.instance_id == instances[0].id,
            WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False),
        ).count() == 1
        assert db.query(UnifiedTodo).filter(
            UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_module == "employment",
            UnifiedTodo.source_biz_id == sub.id,
            UnifiedTodo.todo_type == "EMPLOYMENT_DESTINATION_REVIEW",
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        ).count() == 1
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_return_terminalizes_workflow_and_leaves_no_resubmit_artifact(client):
    """W2/P1：就业 RETURN 提交后，数据库和 HTTP 都不得宣称原流程还能 resubmit。"""
    _seed_teacher()
    sid, uid = _seed_student("W2-RET-001", "退回就业一")
    assert sid != uid
    student_headers = _student_headers("W2-RET-001")

    created = client.post(
        f"{PORTAL}/destination",
        headers=student_headers,
        json={"destinationType": "SIGNED", "companyName": "待补材料单位"},
    ).json()
    assert created["code"] == 0, created
    sub_data = created["data"]

    teacher_headers = _teacher_headers(client)
    returned = client.post(
        f"/api/v1/approvals/tasks/{sub_data['currentTaskId']}/return",
        headers=teacher_headers,
        json=_return_body(client, sub_data["currentTaskId"], teacher_headers),
    )
    assert returned.status_code == 200, returned.text
    payload = returned.json()
    assert payload["code"] == 0, payload
    assert payload["data"]["instanceStatus"] == "RETURNED"
    assert payload["data"]["nextTodo"] is None

    from app.models import EmpDestinationSubmission, UnifiedMessage, UnifiedTodo, WorkflowInstance

    db = get_sessionmaker()()
    try:
        sub = db.get(EmpDestinationSubmission, int(sub_data["submissionId"]))
        assert sub.status == "RETURNED"
        assert sub.current_task_id is None
        inst = db.get(WorkflowInstance, int(sub.workflow_instance_id))
        assert inst.status == "RETURNED"
        assert inst.current_node is None

        # 对外可见的 resubmit 待办必须为 0；同事务里生成过的通用 artifact 被取消+软删。
        assert db.query(UnifiedTodo).filter(
            UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_module == "employment",
            UnifiedTodo.source_biz_id == sub.id,
            UnifiedTodo.todo_type == "APPROVAL_RESUBMIT",
            UnifiedTodo.is_deleted.is_(False),
        ).count() == 0
        cancelled = db.query(UnifiedTodo).filter(
            UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_module == "employment",
            UnifiedTodo.source_biz_id == sub.id,
            UnifiedTodo.todo_type == "APPROVAL_RESUBMIT",
        ).first()
        assert cancelled is not None
        assert cancelled.status == "CANCELLED"
        assert cancelled.is_deleted is True

        message = db.query(UnifiedMessage).filter(
            UnifiedMessage.tenant_id == TID,
            UnifiedMessage.source_module == "employment",
            UnifiedMessage.source_biz_id == sub.id,
            UnifiedMessage.receiver_user_id == uid,
            UnifiedMessage.is_deleted.is_(False),
        ).order_by(UnifiedMessage.id.desc()).first()
        assert message is not None
        assert message.action_key is None
        assert message.action_params_json is None
        assert message.category == "BUSINESS"
        assert message.message_type == "BUSINESS"
        assert message.remark == "RETURNED_TERMINAL"
        instance_version = int(inst.version or 0)
        instance_id = int(inst.id)
    finally:
        db.close()

    # 旧流程已终结：即使申请人本人拿正确 version 调通用 resubmit，也必须 409。
    denied = client.post(
        f"/api/v1/approvals/instances/{instance_id}/resubmit",
        headers=student_headers,
        json={"version": instance_version, "comment": "尝试重提旧记录"},
    )
    assert denied.status_code == 409, denied.text

    # 正确产品语义：新建一条 submission，而不是把历史审批记录改写后重开。
    again = client.post(
        f"{PORTAL}/destination",
        headers=student_headers,
        json={"destinationType": "SIGNED", "companyName": "补正后的新单位"},
    ).json()
    assert again["code"] == 0, again
    assert again["data"]["submissionId"] != sub_data["submissionId"]
