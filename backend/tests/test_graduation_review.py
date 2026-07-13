"""毕业设计中心 · 查重记录 + 教师评阅测试：检测中→回填结果→超标复查审核 + 评阅分配(SoD)→提交→退回重评。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_PLAG = "/api/v1/graduation/gd-plagiarism"
GD_REVIEW = "/api/v1/graduation/gd-reviews"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(client, h, no, name, advisor=None):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    if advisor:
        client.post(f"{GD_STU}/{gid}/assign-advisor", headers=h, json={"advisorName": advisor})
    return gid


def test_plagiarism_submit_result_dispute(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "PL001", "查重测试生")
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationFinal
    db = get_sessionmaker()()
    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), status="PENDING_REVIEW",
        plagiarism_status="未检测", attachments_json=["bound-thesis-file"],
    )
    db.add(final)
    db.commit()
    final_id = str(final.id)
    db.close()

    submit = client.post(f"{GD_PLAG}/{gid}/submit", headers=h, json={"gdFinalId": final_id})
    assert submit.json()["data"]["status"] == "CHECKING"
    pid = submit.json()["data"]["id"]

    duplicate_submit = client.post(f"{GD_PLAG}/{gid}/submit", headers=h, json={"gdFinalId": final_id})
    assert duplicate_submit.json()["data"]["id"] == pid

    bad_rate = client.post(f"{GD_PLAG}/{pid}/result", headers=h, json={"rate": "abc"})
    assert bad_rate.json()["code"] != 0
    out_of_range = client.post(f"{GD_PLAG}/{pid}/result", headers=h, json={"rate": "101"})
    assert out_of_range.json()["code"] != 0
    unsafe_url = client.post(
        f"{GD_PLAG}/{pid}/result", headers=h,
        json={"rate": "35", "reportUrl": "javascript:alert(1)"},
    )
    assert unsafe_url.json()["code"] != 0

    result = client.post(f"{GD_PLAG}/{pid}/result", headers=h, json={"rate": "35"})
    body = result.json()["data"]
    assert body["status"] == "DONE"
    assert body["overThreshold"] is True

    blocked_review = client.post(
        f"/api/v1/graduation/finals/{final_id}/review", headers=h, json={"action": "APPROVE"},
    )
    assert blocked_review.status_code == 409

    dup_result = client.post(f"{GD_PLAG}/{pid}/result", headers=h, json={"rate": "10"})
    assert dup_result.json()["code"] != 0  # 已完成不可重复回填

    dispute = client.post(f"{GD_PLAG}/{pid}/dispute", headers=h, json={"reason": "引用格式误判需复查"})
    assert dispute.json()["data"]["disputeStatus"] == "PENDING"

    review = client.post(f"{GD_PLAG}/{pid}/dispute/review", headers=h, json={"action": "APPROVE", "comment": "核实无误"})
    assert review.json()["data"]["disputeStatus"] == "APPROVED"
    assert review.json()["data"]["overThreshold"] is True

    approved_exception = client.post(
        f"/api/v1/graduation/finals/{final_id}/review", headers=h, json={"action": "APPROVE"},
    )
    assert approved_exception.status_code == 200

    db = get_sessionmaker()()
    refreshed = db.get(GraduationFinal, int(final_id))
    assert refreshed.plagiarism_rate == "35.0%"
    assert refreshed.plagiarism_status == "已检测"
    db.close()

    stats = client.get(f"{GD_PLAG}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1


def test_review_assign_rejects_advisor_conflict_and_submit_return(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "PL101", "评阅测试生", advisor="王导师")

    conflict = client.post(f"{GD_REVIEW}/assign", headers=h, json={"gdStudentId": gid, "reviewerName": "王导师"})
    assert conflict.json()["code"] != 0  # SoD 冲突

    ok = client.post(f"{GD_REVIEW}/assign", headers=h, json={"gdStudentId": gid, "reviewerName": "李评阅"})
    assert ok.json()["code"] == 0
    rid = ok.json()["data"]["id"]
    duplicate = client.post(f"{GD_REVIEW}/assign", headers=h, json={"gdStudentId": gid, "reviewerName": "李评阅"})
    assert duplicate.json()["data"]["id"] == rid

    submit = client.post(f"{GD_REVIEW}/{rid}/submit", headers=h, json={"score": 85, "opinion": "内容完整，逻辑清晰"})
    assert submit.json()["data"]["status"] == "COMPLETED"
    submit_retry = client.post(f"{GD_REVIEW}/{rid}/submit", headers=h, json={"score": 85, "opinion": "内容完整，逻辑清晰"})
    assert submit_retry.json()["data"]["status"] == "COMPLETED"

    short_reason = client.post(f"{GD_REVIEW}/{rid}/return", headers=h, json={"reason": "x"})
    assert short_reason.json()["code"] != 0

    ret = client.post(f"{GD_REVIEW}/{rid}/return", headers=h, json={"reason": "评分依据需补充说明"})
    assert ret.json()["data"]["status"] == "RETURNED"

    resubmit = client.post(f"{GD_REVIEW}/{rid}/submit", headers=h, json={"score": 88, "opinion": "已补充说明"})
    assert resubmit.json()["data"]["status"] == "COMPLETED"

    stats = client.get(f"{GD_REVIEW}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1
