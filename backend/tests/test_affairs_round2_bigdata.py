"""第二轮学工：真实 MySQL 大数据分页完整性。"""
from __future__ import annotations

from math import ceil


TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
RISK_COUNT = 1000
AID_COUNT = 450
PAGE_SIZE = 50


def _hdr(client, login_name):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_big_data(db_mode, client):
    """批量写入一个班的学生、风险和困难认定申请，避免逐条 HTTP 建单。"""
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, SchoolClass, StudentProfile, AidApply

    admin = _hdr(client, "school_admin01")
    batch_response = client.post(
        f"{BASE}/aid/batches",
        headers=admin,
        json={
            "batchName": "大数据分页已发布批次",
            "schoolYear": "2025-2026",
            "publicityDays": 1,
            "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
            "publish": True,
        },
    )
    assert batch_response.status_code == 200, batch_response.text
    batch_id = int(batch_response.json()["data"]["batchId"])

    db = get_sessionmaker()()
    try:
        school_class = SchoolClass(
            tenant_id=TID,
            major_id=1,
            class_name="大数据分页测试班",
            grade="2025",
            status="ACTIVE",
        )
        db.add(school_class)
        db.flush()

        students = [
            StudentProfile(
                tenant_id=TID,
                student_no=f"BIG{index:04d}",
                real_name=f"分页学生{index:04d}",
                class_id=school_class.id,
                current_stage="ORIENTATION",
                student_status="NORMAL",
                status="ACTIVE",
            )
            for index in range(1, RISK_COUNT + 1)
        ]
        db.add_all(students)
        db.flush()

        risks = [
            AffairsRiskRecord(
                tenant_id=TID,
                student_id=student.id,
                source="MANUAL",
                # 即使 MANUAL 当前服务层会忽略来源号，仍显式给出唯一值以覆盖 UK 约束。
                source_ref_id=900000 + index,
                risk_level="HIGH" if index % 10 == 0 else "MEDIUM",
                title=f"大数据风险{index}",
                detail="分页完整性测试数据",
                status="NEW",
            )
            for index, student in enumerate(students, start=1)
        ]
        aid_apps = [
            AidApply(
                tenant_id=TID,
                batch_id=batch_id,
                student_id=student.id,
                apply_level="DIFFICULT",
                final_level="DIFFICULT",
                statement="家庭经济困难，需要学校资助支持完成学业。",
                status="COUNSELOR_REVIEW" if index <= 225 else "APPROVED",
                is_deleted=False, version=0,
            )
            for index, student in enumerate(students[:AID_COUNT], start=1)
        ]
        db.add_all(risks)
        db.add_all(aid_apps)
        db.commit()
        return {
            "admin": admin,
            "batch_id": batch_id,
            "risk_ids": [risk.id for risk in risks],
            "aid_ids": [app.id for app in aid_apps],
        }
    finally:
        db.close()


def test_big_data_risk_and_aid_pagination(client, db_mode):
    seeded = _seed_big_data(db_mode, client)
    admin = seeded["admin"]

    # 风险：总量、最后页、stats 跨页一致、最大 pageSize 和空页。
    first = client.get(
        f"{BASE}/risk/records",
        headers=admin,
        params={"page": 1, "pageSize": PAGE_SIZE},
    )
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["total"] == RISK_COUNT
    assert first_data["stats"]["total"] == RISK_COUNT
    assert len(first_data["items"]) == PAGE_SIZE
    assert first_data["items"][0]["riskId"] == str(seeded["risk_ids"][-1])

    risk_last_page = ceil(RISK_COUNT / PAGE_SIZE)
    risk_last = client.get(
        f"{BASE}/risk/records",
        headers=admin,
        params={"page": risk_last_page, "pageSize": PAGE_SIZE},
    )
    assert risk_last.status_code == 200, risk_last.text
    risk_last_data = risk_last.json()["data"]
    assert risk_last_data["total"] == RISK_COUNT
    assert risk_last_data["stats"] == first_data["stats"]
    assert risk_last_data["items"][-1]["riskId"] == str(seeded["risk_ids"][0])

    maximum_page = client.get(
        f"{BASE}/risk/records", headers=admin, params={"page": 1, "pageSize": 200}
    )
    assert maximum_page.status_code == 200, maximum_page.text
    assert len(maximum_page.json()["data"]["items"]) == 200
    oversize_page = client.get(
        f"{BASE}/risk/records", headers=admin, params={"page": 1, "pageSize": 201}
    )
    # FastAPI Query(le=200) 被本项目的统一校验异常处理器映射成 400（而非默认 422）。
    assert oversize_page.status_code in (200, 400, 422)
    if oversize_page.status_code == 200:
        assert len(oversize_page.json()["data"]["items"]) == 200

    risk_empty = client.get(
        f"{BASE}/risk/records",
        headers=admin,
        params={"page": risk_last_page + 100, "pageSize": PAGE_SIZE},
    )
    assert risk_empty.status_code == 200, risk_empty.text
    assert risk_empty.json()["data"]["items"] == []
    assert risk_empty.json()["data"]["total"] == RISK_COUNT

    # 困难认定：总量、末页，以及 status 过滤后的独立总量和末页。
    aid_first = client.get(
        f"{BASE}/aid/applications",
        headers=admin,
        params={"batchId": seeded["batch_id"], "page": 1, "pageSize": PAGE_SIZE},
    )
    assert aid_first.status_code == 200, aid_first.text
    aid_first_data = aid_first.json()["data"]
    assert aid_first_data["total"] == AID_COUNT
    assert len(aid_first_data["items"]) == PAGE_SIZE
    assert aid_first_data["items"][0]["applyId"] == str(seeded["aid_ids"][-1])

    aid_last_page = ceil(AID_COUNT / PAGE_SIZE)
    aid_last = client.get(
        f"{BASE}/aid/applications",
        headers=admin,
        params={"batchId": seeded["batch_id"], "page": aid_last_page, "pageSize": PAGE_SIZE},
    )
    assert aid_last.status_code == 200, aid_last.text
    assert aid_last.json()["data"]["total"] == AID_COUNT
    assert aid_last.json()["data"]["items"][-1]["applyId"] == str(seeded["aid_ids"][0])

    review_total = 225
    review_last_page = ceil(review_total / PAGE_SIZE)
    aid_review_last = client.get(
        f"{BASE}/aid/applications",
        headers=admin,
        params={
            "batchId": seeded["batch_id"],
            "status": "COUNSELOR_REVIEW",
            "page": review_last_page,
            "pageSize": PAGE_SIZE,
        },
    )
    assert aid_review_last.status_code == 200, aid_review_last.text
    aid_review_data = aid_review_last.json()["data"]
    assert aid_review_data["total"] == review_total < AID_COUNT
    assert len(aid_review_data["items"]) == review_total % PAGE_SIZE
    assert aid_review_data["items"][-1]["applyId"] == str(seeded["aid_ids"][0])
