"""移动端·教师工作台聚合。以只读聚合为主，写操作仅 orientation_checkin（现场报到核验，需审计）。
严格租户过滤（绝不跨租户）。
范围收敛：组织范围读取 teacher_student_scope；实习等具有真实业务外键的场景优先按 user_id
精确匹配，姓名仅兼容尚未回填外键的历史数据。
复用 P7 六域真实 service，不重复造业务，也不暴露 PC 管理端全列表给前端。"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services import (academic_service, approval_service, campus_service_service,
                          orientation_service)
from app.modules.employment.services import employment_service
from app.modules.internship.services import internship_service
from app.modules.graduation.services import graduation_service
from app.services.db_service import _iso, _tid


def _ns(body):
    """移动端路由传入原始 dict；本模块复用的学工域服务函数按对象属性取值（body.xxx），此处做薄转换。"""
    return SimpleNamespace(**(body or {}))


def _session():
    return get_sessionmaker()()


# ══════════ 教师身份与范围判断（统一复用） ══════════

def is_teacher_user(user: dict | None) -> bool:
    u = user or {}
    return (u.get("userType") or "").upper() in ("TEACHER", "STAFF", "ADMIN")


def _require_teacher(user: dict | None):
    u = user or {}
    if (u.get("userType") or "").upper() == "STUDENT":
        raise AppException("NO_PERMISSION", "该接口仅教师端可用")
    return u


# 只有明确的校级业务管理角色可见全租户。学院管理员和普通教师必须继续按关系收敛。
_ADMIN_ROLES = {"SCHOOL_ADMIN", "ACADEMIC_ADMIN", "STUDENT_AFFAIRS_ADMIN",
                "GRADUATION_ADMIN", "LEADER", "SCHOOL_LEADER", "SECURITY_AUDITOR"}
_ADVISOR_ROLES = {"GD_MENTOR", "MENTOR", "INTERN_MENTOR", "INTERNSHIP_MENTOR"}
_RELATION_SCOPED_ROLES = {
    "COLLEGE_ADMIN", "ACADEMIC_TEACHER", "STUDENT_AFFAIRS", "COUNSELOR",
    "PSYCHOLOGY_TEACHER", "FUNDING_TEACHER", "DORM_MANAGER", "YOUTH_LEAGUE",
    "GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN", "GD_MENTOR", "GD_REVIEWER",
    "GD_DEFENSE_SECRETARY", "GD_DEFENSE_EXPERT", "INTERN_MENTOR",
    "INTERNSHIP_MENTOR", "EMPLOYMENT_TEACHER",
}


def resolve_teacher_scope(user: dict) -> dict:
    """解析教师数据范围（t_teacher_student_scope 最小可用版）：
    - 范围表行：CLASS(班级名) / COLLEGE(学院名) / STUDENT(学号) / ADVISOR(历史导师姓名，
      ref_value 可登记别名，用于历史数据导师姓名与账号姓名不一致的过渡映射)
    - 导师类角色默认叠加本人账号 ID；姓名只作历史数据兼容
    - 明确的校级管理角色 → ADMIN_TENANT（租户级）
    - 普通教师/学院角色无任何范围信息 → SCOPED 空范围（默认拒绝）"""
    u = user or {}
    role = (u.get("currentRoleCode") or "").upper()
    name = u.get("realName") or ""
    uid = str(u.get("userId") or "")
    db_uid = uid[3:] if uid.startswith("db-") else uid
    advisor_user_ids = {db_uid} if db_uid.isdigit() else set()
    scope = {"mode": "SCOPED", "by": "DEFAULT_DENY", "advisorName": name,
              "roleCode": role, "tenantId": _tid(),
              "classNames": set(), "studentNos": set(), "collegeNames": set(),
              "advisorNames": set(), "advisorUserIds": advisor_user_ids}
    if role in _ADMIN_ROLES:
        scope["mode"] = "ADMIN_TENANT"
        scope["by"] = "ADMIN"
        return scope
    if db_enabled():
        # 键派生：mock 用户 u_counselor01→counselor01；db 用户 activeContextId=ctx_<login_name>；
        # 姓名兜底（teacher_key 或 teacher_name 任一命中即生效）
        ctx = str(u.get("activeContextId") or "")
        keys = {k for k in (uid,
                            uid[2:] if uid.startswith("u_") else "",
                            ctx[4:] if ctx.startswith("ctx_") else "",
                            name) if k}
        try:
            with _session() as db:
                from app.models import TeacherStudentScope
                rows = db.scalars(select(TeacherStudentScope).where(
                    TeacherStudentScope.tenant_id == _tid(),
                    TeacherStudentScope.is_deleted.is_(False),
                    TeacherStudentScope.status == "ACTIVE",
                    (TeacherStudentScope.teacher_key.in_(keys)) |
                    (TeacherStudentScope.teacher_name.in_(keys)))).all()
        except Exception:  # noqa: BLE001 — 范围表缺失（旧库未迁移）时退回兜底，不 500
            rows = []
        for r in rows:
            if r.role_code and (r.role_code or "").upper() != role:
                continue
            st = (r.scope_type or "").upper()
            if st == "CLASS" and r.ref_value:
                scope["classNames"].add(r.ref_value.strip())
            elif st == "STUDENT" and r.ref_value:
                scope["studentNos"].add(r.ref_value.strip())
            elif st == "COLLEGE" and r.ref_value:
                scope["collegeNames"].add(r.ref_value.strip())
            elif st == "ADVISOR":
                scope["advisorNames"].add((r.ref_value or name).strip())
    if role in _ADVISOR_ROLES and name:
        scope["advisorNames"].add(name)
    if (scope["classNames"] or scope["studentNos"] or scope["collegeNames"]
            or scope["advisorNames"] or (role in _ADVISOR_ROLES and scope["advisorUserIds"])):
        scope["mode"] = "SCOPED"
        scope["by"] = ("BUSINESS_RELATION" if role in _ADVISOR_ROLES
                       and not (scope["classNames"] or scope["studentNos"] or scope["collegeNames"])
                       else "SCOPE_TABLE")
    elif role in _RELATION_SCOPED_ROLES:
        scope["by"] = "DEFAULT_DENY"
    return scope


def _class_match(scope: dict, class_name: str | None) -> bool:
    """班级名匹配（兼容「软件2301」与「软件2301班」两种写法）。"""
    cn = (class_name or "").strip()
    if not cn:
        return False
    variants = {cn, cn.rstrip("班"), cn + "班"}
    return bool(variants & scope["classNames"])


def scope_match_row(scope: dict, student_no=None, class_name=None, advisor_name=None,
                    college_name=None, advisor_user_id=None) -> bool:
    """判断一行学生相关数据是否在教师范围内（SCOPED 才收敛，其余模式恒通过）。"""
    if scope.get("mode") != "SCOPED":
        return True
    # 指导角色以业务分配关系为排他主边界。即使同一账号另有辅导员/学院身份，
    # 在当前指导角色下也不能借班级或学院范围看到其他导师负责的记录。
    if (scope.get("roleCode") or "").upper() in _ADVISOR_ROLES:
        if advisor_user_id not in (None, ""):
            return str(advisor_user_id) in scope.get("advisorUserIds", set())
        if advisor_name:
            return (advisor_name or "").strip() in scope["advisorNames"]
    if student_no and str(student_no).strip() in scope["studentNos"]:
        return True
    if _class_match(scope, class_name):
        return True
    if college_name and (college_name or "").strip() in scope["collegeNames"]:
        return True
    # 非指导角色不能借“本人恰好也是该记录导师”扩大当前角色范围；只有显式
    # ADVISOR 姓名范围用于兼容旧数据。指导角色的稳定账号关系已在上方排他判断。
    if advisor_name and (advisor_name or "").strip() in scope["advisorNames"]:
        return True
    return False


def can_teacher_view_student(user: dict, student, scope: dict | None = None, db=None) -> bool:
    """教师是否可查看某学生。硬边界：必须同租户；SCOPED 时按范围表/导师关系收敛。"""
    if student is None:
        return False
    if getattr(student, "tenant_id", None) != _tid():
        return False
    scope = scope or resolve_teacher_scope(user)
    if scope["mode"] != "SCOPED":
        return True
    no = getattr(student, "student_no", None)
    if no and str(no).strip() in scope["studentNos"]:
        return True
    if db is not None:
        # 班级 / 学院（学生主档 class_id → t_class）
        try:
            from app.models import College, SchoolClass
            if getattr(student, "class_id", None):
                cls = db.get(SchoolClass, student.class_id)
                if cls and _class_match(scope, cls.class_name):
                    return True
            college_id = getattr(student, "college_id", None)
            if not college_id and getattr(student, "major_id", None):
                from app.models import Major
                maj = db.get(Major, student.major_id)
                college_id = maj.college_id if maj else None
            if not college_id and getattr(student, "class_id", None):
                from app.models import Major
                cls = db.get(SchoolClass, student.class_id)
                if cls:
                    maj = db.get(Major, cls.major_id)
                    college_id = maj.college_id if maj else None
            if college_id and scope["collegeNames"]:
                col = db.get(College, college_id)
                if col and (col.college_name or "").strip() in scope["collegeNames"]:
                    return True
            # 各域冗余班级名（迎新/在校/学业/毕设/就业按姓名+学号冗余存班级）
            from app.models import AcademicStudent, CsServiceStudent, EmpStudent, GraduationStudent
            for model in (AcademicStudent, CsServiceStudent, EmpStudent, GraduationStudent):
                row = db.scalars(select(model).where(
                    model.tenant_id == _tid(), model.is_deleted.is_(False),
                    model.student_no == no)).first()
                if row and _class_match(scope, getattr(row, "class_name", None)):
                    return True
            # 导师关系（实习/毕设 advisor_name）
            if scope["advisorNames"]:
                from app.models import GraduationStudent as _GS, InternshipRecord as _IR
                ir = db.scalars(select(_IR).where(
                    _IR.tenant_id == _tid(), _IR.student_id == student.id,
                    _IR.is_deleted.is_(False))).first()
                if ir:
                    if ir.advisor_user_id not in (None, ""):
                        if str(ir.advisor_user_id) in scope.get("advisorUserIds", set()):
                            return True
                    elif (ir.advisor_name or "").strip() in scope["advisorNames"]:
                        return True
                gs = db.scalars(select(_GS).where(
                    _GS.tenant_id == _tid(), _GS.student_no == no,
                    _GS.is_deleted.is_(False))).first()
                if gs and (gs.advisor_name or "").strip() in scope["advisorNames"]:
                    return True
        except Exception:  # noqa: BLE001 — 关系判断异常时按无权限处理（拒绝优先）
            return False
    return False


def filter_students_for_teacher(user: dict, rows: list) -> list:
    """对学生行做范围过滤（同租户）。SCOPED 关系收敛在各域查询里做。"""
    return [r for r in rows if getattr(r, "tenant_id", None) == _tid()]


def _total(fn, **kw):
    try:
        _, total = fn(1, 1, **kw)
        return total
    except Exception:  # noqa: BLE001
        return 0


def _safe_list(fn, page, ps, **kw):
    try:
        rows, total = fn(page, ps, **kw)
        return rows, total
    except Exception:  # noqa: BLE001
        return [], 0


# ══════════ 工作台总览 / 待办 ══════════

def overview(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    pending_leave = _total(campus_service_service.list_leaves, status="PENDING_REVIEW")
    pending_grant = _total(campus_service_service.list_grants, status="REVIEWING")
    pending_wo = _total(campus_service_service.list_work_orders, status="PENDING_HANDLE")
    exc = _total(internship_service.list_attendance_exceptions, status="PENDING_HANDLE")
    reports = _total(internship_service.list_weekly_reports, status="PENDING_REVIEW")
    warn = _total(academic_service.list_warnings, status="PENDING_HANDLE")
    ori_exc = _total(orientation_service.list_exceptions, status="OPEN")
    gd_prop = _total(graduation_service.list_proposals, status="PENDING_REVIEW")
    unemployed = _total(employment_service.list_unemployed)
    return {
        "hasData": True, "role": u.get("currentRoleCode"), "scopeMode": scope["mode"],
        "updatedAt": _iso(datetime.now()),
        "metrics": [
            {"key": "leave", "label": "待审请假", "value": pending_leave, "route": "campus-service"},
            {"key": "grant", "label": "待审资助", "value": pending_grant, "route": "campus-service"},
            {"key": "report", "label": "待批周报", "value": reports, "route": "internship"},
            {"key": "checkin", "label": "打卡异常", "value": exc, "route": "internship"},
            {"key": "warning", "label": "学业预警待处理", "value": warn, "route": "academic"},
            {"key": "proposal", "label": "开题待审", "value": gd_prop, "route": "graduation"},
            {"key": "oriExc", "label": "迎新异常", "value": ori_exc, "route": "orientation"},
            {"key": "workorder", "label": "待处理工单", "value": pending_wo, "route": "campus-service"},
            {"key": "unemployed", "label": "未就业学生", "value": unemployed, "route": "employment"},
        ],
        "pendingTotal": pending_leave + pending_grant + reports + exc + warn + gd_prop + ori_exc + pending_wo,
    }


def todos(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "filters": [], "list": [], "total": 0, "pendingCount": 0,
                "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    items = []

    def add(fn, label, module, group, **kw):
        rows, _ = _safe_list(fn, 1, 20, **kw)
        for r in rows:
            if not scope_match_row(scope, student_no=r.get("studentNo"),
                                   class_name=r.get("className"),
                                   advisor_name=r.get("advisorName")):
                continue
            items.append({"id": r.get("id"), "group": group,
                          "title": f"{label}：{r.get('name') or r.get('studentName') or r.get('title', '')}",
                          "student": r.get("name") or r.get("studentName") or "",
                          "module": module, "status": r.get("status") or r.get("statusLabel", ""),
                          "level": "high" if r.get("riskLevel") in ("HIGH", "URGENT") else "normal",
                          "deadline": r.get("deadline") or r.get("dueAt") or ""})

    add(campus_service_service.list_leaves, "待审请假", "campus-service", "approve", status="PENDING_REVIEW")
    add(internship_service.list_weekly_reports, "待批周报", "internship", "review", status="PENDING_REVIEW")
    add(internship_service.list_attendance_exceptions, "打卡异常", "internship", "risk", status="PENDING_HANDLE")
    add(academic_service.list_warnings, "学业预警", "academic", "risk", status="PENDING_HANDLE")
    add(graduation_service.list_proposals, "开题待审", "graduation", "review", status="PENDING_REVIEW")
    filters = [{"key": "all", "label": "全部"}, {"key": "approve", "label": "待审批"},
               {"key": "review", "label": "待批阅"}, {"key": "risk", "label": "待处理风险"},
               {"key": "confirm", "label": "待确认"}, {"key": "done", "label": "已处理"}]
    return {"hasData": bool(items), "filters": filters, "list": items[:60],
            "total": len(items), "pendingCount": len(items), "scopeMode": scope["mode"]}


# ══════════ 风险学生（替代 PC /students 全列表） ══════════

def risk_students(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "list": [], "total": 0, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    tid = _tid()
    out = {}

    def _key(no, name):
        return (no or "") + "|" + (name or "")

    with _session() as db:
        from app.models import (AcademicStudent, AcademicWarning, CsServiceStudent, InternshipRecord,
                                StudentProfile)
        # 学业预警
        aw = db.execute(select(AcademicWarning, AcademicStudent).join(
            AcademicStudent, AcademicWarning.acad_student_id == AcademicStudent.id).where(
            AcademicWarning.tenant_id == tid, AcademicWarning.is_deleted.is_(False),
            AcademicWarning.record_status == "ACTIVE").order_by(AcademicWarning.id.desc()).limit(80)).all()
        for w, a in aw:
            k = _key(a.student_no, a.name)
            out.setdefault(k, {"name": a.name, "studentNo": a.student_no,
                               "className": a.class_name or "", "riskType": "学业预警",
                               "riskLevel": w.level or "MEDIUM", "latestTime": _iso(w.created_at),
                               "reason": w.reason or "学业预警", "tags": ["学业"]})
        # 实习风险
        ir = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == tid, InternshipRecord.is_deleted.is_(False),
            InternshipRecord.risk_level.in_(["HIGH", "MEDIUM"]))
            .order_by(InternshipRecord.id.desc()).limit(80)).all()
        sids = [r.student_id for r in ir if r.student_id]
        smap = {}
        if sids:
            smap = {s.id: s for s in db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tid, StudentProfile.id.in_(sids))).all()}
        for r in ir:
            s = smap.get(r.student_id)
            nm = s.real_name if s else (r.enterprise_name or "实习学生")
            no = s.student_no if s else ""
            k = _key(no, nm)
            row = out.setdefault(k, {"name": nm, "studentNo": no, "className": "",
                                     "riskType": "实习风险", "riskLevel": r.risk_level,
                                     "latestTime": _iso(r.updated_at), "reason": "实习风险信号",
                                     "tags": []})
            if "实习" not in row["tags"]:
                row["tags"].append("实习")
        # 在校服务高关注
        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == tid, CsServiceStudent.is_deleted.is_(False),
            CsServiceStudent.risk_level.in_(["HIGH", "MEDIUM"]))
            .order_by(CsServiceStudent.id.desc()).limit(80)).all()
        for c in cs:
            k = _key(c.student_no, c.name)
            row = out.setdefault(k, {"name": c.name, "studentNo": c.student_no or "",
                                     "className": c.class_name or "", "riskType": "重点关注",
                                     "riskLevel": c.risk_level, "latestTime": _iso(c.updated_at),
                                     "reason": "在校重点关注", "tags": []})
            if "在校" not in row["tags"]:
                row["tags"].append("在校")
    lst = list(out.values())
    # 范围收敛：SCOPED 教师只看自己负责的班级/学生/指导学生
    if scope["mode"] == "SCOPED":
        lst = [r for r in lst if scope_match_row(scope, student_no=r.get("studentNo"),
                                                 class_name=r.get("className"))]
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    lst.sort(key=lambda x: order.get(x.get("riskLevel"), 3))
    for i, r in enumerate(lst):
        r["id"] = "risk-" + str(i + 1)
        r["studentId"] = r.get("studentNo") or r["id"]
    return {"hasData": bool(lst), "list": lst, "total": len(lst), "scopeMode": scope["mode"]}


# ══════════ 我的班级 / 我的学生（辅导员/班主任按 t_class.counselor_id/head_teacher_id 收敛） ══════════

def _teacher_numeric_id(user: dict):
    """派生教师账号的数值 user_id（兼容 u_ 前缀），用于匹配 t_class.counselor_id/head_teacher_id。"""
    uid = str((user or {}).get("userId") or "")
    raw = uid[2:] if uid.startswith("u_") else uid
    return int(raw) if raw.isdigit() else None


def my_classes(user: dict) -> dict:
    """我的班级：本人担任辅导员/班主任的行政班列表 + 各班在校学生数。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "items": [], "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    tid = _tid()
    with _session() as db:
        from app.models import SchoolClass, StudentProfile
        conds = [SchoolClass.tenant_id == tid, SchoolClass.is_deleted.is_(False)]
        if scope["mode"] != "ADMIN_TENANT":
            numeric_uid = _teacher_numeric_id(u)
            if numeric_uid is None:
                return {"hasData": False, "items": [], "note": "未识别到教师身份，无法匹配班级"}
            conds.append(or_(SchoolClass.counselor_id == numeric_uid, SchoolClass.head_teacher_id == numeric_uid))
        rows = db.scalars(select(SchoolClass).where(*conds).order_by(SchoolClass.id.desc())).all()
        out = []
        for c in rows:
            cnt = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == tid, StudentProfile.class_id == c.id,
                StudentProfile.is_deleted.is_(False))) or 0
            out.append({"classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
                       "studentCount": cnt, "status": c.status})
        return {"hasData": bool(out), "items": out}


def my_students(user: dict, class_id=None) -> dict:
    """我的学生：本人负责班级的学生名单（可按 classId 下钻单班）；管理类角色不收敛(租户级)。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "items": [], "total": 0, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    tid = _tid()
    with _session() as db:
        from app.models import SchoolClass, StudentProfile
        conds = [StudentProfile.tenant_id == tid, StudentProfile.is_deleted.is_(False)]
        if class_id:
            conds.append(StudentProfile.class_id == int(class_id))
        elif scope["mode"] != "ADMIN_TENANT":
            numeric_uid = _teacher_numeric_id(u)
            if numeric_uid is None:
                return {"hasData": False, "items": [], "total": 0, "note": "未识别到教师身份，无法匹配班级"}
            class_ids = [c.id for c in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == tid, SchoolClass.is_deleted.is_(False),
                or_(SchoolClass.counselor_id == numeric_uid, SchoolClass.head_teacher_id == numeric_uid))).all()]
            if not class_ids:
                return {"hasData": False, "items": [], "total": 0, "note": "暂无负责班级"}
            conds.append(StudentProfile.class_id.in_(class_ids))
        rows = db.scalars(select(StudentProfile).where(*conds)
                          .order_by(StudentProfile.id.desc()).limit(200)).all()
        cls_map = {}
        cids = {r.class_id for r in rows if r.class_id}
        if cids:
            cls_map = {c.id: c.class_name for c in db.scalars(
                select(SchoolClass).where(SchoolClass.id.in_(cids))).all()}
        out = [{"studentId": str(r.id), "studentNo": r.student_no, "name": r.real_name,
               "className": cls_map.get(r.class_id, ""), "gender": r.gender or "",
               "stage": r.current_stage, "status": r.student_status} for r in rows]
        return {"hasData": bool(out), "items": out, "total": len(out)}


# ══════════ 家校联系（移动端包装：辅导员登记联系记录 + 登记家长回执。
# 学工域范围口径独立于 resolve_teacher_scope，统一走 _allowed_class_ids/build_affairs_context，
# 与 affairs_talk_service._scope_or_403 强制使用同一口径，避免"选得到、提交却 403"的错位）══════════

def affairs_family_contact_students(user: dict) -> dict:
    """家校联系·可登记学生名单（与 create_contact 内部 _scope_or_403 同一范围口径）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.models import SchoolClass, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with _session() as db:
        allowed, _scope = _allowed_class_ids(db, u)
        if allowed is not None and not allowed:
            return {"list": [], "total": 0}
        conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed))
        rows = db.scalars(select(StudentProfile).where(*conds)
                          .order_by(StudentProfile.id.desc()).limit(200)).all()
        cids = {r.class_id for r in rows if r.class_id}
        cls_map = {c.id: c.class_name for c in db.scalars(
            select(SchoolClass).where(SchoolClass.id.in_(cids))).all()} if cids else {}
        items = [{"studentId": str(r.id), "studentNo": r.student_no, "name": r.real_name,
                  "className": cls_map.get(r.class_id, "")} for r in rows]
        return {"list": items, "total": len(items)}


def affairs_family_contact_list(user: dict, receipt_status: str | None = None) -> dict:
    """家校联系·全局记录列表（数据范围过滤，不含号码本体，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_talk_service as talk_svc
    items, total = talk_svc.list_all_contacts(u, receipt_status, 1, 50)
    return {"list": items, "total": total}


def affairs_family_contact_create(user: dict, student_id: str, body: dict) -> dict:
    """家校联系·登记（owner+范围校验在服务层完成，查看完整号码须填≥5字原因并触发敏感审计）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.api.v1.student_affairs import ContactCreate
    from app.services import affairs_talk_service as talk_svc
    b = body or {}
    payload = ContactCreate(contactType=b.get("contactType") or "PHONE", reason=b.get("reason") or "",
                            result=b.get("result") or "", fullPhoneView=bool(b.get("fullPhoneView")),
                            viewReason=b.get("viewReason") or "")
    result = talk_svc.create_contact(student_id, u, payload)
    _audit_write("MOBILE_FAMILY_CONTACT_CREATE", f"family-contact:{result.get('contactId')}",
                 {"operator": u.get("realName"), "studentId": str(student_id)})
    return result


def affairs_family_contact_receipt(user: dict, contact_id: str, note: str | None = None) -> dict:
    """家校联系·登记家长回执（PENDING→RECEIVED，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_talk_service as talk_svc
    result = talk_svc.mark_receipt(contact_id, u, note or "")
    _audit_write("MOBILE_FAMILY_CONTACT_RECEIPT", f"family-contact:{contact_id}",
                 {"operator": u.get("realName")})
    return result


# ══════════ 学工请假审批（移动端包装：辅导员多级审批链核心操作 + 销假闭环 + 逾期处置 + 续假审批。
# 数据范围+审批节点身份校验均在服务层 _scope_or_403/_check_review_node 完成，直接复用 PC 侧
# affairs_leave_service（节点越权缺口已在服务层修复，见 _check_review_node/_node_visible）。══════════

def affairs_leave_pending(user: dict) -> dict:
    """请假待审批队列（本人数据范围+审批节点双重收敛，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_leave_service as leave_svc
    items, total = leave_svc.list_pending(u, 1, 50)
    return {"list": items, "total": total}


def affairs_leave_followup(user: dict) -> dict:
    """请假后续处理台账（已通过/续假审批中/待销假确认/逾期，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_leave_service as leave_svc
    items, total = leave_svc.list_leaves(u, followup_only=True, page=1, page_size=50)
    return {"list": items, "total": total}


def affairs_leave_detail(user: dict, leave_id: str) -> dict:
    """请假详情（含销假/续假/审计留痕，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实数据")
    from app.services import affairs_leave_service as leave_svc
    return leave_svc.get_detail(leave_id, u)


def affairs_leave_approve(user: dict, leave_id: str, comment: str | None = None) -> dict:
    """请假审批通过（owner+审批节点身份校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.approve(leave_id, u, comment or "")
    _audit_write("MOBILE_AFFAIRS_LEAVE_APPROVE", f"affairs-leave:{leave_id}", {"operator": u.get("realName")})
    return result


def affairs_leave_reject(user: dict, leave_id: str, reason: str) -> dict:
    """请假驳回（原因≥5字，owner+审批节点身份校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.reject(leave_id, u, reason)
    _audit_write("MOBILE_AFFAIRS_LEAVE_REJECT", f"affairs-leave:{leave_id}",
                 {"operator": u.get("realName"), "reason": (reason or "")[:200]})
    return result


def affairs_leave_return(user: dict, leave_id: str, reason: str) -> dict:
    """请假退回重提（原因≥5字，owner+审批节点身份校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.return_leave(leave_id, u, reason)
    _audit_write("MOBILE_AFFAIRS_LEAVE_RETURN", f"affairs-leave:{leave_id}",
                 {"operator": u.get("realName"), "reason": (reason or "")[:200]})
    return result


def affairs_leave_cancel_confirm(user: dict, leave_id: str, action: str,
                                 actual_return_at: str | None = None,
                                 reason: str | None = None, note: str | None = None) -> dict:
    """销假确认(CONFIRM)/退回(RETURN)，owner 校验在服务层完成。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.confirm_cancel(leave_id, u, action=action, actual_return_at=actual_return_at,
                                      reason=reason or "", note=note or "")
    _audit_write("MOBILE_AFFAIRS_LEAVE_CANCEL_CONFIRM", f"affairs-leave:{leave_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


def affairs_leave_proxy_cancel(user: dict, leave_id: str, actual_return_at: str,
                               note: str | None = None) -> dict:
    """代登记销假（学生无法自行操作时，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.proxy_cancel(leave_id, u, actual_return_at, note or "")
    _audit_write("MOBILE_AFFAIRS_LEAVE_PROXY_CANCEL", f"affairs-leave:{leave_id}",
                 {"operator": u.get("realName")})
    return result


def affairs_leave_overdue_handle(user: dict, leave_id: str, handle_type: str, note: str) -> dict:
    """逾期处置登记（CONTACT/TO_HOME_SCHOOL/CLOSE，说明≥5字，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.handle_overdue(leave_id, u, handle_type, note)
    _audit_write("MOBILE_AFFAIRS_LEAVE_OVERDUE_HANDLE", f"affairs-leave:{leave_id}",
                 {"operator": u.get("realName"), "handleType": handle_type})
    return result


def affairs_leave_extension_approve(user: dict, leave_id: str, action: str = "APPROVE",
                                    reason: str | None = None) -> dict:
    """续假审批(APPROVE/REJECT)，owner 校验在服务层完成。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_leave_service as leave_svc
    result = leave_svc.approve_extension(leave_id, u, action=action, reason=reason or "")
    _audit_write("MOBILE_AFFAIRS_LEAVE_EXTENSION_APPROVE", f"affairs-leave:{leave_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


# ══════════ 学工待办处置（困难/奖助/处分/风险）——复用 PC 服务层权限+范围+指派人校验 ══════════

def _uid_int(user) -> int:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _filter_by_assignee_todos(user, items, *, id_keys: tuple[str, ...], todo_types: tuple[str, ...]) -> list:
    """与 teacher_affairs 待办卡同一口径：指派人 + 学院池0；班级范围另含本班学生池化待办。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import StudentProfile, UnifiedTodo
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.db_service import session as _db_session

    if not items:
        return []
    with _db_session() as db:
        ctx = build_affairs_context(user, db)
        uid = _uid_int(user)
        conds = [
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.todo_type.in_(list(todo_types)),
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        ]
        if ctx.scope_type == "TENANT_ALL":
            rows = db.scalars(select(UnifiedTodo).where(*conds)).all()
        elif ctx.scope_type == "COLLEGE":
            rows = db.scalars(select(UnifiedTodo).where(
                *conds,
                or_(UnifiedTodo.assignee_id == uid, UnifiedTodo.assignee_id == 0) if uid
                else UnifiedTodo.assignee_id == 0)).all()
        else:
            allowed, _ = _allowed_class_ids(db, user)
            if allowed is None:
                rows = db.scalars(select(UnifiedTodo).where(*conds)).all()
            elif not allowed:
                rows = []
            else:
                stu_ids = list(db.scalars(select(StudentProfile.id).where(
                    StudentProfile.tenant_id == _tid(),
                    StudentProfile.class_id.in_(list(allowed)),
                    StudentProfile.is_deleted.is_(False))).all())
                pool = and_(UnifiedTodo.assignee_id == 0,
                            UnifiedTodo.student_id.in_(stu_ids)) if stu_ids else False
                if uid:
                    rows = db.scalars(select(UnifiedTodo).where(
                        *conds, or_(UnifiedTodo.assignee_id == uid, pool))).all()
                elif stu_ids:
                    rows = db.scalars(select(UnifiedTodo).where(*conds, pool)).all()
                else:
                    rows = []
        allowed_ids = {int(r.source_biz_id) for r in rows if r.source_biz_id}

    def _biz_id(row: dict) -> int:
        for k in id_keys:
            v = row.get(k)
            if v is None or v == "":
                continue
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        return 0

    return [x for x in items if _biz_id(x) in allowed_ids]


def affairs_aid_pending(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_aid_service as svc
    items, _ = svc.list_applications(u, page=1, page_size=100)
    nodes = {"CLASS_REVIEW", "COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW", "ADJUST_REVIEW"}
    out = [x for x in items if (x.get("status") or "") in nodes]
    out = _filter_by_assignee_todos(
        u, out, id_keys=("applyId", "id"), todo_types=("AID_APPROVAL", "AID_ADJUST"))
    return {"list": out, "total": len(out)}


def affairs_aid_detail(user: dict, apply_id: str) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实数据")
    from app.services import affairs_aid_service as svc
    return svc.get_application(apply_id, u)


def affairs_aid_review(user: dict, apply_id: str, action: str, reason: str = "",
                       level: str | None = None) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_aid_service as svc
    act = (action or "APPROVE").upper()
    detail = svc.get_application(apply_id, u)
    if (detail or {}).get("status") == "ADJUST_REVIEW":
        if act == "RETURN":
            raise AppException("VALIDATION_ERROR", "困难等级调整不支持退回，请选择通过或驳回")
        mapped = "APPROVE" if act in ("APPROVE", "ADJUST_APPROVE") else "REJECT"
        result = svc.approve_adjust(apply_id, u, action=mapped)
    else:
        result = svc.review(apply_id, u, act, level=level, reason=reason or "")
    _audit_write("MOBILE_AFFAIRS_AID_REVIEW", f"aid:{apply_id}",
                 {"operator": u.get("realName"), "action": act})
    return result


def affairs_funding_pending(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_funding_service as svc
    items, _ = svc.list_applications(u, page=1, page_size=100)
    nodes = {"COUNSELOR_REVIEW", "COLLEGE_REVIEW", "SCHOOL_REVIEW"}
    out = [x for x in items if (x.get("status") or "") in nodes]
    out = _filter_by_assignee_todos(
        u, out, id_keys=("applicationId", "appId", "id"), todo_types=("FUNDING_APPROVAL",))
    return {"list": out, "total": len(out)}


def affairs_funding_detail(user: dict, app_id: str) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实数据")
    from app.services import affairs_funding_service as svc
    return svc.get_application(app_id, u)


def affairs_funding_review(user: dict, app_id: str, action: str, reason: str = "") -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_funding_service as svc
    result = svc.review(app_id, u, (action or "APPROVE").upper(), reason=reason or "")
    _audit_write("MOBILE_AFFAIRS_FUNDING_REVIEW", f"funding:{app_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


def affairs_discipline_pending(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_discipline_service as svc
    items, _ = svc.list_cases(u, page=1, page_size=100)
    nodes = {"COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW", "SCHOOL_REVIEW", "REMOVE_REVIEW"}
    out = [x for x in items if (x.get("status") or "") in nodes]
    out = _filter_by_assignee_todos(
        u, out, id_keys=("caseId", "id"),
        todo_types=("DISCIPLINE_APPROVAL", "DISCIPLINE_REMOVE"))
    return {"list": out, "total": len(out)}


def affairs_discipline_detail(user: dict, case_id: str) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实数据")
    from app.services import affairs_discipline_service as svc
    return svc.get_case(case_id, u)


def affairs_discipline_review(user: dict, case_id: str, action: str, reason: str = "") -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_discipline_service as svc
    act = (action or "APPROVE").upper()
    detail = svc.get_case(case_id, u)
    if (detail or {}).get("status") == "REMOVE_REVIEW":
        result = svc.review_remove(case_id, u, act, reason=reason or "")
    else:
        result = svc.review(case_id, u, act, reason=reason or "")
    _audit_write("MOBILE_AFFAIRS_DISC_REVIEW", f"discipline:{case_id}",
                 {"operator": u.get("realName"), "action": act})
    return result


def affairs_risk_pending(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_risk_service as svc
    items = []
    for st in ("ASSIGNED", "PROCESSING", "FOLLOWING", "ESCALATED"):
        chunk, _ = svc.list_risks(u, status=st, page=1, page_size=50)
        items.extend(chunk)
    # 与待办卡 RISK_HANDLE 对齐：先按 UnifiedTodo 指派人收敛；无待办时回退本人 owner
    filtered = _filter_by_assignee_todos(
        u, items, id_keys=("riskId", "id"), todo_types=("RISK_HANDLE",))
    if filtered:
        return {"list": filtered, "total": len(filtered)}
    from app.core.affairs_security import build_affairs_context
    from app.services.db_service import session as _db_session
    with _db_session() as db:
        ctx = build_affairs_context(u, db)
    uid = _uid_int(u)
    if ctx.scope_type != "TENANT_ALL" and uid:
        items = [x for x in items if int(x.get("ownerId") or 0) == uid]
    return {"list": items, "total": len(items)}


def affairs_risk_detail(user: dict, risk_id: str) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实数据")
    from app.services import affairs_risk_service as svc
    return svc.get_risk(risk_id, u)


def affairs_risk_process(user: dict, risk_id: str, content: str) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_risk_service as svc
    result = svc.process(risk_id, u, content=content or "")
    _audit_write("MOBILE_AFFAIRS_RISK_PROCESS", f"risk:{risk_id}", {"operator": u.get("realName")})
    return result


def affairs_risk_close(user: dict, risk_id: str, conclusion: str) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_risk_service as svc
    result = svc.close(risk_id, u, conclusion=conclusion or "")
    _audit_write("MOBILE_AFFAIRS_RISK_CLOSE", f"risk:{risk_id}", {"operator": u.get("realName")})
    return result


# ══════════ 班干部任命/免去（移动端包装：复用 affairs_dashboard_service 全套，owner+范围校验
# 在服务层 _class_in_scope_or_403 完成。学生选择器刻意"先选班级再查该班学生"而不是借用
# /teacher/my-students —— 后者走 resolve_teacher_scope+counselor_id 数字外键，与本模块
# _allowed_class_ids/build_affairs_context 是不同的范围体系，混用会出现"选得到、任命却403"
# 的错位（同此前家校联系模块踩过的坑）。══════════

def affairs_my_classes(user: dict) -> dict:
    """我的班级（本人数据范围内），供任命班干部时先选班级。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_dashboard_service as dash
    items = dash.list_classes(u)
    return {"list": items, "total": len(items)}


def affairs_class_students(user: dict, class_id: str) -> dict:
    """班级学生名单（先校验班级在调用者范围内，再查询该班学生，供任命班干部选人）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from sqlalchemy import select as _select

    from app.models import StudentProfile
    from app.services import affairs_dashboard_service as dash
    with _session() as db:
        dash._class_in_scope_or_403(db, class_id, u)
        rows = db.scalars(_select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.class_id == int(class_id),
            StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id)).all()
        items = [{"studentId": str(r.id), "studentNo": r.student_no or "", "name": r.real_name}
                 for r in rows]
        return {"list": items, "total": len(items)}


def affairs_cadre_list(user: dict, class_id: str) -> dict:
    """在任班干部名单（owner+范围校验+在任状态过滤均在服务层 list_cadres 完成，
    移动端只附加学生姓名/学号补全展示）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.models import StudentProfile
    from app.services import affairs_dashboard_service as dash
    items = list(dash.list_cadres(class_id, u))
    with _session() as db:
        for it in items:
            s = db.get(StudentProfile, int(it["studentId"])) if it.get("studentId") else None
            it["studentName"] = s.real_name if s else ""
            it["studentNo"] = s.student_no if s else ""
    return {"list": items, "total": len(items)}


def affairs_cadre_appoint(user: dict, class_id: str, body: dict) -> dict:
    """任命班干部（同班级同职务在任重复→409，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.api.v1.student_affairs import CadreCreate
    from app.services import affairs_dashboard_service as dash
    b = body or {}
    payload = CadreCreate(studentId=str(b.get("studentId") or ""), position=b.get("position") or "",
                          termCode=b.get("termCode"))
    result = dash.add_cadre(class_id, payload, u)
    _audit_write("MOBILE_CADRE_APPOINT", f"class-cadre:{result.get('cadreId')}",
                 {"operator": u.get("realName"), "classId": str(class_id), "position": payload.position})
    return result


def affairs_cadre_remove(user: dict, cadre_id: str, reason: str | None = None) -> dict:
    """免去班干部（owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_dashboard_service as dash
    result = dash.remove_cadre(cadre_id, u, reason or "")
    _audit_write("MOBILE_CADRE_REMOVE", f"class-cadre:{cadre_id}", {"operator": u.get("realName")})
    return result


# ══════════ 班级材料（辅导员本班范围内查看/新增/作废，owner+范围校验在服务层
# affairs_class_service 完成；COUNSELOR 权限矩阵本就含 studentAffairs.class.create，
# PC 端无权限缺口，此处仅补移动端入口） ══════════

def affairs_class_materials(user: dict, class_id: str, material_type: str | None = None) -> dict:
    """班级材料列表（在任 ACTIVE 材料，范围校验在服务层 _class_in_scope_or_403 完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.services import affairs_class_service as cls
    items, total = cls.list_materials(class_id, u, material_type, page=1, page_size=200)
    return {"list": items, "total": total}


def affairs_class_material_add(user: dict, class_id: str, body: dict) -> dict:
    """新增班级材料（类型/标题必填，范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_class_service as cls
    b = body or {}
    payload = _ns({
        "materialType": b.get("materialType") or "OTHER", "title": b.get("title") or "",
        "fileId": b.get("fileId"), "fileName": b.get("fileName"),
        "materialAt": b.get("materialAt"), "remark": b.get("remark"),
    })
    result = cls.add_material(class_id, u, payload)
    _audit_write("MOBILE_CLASS_MATERIAL_ADD", f"class-material:{result.get('id')}",
                 {"operator": u.get("realName"), "classId": str(class_id), "title": payload.title})
    return result


def affairs_class_material_void(user: dict, material_id: str, reason: str | None = None) -> dict:
    """作废班级材料（owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.services import affairs_class_service as cls
    result = cls.void_material(material_id, u, reason or "")
    _audit_write("MOBILE_CLASS_MATERIAL_VOID", f"class-material:{material_id}",
                 {"operator": u.get("realName")})
    return result


# ══════════ 教务·教师任务确认（直接复用 academic_affairs_task_service，该函数已按
# teacher_key 自校验归属，管理角色代管豁免；list 用 mine=True 收敛为本人任务） ══════════

def affairs_academic_my_tasks(user: dict, status: str | None = None) -> dict:
    """我的教学任务（仅本人 teacher_key 命中的任务，PENDING_ASSIGN/ASSIGNED 等各状态均可查看）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.academic_affairs.services import academic_affairs_task_service as task_svc
    items, total = task_svc.list_all_tasks(u, status=status, mine=True, page=1, page_size=200)
    return {"list": items, "total": total}


def affairs_academic_task_act(user: dict, task_id: str, action: str, reason: str | None = None) -> dict:
    """确认/退回教学任务（归属校验在服务层 _check_teacher_scope 完成，退回原因≥5字同 PC 口径）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_task_service as task_svc
    result = task_svc.teacher_act(task_id, u, action, reason or "")
    _audit_write("MOBILE_ACADEMIC_TASK_ACT", f"academic-task:{task_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


# ══════════ 教务·发起调停课（直接复用 academic_affairs_schedule_change_service，
# submit/cancel/conflict_check/list_changes 均已按 teacher_key/COLLEGE 自校验；
# get_change PC 端本身无归属校验，移动端补一道校验，不改 PC） ══════════

def affairs_academic_my_schedule(user: dict, term_id: str | None = None, week: int | None = None) -> dict:
    """我的课表（供选择「原课位」发起调停课）。self_key 与 `_teacher_key`/`_user_keys` 同口径
    （优先去 u_ 前缀的 userId，再 loginName），避免「教师我的课表」与「调停课选课位」两套 key。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"items": [], "batchId": None, "weeklyHours": 0, "note": ""}
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched_svc
    uid = str(u.get("userId") or "")
    # 与 mobile_academic_affairs_service._teacher_key / grade._user_keys 对齐：优先去 u_ 前缀的 userId，
    # 再尝试 loginName，避免「我的课表」与「调停课原课位」各用一套 key 导致一边有课一边空白。
    from app.modules.academic_affairs.services.mobile_academic_affairs_service import _teacher_key
    self_key = _teacher_key(u) or u.get("loginName") or (uid[2:] if uid.startswith("u_") else uid)
    return sched_svc.teacher_schedule(u, self_key, term_id, week)


def affairs_academic_schedule_conflict_check(user: dict, body: dict) -> dict:
    """目标课位冲突预检（只读，归属校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"conflict": None}
    from app.modules.academic_affairs.services import academic_affairs_schedule_change_service as chg_svc
    return chg_svc.conflict_check(_ns(body), u)


def affairs_academic_schedule_submit(user: dict, body: dict) -> dict:
    """发起调停课（调课/停课/补课），提交即冲突预检，归属校验在服务层完成。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_schedule_change_service as chg_svc
    result = chg_svc.submit(_ns(body), u)
    _audit_write("MOBILE_ACADEMIC_SCHEDULE_SUBMIT", f"schedule-change:{result.get('changeId')}",
                 {"operator": u.get("realName"), "changeType": result.get("changeType")})
    return result


def affairs_academic_schedule_cancel(user: dict, change_id: str, reason: str | None = None) -> dict:
    """撤销调停课申请（终审前，归属校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_schedule_change_service as chg_svc
    result = chg_svc.cancel(change_id, u, reason or "")
    _audit_write("MOBILE_ACADEMIC_SCHEDULE_CANCEL", f"schedule-change:{change_id}",
                 {"operator": u.get("realName")})
    return result


def affairs_academic_schedule_changes(user: dict, status: str | None = None) -> dict:
    """我的调停课申请列表（list_changes 内部已按 teacher_key/COLLEGE 自校验范围）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.academic_affairs.services import academic_affairs_schedule_change_service as chg_svc
    items, total = chg_svc.list_changes(u, status=status, page=1, page_size=100)
    return {"list": items, "total": total}


def affairs_academic_schedule_change_detail(user: dict, change_id: str) -> dict:
    """调停课单详情（归属校验已在服务层 get_change 完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_schedule_change_service as chg_svc
    return chg_svc.get_change(change_id, u)


# ══════════ 缓考审批（辅导员初审 + 任课教师确认两个节点身份，复用同一 defer_review；
# PC 端 defer_list 本身对非学生模式无范围过滤（返回全校数据），不能直接复用，
# 仿答辩评委 judge_pending() 写法：按当前身份对应节点先圈定候选状态集合，
# 再逐条复用 PC 端 _check_defer_scope 同款范围判断，只留下真正轮到本人审批的） ══════════

_DEFER_NODE_STATUS_BY_ROLE = {"COUNSELOR": "COUNSELOR_REVIEW", "ACADEMIC_TEACHER": "TEACHER_CONFIRM"}


def affairs_academic_defer_pending(user: dict) -> dict:
    """缓考待我审批（覆盖 COUNSELOR/ACADEMIC_TEACHER 两个节点身份，其余身份返回空列表）。
    defer_list(status=node_status) 已在服务层按真实业务关系过滤（_visible_defer_record），
    对某一具体节点状态而言与「当前是否轮到我审批」等价，不需要再逐条复核。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    role = (u.get("currentRoleCode") or "").upper()
    node_status = _DEFER_NODE_STATUS_BY_ROLE.get(role)
    if not node_status:
        return {"list": [], "total": 0}
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    items, total = exam_svc.defer_list(u, status=node_status, page=1, page_size=500)
    return {"list": items, "total": total}


def affairs_academic_defer_review(user: dict, defer_id: str, action: str, reason: str | None = None) -> dict:
    """缓考审批动作（APPROVE 推进/RETURN 退回/REJECT 驳回），节点角色+范围校验在服务层
    _check_defer_scope 完成（辅导员限本人所带班级/任课教师限本人授课）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_exam_service as exam_svc
    result = exam_svc.defer_review(u, defer_id, action, reason or "")
    _audit_write("MOBILE_ACADEMIC_DEFER_REVIEW", f"defer:{defer_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


# ══════════ 教务·教学评价（自评/同行/督导 + 我的结果 + 申诉，直接复用
# academic_affairs_evaluation_service 的 list_my_role_tasks/submit_evaluation/list_results
# ——均已按 evaluator_key/teacher_key 自校验；submit_appeal PC 端未校验 result 归属，
# 移动端在此补一道校验，不改 PC） ══════════

def affairs_academic_evaluation_open_batches(user: dict) -> dict:
    """评教窗口列表（status 可选，缺省返回全部；仅批次元信息，非敏感数据，PC 端本身也不做
    调用者范围收敛，教师需要看到有哪些窗口在开放/已出结果）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as eval_svc
    status = None
    items, total = eval_svc.list_batches(u, status=status, page=1, page_size=100)
    return {"list": items, "total": total}


def affairs_academic_evaluation_my_tasks(user: dict, evaluator_type: str, batch_id: str | None = None) -> dict:
    """我的评价任务（自评/同行/督导，按 evaluator_key 命中当前登录身份，PC 端已自校验）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as eval_svc
    items = eval_svc.list_my_role_tasks(u, evaluator_type, batch_id)
    return {"list": items, "total": len(items)}


def affairs_academic_evaluation_submit(user: dict, task_id: str, answers: dict | None,
                                       objective_score: float | None, comment: str | None = None) -> dict:
    """提交评价（评价人归属+重复提交校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as eval_svc
    result = eval_svc.submit_evaluation(u, int(task_id), answers, objective_score, comment)
    _audit_write("MOBILE_ACADEMIC_EVAL_SUBMIT", f"eval-task:{task_id}", {"operator": u.get("realName")})
    return result


def affairs_academic_evaluation_my_results(user: dict) -> dict:
    """我的评价结果（跨批次聚合，PC 端 list_results 按单个 batchId 查询，没有「全部我的结果」入口，
    此处仿答辩评委/缓考待审模式新写聚合：遍历已出结果的批次，逐批复用 PC list_results(mine=True)
    的自校验取本人已发布结果，不重复实现范围逻辑）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as eval_svc
    batches, _bt = eval_svc.list_batches(u, status=None, page=1, page_size=200)
    items = []
    for b in batches:
        if b["status"] not in ("RESULT_READY", "ARCHIVED"):
            continue
        rows, _t = eval_svc.list_results(u, int(b["batchId"]), mine=True, page=1, page_size=200)
        for r in rows:
            r["batchId"] = b["batchId"]
            r["batchName"] = b["batchName"]
        items.extend(rows)
    return {"list": items, "total": len(items)}


def affairs_academic_evaluation_submit_appeal(user: dict, result_id: str, reason: str) -> dict:
    """结果申诉（归属校验已在服务层 submit_appeal 完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as eval_svc
    result = eval_svc.submit_appeal(u, result_id, reason)
    _audit_write("MOBILE_ACADEMIC_EVAL_APPEAL", f"eval-result:{result_id}", {"operator": u.get("realName")})
    return result


# ══════════ 数据看板（移动端包装，直接复用既有 affairs_dashboard_service.get_dashboard，
# 该函数已按数据范围收敛且指标全部真实聚合，零改造） ══════════

def dashboard(user: dict) -> dict:
    _require_teacher(user)
    from app.services import affairs_dashboard_service as dash
    return dash.get_dashboard(user)


# ══════════ 通知发布（移动端首创：教师发通知给学生，按班级/学院/全校，真实写 t_unified_message） ══════════

def notify_publish(user: dict, body: dict) -> dict:
    """教师/管理员发布通知：CLASS 范围任何教师限本人负责班级；COLLEGE/SCHOOL 范围仅管理类角色。
    接收人解析为 StudentProfile.id 写入 receiver_id，与全仓库既有 UnifiedMessage 写入惯例一致
    （见 academic_affairs_grade_service.py/internship_service.py 等既有调用点）。"""
    _require_teacher(user)
    b = body or {}
    title = (b.get("title") or "").strip()
    content = (b.get("content") or "").strip()
    scope_type = (b.get("scopeType") or "").upper()
    if not title:
        raise AppException("VALIDATION_ERROR", "标题必填")
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "内容必填且不少于 5 字")
    if scope_type not in ("CLASS", "COLLEGE", "SCHOOL"):
        raise AppException("VALIDATION_ERROR", "接收范围非法")
    role = (user.get("currentRoleCode") or "").upper()
    is_admin = role in _ADMIN_ROLES
    if scope_type in ("COLLEGE", "SCHOOL") and not is_admin:
        raise AppException("NO_PERMISSION", "仅管理类角色可发布学院/全校范围通知")
    with _session() as db:
        from app.models import SchoolClass, StudentProfile, UnifiedMessage
        tid = _tid()
        conds = [StudentProfile.tenant_id == tid, StudentProfile.is_deleted.is_(False)]
        if scope_type == "CLASS":
            class_id = b.get("classId")
            if not class_id:
                raise AppException("VALIDATION_ERROR", "班级ID必填")
            if not is_admin:
                numeric_uid = _teacher_numeric_id(user)
                cls = db.get(SchoolClass, int(class_id))
                if (not cls or cls.tenant_id != tid or cls.is_deleted or
                        (cls.counselor_id != numeric_uid and cls.head_teacher_id != numeric_uid)):
                    raise AppException("NO_DATA_SCOPE", "该班级不在您的负责范围内")
            conds.append(StudentProfile.class_id == int(class_id))
        elif scope_type == "COLLEGE":
            college_id = b.get("collegeId")
            if not college_id:
                raise AppException("VALIDATION_ERROR", "学院ID必填")
            conds.append(StudentProfile.college_id == int(college_id))
        rows = db.scalars(select(StudentProfile).where(*conds)).all()
        if not rows:
            raise AppException("VALIDATION_ERROR", "该范围内暂无学生，未发布")
        for s in rows:
            db.add(UnifiedMessage(tenant_id=tid, receiver_id=s.id, source_module="teacher-notice",
                                  title=title, content=content, status="UNREAD"))
        db.commit()
        return {"recipientCount": len(rows), "title": title}


# ══════════ 消息通知设置（移动端首创，真实过滤 messages() 聚合） ══════════

def notify_preferences(user: dict) -> dict:
    _require_teacher(user)
    from app.services import notification_preference_service as notify_pref
    return notify_pref.get_preferences(user, notify_pref.TEACHER_CATEGORIES)


def notify_set_preference(user: dict, body: dict) -> dict:
    _require_teacher(user)
    from app.services import notification_preference_service as notify_pref
    b = body or {}
    valid_keys = {c["key"] for c in notify_pref.TEACHER_CATEGORIES}
    if b.get("key") not in valid_keys:
        raise AppException("VALIDATION_ERROR", "未知通知分类")
    return notify_pref.set_preference(user, b.get("key"), bool(b.get("enabled")))


# ══════════ 谈心谈话（移动端包装，复用既有 affairs_talk_service，不新增遮蔽/范围逻辑） ══════════

def talk_list(user: dict, talk_type=None, status=None, student_id=None, page=1, page_size=20) -> dict:
    _require_teacher(user)
    from app.services import affairs_talk_service as talk
    items, total = talk.list_talks(user, talk_type=talk_type, status=status,
                                   student_id=student_id, page=page, page_size=page_size)
    return {"items": items, "total": total}


def talk_detail(user: dict, talk_id) -> dict:
    _require_teacher(user)
    from app.services import affairs_talk_service as talk
    return talk.get_talk(talk_id, user)


def talk_create(user: dict, body: dict) -> dict:
    """建谈话计划：talkType/studentIds/topic 必填（底层按对象属性直接取值，此处先校验避免 AttributeError）。"""
    _require_teacher(user)
    b = body or {}
    if not b.get("talkType"):
        raise AppException("VALIDATION_ERROR", "谈话类型必填")
    if not b.get("studentIds"):
        raise AppException("VALIDATION_ERROR", "至少选择一名学生")
    if not b.get("topic"):
        raise AppException("VALIDATION_ERROR", "谈话主题必填")
    from app.services import affairs_talk_service as talk
    return talk.create_talk(_ns(b), user)


def talk_record(user: dict, talk_id, body: dict) -> dict:
    _require_teacher(user)  # 纵深防御：与同族 talk_* 一致显式收口非教师（底层 _scope_or_403 仍在）
    from app.services import affairs_talk_service as talk
    b = body or {}
    return talk.record_talk(talk_id, user, b.get("content"), b.get("result", ""), bool(b.get("needFollow")))


def talk_follow_up(user: dict, talk_id, body: dict) -> dict:
    _require_teacher(user)  # 纵深防御：与同族 talk_* 一致显式收口非教师（底层 _scope_or_403 仍在）
    from app.services import affairs_talk_service as talk
    b = body or {}
    return talk.follow_up(talk_id, user, b.get("action"), b.get("content", ""))


def talk_stats(user: dict, group_by="TYPE") -> dict:
    _require_teacher(user)
    from app.services import affairs_talk_service as talk
    return talk.talk_stats(user, group_by)


# ══════════ 心理关注（移动端包装，严格保留既有"列表恒遮蔽+详情需授权角色+原因≥5字"红线） ══════════

def mental_list(user: dict, level=None, page=1, page_size=20) -> dict:
    _require_teacher(user)
    from app.services import affairs_mental_service as mental
    items, total = mental.list_attention(user, level=level, page=page, page_size=page_size)
    return {"items": items, "total": total}


def mental_detail(user: dict, ref_id, reason=None) -> dict:
    _require_teacher(user)
    from app.services import affairs_mental_service as mental
    return mental.get_referral(user, ref_id, reason=reason)


def mental_create(user: dict, body: dict) -> dict:
    _require_teacher(user)
    b = body or {}
    if not b.get("studentId"):
        raise AppException("VALIDATION_ERROR", "studentId 必填")
    if not b.get("reasonSummary") or len(str(b["reasonSummary"]).strip()) < 5:
        raise AppException("VALIDATION_ERROR", "转介事由摘要必填且不少于 5 字")
    from app.services import affairs_mental_service as mental
    return mental.create_referral(user, _ns(b))


def mental_follow(user: dict, ref_id, body: dict) -> dict:
    _require_teacher(user)
    from app.services import affairs_mental_service as mental
    return mental.follow_referral(user, ref_id, (body or {}).get("content", ""))


def mental_escalate(user: dict, ref_id, body: dict) -> dict:
    _require_teacher(user)
    from app.services import affairs_mental_service as mental
    return mental.escalate_crisis(user, ref_id, (body or {}).get("content", ""))


def mental_close(user: dict, ref_id, body: dict) -> dict:
    _require_teacher(user)
    from app.services import affairs_mental_service as mental
    return mental.close_referral(user, ref_id, (body or {}).get("conclusion", ""))


def mental_stats(user: dict) -> dict:
    _require_teacher(user)
    from app.services import affairs_mental_service as mental
    return mental.stats(user)


# ══════════ 学生 360 轻量详情（替代 PC /students/{id}，含权限判断） ══════════

def student_detail(user: dict, student_id) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "note": "演示模式"}
    tid = _tid()
    with _session() as db:
        from app.models import (AcademicStudent, AcademicWarning, EmpStudent, GraduationStudent,
                                InternshipRecord, StudentProfile, StudentStageEvent)
        try:
            sid = int(student_id)
        except (TypeError, ValueError):
            sid = None
        stu = None
        if sid is not None:
            stu = db.get(StudentProfile, sid)
            # 跨租户按"不存在"处理，不泄露其它租户学生是否存在
            if stu is not None and stu.tenant_id != tid:
                stu = None
        if stu is None:
            # 兼容传学号（严格本租户）
            stu = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tid, StudentProfile.student_no == str(student_id),
                StudentProfile.is_deleted.is_(False))).first()
        if stu is None or stu.is_deleted:
            raise AppException("DATA_NOT_FOUND", "学生不存在")
        # 同租户内的更细范围（班级/学号/指导关系）越权 → 403
        scope = resolve_teacher_scope(u)
        if not can_teacher_view_student(u, stu, scope=scope, db=db):
            from app.services import audit_log
            audit_log.record("TEACHER_SCOPE_DENIED", f"mobile/teacher/student/{student_id}",
                             detail={"studentNo": stu.student_no}, result="DENIED")
            raise AppException("NO_PERMISSION", "该学生不在你的负责范围内")
        name, no = stu.real_name, stu.student_no
        # 学业
        a = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == tid, AcademicStudent.name == name,
            AcademicStudent.is_deleted.is_(False))).first()
        warn_cnt = 0
        if a:
            warn_cnt = db.scalar(select(func.count()).select_from(AcademicWarning).where(
                AcademicWarning.tenant_id == tid, AcademicWarning.acad_student_id == a.id,
                AcademicWarning.record_status == "ACTIVE", AcademicWarning.is_deleted.is_(False))) or 0
        intern = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == tid, InternshipRecord.student_id == stu.id,
            InternshipRecord.is_deleted.is_(False))).first()
        gd = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == tid, GraduationStudent.name == name,
            GraduationStudent.is_deleted.is_(False))).first()
        emp = db.scalars(select(EmpStudent).where(
            EmpStudent.tenant_id == tid, EmpStudent.name == name,
            EmpStudent.is_deleted.is_(False))).first()
        events = db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.tenant_id == tid, StudentStageEvent.student_id == stu.id
        ).order_by(StudentStageEvent.id.desc()).limit(10)).all()
        pending = []
        if warn_cnt:
            pending.append({"title": "学业预警待跟进", "action": "查看学业"})
        if intern and intern.risk_level in ("HIGH", "MEDIUM"):
            pending.append({"title": "实习风险待处理", "action": "查看实习"})
        return {
            "hasData": True,
            # base 不含身份证/手机/家庭地址明文
            "base": {"name": name, "studentNo": no, "className": stu.grade or "",
                     "stage": stu.current_stage, "status": stu.student_status},
            "risk": {"level": "HIGH" if warn_cnt or (intern and intern.risk_level == "HIGH") else "LOW",
                     "warningCount": warn_cnt,
                     "internRisk": intern.risk_level if intern else "NONE"},
            "lifecycle": [{"stage": e.to_stage, "time": _iso(e.occurred_at),
                           "reason": e.reason or ""} for e in events],
            "pendingItems": pending,
            "internshipSummary": {"hasData": bool(intern),
                                  "enterprise": intern.enterprise_name if intern else "",
                                  "position": intern.position_name if intern else "",
                                  "status": intern.status if intern else "NONE"},
            "academicSummary": {"hasData": bool(a), "gpa": float(a.gpa or 0) if a else 0,
                                "warningCount": warn_cnt,
                                "academicStatus": a.academic_status if a else "NONE"},
            "graduationSummary": {"hasData": bool(gd), "topic": gd.topic_title if gd else "",
                                  "stage": gd.stage if gd else "NONE"},
            "employmentSummary": {"hasData": bool(emp),
                                  "destinationType": emp.destination_type if emp else "NONE",
                                  "verifyStatus": emp.verify_status if emp else "NONE"},
        }


# ══════════ 六域教师页（真实结构，租户过滤 + scopeMode） ══════════

def _advisor_map(ids: list) -> dict:
    """internship_id → advisor_name（一次查询，供范围过滤）。"""
    if not ids:
        return {}
    try:
        with _session() as db:
            from app.models import InternshipRecord
            rows = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.id.in_(ids))).all()
            return {r.id: (r.advisor_name or "") for r in rows}
    except Exception:  # noqa: BLE001
        return {}


def internship(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "weeklyReports": [], "abnormalCheckins": [], "stats": {}}
    scope = resolve_teacher_scope(u)
    reports, rtotal = _safe_list(internship_service.list_weekly_reports, 1, 50, status="PENDING_REVIEW")
    overdue, ototal = _safe_list(internship_service.list_weekly_reports, 1, 50, status="OVERDUE")
    excs, etotal = _safe_list(internship_service.list_attendance_exceptions, 1, 50, status="PENDING_HANDLE")
    # 合并待批阅与逾期未交（去重 id）
    seen = {str(r.get("id")) for r in reports}
    for r in overdue:
        if str(r.get("id")) not in seen:
            reports.append(r)
            seen.add(str(r.get("id")))
    rtotal = len(reports)
    # 范围收敛：列表里只保留自己能处理的（看得见 = 批得了），与写操作范围一致
    if scope["mode"] == "SCOPED":
        adv = _advisor_map([int(r.get("internId") or 0) for r in reports] +
                           [int(e.get("internId") or e.get("internshipId") or 0) for e in excs])
        reports = [r for r in reports if scope_match_row(
            scope, class_name=r.get("className"), advisor_name=adv.get(int(r.get("internId") or 0)),
            student_no=r.get("studentNo"))]
        excs = [e for e in excs if scope_match_row(
            scope, class_name=e.get("className"),
            advisor_name=adv.get(int(e.get("internId") or e.get("internshipId") or 0)),
            student_no=e.get("studentNo"))]
        rtotal, etotal = len(reports), len(excs)
    stats = {}
    try:
        stats = internship_service.get_dashboard_summary()
    except Exception:  # noqa: BLE001
        stats = {"pendingReports": rtotal, "abnormal": etotal}
    return {"hasData": (rtotal + etotal) > 0, "weeklyReports": reports,
            "abnormalCheckins": excs, "stats": stats, "scopeMode": scope["mode"]}


def graduation(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "students": [], "reviewDetail": [], "stats": {}}
    scope = resolve_teacher_scope(u)
    students, stotal = _safe_list(graduation_service.list_students, 1, 50)
    proposals, ptotal = _safe_list(graduation_service.list_proposals, 1, 50, status="PENDING_REVIEW")
    finals, ftotal = _safe_list(graduation_service.list_finals, 1, 50, status="PENDING_REVIEW")
    # SCOPED：严格按范围收敛（导师姓名/别名、班级、学号），不再"过滤为空就放全量"
    if scope["mode"] == "SCOPED":
        students = [s for s in students if scope_match_row(
            scope, advisor_name=s.get("advisorName") or s.get("mentor"),
            class_name=s.get("className"), student_no=s.get("studentNo"))]
        proposals = [p for p in proposals if scope_match_row(
            scope, advisor_name=p.get("advisorName"),
            class_name=p.get("className"), student_no=p.get("studentNo"))]
        finals = [f for f in finals if scope_match_row(
            scope, advisor_name=f.get("advisorName"), class_name=f.get("className"))]
        stotal, ptotal, ftotal = len(students), len(proposals), len(finals)
    stats = {}
    try:
        stats = graduation_service.get_dashboard()
    except Exception:  # noqa: BLE001
        stats = {"pendingProposals": ptotal}
    return {"hasData": (stotal + ptotal + ftotal) > 0, "students": students, "reviewDetail": proposals,
            "finalDetail": finals, "stats": stats, "scopeMode": scope["mode"]}


def employment(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "stats": {}, "tabs": [], "students": [], "jobPool": []}
    scope = resolve_teacher_scope(u)
    students, stotal = _safe_list(employment_service.list_students, 1, 50)
    jobs, _ = _safe_list(employment_service.list_jobs, 1, 30)
    if scope["mode"] == "SCOPED":
        students = [s for s in students if scope_match_row(
            scope, class_name=s.get("className"), student_no=s.get("studentNo"))]
        stotal = len(students)
    stats = {}
    try:
        stats = employment_service.get_dashboard()
    except Exception:  # noqa: BLE001
        stats = {"total": stotal}
    tabs = [{"key": "unemployed", "label": "未就业"}, {"key": "following", "label": "跟进中"},
            {"key": "verify", "label": "待核验"}, {"key": "done", "label": "已落实"}]
    return {"hasData": stotal > 0, "stats": stats, "tabs": tabs, "students": students,
            "jobPool": jobs, "scopeMode": scope["mode"]}


# ══════════ 就业老师·转交学生（保守设计，designSource=ai_proposal）══════════
# 背景：employment_service 全模块无调用者范围收敛，employment_teacher 是自由文本字段，
# 无 FK 无强类型「学生归属哪个就业老师」关系可复用。为在无更好锚点下取最小安全实现，
# 移动端只允许调用者转交「当前 employmentTeacher 字段精确等于调用者本人 realName」的学生
# （即"我负责的学生我可以转给别人"），不允许调剂任意学生；新老师名自由文本录入（PC 端本身
# 也是自由文本）。局限：依赖 realName 精确字符串匹配，同名教师会误判——若学校有员工工号
# 体系应改用该体系重构。该口径是否等同学校"就业老师互相调剂"的实际业务需用户确认。

def affairs_employment_my_students(user: dict) -> dict:
    """我负责的就业学生（employmentTeacher 字段 == 本人 realName），供转交前选人。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    my_name = (u.get("realName") or "").strip()
    if not my_name:
        return {"list": [], "total": 0}
    students, _ = _safe_list(employment_service.list_students, 1, 500)
    mine = [s for s in students if (s.get("employmentTeacher") or "").strip() == my_name]
    return {"list": mine, "total": len(mine)}


def affairs_employment_transfer_student(user: dict, student_id: str, new_teacher: str) -> dict:
    """把本人负责的学生转交给另一位就业老师。仅当目标学生当前 employment_teacher == 本人
    realName 时放行（保守设计，见上）；否则 403。新老师名自由文本。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    new_teacher = (new_teacher or "").strip()
    if not new_teacher:
        raise AppException("VALIDATION_ERROR", "接收就业老师姓名必填")
    my_name = (u.get("realName") or "").strip()
    detail = employment_service.get_student_detail(student_id)
    # get_student_detail 返回 {"student": {...}, "materials": ...}，归属字段在 student 子对象里，
    # 不能读顶层 detail["employmentTeacher"]（恒 None 会导致本人学生也被误判 403）。
    owner = ((detail.get("student") or {}).get("employmentTeacher") or "").strip()
    if not my_name or owner != my_name:
        raise AppException("NO_DATA_SCOPE", "只能转交当前由本人负责的学生")
    result = employment_service.assign_teacher([student_id], new_teacher)
    _audit_write("MOBILE_EMPLOYMENT_TRANSFER", f"emp-student:{student_id}",
                 {"operator": my_name, "newTeacher": new_teacher})
    return result


# ══════════ 就业·企业/岗位库（校级共享主数据，employment_service 已有 CRUD 但无 router 暴露，
# 移动端首次对外接入。门禁在 mobile.py 路由层用 employment.company/job.view/manage，靠
# employment.* 通配放行就业老师/校管、挡其他身份。service 层已校验必填/停用原因≥5字/级联，
# 此处仅包装 + 审计。注意 list_* 返回元组 (items,total)，create_*/disable_* 不接 operator 参数） ══════════

def affairs_employment_companies(user: dict, status: str | None = None) -> dict:
    """企业列表（校级共享，前 200 条 + 状态过滤）。"""
    _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    items, total = employment_service.list_companies(1, 200, status=status)
    return {"list": items, "total": total}


def affairs_employment_company_create(user: dict, body: dict) -> dict:
    """新增企业（name+creditCode 必填，缺失由 service 抛 VALIDATION_ERROR）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    result = employment_service.create_company(body or {})
    _audit_write("MOBILE_EMPLOYMENT_COMPANY_CREATE", f"emp-company:{result.get('id')}",
                 {"operator": u.get("realName"), "name": (body or {}).get("name")})
    return result


def affairs_employment_company_disable(user: dict, company_id: str, reason: str | None = None) -> dict:
    """停用企业（原因≥5字，级联关闭岗位；校验与级联都在 service 层）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    result = employment_service.disable_company(company_id, reason or "")
    _audit_write("MOBILE_EMPLOYMENT_COMPANY_DISABLE", f"emp-company:{company_id}",
                 {"operator": u.get("realName")})
    return result


def affairs_employment_jobs(user: dict, company_id: str | None = None, status: str | None = None) -> dict:
    """岗位列表（可按企业/状态过滤）。"""
    _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    items, total = employment_service.list_jobs(1, 200, status=status, company_id=company_id)
    return {"list": items, "total": total}


def affairs_employment_job_create(user: dict, body: dict) -> dict:
    """新增岗位（companyId+title 必填，缺失由 service 抛 VALIDATION_ERROR）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    result = employment_service.create_job(body or {})
    _audit_write("MOBILE_EMPLOYMENT_JOB_CREATE", f"emp-job:{result.get('id')}",
                 {"operator": u.get("realName"), "title": (body or {}).get("title")})
    return result


def affairs_employment_job_disable(user: dict, job_id: str, reason: str | None = None) -> dict:
    """停用岗位（原因≥5字，校验在 service 层）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    result = employment_service.disable_job(job_id, reason or "")
    _audit_write("MOBILE_EMPLOYMENT_JOB_DISABLE", f"emp-job:{job_id}",
                 {"operator": u.get("realName")})
    return result


# 保留原迎新/在校/学业待处理列表（工作台跳转用）
def _domain(fn, module, user, **kw):
    _require_teacher(user)
    if not db_enabled():
        return {"list": [], "note": "演示模式"}
    rows, total = _safe_list(fn, 1, 50, **kw)
    return {"hasData": total > 0, "list": rows, "total": total, "module": module}


def orientation(user):
    return _domain(orientation_service.list_exceptions, "orientation", user, status="OPEN")


def orientation_checkin(user: dict, admission_no: str) -> dict:
    """现场报到核验（迎新老师扫码/录入报到码）：写操作，需审计。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持核验")
    result = orientation_service.teacher_checkin_by_admission_no(admission_no, u.get("realName") or "")
    from app.services import audit_log
    audit_log.record("迎新现场报到核验", f"orientation-student:{result['id']}",
                     detail={"operator": u.get("realName"), "student": result.get("name")})
    return result


def orientation_dashboard(user: dict) -> dict:
    """迎新看板（移动版·迎新老师查看）：报到 KPI + 未报到学生列表。只读，复用 PC 端看板与列表查询。"""
    _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "kpis": [], "notReported": []}
    d = orientation_service.get_dashboard()
    items, total = orientation_service.list_students(1, 30, report_status="NOT_REPORTED")
    return {"hasData": True, "batchName": d.get("batchName"), "batchPeriod": d.get("batchPeriod"),
            "kpis": d.get("kpis", []), "notReported": items, "notReportedTotal": total}


def orientation_today_checkins(user: dict) -> dict:
    """今日已核验（现场报到）新生列表——供核验页下方展示，供教师核对不重复核验。"""
    _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "list": []}
    from app.models import OrientationStudent
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with _session() as db:
        rows = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.is_deleted.is_(False),
            OrientationStudent.checkin_time.is_not(None),
            OrientationStudent.checkin_time >= today_start,
        ).order_by(OrientationStudent.checkin_time.desc())).all()
        items = [{"id": str(r.id), "name": r.name, "className": r.class_name or "",
                  "checkinTime": _iso(r.checkin_time)} for r in rows]
        return {"hasData": len(items) > 0, "list": items, "total": len(items)}


def internship_visit_plans(user: dict) -> dict:
    """指导巡访（移动版）：复用 PC 端巡访计划查询（owner 范围收敛），按学生拆分展示，
    标记本月是否已巡访（存在本月 InternshipVisit 记录）。"""
    _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "plans": []}
    import re as _re

    from app.models import InternshipRecord, InternshipVisit, StudentProfile
    from app.modules.internship.services import internship_visit_plan_service as plan_svc
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    items, _total = plan_svc.list_visit_plans(1, 50, user=user)
    plans = [p for p in items if p.get("status") in ("PUBLISHED", "IN_PROGRESS")]
    with _session() as db:
        # 批量消嵌套 N+1：先把所有计划的学生姓名一次解析，再批量取实习记录与本月巡访。
        plan_names = [[n.strip() for n in _re.split(r"[,，、;；\n]", p.get("studentScope") or "")
                       if n.strip()] for p in plans]
        all_names = {n for ns in plan_names for n in ns}
        by_name: dict[str, object] = {}
        if all_names:
            for s in db.scalars(select(StudentProfile).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                    StudentProfile.real_name.in_(all_names)).order_by(StudentProfile.id)):
                by_name.setdefault(s.real_name, s)
        sids = [s.id for s in by_name.values()]
        rec_by_sid: dict[int, object] = {}
        if sids:
            for rec in db.scalars(select(InternshipRecord).where(
                    InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id.in_(sids),
                    InternshipRecord.is_deleted.is_(False)).order_by(InternshipRecord.id)):
                rec_by_sid.setdefault(rec.student_id, rec)
        rec_ids = [rec.id for rec in rec_by_sid.values()]
        visited_ids: set = set()
        if rec_ids:
            for v in db.scalars(select(InternshipVisit).where(
                    InternshipVisit.tenant_id == _tid(), InternshipVisit.internship_id.in_(rec_ids),
                    InternshipVisit.visit_at >= month_start, InternshipVisit.is_deleted.is_(False))):
                visited_ids.add(v.internship_id)
        out = []
        for p, names in zip(plans, plan_names):
            students = []
            for name in names:
                stu = by_name.get(name)
                rec = rec_by_sid.get(stu.id) if stu is not None else None
                rec_id = str(rec.id) if rec else None
                students.append({"name": name, "internshipId": rec_id,
                                 "visited": bool(rec and rec.id in visited_ids),
                                 "resolvable": rec_id is not None})
            out.append({"id": p["id"], "enterpriseName": p.get("enterpriseName") or "",
                       "planDate": p.get("planDate") or "", "location": p.get("location") or "",
                       "students": students})
        return {"hasData": len(out) > 0, "plans": out}


def internship_visit_record(user: dict, internship_id: str) -> dict:
    """记录巡访（移动版·快速记录，不含企业/学生反馈正文）：复用 PC 端巡访创建（owner 范围校验+审计）。"""
    _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持记录巡访")
    if not internship_id:
        raise AppException("VALIDATION_ERROR", "缺少实习记录标识")
    from app.modules.internship.services import internship_visit_service
    return internship_visit_service.create(user, {"internshipId": internship_id, "method": "ONSITE"})


def campus(user):
    return _domain(campus_service_service.list_leaves, "campus-service", user, status="PENDING_REVIEW")


def academic(user):
    return _domain(academic_service.list_warnings, "academic", user, status="PENDING_HANDLE")


# ══════════ 教师消息（租户范围/系统消息，轻量生成） ══════════

def messages(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "unreadCount": 0, "tabs": [], "groups": {}}
    scope = resolve_teacher_scope(u)

    def _in_scope(r):
        return scope_match_row(scope, student_no=r.get("studentNo"),
                               class_name=r.get("className"),
                               advisor_name=r.get("advisorName"))
    system_msgs, dynamic_msgs, risk_msgs = [], [], []
    # 学生动态：待批周报 / 开题
    reports, _ = _safe_list(internship_service.list_weekly_reports, 1, 15, status="PENDING_REVIEW")
    for r in filter(_in_scope, reports):
        dynamic_msgs.append({"id": "dyn-wr-" + str(r.get("id")),
                             "title": f"{r.get('name') or r.get('studentName') or '学生'} 提交了实习周报",
                             "module": "岗位实习", "level": "normal", "read": False})
    props, _ = _safe_list(graduation_service.list_proposals, 1, 15, status="PENDING_REVIEW")
    for p in filter(_in_scope, props):
        dynamic_msgs.append({"id": "dyn-gp-" + str(p.get("id")),
                             "title": f"{p.get('name') or p.get('studentName') or '学生'} 提交了开题材料",
                             "module": "毕业设计", "level": "normal", "read": False})
    # 风险预警：打卡异常 / 学业预警
    excs, _ = _safe_list(internship_service.list_attendance_exceptions, 1, 15, status="PENDING_HANDLE")
    for e in filter(_in_scope, excs):
        risk_msgs.append({"id": "risk-ck-" + str(e.get("id")),
                          "title": f"{e.get('name') or e.get('studentName') or '学生'} 打卡异常",
                          "module": "风险预警", "level": "high", "read": False})
    warns, _ = _safe_list(academic_service.list_warnings, 1, 15, status="PENDING_HANDLE")
    for w in filter(_in_scope, warns):
        risk_msgs.append({"id": "risk-aw-" + str(w.get("id")),
                          "title": f"{w.get('name') or w.get('studentName') or '学生'} 学业预警",
                          "module": "风险预警", "level": "high", "read": False})
    system_msgs.append({"id": "sys-1", "title": "本周待办已汇总，请及时处理",
                        "module": "系统通知", "level": "normal", "read": False})
    groups_all = {"system": system_msgs, "dynamic": dynamic_msgs, "risk": risk_msgs}
    from app.services import notification_preference_service as notify_pref
    on = notify_pref.enabled_categories(user, list(groups_all.keys()))
    groups = {k: (v if k in on else []) for k, v in groups_all.items()}
    tabs = [{"key": "system", "label": "系统通知", "badge": len([x for x in groups["system"] if not x["read"]])},
            {"key": "dynamic", "label": "学生动态", "badge": len([x for x in groups["dynamic"] if not x["read"]])},
            {"key": "risk", "label": "风险预警", "badge": len([x for x in groups["risk"] if not x["read"]])}]
    unread = sum(len(v) for v in groups.values())
    return {"hasData": unread > 0, "unreadCount": unread, "tabs": tabs, "groups": groups}


# ══════════ 教师审批列表（复用审批服务，mobile 轻量） ══════════

def _filter_approvals_by_scope(scope: dict, rows: list) -> list:
    """SCOPED 教师的审批列表按申请人（学生）范围收敛：
    按 applicantName 在本租户学生主档内解析，再复用 can_teacher_view_student。
    解析不到申请人的任务（非学生发起/历史数据）保守隐藏。"""
    if scope.get("mode") != "SCOPED" or not rows:
        return rows
    out = []
    try:
        with _session() as db:
            from app.models import StudentProfile
            # 批量解析全部申请人姓名 → 学生主档（一次 IN 查询替代逐行全表扫描，消 N+1）。
            # 同名取 id 最小者，与原 .first() 默认顺序一致；可见性判定仍逐个走 can_teacher_view_student。
            names = {(r.get("applicantName") or "").strip() for r in rows
                     if (r.get("applicantName") or "").strip()}
            by_name: dict[str, object] = {}
            if names:
                for s in db.scalars(select(StudentProfile).where(
                        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                        StudentProfile.real_name.in_(names)).order_by(StudentProfile.id)):
                    by_name.setdefault(s.real_name, s)
            for r in rows:
                stu = by_name.get((r.get("applicantName") or "").strip())
                if stu is not None and can_teacher_view_student({}, stu, scope=scope, db=db):
                    out.append(r)
    except Exception:  # noqa: BLE001 — 收敛异常时宁可少展示，不越权
        return []
    return out


def approvals(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "approvals": [], "filters": [], "pendingCount": 0}
    scope = resolve_teacher_scope(u)
    rows, total = _safe_list(approval_service.list_tasks, 1, 50, status="PENDING")
    rows = _filter_approvals_by_scope(scope, rows)
    total = len(rows) if scope.get("mode") == "SCOPED" else total
    filters = [{"key": "pending", "label": "待处理"}, {"key": "done", "label": "已处理"}]
    return {"hasData": total > 0, "approvals": rows, "filters": filters,
            "pendingCount": total, "scopeMode": scope["mode"]}


# ══════════ 教师写操作（mobile 包装：教师校验 + 范围校验 + 审计 + 冲突 409） ══════════

def _audit_write(action: str, resource: str, detail: dict):
    from app.services import audit_log
    audit_log.record(action, resource, detail=detail)


def _assert_task_in_scope(u: dict, task_id: str):
    """审批任务范围校验：任务必须在本租户（服务层已保证），SCOPED 教师须能看到申请人。"""
    scope = resolve_teacher_scope(u)
    if scope.get("mode") != "SCOPED":
        return
    try:
        row = approval_service.get_task(task_id)
    except Exception:
        return  # 不存在 → 交由后续动作返回 404
    if not _filter_approvals_by_scope(scope, [row]):
        raise AppException("NO_PERMISSION", "该审批不在你的负责范围内")


def approval_act(user: dict, task_id: str, action: str, reason: str | None = None) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实审批")
    _assert_task_in_scope(u, task_id)
    if action == "approve":
        result = approval_service.approve(task_id, reason or "")
    elif action == "reject":
        result = approval_service.reject(task_id, reason or "")
    else:
        raise AppException("VALIDATION_ERROR", "action 必须是 approve/reject")
    _audit_write("MOBILE_APPROVAL_" + action.upper(), f"approval:{task_id}",
                 {"operator": u.get("realName"), "reason": (reason or "")[:200]})
    return result


def weekly_review(user: dict, report_id: str, action: str, comment: str | None = None) -> dict:
    """实习周报批阅（APPROVE/RETURN）。SCOPED 教师只能批阅范围内学生的周报。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = internship_service.get_weekly_report_detail(report_id)  # 不存在 → 404
        if not scope_match_row(scope, class_name=detail.get("className"),
                               advisor_name=detail.get("advisorName"),
                               student_no=detail.get("studentNo")):
            # 兜底：按实习记录导师姓名判定
            allowed = False
            try:
                with _session() as db:
                    from app.models import InternshipRecord, WeeklyReport
                    w = db.get(WeeklyReport, int(report_id))
                    rec = db.get(InternshipRecord, w.internship_id) if w else None
                    if rec and (rec.advisor_name or "").strip() in scope["advisorNames"]:
                        allowed = True
                    if rec and rec.student_id:
                        from app.models import StudentProfile
                        stu = db.get(StudentProfile, rec.student_id)
                        if stu is not None and can_teacher_view_student({}, stu, scope=scope, db=db):
                            allowed = True
            except Exception:  # noqa: BLE001
                allowed = False
            if not allowed:
                raise AppException("NO_PERMISSION", "该周报不在你的负责范围内")
    result = internship_service.review_weekly_report(report_id, action, comment or "")
    _audit_write("MOBILE_WEEKLY_REVIEW", f"internship/weekly:{report_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def exception_handle(user: dict, exception_id: str, action: str, comment: str | None = None) -> dict:
    """打卡异常处理（REASONABLE/ABNORMAL/TO_RISK）。服务层已做租户过滤 + 已处理 409。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实处理")
    result = internship_service.handle_attendance_exception(exception_id, action, comment or "")
    _audit_write("MOBILE_CHECKIN_HANDLE", f"internship/exception:{exception_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def makeup_pending(user: dict) -> dict:
    """补卡审批·待处理队列（移动端范围过滤，复用 PC 补卡审批服务的 owner+数据范围校验）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_makeup_service as mk
    items, total = mk.list_makeups(1, 50, status="PENDING", user=u)
    return {"list": items, "total": total}


def makeup_review(user: dict, makeup_id: str, action: str, comment: str | None = None) -> dict:
    """补卡·教师审批（APPROVE/REJECT）。owner 校验在服务层完成，通过时真实补写打卡。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实审批")
    from app.modules.internship.services import internship_makeup_service as mk
    result = mk.review(u, makeup_id, action, comment or "")
    _audit_write("MOBILE_MAKEUP_REVIEW", f"internship-makeup:{makeup_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def leave_pending(user: dict) -> dict:
    """实习请假审批·待处理队列（移动端范围过滤，复用 PC 请假审批服务的 owner+数据范围校验）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_leave_service as lv_svc
    items, total = lv_svc.list_leaves(1, 50, status="PENDING", user=u)
    return {"list": items, "total": total}


def leave_review(user: dict, leave_id: str, action: str, comment: str | None = None) -> dict:
    """实习请假·教师审批（APPROVE/REJECT）。owner 校验在服务层完成。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实审批")
    from app.modules.internship.services import internship_leave_service as lv_svc
    result = lv_svc.review(u, leave_id, action, comment or "")
    _audit_write("MOBILE_LEAVE_REVIEW", f"internship-leave:{leave_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def internship_my_students(user: dict) -> dict:
    """指导教师·本人指导实习学生名单（复用 PC 实习学生列表的 owner+数据范围收敛，供移动端选择记指导记录用）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    items, total = internship_service.list_internship_students(1, 100, user=u)
    return {"list": items, "total": total}


def internship_guidance_create(user: dict, body: dict) -> dict:
    """指导记录·移动端新增（线上/电话等指导留痕，owner 校验在服务层完成，可联动转风险/通知辅导员）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实记录")
    from app.modules.internship.services import internship_guidance_service as guide_svc
    result = guide_svc.create(u, body or {})
    _audit_write("MOBILE_INTERNSHIP_GUIDANCE_CREATE", f"internship-guidance:{result.get('id')}",
                 {"operator": u.get("realName"), "internshipId": (body or {}).get("internshipId")})
    return result


def student_eval_pending(user: dict) -> dict:
    """指导教师·学生实习鉴定队列（本人指导学生的自评，供填写意见/审核，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_student_eval_service as se
    items, total = se.list_evals(1, 50, user=u)
    return {"list": items, "total": total}


def student_eval_detail(user: dict, eval_id: str) -> dict:
    """学生实习鉴定详情（自评/意见/审核留痕，owner+范围校验）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实鉴定材料")
    from app.modules.internship.services import internship_student_eval_service as se
    return se.get_eval(eval_id, user=u)


def student_eval_advisor_comment(user: dict, eval_id: str, body: dict) -> dict:
    """指导教师·填写学生鉴定意见（owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_student_eval_service as se
    result = se.advisor_comment(u, eval_id, body or {})
    _audit_write("MOBILE_STU_EVAL_ADVISOR_COMMENT", f"internship-student-eval:{eval_id}",
                 {"operator": u.get("realName")})
    return result


def student_eval_review(user: dict, eval_id: str, action: str, comment: str | None = None) -> dict:
    """学生实习鉴定审核（APPROVE/RETURN，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_student_eval_service as se
    result = se.review(u, eval_id, action, comment or "")
    _audit_write("MOBILE_STU_EVAL_REVIEW", f"internship-student-eval:{eval_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def enterprise_eval_pending(user: dict) -> dict:
    """企业评价·教师端列表（本人指导学生的企业评价，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_enterprise_eval_service as ee
    items, total = ee.list_evals(1, 50, user=u)
    return {"list": items, "total": total}


def enterprise_eval_create(user: dict, body: dict) -> dict:
    """企业评价·教师录入（学校录入企业纸质评价，五维评分，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实录入")
    from app.modules.internship.services import internship_enterprise_eval_service as ee
    result = ee.create(u, body or {})
    _audit_write("MOBILE_ENTERPRISE_EVAL_CREATE", f"internship-enterprise-eval:{result.get('id')}",
                 {"operator": u.get("realName"), "internshipId": (body or {}).get("internshipId")})
    return result


def enterprise_eval_review(user: dict, eval_id: str, action: str, comment: str | None = None) -> dict:
    """企业评价审核（APPROVE/RETURN，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_enterprise_eval_service as ee
    result = ee.review(u, eval_id, action, comment or "")
    _audit_write("MOBILE_ENTERPRISE_EVAL_REVIEW", f"internship-enterprise-eval:{eval_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def insurance_pending(user: dict) -> dict:
    """实习保险·待核验队列（本人指导学生，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_insurance_service as ins_svc
    items, total = ins_svc.list_insurances(1, 50, status="PENDING_VERIFY", user=u)
    return {"list": items, "total": total}


def insurance_verify(user: dict, insurance_id: str, action: str, comment: str | None = None) -> dict:
    """实习保险·核验（APPROVE/REJECT，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_insurance_service as ins_svc
    result = ins_svc.verify_insurance(insurance_id, action, comment or "", user=u)
    _audit_write("MOBILE_INSURANCE_VERIFY", f"internship-insurance:{insurance_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def internship_change_pending(user: dict) -> dict:
    """调岗/退岗初审·待处理队列（本人指导学生，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_change_service as change_svc
    items, total = change_svc.list_changes(1, 50, status="PENDING", user=u)
    return {"list": items, "total": total}


def internship_change_review(user: dict, change_id: str, action: str, comment: str | None = None) -> dict:
    """调岗/退岗初审（APPROVE/REJECT，owner 校验在服务层完成，通过后联动更新实习记录）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_change_service as change_svc
    result = change_svc.review_change(change_id, action, comment or "", user=u)
    _audit_write("MOBILE_INTERNSHIP_CHANGE_REVIEW", f"internship-change:{change_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def internship_score_list(user: dict) -> dict:
    """实习成绩·教师端列表（本人指导学生已核算的成绩，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_score_service as score_svc
    items, total = score_svc.list_scores(1, 50, user=u)
    return {"list": items, "total": total}


def internship_score_compute(user: dict, body: dict) -> dict:
    """实习成绩·核算（五项加权，owner 校验在服务层完成，企业评价分未填时自动取已通过均分）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实核算")
    from app.modules.internship.services import internship_score_service as score_svc
    result = score_svc.compute(u, body or {})
    _audit_write("MOBILE_INTERNSHIP_SCORE_COMPUTE", f"internship-score:{result.get('id')}",
                 {"operator": u.get("realName"), "internshipId": (body or {}).get("internshipId")})
    return result


def internship_score_publish(user: dict, score_id: str) -> dict:
    """实习成绩·发布（owner 校验在服务层完成，缺项不可发布）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实发布")
    from app.modules.internship.services import internship_score_service as score_svc
    result = score_svc.publish(u, score_id)
    _audit_write("MOBILE_INTERNSHIP_SCORE_PUBLISH", f"internship-score:{score_id}",
                 {"operator": u.get("realName")})
    return result


def agreement_pending_school(user: dict) -> dict:
    """三方协议·待学校确认队列（本人指导学生，已记录企业签署，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_agreement_service as agr
    items, total = agr.list_agreements(1, 50, status="PENDING_SCHOOL", user=u)
    return {"list": items, "total": total}


def agreement_school_confirm(user: dict, agreement_id: str) -> dict:
    """三方协议·学校确认生效（PENDING_SCHOOL→EFFECTIVE，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_agreement_service as agr
    result = agr.school_confirm(u, agreement_id)
    _audit_write("MOBILE_AGREEMENT_SCHOOL_CONFIRM", f"internship-agreement:{agreement_id}",
                 {"operator": u.get("realName")})
    return result


def process_report_pending(user: dict) -> dict:
    """过程报告(日报/月报/总结)·待批阅队列（本人指导学生，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_process_report_service as pr
    items, total = pr.list_reports(1, 50, status="PENDING_REVIEW", user=u)
    return {"list": items, "total": total}


def process_report_detail(user: dict, report_id: str) -> dict:
    """过程报告详情（含正文，owner+范围校验）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实报告")
    from app.modules.internship.services import internship_process_report_service as pr
    return pr.get_report(report_id, user=u)


def process_report_review(user: dict, report_id: str, action: str, comment: str | None = None) -> dict:
    """过程报告批阅（APPROVE/RETURN，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    from app.modules.internship.services import internship_process_report_service as pr
    result = pr.review_report(report_id, action, comment or "", user=u)
    _audit_write("MOBILE_PROCESS_REPORT_REVIEW", f"internship-process-report:{report_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def plan_task_pending(user: dict) -> dict:
    """实习计划任务完成度·待确认队列（本人指导学生，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_plan_task_service as task_svc
    items, total = task_svc.list_progress(1, 50, status="SUBMITTED", user=u)
    return {"list": items, "total": total}


def plan_task_review(user: dict, progress_id: str, action: str, comment: str | None = None) -> dict:
    """实习计划任务完成度确认（APPROVE/REJECT，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_plan_task_service as task_svc
    result = task_svc.review_progress(progress_id, action, comment or "", user=u)
    _audit_write("MOBILE_PLAN_TASK_REVIEW", f"internship-plan-task:{progress_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def internship_application_pending(user: dict) -> dict:
    """实习申请·待审核队列（本人指导学生，owner+范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.internship.services import internship_application_service as app_svc
    items, total = app_svc.list_applications(1, 50, status="PENDING_REVIEW", user=u)
    return {"list": items, "total": total}


def internship_application_review(user: dict, application_id: str, action: str, comment: str | None = None) -> dict:
    """实习申请审核（APPROVE/REJECT，owner 校验在服务层完成，通过后落岗/落自主实习）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.internship.services import internship_application_service as app_svc
    result = app_svc.review_application(application_id, action, comment or "", user=u)
    _audit_write("MOBILE_INTERNSHIP_APPLICATION_REVIEW", f"internship-application:{application_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def proposal_review(user: dict, proposal_id: str, action: str, comment: str | None = None) -> dict:
    """毕设开题批阅（APPROVE/REJECT）。SCOPED 教师只能批阅范围内学生。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = graduation_service.get_proposal_detail(proposal_id)  # 不存在 → 404
        if not scope_match_row(scope, class_name=detail.get("className"),
                               advisor_name=detail.get("advisorName"),
                               student_no=detail.get("studentNo")):
            raise AppException("NO_PERMISSION", "该开题不在你的指导范围内")
    result = graduation_service.review_proposal(proposal_id, action, comment)
    _audit_write("MOBILE_PROPOSAL_REVIEW", f"graduation/proposal:{proposal_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def proposal_detail(user: dict, proposal_id: str) -> dict:
    """毕设开题详情（移动端批阅前真实查看：背景/方案/预期成果 + 历史版本 + 驳回意见 + 附件数）。
    SCOPED 教师只能查看指导范围内学生的开题，越权 403，不存在 404。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实开题材料")
    detail = graduation_service.get_proposal_detail(proposal_id)  # 不存在 → 404
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED" and not scope_match_row(
            scope, class_name=detail.get("className"), advisor_name=detail.get("advisorName"),
            student_no=detail.get("studentNo")):
        raise AppException("NO_PERMISSION", "该开题不在你的指导范围内")
    content = detail.get("content") or {}
    return {"id": str(detail.get("id") or proposal_id),
            "studentName": detail.get("studentName") or "", "className": detail.get("className") or "",
            "topicTitle": detail.get("topicTitle") or "", "version": detail.get("version") or "",
            "isResubmit": bool(detail.get("isResubmit")), "submitAt": detail.get("submitAt") or "",
            "status": detail.get("status"), "statusLabel": detail.get("statusLabel"),
            "background": content.get("background") or "", "plan": content.get("plan") or "",
            "outcome": content.get("outcome") or "", "reviewComment": detail.get("reviewComment") or "",
            "attachments": int(detail.get("attachments") or 0),
            "attachmentsList": detail.get("attachmentsList") or [],
            "versions": detail.get("versions") or []}


def final_detail(user: dict, final_id: str) -> dict:
    """毕设成果详情（移动端批阅前真实查看：类型/版本/查重 + 历史版本 + 退回意见 + 真实附件）。
    SCOPED 教师只能查看指导范围内学生的成果，越权 403，不存在 404。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实成果材料")
    detail = graduation_service.get_final_detail(final_id)  # 不存在 → 404
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED" and not scope_match_row(
            scope, class_name=detail.get("className"), advisor_name=detail.get("advisorName"),
            student_no=detail.get("studentNo")):
        raise AppException("NO_PERMISSION", "该成果不在你的指导范围内")
    return {"id": str(detail.get("id") or final_id),
            "studentName": detail.get("studentName") or "", "className": detail.get("className") or "",
            "topicTitle": detail.get("topicTitle") or "", "type": detail.get("type") or "",
            "version": detail.get("version") or "", "submitAt": detail.get("submitAt") or "",
            "status": detail.get("status"), "statusLabel": detail.get("statusLabel"),
            "plagiarismRate": detail.get("plagiarismRate") or "—",
            "plagiarismStatus": detail.get("plagiarismStatus") or "未检测",
            "plagiarismTone": detail.get("plagiarismTone") or "success",
            "reviewComment": detail.get("reviewComment") or "",
            "attachmentsList": detail.get("attachmentsList") or [],
            "versions": detail.get("versions") or []}


def final_review(user: dict, final_id: str, action: str, comment: str | None = None) -> dict:
    """毕设成果批阅（APPROVE/REJECT）。SCOPED 教师只能批阅范围内学生；查重超标 GD-R09 不可直接通过（后端拒绝）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = graduation_service.get_final_detail(final_id)  # 不存在 → 404
        if not scope_match_row(scope, class_name=detail.get("className"),
                               advisor_name=detail.get("advisorName"),
                               student_no=detail.get("studentNo")):
            raise AppException("NO_PERMISSION", "该成果不在你的指导范围内")
    result = graduation_service.review_final(final_id, action, comment)
    _audit_write("MOBILE_FINAL_REVIEW", f"graduation/final:{final_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result


def graduation_choices_pending(user: dict) -> list:
    """选题·本人指导题目下待确认的志愿（一对一人工复核队列）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_topic_round_service as round_svc
    return round_svc.list_pending_choices_for_advisor(u.get("realName") or "")


def _can_review_topic(u: dict, advisor_name: str) -> bool:
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "ADMIN_TENANT":
        return True
    return bool(advisor_name) and advisor_name.strip() == (u.get("realName") or "").strip()


def graduation_choice_review(user: dict, choice_id: str, action: str, reason: str | None = None) -> dict:
    """选题·教师确认/驳回单个志愿（CONFIRM/REJECT）。仅本人指导题目可操作。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.graduation.services import graduation_topic_round_service as round_svc
    detail = round_svc.get_choice_detail(choice_id)  # 不存在 → 404
    if not _can_review_topic(u, detail.get("advisorName")):
        raise AppException("NO_PERMISSION", "该志愿关联题目不在你的指导范围内")
    action = (action or "").upper()
    if action == "CONFIRM":
        result = round_svc.confirm_choice(choice_id, operator_name=u.get("realName"))
    elif action == "REJECT":
        result = round_svc.reject_choice(choice_id, reason or "", operator_name=u.get("realName"))
    else:
        raise AppException("VALIDATION_ERROR", "action 必须是 CONFIRM/REJECT")
    _audit_write("MOBILE_CHOICE_REVIEW", f"graduation-topic-choice:{choice_id}",
                 {"operator": u.get("realName"), "action": action, "reason": (reason or "")[:200]})
    return result


def graduation_change_requests_pending(user: dict) -> list:
    """选题·与本人相关（原/新题目导师为本人）的待审变更申请。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_topic_change_service as change_svc
    return change_svc.list_pending_for_advisor(u.get("realName") or "")


def graduation_change_request_review(user: dict, request_id: str, action: str,
                                     comment: str | None = None) -> dict:
    """选题·教师/管理员审核变更申请（APPROVE/REJECT）。仅涉及本人指导题目可操作。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.graduation.services import graduation_topic_change_service as change_svc
    detail = change_svc.get_change_request(request_id)  # 不存在 → 404
    scope = resolve_teacher_scope(u)
    if scope.get("mode") != "ADMIN_TENANT":
        name = (u.get("realName") or "").strip()
        if name not in (detail.get("oldAdvisorName") or "", detail.get("newAdvisorName") or ""):
            raise AppException("NO_PERMISSION", "该变更申请不在你的指导范围内")
    result = change_svc.review_change(request_id, action, comment or "", reviewer_name=u.get("realName"))
    _audit_write("MOBILE_CHANGE_REQUEST_REVIEW", f"graduation-topic-change:{request_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


def warning_handle(user: dict, warning_id: str, action: str, note: str | None = None) -> dict:
    """学业预警处理：CLOSE（关闭）/ ESCALATE（升级）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实处理")
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = academic_service.get_warning_detail(warning_id)  # 不存在 → 404
        w = detail.get("warning") or {}
        s = detail.get("student") or {}
        if not scope_match_row(scope, class_name=w.get("className") or s.get("className"),
                               student_no=s.get("studentNo")):
            raise AppException("NO_PERMISSION", "该预警学生不在你的负责范围内")
    if action == "CLOSE":
        result = academic_service.close_warning(warning_id, note or "")
    elif action == "ESCALATE":
        result = academic_service.escalate_warning(warning_id, note or "")
    else:
        raise AppException("VALIDATION_ERROR", "action 必须是 CLOSE/ESCALATE")
    _audit_write("MOBILE_WARNING_HANDLE", f"academic/warning:{warning_id}",
                 {"operator": u.get("realName"), "action": action, "note": (note or "")[:200]})
    return result


def followup_create(user: dict, body: dict) -> dict:
    """就业跟进记录（真实落库）。SCOPED 就业老师只能跟进范围内学生。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实提交")
    scope = resolve_teacher_scope(u)
    sid = body.get("studentId")
    if scope.get("mode") == "SCOPED" and sid:
        try:
            with _session() as db:
                from app.models import EmpStudent
                es = db.get(EmpStudent, int(sid))
                if es is None or es.is_deleted or es.tenant_id != _tid():
                    raise AppException("DATA_NOT_FOUND", "就业学生不存在")
                if not scope_match_row(scope, student_no=es.student_no,
                                       class_name=es.class_name):
                    raise AppException("NO_PERMISSION", "该学生不在你的负责范围内")
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "studentId 必须为数字")
    result = employment_service.create_followup(body)
    _audit_write("MOBILE_EMP_FOLLOWUP", f"employment/followup:{result.get('id')}",
                 {"operator": u.get("realName"), "studentId": str(sid or "")})
    return result


def graduation_my_students(user: dict) -> list:
    """过程指导·本人指导的毕设学生列表（ADMIN_TENANT 可见全部）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    from sqlalchemy import select as _select

    from app.models import GraduationStudent
    scope = resolve_teacher_scope(u)
    with _session() as db:
        q = _select(GraduationStudent).where(GraduationStudent.tenant_id == _tid(),
                                             GraduationStudent.is_deleted.is_(False),
                                             GraduationStudent.record_status == "ACTIVE")
        if scope.get("mode") != "ADMIN_TENANT":
            q = q.where(GraduationStudent.advisor_name == (u.get("realName") or ""))
        rows = db.scalars(q.order_by(GraduationStudent.id.desc())).all()
        return [{"gdStudentId": str(s.id), "name": s.name, "studentNo": s.student_no or "",
                "className": s.class_name or "", "stage": s.stage,
                "topicTitle": s.topic_title or "（未选题）"} for s in rows]


def graduation_guidance_create(user: dict, gd_student_id: str, body: dict) -> dict:
    """过程指导·教师移动端快速新增指导记录。仅本人指导学生可操作（ADMIN_TENANT 不限）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实提交")
    from app.models import GraduationStudent
    scope = resolve_teacher_scope(u)
    with _session() as db:
        s = db.get(GraduationStudent, int(gd_student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise AppException("DATA_NOT_FOUND", "毕设学生不存在")
        if scope.get("mode") != "ADMIN_TENANT" and (s.advisor_name or "") != (u.get("realName") or ""):
            raise AppException("NO_PERMISSION", "该生不在你的指导范围内")
    from app.modules.graduation.services import graduation_guidance_service as guidance_svc
    result = guidance_svc.create_guidance(gd_student_id, body)
    _audit_write("MOBILE_GUIDANCE_CREATE", f"graduation-guidance:{result.get('id')}",
                 {"operator": u.get("realName"), "gdStudentId": str(gd_student_id)})
    return result


def graduation_taskbook_list(user: dict) -> dict:
    """任务书·教师端列表（本人指导学生，owner+范围校验在服务层完成，复用 GD_MENTOR 指导关系判定）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return {"list": [], "total": 0}
    from app.modules.graduation.services import graduation_taskbook_service as tb
    items, total = tb.list_taskbooks(1, 50)
    return {"list": items, "total": total}


def graduation_taskbook_issue(user: dict, gd_student_id: str, body: dict) -> dict:
    """任务书·下达（owner 校验在服务层完成，须已分配导师且尚无任务书）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.graduation.services import graduation_taskbook_service as tb
    result = tb.issue_taskbook(gd_student_id, body or {})
    _audit_write("MOBILE_GD_TASKBOOK_ISSUE", f"graduation-taskbook:{gd_student_id}",
                 {"operator": u.get("realName")})
    return result


def graduation_taskbook_change(user: dict, gd_student_id: str, body: dict) -> dict:
    """任务书·变更（原因≥5字，仅已确认任务书可变更，owner 校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    from app.modules.graduation.services import graduation_taskbook_service as tb
    result = tb.change_taskbook(gd_student_id, body or {})
    _audit_write("MOBILE_GD_TASKBOOK_CHANGE", f"graduation-taskbook:{gd_student_id}",
                 {"operator": u.get("realName")})
    return result


def graduation_defense_score_pending(user: dict) -> list:
    """答辩评委·本人待评分学生名单（已发布分组，含本人当前轮次评分状态，范围校验在服务层完成）。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_defense_score_service as ds
    return ds.judge_pending()


def graduation_defense_score_entry(user: dict, gd_student_id: str, body: dict) -> dict:
    """答辩评委·录入/更新本人评分（judgeName 由服务端强制取当前登录人姓名，不信任客户端传入，
    比 PC 端更严格——PC 端 judgeName 由调用方在请求体自报，本函数不改动 PC 行为，仅收紧移动端）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实操作")
    b = body or {}
    judge_name = u.get("realName") or ""
    if not judge_name:
        raise AppException("VALIDATION_ERROR", "无法确认评委身份，请重新登录")
    from app.modules.graduation.services import graduation_defense_score_service as ds
    result = ds.enter_score(gd_student_id, judge_name, score=b.get("score"), comment=b.get("comment"),
                            absent=bool(b.get("absent")), absent_reason=b.get("absentReason"))
    _audit_write("MOBILE_GD_DEFENSE_SCORE_ENTRY", f"graduation-defense-score:{result.get('id')}",
                 {"operator": judge_name, "gdStudentId": str(gd_student_id), "absent": bool(b.get("absent"))})
    return result


def _require_gd_student_scope(u: dict, scope: dict, gd_student_id) -> dict:
    """加载毕设学生并做范围校验（非 ADMIN 只能本人指导学生）。不存在 404、越权 403。返回轻量快照。"""
    from app.models import GraduationStudent
    with _session() as db:
        s = db.get(GraduationStudent, int(gd_student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise AppException("DATA_NOT_FOUND", "毕设学生不存在")
        if scope.get("mode") != "ADMIN_TENANT" and (s.advisor_name or "") != (u.get("realName") or ""):
            raise AppException("NO_PERMISSION", "该生不在你的指导范围内")
        return {"id": s.id, "name": s.name, "className": s.class_name or "",
                "studentNo": s.student_no or "", "advisorName": s.advisor_name or ""}


# ══════════ 中期检查（教师移动端：待办队列 + 详情 + 检查/复核整改） ══════════

def graduation_midterm_queue(user: dict) -> list:
    """中期检查·本人指导学生中待检查(PENDING)/待复核整改(RECTIFY_SUBMITTED)的队列。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    scope = resolve_teacher_scope(u)
    from app.modules.graduation.services import graduation_midterm_service as mt
    rows, _ = _safe_list(mt.list_midterms, 1, 100)
    actionable = {"PENDING", "RECTIFY_SUBMITTED"}
    out = []
    for r in rows:
        if r.get("status") not in actionable:
            continue
        if scope["mode"] == "SCOPED" and not scope_match_row(
                scope, advisor_name=r.get("advisorName"), student_no=r.get("studentNo")):
            continue
        out.append(r)
    return out


def graduation_midterm_detail(user: dict, gd_student_id: str) -> dict:
    """中期检查·按学生查看真实记录（结论/检查意见/整改内容/复核）。范围校验。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实中期记录")
    from app.modules.graduation.services import graduation_midterm_service as mt
    d = mt.get_midterm(gd_student_id)  # 学生不存在 → 404
    scope = resolve_teacher_scope(u)
    if scope["mode"] == "SCOPED" and not scope_match_row(
            scope, advisor_name=d.get("advisorName"), student_no=d.get("studentNo")):
        raise AppException("NO_PERMISSION", "该生不在你的指导范围内")
    return d


def graduation_midterm_check(user: dict, gd_student_id: str, conclusion: str,
                             comment: str | None = None, rectify_deadline: str | None = None) -> dict:
    """中期检查·教师给出三档结论 PASS/RECTIFY/FAIL（后端校验状态机）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实中期检查")
    from app.modules.graduation.services import graduation_midterm_service as mt
    d = mt.get_midterm(gd_student_id)
    scope = resolve_teacher_scope(u)
    if scope["mode"] == "SCOPED" and not scope_match_row(
            scope, advisor_name=d.get("advisorName"), student_no=d.get("studentNo")):
        raise AppException("NO_PERMISSION", "该生不在你的指导范围内")
    result = mt.conduct_check(gd_student_id, str(conclusion or "").upper(), comment, rectify_deadline)
    _audit_write("MOBILE_MIDTERM_CHECK", f"graduation/midterm:{gd_student_id}",
                 {"operator": u.get("realName"), "conclusion": conclusion, "comment": (comment or "")[:200]})
    return result


def graduation_midterm_rectify_review(user: dict, gd_student_id: str, action: str,
                                      comment: str | None = None) -> dict:
    """中期检查·教师复核学生整改 PASS/FAIL（须处于 RECTIFY_SUBMITTED）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实复核")
    from app.modules.graduation.services import graduation_midterm_service as mt
    d = mt.get_midterm(gd_student_id)
    scope = resolve_teacher_scope(u)
    if scope["mode"] == "SCOPED" and not scope_match_row(
            scope, advisor_name=d.get("advisorName"), student_no=d.get("studentNo")):
        raise AppException("NO_PERMISSION", "该生不在你的指导范围内")
    result = mt.review_rectification(gd_student_id, str(action or "").upper(), comment)
    _audit_write("MOBILE_MIDTERM_RECTIFY_REVIEW", f"graduation/midterm:{gd_student_id}",
                 {"operator": u.get("realName"), "action": action})
    return result


# ══════════ 评阅（评阅教师移动端：本人评阅任务 + 提交评分/意见；SoD 回避后端已在分配时强制） ══════════

def graduation_my_reviews(user: dict) -> list:
    """评阅·本人作为评阅教师的待提交任务（ASSIGNED/REVIEWING/RETURNED）。评阅人身份即范围。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_review_service as rv
    rows, _ = _safe_list(rv.list_reviews, 1, 100, reviewer_name=u.get("realName") or "")
    return [r for r in rows if r.get("status") in ("ASSIGNED", "REVIEWING", "RETURNED")]


def graduation_review_submit(user: dict, review_id: str, score, opinion: str | None = None) -> dict:
    """评阅·提交评分(0-100)+意见。仅任务的评阅人本人可提交（ADMIN 不限）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实评阅")
    try:
        s = int(score)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "评分必须是 0-100 的整数")
    if s < 0 or s > 100:
        raise AppException("VALIDATION_ERROR", "评分必须在 0-100 之间")
    if not opinion or len(str(opinion).strip()) < 5:
        raise AppException("VALIDATION_ERROR", "评阅意见必填且不少于 5 字")
    from app.modules.graduation.services import graduation_review_service as rv
    scope = resolve_teacher_scope(u)
    mine, _ = rv.list_reviews(1, 500, reviewer_name=u.get("realName") or "")
    target = next((r for r in mine if str(r.get("id")) == str(review_id)), None)
    if not target and scope["mode"] == "ADMIN_TENANT":
        allr, _ = rv.list_reviews(1, 500)
        target = next((r for r in allr if str(r.get("id")) == str(review_id)), None)
    if not target:
        raise AppException("NO_PERMISSION", "该评阅任务不属于你或不存在")
    result = rv.submit_review(review_id, s, str(opinion).strip())
    _audit_write("MOBILE_REVIEW_SUBMIT", f"graduation/review:{review_id}",
                 {"operator": u.get("realName"), "score": s})
    return result


# ══════════ 答辩安排（教师移动端只读：本人指导学生答辩编排，已发布才展示时间/地点/评委） ══════════

def graduation_defense_arrangements(user: dict) -> list:
    """答辩安排·本人指导学生的答辩编排（只读）。未编排/未发布只给状态提示。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    students = graduation_my_students(user)  # 已按范围收敛
    from app.modules.graduation.services import graduation_service as gd
    out = []
    for s in students:
        try:
            v = gd.student_defense_view(int(s["gdStudentId"]))
        except Exception:  # noqa: BLE001
            v = None
        if not v or not v.get("hasData"):
            continue
        out.append({"gdStudentId": s["gdStudentId"], "studentName": s.get("name") or s.get("studentName") or "",
                    "className": s.get("className") or "", "topicTitle": s.get("topicTitle") or "", **v})
    return out


# ══════════ 成绩（教师移动端：待复核队列 + 三段构成详情 + 复核 APPROVE/RETURN） ══════════

def graduation_grade_queue(user: dict) -> list:
    """成绩·本人指导学生中待复核(CALCULATED)的成绩队列。"""
    u = _require_teacher(user)
    if not db_enabled():
        return []
    scope = resolve_teacher_scope(u)
    from app.modules.graduation.services import graduation_grade_service as gr
    rows, _ = _safe_list(gr.list_grades, 1, 100, status="CALCULATED")
    if scope["mode"] == "SCOPED":
        mine = {s.get("studentNo") for s in graduation_my_students(user) if s.get("studentNo")}
        rows = [r for r in rows if r.get("studentNo") in mine]
    return rows


def graduation_grade_detail(user: dict, gd_student_id: str) -> dict:
    """成绩·按学生查看三段构成（导师/评阅/答辩/综合/等级/状态）。范围校验。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持查看真实成绩")
    scope = resolve_teacher_scope(u)
    _require_gd_student_scope(u, scope, gd_student_id)  # 404/403
    from app.modules.graduation.services import graduation_grade_service as gr
    return gr.get_grade(gd_student_id)


def graduation_grade_review(user: dict, gd_student_id: str, action: str, comment: str | None = None) -> dict:
    """成绩·教师复核 APPROVE/RETURN（RETURN 原因≥5 字，后端校验；仅 CALCULATED 可复核）。"""
    u = _require_teacher(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实复核")
    scope = resolve_teacher_scope(u)
    _require_gd_student_scope(u, scope, gd_student_id)
    from app.modules.graduation.services import graduation_grade_service as gr
    result = gr.review_grade(gd_student_id, str(action or "").upper(), comment)
    _audit_write("MOBILE_GRADE_REVIEW", f"graduation/grade:{gd_student_id}",
                 {"operator": u.get("realName"), "action": action, "comment": (comment or "")[:200]})
    return result
