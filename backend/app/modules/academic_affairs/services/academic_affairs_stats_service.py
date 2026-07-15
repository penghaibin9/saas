"""13B 教务中心 · 教务统计（只读聚合）——11 项运行结果性指标 + 多维筛选 + 下钻明细。

设计来源（施工包 `docs/03-业务模块设计/教务中心/施工包/教务统计-生产级施工包.md` §9 / 融合设计 §4 口径已冻结）：
- 纯读侧：不新建表、不写业务表、无迁移（全部实时 count，`project_rule` D-02）。
- 数据范围：复用学工中心已验证的 `build_affairs_context`（不另造 scope 解析器，CLAUDE.md §5.3）。
  · 教务处口径角色（ACADEMIC_ADMIN / ACADEMIC_TEACHER，见 mock dataScope=SCHOOL 与 permissions.py `academicAffairs.*`）
    视为 TENANT_ALL（本校全量）——这两个角色码在 build_affairs_context 中未登记为 TENANT_ALL，
    故本域在 `_resolve_scope` 顶层按业务口径显式归类，**不修改共享 affairs_security 的角色集**（避免影响 R1 成绩审核 scope）。
  · COLLEGE_ADMIN / COLLEGE_SA → 复用 ctx.college_ids / allowed_class_ids（本院），未配 = fail-closed（空，绝不回退全校）。
  · 其它无授权角色 → NONE（fail-closed，指标全 0，传越权 collegeId → NO_DATA_SCOPE）。
- 07/08/09/14（调停课/选课/考务/教学资源统计）底层模块已在后续续工轮次建成真实表
  （`t_aa_schedule_change`/`t_aa_selection_*`/`t_aa_exam_*`/`t_aa_classroom*`），本文件不再对这
  4 项返回 MODULE_NOT_ENABLED 占位（2026-07-16 教务统计第三轮续工更正，施工包 §1/D-07 已过期）。
  调停课在教务总览的卡片为全局计数（复用本文件统一 scope 引擎，与 07 号「调停课统计」独立页面
  ——`/admin/academic-affairs/schedule-change/stats`，`academicAffairs.scheduleChange.view`——
  的"本人课位自助视角"是两种不同口径，互不冲突，不合并实现）。
- 下钻到学生级明细写审计（STATS_DRILL_*）；证件号沿用 `_mask_id_card` 脱敏（§11）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.permissions import is_super_admin
from app.services.db_service import _mask_id_card, _tid, session

# 教务处口径（全校）角色：与 permissions.py `academicAffairs.*` 授权 + mock dataScope=SCHOOL 一致。
# 说明：这是「本域按业务口径的角色归类」而非新 scope 解析器；范围表解析、班级展开仍由 build_affairs_context 承担。
_AA_TENANT_ALL_ROLES = {"ACADEMIC_ADMIN", "ACADEMIC_TEACHER"}


@dataclass
class _AaScope:
    """教务统计数据范围（由 build_affairs_context 派生）。"""
    all: bool = False                                   # True=本校全量（教务处/校管/领导）
    college_ids: set[int] = field(default_factory=set)  # 受限时可见学院
    class_ids: set[int] = field(default_factory=set)    # 受限时可见行政班（college 展开）
    configured: bool = True                             # 受限角色是否已配 scope（否=fail-closed）
    role: str = ""

    @property
    def blocked(self) -> bool:
        """受限且无任何可见范围 → 全部返回空。"""
        return (not self.all) and (not self.college_ids) and (not self.class_ids)


def _resolve_scope(user: dict, db) -> _AaScope:
    role = (user.get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role in _AA_TENANT_ALL_ROLES:
        return _AaScope(all=True, role=role)
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return _AaScope(all=True, role=role)
    allowed = ctx.allowed_class_ids(db)          # None=全量 / set=受限（可空=fail-closed）
    if allowed is None:
        return _AaScope(all=True, role=role)
    return _AaScope(all=False, college_ids=set(ctx.college_ids), class_ids=set(allowed),
                    configured=ctx.is_scope_configured, role=role)


def _validate_college_param(scope: _AaScope, college_id: int | None):
    """受限角色传本范围外 collegeId → 越权拒绝（服务端二次校验，不信任前端）。"""
    if college_id and not scope.all and scope.college_ids and int(college_id) not in scope.college_ids:
        raise no_data_scope("该学院不在您的数据范围内")


def _student_ids(db, scope: _AaScope, college_id: int | None = None,
                 major_id: int | None = None) -> set[int] | None:
    """可见学生主档 id 集合；None=不限（全量且无筛选）。空集=fail-closed。"""
    from app.models import StudentProfile
    if scope.all and not college_id and not major_id:
        return None
    q = select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))
    if not scope.all:
        if scope.college_ids:
            q = q.where(StudentProfile.college_id.in_(scope.college_ids))
        elif scope.class_ids:
            q = q.where(StudentProfile.class_id.in_(scope.class_ids))
        else:
            return set()
    if college_id:
        q = q.where(StudentProfile.college_id == int(college_id))
    if major_id:
        q = q.where(StudentProfile.major_id == int(major_id))
    return set(db.scalars(q).all())


def _acad_student_ids(db, student_ids: set[int] | None) -> set[int] | None:
    """StudentProfile id 集合 → AcademicStudent(t_acad_student) id 集合；None 透传（不限）。"""
    if student_ids is None:
        return None
    if not student_ids:
        return set()
    from app.models import AcademicStudent
    return set(db.scalars(select(AcademicStudent.id).where(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id.in_(student_ids))).all())


def _college_ids_scope(db, scope: _AaScope, college_id: int | None) -> set[int] | None:
    """结构表（课程 owner_college_id / 课表 batch.college_id）用的学院集合；None=不限。"""
    if scope.all and not college_id:
        return None
    if college_id:
        return {int(college_id)}
    return set(scope.college_ids) if scope.college_ids else set()


def _major_ids_scope(db, scope: _AaScope, college_id: int | None, major_id: int | None) -> set[int] | None:
    """培养方案 major_id 用的专业集合；None=不限。"""
    from app.models import Major
    if major_id:
        return {int(major_id)}
    colleges = _college_ids_scope(db, scope, college_id)
    if colleges is None:
        return None
    if not colleges:
        return set()
    return set(db.scalars(select(Major.id).where(
        Major.tenant_id == _tid(), Major.college_id.in_(colleges))).all())


def _class_ids_scope(db, scope: _AaScope, college_id: int | None) -> set[int] | None:
    """教学班/课表 class_id 用的行政班集合；None=不限。"""
    from app.models import Major, StudentProfile
    if scope.all and not college_id:
        return None
    colleges = _college_ids_scope(db, scope, college_id)
    if colleges is None:
        return None
    if not colleges:
        return set(scope.class_ids)   # 受限但无 college（CLASS 直配）→ 用 ctx 班级
    # college → major → class（借 StudentProfile.class_id 归属，避免依赖 SchoolClass.major_id 可能为空）
    ids = set(scope.class_ids)
    majors = db.scalars(select(Major.id).where(
        Major.tenant_id == _tid(), Major.college_id.in_(colleges))).all()
    prof_classes = db.scalars(select(StudentProfile.class_id).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.college_id.in_(colleges))).all()
    ids |= {c for c in prof_classes if c}
    return ids


def _term_codes(db, term_id: int | None) -> set[str] | None:
    """termId → t_acad_grade.term / t_aa_status_change.term_code 可能出现的字符串候选；None=不按学期过滤。"""
    if not term_id:
        return None
    from app.models import AaTerm
    t = db.get(AaTerm, int(term_id))
    if not t or t.tenant_id != _tid():
        return set()
    yc = t.year_code or ""
    return {c for c in (yc, f"{yc}-{t.term_no}", f"{yc}第{t.term_no}学期", str(t.term_no)) if c}


def _rate(num: int, den: int) -> float | None:
    return round(num * 100.0 / den, 1) if den else None


def _ind(key: str, label: str, value=None, numerator=None, denominator=None,
         rate=None, unit="", drill="", status="OK", groups=None, message="") -> dict:
    return {"key": key, "label": label, "value": value, "numerator": numerator,
            "denominator": denominator, "rate": rate, "unit": unit, "drillPath": drill,
            "status": status, "groups": groups or [], "message": message}


def _audit(db, action: str, detail: str = ""):
    """下钻/导出敏感动作写域级审计（AffairsAuditTrail，列对齐 academic_affairs_service._audit）。"""
    from app.models import AffairsAuditTrail
    u = _cur_user()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_STATS", biz_id=None, action=action,
                             operator=(u.get("realName") or u.get("loginName") or str(u.get("userId") or "")),
                             role_name=(u.get("currentRoleCode") or ""),
                             detail=detail[:990], occurred_at=datetime.utcnow()))


def _cur_user() -> dict:
    from app.core.context import get_current_user_ctx
    return get_current_user_ctx() or {}


# ═══════════ 指标聚合 ═══════════

def _i_registration(db, scope, sids, term_id) -> dict:
    from app.models import AaRegistration, AaRegistrationBatch
    q = select(AaRegistration.status).where(
        AaRegistration.tenant_id == _tid(), AaRegistration.is_deleted.is_(False))
    if sids is not None:
        if not sids:
            return _ind("registration", "注册完成率", numerator=0, denominator=0, rate=None,
                        unit="%", drill="registration")
        q = q.where(AaRegistration.student_id.in_(sids))
    if term_id:
        batch_ids = db.scalars(select(AaRegistrationBatch.id).where(
            AaRegistrationBatch.tenant_id == _tid(), AaRegistrationBatch.term_id == int(term_id))).all()
        q = q.where(AaRegistration.batch_id.in_(batch_ids or [-1]))
    statuses = db.scalars(q).all()
    den = len(statuses)
    num = sum(1 for s in statuses if s == "REGISTERED")
    return _ind("registration", "注册完成率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="registration")


def _i_status_change(db, scope, sids, term_id) -> dict:
    from app.models import AaStatusChange
    q = select(AaStatusChange.change_type, func.count()).where(
        AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False),
        AaStatusChange.status == "EFFECTIVE")
    if sids is not None:
        if not sids:
            return _ind("statusChange", "学籍异动人数", value=0, drill="status-change", groups=[])
        q = q.where(AaStatusChange.student_id.in_(sids))
    codes = _term_codes(db, term_id)
    if codes is not None:
        q = q.where(AaStatusChange.term_code.in_(codes or ["-"]))
    rows = db.execute(q.group_by(AaStatusChange.change_type)).all()
    groups = [{"key": r[0] or "UNKNOWN", "count": int(r[1])} for r in rows]
    return _ind("statusChange", "学籍异动人数", value=sum(g["count"] for g in groups),
                drill="status-change", groups=groups)


def _i_program(db, scope, college_id, major_id) -> dict:
    from app.models import AaProgram
    majors = _major_ids_scope(db, scope, college_id, major_id)
    q = select(AaProgram.status).where(
        AaProgram.tenant_id == _tid(), AaProgram.is_deleted.is_(False))
    if majors is not None:
        if not majors:
            return _ind("program", "方案发布率", numerator=0, denominator=0, rate=None, unit="%",
                        drill="program")
        q = q.where(AaProgram.major_id.in_(majors))
    statuses = db.scalars(q).all()
    den = len(statuses)
    num = sum(1 for s in statuses if s == "PUBLISHED")
    return _ind("program", "方案发布率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="program")


def _i_course(db, scope, college_id) -> dict:
    from app.models import AaCourse
    colleges = _college_ids_scope(db, scope, college_id)
    q = select(AaCourse.category, func.count()).where(
        AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False), AaCourse.status == "ENABLED")
    if colleges is not None:
        if not colleges:
            return _ind("course", "课程库启用数", value=0, unit="门", drill="course", groups=[])
        q = q.where(AaCourse.owner_college_id.in_(colleges))
    rows = db.execute(q.group_by(AaCourse.category)).all()
    groups = [{"key": r[0] or "UNKNOWN", "count": int(r[1])} for r in rows]
    return _ind("course", "课程库启用数", value=sum(g["count"] for g in groups), unit="门",
                drill="course", groups=groups)


def _i_teaching_task(db, scope, college_id, term_id) -> dict:
    from app.models import AaTeachingTask
    class_ids = _class_ids_scope(db, scope, college_id)
    q = select(AaTeachingTask.confirm_at).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False))
    if class_ids is not None:
        if not class_ids:
            return _ind("teachingTask", "教学任务完成率", numerator=0, denominator=0, rate=None,
                        unit="%", drill="teaching-task")
        q = q.where(AaTeachingTask.class_id.in_(class_ids))
    rows = db.scalars(q).all()
    den = len(rows)
    num = sum(1 for c in rows if c is not None)   # 已确认=有确认时间（confirm_at）
    return _ind("teachingTask", "教学任务完成率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="teaching-task")


def _i_schedule(db, scope, college_id, term_id) -> dict:
    from app.models import AaScheduleBatch, AaScheduleItem
    colleges = _college_ids_scope(db, scope, college_id)
    bq = select(AaScheduleBatch.id, AaScheduleBatch.status).where(
        AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.is_deleted.is_(False))
    if term_id:
        bq = bq.where(AaScheduleBatch.term_id == int(term_id))
    if colleges is not None:
        if not colleges:
            return _ind("schedule", "课表发布率", numerator=0, denominator=0, rate=None, unit="%",
                        drill="schedule", groups=[{"key": "conflict", "count": 0}])
        bq = bq.where(AaScheduleBatch.college_id.in_(colleges))
    batches = db.execute(bq).all()
    den = len(batches)
    num = sum(1 for b in batches if b[1] == "PUBLISHED")
    batch_ids = [b[0] for b in batches] or [-1]
    # 冲突：同一行政班 + 星期 + 节次 + 单双周 出现 >1 条 EFFECTIVE 排课
    conflict_rows = db.execute(
        select(AaScheduleItem.class_id, AaScheduleItem.weekday, AaScheduleItem.slot_no,
               AaScheduleItem.week_parity, func.count().label("c"))
        .where(AaScheduleItem.tenant_id == _tid(), AaScheduleItem.is_deleted.is_(False),
               AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.batch_id.in_(batch_ids),
               AaScheduleItem.class_id.isnot(None))
        .group_by(AaScheduleItem.class_id, AaScheduleItem.weekday, AaScheduleItem.slot_no,
                  AaScheduleItem.week_parity)
        .having(func.count() > 1)).all()
    conflicts = sum(int(r[4]) - 1 for r in conflict_rows)
    return _ind("schedule", "课表发布率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="schedule", groups=[{"key": "conflict", "count": conflicts}])


def _i_grade_publish(db, scope, college_id, term_id) -> dict:
    from app.models import AaGradeTask
    class_ids = _class_ids_scope(db, scope, college_id)
    q = select(AaGradeTask.status).where(
        AaGradeTask.tenant_id == _tid(), AaGradeTask.is_deleted.is_(False))
    if term_id:
        q = q.where(AaGradeTask.term_id == int(term_id))
    if class_ids is not None:
        if not class_ids:
            return _ind("gradePublish", "成绩录入发布率", numerator=0, denominator=0, rate=None,
                        unit="%", drill="grade")
        q = q.where(AaGradeTask.class_id.in_(class_ids))
    statuses = db.scalars(q).all()
    den = len(statuses)
    num = sum(1 for s in statuses if s == "PUBLISHED")
    return _ind("gradePublish", "成绩录入发布率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="grade")


def _i_fail_rate(db, scope, acad_ids, term_id) -> dict:
    from app.models import AcademicGrade
    q = select(AcademicGrade.pass_status).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.pass_status.in_(["PASSED", "FAILED"]))
    if acad_ids is not None:
        if not acad_ids:
            return _ind("failRate", "挂科率", numerator=0, denominator=0, rate=None, unit="%",
                        drill="grade")
        q = q.where(AcademicGrade.acad_student_id.in_(acad_ids))
    codes = _term_codes(db, term_id)
    if codes is not None:
        q = q.where(AcademicGrade.term.in_(codes or ["-"]))
    rows = db.scalars(q).all()
    den = len(rows)
    num = sum(1 for s in rows if s == "FAILED")
    return _ind("failRate", "挂科率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="grade")


def _i_makeup_retake(db, scope, acad_ids, term_id) -> dict:
    from app.models import AcademicMakeup, AcademicRetake
    mq = select(func.count(func.distinct(AcademicMakeup.acad_student_id))).where(
        AcademicMakeup.tenant_id == _tid(), AcademicMakeup.record_status == "ACTIVE")
    rq = select(func.count(func.distinct(AcademicRetake.acad_student_id))).where(
        AcademicRetake.tenant_id == _tid(), AcademicRetake.record_status == "ACTIVE")
    if acad_ids is not None:
        if not acad_ids:
            return _ind("makeupRetake", "补考/重修人数", value=0, drill="grade",
                        groups=[{"key": "makeup", "count": 0}, {"key": "retake", "count": 0}])
        mq = mq.where(AcademicMakeup.acad_student_id.in_(acad_ids))
        rq = rq.where(AcademicRetake.acad_student_id.in_(acad_ids))
    makeup = int(db.scalar(mq) or 0)
    retake = int(db.scalar(rq) or 0)
    return _ind("makeupRetake", "补考/重修人数", value=makeup + retake, drill="grade",
                groups=[{"key": "makeup", "count": makeup}, {"key": "retake", "count": retake}])


def _i_warning(db, scope, acad_ids) -> dict:
    """按等级分组的预警指标——统计口径统一到 warning_service.group_counts（2026-07-15，与
    「学业预警」模块自身统计共用同一份聚合实现，不再各写一套 GROUP BY）。"""
    from app.modules.academic_affairs.services.academic_affairs_warning_service import group_counts
    rows = group_counts(db, acad_ids, dims=("level",), exclude_closed=True)
    groups = [{"key": r["level"] or "UNKNOWN", "count": r["count"]} for r in rows]
    return _ind("warning", "学业预警数", value=sum(g["count"] for g in groups), drill="warning",
                groups=groups)


def _i_graduation(db, scope, sids) -> dict:
    from app.models import AaGraduationAuditResult
    q = select(AaGraduationAuditResult.overall, AaGraduationAuditResult.conclusion).where(
        AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.is_deleted.is_(False))
    if sids is not None:
        if not sids:
            return _ind("graduation", "毕业资格通过率", numerator=0, denominator=0, rate=None,
                        unit="%", drill="graduation")
        q = q.where(AaGraduationAuditResult.student_id.in_(sids))
    rows = db.execute(q).all()
    den = len(rows)
    num = sum(1 for r in rows if r[0] == "SYSTEM_PASSED" or r[1] == "GRADUATED")
    return _ind("graduation", "毕业资格通过率", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="graduation")


def _i_schedule_change(db, scope, college_id, term_id) -> dict:
    """调停课统计（07 号卡，教务总览卡）：本文件统一 scope 引擎下的全局计数（按类型分组）。
    独立页面 `/schedule-change/stats`（`academicAffairs.scheduleChange.view`）另有教师自助视角
    （非 TENANT_ALL 角色仅见本人课位），两者口径不同，均为真实数据、互不覆盖（见模块头注释）。"""
    from app.models import AaScheduleChange
    class_ids = _class_ids_scope(db, scope, college_id)
    q = select(AaScheduleChange.change_type).where(
        AaScheduleChange.tenant_id == _tid(), AaScheduleChange.is_deleted.is_(False))
    if term_id:
        q = q.where(AaScheduleChange.term_id == int(term_id))
    if class_ids is not None:
        if not class_ids:
            return _ind("scheduleChange", "调停课统计", value=0, unit="单", drill="schedule-change", groups=[])
        q = q.where(AaScheduleChange.class_id.in_(class_ids))
    rows = db.scalars(q).all()
    groups: dict = {}
    for ct in rows:
        groups[ct or "UNKNOWN"] = groups.get(ct or "UNKNOWN", 0) + 1
    return _ind("scheduleChange", "调停课统计", value=len(rows), unit="单", drill="schedule-change",
                groups=[{"key": k, "count": v} for k, v in groups.items()])


def _i_course_selection(db, scope, college_id, term_id) -> dict:
    """选课统计（08 号卡，教务总览卡）：跨批次容量/已选填充率。学院范围通过
    `AaSelectionCourse.course_id → AaCourse.owner_college_id` 联查收敛（供给表本身无 college_id 列）。"""
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse
    bq = select(AaSelectionBatch.id).where(
        AaSelectionBatch.tenant_id == _tid(), AaSelectionBatch.is_deleted.is_(False))
    if term_id:
        bq = bq.where(AaSelectionBatch.term_id == int(term_id))
    batch_ids = db.scalars(bq).all() or [-1]
    colleges = _college_ids_scope(db, scope, college_id)
    q = select(AaSelectionCourse.capacity, AaSelectionCourse.selected_count).where(
        AaSelectionCourse.tenant_id == _tid(), AaSelectionCourse.is_deleted.is_(False),
        AaSelectionCourse.batch_id.in_(batch_ids))
    if colleges is not None:
        if not colleges:
            return _ind("courseSelection", "选课统计", numerator=0, denominator=0, rate=None,
                        unit="%", drill="course-selection")
        course_ids = db.scalars(select(AaCourse.id).where(
            AaCourse.tenant_id == _tid(), AaCourse.owner_college_id.in_(colleges))).all()
        q = q.where(AaSelectionCourse.course_id.in_(course_ids or [-1]))
    rows = db.execute(q).all()
    cap = sum(int(r[0] or 0) for r in rows)
    sel = sum(int(r[1] or 0) for r in rows)
    return _ind("courseSelection", "选课统计", numerator=sel, denominator=cap, rate=_rate(sel, cap),
                unit="%", drill="course-selection")


def _i_exam(db, scope, college_id, term_id) -> dict:
    """考务统计（09 号卡，教务总览卡）：考试课程确认率（`AaExamCourse.college_id` 冗余列直接收敛）。"""
    from app.models import AaExamBatch, AaExamCourse
    bq = select(AaExamBatch.id).where(
        AaExamBatch.tenant_id == _tid(), AaExamBatch.is_deleted.is_(False))
    if term_id:
        bq = bq.where(AaExamBatch.term_id == int(term_id))
    batch_ids = db.scalars(bq).all() or [-1]
    colleges = _college_ids_scope(db, scope, college_id)
    q = select(AaExamCourse.status).where(
        AaExamCourse.tenant_id == _tid(), AaExamCourse.is_deleted.is_(False),
        AaExamCourse.batch_id.in_(batch_ids), AaExamCourse.status != "REMOVED")
    if colleges is not None:
        if not colleges:
            return _ind("exam", "考务统计", numerator=0, denominator=0, rate=None, unit="%", drill="exam")
        q = q.where(AaExamCourse.college_id.in_(colleges))
    rows = db.scalars(q).all()
    den = len(rows)
    num = sum(1 for s in rows if s == "CONFIRMED")
    return _ind("exam", "考务统计", numerator=num, denominator=den, rate=_rate(num, den),
                unit="%", drill="exam")


def _i_resource(db, scope) -> dict:
    """教学资源统计（14 号卡，教务总览卡）：教室字典为校级共享资产（表无 college_id 列，
    非任何学院独占），不做学院级收敛，仅按整体 `scope.blocked` 兜底 fail-closed。"""
    from app.models import AaClassroom
    if scope.blocked:
        return _ind("resource", "教学资源统计", value=0, unit="间", drill="resource", groups=[])
    rows = db.scalars(select(AaClassroom.status).where(
        AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False))).all()
    groups: dict = {}
    for s in rows:
        groups[s or "UNKNOWN"] = groups.get(s or "UNKNOWN", 0) + 1
    return _ind("resource", "教学资源统计", value=len(rows), unit="间", drill="resource",
                groups=[{"key": k, "count": v} for k, v in groups.items()])


# ═══════════ 对外聚合入口 ═══════════

def overview(user: dict, term_id=None, college_id=None, major_id=None) -> dict:
    """教务总览：15 项指标全部为真实聚合（2026-07-16 起 07/08/09/14 不再占位，见模块头注释）。"""
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id, major_id)
        acad_ids = _acad_student_ids(db, sids)
        indicators = [
            _i_registration(db, scope, sids, term_id),
            _i_status_change(db, scope, sids, term_id),
            _i_program(db, scope, college_id, major_id),
            _i_course(db, scope, college_id),
            _i_teaching_task(db, scope, college_id, term_id),
            _i_schedule(db, scope, college_id, term_id),
            _i_grade_publish(db, scope, college_id, term_id),
            _i_fail_rate(db, scope, acad_ids, term_id),
            _i_makeup_retake(db, scope, acad_ids, term_id),
            _i_warning(db, scope, acad_ids),
            _i_graduation(db, scope, sids),
            _i_schedule_change(db, scope, college_id, term_id),
            _i_course_selection(db, scope, college_id, term_id),
            _i_exam(db, scope, college_id, term_id),
            _i_resource(db, scope),
        ]
        return {"indicators": indicators,
                "scope": {"all": scope.all, "role": scope.role,
                          "collegeIds": sorted(scope.college_ids), "blocked": scope.blocked},
                "filters": {"termId": term_id, "collegeId": college_id, "majorId": major_id},
                "asOf": datetime.utcnow().isoformat()}


def filters(user: dict) -> dict:
    """筛选器候选：学期 / 学院 / 专业（受 scope 收敛）。"""
    from app.models import AaTerm, College, Major
    with session() as db:
        scope = _resolve_scope(user, db)
        terms = [{"id": str(t.id), "label": f"{t.year_code} 第{t.term_no}学期",
                  "isCurrent": bool(t.is_current)}
                 for t in db.scalars(select(AaTerm).where(
                     AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)).order_by(
                     AaTerm.year_code.desc(), AaTerm.term_no.desc())).all()]
        cq = select(College).where(College.tenant_id == _tid(), College.is_deleted.is_(False))
        if not scope.all and scope.college_ids:
            cq = cq.where(College.id.in_(scope.college_ids))
        elif not scope.all:
            cq = cq.where(College.id.in_([-1]))
        colleges = [{"id": str(c.id), "label": c.college_name} for c in db.scalars(cq).all()]
        college_ids = _college_ids_scope(db, scope, None)
        mq = select(Major).where(Major.tenant_id == _tid(), Major.is_deleted.is_(False))
        if college_ids is not None:
            mq = mq.where(Major.college_id.in_(college_ids or [-1]))
        majors = [{"id": str(m.id), "label": m.major_name, "collegeId": str(m.college_id or "")}
                  for m in db.scalars(mq).all()]
        return {"terms": terms, "colleges": colleges, "majors": majors}


# ═══════════ 下钻明细（学生级写审计 + 脱敏） ═══════════

def registration_unregistered(user, term_id=None, college_id=None, major_id=None,
                              page=1, page_size=20) -> tuple[list[dict], int]:
    """注册下钻：未注册学生名单（脱敏 + STATS_DRILL 审计）。"""
    from app.models import AaRegistration, AaRegistrationBatch, StudentProfile
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id, major_id)
        q = select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(), AaRegistration.is_deleted.is_(False),
            AaRegistration.status != "REGISTERED")
        if sids is not None:
            if not sids:
                return [], 0
            q = q.where(AaRegistration.student_id.in_(sids))
        if term_id:
            bids = db.scalars(select(AaRegistrationBatch.id).where(
                AaRegistrationBatch.tenant_id == _tid(),
                AaRegistrationBatch.term_id == int(term_id))).all()
            q = q.where(AaRegistration.batch_id.in_(bids or [-1]))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        regs = db.scalars(q.order_by(AaRegistration.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        prof = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r in regs] or [-1]))).all()}
        rows = []
        for r in regs:
            p = prof.get(r.student_id)
            rows.append({"registrationId": str(r.id), "studentId": str(r.student_id),
                         "studentName": (p.real_name if p else ""),
                         "studentNo": _mask_id_card(p.student_no) if p else "",
                         "status": r.status})
        _audit(db, "STATS_DRILL_REGISTRATION", f"未注册名单 total={total} college={college_id or '-'}")
        db.commit()
        return rows, total


def warning_detail(user, level=None, source=None, college_id=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """预警下钻：非 CLOSED 预警明细（脱敏 + 审计）。"""
    from app.models import AcademicStudent, AcademicWarning, StudentProfile
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        acad_ids = _acad_student_ids(db, sids)
        q = select(AcademicWarning).where(
            AcademicWarning.tenant_id == _tid(), AcademicWarning.record_status == "ACTIVE",
            AcademicWarning.status != "CLOSED")
        if acad_ids is not None:
            if not acad_ids:
                return [], 0
            q = q.where(AcademicWarning.acad_student_id.in_(acad_ids))
        if level:
            q = q.where(AcademicWarning.level == level)
        if source:
            q = q.where(AcademicWarning.source_code == source)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        warns = db.scalars(q.order_by(AcademicWarning.id.desc())
                           .offset((page - 1) * page_size).limit(page_size)).all()
        acad = {a.id: a for a in db.scalars(select(AcademicStudent).where(
            AcademicStudent.id.in_([w.acad_student_id for w in warns] or [-1]))).all()}
        rows = []
        for w in warns:
            a = acad.get(w.acad_student_id)
            rows.append({"warningId": str(w.id), "studentName": (a.name if a else ""),
                         "studentNo": _mask_id_card(a.student_no) if a else "",
                         "className": (a.class_name if a else ""),
                         "level": w.level, "warnType": w.warn_type, "status": w.status})
        _audit(db, "STATS_DRILL_WARNING", f"预警明细 total={total} level={level or '-'}")
        db.commit()
        return rows, total


def status_change_detail(user, change_type=None, term_id=None, college_id=None,
                         page=1, page_size=20) -> tuple[list[dict], int]:
    """学籍异动下钻：EFFECTIVE 异动明细。"""
    from app.models import AaStatusChange, StudentProfile
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        q = select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False),
            AaStatusChange.status == "EFFECTIVE")
        if sids is not None:
            if not sids:
                return [], 0
            q = q.where(AaStatusChange.student_id.in_(sids))
        if change_type:
            q = q.where(AaStatusChange.change_type == change_type)
        codes = _term_codes(db, term_id)
        if codes is not None:
            q = q.where(AaStatusChange.term_code.in_(codes or ["-"]))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        changes = db.scalars(q.order_by(AaStatusChange.id.desc())
                             .offset((page - 1) * page_size).limit(page_size)).all()
        prof = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([c.student_id for c in changes] or [-1]))).all()}
        rows = []
        for c in changes:
            p = prof.get(c.student_id)
            rows.append({"changeId": str(c.id), "studentName": (p.real_name if p else ""),
                         "studentNo": _mask_id_card(p.student_no) if p else "",
                         "changeType": c.change_type, "fromStatus": c.from_status,
                         "toStatus": c.to_status})
        _audit(db, "STATS_DRILL_STATUS_CHANGE", f"异动明细 total={total} type={change_type or '-'}")
        db.commit()
        return rows, total


# ═══════════ 09B 教务统计 Tier1 10 项三级模块补充聚合 + 下钻
# （学籍统计/注册统计/课程统计/教学任务统计/课表统计/成绩统计/学业预警统计/毕业资格统计/
#   教师工作量统计/导出报表；`docs/03-业务模块设计/教务中心/施工包/教务统计/三级施工卡/`
#   02/03/04/05/06/10/11/12/13/15 号卡）。全部复用 §指标聚合 已有 `_i_*` 与 scope 辅助函数，
#   不重复实现聚合算法；`/stats/status-change`、`/stats/registration`、`/stats/warning` 三个
#   路径已被既有「教务总览」下钻占用（返回明细列表），故本节对应聚合端点改用 `/summary` 后缀，
#   避免破坏已上线的总览页下钻调用（AaStatsOverviewView.vue 现状实测）。 ═══════════

_WORKLOAD_DISCLAIMER = "基础教学任务量参考，非学校正式工作量核算结果（如需正式核算需学校明确课程/班型/职称系数规则，见三级卡13 D 项待确认）"


def status_change_stats(user, term_id=None, college_id=None) -> dict:
    """学籍统计聚合（02 卡）：按 change_type 分组计数，复用 `_i_status_change`。"""
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        ind = _i_status_change(db, scope, sids, term_id)
        return {"total": ind["value"], "byType": ind["groups"], "scope": {"blocked": scope.blocked}}


def registration_stats(user, term_id=None, college_id=None, major_id=None) -> dict:
    """注册统计聚合（03 卡）：完成率，复用 `_i_registration`。"""
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id, major_id)
        ind = _i_registration(db, scope, sids, term_id)
        return {"registered": ind["numerator"], "expected": ind["denominator"], "rate": ind["rate"],
                "scope": {"blocked": scope.blocked}}


def course_stats(user, category=None, college_id=None) -> dict:
    """课程统计聚合（04 卡）：ENABLED 课程按类别/学院双维分组。"""
    from app.models import AaCourse
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        colleges = _college_ids_scope(db, scope, college_id)
        q = select(AaCourse.category, AaCourse.owner_college_id, func.count()).where(
            AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False), AaCourse.status == "ENABLED")
        if category:
            q = q.where(AaCourse.category == category)
        if colleges is not None:
            if not colleges:
                return {"total": 0, "byCategory": [], "byCollege": [], "scope": {"blocked": scope.blocked}}
            q = q.where(AaCourse.owner_college_id.in_(colleges))
        rows = db.execute(q.group_by(AaCourse.category, AaCourse.owner_college_id)).all()
        by_cat: dict = {}
        by_col: dict = {}
        total = 0
        for cat, col, c in rows:
            c = int(c)
            total += c
            by_cat[cat or "UNKNOWN"] = by_cat.get(cat or "UNKNOWN", 0) + c
            key = str(col) if col else "UNKNOWN"
            by_col[key] = by_col.get(key, 0) + c
        return {"total": total,
                "byCategory": [{"key": k, "count": v} for k, v in by_cat.items()],
                "byCollege": [{"key": k, "count": v} for k, v in by_col.items()],
                "scope": {"blocked": scope.blocked}}


def course_detail(user, category=None, college_id=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """课程统计下钻（04 卡）：ENABLED 课程明细。"""
    from app.models import AaCourse
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        colleges = _college_ids_scope(db, scope, college_id)
        q = select(AaCourse).where(
            AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False), AaCourse.status == "ENABLED")
        if category:
            q = q.where(AaCourse.category == category)
        if colleges is not None:
            if not colleges:
                return [], 0
            q = q.where(AaCourse.owner_college_id.in_(colleges))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(AaCourse.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = [{"courseId": str(c.id), "courseCode": c.course_code, "courseName": c.course_name,
                 "category": c.category, "credit": float(c.credit) if c.credit is not None else None,
                 "hoursTotal": c.hours_total, "ownerCollegeId": str(c.owner_college_id or "")}
                for c in rows]
        return items, total


def teaching_task_stats(user, college_id=None, term_id=None) -> dict:
    """教学任务统计聚合（05 卡）：确认完成率，复用 `_i_teaching_task`。"""
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        ind = _i_teaching_task(db, scope, college_id, term_id)
        return {"confirmed": ind["numerator"], "expected": ind["denominator"], "rate": ind["rate"],
                "scope": {"blocked": scope.blocked}}


def teaching_task_pending(user, college_id=None, term_id=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """教学任务统计下钻（05 卡）：未确认（`confirm_at IS NULL`）任务清单。"""
    from app.models import AaTeachingTask
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        class_ids = _class_ids_scope(db, scope, college_id)
        q = select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.confirm_at.is_(None))
        if class_ids is not None:
            if not class_ids:
                return [], 0
            q = q.where(AaTeachingTask.class_id.in_(class_ids))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(AaTeachingTask.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = [{"taskId": str(t.id), "courseName": t.course_name,
                 "teachingClassName": t.teaching_class_name, "teacherName": t.teacher_name,
                 "status": t.status} for t in rows]
        return items, total


def schedule_stats(user, college_id=None, term_id=None) -> dict:
    """课表统计聚合（06 卡）：发布覆盖率 + 未解决冲突数，复用 `_i_schedule`。"""
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        ind = _i_schedule(db, scope, college_id, term_id)
        conflicts = next((g["count"] for g in ind["groups"] if g["key"] == "conflict"), 0)
        return {"publishedRate": ind["rate"], "published": ind["numerator"],
                "totalBatches": ind["denominator"], "unresolvedConflicts": conflicts,
                "scope": {"blocked": scope.blocked}}


def schedule_conflicts(user, college_id=None, term_id=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """课表统计下钻（06 卡）：冲突分组明细（班级+星期+节次+单双周，复用 `_i_schedule` 同一判定口径）。"""
    from app.models import AaScheduleBatch, AaScheduleItem
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        colleges = _college_ids_scope(db, scope, college_id)
        bq = select(AaScheduleBatch.id).where(
            AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaScheduleBatch.term_id == int(term_id))
        if colleges is not None:
            if not colleges:
                return [], 0
            bq = bq.where(AaScheduleBatch.college_id.in_(colleges))
        batch_ids = db.scalars(bq).all() or [-1]
        groups = db.execute(
            select(AaScheduleItem.class_id, AaScheduleItem.class_name, AaScheduleItem.weekday,
                   AaScheduleItem.slot_no, AaScheduleItem.week_parity, func.count().label("c"))
            .where(AaScheduleItem.tenant_id == _tid(), AaScheduleItem.is_deleted.is_(False),
                   AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.batch_id.in_(batch_ids),
                   AaScheduleItem.class_id.isnot(None))
            .group_by(AaScheduleItem.class_id, AaScheduleItem.class_name, AaScheduleItem.weekday,
                      AaScheduleItem.slot_no, AaScheduleItem.week_parity)
            .having(func.count() > 1)).all()
        total = len(groups)
        page_rows = groups[(page - 1) * page_size: (page - 1) * page_size + page_size]
        items = []
        for class_id, class_name, weekday, slot_no, parity, c in page_rows:
            detail_rows = db.scalars(select(AaScheduleItem).where(
                AaScheduleItem.tenant_id == _tid(), AaScheduleItem.is_deleted.is_(False),
                AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.batch_id.in_(batch_ids),
                AaScheduleItem.class_id == class_id, AaScheduleItem.weekday == weekday,
                AaScheduleItem.slot_no == slot_no, AaScheduleItem.week_parity == parity)).all()
            items.append({"className": class_name, "weekday": weekday, "slotNo": slot_no,
                         "weekParity": parity, "conflictCount": int(c),
                         "courses": [{"courseName": d.course_name, "teacherName": d.teacher_name,
                                     "classroomText": d.classroom_text} for d in detail_rows]})
        return items, total


def grade_stats(user, term_id=None, college_id=None) -> dict:
    """成绩统计聚合（10 卡）：挂科率 + 录入发布率 + 补考/重修人数，复用 `_i_fail_rate`/`_i_grade_publish`/`_i_makeup_retake`。"""
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        acad_ids = _acad_student_ids(db, sids)
        fail = _i_fail_rate(db, scope, acad_ids, term_id)
        pub = _i_grade_publish(db, scope, college_id, term_id)
        mkr = _i_makeup_retake(db, scope, acad_ids, term_id)
        makeup = next((g["count"] for g in mkr["groups"] if g["key"] == "makeup"), 0)
        retake = next((g["count"] for g in mkr["groups"] if g["key"] == "retake"), 0)
        return {"failRate": fail["rate"], "failNumerator": fail["numerator"],
                "failDenominator": fail["denominator"], "entryPublishRate": pub["rate"],
                "publishNumerator": pub["numerator"], "publishDenominator": pub["denominator"],
                "makeupCount": makeup, "retakeCount": retake, "makeupRetakeCount": mkr["value"],
                "scope": {"blocked": scope.blocked}}


def grade_detail(user, term_id=None, college_id=None, course_name=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """成绩统计下钻（10 卡）：挂科学生明细（`pass_status` 口径同 `academic_affairs_grade_service.fail_list` 已核验的
    真实枚举值 FAIL/FAILED 双值防御，见 10 号卡 §1 勘误），扩展 scope 收敛（既有 `fail_list` 无此收敛，本函数按施工卡要求新建，不改动既有函数）。"""
    from app.models import AcademicGrade, AcademicStudent
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        acad_ids = _acad_student_ids(db, sids)
        q = select(AcademicGrade).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.pass_status.in_(["FAIL", "FAILED"]))
        if acad_ids is not None:
            if not acad_ids:
                return [], 0
            q = q.where(AcademicGrade.acad_student_id.in_(acad_ids))
        codes = _term_codes(db, term_id)
        if codes is not None:
            q = q.where(AcademicGrade.term.in_(codes or ["-"]))
        if course_name:
            q = q.where(AcademicGrade.course_name.like(f"%{course_name}%"))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(AcademicGrade.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        acad = {a.id: a for a in db.scalars(select(AcademicStudent).where(
            AcademicStudent.id.in_([g.acad_student_id for g in rows] or [-1]))).all()}
        items = []
        for g in rows:
            a = acad.get(g.acad_student_id)
            items.append({"gradeId": str(g.id), "studentName": (a.name if a else ""),
                         "studentNo": _mask_id_card(a.student_no) if a else "",
                         "courseName": g.course_name, "term": g.term or "", "score": g.score})
        _audit(db, "STATS_DRILL_GRADE", f"挂科明细 total={total} term={term_id or '-'}")
        db.commit()
        return items, total


def warning_stats(user, term_id=None, college_id=None) -> dict:
    """学业预警统计聚合（11 卡）：按等级+来源双维分组，两维均复用 warning_service.group_counts
    （与「学业预警」模块自身统计口径统一，2026-07-15）。"""
    from app.modules.academic_affairs.services.academic_affairs_warning_service import group_counts
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        acad_ids = _acad_student_ids(db, sids)
        ind = _i_warning(db, scope, acad_ids)
        rows = group_counts(db, acad_ids, dims=("source_code",), exclude_closed=True)
        by_source = [{"key": r["source_code"] or "UNKNOWN", "count": r["count"]} for r in rows]
        return {"total": ind["value"], "byLevel": ind["groups"], "bySource": by_source,
                "scope": {"blocked": scope.blocked}}


def graduation_stats(user, batch_id=None, college_id=None) -> dict:
    """毕业资格统计聚合（12 卡）：通过率 + 异常项类型分布（解析 `item_results_json`，逐生七项判定见
    `academic_affairs_graduation_service._run_items` 已核验结构 `{item,result,owner,evidence}`）。"""
    import json
    from app.models import AaGraduationAuditResult
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        q = select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.is_deleted.is_(False))
        if batch_id:
            q = q.where(AaGraduationAuditResult.batch_id == int(batch_id))
        if sids is not None:
            if not sids:
                return {"passRate": None, "passed": 0, "expected": 0, "byAbnormalItem": [],
                        "scope": {"blocked": scope.blocked}}
            q = q.where(AaGraduationAuditResult.student_id.in_(sids))
        rows = db.scalars(q).all()
        den = len(rows)
        num = 0
        item_counts: dict = {}
        for r in rows:
            if r.overall == "SYSTEM_PASSED" or r.conclusion == "GRADUATED":
                num += 1
            if r.item_results_json:
                try:
                    items = json.loads(r.item_results_json)
                except (ValueError, TypeError):
                    items = []
                for it in items:
                    if it.get("result") == "FAIL":
                        k = it.get("item") or "UNKNOWN"
                        item_counts[k] = item_counts.get(k, 0) + 1
        return {"passRate": _rate(num, den), "passed": num, "expected": den,
                "byAbnormalItem": [{"key": k, "count": v} for k, v in item_counts.items()],
                "scope": {"blocked": scope.blocked}}


def graduation_abnormal(user, batch_id=None, college_id=None, item_type=None,
                        page=1, page_size=20) -> tuple[list[dict], int]:
    """毕业资格统计下钻（12 卡）：SYSTEM_ABNORMAL 学生名单 + 命中的异常项类型。"""
    import json
    from app.models import AaGraduationAuditResult, StudentProfile
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        sids = _student_ids(db, scope, college_id)
        q = select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.is_deleted.is_(False),
            AaGraduationAuditResult.overall == "SYSTEM_ABNORMAL")
        if batch_id:
            q = q.where(AaGraduationAuditResult.batch_id == int(batch_id))
        if sids is not None:
            if not sids:
                return [], 0
            q = q.where(AaGraduationAuditResult.student_id.in_(sids))
        rows = db.scalars(q.order_by(AaGraduationAuditResult.id.desc())).all()
        filtered = []
        for r in rows:
            items = []
            if r.item_results_json:
                try:
                    items = json.loads(r.item_results_json)
                except (ValueError, TypeError):
                    items = []
            fail_items = [it.get("item") for it in items if it.get("result") == "FAIL"]
            if item_type and item_type not in fail_items:
                continue
            filtered.append((r, fail_items))
        total = len(filtered)
        page_rows = filtered[(page - 1) * page_size: (page - 1) * page_size + page_size]
        prof = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r, _ in page_rows] or [-1]))).all()}
        items_out = []
        for r, fail_items in page_rows:
            p = prof.get(r.student_id)
            items_out.append({"resultId": str(r.id), "studentName": (p.real_name if p else ""),
                             "studentNo": _mask_id_card(p.student_no) if p else "",
                             "abnormalItems": fail_items, "status": r.status})
        _audit(db, "STATS_DRILL_GRADUATION", f"毕业异常明细 total={total} batch={batch_id or '-'}")
        db.commit()
        return items_out, total


def workload_stats(user, term_id=None, college_id=None) -> dict:
    """教师工作量统计聚合（13 卡，`ai_proposal`）：教师学时合计+任务数排行，**基础参考，非正式核算**（§1 待确认项）。"""
    from app.models import AaTeachingTask
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        class_ids = _class_ids_scope(db, scope, college_id)
        q = select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.teacher_key.isnot(None))
        if class_ids is not None:
            if not class_ids:
                return {"ranking": [], "disclaimer": _WORKLOAD_DISCLAIMER,
                        "scope": {"blocked": scope.blocked}}
            q = q.where(AaTeachingTask.class_id.in_(class_ids))
        rows = db.scalars(q).all()
        agg: dict = {}
        for t in rows:
            k = t.teacher_key
            item = agg.setdefault(k, {"teacherKey": k, "teacherName": t.teacher_name or "",
                                      "totalHours": 0, "taskCount": 0})
            item["totalHours"] += int(t.total_hours or 0)
            item["taskCount"] += 1
        ranking = sorted(agg.values(), key=lambda x: -x["totalHours"])
        return {"ranking": ranking, "disclaimer": _WORKLOAD_DISCLAIMER,
                "scope": {"blocked": scope.blocked}}


def workload_detail(user, teacher_key, college_id=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """教师工作量统计下钻（13 卡）：单个教师的授课任务明细。

    注：`_resolve_scope` 现状把 ACADEMIC_TEACHER 与 ACADEMIC_ADMIN 同等归为 TENANT_ALL（见模块头注释），
    教务域当前未实现"教师仅查本人"（SELF-COURSE）的强制收窄——这是本文件既有共享 scope 解析器的现状，
    非本次新增缺口，不在本轮 10 模块范围内改动共享 `_resolve_scope`（会影响已上线总览页），如实登记。
    """
    if not teacher_key:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "teacherKey 必填")
    from app.models import AaTeachingTask
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        class_ids = _class_ids_scope(db, scope, college_id)
        q = select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.teacher_key == teacher_key)
        if class_ids is not None:
            if not class_ids:
                return [], 0
            q = q.where(AaTeachingTask.class_id.in_(class_ids))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(AaTeachingTask.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = [{"taskId": str(t.id), "courseName": t.course_name,
                 "teachingClassName": t.teaching_class_name, "weeklyHours": t.weekly_hours,
                 "totalHours": t.total_hours, "status": t.status} for t in rows]
        return items, total


# ═══════════ 教务统计第三轮续工（2026-07-16）：08/09/14 号卡独立 Tab 聚合 + 下钻
# （选课统计/考务统计/教学资源统计；07 调停课统计不在本节——其完整交互在独立页面
#  `/schedule-change/stats`，本文件仅在 overview() 提供全局计数卡，见 `_i_schedule_change`）。═══════════

def course_selection_stats(user, term_id=None, college_id=None) -> dict:
    """选课统计聚合（08 号卡）：跨批次容量/已选/填充率 + 低人数/满额课程数 + 批次状态分布 + 选课记录数。"""
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse, AaSelectionRecord
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        bq = select(AaSelectionBatch).where(
            AaSelectionBatch.tenant_id == _tid(), AaSelectionBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaSelectionBatch.term_id == int(term_id))
        batches = db.scalars(bq).all()
        by_status: dict = {}
        for b in batches:
            by_status[b.status] = by_status.get(b.status, 0) + 1
        by_status_out = [{"key": k, "count": v} for k, v in by_status.items()]
        batch_ids = [b.id for b in batches] or [-1]
        colleges = _college_ids_scope(db, scope, college_id)
        cq = select(AaSelectionCourse).where(
            AaSelectionCourse.tenant_id == _tid(), AaSelectionCourse.is_deleted.is_(False),
            AaSelectionCourse.batch_id.in_(batch_ids))
        if colleges is not None:
            if not colleges:
                return {"byBatchStatus": by_status_out, "totalCapacity": 0, "totalSelected": 0,
                        "fillRate": None, "lowEnrollCount": 0, "fullCount": 0, "recordCount": 0,
                        "scope": {"blocked": scope.blocked}}
            course_ids = db.scalars(select(AaCourse.id).where(
                AaCourse.tenant_id == _tid(), AaCourse.owner_college_id.in_(colleges))).all()
            cq = cq.where(AaSelectionCourse.course_id.in_(course_ids or [-1]))
        courses = db.scalars(cq).all()
        cap = sum(int(c.capacity or 0) for c in courses)
        sel = sum(int(c.selected_count or 0) for c in courses)
        low = sum(1 for c in courses if c.status == "OPEN" and (c.selected_count or 0) < (c.min_capacity or 0))
        full = sum(1 for c in courses if (c.selected_count or 0) >= (c.capacity or 0) > 0)
        sel_course_ids = [c.id for c in courses] or [-1]
        rec_q = select(AaSelectionRecord.id).where(
            AaSelectionRecord.tenant_id == _tid(), AaSelectionRecord.is_deleted.is_(False),
            AaSelectionRecord.selection_course_id.in_(sel_course_ids),
            AaSelectionRecord.status.in_(["SELECTED", "LOCKED"]))
        rec_total = int(db.scalar(select(func.count()).select_from(rec_q.subquery())) or 0)
        return {"byBatchStatus": by_status_out, "totalCapacity": cap, "totalSelected": sel,
                "fillRate": _rate(sel, cap), "lowEnrollCount": low, "fullCount": full,
                "recordCount": rec_total, "scope": {"blocked": scope.blocked}}


def course_selection_detail(user, term_id=None, college_id=None, page=1, page_size=20) -> tuple[list[dict], int]:
    """选课统计下钻（08 号卡）：低人数课程清单（OPEN 且 selected_count < min_capacity，
    需教务处/学院决策取消开课或催选，课程级数据非学生级，不涉敏感字段，无需脱敏/审计）。"""
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        bq = select(AaSelectionBatch.id, AaSelectionBatch.batch_name).where(
            AaSelectionBatch.tenant_id == _tid(), AaSelectionBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaSelectionBatch.term_id == int(term_id))
        batch_name = {b[0]: b[1] for b in db.execute(bq).all()}
        batch_ids = list(batch_name.keys()) or [-1]
        colleges = _college_ids_scope(db, scope, college_id)
        cq = select(AaSelectionCourse).where(
            AaSelectionCourse.tenant_id == _tid(), AaSelectionCourse.is_deleted.is_(False),
            AaSelectionCourse.batch_id.in_(batch_ids), AaSelectionCourse.status == "OPEN")
        if colleges is not None:
            if not colleges:
                return [], 0
            course_ids = db.scalars(select(AaCourse.id).where(
                AaCourse.tenant_id == _tid(), AaCourse.owner_college_id.in_(colleges))).all()
            cq = cq.where(AaSelectionCourse.course_id.in_(course_ids or [-1]))
        rows = [c for c in db.scalars(cq).all() if (c.selected_count or 0) < (c.min_capacity or 0)]
        total = len(rows)
        page_rows = rows[(page - 1) * page_size: (page - 1) * page_size + page_size]
        items = [{"courseId": str(c.id), "batchId": str(c.batch_id),
                 "batchName": batch_name.get(c.batch_id, ""), "courseName": c.course_name or "",
                 "teacherName": c.teacher_name or "", "capacity": c.capacity,
                 "minCapacity": c.min_capacity, "selectedCount": c.selected_count,
                 "status": c.status} for c in page_rows]
        return items, total


def exam_stats(user, term_id=None, college_id=None) -> dict:
    """考务统计聚合（09 号卡）：跨批次考试课程确认率 + 缺考/违纪人次 + 批次状态分布。"""
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        bq = select(AaExamBatch).where(AaExamBatch.tenant_id == _tid(), AaExamBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaExamBatch.term_id == int(term_id))
        batches = db.scalars(bq).all()
        by_status: dict = {}
        for b in batches:
            by_status[b.status] = by_status.get(b.status, 0) + 1
        by_status_out = [{"key": k, "count": v} for k, v in by_status.items()]
        batch_ids = [b.id for b in batches] or [-1]
        colleges = _college_ids_scope(db, scope, college_id)
        cq = select(AaExamCourse).where(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.is_deleted.is_(False),
            AaExamCourse.batch_id.in_(batch_ids), AaExamCourse.status != "REMOVED")
        if colleges is not None:
            if not colleges:
                return {"byBatchStatus": by_status_out, "courseTotal": 0, "confirmedCount": 0,
                        "confirmRate": None, "absentCount": 0, "violationCount": 0,
                        "scope": {"blocked": scope.blocked}}
            cq = cq.where(AaExamCourse.college_id.in_(colleges))
        courses = db.scalars(cq).all()
        course_ids = [c.id for c in courses] or [-1]
        confirmed = sum(1 for c in courses if c.status == "CONFIRMED")
        incidents = db.scalars(select(AaExamIncident.incident_type).where(
            AaExamIncident.tenant_id == _tid(), AaExamIncident.status == "ACTIVE",
            AaExamIncident.exam_course_id.in_(course_ids))).all()
        absent = sum(1 for t in incidents if t == "ABSENT")
        violation = sum(1 for t in incidents if t == "DISCIPLINE_VIOLATION")
        return {"byBatchStatus": by_status_out, "courseTotal": len(courses), "confirmedCount": confirmed,
                "confirmRate": _rate(confirmed, len(courses)), "absentCount": absent,
                "violationCount": violation, "scope": {"blocked": scope.blocked}}


def exam_detail(user, term_id=None, college_id=None, incident_type=None,
               page=1, page_size=20) -> tuple[list[dict], int]:
    """考务统计下钻（09 号卡）：缺考/违纪学生明细（脱敏 + 审计，口径同 `_batch_stats_calc`
    ——课程级 REMOVED 排除 + incident.status=ACTIVE，不重复实现，仅改跨批次聚合范围）。"""
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident
    with session() as db:
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        bq = select(AaExamBatch.id).where(AaExamBatch.tenant_id == _tid(), AaExamBatch.is_deleted.is_(False))
        if term_id:
            bq = bq.where(AaExamBatch.term_id == int(term_id))
        batch_ids = db.scalars(bq).all() or [-1]
        colleges = _college_ids_scope(db, scope, college_id)
        course_q = select(AaExamCourse.id).where(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.is_deleted.is_(False),
            AaExamCourse.batch_id.in_(batch_ids), AaExamCourse.status != "REMOVED")
        if colleges is not None:
            if not colleges:
                return [], 0
            course_q = course_q.where(AaExamCourse.college_id.in_(colleges))
        course_ids = db.scalars(course_q).all() or [-1]
        q = select(AaExamIncident).where(
            AaExamIncident.tenant_id == _tid(), AaExamIncident.status == "ACTIVE",
            AaExamIncident.exam_course_id.in_(course_ids))
        if incident_type:
            q = q.where(AaExamIncident.incident_type == incident_type)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(AaExamIncident.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = [{"incidentId": str(i.id), "studentName": i.student_name or "",
                 "studentNo": _mask_id_card(i.student_no) if i.student_no else "",
                 "incidentType": i.incident_type} for i in rows]
        _audit(db, "STATS_DRILL_EXAM", f"考务异常明细 total={total} type={incident_type or '-'}")
        db.commit()
        return items, total


def resource_stats(user) -> dict:
    """教学资源统计聚合（14 号卡）：教室字典按状态/类型分布 + 教室预约按状态分布
    （校级共享资产，不做学院级收敛，见 `_i_resource` 注释）。"""
    from app.models import AaClassroom, AaClassroomBooking
    with session() as db:
        scope = _resolve_scope(user, db)
        if scope.blocked:
            return {"classroomTotal": 0, "byStatus": [], "byType": [], "bookingTotal": 0,
                    "byBookingStatus": [], "scope": {"blocked": True}}
        rooms = db.scalars(select(AaClassroom).where(
            AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False))).all()
        by_status: dict = {}
        by_type: dict = {}
        for c in rooms:
            by_status[c.status] = by_status.get(c.status, 0) + 1
            by_type[c.room_type] = by_type.get(c.room_type, 0) + 1
        bookings = db.scalars(select(AaClassroomBooking.status).where(
            AaClassroomBooking.tenant_id == _tid(), AaClassroomBooking.is_deleted.is_(False))).all()
        by_booking: dict = {}
        for s in bookings:
            by_booking[s] = by_booking.get(s, 0) + 1
        return {"classroomTotal": len(rooms),
                "byStatus": [{"key": k, "count": v} for k, v in by_status.items()],
                "byType": [{"key": k, "count": v} for k, v in by_type.items()],
                "bookingTotal": len(bookings),
                "byBookingStatus": [{"key": k, "count": v} for k, v in by_booking.items()],
                "scope": {"blocked": False}}


def resource_detail(user, page=1, page_size=20) -> tuple[list[dict], int]:
    """教学资源统计下钻（14 号卡）：待审核教室预约清单（操作导向、非学生级数据，无需脱敏/审计）。"""
    from app.models import AaClassroomBooking
    with session() as db:
        scope = _resolve_scope(user, db)
        if scope.blocked:
            return [], 0
        q = select(AaClassroomBooking).where(
            AaClassroomBooking.tenant_id == _tid(), AaClassroomBooking.is_deleted.is_(False),
            AaClassroomBooking.status == "PENDING")
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(AaClassroomBooking.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        items = [{"bookingId": str(b.id), "classroomText": b.classroom_text or "",
                 "bookingDate": b.booking_date, "slotNo": b.slot_no,
                 "applicantName": b.applicant_name or "", "purpose": b.purpose or "",
                 "status": b.status} for b in rows]
        return items, total


# ═══════════ 导出（xlsx + 水印 + 审计，同步下载；15 号卡「导出报表」domain 选择器） ═══════════

_EXPORT_DOMAINS = {
    "overview": "教务统计总览", "statusChange": "学籍统计", "registration": "注册统计",
    "course": "课程统计", "teachingTask": "教学任务统计", "schedule": "课表统计",
    "grade": "成绩统计", "warning": "学业预警统计", "graduation": "毕业资格统计",
    "workload": "教师工作量统计", "courseSelection": "选课统计", "exam": "考务统计",
    "resource": "教学资源统计",
}


def export_stats_xlsx(user, domain="overview", term_id=None, college_id=None, major_id=None,
                      purpose="") -> bytes:
    """15 号卡「导出报表」：按 domain 选择导出内容，统一水印+审计+xlsx（同步下载，非异步任务，
    见 15 号卡 §14/§8 施工前置核实项——项目既有 `t_export_task` 表当前未在本导出口接入，
    本轮沿用「教务总览」已验证的同步下载模式，未新建异步任务态，如实登记为与卡片设计的简化差异）。"""
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    domain = domain or "overview"
    if domain not in _EXPORT_DOMAINS:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", f"未知导出维度：{domain}")
    from app.services.xlsx_util import build_ledger_xlsx
    u = _cur_user()
    watermark = (f"导出人：{u.get('realName') or u.get('loginName') or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}")
    title = _EXPORT_DOMAINS[domain]
    if domain == "overview":
        data = overview(user, term_id, college_id, major_id)
        headers = ["指标", "分子", "分母", "比率(%)", "值", "状态"]
        rows = [[it["label"], it["numerator"], it["denominator"], it["rate"], it["value"], it["status"]]
                for it in data["indicators"]]
    elif domain == "statusChange":
        d = status_change_stats(user, term_id, college_id)
        headers = ["异动类型", "人数"]
        rows = [[g["key"], g["count"]] for g in d["byType"]]
    elif domain == "registration":
        d = registration_stats(user, term_id, college_id, major_id)
        headers = ["已注册", "应注册", "完成率(%)"]
        rows = [[d["registered"], d["expected"], d["rate"]]]
    elif domain == "course":
        d = course_stats(user, None, college_id)
        headers = ["类别", "启用课程数"]
        rows = [[g["key"], g["count"]] for g in d["byCategory"]]
    elif domain == "teachingTask":
        d = teaching_task_stats(user, college_id, term_id)
        headers = ["已确认", "应开", "完成率(%)"]
        rows = [[d["confirmed"], d["expected"], d["rate"]]]
    elif domain == "schedule":
        d = schedule_stats(user, college_id, term_id)
        headers = ["已发布", "总批次", "发布率(%)", "未解决冲突"]
        rows = [[d["published"], d["totalBatches"], d["publishedRate"], d["unresolvedConflicts"]]]
    elif domain == "grade":
        d = grade_stats(user, term_id, college_id)
        headers = ["挂科率(%)", "录入发布率(%)", "补考人数", "重修人数"]
        rows = [[d["failRate"], d["entryPublishRate"], d["makeupCount"], d["retakeCount"]]]
    elif domain == "warning":
        d = warning_stats(user, term_id, college_id)
        headers = ["维度", "分类", "数量"]
        rows = [["等级", g["key"], g["count"]] for g in d["byLevel"]] + \
               [["来源", g["key"], g["count"]] for g in d["bySource"]]
    elif domain == "graduation":
        d = graduation_stats(user, None, college_id)
        headers = ["通过率(%)", "通过人数", "应审人数"]
        rows = [[d["passRate"], d["passed"], d["expected"]]]
    elif domain == "courseSelection":
        d = course_selection_stats(user, term_id, college_id)
        headers = ["批次状态", "已选人次", "总容量", "填充率(%)", "低人数课程", "满额课程"]
        rows = [[g["key"], d["totalSelected"], d["totalCapacity"], d["fillRate"],
                 d["lowEnrollCount"], d["fullCount"]] for g in (d["byBatchStatus"] or [{"key": "-"}])]
    elif domain == "exam":
        d = exam_stats(user, term_id, college_id)
        headers = ["批次状态", "已确认课程", "课程总数", "确认率(%)", "缺考人次", "违纪人次"]
        rows = [[g["key"], d["confirmedCount"], d["courseTotal"], d["confirmRate"],
                 d["absentCount"], d["violationCount"]] for g in (d["byBatchStatus"] or [{"key": "-"}])]
    elif domain == "resource":
        d = resource_stats(user)
        headers = ["教室总数", "预约总数", "维度", "分类", "数量"]
        rows = [[d["classroomTotal"], d["bookingTotal"], "教室状态", g["key"], g["count"]]
                for g in d["byStatus"]] + \
               [[d["classroomTotal"], d["bookingTotal"], "预约状态", g["key"], g["count"]]
                for g in d["byBookingStatus"]]
    else:  # workload
        d = workload_stats(user, term_id, college_id)
        headers = ["教师", "学时合计", "任务数", "说明"]
        rows = [[r["teacherName"] or r["teacherKey"], r["totalHours"], r["taskCount"],
                 _WORKLOAD_DISCLAIMER] for r in d["ranking"]]
    content = build_ledger_xlsx(title, headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "STATS_EXPORT", f"{title} 导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content


def export_overview_xlsx(user, term_id=None, college_id=None, major_id=None, purpose="") -> bytes:
    """向后兼容包装：等价于 `export_stats_xlsx(domain='overview')`（既有路由/测试调用点不变）。"""
    return export_stats_xlsx(user, "overview", term_id, college_id, major_id, purpose)
