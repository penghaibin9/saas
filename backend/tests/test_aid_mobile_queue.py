"""Exercise the real queue past the former 100-row cap and through a mobile review."""
from sqlalchemy import select

from test_affairs_aid import BASE, TID, _apply, _open_batch, _seed

MOBILE = "/api/v1/mobile/teacher/affairs/aid"


def _login(client, name, client_type):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User
    with get_sessionmaker()() as db:
        user = db.scalar(select(User).where(User.login_name == name, User.tenant_id == TID))
        user.password_hash = hash_password("AidQueue-Test-2026!")
        db.commit()
    response = client.post("/api/v1/auth/login", json={"loginName": name,
        "password": "AidQueue-Test-2026!", "clientType": client_type})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}


def test_queue_filters_before_paging_and_agrees_with_review_authority(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, StudentProfile, UnifiedTodo, User, WorkflowTask

    ids = _seed(db_mode)
    admin, counselor = _login(client, "school_admin01", "PC"), _login(client, "counselor01", "TEACHER_MINI")
    batch_id = _open_batch(client, admin)
    real = _apply(client, admin, batch_id, ids["sa"]).json()["data"]
    expected = {real["applyId"]}
    with get_sessionmaker()() as db:
        owner = db.scalar(select(User.id).where(User.login_name == "counselor01"))
        other = db.scalar(select(User.id).where(User.login_name == "counselor02"))
        school = db.scalar(select(User.id).where(User.login_name == "school_admin01"))
        college_id = db.get(StudentProfile, ids["sa"]).college_id
        # 130 pending + newer terminal, unassigned-to-this-teacher, other-class,
        # wrong-node and missing-todo records. No production data or policy is used.
        for i in range(145):
            student = StudentProfile(tenant_id=TID, student_no=f"QUEUE{i:03}",
                real_name="含%字符" if i == 0 else f"队列学生{i:03}",
                college_id=college_id, class_id=ids["B"] if i == 140 else ids["A"],
                current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
            db.add(student); db.flush()
            status = "CLASS_REVIEW" if i < 130 or i in (139, 140, 142) else (
                "ADJUST_REVIEW" if i == 143 else "COLLEGE_REVIEW" if i == 141 else "APPROVED")
            row = AidApply(tenant_id=TID, batch_id=int(batch_id), student_id=student.id,
                status=status, apply_level="DIFFICULT", statement="只应出现在授权单笔详情的家庭情况")
            db.add(row); db.flush()
            if i < 130:
                expected.add(str(row.id))
            if i == 143:
                adjust_id = str(row.id)
            if i != 142:
                db.add(UnifiedTodo(tenant_id=TID, source_module="student-affairs",
                    source_biz_type="AID", source_biz_id=row.id, student_id=student.id,
                    todo_type="AID_ADJUST" if i == 143 else "AID_APPROVAL",
                    assignee_id=other if i == 139 else school if i in (141, 143) else owner,
                    title="隔离测试待办", status="PENDING"))
        db.commit()

    seen = []
    for page in range(1, 8):
        result = client.get(f"{MOBILE}/pending", headers=counselor,
            params={"page": page, "pageSize": 20, "kind": "AID_APPROVAL"})
        assert result.status_code == 200, result.text
        data = result.json()["data"]
        assert data["total"] == 131, data
        assert len(data["list"]) == (11 if page == 7 else 20)
        for row in data["list"]:
            seen.append(row["applyId"])
            assert row["allowedActions"] == ["APPROVE", "RETURN", "REJECT"]
            assert "statement" not in row and "annualIncome" not in row
            assert row["version"] is not None
    assert len(seen) == len(set(seen)) == 131
    assert set(seen) == expected

    found = client.get(f"{MOBILE}/pending", headers=counselor,
        params={"keyword": "%", "kind": "AID_APPROVAL"}).json()["data"]
    assert found["total"] == 1, found
    assert found["list"][0]["realName"] == "含%字符"
    assert client.get(f"{MOBILE}/pending", headers=counselor,
        params={"kind": "AID_ADJUST"}).json()["data"]["total"] == 0
    adjusts = client.get(f"{MOBILE}/pending", headers=admin,
        params={"kind": "AID_ADJUST"}).json()["data"]
    assert [r["applyId"] for r in adjusts["list"]] == [adjust_id]
    assert adjusts["list"][0]["allowedActions"] == ["APPROVE", "REJECT"]
    for params in ({"page": 0}, {"pageSize": 101}, {"kind": "UNKNOWN"}):
        assert client.get(f"{MOBILE}/pending", headers=counselor, params=params).status_code == 400

    # A transferred workflow task wins over the old pending todo's assignee.
    with get_sessionmaker()() as db:
        row = db.get(AidApply, int(real["applyId"]))
        task = db.scalar(select(WorkflowTask).where(WorkflowTask.instance_id == row.workflow_instance_id,
            WorkflowTask.status == "PENDING").order_by(WorkflowTask.id.desc()))
        task.assignee_id = other
        db.commit()
    assert client.get(f"{MOBILE}/pending", headers=counselor).json()["data"]["total"] == 130
    detail = client.get(f"{MOBILE}/{real['applyId']}", headers=counselor).json()["data"]
    assert detail["allowedActions"] == []
    denied = client.post(f"{MOBILE}/{real['applyId']}/review", headers=counselor,
        json={"action": "APPROVE", "version": real["version"]})
    assert denied.status_code == 403, denied.text
    with get_sessionmaker()() as db:
        task = db.get(WorkflowTask, task.id)
        task.assignee_id = owner
        db.commit()
    for _ in range(2):
        detail = client.get(f"{MOBILE}/{real['applyId']}", headers=counselor).json()["data"]
        assert "APPROVE" in detail["allowedActions"]
        result = client.post(f"{MOBILE}/{real['applyId']}/review", headers=counselor,
            json={"action": "APPROVE", "version": detail["version"]})
        assert result.status_code == 200, result.text
    final = client.get(f"{BASE}/aid/applications/{real['applyId']}", headers=admin).json()["data"]
    assert final["status"] == "COLLEGE_REVIEW"
    assert client.get(f"{MOBILE}/{real['applyId']}", headers=counselor).json()["data"]["allowedActions"] == []
    assert client.get(f"{MOBILE}/pending", headers=counselor).json()["data"]["total"] == 130
