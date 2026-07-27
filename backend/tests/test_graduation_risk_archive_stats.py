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


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_risk_scan_accept_process_close(client, auth_headers, db_mode):
    h = auth_headers
    bid = client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "风险扫描批", "batchNo": "GD-RK-SCAN-1", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    sid = client.post(STU, headers=h, json={"studentNo": "RK001", "realName": "预警测试生", "classId": make_org_class()}).json()["data"]["id"]
    client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid})  # stage=TOPIC_SELECTING, no topic → GD-R01

    scan = client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid})
    body = scan.json()["data"]
    assert body["newCasesCreated"] >= 1

    lst = client.get(GD_RISK, headers=h, params={"riskCode": "GD-R01", "batchId": bid}).json()["data"]["items"]
    assert len(lst) >= 1
    rid = lst[0]["id"]
    assert lst[0]["status"] == "OPEN"

    accept = client.post(f"{GD_RISK}/{rid}/accept", headers=h, json={})
    assert accept.json()["data"]["status"] == "PROCESSING"

    process = client.post(f"{GD_RISK}/{rid}/process", headers=h, json={"note": "已联系学生督促选题"})
    assert process.json()["data"]["handleNote"]

    short_close = client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "x"})
    assert short_close.json()["code"] != 0

    close = client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "学生已完成选题风险解除"})
    assert close.json()["data"]["status"] == "CLOSED"

    rescan = client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid}).json()["data"]
    assert rescan["newCasesCreated"] == 0  # 幂等，不重复生成已存在（含已关闭）项

    stats = client.get(f"{GD_RISK}/stats", headers=h, params={"batchId": bid}).json()["data"]
    assert stats["total"] >= 1


def test_archive_generate_blocks_submit_until_complete_then_files(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "AR001", "归档测试生")

    gen = client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h)
    body = gen.json()["data"]
    assert body["status"] == "PENDING_SUBMIT"
    checklist_labels = {item["label"] for item in body["checklist"] if item.get("required")}
    assert checklist_labels.issubset(set(body["missingItems"]))  # 全部必备清单材料缺失

    blocked = client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h)
    assert blocked.json()["code"] != 0

    detail = client.get(f"{GD_ARCHIVE}/{gid}", headers=h).json()["data"]
    assert detail["status"] == "PENDING_SUBMIT"

    stats = client.get(f"{GD_ARCHIVE}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1

    export = client.post(f"{GD_ARCHIVE}/export", headers=h)
    assert export.json()["code"] == 0
    assert export.json()["data"]["rowCount"] >= 1


def test_complete_archive_is_idempotent_and_archives_student_atomically(client, auth_headers, db_mode):
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (FileObject, GraduationDefenseScore, GraduationFinal, GraduationGrade,
                            GraduationMidterm, GraduationProposal, GraduationReview,
                            GraduationStudent, GraduationTaskBook, PortalSignRecord)
    h = auth_headers
    gid = _gd_student(client, h, "AR-COMPLETE-01", "完整归档测试生")
    db = get_sessionmaker()()
    file_obj = FileObject(
        tenant_id=1000000000000000001, file_key=f"test/final-{gid}.docx",
        file_name="final.docx", ext="docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=128, sha256=f"{int(gid):064x}"[-64:], biz_type="GRADUATION_FINAL", biz_id=str(gid),
        visibility="BIZ_SCOPED", status="AVAILABLE",
    )
    db.add(file_obj)
    db.flush()
    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), plagiarism_rate="8.0%",
        plagiarism_status="已检测", status="APPROVED", attachments_json=[str(file_obj.id)],
    )
    db.add(final)
    db.flush()
    db.add_all([
        GraduationTaskBook(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CONFIRMED",
                           taskbook_version=1),
        PortalSignRecord(tenant_id=1000000000000000001, student_id=int(gid),
                         biz_type="GRADUATION_TASKBOOK", biz_id=f"{int(gid)}:v1",
                         content_hash=f"taskbook-{gid}", signer_name="测试学生"),
        GraduationProposal(tenant_id=1000000000000000001, gd_student_id=int(gid), version="v1", status="APPROVED"),
        GraduationMidterm(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CHECKED_PASS"),
        GraduationReview(tenant_id=1000000000000000001, gd_student_id=int(gid), gd_final_id=final.id,
                         reviewer_name="李评阅", status="COMPLETED", score=88),
        GraduationDefenseScore(tenant_id=1000000000000000001, gd_student_id=int(gid),
                               judge_name="王评委", score=90, status="CONFIRMED"),
        GraduationGrade(tenant_id=1000000000000000001, gd_student_id=int(gid),
                        total_score=89, grade_level="良好", status="PUBLISHED"),
    ])
    db.commit()
    db.close()

    generated = client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h).json()["data"]
    assert generated["missingItems"] == []
    submitted = client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).json()["data"]
    submitted_retry = client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).json()["data"]
    assert submitted_retry["version"] == submitted["version"]

    filed = client.post(
        f"{GD_ARCHIVE}/{gid}/file", headers=h, json={"archiveBatchNo": "GDARCH-TEST-001"},
    ).json()["data"]
    filed_retry = client.post(
        f"{GD_ARCHIVE}/{gid}/file", headers=h, json={"archiveBatchNo": "GDARCH-TEST-001"},
    ).json()["data"]
    assert filed["status"] == "FILED"
    assert len(filed["manifestHash"]) == 64
    assert filed_retry["version"] == filed["version"]
    conflict = client.post(
        f"{GD_ARCHIVE}/{gid}/file", headers=h, json={"archiveBatchNo": "GDARCH-OTHER"},
    )
    assert conflict.status_code == 409

    db = get_sessionmaker()()
    assert db.get(GraduationStudent, int(gid)).stage == "ARCHIVED"
    db.close()


def test_stats_overview_and_college_comparison(client, auth_headers, db_mode):
    h = auth_headers
    _gd_student(client, h, "ST001", "统计测试生")

    overview = client.get(f"{GD_STATS}/overview", headers=h).json()["data"]
    assert overview["studentTotal"] >= 1
    assert "byStage" in overview and "mentor" in overview and "risk" in overview

    comp = client.get(f"{GD_STATS}/college-comparison", headers=h).json()["data"]
    assert isinstance(comp, list)

def test_risk_list_filter_by_student(client, auth_headers, db_mode):
    """gdStudentId 过滤：只返回该生风险，不串其他学生。"""
    h = auth_headers
    bid = client.post("/api/v1/graduation/batches", headers=h, json={
        "batchName": "风险过滤批", "batchNo": "GD-RK-FLT-1", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    sid_a = client.post(STU, headers=h, json={"studentNo": "RKF01", "realName": "过滤生甲", "classId": make_org_class()}).json()["data"]["id"]
    sid_b = client.post(STU, headers=h, json={"studentNo": "RKF02", "realName": "过滤生乙", "classId": make_org_class()}).json()["data"]["id"]
    gid_a = client.post(GD_STU, headers=h, json={"studentId": sid_a, "batchId": bid}).json()["data"]["id"]
    gid_b = client.post(GD_STU, headers=h, json={"studentId": sid_b, "batchId": bid}).json()["data"]["id"]
    scan = client.post(f"{GD_RISK}/scan", headers=h, params={"batchId": bid})
    assert scan.json()["code"] == 0, scan.json()

    only_a = client.get(GD_RISK, headers=h, params={"gdStudentId": gid_a, "batchId": bid}).json()["data"]["items"]
    assert len(only_a) >= 1
    assert all(str(r["gdStudentId"]) == str(gid_a) for r in only_a)

    only_b = client.get(GD_RISK, headers=h, params={"gdStudentId": gid_b, "batchId": bid}).json()["data"]["items"]
    assert all(str(r["gdStudentId"]) == str(gid_b) for r in only_b)
    a_ids = {r["id"] for r in only_a}
    assert a_ids.isdisjoint({r["id"] for r in only_b})
