"""Funding project and batch lifecycle shared by the four student-affairs clients."""
from datetime import datetime, timedelta

from test_aid_material_flow import _data
from test_aid_mobile_queue import _login
from test_affairs_funding import BASE
from test_funding_application_workspace import _accounts


def test_funding_catalog_draft_publish_close_and_project_switch(client, db_mode):
    _accounts(db_mode)
    admin = _login(client, "school_admin01", "PC")
    student_pc = _login(client, "fund_student", "PC")
    student_mini = _login(client, "fund_student", "STUDENT_MINI")
    other_pc = _login(client, "fund_other", "PC")

    project = _data(client.post(f"{BASE}/funding/projects", headers=admin, json={
        "projectName": "2026 校级100%成长奖学金",
        "projectType": "SCHOLARSHIP",
        "amount": 3000,
        "quota": 10,
    }))
    assert project["status"] == "ENABLED"
    assert project["allowedActions"] == ["DISABLE"]
    assert project["version"] == 0

    projects = _data(client.get(f"{BASE}/funding/projects", headers=admin, params={"keyword": "%"}))
    assert projects["total"] == 1
    assert projects["items"][0]["projectId"] == project["projectId"]
    assert projects["summary"]["all"] == 1
    assert projects["summary"]["byStatus"] == {"ENABLED": 1}
    assert projects["summary"]["byType"] == {"SCHOLARSHIP": 1}

    now = datetime.utcnow()
    batch = _data(client.post(f"{BASE}/funding/batches", headers=admin, json={
        "projectId": project["projectId"],
        "schoolYear": "2026-2027",
        "applyStart": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        "applyEnd": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        "publicityDays": 5,
        "publish": False,
    }))
    assert batch["status"] == "DRAFT"
    assert batch["intakeState"] == "DRAFT"
    assert batch["quota"] == 10
    assert batch["amountBudget"] == "30000.00"
    assert batch["allowedActions"] == ["PUBLISH"]

    batches = _data(client.get(f"{BASE}/funding/batches", headers=admin, params={"keyword": "100%"}))
    assert batches["total"] == 1
    assert batches["summary"]["byStatus"] == {"DRAFT": 1}
    assert batches["summary"]["availableNow"] == 0
    assert batches["items"][0]["projectName"] == project["projectName"]

    student_batch_urls = (
        "/api/v1/portal/affairs/funding/batches",
        "/api/v1/mobile/affairs/funding/batches",
    )
    for url, headers in zip(student_batch_urls, (student_pc, student_mini)):
        assert _data(client.get(url, headers=headers))["total"] == 0

    published = _data(client.post(
        f"{BASE}/funding/batches/{batch['batchId']}/action",
        headers=admin,
        json={"action": "PUBLISH", "version": batch["version"]},
    ))
    assert published["status"] == "OPEN"
    assert published["intakeState"] == "OPEN"
    assert published["version"] == batch["version"] + 1
    assert published["allowedActions"] == ["CLOSE"]
    stale = client.post(
        f"{BASE}/funding/batches/{batch['batchId']}/action",
        headers=admin,
        json={"action": "CLOSE", "version": batch["version"]},
    )
    assert stale.status_code == 409

    for url, headers in zip(student_batch_urls, (student_pc, student_mini)):
        visible = _data(client.get(url, headers=headers))
        assert visible["total"] == 1
        assert visible["items"][0]["batchId"] == batch["batchId"]

    application = _data(client.post(
        "/api/v1/portal/affairs/funding/apply",
        headers=student_pc,
        json={
            "batchId": batch["batchId"],
            "statement": "按学校开放批次提交奖学金申请，保留关闭前已受理流程。",
            "confirm": True,
        },
    ))
    closed = _data(client.post(
        f"{BASE}/funding/batches/{batch['batchId']}/action",
        headers=admin,
        json={"action": "CLOSE", "version": published["version"]},
    ))
    assert closed["status"] == "CLOSED"
    assert closed["applicationCount"] == 1
    assert closed["allowedActions"] == []

    for url, headers in zip(student_batch_urls, (student_pc, student_mini)):
        assert _data(client.get(url, headers=headers))["total"] == 0
    rejected = client.post(
        "/api/v1/portal/affairs/funding/apply",
        headers=other_pc,
        json={"batchId": batch["batchId"], "statement": "批次关闭后不应允许新申请。", "confirm": True},
    )
    assert rejected.status_code == 409
    for url, headers in (
        (f"/api/v1/portal/affairs/funding/applications/{application['applicationId']}", student_pc),
        (f"/api/v1/mobile/affairs/funding/applications/{application['applicationId']}", student_mini),
    ):
        detail = _data(client.get(url, headers=headers))
        assert detail["applicationId"] == application["applicationId"]
        assert detail["status"] == "COUNSELOR_REVIEW"

    second = _data(client.post(f"{BASE}/funding/batches", headers=admin, json={
        "projectId": project["projectId"],
        "schoolYear": "2027-2028",
        "publicityDays": 5,
        "publish": True,
    }))
    disabled = _data(client.post(
        f"{BASE}/funding/projects/{project['projectId']}/status",
        headers=admin,
        json={"status": "DISABLED", "version": project["version"]},
    ))
    assert disabled["status"] == "DISABLED"
    assert disabled["allowedActions"] == ["ENABLE"]
    for url, headers in zip(student_batch_urls, (student_pc, student_mini)):
        assert _data(client.get(url, headers=headers))["total"] == 0
    assert client.post(
        "/api/v1/portal/affairs/funding/apply",
        headers=other_pc,
        json={"batchId": second["batchId"], "statement": "停用项目不应再接收新申请。", "confirm": True},
    ).status_code == 409
    assert client.post(
        f"{BASE}/funding/projects/{project['projectId']}/status",
        headers=admin,
        json={"status": "ENABLED", "version": project["version"]},
    ).status_code == 409

    enabled = _data(client.post(
        f"{BASE}/funding/projects/{project['projectId']}/status",
        headers=admin,
        json={"status": "ENABLED", "version": disabled["version"]},
    ))
    assert enabled["status"] == "ENABLED"
    for url, headers in zip(student_batch_urls, (student_pc, student_mini)):
        visible = _data(client.get(url, headers=headers))
        assert visible["total"] == 1
        assert visible["items"][0]["batchId"] == second["batchId"]

    assert client.post(
        f"{BASE}/funding/projects/{project['projectId']}/status",
        headers=student_pc,
        json={"status": "DISABLED", "version": enabled["version"]},
    ).status_code == 403
    assert client.post(
        f"{BASE}/funding/batches/{second['batchId']}/action",
        headers=student_pc,
        json={"action": "CLOSE", "version": second["version"]},
    ).status_code == 403
