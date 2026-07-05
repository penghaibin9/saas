"""演示租户（demo-school）六大模块完整演示数据（幂等 · 只新增，不修改/删除任何现有行）。
目标：登录页「进入演示环境」后，学生端/教师端/PC 端每个模块都有可看、可批、可跟进的内容。
- 演示学生 张同学 / 2026D0006（与 student_demo 账号同名，登录即见本人六域数据）
- 教师侧待办：待审请假 / 待批周报 / 打卡异常 / 学业预警 / 待批开题 / 未就业跟进 / 待办审批
- 教师范围：counselor_demo→数媒2601班；teacher_demo→指导学生（李导师）；admin_demo→全校
已存在（按 张同学 是否在库判断）则整体跳过，可安全重复执行。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (AcademicGrade, AcademicStudent, AcademicWarning, AttendanceException,
                        CsLeave, CsServiceStudent, CsWorkOrder, EmpJob, EmpStudent,
                        GraduationProposal, GraduationStudent, InternshipRecord, OrientationStudent,
                        StudentContact, StudentProfile, TeacherStudentScope, UnifiedMessage,
                        UnifiedTodo, WeeklyReport, WorkflowInstance, WorkflowTask)

TID2 = 1000000000000000003
DEMO_NAME = "张同学"
DEMO_NO = "2026D0006"
DEMO_CLASS = "数媒2601班"
MENTOR = "李导师"      # teacher_demo 真实姓名（毕设/实习指导关系按此收敛）
COUNSELOR = "王辅导"   # counselor_demo 真实姓名


def seed_demo_school(db) -> dict:
    if db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == TID2,
                  StudentProfile.real_name == DEMO_NAME)).first():
        return {"skipped": True}
    now = datetime.now()

    # ── 演示学生 张同学（新增，不动已有 演示学生1-5）──
    p = StudentProfile(tenant_id=TID2, student_no=DEMO_NO, real_name=DEMO_NAME, gender="男",
                       grade="2026", current_stage="INTERNSHIP", student_status="NORMAL",
                       status="ACTIVE")
    db.add(p)
    db.flush()
    db.add(StudentContact(tenant_id=TID2, student_id=p.id, contact_type="PHONE",
                          contact_value_encrypted="13900006666", is_primary=True,
                          verified_status="VERIFIED"))

    # 迎新（已完成态，展示全流程）
    db.add(OrientationStudent(tenant_id=TID2, name=DEMO_NAME, admission_no=f"LQ{DEMO_NO}",
                              student_id=p.id, class_name=DEMO_CLASS, grade="2026级",
                              stage="ENROLLED", report_status="CHECKED_IN", payment_status="PAID",
                              material_status="APPROVED", dorm_status="CHECKED_IN",
                              building="桂花苑2号楼", room="2-508-1", risk_level="LOW",
                              steps_json={"ACTIVATE": "DONE", "INFO": "DONE", "MATERIAL": "DONE",
                                          "PAYMENT": "DONE", "DORM": "DONE", "CHECKIN": "DONE",
                                          "CONFIRM": "DONE"}))
    # 在校服务：一条已批请假 + 一条待审请假（教师可现场演示审批）+ 一条已结工单
    cs = CsServiceStudent(tenant_id=TID2, name=DEMO_NAME, student_no=DEMO_NO, student_id=p.id,
                          class_name=DEMO_CLASS, care_level="NORMAL", risk_level="LOW",
                          counselor=COUNSELOR, record_status="ACTIVE")
    db.add(cs)
    db.flush()
    db.add(CsLeave(tenant_id=TID2, code="DLV-2026-0001", cs_student_id=cs.id, leave_type="SICK",
                   start_time=now - timedelta(days=9), duration="1 天", reason="感冒就医",
                   status="APPROVED", apply_time=now - timedelta(days=10), reviewer=COUNSELOR))
    db.add(CsLeave(tenant_id=TID2, code="DLV-2026-0002", cs_student_id=cs.id, leave_type="PERSONAL",
                   start_time=now + timedelta(days=1), duration="2 天", reason="家中有事需返乡处理",
                   status="PENDING_REVIEW", apply_time=now - timedelta(hours=3)))
    db.add(CsWorkOrder(tenant_id=TID2, code="DWO-2026-0001", cs_student_id=cs.id,
                       title="宿舍空调维修", wo_type="REPAIR", priority="MEDIUM",
                       status="COMPLETED", handler="后勤刘师傅"))
    # 学业：成绩 + 一条待处理预警（教师可演示处理/升级）
    acad = AcademicStudent(tenant_id=TID2, name=DEMO_NAME, student_no=DEMO_NO,
                           class_name=DEMO_CLASS, gpa=3.1, avg_score=81, failed_count=1,
                           obtained_credits=62, required_credits=120, warning_level="LOW",
                           warning_count=1, academic_status="WARNING", record_status="ACTIVE")
    db.add(acad)
    db.flush()
    for cn, cr, sc in [("UI设计基础", 4, 86), ("数据结构", 5, 55), ("职业素养", 2, 92)]:
        db.add(AcademicGrade(tenant_id=TID2, acad_student_id=acad.id, course_name=cn,
                             term="2025-2026-2", nature="REQUIRED", credit_value=cr, score=sc,
                             pass_status="PASSED" if sc >= 60 else "FAILED", exam_type="FINAL"))
    db.add(AcademicWarning(tenant_id=TID2, code="DAW-2026-0001", acad_student_id=acad.id,
                           warn_type="MULTI_FAIL", level="LOW", reason="数据结构不及格，请关注补考",
                           status="PENDING_HANDLE", owner=COUNSELOR, record_status="ACTIVE",
                           trigger_time=now - timedelta(days=2)))
    # 实习：在岗 + 一份已批周报 + 一份待批周报 + 一条待处理打卡异常（指导老师=李导师）
    rec = InternshipRecord(tenant_id=TID2, student_id=p.id, enterprise_name="星河数字创意有限公司",
                           position_name="UI设计实习生", advisor_name=MENTOR,
                           enterprise_mentor_name="周主管", status="ONBOARD", risk_level="LOW",
                           intern_start_date=datetime(2026, 3, 2), intern_end_date=datetime(2026, 8, 28))
    db.add(rec)
    db.flush()
    db.add(WeeklyReport(tenant_id=TID2, internship_id=rec.id, week_number=1,
                        work_content="熟悉设计规范与组件库，完成 3 张活动页初稿。",
                        harvest_content="掌握了设计走查流程。", plan_content="下周进入详情页改版。",
                        word_count=40, report_version=1, status="APPROVED",
                        review_comment="内容充实，继续保持。", reviewed_by_name=MENTOR,
                        submitted_at=now - timedelta(days=9)))
    db.add(WeeklyReport(tenant_id=TID2, internship_id=rec.id, week_number=2,
                        work_content="完成详情页改版初稿并跟进开发还原度走查，输出走查问题清单。",
                        harvest_content="学会用还原度清单推动开发协作。", plan_content="下周做可用性测试。",
                        word_count=52, report_version=1, status="PENDING_REVIEW",
                        submitted_at=now - timedelta(days=2)))
    db.add(AttendanceException(tenant_id=TID2, internship_id=rec.id, exception_type="OUT_OF_RANGE",
                               exception_date=now - timedelta(days=1), distance_km=2.6,
                               student_note="上午随企业导师外出参加客户评审会", streak_days=1,
                               status="PENDING_HANDLE"))
    # 毕设：指导中 + 一份待批开题（导师=李导师）
    gd = GraduationStudent(tenant_id=TID2, name=DEMO_NAME, student_no=DEMO_NO,
                           class_name=DEMO_CLASS, topic_title="校园活动数字海报生成工具设计与实现",
                           topic_source="教师申报", advisor_name=MENTOR, stage="GUIDING",
                           material_summary="任务书已确认", risk_level="LOW", record_status="ACTIVE")
    db.add(gd)
    db.flush()
    db.add(GraduationProposal(tenant_id=TID2, gd_student_id=gd.id, version="v1",
                              submit_at=now - timedelta(days=1), status="PENDING_REVIEW",
                              background="活动海报制作效率低", plan="模板引擎+素材库",
                              outcome="可用工具与论文"))
    # 就业：签约 + 材料已审（学生端就业页有内容）
    emp = EmpStudent(tenant_id=TID2, name=DEMO_NAME, student_no=DEMO_NO, grade="2026届",
                     class_name=DEMO_CLASS, destination_type="SIGNED",
                     company_name="星河数字创意有限公司", job_title="UI设计师",
                     salary_range="5k-7k", verify_status="VERIFIED", material_status="APPROVED",
                     help_level="NORMAL", risk_level="LOW", counselor=COUNSELOR,
                     record_status="ACTIVE")
    db.add(emp)

    # ── 配角学生（复用已有 演示学生1/2/3 档案，不改动其主档；只补域数据）──
    others = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == TID2, StudentProfile.real_name.like("演示学生%"),
        StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id)).all()
    for i, o in enumerate(others[:3], start=1):
        db.add(AcademicStudent(tenant_id=TID2, name=o.real_name, student_no=o.student_no,
                               class_name=DEMO_CLASS, gpa=2.4 + i * 0.2, avg_score=68 + i,
                               academic_status="NORMAL", warning_level="NONE", record_status="ACTIVE"))
        db.add(EmpStudent(tenant_id=TID2, name=o.real_name, student_no=o.student_no, grade="2026届",
                          class_name=DEMO_CLASS,
                          destination_type="UNEMPLOYED" if i < 3 else "FLEXIBLE",
                          verify_status="PENDING_HANDLE", material_status="NOT_SUBMITTED",
                          help_level="KEY" if i == 1 else "NORMAL", risk_level="LOW",
                          counselor=COUNSELOR, record_status="ACTIVE"))
    # 一条演示岗位（就业老师页岗位池）
    db.add(EmpJob(tenant_id=TID2, company_id=1, company_name="星河数字创意有限公司",
                  title="视觉设计师", category="设计", salary_range="6k-9k", headcount=3,
                  status="OPEN", publish_time=f"{now:%Y-%m-%d}"))

    # ── 审批中心：一条待审任务（PC/移动审批演示）──
    inst = WorkflowInstance(tenant_id=TID2, workflow_code="wf_student", source_module="student",
                            source_biz_type="PROFILE_CORRECTION", source_biz_id=p.id,
                            applicant_id=p.id, title=f"{DEMO_NAME} · 联系方式变更", status="RUNNING",
                            remark=DEMO_NAME)
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(tenant_id=TID2, instance_id=inst.id, node_code="COUNSELOR_REVIEW",
                        assignee_id=1, status="PENDING",
                        deadline_at=datetime.utcnow() + timedelta(days=2)))

    # ── 张同学的待办 + 站内通知（消息中心演示）──
    db.add(UnifiedTodo(tenant_id=TID2, source_module="internship", source_biz_id=rec.id,
                       todo_type="SUBMIT", assignee_id=p.id, student_id=p.id,
                       title="提交本周实习周报", status="PENDING"))
    db.add(UnifiedMessage(tenant_id=TID2, receiver_id=p.id, title="第 1 周周报已批阅通过",
                          content="指导老师评语：内容充实，继续保持。", message_type="ANNOUNCEMENT",
                          status="UNREAD"))

    # ── 教师范围（演示账号 SCOPED）──
    if not db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == TID2)).first():
        db.add(TeacherStudentScope(tenant_id=TID2, teacher_key="counselor_demo",
                                   teacher_name=COUNSELOR, role_code="COUNSELOR",
                                   scope_type="CLASS", ref_value=DEMO_CLASS, status="ACTIVE"))
        db.add(TeacherStudentScope(tenant_id=TID2, teacher_key="teacher_demo",
                                   teacher_name=MENTOR, role_code=None,
                                   scope_type="ADVISOR", ref_value=MENTOR, status="ACTIVE"))

    db.commit()
    return {"demoStudent": DEMO_NAME, "studentNo": DEMO_NO, "tenant": "demo-school", "domains": 6}
