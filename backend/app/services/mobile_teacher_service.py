"""移动端·教师工作台聚合（只读）。严格租户过滤（绝不跨租户）。
范围收敛：当前无独立 teacher_student_scope 表，先做「租户隔离 + 姓名关系尽力收敛」，
返回体带 scopeMode（SCOPED / TENANT_FALLBACK）标识，后续可替换为正式范围表。
复用 P7 六域真实 service，不重复造业务，也不暴露 PC 管理端全列表给前端。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services import (academic_service, approval_service, campus_service_service,
                          employment_service, graduation_service, internship_service,
                          orientation_service)
from app.services.db_service import _iso, _tid


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


# 管理类角色：租户级可见是设计预期（校级/学院管理员/教务处）
_ADMIN_ROLES = {"SCHOOL_ADMIN", "COLLEGE_ADMIN", "ACADEMIC_TEACHER", "SCHOOL_LEADER"}
_ADVISOR_ROLES = {"GD_MENTOR", "MENTOR", "INTERN_MENTOR", "INTERNSHIP_MENTOR"}


def resolve_teacher_scope(user: dict) -> dict:
    """解析教师数据范围（t_teacher_student_scope 最小可用版）：
    - 范围表行：CLASS(班级名) / COLLEGE(学院名) / STUDENT(学号) / ADVISOR(按导师姓名，
      ref_value 可登记别名，用于历史数据导师姓名与账号姓名不一致的过渡映射)
    - 导师类角色（GD_MENTOR/INTERN_MENTOR）默认叠加本人姓名的 ADVISOR 收敛
    - 管理类角色（校级/院级/教务）→ ADMIN_TENANT（租户级，设计预期）
    - 无任何范围信息 → TENANT_FALLBACK（仅租户隔离；试点可用，标准版应逐步清零）"""
    u = user or {}
    role = (u.get("currentRoleCode") or "").upper()
    name = u.get("realName") or ""
    uid = str(u.get("userId") or "")
    scope = {"mode": "TENANT_FALLBACK", "by": "TENANT", "advisorName": name,
             "roleCode": role, "tenantId": _tid(),
             "classNames": set(), "studentNos": set(), "collegeNames": set(),
             "advisorNames": set()}
    if (u.get("userType") or "").upper() == "ADMIN" or role in _ADMIN_ROLES:
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
    if scope["classNames"] or scope["studentNos"] or scope["collegeNames"] or scope["advisorNames"]:
        scope["mode"] = "SCOPED"
        scope["by"] = "SCOPE_TABLE"
    return scope


def _class_match(scope: dict, class_name: str | None) -> bool:
    """班级名匹配（兼容「软件2301」与「软件2301班」两种写法）。"""
    cn = (class_name or "").strip()
    if not cn:
        return False
    variants = {cn, cn.rstrip("班"), cn + "班"}
    return bool(variants & scope["classNames"])


def scope_match_row(scope: dict, student_no=None, class_name=None, advisor_name=None,
                    college_name=None) -> bool:
    """判断一行学生相关数据是否在教师范围内（SCOPED 才收敛，其余模式恒通过）。"""
    if scope.get("mode") != "SCOPED":
        return True
    if student_no and str(student_no).strip() in scope["studentNos"]:
        return True
    if _class_match(scope, class_name):
        return True
    if advisor_name and (advisor_name or "").strip() in scope["advisorNames"]:
        return True
    if college_name and (college_name or "").strip() in scope["collegeNames"]:
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
            if getattr(student, "college_id", None) and scope["collegeNames"]:
                col = db.get(College, student.college_id)
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
                if ir and (ir.advisor_name or "").strip() in scope["advisorNames"]:
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
    excs, etotal = _safe_list(internship_service.list_attendance_exceptions, 1, 50, status="PENDING_HANDLE")
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
    # SCOPED：严格按范围收敛（导师姓名/别名、班级、学号），不再"过滤为空就放全量"
    if scope["mode"] == "SCOPED":
        students = [s for s in students if scope_match_row(
            scope, advisor_name=s.get("advisorName") or s.get("mentor"),
            class_name=s.get("className"), student_no=s.get("studentNo"))]
        proposals = [p for p in proposals if scope_match_row(
            scope, advisor_name=p.get("advisorName"),
            class_name=p.get("className"), student_no=p.get("studentNo"))]
        stotal, ptotal = len(students), len(proposals)
    stats = {}
    try:
        stats = graduation_service.get_dashboard()
    except Exception:  # noqa: BLE001
        stats = {"pendingProposals": ptotal}
    return {"hasData": (stotal + ptotal) > 0, "students": students, "reviewDetail": proposals,
            "stats": stats, "scopeMode": scope["mode"]}


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


# 保留原迎新/在校/学业待处理列表（工作台跳转用）
def _domain(fn, module, user, **kw):
    _require_teacher(user)
    if not db_enabled():
        return {"list": [], "note": "演示模式"}
    rows, total = _safe_list(fn, 1, 50, **kw)
    return {"hasData": total > 0, "list": rows, "total": total, "module": module}


def orientation(user):
    return _domain(orientation_service.list_exceptions, "orientation", user, status="OPEN")


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
    groups = {"system": system_msgs, "dynamic": dynamic_msgs, "risk": risk_msgs}
    tabs = [{"key": "system", "label": "系统通知", "badge": len([x for x in system_msgs if not x["read"]])},
            {"key": "dynamic", "label": "学生动态", "badge": len([x for x in dynamic_msgs if not x["read"]])},
            {"key": "risk", "label": "风险预警", "badge": len([x for x in risk_msgs if not x["read"]])}]
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
            for r in rows:
                nm = (r.get("applicantName") or "").strip()
                if not nm:
                    continue
                stu = db.scalars(select(StudentProfile).where(
                    StudentProfile.tenant_id == _tid(), StudentProfile.real_name == nm,
                    StudentProfile.is_deleted.is_(False))).first()
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
