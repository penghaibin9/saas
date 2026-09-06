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

    approved = _data(client.post(
        f"{BASE}/student-affairs/fee-reductions/{fee_id}/action", headers=admin_pc,
        json={"action": "APPROVE", "opinion": "材料核验通过，同意临时困难补助。",
              "version": resubmitted["version"]},
    ))
    assert approved["status"] == "APPROVED" and approved["allowedActions"] == ["FULFILL"]
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
