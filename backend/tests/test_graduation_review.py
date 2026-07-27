"""毕业设计中心 · 查重记录 + 教师评阅测试：检测中→回填结果→超标复查审核 + 评阅分配(SoD)→提交→退回重评。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_PLAG = "/api/v1/graduation/gd-plagiarism"
GD_REVIEW = "/api/v1/graduation/gd-reviews"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(client, h, no, name, advisor=None):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    if advisor:
        client.post(f"{GD_STU}/{gid}/assign-advisor", headers=h, json={"advisorName": advisor})
    return gid


def _reviewer_token(real_name):
    """构造一个非全范围角色（GD_REVIEWER）的登录令牌，真实姓名可指定，用来验证
    评阅提交是否按「被指派评阅人」而非「对该生有任意评阅关系」收敛。"""
    from hashlib import sha1
    from app.core.security import create_access_token
    main_tid = 1000000000000000001
    login_name = f"TEST-{sha1(real_name.encode('utf-8')).hexdigest()[:12]}"
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-reviewer-{real_name}", "realName": real_name, "userType": "TEACHER", "tid": "demo",
        "tenantId": str(main_tid), "activeContextId": "ctx", "currentRoleCode": "GD_REVIEWER",
        "clientType": "PC", "loginName": login_name})}


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
    recheck_id = review.json()["data"]["recheckTaskId"]
    recheck_result = client.post(f"{GD_PLAG}/{recheck_id}/result", headers=h, json={"rate": "12"})
    assert recheck_result.json()["data"]["overThreshold"] is False

    approved_exception = client.post(
        f"/api/v1/graduation/finals/{final_id}/review", headers=h, json={"action": "APPROVE"},
    )
    assert approved_exception.status_code == 200

    db = get_sessionmaker()()
    refreshed = db.get(GraduationFinal, int(final_id))
    assert refreshed.plagiarism_rate == "12.0%"
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


def test_submit_review_rejects_non_assigned_reviewer(client, auth_headers, db_mode):
    """审计发现：同一学生可有多个独立评阅任务，此前 submit_review 只校验「对该生有任意评阅
    关系」（assert_student_access），不校验「本人即当前这条任务的被指派评阅人」——导致同一学生
    的另一评阅人可用自己的评阅关系覆盖别人评分。本测试复现该场景并验证已按 reviewer_name 收敛。"""
    h = auth_headers
    gid = _gd_student(client, h, "PL301", "评阅越权测试生")

    r1 = client.post(f"{GD_REVIEW}/assign", headers=h, json={"gdStudentId": gid, "reviewerName": "李评阅"})
    rid1 = r1.json()["data"]["id"]
    r2 = client.post(f"{GD_REVIEW}/assign", headers=h, json={"gdStudentId": gid, "reviewerName": "赵评阅"})
    rid2 = r2.json()["data"]["id"]
    assert rid2 != rid1  # 同一学生两个独立评阅任务，分属不同评阅人

    # 赵评阅对该生确有评阅关系（自己的 rid2），但不是 rid1（李评阅）的被指派人：
    # 借自己的评阅关系去提交/覆盖李评阅的任务应被拒绝。
    zhao = _reviewer_token("赵评阅")
    hijack = client.post(f"{GD_REVIEW}/{rid1}/submit", headers=zhao,
                         json={"score": 60, "opinion": "尝试覆盖他人评分"})
    assert hijack.status_code == 403, f"非被指派评阅人提交应 403，实际 {hijack.status_code}"

    # 李评阅本人提交自己被指派的任务应正常通过。
    li = _reviewer_token("李评阅")
    ok = client.post(f"{GD_REVIEW}/{rid1}/submit", headers=li, json={"score": 90, "opinion": "本人正常提交"})
    assert ok.json()["data"]["status"] == "COMPLETED", f"被指派评阅人本人提交应成功，实际 {ok.json()}"

    stats = client.get(f"{GD_REVIEW}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1
