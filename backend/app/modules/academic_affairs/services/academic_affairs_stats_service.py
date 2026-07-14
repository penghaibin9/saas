"""13B 教务中心 · 教务统计（只读聚合）——11 项运行结果性指标 + 多维筛选 + 下钻明细。

设计来源（施工包 `docs/03-业务模块设计/教务中心/施工包/教务统计-生产级施工包.md` §9 / 融合设计 §4 口径已冻结）：
- 纯读侧：不新建表、不写业务表、无迁移（全部实时 count，`project_rule` D-02）。
- 数据范围：复用学工中心已验证的 `build_affairs_context`（不另造 scope 解析器，CLAUDE.md §5.3）。
  · 教务处口径角色（ACADEMIC_ADMIN / ACADEMIC_TEACHER，见 mock dataScope=SCHOOL 与 permissions.py `academicAffairs.*`）
    视为 TENANT_ALL（本校全量）——这两个角色码在 build_affairs_context 中未登记为 TENANT_ALL，
    故本域在 `_resolve_scope` 顶层按业务口径显式归类，**不修改共享 affairs_security 的角色集**（避免影响 R1 成绩审核 scope）。
  · COLLEGE_ADMIN / COLLEGE_SA → 复用 ctx.college_ids / allowed_class_ids（本院），未配 = fail-closed（空，绝不回退全校）。
  · 其它无授权角色 → NONE（fail-closed，指标全 0，传越权 collegeId → NO_DATA_SCOPE）。
- 4 项底层未建模块（调停课 / 选课 / 考务 / 教学资源）返回 MODULE_NOT_ENABLED 占位，不冒充数据（施工包 §1 更正、D-07）。
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

# 未建底层模块 → 占位（不冒充数据）
_MODULE_NOT_ENABLED = {"scheduleChange": "调停课模块未启用", "courseSelection": "选课管理模块未启用",
                       "exam": "考务管理模块未启用", "resource": "教学资源模块（P2）未启用"}


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
    from app.models import AcademicWarning
    q = select(AcademicWarning.level, func.count()).where(
        AcademicWarning.tenant_id == _tid(), AcademicWarning.record_status == "ACTIVE",
        AcademicWarning.status != "CLOSED")
    if acad_ids is not None:
        if not acad_ids:
            return _ind("warning", "学业预警数", value=0, drill="warning", groups=[])
        q = q.where(AcademicWarning.acad_student_id.in_(acad_ids))
    rows = db.execute(q.group_by(AcademicWarning.level)).all()
    groups = [{"key": r[0] or "UNKNOWN", "count": int(r[1])} for r in rows]
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


def _unknown(key: str, label: str, biz: str) -> dict:
    return _ind(key, label, status="MODULE_NOT_ENABLED", message=_MODULE_NOT_ENABLED[biz])


# ═══════════ 对外聚合入口 ═══════════

def overview(user: dict, term_id=None, college_id=None, major_id=None) -> dict:
    """教务总览：11 项已就绪指标 + 4 项 UNKNOWN 占位。"""
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
            _unknown("scheduleChange", "调停课统计", "scheduleChange"),
            _unknown("courseSelection", "选课统计", "courseSelection"),
            _unknown("exam", "考务统计", "exam"),
            _unknown("resource", "教学资源统计", "resource"),
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


# ═══════════ 导出（xlsx + 水印 + 审计，同步下载） ═══════════

def export_overview_xlsx(user, term_id=None, college_id=None, major_id=None, purpose="") -> bytes:
    """导出教务总览指标为 .xlsx（首行水印 + 审计）。"""
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx
    data = overview(user, term_id, college_id, major_id)
    u = _cur_user()
    watermark = (f"导出人：{u.get('realName') or u.get('loginName') or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}")
    headers = ["指标", "分子", "分母", "比率(%)", "值", "状态"]
    rows = []
    for it in data["indicators"]:
        rows.append([it["label"], it["numerator"], it["denominator"], it["rate"],
                     it["value"], it["status"]])
    content = build_ledger_xlsx("教务统计总览", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "STATS_EXPORT", f"教务总览导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content
