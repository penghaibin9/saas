"""勤工助学四端核心流：发岗、自主申请、录用、协议上岗、月考核与本人结果。"""
from __future__ import annotations

from datetime import datetime, timedelta

from test_aid_material_flow import _data
from test_aid_mobile_queue import _login
from test_funding_application_workspace import _accounts


BASE = "/api/v1"


def test_work_study_four_end_core_flow(client, db_mode):
    ids = _accounts(db_mode)
    admin_pc = _login(client, "school_admin01", "PC")
    admin_mini = _login(client, "school_admin01", "TEACHER_MINI")
    student_pc = _login(client, "fund_student", "PC")
    student_mini = _login(client, "fund_student", "STUDENT_MINI")
    other_pc = _login(client, "fund_other", "PC")

    post = _data(client.post(f"{BASE}/student-affairs/work-study/posts", headers=admin_pc, json={
        "deptName": "图书馆",
        "postName": "阅览室服务助理",
        "salary": "800.00",
        "headcount": 2,
        "employmentType": "FIXED",
        "workLocation": "图书馆二层",
        "scheduleText": "周一至周五课余时段排班",
        "requirement": "工作认真，服从排班",
        "applyEnd": (datetime.utcnow() + timedelta(days=10)).isoformat(timespec="seconds"),
        "monthlyHoursLimit": "40.00",
        "agreementRequired": True,
    }))
    post_id = post["postId"]

    for url, headers in [
        (f"{BASE}/portal/affairs/work-study/posts", student_pc),
        (f"{BASE}/mobile/affairs/work-study/posts", student_mini),
    ]:
        listed = _data(client.get(url, headers=headers, params={"keyword": "阅览室"}))
        assert listed["total"] == 1
        assert listed["items"][0]["postId"] == post_id
        assert listed["items"][0]["monthlyHoursLimit"] == "40.00"
        assert listed["items"][0]["myRecord"] is None

    record = _data(client.post(
        f"{BASE}/portal/affairs/work-study/posts/{post_id}/apply", headers=student_pc,
        json={"statement": "希望通过劳动锻炼服务能力并减轻生活负担。",
              "availability": "周二、周四下午无课时段", "confirm": True},
    ))
    record_id = record["recordId"]
    assert record["studentId"] == str(ids["sa"])
    assert client.post(
        f"{BASE}/mobile/affairs/work-study/posts/{post_id}/apply", headers=student_mini,
        json={"statement": "重复申请应被拒绝。", "availability": "周末", "confirm": True},
    ).status_code == 409

    assert _data(client.get(f"{BASE}/portal/affairs/work-study/my", headers=other_pc))["items"] == []
    teacher_queue = _data(client.get(
        f"{BASE}/mobile/teacher/affairs/work-study/records", headers=admin_mini,
        params={"keyword": "甲一", "page": 1, "pageSize": 20},
    ))
    target = next(item for item in teacher_queue["items"] if item["recordId"] == record_id)
    assert target["post"]["postName"] == "阅览室服务助理"
    assert target["applyStatement"].startswith("希望通过劳动")

    approved = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/work-study/records/{record_id}/action",
        headers=admin_mini,
        json={"action": "APPROVE", "version": target["version"]},
    ))
    missing_agreement = client.post(
        f"{BASE}/mobile/teacher/affairs/work-study/records/{record_id}/action",
        headers=admin_mini,
        json={"action": "ONBOARD", "version": approved["version"], "agreementConfirmed": False},
    )
    assert missing_agreement.status_code == 409
    onboard = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/work-study/records/{record_id}/action",
        headers=admin_mini,
        json={"action": "ONBOARD", "version": approved["version"], "agreementConfirmed": True},
    ))
    assert onboard["status"] == "ONBOARD" and onboard["agreementConfirmed"] is True
    assert "MONTHLY" in onboard["allowedActions"]

    month = "2026-09"
    first_month = _data(client.post(
        f"{BASE}/mobile/teacher/affairs/work-study/records/{record_id}/monthly",
        headers=admin_mini,
        json={"monthCode": month, "workHours": "32", "rating": "PASS",
              "subsidyAmount": "640.00", "remark": "本月考核合格"},
    ))
    assert first_month["subsidyAmount"] == "640.00"
    assert client.post(
        f"{BASE}/mobile/teacher/affairs/work-study/records/{record_id}/monthly",
        headers=admin_mini,
        json={"monthCode": month, "workHours": "9", "rating": "PASS",
              "subsidyAmount": "180.00"},
    ).status_code == 409

    for url, headers in [
        (f"{BASE}/portal/affairs/work-study/my", student_pc),
        (f"{BASE}/mobile/affairs/work-study/my", student_mini),
    ]:
        mine = _data(client.get(url, headers=headers))["items"]
        same = next(item for item in mine if item["recordId"] == record_id)
        assert same["status"] == "ONBOARD"
        assert same["post"]["workLocation"] == "图书馆二层"
        assert same["monthly"][0]["monthCode"] == month
        assert same["monthly"][0]["workHours"] == 32.0
        assert same["monthly"][0]["subsidyAmount"] == "640.00"
        assert same["subsidyTotal"] == "640.00"
        assert same["allowedActions"] == []

    disabled = _data(client.post(
        f"{BASE}/student-affairs/work-study/posts/{post_id}/action", headers=admin_pc,
        json={"action": "DISABLE", "version": post["version"]},
    ))
    assert disabled["status"] == "DISABLED"
    assert _data(client.get(
        f"{BASE}/portal/affairs/work-study/posts", headers=student_pc,
        params={"keyword": "阅览室"},
    ))["total"] == 0
