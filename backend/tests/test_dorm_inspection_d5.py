"""D5 宿舍检查 → 整改 → 复检闭环（真实 MySQL）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from affairs_contract_test_support import role_headers


TID = 1000000000000000001
PC = "/api/v1/student-affairs"
MOBILE = "/api/v1/mobile"


def _student_headers(user_id: int) -> dict[str, str]:
    """复用正式登录签发，避免手拼 token 绕过租户/权限版本契约。"""
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services import auth_service_db

    db = get_sessionmaker()()
    try:
        user = db.get(User, int(user_id))
        assert user is not None
        token = auth_service_db.build_login_result(
            db, user, client_type="STUDENT_MINI",
        )["accessToken"]
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def _temporary_photo(owner_user_id: int, suffix: str, *, scan_status: str = "CLEAN") -> str:
    from app.db.session import get_sessionmaker
    from app.models import FileObject

    db = get_sessionmaker()()
    try:
        ready = scan_status in {"CLEAN", "NOT_REQUIRED"}
        row = FileObject(
            tenant_id=TID,
            file_key=f"d5/{suffix}.jpg",
            file_name=f"{suffix}.jpg",
            ext="jpg",
            mime_type="image/jpeg",
            size_bytes=256,
            sha256=(suffix.encode("utf-8").hex() * 64)[:64].ljust(64, "a"),
            biz_type="TEMP_PRIVATE",
            biz_id=None,
            owner_user_id=owner_user_id,
            visibility="PRIVATE",
            security_level="INTERNAL",
            status="AVAILABLE" if ready else "QUARANTINED",
            storage_backend="local",
            storage_zone="ACTIVE" if ready else "QUARANTINE",
            upload_source="USER",
            scan_required=scan_status != "NOT_REQUIRED",
            scan_status=scan_status,
            available_at=datetime.utcnow() if ready else None,
        )
        db.add(row)
        db.commit()
        return str(row.id)
    finally:
        db.close()


def _create_building(client, admin, *, name: str, manager: str) -> tuple[str, str, str]:
    response = client.post(f"{PC}/dorm/buildings", headers=admin, json={
        "buildingName": name,
        "buildingCode": name,
        "genderLimit": "MALE",
        "managerTeacherKey": manager,
    })
    assert response.status_code == 200, response.text
    building_id = response.json()["data"]["buildingId"]
    generated = client.post(
        f"{PC}/dorm/buildings/{building_id}/generate",
        headers=admin,
        json={"floors": 2, "roomsPerFloor": 2, "bedsPerRoom": 2},
    )
    assert generated.status_code == 200, generated.text
    rooms = client.get(
        f"{PC}/dorm/buildings/{building_id}/rooms?floor=1", headers=admin,
    ).json()["data"]["items"]
    room_id = rooms[0]["roomId"]
    bed_id = client.get(
        f"{PC}/dorm/rooms/{room_id}/beds", headers=admin,
    ).json()["data"]["items"][0]["bedId"]
    return str(building_id), str(room_id), str(bed_id)


def test_d5_four_end_inspection_rectification_recheck_and_negative_gates(client, db_mode):
    """DG12/13/14 + D-N09：真实四端闭环、证据、消息、CAS、幂等、范围和风险阈值。"""
    from app.db.session import get_sessionmaker
    from app.models import Role, StudentAccountLink, StudentProfile, User, UserRole

    admin = role_headers("SCHOOL_ADMIN", login_name="school_admin01", real_name="陈校")
    manager = role_headers("DORM_MANAGER", login_name="dorm01", real_name="宿管·李")
    other_manager = role_headers("DORM_MANAGER", login_name="other", real_name="宿管·王")

    db = get_sessionmaker()()
    try:
        student = db.get(StudentProfile, int(db_mode["student"]))
        assert student is not None
        student.student_no = "D5-RECTIFY-001"
        student.real_name = "D5整改学生"
        student.gender = "M"
        student.status = "ACTIVE"
        student_user = User(
            tenant_id=TID,
            login_name=student.student_no,
            real_name=student.real_name,
            password_hash="test-only",
            user_type="STUDENT",
            status="ACTIVE",
        )
        db.add(student_user)
        db.flush()
        db.add(StudentAccountLink(
            tenant_id=TID,
            student_id=student.id,
            user_id=student_user.id,
            link_status="ACTIVE",
            bound_login_name=student_user.login_name,
            bound_student_no=student.student_no,
            source="MANUAL",
            bound_at=datetime.utcnow(),
        ))
        student_role = db.query(Role).filter_by(
            tenant_id=TID, role_code="STUDENT",
        ).first()
        if student_role is None:
            student_role = Role(
                tenant_id=TID,
                role_code="STUDENT",
                role_name="学生",
                role_type="SYSTEM",
                status="ACTIVE",
            )
            db.add(student_role)
            db.flush()
        db.add(UserRole(
            tenant_id=TID,
            user_id=student_user.id,
            role_id=student_role.id,
            status="ACTIVE",
        ))
        db.commit()
        student_id = int(student.id)
        student_user_id = int(student_user.id)
        manager_user_id = int(db.query(User).filter_by(
            tenant_id=TID, login_name="dorm01",
        ).one().id)
        other_manager_user_id = int(db.query(User).filter_by(
            tenant_id=TID, login_name="other",
        ).one().id)
    finally:
        db.close()
    student_mobile = _student_headers(student_user_id)

    building_id, room_id, bed_id = _create_building(
        client, admin, name="D5安全检查楼", manager="dorm01",
    )
    other_building_id, _, _ = _create_building(
        client, admin, name="D5越权校验楼", manager="other",
    )
    assert client.post(
        f"{PC}/dorm/beds/{bed_id}/checkin",
        headers=admin,
        json={"studentId": str(student_id)},
    ).status_code == 200

    templates = client.get(f"{PC}/dorm/inspection-templates", headers=admin)
    assert templates.status_code == 200, templates.text
    template_data = templates.json()["data"]
    assert template_data["configKey"] == "DORM_INSPECTION_POLICY"
    assert {row["checkType"] for row in template_data["items"]} == {
        "HYGIENE", "SAFETY", "CONTRABAND", "NIGHT_ABSENCE",
        "FIRE_SAFETY", "FACILITY", "OTHER",
    }
    assert template_data["riskSeverities"] == ["HIGH", "CRITICAL"]

    task_body = {
        "taskName": "D5用电消防安全巡检",
        "buildingId": building_id,
        "checkType": "SAFETY",
        "floorScope": [1],
        "templateKey": "DORM-SAFETY-DEFAULT",
        "templateVersion": 1,
        "plannedAt": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "checkerUserId": str(manager_user_id),
        "clientRequestId": "d5-task-safety-0001",
    }
    created_task = client.post(f"{PC}/dorm/check-tasks", headers=admin, json=task_body)
    assert created_task.status_code == 200, created_task.text
    task = created_task.json()["data"]
    assert task["status"] == "RUNNING"
    assert task["floorScope"] == [1]
    assert task["templateKey"] == "DORM-SAFETY-DEFAULT"
    replay_task = client.post(f"{PC}/dorm/check-tasks", headers=admin, json=task_body)
    assert replay_task.status_code == 200
    assert replay_task.json()["data"]["taskId"] == task["taskId"]
    conflict_body = {**task_body, "taskName": "同一幂等号的另一任务"}
    assert client.post(f"{PC}/dorm/check-tasks", headers=admin, json=conflict_body).status_code == 409

    visible_tasks = client.get(
        f"{MOBILE}/teacher/affairs/dorm/check-tasks?status=RUNNING", headers=manager,
    )
    assert visible_tasks.status_code == 200, visible_tasks.text
    assert task["taskId"] in {row["taskId"] for row in visible_tasks.json()["data"]["items"]}
    forbidden_task = client.post(f"{PC}/dorm/check-tasks", headers=manager, json={
        **task_body,
        "taskName": "越权楼栋检查",
        "buildingId": other_building_id,
        "checkerUserId": str(other_manager_user_id),
        "clientRequestId": "d5-task-cross-scope-0001",
    })
    assert forbidden_task.status_code == 403, forbidden_task.text

    item_results = [
        {"itemCode": "ELECTRIC", "status": "FAIL", "score": 0, "note": "发现违规大功率电器"},
        {"itemCode": "FIRE_PASSAGE", "status": "PASS", "score": 35},
        {"itemCode": "CONTRABAND", "status": "PASS", "score": 30},
    ]
    pending_file = _temporary_photo(manager_user_id, "pending-inspection", scan_status="PENDING")
    infected_file = _temporary_photo(manager_user_id, "infected-inspection", scan_status="INFECTED")
    for suffix, file_id in (("pending", pending_file), ("infected", infected_file)):
        rejected = client.post(
            f"{MOBILE}/teacher/affairs/dorm/check-tasks/{task['taskId']}/records",
            headers=manager,
            json={
                "roomId": room_id,
                "result": "ABNORMAL",
                "issueType": "SAFETY",
                "detail": "宿舍违规使用大功率电器，须立即断电整改",
                "studentId": str(student_id),
                "fileIds": [file_id],
                "itemResults": item_results,
                "clientRequestId": f"d5-record-{suffix}-0001",
            },
        )
        assert rejected.status_code == 400, rejected.text
        assert rejected.json()["bizCode"] == "FILE_NOT_READY"

    inspection_file = _temporary_photo(manager_user_id, "clean-inspection")
    record_body = {
        "roomId": room_id,
        "result": "ABNORMAL",
        "issueType": "SAFETY",
        "detail": "宿舍违规使用大功率电器，须立即断电整改",
        "studentId": str(student_id),
        "fileIds": [inspection_file],
        "itemResults": item_results,
        "clientRequestId": "d5-record-safety-0001",
    }
    recorded = client.post(
        f"{MOBILE}/teacher/affairs/dorm/check-tasks/{task['taskId']}/records",
        headers=manager,
        json=record_body,
    )
    assert recorded.status_code == 200, recorded.text
    record = recorded.json()["data"]
    assert record["result"] == "ABNORMAL" and record["severity"] == "HIGH"
    assert record["fileIds"] == [inspection_file]
    assert record["relatedRiskId"] and record["rectificationId"]
    replay_record = client.post(
        f"{MOBILE}/teacher/affairs/dorm/check-tasks/{task['taskId']}/records",
        headers=manager,
        json=record_body,
    )
    assert replay_record.status_code == 200
    assert replay_record.json()["data"]["recordId"] == record["recordId"]

    student_list = client.get(
        f"{MOBILE}/affairs/dorm/rectifications/my?status=PENDING", headers=student_mobile,
    )
    assert student_list.status_code == 200, student_list.text
    student_rows = student_list.json()["data"]["items"]
    assert [row["rectificationId"] for row in student_rows] == [record["rectificationId"]]
    rect = student_rows[0]
    assert rect["status"] == "OPEN" and rect["allowedActions"] == ["START", "SUBMIT"]
    started = client.post(
        f"{MOBILE}/affairs/dorm/rectifications/{rect['rectificationId']}/start",
        headers=student_mobile,
        json={"expectedVersion": rect["version"]},
    )
    assert started.status_code == 200, started.text
    started_rect = started.json()["data"]
    assert started_rect["status"] == "RECTIFYING"
    stale_start = client.post(
        f"{MOBILE}/affairs/dorm/rectifications/{rect['rectificationId']}/start",
        headers=student_mobile,
        json={"expectedVersion": rect["version"]},
    )
    assert stale_start.status_code == 409

    rectification_file = _temporary_photo(student_user_id, "student-rectification")
    submit_body = {
        "expectedVersion": started_rect["version"],
        "note": "已移除违规电器并完成宿舍用电安全自查",
        "fileIds": [rectification_file],
        "clientRequestId": "d5-rectify-submit-0001",
    }
    submitted = client.post(
        f"{MOBILE}/affairs/dorm/rectifications/{rect['rectificationId']}/submit",
        headers=student_mobile,
        json=submit_body,
    )
    assert submitted.status_code == 200, submitted.text
    waiting = submitted.json()["data"]
    assert waiting["status"] == "WAITING_RECHECK"
    assert [row["fileId"] for row in waiting["rectificationFiles"]] == [rectification_file]
    exact_replay = client.post(
        f"{MOBILE}/affairs/dorm/rectifications/{rect['rectificationId']}/submit",
        headers=student_mobile,
        json=submit_body,
    )
    assert exact_replay.status_code == 200
    assert exact_replay.json()["data"]["status"] == "WAITING_RECHECK"
    changed_replay = client.post(
        f"{MOBILE}/affairs/dorm/rectifications/{rect['rectificationId']}/submit",
        headers=student_mobile,
        json={**submit_body, "note": "复用幂等号但恶意改变整改内容"},
    )
    assert changed_replay.status_code == 409

    recheck_file = _temporary_photo(manager_user_id, "manager-recheck")
    passed = client.post(
        f"{MOBILE}/teacher/affairs/dorm/rectifications/{rect['rectificationId']}/recheck",
        headers=manager,
        json={
            "expectedVersion": waiting["version"],
            "action": "PASS",
            "note": "现场复检确认违规电器已移除，用电环境恢复正常",
            "fileIds": [recheck_file],
        },
    )
    assert passed.status_code == 200, passed.text
    closed = passed.json()["data"]
    assert closed["status"] == "CLOSED" and closed["allowedActions"] == []
    assert [row["fileId"] for row in closed["recheckFiles"]] == [recheck_file]
    stale_recheck = client.post(
        f"{MOBILE}/teacher/affairs/dorm/rectifications/{rect['rectificationId']}/recheck",
        headers=manager,
        json={
            "expectedVersion": waiting["version"],
            "action": "PASS",
            "note": "重复复检必须被状态机拒绝",
            "fileIds": [],
        },
    )
    assert stale_recheck.status_code == 409

    hygiene_task = client.post(f"{PC}/dorm/check-tasks", headers=admin, json={
        "taskName": "D5房间卫生检查",
        "buildingId": building_id,
        "checkType": "HYGIENE",
        "floorScope": [1],
        "templateKey": "DORM-HYGIENE-DEFAULT",
        "clientRequestId": "d5-task-hygiene-0001",
    })
    assert hygiene_task.status_code == 200, hygiene_task.text
    hygiene_task_id = hygiene_task.json()["data"]["taskId"]
    hygiene = client.post(
        f"{MOBILE}/teacher/affairs/dorm/check-tasks/{hygiene_task_id}/records",
        headers=manager,
        json={
            "roomId": room_id,
            "result": "ABNORMAL",
            "detail": "地面有少量纸屑，需要当天完成清洁",
            "itemResults": [
                {"itemCode": "FLOOR", "status": "FAIL", "score": 0},
                {"itemCode": "DESK", "status": "PASS", "score": 20},
                {"itemCode": "BED", "status": "PASS", "score": 20},
                {"itemCode": "BALCONY", "status": "PASS", "score": 20},
                {"itemCode": "WASTE", "status": "PASS", "score": 20},
            ],
            "fileIds": [],
            "clientRequestId": "d5-record-hygiene-0001",
        },
    )
    assert hygiene.status_code == 200, hygiene.text
    hygiene_record = hygiene.json()["data"]
    assert hygiene_record["severity"] == "LOW"
    assert hygiene_record["relatedRiskId"] == ""

    from app.models import (
        AffairsRiskRecord, CsDormException, DormCheckRecord, DormCheckTask,
        DormRectification, MessageEventOutbox, UnifiedTodo,
    )
    from app.models.file import FileBinding, FileObject

    db = get_sessionmaker()()
    try:
        stored_task = db.get(DormCheckTask, int(task["taskId"]))
        assert stored_task.template_snapshot_json["templateKey"] == "DORM-SAFETY-DEFAULT"
        assert stored_task.template_snapshot_json["riskSeverities"] == ["HIGH", "CRITICAL"]
        stored_record = db.get(DormCheckRecord, int(record["recordId"]))
        stored_rect = db.get(DormRectification, int(rect["rectificationId"]))
        assert stored_record.status == "CLOSED"
        assert stored_rect.status == "CLOSED" and stored_rect.student_id == student_id
        exception = db.get(CsDormException, int(stored_rect.related_exception_id))
        assert exception.status == "HANDLED"

        risks = db.query(AffairsRiskRecord).filter_by(tenant_id=TID, source="DORM").all()
        assert len(risks) == 1
        assert risks[0].student_id == student_id
        assert risks[0].source_ref_id == stored_rect.id
        hygiene_rect = db.get(DormRectification, int(hygiene_record["rectificationId"]))
        assert hygiene_rect.student_id is None and hygiene_rect.related_risk_id is None
        assert not db.query(AffairsRiskRecord).filter_by(
            tenant_id=TID, source="DORM", student_id=0,
        ).first()

        bindings = db.query(FileBinding).filter(
            FileBinding.tenant_id == TID,
            FileBinding.file_id.in_([
                int(inspection_file), int(rectification_file), int(recheck_file),
            ]),
        ).all()
        assert {(row.biz_type, row.relation_type) for row in bindings} == {
            ("DORM_CHECK_RECORD", "INSPECTION_EVIDENCE"),
            ("DORM_RECTIFICATION", "RECTIFICATION_EVIDENCE"),
            ("DORM_RECTIFICATION", "RECHECK_EVIDENCE"),
        }
        assert all(db.get(FileObject, row.file_id).visibility == "BIZ_SCOPED" for row in bindings)
        assert not db.query(FileBinding).filter(
            FileBinding.file_id.in_([int(pending_file), int(infected_file)]),
        ).first()

        todos = db.query(UnifiedTodo).filter_by(
            tenant_id=TID,
            source_module="student-affairs",
            source_biz_type="DORM_RECTIFICATION",
            source_biz_id=stored_rect.id,
        ).all()
        assert {(row.todo_type, row.status) for row in todos} == {
            ("DORM_RECTIFICATION", "DONE"),
            ("DORM_RECTIFICATION_RECHECK", "DONE"),
        }
        assert any(row.assignee_id == student_user_id for row in todos)
        assert any(row.assignee_id == manager_user_id for row in todos)

        event_codes = {
            row.event_code for row in db.query(MessageEventOutbox).filter_by(
                tenant_id=TID,
                source_biz_type="DORM_RECTIFICATION",
                source_biz_id=stored_rect.id,
            ).all()
        }
        assert {"DORM.RECTIFICATION.CREATED", "DORM.RECTIFICATION.CLOSED"} <= event_codes
    finally:
        db.close()

    assert other_manager_user_id > 0
