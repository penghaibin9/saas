"""双真实租户演示体系种子（幂等 · 分块判断 · 只新增，不删改其他租户任何数据）。
────────────────────────────────────────────────────────────
- demo-school   (1000000000000000003) 正式演示租户：账号 admin / teacher / student（123456）
  组织 2 学院 / 3 专业 / 3 班级；学生 ≥20；六大业务域三态样例；教师范围=看得见即能处理。
  该租户在中间件层强制只读（写操作 403），数据不会被参观者改动。
- sandbox-school(1000000000000000004) 自由体验租户：账号 admin2 / teacher2 / student2（123456）
  沙箱种子/重置的唯一实现在 app/services/sandbox_service.py（每晚 0 点定时重置共用）。
密码只以 pbkdf2 hash 落库（复用全局 hash_password），绝无明文；弱密码账号仅存在于这两个租户。
所有账号走真实 /api/v1/auth/login，与 mock-login 无关。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import (AcademicGrade, AcademicStudent, AcademicWarning, AttendanceException,
                        College, CsLeave, CsServiceStudent, CsWorkOrder, EmpFollowup, EmpJob,
                        EmpMaterial, EmpStudent, GraduationFinal, GraduationProposal,
                        GraduationStudent, InternshipCheckin, InternshipRecord, Major,
                        OrientationStudent, SchoolClass, StudentContact, StudentProfile,
                        TeacherStudentScope, Tenant, TenantBrandConfig, UnifiedMessage,
                        UnifiedTodo, User, WeeklyReport, WorkflowInstance, WorkflowTask)

DEMO_TID = 1000000000000000003
DEMO_CODE = "demo-school"
DEMO_NAME = "演示职业技术学校"
SANDBOX_TID = 1000000000000000004
SANDBOX_CODE = "sandbox-school"
SANDBOX_NAME = "体验沙箱学校"

DEMO_STUDENT_NAME = "张同学"      # student 账号绑定的学生档案（沿用既有富数据档案）
DEMO_STUDENT_NO = "2026D0006"
DEMO_TEACHER_NAME = "李导师"      # teacher 账号真实姓名（与既有实习/毕设 advisor_name 一致）
DEMO_CLASSES = ["数媒2601班", "软件2601班", "电商2601班"]

SBX_STUDENT_NAME = "李体验"
SBX_STUDENT_NO = "2026S0001"
SBX_TEACHER_NAME = "王老师"
SBX_CLASS = "体验2601班"


def _user_exists(db, tid: int, login: str) -> bool:
    return db.scalars(select(User).where(User.tenant_id == tid, User.login_name == login,
                                         User.is_deleted.is_(False))).first() is not None


def _add_user(db, tid: int, login: str, name: str, utype: str, pwd: str = "123456"):
    if not _user_exists(db, tid, login):
        db.add(User(tenant_id=tid, login_name=login, real_name=name,
                    password_hash=hash_password(pwd), user_type=utype, status="ACTIVE"))


def _count(db, model, tid: int) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tid)) or 0


# ═══════════════ demo-school 正式演示租户 ═══════════════

def seed_demo_tenant(db) -> dict:
    out = {}
    # 租户存在 + 名称对齐（唯一的 upsert：只改演示租户展示名）
    t = db.get(Tenant, DEMO_TID)
    if t is None:
        db.add(Tenant(id=DEMO_TID, tenant_code=DEMO_CODE, school_name=DEMO_NAME,
                      short_name="演示职校", status="ACTIVE"))
        db.add(TenantBrandConfig(tenant_id=DEMO_TID, platform_name="高校学生全生命周期管理平台",
                                 browser_title="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", default_theme="academy_blue",
                                 watermark_text="演示职校内部系统"))
    elif (t.school_name or "") != DEMO_NAME:
        t.school_name = DEMO_NAME

    # 账号（弱密码仅演示租户；hash 落库）
    _add_user(db, DEMO_TID, "admin", "陈管理", "ADMIN")
    _add_user(db, DEMO_TID, "teacher", DEMO_TEACHER_NAME, "TEACHER")
    _add_user(db, DEMO_TID, "student", DEMO_STUDENT_NAME, "STUDENT")
    out["accounts"] = "admin/teacher/student"

    # 组织：2 学院 / 3 专业 / 3 班级
    if _count(db, College, DEMO_TID) == 0:
        c1 = College(tenant_id=DEMO_TID, code="D01", college_name="信息工程学院", status="ACTIVE")
        c2 = College(tenant_id=DEMO_TID, code="D02", college_name="现代服务学院", status="ACTIVE")
        db.add_all([c1, c2]); db.flush()
        m1 = Major(tenant_id=DEMO_TID, college_id=c1.id, code="DM01", major_name="数字媒体技术", status="ACTIVE")
        m2 = Major(tenant_id=DEMO_TID, college_id=c1.id, code="DM02", major_name="软件技术", status="ACTIVE")
        m3 = Major(tenant_id=DEMO_TID, college_id=c2.id, code="DM03", major_name="电子商务", status="ACTIVE")
        db.add_all([m1, m2, m3]); db.flush()
        for m, cname in ((m1, DEMO_CLASSES[0]), (m2, DEMO_CLASSES[1]), (m3, DEMO_CLASSES[2])):
            db.add(SchoolClass(tenant_id=DEMO_TID, major_id=m.id,
                               class_name=cname, grade="2026", status="ACTIVE"))
        out["org"] = "2学院/3专业/3班级"
    db.flush()
    classes = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == DEMO_TID)).all()
    majors = {m.id: m for m in db.scalars(select(Major).where(Major.tenant_id == DEMO_TID)).all()}

    def _org_of(k):
        m = majors.get(k.major_id)
        return (m.college_id if m else None), k.major_id, k.id

    # 学生补齐到 ≥20（跳过已占用学号，班级轮换 + 挂组织）
    existing_nos = {s.student_no for s in db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == DEMO_TID, StudentProfile.is_deleted.is_(False))).all()}
    if len(existing_nos) < 20 and classes:
        seq = 0
        while len(existing_nos) < 20:
            seq += 1
            no = f"2026D{seq:04d}"
            if no in existing_nos:
                continue
            k = classes[seq % len(classes)]
            cid, mid, kid = _org_of(k)
            sp = StudentProfile(tenant_id=DEMO_TID, student_no=no,
                                real_name=f"演示学生{seq}", gender="男" if seq % 2 else "女",
                                grade="2026", college_id=cid, major_id=mid,
                                class_id=kid, current_stage="ON_CAMPUS",
                                student_status="NORMAL", status="ACTIVE")
            db.add(sp); db.flush()
            db.add(StudentContact(tenant_id=DEMO_TID, student_id=sp.id, contact_type="PHONE",
                                  contact_value_encrypted=f"139000066{seq:02d}", is_primary=True,
                                  verified_status="VERIFIED"))
            existing_nos.add(no)
        out["students"] = ">=20"
    # 张同学挂组织（不改姓名学号）
    zs = db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == DEMO_TID,
                    StudentProfile.real_name == DEMO_STUDENT_NAME)).first()
    if zs is not None and not zs.class_id and classes:
        zs.college_id, zs.major_id, zs.class_id = _org_of(classes[0])

    # 六域三态样例（以“异常报到样例”是否存在做幂等标记）
    now = datetime.now()
    flag = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == DEMO_TID,
        OrientationStudent.name == "演示学生7")).first()
    if flag is None:
        # 迎新：待完成 + 异常（已完成=张同学既有）
        db.add(OrientationStudent(tenant_id=DEMO_TID, name="演示学生6", admission_no="LQ2026D0007",
                                  class_name=DEMO_CLASSES[0], grade="2026级", stage="PRE_REGISTER",
                                  report_status="NOT_REPORTED", payment_status="UNPAID",
                                  material_status="NOT_SUBMITTED", dorm_status="NOT_ASSIGNED",
                                  risk_level="LOW", steps_json={"ACTIVATE": "DONE", "INFO": "PENDING"}))
        db.add(OrientationStudent(tenant_id=DEMO_TID, name="演示学生7", admission_no="LQ2026D0008",
                                  class_name=DEMO_CLASSES[1], grade="2026级", stage="PRE_REGISTER",
                                  report_status="NOT_REPORTED", payment_status="UNPAID",
                                  material_status="REJECTED", dorm_status="NOT_ASSIGNED",
                                  blocked_step="MATERIAL", blocked_reason="身份材料照片模糊需重传",
                                  risk_level="MEDIUM", steps_json={"ACTIVATE": "DONE", "MATERIAL": "REJECTED"}))
        # 在校服务：已退回样例（待审+已通过=张同学既有）
        cs8 = CsServiceStudent(tenant_id=DEMO_TID, name="演示学生8", student_no="2026D0008",
                               class_name=DEMO_CLASSES[0], care_level="NORMAL", risk_level="LOW",
                               counselor=DEMO_TEACHER_NAME, record_status="ACTIVE")
        db.add(cs8); db.flush()
        db.add(CsLeave(tenant_id=DEMO_TID, code="DLV-2026-0003", cs_student_id=cs8.id,
                       leave_type="PERSONAL", start_time=now - timedelta(days=3), duration="3 天",
                       reason="外出旅游", status="RETURNED", apply_time=now - timedelta(days=4),
                       reviewer=DEMO_TEACHER_NAME, return_reason="事由不符合请假规范，请修改后重新提交"))
        # 学业：已关闭预警样例（待处理=张同学既有）
        a9 = AcademicStudent(tenant_id=DEMO_TID, name="演示学生9", student_no="2026D0009",
                             class_name=DEMO_CLASSES[0], gpa=2.6, avg_score=72,
                             academic_status="NORMAL", warning_level="NONE", record_status="ACTIVE")
        db.add(a9); db.flush()
        db.add(AcademicWarning(tenant_id=DEMO_TID, code="DAW-2026-0002", acad_student_id=a9.id,
                               warn_type="CREDIT", level="LOW", reason="学分进度滞后",
                               status="CLOSED", close_result="已制定补修计划，按期跟进",
                               owner=DEMO_TEACHER_NAME, record_status="ACTIVE",
                               trigger_time=now - timedelta(days=30)))
        # 实习：打卡样例（张同学既有周报待批/已批 + 打卡异常）
        zrec = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == DEMO_TID)).first()
        if zrec is not None:
            db.add(InternshipCheckin(tenant_id=DEMO_TID, internship_id=zrec.id,
                                     checkin_date=f"{now - timedelta(days=1):%Y-%m-%d}",
                                     checkin_at=now - timedelta(days=1), lat=30.2, lng=120.1,
                                     address="星河数字创意园区", result="RECORDED"))
        # 毕设：中期 + 终稿待批样例（开题待批=张同学既有）
        g10 = GraduationStudent(tenant_id=DEMO_TID, name="演示学生10", student_no="2026D0010",
                                class_name=DEMO_CLASSES[0], topic_title="校园二手书交易小程序设计",
                                topic_source="学生自拟", advisor_name=DEMO_TEACHER_NAME,
                                stage="MIDTERM", midterm_conclusion="通过", material_summary="中期已过",
                                risk_level="LOW", record_status="ACTIVE")
        db.add(g10); db.flush()
        db.add(GraduationFinal(tenant_id=DEMO_TID, gd_student_id=g10.id, final_type="PAPER",
                               version="v1", submit_at=now - timedelta(days=1),
                               status="PENDING_REVIEW", plagiarism_rate="8.2%",
                               plagiarism_status="PASSED"))
        # 就业：材料核验样例 + 跟进记录（签约/未就业=既有）
        e11 = db.scalars(select(EmpStudent).where(EmpStudent.tenant_id == DEMO_TID,
                         EmpStudent.destination_type == "UNEMPLOYED")).first()
        if e11 is not None:
            db.add(EmpMaterial(tenant_id=DEMO_TID, emp_student_id=e11.id, material_type="INTENT",
                               file_name="就业意向书.pdf", submit_time=now - timedelta(days=2),
                               status="PENDING_REVIEW"))
            db.add(EmpFollowup(tenant_id=DEMO_TID, emp_student_id=e11.id, way="PHONE",
                               content="电话沟通就业意向，推荐两个校招岗位", operator=DEMO_TEACHER_NAME,
                               status="OPEN", follow_time=now - timedelta(days=1)))
        out["domains"] = "六域三态样例"

    # 教师范围：teacher 账号 = 3 个班级辅导员 + 李导师指导关系（看得见=能处理）
    if not db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == DEMO_TID,
            TeacherStudentScope.teacher_key == "teacher")).first():
        for cn in DEMO_CLASSES:
            db.add(TeacherStudentScope(tenant_id=DEMO_TID, teacher_key="teacher",
                                       teacher_name=DEMO_TEACHER_NAME, role_code=None,
                                       scope_type="CLASS", ref_value=cn, status="ACTIVE"))
        db.add(TeacherStudentScope(tenant_id=DEMO_TID, teacher_key="teacher",
                                   teacher_name=DEMO_TEACHER_NAME, role_code=None,
                                   scope_type="ADVISOR", ref_value=DEMO_TEACHER_NAME, status="ACTIVE"))
    db.commit()
    return out


# ═══════════════ sandbox-school 自由体验租户（实现见 app/services/sandbox_service.py） ═══════════════

def seed_sandbox_school(db) -> dict:
    """沙箱租户全量种子（与每晚 0 点重置共用 app 层实现）。"""
    from app.services.sandbox_service import seed_sandbox
    return seed_sandbox(db)


def seed_two_tenants(db) -> dict:
    return {"demo": seed_demo_tenant(db), "sandbox": seed_sandbox_school(db)}
