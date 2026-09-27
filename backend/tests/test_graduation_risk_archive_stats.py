"""毕业设计中心 · 问题预警 + 毕设归档 + 毕设统计测试：扫描生成→受理→处理→关闭；
归档清单生成(缺失材料拦截提交)→提交→核验归档→驳回；总览统计聚合。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

GD_RISK = "/api/v1/graduation/gd-risks"
GD_ARCHIVE = "/api/v1/graduation/gd-archives"
GD_STATS = "/api/v1/graduation/gd-stats"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(graduation_client, h, no, name):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    return graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_risk_scan_accept_process_close(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bid = graduation_client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "风险扫描批", "batchNo": "GD-RK-SCAN-1", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    sid = graduation_client.post(STU, headers=h, json={"studentNo": "RK001", "realName": "预警测试生", "classId": make_org_class()}).json()["data"]["id"]
    graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid})  # stage=TOPIC_SELECTING, no topic → GD-R01

    scan = graduation_client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid})
    body = scan.json()["data"]
    assert body["newCasesCreated"] >= 1

    lst = graduation_client.get(GD_RISK, headers=h, params={"riskCode": "GD-R01", "batchId": bid}).json()["data"]["items"]
    assert len(lst) >= 1
    rid = lst[0]["id"]
    assert lst[0]["status"] == "OPEN"

    accept = graduation_client.post(f"{GD_RISK}/{rid}/accept", headers=h, json={})
    assert accept.json()["data"]["status"] == "PROCESSING"

    process = graduation_client.post(f"{GD_RISK}/{rid}/process", headers=h, json={"note": "已联系学生督促选题"})
    assert process.json()["data"]["handleNote"]

    short_close = graduation_client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "x"})
    assert short_close.json()["code"] != 0

    close = graduation_client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "学生已完成选题风险解除"})
    assert close.json()["data"]["status"] == "CLOSED"

    rescan = graduation_client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid}).json()["data"]
    assert rescan["newCasesCreated"] == 0  # 幂等，不重复生成已存在（含已关闭）项

    stats = graduation_client.get(f"{GD_RISK}/stats", headers=h, params={"batchId": bid}).json()["data"]
    assert stats["total"] >= 1


def test_archive_generate_blocks_submit_until_complete_then_files(graduation_client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(graduation_client, h, "AR001", "归档测试生")

    gen = graduation_client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h)
    body = gen.json()["data"]
    assert body["status"] == "PENDING_SUBMIT"
    checklist_labels = {item["label"] for item in body["checklist"] if item.get("required")}
    assert checklist_labels.issubset(set(body["missingItems"]))  # 全部必备清单材料缺失

    blocked = graduation_client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h)
    assert blocked.json()["code"] != 0

    detail = graduation_client.get(f"{GD_ARCHIVE}/{gid}", headers=h).json()["data"]
    assert detail["status"] == "PENDING_SUBMIT"

    stats = graduation_client.get(f"{GD_ARCHIVE}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1

    export = graduation_client.post(f"{GD_ARCHIVE}/export", headers=h)
    assert export.json()["code"] == 0
    assert export.json()["data"]["rowCount"] >= 1


def test_complete_archive_is_idempotent_and_archives_student_atomically(graduation_client, auth_headers, db_mode):
    from datetime import datetime
    from sqlalchemy import text
    from app.db.session import get_sessionmaker
    from app.models import (GraduationDefenseScore, GraduationFinal, GraduationGrade, GraduationMentor,
                            GraduationMidterm, GraduationProposal, GraduationReview,
                            GraduationStudent, GraduationTaskBook, PortalSignRecord)
    from app.models.file import FileAsset, FileVersion
    from app.models.graduation_material import GraduationStudentMaterial
    h = auth_headers
    gid = _gd_student(graduation_client, h, "AR-COMPLETE-01", "完整归档测试生")
    uploaded = graduation_client.post(
        "/api/v1/files", headers=h,
        files={"file": (
            "final.pdf", b"%PDF-1.4 graduation final document",
            "application/pdf",
        )},
        params={"bizType": "GRADUATION_FINAL", "bizId": str(gid)},
    ).json()
    assert uploaded["code"] == 0, uploaded
    file_id = int(uploaded["data"]["fileId"])

    db = get_sessionmaker()()
    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), plagiarism_rate="8.0%",
        plagiarism_status="已检测", status="APPROVED", attachments_json=[str(file_id)],
    )
    db.add(final)
    db.flush()
    stu = db.get(GraduationStudent, int(gid))
    asset = FileAsset(tenant_id=1000000000000000001, asset_code=f"archive-final-{gid}",
                      title="归档定稿", category_code="GRADUATION_FINAL")
    db.add(asset)
    db.flush()
    version = FileVersion(tenant_id=1000000000000000001, asset_id=asset.id,
                          file_object_id=file_id, version_no=1, status="APPROVED", is_current=True)
    db.add(version)
    db.flush()
    material = GraduationStudentMaterial(
        tenant_id=1000000000000000001, batch_id=stu.batch_id, gd_student_id=int(gid),
        material_code="THESIS_FINAL", material_name="成果定稿", biz_stage="SUBMISSION",
        source_record_type="FINAL", source_record_id=str(final.id),
        asset_id=asset.id, current_version_id=version.id,
        business_status="APPROVED", review_status="APPROVED",
    )
    db.add(material)
    db.flush()
    reviewers = [
        GraduationMentor(tenant_id=1000000000000000001, teacher_no=f"AR-{gid}-{n}",
                         teacher_name=name, qualification_status="QUALIFIED")
        for n, name in ((1, "李评阅"), (2, "王评阅"))
    ]
    db.add_all(reviewers)
    db.flush()
    first_review = GraduationReview(tenant_id=1000000000000000001, gd_student_id=int(gid),
                                    gd_final_id=final.id, reviewer_name="李评阅",
                                    reviewer_mentor_id=reviewers[0].id, status="COMPLETED", score=88)
    second_review = GraduationReview(tenant_id=1000000000000000001, gd_student_id=int(gid),
                                     gd_final_id=final.id, reviewer_name="王评阅",
                                     reviewer_mentor_id=reviewers[1].id, status="COMPLETED", score=88)
    db.add_all([
        GraduationTaskBook(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CONFIRMED",
                           taskbook_version=1),
        PortalSignRecord(tenant_id=1000000000000000001, student_id=int(gid),
                         biz_type="GRADUATION_TASKBOOK", biz_id=f"{int(gid)}:v1",
                         content_hash=f"taskbook-{gid}", signer_name="测试学生"),
        GraduationProposal(tenant_id=1000000000000000001, gd_student_id=int(gid), version="v1", status="APPROVED"),
        GraduationMidterm(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CHECKED_PASS"),
        first_review,
        GraduationDefenseScore(tenant_id=1000000000000000001, gd_student_id=int(gid),
                               judge_name="王评委", score=90, status="CONFIRMED"),
        GraduationGrade(tenant_id=1000000000000000001, gd_student_id=int(gid),
                        total_score=89, grade_level="良好", status="PUBLISHED"),
    ])
    db.flush()
    file_hash = db.execute(text("SELECT sha256 FROM t_file_object WHERE id=:file_id"), {"file_id": file_id}).scalar_one()
    db.execute(text("UPDATE t_gd_review SET material_id=:material,file_version_id=:version,source_sha256=:sha "
                    "WHERE tenant_id=:tenant AND id=:first"), {
        "material": material.id, "version": version.id, "sha": file_hash,
        "tenant": 1000000000000000001, "first": first_review.id,
    })
    db.commit()
    db.close()

    one_reviewer = graduation_client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h).json()["data"]
    assert any(item["item"] == "review" and not item["present"] for item in one_reviewer["checklist"])
    assert graduation_client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).status_code == 409
    db = get_sessionmaker()()
    db.add(second_review)
    db.flush()
    db.execute(text("UPDATE t_gd_review SET material_id=:material,file_version_id=:version,source_sha256=:sha "
                    "WHERE tenant_id=:tenant AND id=:review"), {
        "material": material.id, "version": version.id, "sha": file_hash,
        "tenant": 1000000000000000001, "review": second_review.id,
    })
    db.commit()
    db.close()

    generated = graduation_client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h).json()["data"]
    assert generated["missingItems"] == []
    submitted = graduation_client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).json()["data"]
    submitted_retry = graduation_client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).json()["data"]
    assert submitted_retry["version"] == submitted["version"]

    filed = graduation_client.post(
        f"{GD_ARCHIVE}/{gid}/file", headers=h, json={"archiveBatchNo": "GDARCH-TEST-001"},
    ).json()["data"]
    filed_retry = graduation_client.post(
        f"{GD_ARCHIVE}/{gid}/file", headers=h, json={"archiveBatchNo": "GDARCH-TEST-001"},
    ).json()["data"]
    assert filed["status"] == "FILED"
    assert len(filed["manifestHash"]) == 64
    assert filed_retry["version"] == filed["version"]
    conflict = graduation_client.post(
        f"{GD_ARCHIVE}/{gid}/file", headers=h, json={"archiveBatchNo": "GDARCH-OTHER"},
    )
    assert conflict.status_code == 409

    db = get_sessionmaker()()
    assert db.get(GraduationStudent, int(gid)).stage == "ARCHIVED"
    db.close()


def test_stats_overview_and_college_comparison(graduation_client, auth_headers, db_mode):
    h = auth_headers
    _gd_student(graduation_client, h, "ST001", "统计测试生")

    overview = graduation_client.get(f"{GD_STATS}/overview", headers=h).json()["data"]
    assert overview["studentTotal"] >= 1
    assert "byStage" in overview and "mentor" in overview and "risk" in overview

    comp = graduation_client.get(f"{GD_STATS}/college-comparison", headers=h).json()["data"]
    assert isinstance(comp, list)

def test_risk_list_filter_by_student(graduation_client, auth_headers, db_mode):
    """gdStudentId 过滤：只返回该生风险，不串其他学生。"""
    h = auth_headers
    bid = graduation_client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "风险过滤批", "batchNo": "GD-RK-FLT-1", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    sid_a = graduation_client.post(STU, headers=h, json={"studentNo": "RKF01", "realName": "过滤生甲", "classId": make_org_class()}).json()["data"]["id"]
    sid_b = graduation_client.post(STU, headers=h, json={"studentNo": "RKF02", "realName": "过滤生乙", "classId": make_org_class()}).json()["data"]["id"]
    gid_a = graduation_client.post(GD_STU, headers=h, json={"studentId": sid_a, "batchId": bid}).json()["data"]["id"]
    gid_b = graduation_client.post(GD_STU, headers=h, json={"studentId": sid_b, "batchId": bid}).json()["data"]["id"]
    scan = graduation_client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid})
    assert scan.json()["code"] == 0, scan.json()

    only_a = graduation_client.get(GD_RISK, headers=h, params={"gdStudentId": gid_a, "batchId": bid}).json()["data"]["items"]
    assert len(only_a) >= 1
    assert all(str(r["gdStudentId"]) == str(gid_a) for r in only_a)

    only_b = graduation_client.get(GD_RISK, headers=h, params={"gdStudentId": gid_b, "batchId": bid}).json()["data"]["items"]
    assert all(str(r["gdStudentId"]) == str(gid_b) for r in only_b)
    a_ids = {r["id"] for r in only_a}
    assert a_ids.isdisjoint({r["id"] for r in only_b})
