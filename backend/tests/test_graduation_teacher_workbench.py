"""老师毕设工作台：一个老师身兼导师/评委/秘书，待办按业务顺序汇总（真库）。"""
from __future__ import annotations

from datetime import datetime, timezone

from test_graduation_auto_identity import (  # 复用同一套造数工具
    MAIN, MOBILE, _batch, _headers, _mentor, _ok, _student, _uniq,
)

from app.db.session import get_sessionmaker
from app.models import (
    GraduationDefenseScore, GraduationFinal, GraduationProposal, GraduationReview,
    GraduationStudent, GraduationTopic, GraduationTopicChoice,
)

WB = "/api/v1/graduation/teacher-workbench"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _db_add(*rows):
    db = get_sessionmaker()()
    try:
        for row in rows:
            db.add(row)
        db.commit()
        return [int(row.id) for row in rows]
    finally:
        db.close()


def _update_student(gid, **fields):
    db = get_sessionmaker()()
    try:
        row = db.get(GraduationStudent, int(gid))
        for key, value in fields.items():
            setattr(row, key, value)
        db.commit()
    finally:
        db.close()


def _tasks(data):
    return {task["key"]: task for task in data["tasks"]}


def test_teacher_workbench_aggregates_all_identities_in_business_order(graduation_client, auth_headers, db_mode):
    from app.models import GraduationDefenseGroup

    h = auth_headers
    bid = _batch(graduation_client, h)
    login_a, login_b = _uniq("WA"), _uniq("WB")
    mid_a = _mentor(graduation_client, h, login_a, "工作台导师甲")
    mid_b = _mentor(graduation_client, h, login_b, "工作台导师乙")

    s_prop = _student(graduation_client, h, bid, mid_a, "待批开题生")
    s_mid = _student(graduation_client, h, bid, mid_a, "中期生")
    s_tb = _student(graduation_client, h, bid, mid_a, "待任务书生")
    s_choice = _student(graduation_client, h, bid, None, "选题生")
    s_def = _student(graduation_client, h, bid, mid_b, "答辩生")
    s_rev = _student(graduation_client, h, bid, mid_b, "评阅生")

    (topic_id,) = _db_add(GraduationTopic(tenant_id=MAIN, batch_id=bid, title="工作台测试题目",
                                          advisor_name="工作台导师甲", advisor_mentor_id=mid_a,
                                          capacity=2, review_status="APPROVED", status="OPEN"))
    _update_student(s_mid, stage="MIDTERM")
    _update_student(s_tb, stage="TASKBOOK_CONFIRM", topic_id=topic_id, topic_title="工作台测试题目")
    _db_add(
        GraduationProposal(tenant_id=MAIN, gd_student_id=s_prop, status="PENDING_REVIEW", version="v1",
                           submit_at=_now(), active_key=f"pending:{s_prop}"),
        GraduationFinal(tenant_id=MAIN, gd_student_id=s_prop, status="PENDING_REVIEW", final_type="初稿",
                        version="v1", submit_at=_now(), active_key=f"pending:{s_prop}"),
        GraduationTopicChoice(tenant_id=MAIN, round_id=1, gd_student_id=s_choice, topic_id=topic_id,
                              choice_order=1, status="PENDING"),
        GraduationReview(tenant_id=MAIN, gd_student_id=s_rev, reviewer_name="工作台导师甲",
                         reviewer_mentor_id=mid_a, status="ASSIGNED", assigned_at=_now()),
    )
    grp = graduation_client.post("/api/v1/graduation/defense-groups", headers=h, params={"batchId": bid}, json={
        "groupName": _uniq("组"), "batchId": bid, "location": "D401",
        "chairMentorId": mid_a, "secretaryMentorId": mid_b, "memberMentorIds": [],
    })
    assert _ok(grp), grp.json()
    group_id = int(grp.json()["data"]["id"])
    db = get_sessionmaker()()
    try:
        db.get(GraduationDefenseGroup, group_id).published = True
        db.commit()
    finally:
        db.close()
    _update_student(s_def, defense_group_id=group_id, stage="DEFENSE")

    ha, hb = _headers(login_a), _headers(login_b)
    resp = graduation_client.get(WB, headers=ha, params={"batchId": bid})
    assert _ok(resp), resp.json()
    data = resp.json()["data"]
    assert data["identities"] == ["GD_MENTOR", "GD_REVIEWER", "GD_DEFENSE_EXPERT"]
    keys = [task["key"] for task in data["tasks"]]
    assert keys == ["topicChoice", "topicChange", "taskbook", "proposal", "midterm", "final", "advisorScore",
                    "review", "defenseScore"]
    tasks = _tasks(data)
    ids = lambda key: {item["gdStudentId"] for item in tasks[key]["items"]}  # noqa: E731
    assert tasks["topicChoice"]["count"] == 1 and ids("topicChoice") == {str(s_choice)}
    assert tasks["topicChange"]["count"] == 0
    assert tasks["advisorScore"]["count"] == 0  # 没有定稿已通过的学生，暂不需要打导师分
    assert ids("taskbook") == {str(s_tb)}
    assert ids("proposal") == {str(s_prop)} and ids("final") == {str(s_prop)}
    assert str(s_mid) in ids("midterm")
    assert ids("review") == {str(s_rev)}
    assert ids("defenseScore") == {str(s_def)}
    assert data["todoTotal"] == sum(task["count"] for task in data["tasks"])
    assert {row["gdStudentId"] for row in data["students"]} == {str(s_prop), str(s_mid), str(s_tb)}
    assert data["groups"][0]["myRoles"] == ["组长"]

    # 乙：导师 + 秘书；评委还没评完分 → 暂无“确认答辩成绩”
    data_b = graduation_client.get(WB, headers=hb, params={"batchId": bid}).json()["data"]
    assert "GD_DEFENSE_SECRETARY" in data_b["identities"]
    assert _tasks(data_b)["defenseConfirm"]["count"] == 0

    # 甲评完分 → 甲的评分待办消失，乙出现待确认
    _db_add(GraduationDefenseScore(tenant_id=MAIN, gd_student_id=s_def, defense_group_id=group_id,
                                   judge_name="工作台导师甲", judge_mentor_id=mid_a,
                                   judge_identity=f"MENTOR:{mid_a}", score=85, round_no=1, status="SCORED"))
    data = graduation_client.get(WB, headers=ha, params={"batchId": bid}).json()["data"]
    assert _tasks(data)["defenseScore"]["count"] == 0
    data_b = graduation_client.get(WB, headers=hb, params={"batchId": bid}).json()["data"]
    confirm = _tasks(data_b)["defenseConfirm"]
    assert confirm["count"] == 1 and confirm["items"][0]["gdStudentId"] == str(s_def)

    # 小程序与 PC 同源
    mobile = graduation_client.get(f"{MOBILE}/teacher/graduation/workbench", headers=_headers(login_a, client_type="MP"),
                                   params={"batchId": bid})
    assert _ok(mobile), mobile.json()
    assert mobile.json()["data"]["todoTotal"] == data["todoTotal"]


def test_teacher_workbench_for_teacher_without_mentor_ledger_is_denied(graduation_client, auth_headers, db_mode):
    bid = _batch(graduation_client, auth_headers)
    resp = graduation_client.get(WB, headers=_headers(_uniq("WX")), params={"batchId": bid})
    assert not _ok(resp)
