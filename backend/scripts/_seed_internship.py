"""岗位实习域种子（挂在主租户 demo 上，用已有学生；幂等：已有实习记录则跳过）。
不新增/删除任何 StudentProfile，不影响 demo=5 / 主租户=100 基线。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (
    AttendanceException, EmpCompany, InternshipApplication, InternshipAuditTrail,
    InternshipBatch, InternshipLeave, InternshipMatch, InternshipPosition, InternshipRecord, RiskRecord,
    Role, StudentProfile, User, UserRole, WeeklyReport,
)

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

    # 真实关联的企业、岗位、正式申请、匹配冲突与校内指导教师账号。
    company = EmpCompany(
        tenant_id=tenant_id, name="华信智能科技有限公司", credit_code="91320594DEMO202601",
        industry="软件和信息技术服务业", nature="民营企业", city="苏州",
        contact_person="周明", cooperation_level="核心合作", status="ACTIVE",
        region="江苏省苏州市", address="吴中区数字产业园8号楼", scale="中型",
        source="SCHOOL_ENTERPRISE", coop_status="ACTIVE", qualification_status="PASSED",
    )
    db.add(company)
    db.flush()
    position = InternshipPosition(
        tenant_id=tenant_id, company_id=company.id, company_name=company.name, batch_id=batch.id,
        title="前端开发实习生", category="软件开发", major_requirement="软件技术/计算机应用",
        grade_requirement="2026届", work_location="苏州市吴中区", salary_range="3500-5000元/月",
        subsidy="餐补+交通补贴", headcount=5, allocated_count=1, mentor_name="周明",
        status="PUBLISHED", publish_at=now - timedelta(days=45),
    )
    db.add(position)
    db.flush()
    recs[0].enterprise_id = company.id
    recs[0].position_id = position.id
    recs[0].destination_type = "ASSIGNED"
    recs[0].eligibility_status = "QUALIFIED"

    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id, Role.role_code == "INTERN_MENTOR")).first()
    if role is None:
        role = Role(tenant_id=tenant_id, role_code="INTERN_MENTOR", role_name="岗位实习指导教师",
                    role_type="SYSTEM", status="ACTIVE")
        db.add(role)
        db.flush()
    teacher = db.scalars(select(User).where(
        User.tenant_id == tenant_id, User.login_name == "demo_intern_mentor")).first()
    if teacher is None:
        fallback = db.scalars(select(User).where(User.tenant_id == tenant_id).order_by(User.id)).first()
        teacher = User(tenant_id=tenant_id, login_name="demo_intern_mentor", real_name="刘强",
                       password_hash=fallback.password_hash if fallback else "demo-not-for-login",
                       user_type="TEACHER", status="ACTIVE")
        db.add(teacher)
        db.flush()
    if not db.scalars(select(UserRole).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == teacher.id,
            UserRole.role_id == role.id)).first():
        db.add(UserRole(tenant_id=tenant_id, user_id=teacher.id, role_id=role.id, status="ACTIVE"))
    recs[0].advisor_user_id = teacher.id
    recs[0].advisor_name = teacher.real_name

    db.add_all([
        InternshipApplication(
            tenant_id=tenant_id, record_id=recs[0].id, student_id=students[0].id, batch_id=batch.id,
            application_type="POSITION", volunteer_no=1, position_id=position.id,
            company_name=company.name, position_name=position.title, work_address=position.work_location,
            contact_name="周明", contact_phone="13800001234", application_note="第一志愿，专业对口",
            status="PENDING_REVIEW", submitted_at=now - timedelta(days=4),
        ),
        InternshipApplication(
            tenant_id=tenant_id, record_id=recs[1].id, student_id=students[1].id, batch_id=batch.id,
            application_type="SELF_ARRANGED", volunteer_no=0, company_name="星辰网络技术有限公司",
            position_name="软件测试实习生", work_address="苏州工业园区", contact_name="陈经理",
            contact_phone="13900005678", evidence_file_id="demo-internship-agreement-01",
            application_note="学生自主联系，协议及资质材料齐全", status="APPROVED",
            submitted_at=now - timedelta(days=12), reviewed_by_name="实习就业处",
            reviewed_at=now - timedelta(days=10), review_comment="材料完整，同意",
        ),
        InternshipMatch(
            tenant_id=tenant_id, record_id=recs[2].id, student_id=students[2].id,
            position_id=position.id, company_id=company.id, match_type="AUTO_MAJOR", score=92,
            major_hit=True, enterprise_hit=True, conflict_flag=True,
            conflict_reason="岗位容量临近上限，需人工确认名额", status="CONFLICT",
            remark="系统自动匹配后转人工复核",
        ),
        InternshipLeave(
            tenant_id=tenant_id, internship_id=recs[3].id, student_id=students[3].id,
            leave_type="SICK", start_date=(now + timedelta(days=20)).strftime("%Y-%m-%d"),
            end_date=(now + timedelta(days=21)).strftime("%Y-%m-%d"), days=2,
            reason="发热就医，已上传门诊证明", status="APPROVED",
            apply_by_name=students[3].real_name, review_by_name="刘强",
            review_at=now - timedelta(days=1), review_comment="证明有效，同意请假",
            file_id="demo-intern-leave-proof-01",
        ),
        InternshipAuditTrail(
            tenant_id=tenant_id, target_id=recs[0].id, target_type="INTERN_STUDENT",
            action="ASSIGN_POSITION", operator_name="实习就业处",
            detail_json={"companyName": company.name, "positionName": position.title},
            occurred_at=now - timedelta(days=8),
        ),
        InternshipAuditTrail(
            tenant_id=tenant_id, target_id=recs[0].id, target_type="INTERN_STUDENT",
            action="ASSIGN_ADVISOR", operator_name="实习就业处",
            detail_json={"advisorUserId": str(teacher.id), "advisorName": teacher.real_name},
            occurred_at=now - timedelta(days=7),
        ),
    ])

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
