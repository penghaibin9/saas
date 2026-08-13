"""V9.2 U4/M11/M12：过程指导 600 人真分页 + 130 人不足统计。"""
from __future__ import annotations

from datetime import datetime, timezone
import inspect

from app.db.session import get_sessionmaker
from app.models import GraduationBatch, GraduationGuidance, GraduationGuidancePlan, GraduationMidterm, GraduationStudent
from app.modules.graduation.services import graduation_process_consistency as process_read
from app.modules.graduation.services import graduation_guidance_stats_read_service as stats_read

TID = 1000000000000000001


def _seed():
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=TID,
            batch_name="U4 过程指导 600 人验收",
            batch_no=f"U4-PROCESS-{datetime.now(timezone.utc).timestamp():.6f}",
            academic_year="2026-2027",
            grade_year="2027届",
            planned_count=600,
            status="RUNNING",
        )
        db.add(batch)
        db.flush()
        students = [GraduationStudent(
            tenant_id=TID,
            batch_id=batch.id,
            student_no=f"M11{idx:04d}",
            name=f"M11学生{idx:04d}",
            class_name=f"软件{(idx - 1) // 50 + 1:02d}班",
            topic_title=f"M11课题{idx:04d}",
            stage="GUIDING",
            record_status="ACTIVE",
        ) for idx in range(1, 601)]
        db.add_all(students)
        db.flush()
        now = datetime.now(timezone.utc)
        guidance = []
        plans = []
        midterms = []
        for idx, student in enumerate(students, 1):
            for seq in range(3 if idx <= 470 else 1):
                guidance.append(GraduationGuidance(
                    tenant_id=TID,
                    gd_student_id=student.id,
                    guidance_date=now,
                    method="ONLINE",
                    content=f"第{seq + 1}次指导",
                ))
            plans.append(GraduationGuidancePlan(
                tenant_id=TID,
                gd_student_id=student.id,
                title=f"计划{idx:04d}",
                plan_date=now,
                status="PLANNED",
            ))
            midterms.append(GraduationMidterm(
                tenant_id=TID,
                gd_student_id=student.id,
                batch_id=batch.id,
                status="PENDING",
            ))
        db.add_all(guidance + plans + midterms)
        db.commit()
        return int(batch.id)
    finally:
        db.close()


def test_u4_read_models_lock_sql_join_pagination_and_full_stats():
    for fn in (process_read.list_guidance, process_read.list_plans, process_read.list_midterms):
        source = inspect.getsource(fn)
        assert ".join(GraduationStudent" in source
        assert ".offset(" in source and ".limit(" in source
        assert "db.get(GraduationStudent" not in source
    stats_source = inspect.getsource(stats_read.guidance_stats)
    assert ".outerjoin(" in stats_source
    assert ".group_by(" in stats_source
    assert "[:50]" not in stats_source


def test_u4_mysql_600_students_and_130_insufficient(db_mode, graduation_client, auth_headers):
    batch_id = _seed()

    guidance = graduation_client.get(
        "/api/v1/graduation/gd-guidances",
        headers=auth_headers,
        params={"batchId": batch_id, "page": 1, "pageSize": 20},
    ).json()["data"]
    assert guidance["total"] == 1540
    assert len(guidance["items"]) == 20

    late = graduation_client.get(
        "/api/v1/graduation/gd-guidances",
        headers=auth_headers,
        params={"batchId": batch_id, "keyword": "M110521", "page": 1, "pageSize": 20},
    ).json()["data"]
    assert late["total"] == 1
    assert late["items"][0]["studentName"] == "M11学生0521"

    plans = graduation_client.get(
        "/api/v1/graduation/gd-guidance-plans",
        headers=auth_headers,
        params={"batchId": batch_id, "page": 30, "pageSize": 20},
    ).json()["data"]
    assert plans["total"] == 600
    assert len(plans["items"]) == 20

    midterm = graduation_client.get(
        "/api/v1/graduation/gd-midterms",
        headers=auth_headers,
        params={"batchId": batch_id, "keyword": "M110521", "page": 1, "pageSize": 20},
    ).json()["data"]
    assert midterm["total"] == 1
    assert midterm["items"][0]["studentName"] == "M11学生0521"

    stats = graduation_client.get(
        "/api/v1/graduation/gd-guidances/stats",
        headers=auth_headers,
        params={"batchId": batch_id, "threshold": 3},
    ).json()["data"]
    assert stats["studentCount"] == 600
    assert stats["avgCount"] == 2.6
    assert stats["insufficientCount"] == 130
    assert len(stats["insufficientStudents"]) == 130
    assert stats["insufficientStudents"][0]["studentName"] == "M11学生0471"
    assert stats["insufficientStudents"][-1]["studentName"] == "M11学生0600"
