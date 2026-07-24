"""学工第二阶段：多领域大数据分页验收（真实 MySQL，不覆盖 10 万风险性能压测）。

规模：
- 困难申请 / 奖助申请 / 处分 / 心理关注 / 党团发展 / 风险：各 1000
- 活动 / 社团：各 300（注明：优先 1000，当前为控时取 300）
"""
from __future__ import annotations

from math import ceil


TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
COUNT = 1000
SMALL_COUNT = 300  # 活动/社团：优先 1000，控时取 300
PAGE_SIZE = 50


def _hdr(client):
    last = None
    for _ in range(5):
        last = client.post(
            "/api/v1/auth/mock-login",
            json={"loginName": "school_admin01", "password": "any"},
        )
        body = last.json() if last.content else {}
        data = body.get("data") if isinstance(body, dict) else None
        if last.status_code == 200 and data and data.get("accessToken"):
            return {"Authorization": f"Bearer {data['accessToken']}"}
        # 共享测试库并发 DDL 时 refresh token 写入可能短暂失败
        if isinstance(body, dict) and body.get("bizCode") == "AUTH_STORE_UNAVAILABLE":
            import time
            time.sleep(1.5)
            continue
    raise AssertionError(
        f"mock-login failed: status={getattr(last, 'status_code', None)} body={getattr(last, 'text', None)}"
    )


def _post_ok(client, path, headers, json_body, label):
    import time
    last = None
    for attempt in range(5):
        last = client.post(path, headers=headers, json=json_body)
        if last.status_code == 200:
            return last
        body = last.json() if last.content else {}
        if isinstance(body, dict) and body.get("bizCode") == "AUTH_STORE_UNAVAILABLE":
            headers.update(_hdr(client))
            time.sleep(1.5)
            continue
        break
    raise AssertionError(f"{label} failed: {getattr(last, 'text', None)}")


def _seed(client, headers):
    """对齐 round2：HTTP 建批次，再 ORM 批量灌数。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsActivity,
        AffairsClub,
        AffairsLeagueDev,
        AffairsRiskRecord,
        AidApply,
        DisciplineCase,
        FundingApplication,
        PsyReferral,
        SchoolClass,
        StudentProfile,
    )

    aid_batch = _post_ok(
        client,
        f"{BASE}/aid/batches",
        headers,
        {
            "batchName": "二阶段困难认定批次",
            "schoolYear": "2025-2026",
            "publicityDays": 0,
            "levelConfig": {"levels": ["SPECIAL", "DIFFICULT", "GENERAL"]},
            "publish": True,
        },
        "aid batch",
    )
    aid_batch_id = int(aid_batch.json()["data"]["batchId"])

    project = _post_ok(
        client,
        f"{BASE}/funding/projects",
        headers,
        {"projectType": "GRANT", "projectName": "二阶段助学金", "amount": 3000, "quota": COUNT},
        "funding project",
    )
    project_id = int(project.json()["data"]["projectId"])

    funding_batch = _post_ok(
        client,
        f"{BASE}/funding/batches",
        headers,
        {
            "projectId": str(project_id),
            "schoolYear": "2025-2026",
            "publicityDays": 0,
            "quota": COUNT,
            "publish": True,
        },
        "funding batch",
    )
    funding_batch_id = int(funding_batch.json()["data"]["batchId"])

    db = get_sessionmaker()()
    try:
        school_class = SchoolClass(
            tenant_id=TID,
            major_id=1,
            class_name="二阶段大数据验收班",
            grade="2025",
            status="ACTIVE",
        )
        db.add(school_class)
        db.flush()

        students = [
            StudentProfile(
                tenant_id=TID,
                student_no=f"P2BIG{i:04d}",
                real_name=f"二阶段学生{i:04d}",
                class_id=school_class.id,
                current_stage="ORIENTATION",
                student_status="NORMAL",
                status="ACTIVE",
            )
            for i in range(1, COUNT + 1)
        ]
        db.add_all(students)
        db.flush()

        half = COUNT // 2
        db.add_all(
            [
                AidApply(
                    tenant_id=TID,
                    batch_id=aid_batch_id,
                    student_id=s.id,
                    apply_level="DIFFICULT",
                    final_level="DIFFICULT",
                    statement="二阶段大数据困难认定申请说明不少于十字",
                    status="REVIEW" if i <= half else "APPROVED",
                )
                for i, s in enumerate(students, 1)
            ]
        )
        db.add_all(
            [
                FundingApplication(
                    tenant_id=TID,
                    batch_id=funding_batch_id,
                    student_id=s.id,
                    project_type="GRANT",
                    apply_source="SELF",
                    amount=3000,
                    statement="二阶段大数据奖助申请",
                    status="COUNSELOR_REVIEW" if i <= half else "GRANTED",
                )
                for i, s in enumerate(students, 1)
            ]
        )
        db.add_all(
            [
                DisciplineCase(
                    tenant_id=TID,
                    student_id=s.id,
                    disc_type="WARNING",
                    reason="二阶段大数据处分事实说明",
                    status="COLLEGE_REVIEW" if i <= half else "EFFECTIVE",
                )
                for i, s in enumerate(students, 1)
            ]
        )
        db.add_all(
            [
                PsyReferral(
                    tenant_id=TID,
                    student_id=s.id,
                    level="FOCUS",
                    channel="校内咨询",
                    reason_summary="二阶段心理关注摘要",
                    status="REFERRED" if i <= half else "FOLLOWING",
                )
                for i, s in enumerate(students, 1)
            ]
        )
        db.add_all(
            [
                AffairsLeagueDev(
                    tenant_id=TID,
                    student_id=s.id,
                    dev_type="PARTY",
                    current_stage="APPLICANT",
                    branch_name="二阶段党支部",
                    status="ONGOING",
                )
                for s in students
            ]
        )
        db.add_all(
            [
                AffairsRiskRecord(
                    tenant_id=TID,
                    student_id=s.id,
                    source="MANUAL",
                    source_ref_id=7_000_000 + i,
                    risk_level="HIGH" if i % 10 == 0 else "MEDIUM",
                    title=f"二阶段风险{i}",
                    detail="二阶段大数据风险明细不少于五字",
                    status="NEW",
                )
                for i, s in enumerate(students, 1)
            ]
        )
        db.add_all(
            [
                AffairsActivity(
                    tenant_id=TID,
                    activity_name=f"二阶段活动{i:04d}",
                    activity_type="ACTIVITY",
                    status="PUBLISHED" if i <= SMALL_COUNT // 2 else "DRAFT",
                )
                for i in range(1, SMALL_COUNT + 1)
            ]
        )
        db.add_all(
            [
                AffairsClub(
                    tenant_id=TID,
                    club_name=f"二阶段社团{i:04d}",
                    club_type="INTEREST",
                    status="ACTIVE" if i <= SMALL_COUNT // 2 else "PENDING",
                )
                for i in range(1, SMALL_COUNT + 1)
            ]
        )
        db.commit()
        return {"aid": aid_batch_id, "funding": funding_batch_id}
    finally:
        db.close()


def _assert_paged(client, headers, path, expected, params=None, item_id=None, status_filter=None, filter_expected=None):
    params = dict(params or {})
    params.update({"page": 1, "pageSize": PAGE_SIZE})
    first = client.get(path, headers=headers, params=params)
    assert first.status_code == 200, first.text
    body = first.json()["data"]
    assert body["total"] == expected, f"{path} total={body.get('total')} expected={expected}"
    assert len(body["items"]) == min(expected, PAGE_SIZE)
    first_id = body["items"][0].get(item_id) if item_id else None

    last_page = ceil(expected / PAGE_SIZE)
    last = client.get(path, headers=headers, params={**params, "page": last_page})
    assert last.status_code == 200, last.text
    last_body = last.json()["data"]
    assert last_body["total"] == expected and last_body["items"], "末页不可见或静默丢数据"
    if item_id:
        last_id = last_body["items"][-1].get(item_id)
        assert last_id, "末页记录缺少主键"
        # 列表按 id desc：首页第一条应大于末页最后一条，证明未静默截断边界
        if first_id is not None:
            assert int(first_id) >= int(last_id)

    if "statusCounts" in body:
        assert int(body["statusCounts"].get("ALL", expected)) == expected

    if status_filter:
        filtered = client.get(path, headers=headers, params={**params, "status": status_filter})
        assert filtered.status_code == 200, filtered.text
        want = filter_expected if filter_expected is not None else expected // 2
        assert filtered.json()["data"]["total"] == want

    oversize = client.get(path, headers=headers, params={**params, "pageSize": 201})
    assert oversize.status_code in (200, 400, 422), oversize.text
    if oversize.status_code == 200:
        assert len(oversize.json()["data"]["items"]) <= 200


def test_phase2_bigdata_multi_domain_pagination(client, db_mode):
    headers = _hdr(client)
    ids = _seed(client, headers)

    _assert_paged(
        client, headers, f"{BASE}/aid/applications", COUNT,
        {"batchId": ids["aid"]}, "applyId", "REVIEW", COUNT // 2,
    )
    _assert_paged(
        client, headers, f"{BASE}/funding/applications", COUNT,
        {"batchId": ids["funding"]}, "applicationId", "COUNSELOR_REVIEW", COUNT // 2,
    )
    _assert_paged(
        client, headers, f"{BASE}/discipline/cases", COUNT,
        item_id="caseId", status_filter="COLLEGE_REVIEW", filter_expected=COUNT // 2,
    )
    _assert_paged(client, headers, f"{BASE}/mental/list", COUNT, item_id="referralId")
    _assert_paged(
        client, headers, f"{BASE}/activities", SMALL_COUNT,
        item_id="activityId", status_filter="PUBLISHED", filter_expected=SMALL_COUNT // 2,
    )
    _assert_paged(
        client, headers, f"{BASE}/clubs", SMALL_COUNT,
        item_id="clubId", status_filter="ACTIVE", filter_expected=SMALL_COUNT // 2,
    )
    _assert_paged(client, headers, f"{BASE}/party-league/dev", COUNT, item_id="devId")
    _assert_paged(client, headers, f"{BASE}/risk/records", COUNT, item_id="riskId")
