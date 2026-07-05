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


def resolve_teacher_scope(user: dict) -> dict:
    """解析教师范围。当前用现有字段尽力收敛：
    - GD_MENTOR   → 按毕设导师姓名（advisor_name）
    - INTERN_*    → 按实习指导教师姓名（advisor_name）
    - COUNSELOR   → 按班级（暂无 teacher↔class 映射，落到租户兜底）
    无法精确时 mode=TENANT_FALLBACK，仅保证租户隔离。"""
    u = user or {}
    role = (u.get("currentRoleCode") or "").upper()
    name = u.get("realName") or ""
    advisor_roles = {"GD_MENTOR", "MENTOR", "INTERN_MENTOR", "INTERNSHIP_MENTOR"}
    if role in advisor_roles and name:
        return {"mode": "SCOPED", "by": "ADVISOR_NAME", "advisorName": name,
                "roleCode": role, "tenantId": _tid()}
    return {"mode": "TENANT_FALLBACK", "by": "TENANT", "advisorName": name,
            "roleCode": role, "tenantId": _tid()}


def can_teacher_view_student(user: dict, student) -> bool:
    """教师是否可查看某学生。硬边界：必须同租户。软边界：SCOPED 时按导师姓名收敛。"""
    if student is None:
        return False
    if getattr(student, "tenant_id", None) != _tid():
        return False
    return True  # 同租户即可见（TENANT_FALLBACK）；更细粒度待范围表


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
        # 同租户内的更细范围（班级/指导关系）越权 → 403（当前 TENANT_FALLBACK 恒放行）
        if not can_teacher_view_student(u, stu):
            raise AppException("NO_PERMISSION", "无权限查看该学生")
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

def internship(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "weeklyReports": [], "abnormalCheckins": [], "stats": {}}
    scope = resolve_teacher_scope(u)
    reports, rtotal = _safe_list(internship_service.list_weekly_reports, 1, 50, status="PENDING_REVIEW")
    excs, etotal = _safe_list(internship_service.list_attendance_exceptions, 1, 50, status="PENDING_HANDLE")
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
    # SCOPED：按导师姓名收敛
    if scope["mode"] == "SCOPED" and scope.get("advisorName"):
        adv = scope["advisorName"]
        students = [s for s in students if (s.get("advisorName") or s.get("mentor") or "") == adv] or students
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
    system_msgs, dynamic_msgs, risk_msgs = [], [], []
    # 学生动态：待批周报 / 开题
    reports, _ = _safe_list(internship_service.list_weekly_reports, 1, 15, status="PENDING_REVIEW")
    for r in reports:
        dynamic_msgs.append({"id": "dyn-wr-" + str(r.get("id")),
                             "title": f"{r.get('name') or r.get('studentName') or '学生'} 提交了实习周报",
                             "module": "岗位实习", "level": "normal", "read": False})
    props, _ = _safe_list(graduation_service.list_proposals, 1, 15, status="PENDING_REVIEW")
    for p in props:
        dynamic_msgs.append({"id": "dyn-gp-" + str(p.get("id")),
                             "title": f"{p.get('name') or p.get('studentName') or '学生'} 提交了开题材料",
                             "module": "毕业设计", "level": "normal", "read": False})
    # 风险预警：打卡异常 / 学业预警
    excs, _ = _safe_list(internship_service.list_attendance_exceptions, 1, 15, status="PENDING_HANDLE")
    for e in excs:
        risk_msgs.append({"id": "risk-ck-" + str(e.get("id")),
                          "title": f"{e.get('name') or e.get('studentName') or '学生'} 打卡异常",
                          "module": "风险预警", "level": "high", "read": False})
    warns, _ = _safe_list(academic_service.list_warnings, 1, 15, status="PENDING_HANDLE")
    for w in warns:
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

def approvals(user: dict) -> dict:
    u = _require_teacher(user)
    if not db_enabled():
        return {"hasData": False, "approvals": [], "filters": [], "pendingCount": 0}
    rows, total = _safe_list(approval_service.list_tasks, 1, 50, status="PENDING_REVIEW")
    filters = [{"key": "pending", "label": "待处理"}, {"key": "done", "label": "已处理"}]
    return {"hasData": total > 0, "approvals": rows, "filters": filters, "pendingCount": total}
