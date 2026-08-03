"""13A-P6 学工归档 · 端到端（真实 DB 模式）。

批次→收集真实档案包→逐级流转→ARCHIVED，并登记公共文件对象承载的归档清单导出任务。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="A002", real_name="甲二", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(s1); db.add(s2); db.flush()
    ids = {"s1": s1.id, "s2": s2.id}
    db.commit()
    db.close()
    return ids


def _create_batch(client, hdr, name):
    response = client.post(f"{BASE}/archive/batches", headers=hdr, json={
        "batchName": name, "yearCode": "2026",
    }).json()
    assert response["code"] == 0, response
    return response["data"]


def test_archive_full_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    batch = _create_batch(client, hdr, "2026届学工归档")
    bid = batch["batchId"]

    collected_response = client.post(
        f"{BASE}/archive/batches/{bid}/collect",
        headers=hdr,
        json={
            "studentIds": [str(ids["s1"]), str(ids["s2"])],
            "version": batch["version"],
        },
    ).json()
    assert collected_response["code"] == 0, collected_response
    collected = collected_response["data"]
    assert collected["packagesCreated"] == 2
    assert collected["status"] == "COLLECTING"
    assert collected["packagesGenerated"] == 2
    assert collected["packagesPending"] == 0

    current = collected
    for expected_status in ("COLLEGE_REVIEW", "SA_CONFIRM", "ARCHIVED"):
        response = client.post(
            f"{BASE}/archive/batches/{bid}/advance",
            headers=hdr,
            json={"action": "APPROVE", "version": current["version"]},
        ).json()
        assert response["code"] == 0, response
        current = response["data"]
        assert current["status"] == expected_status

    detail = client.get(f"{BASE}/archive/batches/{bid}", headers=hdr).json()["data"]
    assert all(
        package["status"] == "ARCHIVED"
        and package["exportTaskId"]
        and package["packageFileId"]
        and package["missingItems"] == []
        for package in detail["packages"]
    )

    from app.db.session import get_sessionmaker
    from app.models import ExportTask
    from app.models.file import FileObject

    db = get_sessionmaker()()
    task = db.query(ExportTask).filter_by(
        module_code="student-affairs", export_mode="ARCHIVE_MANIFEST",
    ).one()
    assert task.status == "SUCCESS"
    assert task.row_count == 2
    assert task.file_hash and len(task.file_hash) == 64
    assert task.remark and task.remark.startswith("file-object:")
    file_id = int(task.remark.split(":", 1)[1])
    file_obj = db.get(FileObject, file_id)
    assert file_obj is not None
    assert file_obj.file_name.endswith(".xlsx")
    assert file_obj.biz_type == "AFFAIRS_ARCHIVE_MANIFEST"
    assert file_obj.sha256 == task.file_hash
    db.close()


def test_archive_batches_list(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    batch1 = _create_batch(client, hdr, "批次A")
    batch2 = _create_batch(client, hdr, "批次B")
    b1, b2 = batch1["batchId"], batch2["batchId"]

    collected = client.post(
        f"{BASE}/archive/batches/{b1}/collect",
        headers=hdr,
        json={"studentIds": [str(ids["s1"])], "version": batch1["version"]},
    ).json()
    assert collected["code"] == 0, collected

    response = client.get(f"{BASE}/archive/batches", headers=hdr).json()
    assert response["code"] == 0
    items = response["data"]["items"]
    assert len(items) >= 2
    by_id = {item["batchId"]: item for item in items}
    assert str(b1) in by_id and str(b2) in by_id
    assert by_id[str(b1)]["packageCount"] == 1
    assert by_id[str(b2)]["packageCount"] == 0

    drafts = client.get(f"{BASE}/archive/batches?status=DRAFT", headers=hdr).json()
    assert all(item["status"] == "DRAFT" for item in drafts["data"]["items"])
