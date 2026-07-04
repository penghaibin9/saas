"""岗位实习域种子（挂在主租户 demo 上，用已有学生；幂等：已有实习记录则跳过）。
不新增/删除任何 StudentProfile，不影响 demo=5 / 主租户=100 基线。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (AttendanceException, InternshipAuditTrail, InternshipBatch,
                        InternshipRecord, RiskRecord, StudentProfile, WeeklyReport)

TID = 1000000000000000001


def seed_internship(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(InternshipRecord).where(InternshipRecord.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()

    batch = InternshipBatch(tenant_id=tenant_id, batch_name="2026 届春季实习批次",
                            batch_no="INT-2026-SPRING", start_date=datetime(2026, 3, 2),
                            end_date=datetime(2026, 8, 28), status="RUNNING")
    db.add(batch)
    db.flush()

    students = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id).limit(8)).all()
    if not students:
        return {"skipped": True, "reason": "no students"}

    ents = ["华信智能科技有限公司", "星辰网络技术有限公司"]
    positions = ["前端开发实习生", "测试实习生", "运维实习生", "产品实习生"]
    advisors = ["刘强", "陈敏", "王磊"]
    risk_levels = ["NONE", "NONE", "NONE", "LOW", "MEDIUM", "HIGH", "NONE", "NONE"]
    recs = []
    for i, stu in enumerate(students):
        r = InternshipRecord(
            tenant_id=tenant_id, student_id=stu.id, batch_id=batch.id,
            enterprise_name=ents[i % 2], position_name=positions[i % 4],
            advisor_name=advisors[i % 3], enterprise_mentor_name="周工",
            status="ONBOARD" if i < 7 else "READY", risk_level=risk_levels[i],
            intern_start_date=datetime(2026, 3, 2), intern_end_date=datetime(2026, 8, 28),
            insurance_info="实习责任险 · 有效至 2026-08-31", agreement_info="三方协议已生效")
        db.add(r)
        db.flush()
        recs.append(r)

    # 打卡异常 3 条（1 条连续 3 天，待核实）
    db.add_all([
        AttendanceException(tenant_id=tenant_id, internship_id=recs[0].id,
                            exception_type="OUT_OF_RANGE", exception_date=now - timedelta(hours=2),
                            distance_km=1.2, gps_accuracy=12.0, address="苏州市吴中区XX产业园",
                            student_note="本周被安排到客户现场装机，附现场照片", streak_days=3,
                            status="PENDING_HANDLE"),
        AttendanceException(tenant_id=tenant_id, internship_id=recs[5].id,
                            exception_type="MOCK_LOCATION", exception_date=now - timedelta(days=1),
                            device_risk_flag="is_mock", student_note="", streak_days=1,
                            status="PENDING_HANDLE"),
        AttendanceException(tenant_id=tenant_id, internship_id=recs[1].id,
                            exception_type="MISSING", exception_date=now - timedelta(days=2),
                            student_note="忘记打卡", streak_days=0, status="COMPLETED",
                            handle_action="REASONABLE", handle_comment="已电话核实，属实",
                            handled_by_name="刘强", handled_at=now - timedelta(days=1)),
    ])

    # 周报 5 条（含重交 v2、逾期）
    db.add_all([
        WeeklyReport(tenant_id=tenant_id, internship_id=recs[0].id, week_number=3,
                     work_content="本周主要在客户现场参与装机与联调，处理接口 Mock 与排错。",
                     harvest_content="掌握了接口 Mock 与联调排错方法，理解了现场交付流程。",
                     plan_content="返回公司参与组件库开发与单测补充。", word_count=1430,
                     report_version=2, risk_flag="", submitted_at=now - timedelta(hours=6),
                     status="PENDING_REVIEW"),
        WeeklyReport(tenant_id=tenant_id, internship_id=recs[1].id, week_number=4,
                     work_content="完成登录与订单模块回归测试，梳理用例分层。",
                     harvest_content="学会了用例分层设计与缺陷定位。",
                     plan_content="下周开始接口自动化。", word_count=1120, report_version=1,
                     submitted_at=now - timedelta(hours=2), status="PENDING_REVIEW"),
        WeeklyReport(tenant_id=tenant_id, internship_id=recs[2].id, week_number=3,
                     work_content="部署与监控配置。", harvest_content="熟悉了容器编排。",
                     plan_content="补充告警规则。", word_count=980, report_version=1,
                     submitted_at=now - timedelta(days=3), status="APPROVED",
                     review_action="APPROVE", review_comment="内容扎实，通过",
                     reviewed_by_name="王磊", reviewed_at=now - timedelta(days=2)),
        WeeklyReport(tenant_id=tenant_id, internship_id=recs[3].id, week_number=2,
                     work_content="需求梳理。", harvest_content="了解了产品流程。",
                     plan_content="继续跟进。", word_count=420, report_version=1, risk_flag="HIGH",
                     submitted_at=now - timedelta(days=4), status="RETURNED",
                     review_action="RETURN", review_comment="字数不足，内容偏薄，请补充细化",
                     reviewed_by_name="陈敏", reviewed_at=now - timedelta(days=3)),
        WeeklyReport(tenant_id=tenant_id, internship_id=recs[4].id, week_number=4,
                     work_content="", harvest_content="", plan_content="", word_count=0,
                     report_version=1, status="OVERDUE"),
    ])

    # 风险单 2 条
    db.add_all([
        RiskRecord(tenant_id=tenant_id, internship_id=recs[0].id, risk_code="INT-R07",
                   risk_title="连续 3 天打卡异常", risk_level="HIGH", source_module="system",
                   owner_name="刘强", deadline_at=now + timedelta(days=3), status="PROCESSING",
                   last_follow_at=now - timedelta(days=1),
                   last_follow_note="07-01 已电话核实客户现场安排"),
        RiskRecord(tenant_id=tenant_id, internship_id=recs[3].id, risk_code="INT-R10",
                   risk_title="周报质量不达标", risk_level="MEDIUM", source_module="system",
                   owner_name="陈敏", deadline_at=now + timedelta(days=5), status="PENDING_HANDLE"),
    ])
    db.flush()

    db.add(InternshipAuditTrail(tenant_id=tenant_id, target_id=recs[0].id, target_type="RECORD",
                                action="CREATED", operator_name="系统",
                                detail_json={"batch": "INT-2026-SPRING"},
                                occurred_at=now - timedelta(days=10)))
    db.commit()
    return {"records": len(recs), "batch": batch.batch_no}
