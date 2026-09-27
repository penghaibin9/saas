"""13A-P6 学工归档 · 端到端（真实 DB 模式）。

批次→收集真实档案包→逐级流转→ARCHIVED，并登记公共文件对象承载的归档清单导出任务。
"""
from __future__ import annotations

from datetime import datetime, timedelta

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
    assert collected["packagesQueued"] == 2
    assert collected["packagesGenerated"] == 0
    assert collected["packagesPending"] == 2

    from app.core.context import set_tenant
    from app.services import affairs_archive_service

    set_tenant({"tenantId": str(TID)})
    try:
        worker = affairs_archive_service.run_pending_packages(limit=10)
    finally:
        set_tenant(None)
    assert worker == {"claimed": 2, "succeeded": 2, "failed": 0, "stale": 0}

    detail_after_worker = client.get(f"{BASE}/archive/batches/{bid}", headers=hdr).json()["data"]
    assert all(package["status"] == "SUBMITTED" for package in detail_after_worker["packages"])

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


def test_college_archive_review_requires_every_package_in_own_college(client, db_mode):
    """学院节点不能把混批或其他学院整批推进；本院整批仍可正常办理。"""
    from app.db.session import get_sessionmaker
    from app.models import (AffairsAuditTrail, College, Major, SchoolClass,
                            StudentProfile, TeacherStudentScope)

    db = get_sessionmaker()()
    try:
        college_a = College(tenant_id=TID, college_name="归档甲学院", status="ACTIVE")
        college_b = College(tenant_id=TID, college_name="归档乙学院", status="ACTIVE")
        db.add_all([college_a, college_b]); db.flush()
        major_a = Major(tenant_id=TID, college_id=college_a.id, major_name="归档甲专业", status="ACTIVE")
        major_b = Major(tenant_id=TID, college_id=college_b.id, major_name="归档乙专业", status="ACTIVE")
        db.add_all([major_a, major_b]); db.flush()
        class_a = SchoolClass(tenant_id=TID, major_id=major_a.id, class_name="归档甲班", grade="2023", status="ACTIVE")
        class_b = SchoolClass(tenant_id=TID, major_id=major_b.id, class_name="归档乙班", grade="2023", status="ACTIVE")
        db.add_all([class_a, class_b]); db.flush()
        student_a = StudentProfile(tenant_id=TID, student_no="ARCH-A01", real_name="归档甲生",
                                   college_id=college_a.id, major_id=major_a.id, class_id=class_a.id,
                                   current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
        student_b = StudentProfile(tenant_id=TID, student_no="ARCH-B01", real_name="归档乙生",
                                   college_id=college_b.id, major_id=major_b.id, class_id=class_b.id,
                                   current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
        db.add_all([student_a, student_b])
        db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", teacher_name="学院管理员",
                                   role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value="归档甲学院", status="ACTIVE"))
        db.commit()
        student_ids = {"A": str(student_a.id), "B": str(student_b.id)}
    finally:
        db.close()

    school = _hdr(client, "school_admin01")
    college = _hdr(client, "college_admin01")

    def review_ready(name, ids):
        batch = _create_batch(client, school, name)
        bid = batch["batchId"]
        collected = client.post(f"{BASE}/archive/batches/{bid}/collect", headers=school,
                                json={"studentIds": ids, "version": batch["version"]}).json()
        assert collected["code"] == 0, collected
        advanced = client.post(f"{BASE}/archive/batches/{bid}/advance", headers=school,
                               json={"action": "APPROVE", "version": collected["data"]["version"]}).json()
        assert advanced["code"] == 0, advanced
        assert advanced["data"]["status"] == "COLLEGE_REVIEW"
        return bid, advanced["data"]["version"]

    def audit_count(bid):
        db = get_sessionmaker()()
        try:
            return db.query(AffairsAuditTrail).filter_by(
                tenant_id=TID, biz_type="ARCHIVE", biz_id=int(bid), action="ADVANCE",
            ).count()
        finally:
            db.close()

    for name, ids in [
        ("混合两院批次", [student_ids["A"], student_ids["B"]]),
        ("其他学院批次", [student_ids["B"]]),
    ]:
        bid, version = review_ready(name, ids)
        before_audit = audit_count(bid)
        rejected = client.post(f"{BASE}/archive/batches/{bid}/advance", headers=college,
                               json={"action": "APPROVE", "version": version})
        assert rejected.status_code == 403 and rejected.json()["bizCode"] == "NO_DATA_SCOPE"
        after = client.get(f"{BASE}/archive/batches/{bid}", headers=school).json()["data"]
        assert after["status"] == "COLLEGE_REVIEW" and after["version"] == version
        assert audit_count(bid) == before_audit

    bid, version = review_ready("本学院批次", [student_ids["A"]])
    before_audit = audit_count(bid)
    approved = client.post(f"{BASE}/archive/batches/{bid}/advance", headers=college,
                           json={"action": "APPROVE", "version": version}).json()
    assert approved["code"] == 0, approved
    assert approved["data"]["status"] == "SA_CONFIRM"
    assert audit_count(bid) == before_audit + 1


def test_archive_generation_lease_reclaims_stale_worker_without_late_overwrite(db_mode):
    ids = _seed(db_mode)
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import ArchiveBatch, ArchivePackage
    from app.services import affairs_archive_service as archive

    db = get_sessionmaker()()
    batch = ArchiveBatch(tenant_id=TID, batch_name="租约回收", status="COLLECTING")
    db.add(batch); db.flush()
    package = ArchivePackage(
        tenant_id=TID, batch_id=batch.id, student_id=ids["s1"],
        missing_items_json="[]", status="PENDING_GEN",
    )
    db.add(package); db.commit()
    package_id = int(package.id)
    db.close()

    set_tenant({"tenantId": str(TID)})
    try:
        first = archive._claim_pending_packages(limit=1)
        assert len(first) == 1
        db = get_sessionmaker()()
        row = db.get(ArchivePackage, package_id)
        row.generation_lease_until = datetime.utcnow() - timedelta(seconds=1)
        db.commit(); db.close()

        second = archive._claim_pending_packages(limit=1)
        assert len(second) == 1
        assert second[0]["leaseToken"] != first[0]["leaseToken"]
        assert archive._fail_package_generation(
            package_id, first[0]["leaseToken"], first[0]["version"], "late worker",
        ) is False
        db = get_sessionmaker()()
        row = db.get(ArchivePackage, package_id)
        assert row.status == "GENERATING"
        assert row.generation_lease_token == second[0]["leaseToken"]
        assert row.generation_attempts == 2
        db.close()
    finally:
        set_tenant(None)
