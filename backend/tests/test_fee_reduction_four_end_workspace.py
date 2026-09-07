"""减免与临时补助四端核心流：本人申请、退回补正、批准与结果落实。"""
from __future__ import annotations

from test_aid_material_flow import _data
from test_aid_mobile_queue import _login
from test_funding_application_workspace import _accounts


BASE = "/api/v1"


def _upload(client, headers, name: str) -> dict:
    return _data(client.post(
        f"{BASE}/files", headers=headers,
        files={"file": (name, b"hardship evidence", "text/plain")},
        data={"bizType": "REDUCTION"},
    ))


def _todos(fee_id, pending_type=None):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import UnifiedTodo, User
    from app.services.todo_route_registry import resolve_todo_route
    with get_sessionmaker()() as db:
        rows = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == 1000000000000000001,
            UnifiedTodo.source_biz_type == "FEE_REDUCTION", UnifiedTodo.source_biz_id == int(fee_id),
            UnifiedTodo.is_deleted.is_(False),
        )).all()
        active = [r for r in rows if r.status == "PENDING"]
        assert len(active) == (1 if pending_type else 0)
        if not pending_type:
            return
        row = active[0]
        assert row.todo_type == pending_type
        assert db.get(User, row.assignee_id).login_name == ("fund_student" if pending_type == "FEE_REDUCTION_CORRECTION" else "sa_admin01")
        clients = [("studentPc", "/campus-service"), ("studentMini", "/pages/student/affairs/reduction")] if pending_type == "FEE_REDUCTION_CORRECTION" else [("pc", "/admin/student-affairs/funding/fee-reductions"), ("teacherMini", "/pages/teacher/affairs/reduction/index")]
        for client, path in clients:
            target = resolve_todo_route(row.todo_type, str(fee_id), client=client)
            assert target["path"] == path and target["exact"] is True
            assert target["query"]["recordId"] == str(fee_id)
        return str(row.id)


def test_fee_reduction_four_end_core_flow(client, db_mode):
    ids = _accounts(db_mode)
    admin_pc = _login(client, "school_admin01", "PC")
    admin_mini = _login(client, "school_admin01", "TEACHER_MINI")
    student_pc = _login(client, "fund_student", "PC")
    student_mini = _login(client, "fund_student", "STUDENT_MINI")
    other_pc = _login(client, "fund_other", "PC")

    evidence = _upload(client, student_pc, "temporary-aid-2098.txt")
    assert evidence["readyForBusiness"] is True
    submitted = _data(client.post(f"{BASE}/portal/affairs/fee-reductions", headers=student_pc, json={
        "itemType": "TEMP_AID", "yearCode": "2098-2099", "reasonCategory": "FAMILY_CHANGE",
        "amount": "2600.00", "reason": "家庭主要收入来源突然中断，申请临时困难补助。",
        "attachmentIds": [evidence["fileId"]], "confirm": True,
    }))
    fee_id = submitted["feeId"]
    first_todo = _todos(fee_id, "FEE_REDUCTION_REVIEW")
    receiver = _login(client, "sa_admin01", "TEACHER_MINI")
    inbox = _data(client.get(f"{BASE}/teacher-mobile/todos/grouped-continuous", headers=receiver))
    item = next(t for t in inbox["items"] if str(t["todoId"]) == first_todo)
    assert item["action"]["target"]["path"] == "/pages/teacher/affairs/reduction/index"
    assert item["action"]["target"]["query"]["recordId"] == fee_id
    assert client.post(f"{BASE}/teacher-mobile/todos/{first_todo}/complete", headers=receiver,
                       json={"comment":"不能跳过真实审核"}).status_code >= 400
    assert _todos(fee_id, "FEE_REDUCTION_REVIEW") == first_todo
    assert client.get(f"{BASE}/mobile/teacher/affairs/fee-reductions", headers=student_mini,
                      params={"recordId":fee_id}).status_code == 403

    assert submitted["studentId"] == str(ids["sa"])
    assert submitted["status"] == "SUBMITTED"
    assert submitted["amount"] == "2600.00"
    assert submitted["allowedActions"] == ["WITHDRAW"]
    assert submitted["evidence"][0]["fileId"] == evidence["fileId"]

    mine_mini = _data(client.get(f"{BASE}/mobile/affairs/fee-reductions", headers=student_mini))
    assert next(item for item in mine_mini["items"] if item["feeId"] == fee_id)["status"] == "SUBMITTED"
    assert _data(client.get(f"{BASE}/portal/affairs/fee-reductions", headers=other_pc))["items"] == []
    assert client.get(f"{BASE}/files/{evidence['fileId']}", headers=student_pc).status_code == 200
    assert client.get(f"{BASE}/files/{evidence['fileId']}", headers=admin_pc).status_code == 200
    assert client.get(f"{BASE}/files/{evidence['fileId']}", headers=other_pc).status_code == 404

    duplicate = client.post(f"{BASE}/mobile/affairs/fee-reductions", headers=student_mini, json={
        "itemType": "TEMP_AID", "yearCode": "2098-2099", "reasonCategory": "ACCIDENT",
        "amount": "1000", "reason": "本人突发意外需要新增医疗支出，申请临时帮助。",
        "attachmentIds": [evidence["fileId"]], "confirm": True,
    })
    assert duplicate.status_code == 409

    queue = _data(client.get(
        f"{BASE}/mobile/teacher/affairs/fee-reductions", headers=admin_mini,
        params={"status": "SUBMITTED", "keyword": "甲一", "yearCode": "2098-2099"},
    ))
    target = next(item for item in queue["items"] if item["feeId"] == fee_id)
    assert set(target["allowedActions"]) == {"APPROVE", "RETURN", "REJECT"}
    assert client.post(
        f"{BASE}/mobile/teacher/affairs/fee-reductions/{fee_id}/action", headers=admin_mini,
        json={"action": "RETURN", "opinion": "短", "version": target["version"]},
    ).status_code == 400
    returned = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/fee-reductions/{fee_id}/action", headers=admin_mini,
        json={"action": "RETURN", "opinion": "请补充家庭收入中断时间及对应证明。", "version": target["version"]},
    ))
    assert returned["status"] == "RETURNED"
    _todos(fee_id, "FEE_REDUCTION_CORRECTION")

    returned_mine = next(item for item in _data(client.get(
        f"{BASE}/mobile/affairs/fee-reductions", headers=student_mini))["items"] if item["feeId"] == fee_id)
    replacement = _upload(client, student_mini, "temporary-aid-2098-fixed.txt")
    resubmitted = _data(client.post(
        f"{BASE}/mobile/affairs/fee-reductions/{fee_id}/resubmit", headers=student_mini,
        json={"itemType": "TEMP_AID", "yearCode": "2098-2099", "reasonCategory": "FAMILY_CHANGE",
              "amount": "2600.00", "reason": "家庭收入于九月中断，现补充收入变化证明并申请临时补助。",
              "attachmentIds": [replacement["fileId"]], "confirm": True,
              "version": returned_mine["version"]},
    ))
    assert resubmitted["status"] == "SUBMITTED" and resubmitted["reviewOpinion"] == ""
    assert len(resubmitted["evidence"]) == 2
    assert _todos(fee_id, "FEE_REDUCTION_REVIEW") == first_todo

    approved = _data(client.post(
        f"{BASE}/student-affairs/fee-reductions/{fee_id}/action", headers=admin_pc,
        json={"action": "APPROVE", "opinion": "材料核验通过，同意临时困难补助。",
              "version": resubmitted["version"]},
    ))
    assert approved["status"] == "APPROVED" and approved["allowedActions"] == ["FULFILL"]
    _todos(fee_id, "FEE_REDUCTION_FULFILL")
    assert client.post(
        f"{BASE}/student-affairs/fee-reductions/{fee_id}/action", headers=admin_pc,
        json={"action": "FULFILL", "fulfillmentChannel": "TUITION_LEDGER",
              "version": approved["version"]},
    ).status_code == 400
    fulfilled = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/fee-reductions/{fee_id}/action", headers=admin_mini,
        json={"action": "FULFILL", "fulfillmentChannel": "BANK_TRANSFER",
              "fulfillmentReference": "财务批次 2098-09", "version": approved["version"]},
    ))
    assert fulfilled["status"] == "ISSUED" and fulfilled["statusLabel"] == "补助已发放"
    assert fulfilled["issuedAt"]
    _todos(fee_id)
    final_mine = next(item for item in _data(client.get(
        f"{BASE}/portal/affairs/fee-reductions", headers=student_pc))["items"] if item["feeId"] == fee_id)
    assert final_mine["statusLabel"] == "补助已发放" and final_mine["allowedActions"] == []

    # 临补完成后可因新的突发困难再次申请；同学年学费减免完成后不重复办理。
    later_evidence = _upload(client, student_pc, "temporary-aid-2098-second.txt")
    later = client.post(f"{BASE}/portal/affairs/fee-reductions", headers=student_pc, json={
        "itemType": "TEMP_AID", "yearCode": "2098-2099", "reasonCategory": "SERIOUS_ILLNESS",
        "amount": "1800", "reason": "家庭成员突发重大疾病产生额外支出，申请再次救助。",
        "attachmentIds": [later_evidence["fileId"]], "confirm": True,
    })
    assert later.status_code == 200
    later_row = _data(later)
    _todos(later_row["feeId"], "FEE_REDUCTION_REVIEW")
    withdrawn = _data(client.post(f"{BASE}/mobile/affairs/fee-reductions/{later_row['feeId']}/withdraw",
                                 headers=student_mini, json={"version": later_row["version"]}))
    assert withdrawn["status"] == "WITHDRAWN"
    _todos(later_row["feeId"])
    for prefix, headers in [("student-affairs", admin_pc), ("mobile/teacher/affairs", admin_mini)]:
        exact = _data(client.get(f"{BASE}/{prefix}/fee-reductions", headers=headers, params={"recordId":fee_id}))
        assert [x["feeId"] for x in exact["items"]] == [fee_id]
        absent = _data(client.get(f"{BASE}/{prefix}/fee-reductions", headers=headers, params={"recordId":999999999}))
        assert absent["items"] == []


    reduction = _data(client.post(f"{BASE}/student-affairs/fee-reductions", headers=admin_pc, json={
        "studentId": ids["sb"], "itemType": "REDUCTION", "yearCode": "2098-2099",
        "reasonCategory": "EXTREME_DIFFICULTY", "amount": "3200",
        "reason": "经核实属于特别困难学生，代录学费减免申请。",
    }))
    approved_reduction = _data(client.post(
        f"{BASE}/student-affairs/fee-reductions/{reduction['feeId']}/review", headers=admin_pc,
        json={"action": "APPROVE", "opinion": "同意减免。", "version": reduction["version"]},
    ))
    final_reduction = _data(client.post(
        f"{BASE}/student-affairs/fee-reductions/{reduction['feeId']}/issue", headers=admin_pc,
        json={"version": approved_reduction["version"]},
    ))
    assert final_reduction["statusLabel"] == "减免已确认"

    # 配置缺失不得留下一张无人受理的申请，业务、材料绑定和待办一起回滚。
    from sqlalchemy import func, select
    from app.db.session import get_sessionmaker
    from app.models import FeeReduction, Role, UserRole, UnifiedTodo
    missing_evidence = _upload(client, student_pc, "temporary-aid-no-receiver.txt")
    with get_sessionmaker()() as db:
        count_before = db.scalar(select(func.count()).select_from(FeeReduction))
        role_ids = db.scalars(select(Role.id).where(Role.tenant_id == 1000000000000000001,
            Role.role_code.in_(["FUNDING_TEACHER", "STUDENT_AFFAIRS_ADMIN", "SCHOOL_ADMIN"]))).all()
        links = db.scalars(select(UserRole).where(UserRole.tenant_id == 1000000000000000001,
            UserRole.role_id.in_(role_ids))).all()
        for link in links:
            link.status = "INACTIVE"
        db.commit()
    rejected = client.post(f"{BASE}/portal/affairs/fee-reductions", headers=student_pc, json={
        "itemType":"TEMP_AID", "yearCode":"2098-2099", "reasonCategory":"FAMILY_CHANGE",
        "amount":"600", "reason":"隔离测试验证无受理岗位时不应保存无人处理申请。",
        "attachmentIds":[missing_evidence["fileId"]], "confirm":True,
    })
    assert rejected.status_code >= 400
    assert "受理人" in rejected.json().get("message", "")
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count()).select_from(FeeReduction)) == count_before
        assert db.scalar(select(func.count()).select_from(UnifiedTodo).where(
            UnifiedTodo.source_biz_type == "FEE_REDUCTION", UnifiedTodo.status == "PENDING")) == 0
