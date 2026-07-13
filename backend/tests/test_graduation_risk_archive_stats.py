"""毕业设计中心 · 问题预警 + 毕设归档 + 毕设统计测试：扫描生成→受理→处理→关闭；
归档清单生成(缺失材料拦截提交)→提交→核验归档→驳回；总览统计聚合。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

GD_RISK = "/api/v1/graduation/gd-risks"
GD_ARCHIVE = "/api/v1/graduation/gd-archives"
GD_STATS = "/api/v1/graduation/gd-stats"
GD_STU = "/api/v1/graduation/gd-students"
STU = "/api/v1/students"


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_risk_scan_accept_process_close(client, auth_headers, db_mode):
    h = auth_headers
    _gd_student(client, h, "RK001", "预警测试生")  # stage=TOPIC_SELECTING, no topic → GD-R01

    scan = client.post(f"{GD_RISK}/scan", headers=h)
    body = scan.json()["data"]
    assert body["newCasesCreated"] >= 1

    lst = client.get(GD_RISK, headers=h, params={"riskCode": "GD-R01"}).json()["data"]["items"]
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

    rescan = client.post(f"{GD_RISK}/scan", headers=h).json()["data"]
    assert rescan["newCasesCreated"] == 0  # 幂等，不重复生成已存在（含已关闭）项

    stats = client.get(f"{GD_RISK}/stats", headers=h).json()["data"]
    assert stats["total"] >= 1


def test_archive_generate_blocks_submit_until_complete_then_files(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "AR001", "归档测试生")

    gen = client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h)
    body = gen.json()["data"]
    assert body["status"] == "PENDING_SUBMIT"
    assert len(body["missingItems"]) == len(body["checklist"])  # 全部材料缺失

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
    from app.models import (GraduationDefenseScore, GraduationFinal, GraduationGrade,
                            GraduationMidterm, GraduationProposal, GraduationReview,
                            GraduationStudent, GraduationTaskBook)
    h = auth_headers
    gid = _gd_student(client, h, "AR-COMPLETE-01", "完整归档测试生")
    db = get_sessionmaker()()
    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), plagiarism_rate="8.0%",
        plagiarism_status="已检测", status="APPROVED", attachments_json=["test-file"],
    )
    db.add(final)
    db.flush()
    db.add_all([
        GraduationTaskBook(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CONFIRMED"),
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
    sid_a = _gd_student(client, h, "RKF01", "过滤生甲")
    sid_b = _gd_student(client, h, "RKF02", "过滤生乙")
    client.post(f"{GD_RISK}/scan", headers=h)

    only_a = client.get(GD_RISK, headers=h, params={"gdStudentId": sid_a}).json()["data"]["items"]
    assert len(only_a) >= 1
    assert all(str(r["gdStudentId"]) == str(sid_a) for r in only_a)

    only_b = client.get(GD_RISK, headers=h, params={"gdStudentId": sid_b}).json()["data"]["items"]
    assert all(str(r["gdStudentId"]) == str(sid_b) for r in only_b)
    a_ids = {r["id"] for r in only_a}
    assert a_ids.isdisjoint({r["id"] for r in only_b})
