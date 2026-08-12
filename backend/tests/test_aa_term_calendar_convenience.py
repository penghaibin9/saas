"""D1-U 学期/校历/作息便利性 preview 黑盒合同。

只验证辅助读侧：preview 不得落库；确认写入仍由现有 canonical API 负责。
MySQL 8 由 CI TEST_DATABASE_URL 提供权威证据。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name="school_admin01"):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _term(
    client,
    hdr,
    *,
    year,
    no,
    start,
    end,
    teaching_weeks=20,
    exam_week_start=18,
):
    response = client.post(
        f"{BASE}/terms",
        headers=hdr,
        json={
            "yearCode": year,
            "termNo": no,
            "termName": f"{year}第{no}学期",
            "startDate": start,
            "endDate": end,
            "teachingWeeks": teaching_weeks,
            "examWeekStart": exam_week_start,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["termId"]


def test_calendar_copy_preview_uses_teaching_week_mapping_and_writes_nothing(client, db_mode):
    hdr = _hdr(client)
    source_start = date(2040, 9, 1)
    target_start = date(2041, 9, 3)
    source_id = _term(
        client,
        hdr,
        year="2040-2041",
        no=1,
        start=source_start.isoformat(),
        end="2041-01-31",
        teaching_weeks=20,
        exam_week_start=18,
    )
    target_id = _term(
        client,
        hdr,
        year="2041-2042",
        no=1,
        start=target_start.isoformat(),
        end="2042-01-31",
        teaching_weeks=20,
        exam_week_start=19,
    )

    holiday_date = source_start + timedelta(days=14)
    holiday = client.post(
        f"{BASE}/terms/{source_id}/calendar",
        headers=hdr,
        json={
            "eventType": "HOLIDAY",
            "startDate": holiday_date.isoformat(),
            "endDate": holiday_date.isoformat(),
            "remark": "源学期假期",
        },
    )
    assert holiday.status_code == 200, holiday.text

    source_exam_start = source_start + timedelta(days=(18 - 1) * 7)
    exam = client.post(
        f"{BASE}/terms/{source_id}/calendar",
        headers=hdr,
        json={
            "eventType": "EXAM",
            "startDate": source_exam_start.isoformat(),
            "endDate": (source_exam_start + timedelta(days=1)).isoformat(),
            "remark": "期末考试",
        },
    )
    assert exam.status_code == 200, exam.text

    before = client.get(f"{BASE}/terms/{target_id}/calendar", headers=hdr).json()["data"]["items"]
    assert before == []

    preview = client.post(
        f"{BASE}/terms/{target_id}/calendar/copy-preview",
        headers=hdr,
        json={"sourceTermId": source_id},
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["mappingRule"] == "TEACHING_WEEK_RELATIVE_WITH_EXAM_WEEK_ALIGNMENT"
    assert data["targetExistingCount"] == 0
    assert data["blockedCount"] == 0
    assert data["reviewCount"] == 1
    assert data["canConfirm"] is True

    holiday_row = next(item for item in data["items"] if item["eventType"] == "HOLIDAY")
    assert holiday_row["status"] == "REVIEW"
    assert holiday_row["needsReview"] is True
    assert holiday_row["startDate"] == (target_start + timedelta(days=14)).isoformat()
    # 关键合同：不能把复制校历偷换成“日期 + 365”。
    assert holiday_row["startDate"] != (holiday_date + timedelta(days=365)).isoformat()

    exam_row = next(item for item in data["items"] if item["eventType"] == "EXAM")
    expected_exam = target_start + timedelta(days=(19 - 1) * 7)
    assert exam_row["startDate"] == expected_exam.isoformat()
    assert exam_row["status"] == "READY"

    after = client.get(f"{BASE}/terms/{target_id}/calendar", headers=hdr).json()["data"]["items"]
    assert after == [], "copy-preview must never write target calendar facts"


def test_calendar_copy_preview_blocks_nonempty_target_without_deleting_user_work(client, db_mode):
    hdr = _hdr(client)
    source_id = _term(
        client,
        hdr,
        year="2042-2043",
        no=1,
        start="2042-09-01",
        end="2043-01-31",
    )
    target_id = _term(
        client,
        hdr,
        year="2043-2044",
        no=1,
        start="2043-09-04",
        end="2044-01-31",
    )
    client.post(
        f"{BASE}/terms/{source_id}/calendar",
        headers=hdr,
        json={"eventType": "TEACHING", "startDate": "2042-09-08", "remark": "源事件"},
    )
    existing = client.post(
        f"{BASE}/terms/{target_id}/calendar",
        headers=hdr,
        json={"eventType": "TEACHING", "startDate": "2043-09-11", "remark": "用户已录入"},
    )
    assert existing.status_code == 200, existing.text

    preview = client.post(
        f"{BASE}/terms/{target_id}/calendar/copy-preview",
        headers=hdr,
        json={"sourceTermId": source_id},
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["targetExistingCount"] == 1
    assert data["canConfirm"] is False
    assert "已有校历事件" in data["nextStep"]

    target_rows = client.get(f"{BASE}/terms/{target_id}/calendar", headers=hdr).json()["data"]["items"]
    assert len(target_rows) == 1
    assert target_rows[0]["remark"] == "用户已录入"


def test_calendar_copy_preview_rejects_published_target_with_409(client, db_mode):
    hdr = _hdr(client)
    source_id = _term(
        client,
        hdr,
        year="2044-2045",
        no=1,
        start="2044-09-01",
        end="2045-01-31",
    )
    target_id = _term(
        client,
        hdr,
        year="2045-2046",
        no=1,
        start="2045-09-01",
        end="2046-01-31",
    )
    assert client.post(f"{BASE}/terms/{target_id}/publish", headers=hdr).status_code == 200
    response = client.post(
        f"{BASE}/terms/{target_id}/calendar/copy-preview",
        headers=hdr,
        json={"sourceTermId": source_id},
    )
    assert response.status_code == 409


def test_time_slot_8_and_10_templates_are_preview_only(client, db_mode):
    hdr = _hdr(client)
    before = client.get(f"{BASE}/time-slots", headers=hdr, params={"includeDisabled": True})
    assert before.status_code == 200
    before_items = before.json()["data"]["items"]

    preview8 = client.post(
        f"{BASE}/time-slots/template-preview",
        headers=hdr,
        json={"templateKey": "STANDARD_8"},
    )
    assert preview8.status_code == 200, preview8.text
    data8 = preview8.json()["data"]
    assert data8["templateKey"] == "STANDARD_8"
    assert len(data8["items"]) == 8
    assert data8["readyCount"] + data8["existingCount"] + data8["blockedCount"] == 8
    assert data8["items"][0]["desired"] == {
        "slotNo": 1,
        "slotName": "第1节",
        "startTime": "08:00",
        "endTime": "08:45",
    }

    preview10 = client.post(
        f"{BASE}/time-slots/template-preview",
        headers=hdr,
        json={"templateKey": "STANDARD_10"},
    )
    assert preview10.status_code == 200, preview10.text
    data10 = preview10.json()["data"]
    assert len(data10["items"]) == 10
    assert data10["items"][-1]["desired"]["slotNo"] == 10

    after = client.get(f"{BASE}/time-slots", headers=hdr, params={"includeDisabled": True})
    assert after.status_code == 200
    assert after.json()["data"]["items"] == before_items, "template-preview must not create time slots"


def test_d1_convenience_previews_fail_closed_for_student(client, db_mode):
    admin = _hdr(client)
    source_id = _term(
        client,
        admin,
        year="2046-2047",
        no=1,
        start="2046-09-01",
        end="2047-01-31",
    )
    target_id = _term(
        client,
        admin,
        year="2047-2048",
        no=1,
        start="2047-09-02",
        end="2048-01-31",
    )
    student = _hdr(client, "student01")

    calendar_preview = client.post(
        f"{BASE}/terms/{target_id}/calendar/copy-preview",
        headers=student,
        json={"sourceTermId": source_id},
    )
    assert calendar_preview.status_code == 403

    template_preview = client.post(
        f"{BASE}/time-slots/template-preview",
        headers=student,
        json={"templateKey": "STANDARD_8"},
    )
    assert template_preview.status_code == 403


def test_calendar_copy_preview_cannot_read_source_term_from_another_tenant(client, db_mode):
    """即使猜中别校 sourceTermId，也只能得到 404，不能借 preview 跨租户读校历。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTerm

    admin = _hdr(client)
    target_id = _term(
        client,
        admin,
        year="2048-2049",
        no=1,
        start="2048-09-01",
        end="2049-01-31",
    )

    db = get_sessionmaker()()
    foreign = AaTerm(
        tenant_id=1000000000000000002,
        year_code="2098-2099",
        term_no=1,
        term_name="别校学期",
        start_date=datetime(2098, 9, 1),
        end_date=datetime(2099, 1, 31),
        teaching_weeks=20,
        exam_week_start=18,
        status="DRAFT",
        is_current=False,
    )
    db.add(foreign)
    db.commit()
    db.refresh(foreign)
    foreign_id = foreign.id
    db.close()

    response = client.post(
        f"{BASE}/terms/{target_id}/calendar/copy-preview",
        headers=admin,
        json={"sourceTermId": foreign_id},
    )
    assert response.status_code == 404
    assert "别校学期" not in response.text
