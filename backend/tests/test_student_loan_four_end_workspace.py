"""助学贷款四端核心流：本人回执、退回重提、学校核验和台账确认。"""
from __future__ import annotations

from test_aid_material_flow import _data
from test_aid_mobile_queue import _login
from test_funding_application_workspace import _accounts


BASE = "/api/v1"


def _upload_receipt(client, headers, name: str) -> dict:
    return _data(client.post(
        f"{BASE}/files", headers=headers,
        files={"file": (name, b"loan receipt evidence", "text/plain")},
        data={"bizType": "LOAN"},
    ))


def test_student_loan_four_end_core_flow(client, db_mode):
    ids = _accounts(db_mode)
    admin_pc = _login(client, "school_admin01", "PC")
    admin_mini = _login(client, "school_admin01", "TEACHER_MINI")
    student_pc = _login(client, "fund_student", "PC")
    student_mini = _login(client, "fund_student", "STUDENT_MINI")
    other_pc = _login(client, "fund_other", "PC")

    uploaded = _upload_receipt(client, student_pc, "receipt-2092.txt")
    assert uploaded["readyForBusiness"] is True
    submitted = _data(client.post(f"{BASE}/portal/affairs/loans", headers=student_pc, json={
        "loanType": "ORIGIN", "bankName": "国家开发银行", "bankLast4": "2468",
        "yearCode": "2092-2093", "amount": "12000.00", "receiptCode": "GJKF-2092-ABC123",
        "receiptFileId": uploaded["fileId"], "confirm": True,
    }))
    loan_id = submitted["loanId"]
    assert submitted["studentId"] == str(ids["sa"])
    assert submitted["status"] == "RECEIPT"
    assert submitted["amount"] == "12000.00"
    assert submitted["receiptCodeMasked"] == "•••• ABC123"
    assert "GJKF-2092" not in str(submitted)
    assert submitted["receiptFile"]["fileId"] == uploaded["fileId"]

    mine_pc = _data(client.get(f"{BASE}/portal/affairs/loans", headers=student_pc))
    mine_mini = _data(client.get(f"{BASE}/mobile/affairs/loans", headers=student_mini))
    assert mine_pc["policy"]["maxAmount"] == "20000.00"
    assert next(item for item in mine_pc["items"] if item["loanId"] == loan_id)["amount"] == "12000.00"
    assert next(item for item in mine_mini["items"] if item["loanId"] == loan_id)["status"] == "RECEIPT"
    assert _data(client.get(f"{BASE}/portal/affairs/loans", headers=other_pc))["items"] == []

    # 本人及经办教师能读当前回执，其他学生不能枚举该文件。
    assert client.get(f"{BASE}/files/{uploaded['fileId']}", headers=student_pc).status_code == 200
    assert client.get(f"{BASE}/files/{uploaded['fileId']}", headers=admin_pc).status_code == 200
    assert client.get(f"{BASE}/files/{uploaded['fileId']}", headers=other_pc).status_code == 404

    duplicate = client.post(f"{BASE}/mobile/affairs/loans", headers=student_mini, json={
        "loanType": "CAMPUS", "yearCode": "2092-2093", "amount": "10000",
        "receiptCode": "SECOND-2092-XYZ999", "confirm": True,
    })
    assert duplicate.status_code == 409
    assert client.post(f"{BASE}/portal/affairs/loans", headers=student_pc, json={
        "loanType": "ORIGIN", "yearCode": "2094-2096", "amount": "999",
        "receiptCode": "BAD-2094-CODE", "confirm": True,
    }).status_code == 400

    queue = _data(client.get(
        f"{BASE}/mobile/teacher/affairs/loans", headers=admin_mini,
        params={"status": "RECEIPT", "keyword": "甲一", "yearCode": "2092-2093"},
    ))
    target = next(item for item in queue["items"] if item["loanId"] == loan_id)
    assert target["receiptCodeMasked"] == "•••• ABC123"
    assert set(target["allowedActions"]) == {"VERIFY", "RETURN"}

    assert client.post(
        f"{BASE}/mobile/teacher/affairs/loans/{loan_id}/action", headers=admin_mini,
        json={"action": "RETURN", "reason": "短", "version": target["version"]},
    ).status_code == 400
    returned = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/loans/{loan_id}/action", headers=admin_mini,
        json={"action": "RETURN", "reason": "回执学年与申请信息不一致，请修正后重提。", "version": target["version"]},
    ))
    assert returned["status"] == "RETURNED"
    returned_mine = next(item for item in _data(client.get(
        f"{BASE}/mobile/affairs/loans", headers=student_mini))["items"] if item["loanId"] == loan_id)
    assert returned_mine["reviewOpinion"].startswith("回执学年")
    assert returned_mine["allowedActions"] == ["RESUBMIT"]

    replacement = _upload_receipt(client, student_mini, "receipt-2092-fixed.txt")
    resubmitted = _data(client.post(
        f"{BASE}/mobile/affairs/loans/{loan_id}/resubmit", headers=student_mini,
        json={"loanType": "ORIGIN", "bankName": "国家开发银行", "bankLast4": "2468",
              "yearCode": "2092-2093", "amount": "12000.00", "receiptCode": "GJKF-2092-FIX456",
              "receiptFileId": replacement["fileId"], "confirm": True, "version": returned_mine["version"]},
    ))
    assert resubmitted["status"] == "RECEIPT" and resubmitted["reviewOpinion"] == ""
    assert resubmitted["receiptFile"]["fileId"] == replacement["fileId"]

    verified = _data(client.post(
        f"{BASE}/student-affairs/loans/{loan_id}/action", headers=admin_pc,
        json={"action": "VERIFY", "reason": "已核对学生、学年、金额和回执材料。",
              "version": resubmitted["version"]},
    ))
    assert verified["status"] == "VERIFIED" and verified["verifiedAt"]
    stale = client.post(
        f"{BASE}/student-affairs/loans/{loan_id}/action", headers=admin_pc,
        json={"action": "CONFIRM", "version": resubmitted["version"]},
    )
    assert stale.status_code == 409
    confirmed = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/loans/{loan_id}/action", headers=admin_mini,
        json={"action": "CONFIRM", "version": verified["version"]},
    ))
    assert confirmed["status"] == "CONFIRMED" and confirmed["confirmedAt"]
    final_mine = next(item for item in _data(client.get(
        f"{BASE}/portal/affairs/loans", headers=student_pc))["items"] if item["loanId"] == loan_id)
    assert final_mine["status"] == "CONFIRMED" and final_mine["allowedActions"] == []
    assert client.post(
        f"{BASE}/portal/affairs/loans/{loan_id}/withdraw", headers=student_pc,
        json={"version": final_mine["version"]},
    ).status_code == 409

    # 教师可为纸质来件先建档，再由本人补录电子回执；撤回后允许同学年重新提交。
    proxy = _data(client.post(f"{BASE}/student-affairs/loans", headers=admin_pc, json={
        "studentId": ids["sb"], "loanType": "CAMPUS", "bankName": "中国银行",
        "yearCode": "2097-2098", "amount": "8000.00",
    }))
    assert proxy["status"] == "REGISTERED" and proxy["allowedActions"] == ["SUBMIT_RECEIPT"]
    proxy_receipt = _upload_receipt(client, other_pc, "receipt-2097.txt")
    completed_proxy = _data(client.post(
        f"{BASE}/portal/affairs/loans/{proxy['loanId']}/resubmit", headers=other_pc,
        json={"receiptCode": "CAMPUS-2097-RET789", "receiptFileId": proxy_receipt["fileId"],
              "confirm": True, "version": proxy["version"]},
    ))
    withdrawn = _data(client.post(
        f"{BASE}/portal/affairs/loans/{proxy['loanId']}/withdraw", headers=other_pc,
        json={"version": completed_proxy["version"]},
    ))
    assert withdrawn["status"] == "WITHDRAWN"
    replacement_record = _data(client.post(f"{BASE}/portal/affairs/loans", headers=other_pc, json={
        "loanType": "ORIGIN", "bankName": "国家开发银行", "yearCode": "2097-2098",
        "amount": "9000.00", "receiptCode": "GJKF-2097-NEW999", "confirm": True,
    }))
    assert replacement_record["status"] == "RECEIPT"
