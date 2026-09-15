"""学生小程序请假：真实文件绑定、分页和本人边界回归。"""
from __future__ import annotations

from sqlalchemy import select

from test_affairs_leave import TID, _seed
from test_aid_mobile_queue import _login


def _data(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["code"] == 0, payload
    return payload["data"]


def _seed_student_accounts(ids: dict[str, int]) -> None:
    """为既有请假状态机 fixture 补齐真实学生账号与稳定账号链接。"""
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, StudentAccountLink, User, UserRole

    with get_sessionmaker()() as db:
        role = db.scalar(select(Role).where(
            Role.tenant_id == TID,
            Role.role_code == "STUDENT",
            Role.is_deleted.is_(False),
        ))
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
        for login_name, student_id in (
            ("leave_mobile_student_a", int(ids["sa"])),
            ("leave_mobile_student_b", int(ids["sb"])),
        ):
            user = db.scalar(select(User).where(
                User.tenant_id == TID,
                User.login_name == login_name,
                User.is_deleted.is_(False),
            ))
            if user is None:
                user = User(
                    tenant_id=TID,
                    login_name=login_name,
                    real_name=login_name,
                    user_type="STUDENT",
                    password_hash=hash_password("LeaveMobile-Test-2026!"),
                    status="ACTIVE",
                    must_change_password=False,
                )
                db.add(user)
                db.flush()
            else:
                user.status = "ACTIVE"
                user.must_change_password = False
                user.password_hash = hash_password("LeaveMobile-Test-2026!")
            user_role = db.scalar(select(UserRole).where(
                UserRole.tenant_id == TID,
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            ))
            if user_role is None:
                db.add(UserRole(
                    tenant_id=TID,
                    user_id=user.id,
                    role_id=role.id,
                    status="ACTIVE",
                ))
            else:
                user_role.status = "ACTIVE"
                user_role.is_deleted = False
            link = db.scalar(select(StudentAccountLink).where(
                StudentAccountLink.tenant_id == TID,
                StudentAccountLink.user_id == user.id,
                StudentAccountLink.link_status == "ACTIVE",
                StudentAccountLink.is_deleted.is_(False),
            ))
            if link is None:
                db.add(StudentAccountLink(
                    tenant_id=TID,
                    user_id=user.id,
                    student_id=student_id,
                    link_status="ACTIVE",
                    source="MANUAL",
                    bound_login_name=login_name,
                ))
            else:
                assert int(link.student_id) == student_id
        db.commit()


def _login_student(client, login_name: str) -> dict[str, str]:
    """复用真账号密码链路，不能用 mock 身份替代学生本人解析。"""
    return _login(client, login_name, "STUDENT_MINI")


def _upload(client, headers: dict[str, str], name: str, content: bytes) -> str:
    return _data(client.post(
        "/api/v1/files",
        headers=headers,
        data={"bizType": "AFFAIRS_LEAVE"},
        files={"file": (name, content, "text/plain")},
    ))["fileId"]


def _apply(client, headers: dict[str, str], *, start: str, end: str, file_ids=None) -> dict:
    return _data(client.post(
        "/api/v1/mobile/affairs/leave",
        headers=headers,
        json={
            "leaveType": "PERSONAL",
            "startTime": start,
            "endTime": end,
            "reason": "家庭事务需要本人处理",
            "fileIds": list(file_ids or []),
        },
    ))


def test_mobile_leave_binds_files_paginates_and_rejects_cross_student_access(client, db_mode):
    """同一正式 CsLeave 贯通提交→退回补件→重提→通过，材料不越权。"""
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail, CsLeave, MessageEventOutbox, UnifiedMessage, UnifiedTodo
    from app.models.file import FileBinding, FileObject

    ids = _seed(db_mode)
    _seed_student_accounts(ids)
    student_a = _login_student(client, "leave_mobile_student_a")
    student_b = _login_student(client, "leave_mobile_student_b")
    counselor = _login(client, "counselor01", "TEACHER_MINI")

    # A 不能把 B 的临时文件绑定到自己的请假；fileId 猜测必须由后端拒绝。
    foreign_file = _upload(client, student_b, "foreign.txt", b"other student private evidence")
    denied = client.post("/api/v1/mobile/affairs/leave", headers=student_a, json={
        "leaveType": "PERSONAL", "startTime": "2026-12-10", "endTime": "2026-12-11",
        "reason": "家庭事务需要本人处理", "fileIds": [foreign_file],
    })
    assert denied.status_code == 403, denied.text

    first_file = _upload(client, student_a, "leave-proof-v1.txt", b"leave evidence version one")
    applied = _apply(
        client,
        student_a,
        start="2026-12-10",
        end="2026-12-11",
        file_ids=[first_file],
    )
    leave_id = str(applied["id"])
    assert applied["affairsStatus"] == "COUNSELOR_REVIEW"

    # 不是客户端在 localStorage 记 fileId：业务命令已在同一事务把 TEMP_PRIVATE 转为正式绑定。
    with get_sessionmaker()() as db:
        file_obj = db.get(FileObject, int(first_file))
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == TID,
            FileBinding.file_id == int(first_file),
            FileBinding.biz_type == "AFFAIRS_LEAVE",
            FileBinding.biz_id == leave_id,
            FileBinding.relation_type == "BUSINESS_EVIDENCE",
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
        ))
        assert file_obj and file_obj.visibility == "BIZ_SCOPED"
        assert binding and binding.subject_type == "STUDENT" and int(binding.subject_id) == int(ids["sa"])

    detail = _data(client.get(f"/api/v1/mobile/affairs/leave/{leave_id}/detail", headers=student_a))
    assert [str(item["fileId"]) for item in detail["attachments"]] == [first_file]
    assert client.get(f"/api/v1/mobile/affairs/leave/{leave_id}/detail", headers=student_b).status_code == 404
    assert client.get(f"/api/v1/files/{first_file}", headers=student_b).status_code in {403, 404}

    # 学生列表在服务端分页，既不取全表也不让另一学生混入。
    _apply(client, student_a, start="2026-12-20", end="2026-12-21")
    page_one = _data(client.get(
        "/api/v1/mobile/affairs/leave/my?page=1&pageSize=1", headers=student_a,
    ))
    page_two = _data(client.get(
        "/api/v1/mobile/affairs/leave/my?page=2&pageSize=1", headers=student_a,
    ))
    assert page_one["total"] == 2 and page_one["hasMore"] is True
    assert len(page_one["items"]) == len(page_two["items"]) == 1
    assert page_one["items"][0]["leaveId"] != page_two["items"][0]["leaveId"]
    assert _data(client.get(
        "/api/v1/mobile/affairs/leave/my?page=1&pageSize=1", headers=student_b,
    ))["total"] == 0

    # 退回后仅允许新增本人临时文件；既有材料不能被 body.fileIds 静默解绑。
    # 历史消息积压不能挤掉刚刚退回的学生结果。这里用同一正式 outbox producer
    # 制造比本单更早的待消费事件；请假状态机必须精确领取自己的 outbox ID。
    from app.services.message_event_outbox_service import emit_message_event
    with get_sessionmaker()() as db:
        for index in range(25):
            emit_message_event(
                db,
                tenant_id=TID,
                event_code="LEAVE.CLOSED",
                source_module="student-affairs",
                source_biz_type="leave_queue_fixture",
                source_biz_id=900000 + index,
                recipient_refs=[{"studentId": int(ids["sa"])}],
                title="历史消息积压夹具",
                content="仅用于验证本次请假结果不会被历史队列延迟",
                dedup_key=f"leave-message-backlog:{index}",
            )
        db.commit()

    teacher_detail = _data(client.get(f"/api/v1/student-affairs/leave/{leave_id}", headers=counselor))
    returned = _data(client.post(f"/api/v1/student-affairs/leave/{leave_id}/return", headers=counselor, json={
        "reason": "请补充更清晰的证明材料后重新提交",
        "version": teacher_detail["version"],
    }))
    assert returned["affairsStatus"] == "RETURNED"
    # 退回后是学生本人要处理的工作，不能复用/泄漏教师 LEAVE_APPROVAL 待办。
    # 同时断言 typed deep-link 已由服务端给出，不允许首页再按标题拼 URL。
    pending_todos = _data(client.get(
        "/api/v1/student-mini/todos?status=PENDING", headers=student_a,
    ))
    returned_todo = next(item for item in pending_todos["items"]
                         if item["todoType"] == "LEAVE_STUDENT_RESUBMIT")
    assert returned_todo["sourceBizType"] == "LEAVE"
    assert returned_todo["recordId"] == leave_id
    assert returned_todo["routePath"] == "/pages/student/affairs/leave"
    assert returned_todo["query"]["recordId"] == leave_id
    with get_sessionmaker()() as db:
        returned_outbox = db.scalar(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == TID,
            MessageEventOutbox.source_biz_id == int(leave_id),
            MessageEventOutbox.event_code == "LEAVE.RETURNED",
        ))
        assert returned_outbox and returned_outbox.status == "SUCCEEDED"
    second_file = _upload(client, student_a, "leave-proof-v2.txt", b"leave evidence version two")
    editable = _data(client.get(f"/api/v1/mobile/affairs/leave/{leave_id}/editable", headers=student_a))
    updated = _data(client.put(f"/api/v1/mobile/affairs/leave/{leave_id}/returned", headers=student_a, json={
        "leaveType": "PERSONAL",
        "startTime": "2026-12-10",
        "endTime": "2026-12-11",
        "reason": "已按意见补充清晰证明材料后重新提交",
        "fileIds": [second_file],
        "version": editable["version"],
    }))
    assert updated["allowedActions"] == ["RESUBMIT"]
    resubmitted = _data(client.post(f"/api/v1/mobile/affairs/leave/{leave_id}/resubmit", headers=student_a, json={
        "version": updated["version"],
    }))
    assert resubmitted["affairsStatus"] == "COUNSELOR_REVIEW"
    pending_after_resubmit = _data(client.get(
        "/api/v1/student-mini/todos?status=PENDING", headers=student_a,
    ))
    assert all(item["todoType"] != "LEAVE_STUDENT_RESUBMIT"
               for item in pending_after_resubmit["items"])
    # 小程序消息“待办”标签必须与角标同为 PENDING 口径；不能把刚关闭的退回补正
    # 任务继续渲染成“已完成”，否则学生会误以为还有一项需要处理。
    mobile_todo_page = _data(client.get(
        "/api/v1/mobile/performance/student/messages-page?tab=todo&page=1&pageSize=20",
        headers=student_a,
    ))
    assert all(item.get("todoType") != "LEAVE_STUDENT_RESUBMIT"
               for item in mobile_todo_page["list"])
    final_teacher_detail = _data(client.get(f"/api/v1/student-affairs/leave/{leave_id}", headers=counselor))
    approved = _data(client.post(f"/api/v1/student-affairs/leave/{leave_id}/approve", headers=counselor, json={
        "version": final_teacher_detail["version"],
    }))
    assert approved["affairsStatus"] == "APPROVED"
    final_student_detail = _data(client.get(f"/api/v1/mobile/affairs/leave/{leave_id}/detail", headers=student_a))
    assert final_student_detail["affairsStatus"] == "APPROVED"
    assert {str(item["fileId"]) for item in final_student_detail["attachments"]} == {first_file, second_file}

    with get_sessionmaker()() as db:
        row = db.get(CsLeave, int(leave_id))
        assert row and row.affairs_status == "APPROVED"
        assert db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == TID,
            FileBinding.file_id == int(second_file),
            FileBinding.biz_type == "AFFAIRS_LEAVE",
            FileBinding.biz_id == leave_id,
            FileBinding.status == "ACTIVE",
        )) is not None
        actions = set(db.scalars(select(AffairsAuditTrail.action).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "LEAVE",
            AffairsAuditTrail.biz_id == int(leave_id),
        )).all())
        assert {"APPLY", "RETURNED", "STUDENT_EDIT_RETURNED", "RESUBMIT", "APPROVED"}.issubset(actions)
        todos = list(db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == TID,
            UnifiedTodo.source_biz_type == "LEAVE",
            UnifiedTodo.source_biz_id == int(leave_id),
        )).all())
        assert todos and all(todo.status == "DONE" for todo in todos)
        assert any(todo.todo_type == "LEAVE_STUDENT_RESUBMIT" for todo in todos)
        messages = list(db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TID,
            UnifiedMessage.source_module == "student-affairs",
            UnifiedMessage.source_biz_id == int(leave_id),
            UnifiedMessage.action_key == "AFFAIRS_LEAVE",
        )).all())
        assert len(messages) >= 2 and all(item.delivery_status == "DELIVERED" for item in messages)
        outbox = list(db.scalars(select(MessageEventOutbox).where(
            MessageEventOutbox.tenant_id == TID,
            MessageEventOutbox.source_module == "student-affairs",
            MessageEventOutbox.source_biz_id == int(leave_id),
        )).all())
        assert {"LEAVE.RETURNED", "LEAVE.APPROVED"}.issubset({item.event_code for item in outbox})
        assert all(item.status == "SUCCEEDED" for item in outbox)
