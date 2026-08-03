"""毕业设计中心 · 答辩评分 + 成绩评定测试：多评委录入→确认→二次答辩 + 核算→复核→发布→撤回。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_SCORE = "/api/v1/graduation/gd-defense-scores"
GD_GRADE = "/api/v1/graduation/gd-grades"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _judge_headers(no, name):
    from app.core.security import create_access_token
    suffix = "JA" if name == "评委甲" else "JB"
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{no}-{suffix}", "realName": name, "userType": "TEACHER",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "GD_DEFENSE_EXPERT", "clientType": "PC",
        "loginName": f"{no}-{suffix}",
    })}


def _gd_student(graduation_client, h, no, name):
    from app.db.session import get_sessionmaker
    from app.models import GraduationDefenseGroup, GraduationMentor, GraduationStudent

    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    gid = graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    try:
        judge_a = GraduationMentor(
            tenant_id=1000000000000000001, teacher_no=f"{no}-JA",
            teacher_name="评委甲", qualification_status="QUALIFIED",
        )
        judge_b = GraduationMentor(
            tenant_id=1000000000000000001, teacher_no=f"{no}-JB",
            teacher_name="评委乙", qualification_status="QUALIFIED",
        )
        db.add_all([judge_a, judge_b])
        db.flush()
        group = GraduationDefenseGroup(
            tenant_id=1000000000000000001, batch_id=int(graduation_client._active_batch_id),
            group_name=f"{no}答辩组", chair="评委甲", chair_mentor_id=judge_a.id,
            members_json=[{"mentorId": judge_b.id, "name": "评委乙", "teacherNo": judge_b.teacher_no}],
            published=True, student_count=1,
        )
        db.add(group)
        db.flush()
        stu = db.get(GraduationStudent, int(gid))
        stu.defense_group_id = group.id
        stu.defense_group = group.group_name
        stu.stage = "DEFENSE"
        db.commit()
        graduation_client._defense_judges = {
            **getattr(graduation_client, "_defense_judges", {}),
            (str(gid), "评委甲"): str(judge_a.id),
            (str(gid), "评委乙"): str(judge_b.id),
        }
        return gid
    finally:
        db.close()


def test_defense_score_entry_absent_and_confirm(graduation_client, auth_headers, db_mode):
    h = auth_headers
    no = "DS001"
    gid = _gd_student(graduation_client, h, no, "答辩测试生")

    mid_a = graduation_client._defense_judges[(str(gid), "评委甲")]
    mid_b = graduation_client._defense_judges[(str(gid), "评委乙")]
    judge_a_h = _judge_headers(no, "评委甲")
    judge_b_h = _judge_headers(no, "评委乙")
    bad = graduation_client.post(f"{GD_SCORE}/entry", headers=judge_a_h, json={"gdStudentId": gid, "judgeName": "评委甲", "judgeMentorId": mid_a})
    assert bad.json()["code"] != 0  # 未缺席须评分

    e1 = graduation_client.post(f"{GD_SCORE}/entry", headers=judge_a_h, json={"gdStudentId": gid, "judgeName": "评委甲", "judgeMentorId": mid_a, "score": 88})
    assert e1.json()["data"]["status"] == "SCORED"
    e2 = graduation_client.post(f"{GD_SCORE}/entry", headers=judge_b_h, json={
        "gdStudentId": gid, "judgeName": "评委乙", "judgeMentorId": mid_b, "absent": True, "absentReason": "临时公务"})
    assert e2.json()["data"]["absent"] is True

    confirm = graduation_client.post(f"{GD_SCORE}/{gid}/confirm", headers=h)
    assert confirm.json()["data"]["judgeCount"] == 2
    assert confirm.json()["data"]["average"] == 88

    lst = graduation_client.get(GD_SCORE, headers=h, params={"gdStudentId": gid}).json()["data"]["items"]
    assert all(x["status"] == "CONFIRMED" for x in lst)

    dup_update = graduation_client.post(f"{GD_SCORE}/entry", headers=judge_a_h, json={"gdStudentId": gid, "judgeName": "评委甲", "judgeMentorId": mid_a, "score": 90})
    assert dup_update.json()["code"] != 0  # 已确认不可修改

    stats = graduation_client.get(f"{GD_SCORE}/stats", headers=h).json()["data"]
    assert stats["confirmed"] >= 2


def test_second_defense_requires_first_round_confirmed(graduation_client, auth_headers, db_mode):
    h = auth_headers
    no = "DS101"
    gid = _gd_student(graduation_client, h, no, "二辩测试生")
    mid_a = graduation_client._defense_judges[(str(gid), "评委甲")]
    mid_b = graduation_client._defense_judges[(str(gid), "评委乙")]
    graduation_client.post(f"{GD_SCORE}/entry", headers=_judge_headers(no, "评委甲"), json={"gdStudentId": gid, "judgeName": "评委甲", "judgeMentorId": mid_a, "score": 55})
    graduation_client.post(f"{GD_SCORE}/entry", headers=_judge_headers(no, "评委乙"), json={"gdStudentId": gid, "judgeName": "评委乙", "judgeMentorId": mid_b, "score": 58})

    too_early = graduation_client.post(f"{GD_SCORE}/{gid}/second-defense", headers=h, json={"reason": "分数不理想需二辩"})
    assert too_early.json()["code"] != 0

    graduation_client.post(f"{GD_SCORE}/{gid}/confirm", headers=h)
    ok = graduation_client.post(f"{GD_SCORE}/{gid}/second-defense", headers=h, json={"reason": "分数不理想需二辩"})
    assert ok.json()["data"]["newRound"] == 2


def test_grade_calculate_review_publish_withdraw(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(graduation_client, h, "GR001", "成绩测试生")
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import GraduationDefenseScore, GraduationFinal, GraduationReview
    db = get_sessionmaker()()
    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), status="APPROVED",
        plagiarism_rate="10.0%", plagiarism_status="已检测", attachments_json=["test-file"],
    )
    db.add(final)
    db.flush()
    db.add(GraduationReview(
        tenant_id=1000000000000000001, gd_student_id=int(gid), gd_final_id=final.id,
        reviewer_name="李评阅",
        status="COMPLETED", score=90, opinion="评阅完成", reviewed_at=datetime.utcnow(),
    ))
    db.add(GraduationDefenseScore(
        tenant_id=1000000000000000001, gd_student_id=int(gid), judge_name="王评委",
        score=90, absent=False, round_no=1, status="CONFIRMED", confirmed_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()

    detail = graduation_client.get(f"{GD_GRADE}/{gid}", headers=h).json()["data"]
    assert detail["status"] == "DRAFT"
    assert detail["sourceScores"]["reviewerScore"] == 90
    assert detail["sourceScores"]["defenseScore"] == 90

    calc = graduation_client.post(f"{GD_GRADE}/{gid}/calculate", headers=h, json={
        "advisorScore": 95, "reviewerScore": 90, "defenseScore": 90})
    body = calc.json()["data"]
    assert body["status"] == "CALCULATED"
    assert body["totalScore"] == round(95 * 0.4 + 90 * 0.3 + 90 * 0.3)
    assert body["gradeLevel"] == "优秀"

    publish_before_review = graduation_client.post(f"{GD_GRADE}/{gid}/publish", headers=h)
    assert publish_before_review.json()["code"] != 0  # 未复核不可发布

    return_short = graduation_client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "RETURN", "comment": "x"})
    assert return_short.json()["code"] != 0
    ret = graduation_client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "RETURN", "comment": "答辩分需核实原始记录"})
    assert ret.json()["data"]["status"] == "DRAFT"

    mismatch = graduation_client.post(
        f"{GD_GRADE}/{gid}/calculate", headers=h,
        json={"advisorScore": 90, "reviewerScore": 90, "defenseScore": 88},
    )
    assert mismatch.status_code == 409
    graduation_client.post(f"{GD_GRADE}/{gid}/calculate", headers=h, json={
        "advisorScore": 90, "reviewerScore": 90, "defenseScore": 90,
    })
    approve = graduation_client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "APPROVE"})
    assert approve.json()["data"]["reviewedBy"]
    assert len(approve.json()["data"]["sourceSnapshotHash"]) == 64
    approve_retry = graduation_client.post(f"{GD_GRADE}/{gid}/review", headers=h, json={"action": "APPROVE"})
    assert approve_retry.json()["data"]["version"] == approve.json()["data"]["version"]

    db = get_sessionmaker()()
    review_row = db.query(GraduationReview).filter(GraduationReview.gd_student_id == int(gid)).one()
    review_row.score = 91
    db.commit()
    db.close()
    stale_publish = graduation_client.post(f"{GD_GRADE}/{gid}/publish", headers=h)
    assert stale_publish.status_code == 409
    db = get_sessionmaker()()
    review_row = db.query(GraduationReview).filter(GraduationReview.gd_student_id == int(gid)).one()
    review_row.score = 90
    db.commit()
    db.close()

    publish = graduation_client.post(f"{GD_GRADE}/{gid}/publish", headers=h)
    assert publish.json()["data"]["status"] == "PUBLISHED"
    publish_retry = graduation_client.post(f"{GD_GRADE}/{gid}/publish", headers=h)
    assert publish_retry.json()["data"]["version"] == publish.json()["data"]["version"]

    withdraw_short = graduation_client.post(f"{GD_GRADE}/{gid}/withdraw", headers=h, json={"reason": "x"})
    assert withdraw_short.json()["code"] != 0
    withdraw = graduation_client.post(f"{GD_GRADE}/{gid}/withdraw", headers=h, json={"reason": "发现导师分录入错误需重新核算"})
    assert withdraw.json()["data"]["status"] == "WITHDRAWN"
    withdraw_retry = graduation_client.post(
        f"{GD_GRADE}/{gid}/withdraw", headers=h,
        json={"reason": "发现导师分录入错误需重新核算"},
    )
    assert withdraw_retry.json()["data"]["version"] == withdraw.json()["data"]["version"]

    stats = graduation_client.get(f"{GD_GRADE}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1
