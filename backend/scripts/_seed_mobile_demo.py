"""移动端演示学生种子：把主租户首个学生设为「李晓萌」（对应 mock-login student01 的 realName），
并为其补齐六域"本人"记录，使学生端小程序 /mobile/*/my 能看到真实跨域数据。
幂等；不新增 StudentProfile（重命名，主租户学生数仍=100）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (AcademicGrade, AcademicStudent, AcademicWarning, College, CsLeave, CsServiceStudent,
                        CsWorkOrder, EmpMaterial, EmpStudent, GraduationStudent, InternshipRecord,
                        Major, OrientationBatch, OrientationStudent, SchoolClass, StudentProfile,
                        UnifiedMessage, UnifiedTodo)
from app.services.orientation_flow_service import (ensure_published_flow_version,
                                                    ensure_student_steps)

TID = 1000000000000000001
DEMO_NAME = "张一鸣"
DEMO_NO = "2023100001"


def seed_mobile_demo(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == tenant_id,
                  StudentProfile.real_name == DEMO_NAME)).first():
        return {"skipped": True}
    prof = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == tenant_id,
                      StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id)).first()
    if not prof:
        return {"skipped": True, "reason": "no student"}
    prof.real_name = DEMO_NAME
    prof.student_no = DEMO_NO
    prof.grade = "2023"
    prof.current_stage = "INTERNSHIP"
    now = datetime.now()
    school_class = db.get(SchoolClass, prof.class_id)
    major = db.get(Major, prof.major_id)
    college = db.get(College, prof.college_id)
    if not school_class or not major or not college:
        raise RuntimeError("移动演示迎新种子需要学生已绑定完整稳定组织")
    orientation_batch = db.scalars(select(OrientationBatch).where(
        OrientationBatch.tenant_id == tenant_id,
        OrientationBatch.batch_no == "MOBILE-DEMO-ORI",
    )).first()
    if not orientation_batch:
        flow_version = ensure_published_flow_version(db, tenant_id)
        orientation_batch = OrientationBatch(
            tenant_id=tenant_id, batch_name="移动演示迎新批次", batch_no="MOBILE-DEMO-ORI",
            year="2023", status="CLOSED", planned_count=1, remark="移动演示历史批次",
            flow_version_id=flow_version.id,
        )
        db.add(orientation_batch); db.flush()

    # 实习：首条实习记录本就 link 到首个学生（=现在的李晓萌），确保存在
    rec = db.scalars(select(InternshipRecord).where(InternshipRecord.tenant_id == tenant_id,
                     InternshipRecord.student_id == prof.id)).first()
    if not rec:
        db.add(InternshipRecord(tenant_id=tenant_id, student_id=prof.id, enterprise_name="华信智能科技有限公司",
                                position_name="前端开发实习生", advisor_name="刘强", status="ONBOARD",
                                risk_level="LOW", intern_start_date=datetime(2026, 3, 2),
                                intern_end_date=datetime(2026, 8, 28)))

    # 迎新
    orientation_student = OrientationStudent(tenant_id=tenant_id, batch_id=orientation_batch.id,
                              name=DEMO_NAME, admission_no="LQ2023100001", student_id=prof.id,
                              identity_status="LINKED",
                              college_id=college.id, college_name=college.college_name,
                              major_id=major.id, major_name=major.major_name,
                              class_id=school_class.id, class_name=school_class.class_name, grade="2023级",
                              stage="ENROLLED", report_status="CHECKED_IN", payment_status="PAID",
                              material_status="APPROVED", dorm_status="CHECKED_IN", building="梧桐苑1号楼",
                              room="1-302-2", risk_level="LOW",
                              steps_json={"ACTIVATE": "DONE", "INFO": "DONE", "MATERIAL": "DONE",
                                          "PAYMENT": "DONE", "DORM": "DONE", "CHECKIN": "DONE",
                                          "CONFIRM": "DONE"},
                              source_type="MANUAL", source_record_id="LQ2023100001")
    db.add(orientation_student); db.flush()
    ensure_student_steps(db, orientation_student, status_source="PROCESS_FACT")
    # 在校服务
    cs = CsServiceStudent(tenant_id=tenant_id, name=DEMO_NAME, student_no=DEMO_NO, class_name="软件2301班",
                          care_level="NORMAL", risk_level="LOW", counselor="李辅导")
    db.add(cs)
    db.flush()
    db.add(CsLeave(tenant_id=tenant_id, code="LV-2026-1001", cs_student_id=cs.id, leave_type="SICK",
                   start_time=now - timedelta(days=5), duration="1 天", reason="感冒就医", status="APPROVED",
                   apply_time=now - timedelta(days=6), reviewer="李辅导"))
    db.add(CsWorkOrder(tenant_id=tenant_id, code="WO-2026-1001", cs_student_id=cs.id, title="宿舍网络报修",
                       wo_type="REPAIR", priority="MEDIUM", status="COMPLETED", handler="后勤张师傅"))
    # 学业
    acad = AcademicStudent(tenant_id=tenant_id, name=DEMO_NAME, student_no=DEMO_NO, class_name="软件2301班",
                           gpa=3.2, avg_score=82, failed_count=1, obtained_credits=66, required_credits=120,
                           warning_level="LOW", warning_count=1, academic_status="WARNING")
    db.add(acad)
    db.flush()
    for cn, cr, sc in [("Web前端开发", 4, 88), ("高等数学", 5, 55), ("职业素养", 2, 90)]:
        db.add(AcademicGrade(tenant_id=tenant_id, acad_student_id=acad.id, course_name=cn, term="2025-2026-2",
                             nature="REQUIRED", credit_value=cr, score=sc,
                             pass_status="PASSED" if sc >= 60 else "FAILED", exam_type="FINAL"))
    db.add(AcademicWarning(tenant_id=tenant_id, code="AW-2026-1001", acad_student_id=acad.id,
                           warn_type="MULTI_FAIL", level="LOW", reason="高等数学不及格，提醒关注",
                           status="PROCESSING", owner="李辅导", trigger_time=now - timedelta(days=3)))
    # 毕设
    db.add(GraduationStudent(tenant_id=tenant_id, name=DEMO_NAME, student_no=DEMO_NO, class_name="软件2301班",
                             topic_title="基于 Vue3 的校园二手交易平台设计与实现", topic_source="教师申报",
                             advisor_name="王芳", stage="MIDTERM", material_summary="开题已通过",
                             risk_level="LOW", midterm_conclusion="通过"))
    # 就业
    emp = EmpStudent(tenant_id=tenant_id, name=DEMO_NAME, student_no=DEMO_NO, grade="2026届",
                     class_name="软件2301班", destination_type="SIGNED", company_name="杭州云启科技有限公司",
                     job_title="前端开发工程师", salary_range="6k-8k", verify_status="VERIFIED",
                     material_status="APPROVED", help_level="NORMAL", risk_level="LOW", counselor="李辅导")
    db.add(emp)
    db.flush()
    db.add(EmpMaterial(tenant_id=tenant_id, emp_student_id=emp.id, material_type="AGREEMENT",
                       file_name="就业协议书.pdf", submit_time=now - timedelta(days=10), status="APPROVED",
                       reviewer="王就业"))
    # 我的待办 + 消息
    db.add(UnifiedTodo(tenant_id=tenant_id, source_module="internship", source_biz_id=1,
                       todo_type="SUBMIT", assignee_id=1, student_id=prof.id,
                       title="提交本周实习周报", status="PENDING"))
    db.add(UnifiedMessage(tenant_id=tenant_id, receiver_id=1, title="毕设中期检查通过通知",
                          content="你的毕设中期检查已通过，请继续推进。", message_type="ANNOUNCEMENT",
                          status="UNREAD"))
    db.commit()
    return {"demoStudent": DEMO_NAME, "studentNo": DEMO_NO, "domains": 6}
