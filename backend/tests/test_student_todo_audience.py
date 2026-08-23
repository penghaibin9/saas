"""学生待办 audience 回归：student_id 是业务主体，不是收件人。

真实 MySQL 下故意让 StudentProfile.id 与 User-style assignee id 完全不同：
- 老师待办：student_id=该生，但 assignee_id=老师 → 学生不可见；
- 学生待办：student_id=该生，assignee_id=当前学生 User.id → 学生可见；
- 他人待办：student_id=该生，assignee_id=另一个人 → 学生不可见。

这锁死“subject != audience”，避免请假/奖助/违纪等老师待办因为关联了学生就泄漏到学生端。
"""
from __future__ import annotations

TID = 1000000000000000001
STUDENT_USER_ID = 62001
TEACHER_USER_ID = 51001
OTHER_USER_ID = 62002
STUDENT_NO = "AUD-STU-001"


def _student_headers():
    from app.core.security import create_access_token

    token = create_access_token({
        "userId": f"u_{STUDENT_USER_ID}",
        "loginName": "aud_student",
        "realName": "受众测试学生",
        "studentNo": STUDENT_NO,
        "userType": "STUDENT",
        "tid": "demo",
        "tenantId": str(TID),
        "activeContextId": "ctx_student",
        "currentRoleCode": "STUDENT",
        "clientType": "STUDENT_MINI",
    })
    return {"Authorization": f"Bearer {token}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, UnifiedTodo

    db = get_sessionmaker()()
    try:
        student = StudentProfile(
            tenant_id=TID,
            student_no=STUDENT_NO,
            real_name="受众测试学生",
            current_stage="ON_CAMPUS",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        assert int(student.id) != STUDENT_USER_ID, "测试必须证明学籍主键与用户主键不能混用"

        staff_todo = UnifiedTodo(
            tenant_id=TID,
            source_module="student-affairs",
            source_biz_type="LEAVE",
            source_biz_id=81001,
            todo_type="LEAVE_APPROVAL",
            assignee_id=TEACHER_USER_ID,
            student_id=student.id,
            title="老师处理：该生请假审批",
            status="PENDING",
        )
        student_todo = UnifiedTodo(
            tenant_id=TID,
            source_module="student-portal",
            source_biz_type="PROFILE",
            source_biz_id=81002,
            todo_type="PROFILE_CONFIRM",
            assignee_id=STUDENT_USER_ID,
            student_id=student.id,
            title="学生本人处理：确认个人资料",
            status="PENDING",
        )
        other_todo = UnifiedTodo(
            tenant_id=TID,
            source_module="student-affairs",
            source_biz_type="AID",
            source_biz_id=81003,
            todo_type="AID_APPROVAL",
            assignee_id=OTHER_USER_ID,
            student_id=student.id,
            title="他人处理：该生困难认定",
            status="PENDING",
        )
        db.add_all([staff_todo, student_todo, other_todo])
        db.commit()
        return {
            "staffTodoId": staff_todo.id,
            "studentTodoId": student_todo.id,
            "otherTodoId": other_todo.id,
        }
    finally:
        db.close()


def test_student_list_only_contains_explicitly_assigned_todo(client, db_mode):
    ids = _seed(db_mode)
    response = client.get(
        "/api/v1/student-mini/todos",
        headers=_student_headers(),
        params={"status": "PENDING"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    items = body["data"]["items"]
    titles = {x["title"] for x in items}
    assert "学生本人处理：确认个人资料" in titles
    assert "老师处理：该生请假审批" not in titles, "student_id subject 被错误当成学生 audience"
    assert "他人处理：该生困难认定" not in titles, "他人 assignee 待办泄漏给学生"
    assert body["data"]["total"] == 1

    count = client.get("/api/v1/student-mini/todos/count", headers=_student_headers()).json()
    assert count["code"] == 0
    assert count["data"]["total"] == 1

    # 详情也必须复用同一 audience 口径；不可见对象统一 404 隐身。
    staff_detail = client.get(
        f"/api/v1/student-mini/todos/{ids['staffTodoId']}", headers=_student_headers()
    )
    own_detail = client.get(
        f"/api/v1/student-mini/todos/{ids['studentTodoId']}", headers=_student_headers()
    )
    assert staff_detail.status_code == 404, staff_detail.text
    assert own_detail.status_code == 200 and own_detail.json()["code"] == 0, own_detail.text
