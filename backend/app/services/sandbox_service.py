"""体验沙箱租户（sandbox-school）种子与重置 —— 运营平台手动恢复与可选定时任务共用。
────────────────────────────────────────────────────────────
安全边界（写死，不接受参数覆盖）：
- 只操作 tenant_id == SANDBOX_TID（1000000000000000007）的行；
- 保留 t_tenant / t_tenant_brand_config 行（租户身份不删）；
- 绝不无租户条件删除、绝不 truncate、绝不触碰 demo-school 与正式租户；
- 清空/重灌前强制校验目标租户 tenant_code == sandbox-school，杜绝误伤 trial/expired/disabled 等平台租户槽位。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.student_lifecycle import ENROLLED, INTERN

logger = logging.getLogger("app.sandbox")

SANDBOX_TID = 1000000000000000007
SANDBOX_CODE = "sandbox-school"
SANDBOX_NAME = "体验沙箱学校"
DEMO_TID = 1000000000000000003  # 保护对象：任何情况下不得删除
# 平台种子已占用的租户槽位（_seed_platform.py）：主/演示/trial/expired/disabled。
# 沙箱 ID 绝不能落在这些值上，否则一次「恢复沙箱」会清空/改写真实平台租户。
_RESERVED_TENANT_IDS = frozenset({
    1000000000000000000, 1000000000000000001, 1000000000000000002,
    1000000000000000003, 1000000000000000004, 1000000000000000005,
    1000000000000000006,
})
assert SANDBOX_TID not in _RESERVED_TENANT_IDS, "沙箱租户 ID 撞上平台已分配租户槽位"

SBX_STUDENT_NAME = "李体验"
SBX_STUDENT_NO = "2026S0001"
SBX_TEACHER_NAME = "王老师"
SBX_CLASS = "体验2601班"
DEMO_SURNAMES = ("王", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴", "徐",
                 "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗", "梁")
DEMO_GIVEN_NAMES = ("子涵", "浩然", "雨桐", "宇轩", "欣怡")

# 重置时保留的表（租户身份/品牌）；其余含 tenant_id 的表按租户条件清空
_KEEP_TABLES = {
    "t_tenant", "t_tenant_brand_config",
    "t_user", "t_role", "t_user_role", "t_role_permission",
}


def _tenant_tables(db=None):
    """全部带 tenant_id 列且真实存在于库中的业务表（倒序删除，规避潜在外键顺序）。
    代码里新增但尚未建表的模型（如迁移未跑）自动跳过，不让重置流程 500。"""
    from app.models import Base
    existing = None
    if db is not None:
        try:
            from sqlalchemy import inspect
            existing = set(inspect(db.get_bind()).get_table_names())
        except Exception:  # noqa: BLE001
            existing = None
    out = []
    for tbl in reversed(Base.metadata.sorted_tables):
        if tbl.name in _KEEP_TABLES:
            continue
        if existing is not None and tbl.name not in existing:
            continue
        if "tenant_id" in tbl.c:
            out.append(tbl)
    return out


def sandbox_row_counts(db) -> dict[str, int]:
    """沙箱租户当前各表行数（dry-run 报告 / 删除前留痕）。"""
    counts = {}
    for tbl in _tenant_tables(db):
        n = db.execute(select(func.count()).select_from(tbl)
                       .where(tbl.c.tenant_id == SANDBOX_TID)).scalar() or 0
        if n:
            counts[tbl.name] = int(n)
    return counts


def _revoke_sandbox_logins(db) -> int:
    """吊销沙箱用户的 refreshToken（按 db-<user_id> 前缀），旧会话重置后即失效。"""
    from app.models import AuthRefreshToken, User
    uids = [f"db-{u.id}" for u in db.scalars(select(User).where(
        User.tenant_id == SANDBOX_TID)).all()]
    if not uids:
        return 0
    res = db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.user_id.in_(uids)))
    return int(res.rowcount or 0)


def _assert_target_is_sandbox(db) -> None:
    """清空/重灌前置守卫：目标租户若已存在，其 tenant_code 必须是 sandbox-school。
    杜绝沙箱 ID 万一撞上 trial/expired/disabled 等平台租户时静默清空真实数据。"""
    from app.models import Tenant
    from app.core.exceptions import AppException
    assert SANDBOX_TID != DEMO_TID, "安全断言：沙箱租户 ID 不得等于演示租户"
    tenant = db.get(Tenant, SANDBOX_TID)
    if tenant is not None and (tenant.tenant_code or "") != SANDBOX_CODE:
        raise AppException("DATA_CONFLICT",
                           f"拒绝操作：租户 {SANDBOX_TID} 的 code 是 {tenant.tenant_code!r}，"
                           f"不是 {SANDBOX_CODE}，可能是平台真实租户，已阻断清空/重灌。")


def wipe_sandbox(db) -> dict[str, int]:
    """按租户条件清空沙箱业务数据（不含 t_tenant / 品牌行）。返回各表删除行数。"""
    _assert_target_is_sandbox(db)
    removed: dict[str, int] = {}
    removed["_auth_refresh_revoked"] = _revoke_sandbox_logins(db)
    for tbl in _tenant_tables(db):
        res = db.execute(delete(tbl).where(tbl.c.tenant_id == SANDBOX_TID))
        if res.rowcount:
            removed[tbl.name] = int(res.rowcount)
    db.commit()
    return removed


def seed_sandbox(db) -> dict:
    """沙箱租户全量种子（幂等；重置后重建基础组织/账号/教师范围/六域最小数据）。"""
    from app.core.security import hash_password
    from app.models import (AcademicGrade, AcademicStudent, AcademicWarning, College, CsLeave,
                            CsServiceStudent, EmpJob, EmpStudent, GraduationProposal,
                            GraduationStudent, InternshipRecord, Major, OrientationStudent,
                            Role, SchoolClass, StudentContact, StudentProfile, TeacherStudentScope,
                            Tenant, TenantBrandConfig, UnifiedMessage, UnifiedTodo, User,
                            UserRole, WeeklyReport, WorkflowInstance, WorkflowTask)
    _assert_target_is_sandbox(db)
    out = {}
    tenant = db.get(Tenant, SANDBOX_TID)
    if tenant is None:
        tenant = Tenant(id=SANDBOX_TID, tenant_code=SANDBOX_CODE, school_name=SANDBOX_NAME,
                        short_name="体验沙箱", status="ACTIVE")
        db.add(tenant)
    else:
        tenant.tenant_code = SANDBOX_CODE
        tenant.school_name = SANDBOX_NAME
        tenant.short_name = "体验沙箱"
        tenant.status = "ACTIVE"
        tenant.is_deleted = False
    if not db.scalars(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == SANDBOX_TID)).first():
        db.add(TenantBrandConfig(tenant_id=SANDBOX_TID, platform_name="高校学生全生命周期管理平台",
                                 browser_title="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", default_theme="academy_blue",
                                 watermark_text="真实演示沙箱 · 可在运营平台手动恢复"))

    def _add_user(login, name, utype):
        row = db.scalars(select(User).where(
            User.tenant_id == SANDBOX_TID, User.login_name == login)).first()
        if row is None:
            row = User(tenant_id=SANDBOX_TID, login_name=login, real_name=name,
                       password_hash=hash_password("123456"), user_type=utype, status="ACTIVE")
            db.add(row)
        else:
            # “恢复演示数据”同时恢复固定演示账号，避免历史停用/改密后无法继续现场演示。
            row.real_name = name
            row.user_type = utype
            row.status = "ACTIVE"
            row.is_deleted = False
            row.must_change_password = False
            row.password_hash = hash_password("123456")

    _add_user("admin2", "胡管理", "ADMIN")
    _add_user("teacher2", SBX_TEACHER_NAME, "TEACHER")
    _add_user("student2", SBX_STUDENT_NAME, "STUDENT")
    db.flush()
    # 页面里的责任人/指导教师选择器必须来自真实在职账号与真实角色关系。
    role_specs = (("SCHOOL_ADMIN", "学校管理员", "admin2"),)
    for role_code, role_name, login_name in role_specs:
        role = db.scalars(select(Role).where(
            Role.tenant_id == SANDBOX_TID, Role.role_code == role_code,
            Role.is_deleted.is_(False))).first()
        if role is None:
            role = Role(tenant_id=SANDBOX_TID, role_code=role_code, role_name=role_name,
                        role_type="SYSTEM", status="ACTIVE")
            db.add(role)
            db.flush()
        user_row = db.scalars(select(User).where(
            User.tenant_id == SANDBOX_TID, User.login_name == login_name,
            User.is_deleted.is_(False))).first()
        if user_row and not db.scalars(select(UserRole).where(
                UserRole.tenant_id == SANDBOX_TID, UserRole.user_id == user_row.id,
                UserRole.role_id == role.id, UserRole.is_deleted.is_(False))).first():
            db.add(UserRole(tenant_id=SANDBOX_TID, user_id=user_row.id,
                            role_id=role.id, status="ACTIVE"))
    out["accounts"] = "admin2/teacher2/student2"

    # ORG_WRITE_BYPASS_ALLOWLIST: sandbox_service — 演示沙箱种子，非学校正式管理写入口
    k = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == SANDBOX_TID)).first()
    if k is None:
        c = College(tenant_id=SANDBOX_TID, code="S01", college_name="体验学院", status="ACTIVE")
        db.add(c); db.flush()
        m = Major(tenant_id=SANDBOX_TID, college_id=c.id, code="SM01",
                  major_name="电子商务", status="ACTIVE")
        db.add(m); db.flush()
        k = SchoolClass(tenant_id=SANDBOX_TID, major_id=m.id,
                        class_name=SBX_CLASS, grade="2026", status="ACTIVE")
        db.add(k); db.flush()
        _college_id = c.id
        out["org"] = "1学院/1专业/1班级"
    else:
        m = db.get(Major, k.major_id)
        _college_id = m.college_id if m else None

    if (db.scalar(select(func.count()).select_from(College).where(
            College.tenant_id == SANDBOX_TID)) or 0) < 4:
        for college_code, college_name, major_names in (
            ("S02", "智能制造学院", ("机电一体化技术", "工业机器人技术")),
            ("S03", "信息工程学院", ("软件技术", "大数据技术")),
            ("S04", "健康服务学院", ("护理", "康复治疗技术")),
        ):
            college = College(tenant_id=SANDBOX_TID, code=college_code,
                              college_name=college_name, status="ACTIVE")
            db.add(college); db.flush()
            for major_index, major_name in enumerate(major_names, 1):
                major = Major(tenant_id=SANDBOX_TID, college_id=college.id,
                              code=f"{college_code}M{major_index:02d}",
                              major_name=major_name, status="ACTIVE")
                db.add(major); db.flush()
                for grade in ("2025", "2026"):
                    db.add(SchoolClass(tenant_id=SANDBOX_TID, major_id=major.id,
                                       class_name=f"{grade[-2:]}{major_name[:2]}{major_index}班",
                                       grade=grade, status="ACTIVE"))
        db.flush()
        out["org"] = "4学院/7专业/13班级/2年级"

    if not db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == SANDBOX_TID,
                      StudentProfile.real_name == SBX_STUDENT_NAME)).first():
        now = datetime.now()
        p = None
        for i in range(1, 101):
            nm = SBX_STUDENT_NAME if i == 1 else (
                DEMO_SURNAMES[(i - 2) % len(DEMO_SURNAMES)]
                + DEMO_GIVEN_NAMES[(i - 2) // len(DEMO_SURNAMES)]
            )
            sp = StudentProfile(tenant_id=SANDBOX_TID, student_no=f"2026S{i:04d}", real_name=nm,
                                gender="男" if i % 2 else "女", grade="2026",
                                college_id=_college_id, major_id=k.major_id, class_id=k.id,
                                current_stage=INTERN if i == 1 else ENROLLED,
                                student_status="NORMAL", status="ACTIVE")
            db.add(sp); db.flush()
            db.add(StudentContact(tenant_id=SANDBOX_TID, student_id=sp.id, contact_type="PHONE",
                                  contact_value_encrypted=f"137000077{i:02d}", is_primary=True,
                                  verified_status="VERIFIED"))
            if i == 1:
                p = sp
        db.flush()
        classes = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == SANDBOX_TID).order_by(SchoolClass.id)).all()
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == SANDBOX_TID).order_by(StudentProfile.id)).all()
        for index, student in enumerate(students):
            school_class = classes[index % len(classes)]
            major = db.get(Major, school_class.major_id)
            student.class_id = school_class.id
            student.major_id = school_class.major_id
            student.college_id = major.college_id if major else None
            student.grade = school_class.grade
        db.flush()
        # 主流程先使用各领域显式种子，确保列表、详情和关联关系真实可用。
        from scripts._seed_academic import seed_academic
        from scripts._seed_campus_service import seed_campus_service
        from scripts._seed_employment import seed_employment
        from scripts._seed_graduation import seed_graduation
        from scripts._seed_internship import seed_internship
        from scripts._seed_orientation import seed_orientation
        out["orientationFull"] = seed_orientation(db, SANDBOX_TID)
        out["campusServiceFull"] = seed_campus_service(db, SANDBOX_TID)
        out["academicFull"] = seed_academic(db, SANDBOX_TID)
        out["internshipFull"] = seed_internship(db, SANDBOX_TID)
        out["employmentFull"] = seed_employment(db, SANDBOX_TID)
        out["graduationFull"] = seed_graduation(db, SANDBOX_TID)
        db.add(OrientationStudent(tenant_id=SANDBOX_TID, name=SBX_STUDENT_NAME,
                                  admission_no=f"LQ{SBX_STUDENT_NO}", student_id=p.id,
                                  class_name=SBX_CLASS, grade="2026级", stage="ENROLLED",
                                  report_status="CHECKED_IN", payment_status="PAID",
                                  material_status="APPROVED", dorm_status="CHECKED_IN",
                                  building="沙箱1号楼", room="1-101-1", risk_level="LOW",
                                  steps_json={"ACTIVATE": "DONE", "CHECKIN": "DONE"}))
        cs = CsServiceStudent(tenant_id=SANDBOX_TID, name=SBX_STUDENT_NAME, student_no=SBX_STUDENT_NO,
                              student_id=p.id, class_name=SBX_CLASS, care_level="NORMAL",
                              risk_level="LOW", counselor=SBX_TEACHER_NAME, record_status="ACTIVE")
        db.add(cs); db.flush()
        db.add(CsLeave(tenant_id=SANDBOX_TID, code="SLV-2026-0001", cs_student_id=cs.id,
                       leave_type="PERSONAL", start_time=now + timedelta(days=1), duration="1 天",
                       reason="体验请假流程示例", status="PENDING_REVIEW",
                       student_id=p.id, affairs_status="COUNSELOR_REVIEW", days=1,
                       end_time=now + timedelta(days=2), expected_return_at=now + timedelta(days=2),
                       apply_time=now - timedelta(hours=1)))
        acad = AcademicStudent(tenant_id=SANDBOX_TID, name=SBX_STUDENT_NAME, student_no=SBX_STUDENT_NO,
                               class_name=SBX_CLASS, gpa=3.0, avg_score=80, obtained_credits=60,
                               required_credits=120, academic_status="WARNING",
                               warning_level="LOW", record_status="ACTIVE")
        db.add(acad); db.flush()
        db.add(AcademicGrade(tenant_id=SANDBOX_TID, acad_student_id=acad.id, course_name="电商运营",
                             term="2025-2026-2", nature="REQUIRED", credit_value=4, score=82,
                             pass_status="PASSED", exam_type="FINAL"))
        db.add(AcademicWarning(tenant_id=SANDBOX_TID, code="SAW-2026-0001", acad_student_id=acad.id,
                               warn_type="GPA", level="LOW", reason="体验预警处理流程",
                               status="PENDING_HANDLE", owner=SBX_TEACHER_NAME,
                               record_status="ACTIVE", trigger_time=now - timedelta(days=1)))
        rec = InternshipRecord(tenant_id=SANDBOX_TID, student_id=p.id,
                               enterprise_name="沙箱电商有限公司", position_name="运营实习生",
                               advisor_name=SBX_TEACHER_NAME, status="ONBOARD", risk_level="LOW",
                               intern_start_date=datetime(2026, 3, 2),
                               intern_end_date=datetime(2026, 8, 28))
        db.add(rec); db.flush()
        db.add(WeeklyReport(tenant_id=SANDBOX_TID, internship_id=rec.id, week_number=1,
                            work_content="体验周报：熟悉店铺后台与商品上架流程。",
                            status="PENDING_REVIEW", word_count=20, report_version=1,
                            submitted_at=now - timedelta(days=1)))
        gd = GraduationStudent(tenant_id=SANDBOX_TID, name=SBX_STUDENT_NAME, student_no=SBX_STUDENT_NO,
                               class_name=SBX_CLASS, topic_title="社区团购运营方案设计",
                               topic_source="学生自拟", advisor_name=SBX_TEACHER_NAME,
                               stage="PROPOSAL", risk_level="LOW", record_status="ACTIVE")
        db.add(gd); db.flush()
        db.add(GraduationProposal(tenant_id=SANDBOX_TID, gd_student_id=gd.id, version="v1",
                                  submit_at=now - timedelta(hours=6), status="PENDING_REVIEW",
                                  background="体验开题批阅", plan="调研+方案", outcome="方案与论文"))
        db.add(EmpStudent(tenant_id=SANDBOX_TID, name=SBX_STUDENT_NAME, student_no=SBX_STUDENT_NO,
                          grade="2026届", class_name=SBX_CLASS, destination_type="UNEMPLOYED",
                          verify_status="PENDING_HANDLE", material_status="NOT_SUBMITTED",
                          help_level="NORMAL", risk_level="LOW", counselor=SBX_TEACHER_NAME,
                          record_status="ACTIVE"))
        db.add(EmpJob(tenant_id=SANDBOX_TID, company_id=1, company_name="沙箱电商有限公司",
                      title="电商运营专员", category="运营", salary_range="5k-7k", headcount=2,
                      status="OPEN", publish_time=f"{now:%Y-%m-%d}"))
        db.add(UnifiedTodo(tenant_id=SANDBOX_TID, source_module="internship", source_biz_id=rec.id,
                           todo_type="SUBMIT", assignee_id=p.id, student_id=p.id,
                           title="提交本周实习周报", status="PENDING"))
        db.add(UnifiedMessage(tenant_id=SANDBOX_TID, receiver_id=p.id, title="欢迎体验沙箱学校",
                              content="本环境为真实数据库演示沙箱，运营人员可随时恢复预制演示数据。",
                              message_type="SYSTEM", status="UNREAD"))
        inst = WorkflowInstance(tenant_id=SANDBOX_TID, workflow_code="wf_student",
                                source_module="student", source_biz_type="PROFILE_CORRECTION",
                                source_biz_id=p.id, applicant_id=p.id,
                                title=f"{SBX_STUDENT_NAME} · 联系方式变更", status="RUNNING",
                                remark=SBX_STUDENT_NAME)
        db.add(inst); db.flush()
        db.add(WorkflowTask(tenant_id=SANDBOX_TID, instance_id=inst.id, node_code="COUNSELOR_REVIEW",
                            assignee_id=1, status="PENDING",
                            deadline_at=datetime.utcnow() + timedelta(days=2)))
        out["students"] = 100
        out["domains"] = "六域最小数据"

    # ── 13A 学工中心域最小演示数据（困难认定/奖助/违纪，幂等；反映 P3/P4 已闭环工作流）──
    sbx_stu = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == SANDBOX_TID,
        StudentProfile.real_name == SBX_STUDENT_NAME)).first()
    if sbx_stu is not None:
        aff_out = _seed_sandbox_affairs_13a(db, sbx_stu)
        if aff_out:
            out.update(aff_out)

    if not db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == SANDBOX_TID,
            TeacherStudentScope.teacher_key == "teacher2")).first():
        db.add(TeacherStudentScope(tenant_id=SANDBOX_TID, teacher_key="teacher2",
                                   teacher_name=SBX_TEACHER_NAME, role_code=None,
                                   scope_type="CLASS", ref_value=SBX_CLASS, status="ACTIVE"))
        db.add(TeacherStudentScope(tenant_id=SANDBOX_TID, teacher_key="teacher2",
                                   teacher_name=SBX_TEACHER_NAME, role_code=None,
                                   scope_type="ADVISOR", ref_value=SBX_TEACHER_NAME, status="ACTIVE"))
    # 所有主流程完成后，再补齐余下页面表与模型声明的流程状态。
    from scripts._seed_sandbox_coverage import seed_sandbox_flow_coverage
    out["flowCoverage"] = seed_sandbox_flow_coverage(db, SANDBOX_TID)
    # 该状态是实习返岗闭环的展示前置；用真实实习记录兜底，避免通用状态行缺少关联。
    from app.models import InternshipLeave
    if not db.scalars(select(InternshipLeave).where(
            InternshipLeave.tenant_id == SANDBOX_TID,
            InternshipLeave.status == "APPROVED")).first():
        linked_record = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == SANDBOX_TID).order_by(InternshipRecord.id)).first()
        if linked_record is not None:
            linked_student = db.get(StudentProfile, linked_record.student_id)
            db.add(InternshipLeave(
                tenant_id=SANDBOX_TID, internship_id=linked_record.id,
                student_id=linked_record.student_id, leave_type="SICK",
                start_date=(now + timedelta(days=20)).strftime("%Y-%m-%d"),
                end_date=(now + timedelta(days=21)).strftime("%Y-%m-%d"), days=2,
                reason="发热就医，门诊证明已核验", status="APPROVED",
                apply_by_name=linked_student.real_name if linked_student else "演示学生",
                review_by_name="王老师", review_at=now - timedelta(days=1),
                review_comment="证明有效，同意请假",
            ))
            db.flush()
    out["baseline"] = _register_sandbox_baseline(db)
    db.commit()
    return out


def _register_sandbox_baseline(db) -> dict:
    """把本次预制的全部沙箱业务行登记为不可删除基线；后续现场新增行不会被登记。"""
    from app.models import SandboxBaseline

    existing = {(x.table_name, int(x.row_id)) for x in db.scalars(select(SandboxBaseline).where(
        SandboxBaseline.tenant_id == SANDBOX_TID)).all()}
    added = 0
    tables = 0
    for table in _tenant_tables(db):
        if table.name == SandboxBaseline.__tablename__ or "id" not in table.c:
            continue
        row_ids = [int(x) for x in db.scalars(select(table.c.id).where(
            table.c.tenant_id == SANDBOX_TID)).all()]
        if row_ids:
            tables += 1
        for row_id in row_ids:
            key = (table.name, row_id)
            if key in existing:
                continue
            db.add(SandboxBaseline(tenant_id=SANDBOX_TID, table_name=table.name,
                                   row_id=row_id, label="系统预制演示数据"))
            existing.add(key)
            added += 1
    db.flush()
    return {"protectedRows": len(existing), "added": added, "tables": tables}


def _seed_sandbox_affairs_13a(db, stu) -> dict:
    """沙箱 13A 学工域最小演示数据（困难认定/奖助/违纪，幂等）。
    stu = 李体验（SBX_STUDENT_NAME）StudentProfile；各域各留一条中间态单据，便于体验审批流。
    与 seed_sandbox 一致：仅在对应表尚无沙箱行时创建，二次种子不新增。"""
    from app.models import (AidApply, AidBatch, AidFamilyEconomy, DisciplineCase,
                            FundingApplication, FundingBatch, FundingProject)
    now = datetime.now()
    out: dict = {}
    # 困难认定：批次(OPEN) + 申请(班级评议中) + 家庭经济(强敏感隔离表)
    if not db.scalars(select(AidBatch).where(AidBatch.tenant_id == SANDBOX_TID)).first():
        batch = AidBatch(tenant_id=SANDBOX_TID, batch_name="2026 春季家庭经济困难认定",
                         year_code="2025-2026", status="OPEN", publicity_days=5,
                         apply_start=now - timedelta(days=3), apply_end=now + timedelta(days=7))
        db.add(batch); db.flush()
        ap = AidApply(tenant_id=SANDBOX_TID, batch_id=batch.id, student_id=stu.id,
                      apply_level="DIFFICULT", suggest_level="DIFFICULT", status="CLASS_REVIEW",
                      statement="家庭务农，父亲长期患病，家庭收入来源单一，恳请认定家庭经济困难。")
        db.add(ap); db.flush()
        db.add(AidFamilyEconomy(tenant_id=SANDBOX_TID, apply_id=ap.id, student_id=stu.id,
                                member_count=4, income_encrypted="18000",
                                special_flags_json='["单亲","低保"]'))
        out["aid"] = "1批次+1申请(班级评议)"
    # 困难学生库只读取 APPROVED；保留一条办理中，再单独留一条已认定结果。
    if not db.scalars(select(AidApply).where(
            AidApply.tenant_id == SANDBOX_TID, AidApply.status == "APPROVED")).first():
        approved_batch = AidBatch(
            tenant_id=SANDBOX_TID, batch_name="2025 秋季家庭经济困难认定（已结束）",
            year_code="2025-2026", status="CLOSED", publicity_days=5,
            apply_start=now - timedelta(days=90), apply_end=now - timedelta(days=70),
        )
        db.add(approved_batch)
        db.flush()
        db.add(AidApply(
            tenant_id=SANDBOX_TID, batch_id=approved_batch.id, student_id=stu.id,
            apply_level="DIFFICULT", suggest_level="DIFFICULT", final_level="DIFFICULT",
            status="APPROVED", statement="家庭收入来源单一，已完成班级、学院及学校认定。",
            class_review_score=92, class_review_rank=2, result_at=now - timedelta(days=60),
        ))
        out["difficultLibrary"] = "1名已认定困难学生"
    # 奖助：项目(助学金) + 学年批次(OPEN) + 申请(辅导员初审中)
    if not db.scalars(select(FundingProject).where(FundingProject.tenant_id == SANDBOX_TID)).first():
        proj = FundingProject(tenant_id=SANDBOX_TID, project_name="国家助学金", project_type="GRANT",
                              amount=3300, quota=5, status="ENABLED")
        db.add(proj); db.flush()
        fb = FundingBatch(tenant_id=SANDBOX_TID, project_id=proj.id, project_type="GRANT",
                          year_code="2025-2026", status="OPEN", quota=5, publicity_days=5,
                          apply_start=now - timedelta(days=2), apply_end=now + timedelta(days=8))
        db.add(fb); db.flush()
        db.add(FundingApplication(tenant_id=SANDBOX_TID, batch_id=fb.id, student_id=stu.id,
                                  apply_source="SELF", project_type="GRANT", amount=3300,
                                  status="COUNSELOR_REVIEW", statement="家庭经济困难，申请国家助学金资助。"))
        out["funding"] = "1项目+1批次+1申请(辅导员初审)"
    # 违纪处分：一条已登记的警告（演示登记态，未生效不投影 t_cs_discipline）
    if not db.scalars(select(DisciplineCase).where(DisciplineCase.tenant_id == SANDBOX_TID)).first():
        db.add(DisciplineCase(tenant_id=SANDBOX_TID, student_id=stu.id, disc_type="WARNING",
                              reason="晚归违反宿舍管理规定一次（演示数据）。", status="REGISTERED"))
        out["discipline"] = "1登记警告"
    db.flush()
    return out


def reset_sandbox(db, dry_run: bool = True) -> dict:
    """重置沙箱：dry_run=True 只统计不落库；False 时删除并重建。返回报告。"""
    counts = sandbox_row_counts(db)
    report = {"tenant": SANDBOX_CODE, "tenantId": str(SANDBOX_TID),
              "dryRun": dry_run, "wouldRemove": counts}
    if dry_run:
        db.rollback()  # 保证 dry-run 绝不落库
        return report
    report["removed"] = wipe_sandbox(db)
    report["reseeded"] = seed_sandbox(db)
    try:
        from app.services import audit_log
        audit_log.record("SANDBOX_RESET", SANDBOX_CODE,
                         detail={"removed": report["removed"]})
    except Exception:  # noqa: BLE001
        pass
    logger.info("sandbox reset done: %s", report.get("removed"))
    return report


def seconds_until_next_midnight() -> float:
    now = datetime.now()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (nxt - now).total_seconds())
