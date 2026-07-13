"""体验沙箱租户（sandbox-school）种子与重置 —— 脚本与每晚 0 点定时任务共用同一实现。
────────────────────────────────────────────────────────────
安全边界（写死，不接受参数覆盖）：
- 只操作 tenant_id == SANDBOX_TID（1000000000000000007）的行；
- 保留 t_tenant / t_tenant_brand_config 行（租户身份不删）；
- 绝不无租户条件删除、绝不 truncate、绝不触碰 demo-school 与正式租户。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select

logger = logging.getLogger("app.sandbox")

SANDBOX_TID = 1000000000000000007
SANDBOX_CODE = "sandbox-school"
SANDBOX_NAME = "体验沙箱学校"
DEMO_TID = 1000000000000000003  # 保护对象：任何情况下不得删除

SBX_STUDENT_NAME = "李体验"
SBX_STUDENT_NO = "2026S0001"
SBX_TEACHER_NAME = "王老师"
SBX_CLASS = "体验2601班"

# 重置时保留的表（租户身份/品牌）；其余含 tenant_id 的表按租户条件清空
_KEEP_TABLES = {"t_tenant", "t_tenant_brand_config"}


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


def wipe_sandbox(db) -> dict[str, int]:
    """按租户条件清空沙箱业务数据（不含 t_tenant / 品牌行）。返回各表删除行数。"""
    assert SANDBOX_TID != DEMO_TID, "安全断言：沙箱租户 ID 不得等于演示租户"
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
                            SchoolClass, StudentContact, StudentProfile, TeacherStudentScope,
                            Tenant, TenantBrandConfig, UnifiedMessage, UnifiedTodo, User,
                            WeeklyReport, WorkflowInstance, WorkflowTask)
    out = {}
    if db.get(Tenant, SANDBOX_TID) is None:
        db.add(Tenant(id=SANDBOX_TID, tenant_code=SANDBOX_CODE, school_name=SANDBOX_NAME,
                      short_name="体验沙箱", status="ACTIVE"))
    if not db.scalars(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == SANDBOX_TID)).first():
        db.add(TenantBrandConfig(tenant_id=SANDBOX_TID, platform_name="高校学生全生命周期管理平台",
                                 browser_title="高校学生全生命周期管理平台",
                                 primary_color="#2563EB", default_theme="academy_blue",
                                 watermark_text="体验沙箱 · 每晚 0 点自动重置"))

    def _add_user(login, name, utype):
        if not db.scalars(select(User).where(User.tenant_id == SANDBOX_TID,
                          User.login_name == login, User.is_deleted.is_(False))).first():
            db.add(User(tenant_id=SANDBOX_TID, login_name=login, real_name=name,
                        password_hash=hash_password("123456"), user_type=utype, status="ACTIVE"))

    _add_user("admin2", "胡管理", "ADMIN")
    _add_user("teacher2", SBX_TEACHER_NAME, "TEACHER")
    _add_user("student2", SBX_STUDENT_NAME, "STUDENT")
    out["accounts"] = "admin2/teacher2/student2"

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

    if not db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == SANDBOX_TID,
                      StudentProfile.real_name == SBX_STUDENT_NAME)).first():
        now = datetime.now()
        p = None
        for i in range(1, 7):
            nm = SBX_STUDENT_NAME if i == 1 else f"体验学生{i}"
            sp = StudentProfile(tenant_id=SANDBOX_TID, student_no=f"2026S{i:04d}", real_name=nm,
                                gender="男" if i % 2 else "女", grade="2026",
                                college_id=_college_id, major_id=k.major_id, class_id=k.id,
                                current_stage="INTERNSHIP" if i == 1 else "ON_CAMPUS",
                                student_status="NORMAL", status="ACTIVE")
            db.add(sp); db.flush()
            db.add(StudentContact(tenant_id=SANDBOX_TID, student_id=sp.id, contact_type="PHONE",
                                  contact_value_encrypted=f"137000077{i:02d}", is_primary=True,
                                  verified_status="VERIFIED"))
            if i == 1:
                p = sp
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
                              content="本环境数据每晚 0 点自动重置，请放心随便点。",
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
        out["students"] = 6
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
    db.commit()
    return out


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
