"""移动端·学生自视图聚合。严格只返回"当前登录学生本人"的跨域数据。
身份解析：token 的 realName（+可选 studentNo）在当前租户内匹配学生档案；
匹配不到返回空态（不 500）。敏感字段脱敏。复用 P7 六域真实表，不暴露管理端全列表。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services import audit_log
from app.services.db_service import _iso, _mask_id_card, _mask_phone, _org_names, _primary_phone, _tid


def _require_student(user: dict | None):
    u = user or {}
    if (u.get("userType") or "").upper() != "STUDENT":
        raise AppException("NO_PERMISSION", "该接口仅学生端可用")
    return u


def _session():
    return get_sessionmaker()()


def resolve_student(db, u: dict):
    """在当前租户内解析当前登录学生的主档：优先 studentNo，其次 realName。找不到返回 None。"""
    from app.models import StudentProfile
    tid = _tid()
    sn = u.get("studentNo")
    q = select(StudentProfile).where(StudentProfile.tenant_id == tid,
                                     StudentProfile.is_deleted.is_(False))
    if sn:
        row = db.scalars(q.where(StudentProfile.student_no == sn)).first()
        if row:
            return row
    name = u.get("realName")
    if name:
        return db.scalars(q.where(StudentProfile.real_name == name)).first()
    return None


def _empty(reason="尚未建立你的学生档案或暂无数据"):
    return {"hasData": False, "note": reason}


# ─────────── 我的首页 overview ───────────

def me_overview(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return {"student": None, **_empty("演示模式")}
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return {"student": None, "stage": None, "todos": [], "alerts": [], "notices": [],
                    "domains": [], **_empty()}
        from app.models import (AcademicStudent, AcademicWarning, EmpStudent, InternshipRecord,
                                OrientationStudent, UnifiedMessage, UnifiedTodo)
        sid, name = stu.id, stu.real_name
        # 我的待办（assignee 或与我相关，简化：按 student_id 关联）
        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.student_id == sid, UnifiedTodo.status == "PENDING").limit(10)).all()
        notices = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False)
        ).order_by(UnifiedMessage.id.desc()).limit(5)).all()
        # 各域是否有我的记录 + 关键状态
        intern = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == sid,
            InternshipRecord.is_deleted.is_(False))).first()
        ori = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.name == name,
            OrientationStudent.is_deleted.is_(False))).first()
        acad = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.name == name,
            AcademicStudent.is_deleted.is_(False))).first()
        warn = 0
        if acad:
            warn = db.scalar(select(func.count()).select_from(AcademicWarning).where(
                AcademicWarning.tenant_id == _tid(), AcademicWarning.acad_student_id == acad.id,
                AcademicWarning.is_deleted.is_(False),
                AcademicWarning.status.in_(["PENDING_HANDLE", "PROCESSING", "ESCALATED"]))) or 0
        emp = db.scalars(select(EmpStudent).where(
            EmpStudent.tenant_id == _tid(), EmpStudent.name == name,
            EmpStudent.is_deleted.is_(False))).first()
        alerts = []
        if warn:
            alerts.append({"level": "HIGH", "title": "你有学业预警待跟进", "domain": "academic"})
        if ori and ori.blocked_step:
            alerts.append({"level": "MEDIUM", "title": f"报到卡点：{ori.blocked_reason or ori.blocked_step}",
                           "domain": "orientation"})
        return {
            "student": {"name": name, "studentNo": stu.student_no, "grade": stu.grade or "",
                        "className": (stu.grade + "级") if stu.grade else "", "stage": stu.current_stage},
            "stage": {"code": stu.current_stage, "label": stu.current_stage},
            "todos": [{"id": str(t.id), "title": t.title, "type": t.todo_type,
                       "dueAt": _iso(t.due_at) if hasattr(t, "due_at") else None} for t in todos],
            "alerts": alerts,
            "notices": [{"id": str(n.id), "title": n.title, "type": n.message_type,
                         "status": n.status} for n in notices],
            "domains": [
                {"key": "orientation", "label": "数字迎新", "status": ori.report_status if ori else "NONE",
                 "hasData": bool(ori)},
                {"key": "internship", "label": "岗位实习",
                 "status": intern.status if intern else "NONE", "hasData": bool(intern)},
                {"key": "academic", "label": "学业过程", "status": "WARNING" if warn else "NORMAL",
                 "hasData": True},
                {"key": "employment", "label": "就业去向",
                 "status": emp.destination_type if emp else "NONE", "hasData": bool(emp)},
            ],
            "hasData": True,
        }


def my_todos(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return {"list": [], **_empty("演示模式")}
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return {"list": [], **_empty()}
        from app.models import UnifiedTodo
        rows = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.student_id == stu.id).order_by(UnifiedTodo.id.desc())).all()
        return {"list": [{"id": str(t.id), "title": t.title, "type": t.todo_type,
                          "status": t.status} for t in rows], "hasData": True}


def _empty_messages():
    return {"hasData": False, "unreadCount": 0,
            "tabs": [{"key": "todo", "label": "待办", "badge": 0},
                     {"key": "notice", "label": "通知", "badge": 0},
                     {"key": "progress", "label": "服务进度", "badge": 0}],
            "groups": {"todo": [], "notice": [], "progress": []}, "list": []}


def my_messages(user: dict) -> dict:
    """学生本人消息中心：只由本人 todo/业务状态生成轻量消息，绝不返回全校消息表。
    这样保证严格本人可见，不依赖统一消息表 receiver 精准关联。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty_messages()
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty_messages()
        from app.models import (AcademicStudent, AcademicWarning, CsLeave, CsServiceStudent,
                                CsWorkOrder, UnifiedMessage, UnifiedTodo)
        sid, name = stu.id, stu.real_name
        todo_msgs, notice_msgs, progress_msgs = [], [], []
        # 待办 → 本人 todo
        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.is_deleted.is_(False),
            UnifiedTodo.student_id == sid).order_by(UnifiedTodo.id.desc()).limit(30)).all()
        for t in todos:
            todo_msgs.append({"id": "todo-" + str(t.id), "title": t.title,
                              "module": t.source_module or "待办",
                              "level": "high" if (t.status or "") == "PENDING" else "normal",
                              "time": _iso(getattr(t, "created_at", None)),
                              "deadline": _iso(getattr(t, "due_at", None)),
                              "read": (t.status or "") != "PENDING",
                              "status": t.status, "link": t.source_module or ""})
        # 通知 → 本人接收的统一消息（receiver_id 精准匹配本人 user_id，无法匹配则不返回）
        uid = _resolve_uid(u)
        if uid is not None:
            notices = db.scalars(select(UnifiedMessage).where(
                UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
                UnifiedMessage.receiver_id == uid).order_by(UnifiedMessage.id.desc()).limit(30)).all()
            for m in notices:
                notice_msgs.append({"id": "msg-" + str(m.id), "title": m.title,
                                    "module": m.source_module or "通知", "level": "normal",
                                    "time": _iso(m.created_at), "deadline": None,
                                    "read": (m.status or "") == "READ",
                                    "status": m.status, "link": m.source_module or ""})
        # 服务进度 → 本人请假/工单状态流转
        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.is_deleted.is_(False),
            (CsServiceStudent.student_no == stu.student_no) | (CsServiceStudent.name == name))).first()
        if cs:
            for lv in db.scalars(select(CsLeave).where(CsLeave.tenant_id == _tid(),
                                 CsLeave.cs_student_id == cs.id, CsLeave.is_deleted.is_(False)
                                 ).order_by(CsLeave.id.desc()).limit(10)).all():
                progress_msgs.append({"id": "leave-" + str(lv.id),
                                      "title": f"你的请假申请当前状态：{lv.status}",
                                      "module": "服务进度", "level": "normal",
                                      "time": _iso(getattr(lv, "apply_time", None)), "deadline": None,
                                      "read": lv.status not in ("PENDING_REVIEW",),
                                      "status": lv.status, "link": "campus-service"})
            for wo in db.scalars(select(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid(),
                                 CsWorkOrder.cs_student_id == cs.id, CsWorkOrder.is_deleted.is_(False)
                                 ).order_by(CsWorkOrder.id.desc()).limit(10)).all():
                progress_msgs.append({"id": "wo-" + str(wo.id),
                                      "title": f"工单「{wo.title}」当前状态：{wo.status}",
                                      "module": "服务进度", "level": "normal",
                                      "time": None, "deadline": None,
                                      "read": wo.status not in ("PENDING_HANDLE",),
                                      "status": wo.status, "link": "campus-service"})
        groups = {"todo": todo_msgs, "notice": notice_msgs, "progress": progress_msgs}
        unread = sum(1 for g in groups.values() for x in g if not x.get("read"))
        tabs = [{"key": k, "label": lb,
                 "badge": sum(1 for x in groups[k] if not x.get("read"))}
                for k, lb in (("todo", "待办"), ("notice", "通知"), ("progress", "服务进度"))]
        flat = todo_msgs + notice_msgs + progress_msgs
        return {"hasData": bool(flat), "unreadCount": unread, "tabs": tabs,
                "groups": groups, "list": flat}


def _resolve_uid(u: dict):
    """从 token 尽力解析本人 user_id（int）；解析不到返回 None（则通知区不返回全校消息）。"""
    v = u.get("userId")
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ─────────── 六大域·我的 ───────────

def orientation_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import OrientationStudent
        o = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.name == stu.real_name,
            OrientationStudent.is_deleted.is_(False))).first()
        if not o:
            return _empty("你暂无迎新报到记录")
        return {"hasData": True, "reportStatus": o.report_status, "paymentStatus": o.payment_status,
                "materialStatus": o.material_status, "dormStatus": o.dorm_status,
                "greenChannelStatus": o.green_channel_status,
                "building": o.building or "", "room": o.room or "",
                "blockedStep": o.blocked_step or "", "blockedReason": o.blocked_reason or "",
                "steps": [{"key": k, "status": v} for k, v in (o.steps_json or {}).items()]}


def campus_service_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import CsDiscipline, CsLeave, CsServiceStudent, CsWorkOrder
        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_no == stu.student_no,
            CsServiceStudent.is_deleted.is_(False))).first()
        if not cs:
            cs = db.scalars(select(CsServiceStudent).where(
                CsServiceStudent.tenant_id == _tid(), CsServiceStudent.name == stu.real_name,
                CsServiceStudent.is_deleted.is_(False))).first()
        if not cs:
            return _empty("你暂无在校服务记录")
        leaves = db.scalars(select(CsLeave).where(CsLeave.tenant_id == _tid(),
                            CsLeave.cs_student_id == cs.id, CsLeave.is_deleted.is_(False)
                            ).order_by(CsLeave.id.desc())).all()
        wos = db.scalars(select(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid(),
                         CsWorkOrder.cs_student_id == cs.id, CsWorkOrder.is_deleted.is_(False)
                         ).order_by(CsWorkOrder.id.desc())).all()
        # 处分：仅显示"有无 + 数量"，不显示细节（敏感，脱敏）
        disc_cnt = db.scalar(select(func.count()).select_from(CsDiscipline).where(
            CsDiscipline.tenant_id == _tid(), CsDiscipline.cs_student_id == cs.id,
            CsDiscipline.record_status == "ACTIVE", CsDiscipline.is_deleted.is_(False))) or 0
        return {"hasData": True,
                "leaves": [{"id": str(x.id), "type": x.leave_type, "duration": x.duration or "",
                            "status": x.status, "reason": x.reason or ""} for x in leaves],
                "workOrders": [{"id": str(x.id), "title": x.title, "type": x.wo_type,
                                "status": x.status} for x in wos],
                "disciplineNotice": {"count": disc_cnt,
                                     "hint": "如有疑问请联系辅导员" if disc_cnt else "无"},
                "mentalNotice": "如需心理支持，可在学工处预约（记录仅心理老师可见）"}


def academic_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import AcademicGrade, AcademicStudent, AcademicWarning
        a = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_no == stu.student_no,
            AcademicStudent.is_deleted.is_(False))).first()
        if not a:
            a = db.scalars(select(AcademicStudent).where(
                AcademicStudent.tenant_id == _tid(), AcademicStudent.name == stu.real_name,
                AcademicStudent.is_deleted.is_(False))).first()
        if not a:
            return _empty("你暂无学业记录")
        grades = db.scalars(select(AcademicGrade).where(AcademicGrade.tenant_id == _tid(),
                            AcademicGrade.acad_student_id == a.id, AcademicGrade.is_deleted.is_(False)
                            ).order_by(AcademicGrade.id.desc())).all()
        warns = db.scalars(select(AcademicWarning).where(AcademicWarning.tenant_id == _tid(),
                           AcademicWarning.acad_student_id == a.id, AcademicWarning.is_deleted.is_(False),
                           AcademicWarning.record_status == "ACTIVE").order_by(AcademicWarning.id.desc())).all()
        return {"hasData": True,
                "summary": {"gpa": float(a.gpa or 0), "avgScore": a.avg_score,
                            "obtainedCredits": float(a.obtained_credits or 0),
                            "requiredCredits": float(a.required_credits or 0),
                            "failedCount": a.failed_count, "academicStatus": a.academic_status,
                            "warningLevel": a.warning_level},
                "grades": [{"course": g.course_name, "term": g.term or "", "score": g.score,
                            "passStatus": g.pass_status} for g in grades],
                "warnings": [{"type": w.warn_type, "level": w.level, "reason": w.reason or "",
                              "status": w.status} for w in warns]}


def internship_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import AttendanceException, InternshipRecord, WeeklyReport
        rec = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
            InternshipRecord.is_deleted.is_(False))).first()
        if not rec:
            return _empty("你暂无实习记录")
        reports = db.scalars(select(WeeklyReport).where(WeeklyReport.tenant_id == _tid(),
                             WeeklyReport.internship_id == rec.id, WeeklyReport.is_deleted.is_(False)
                             ).order_by(WeeklyReport.week_number.desc())).all()
        excs = db.scalars(select(AttendanceException).where(AttendanceException.tenant_id == _tid(),
                          AttendanceException.internship_id == rec.id,
                          AttendanceException.is_deleted.is_(False)).order_by(
                          AttendanceException.id.desc())).all()
        return {"hasData": True,
                "enterpriseName": rec.enterprise_name or "", "positionName": rec.position_name or "",
                "advisorName": rec.advisor_name or "", "status": rec.status,
                "riskLevel": rec.risk_level,
                "weeklyReports": [{"week": r.week_number, "status": r.status,
                                   "reviewComment": r.review_comment or ""} for r in reports],
                "attendanceExceptions": [{"type": e.exception_type, "status": e.status,
                                          "date": _iso(e.exception_date)} for e in excs]}


def graduation_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import GraduationFinal, GraduationProposal, GraduationStudent
        g = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.student_no == stu.student_no,
            GraduationStudent.is_deleted.is_(False))).first()
        if not g:
            g = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.name == stu.real_name,
                GraduationStudent.is_deleted.is_(False))).first()
        if not g:
            return _empty("你暂无毕设记录")
        props = db.scalars(select(GraduationProposal).where(GraduationProposal.tenant_id == _tid(),
                           GraduationProposal.gd_student_id == g.id, GraduationProposal.is_deleted.is_(False)
                           ).order_by(GraduationProposal.id.desc())).all()
        finals = db.scalars(select(GraduationFinal).where(GraduationFinal.tenant_id == _tid(),
                            GraduationFinal.gd_student_id == g.id, GraduationFinal.is_deleted.is_(False)
                            ).order_by(GraduationFinal.id.desc())).all()
        return {"hasData": True, "topicTitle": g.topic_title or "（未选题）",
                "advisorName": g.advisor_name or "", "stage": g.stage,
                "defenseGroup": g.defense_group or "待分组", "plagiarismRate": g.plagiarism_rate or "—",
                "proposals": [{"version": p.version or "", "status": p.status,
                               "reviewComment": p.review_comment or ""} for p in props],
                "finals": [{"type": f.final_type, "version": f.version or "", "status": f.status,
                            "plagiarismRate": f.plagiarism_rate or "—"} for f in finals]}


def employment_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import EmpFollowup, EmpMaterial, EmpStudent
        e = db.scalars(select(EmpStudent).where(
            EmpStudent.tenant_id == _tid(), EmpStudent.student_no == stu.student_no,
            EmpStudent.is_deleted.is_(False))).first()
        if not e:
            e = db.scalars(select(EmpStudent).where(
                EmpStudent.tenant_id == _tid(), EmpStudent.name == stu.real_name,
                EmpStudent.is_deleted.is_(False))).first()
        if not e:
            return _empty("你暂无就业记录")
        mats = db.scalars(select(EmpMaterial).where(EmpMaterial.tenant_id == _tid(),
                          EmpMaterial.emp_student_id == e.id, EmpMaterial.is_deleted.is_(False)
                          ).order_by(EmpMaterial.id.desc())).all()
        fus = db.scalars(select(EmpFollowup).where(EmpFollowup.tenant_id == _tid(),
                         EmpFollowup.emp_student_id == e.id, EmpFollowup.is_deleted.is_(False)
                         ).order_by(EmpFollowup.id.desc())).all()
        return {"hasData": True, "destinationType": e.destination_type,
                "companyName": e.company_name or "", "jobTitle": e.job_title or "",
                "verifyStatus": e.verify_status, "materialStatus": e.material_status,
                "helpLevel": e.help_level,
                "materials": [{"type": m.material_type, "fileName": m.file_name or "",
                               "status": m.status} for m in mats],
                "followUps": [{"way": f.way, "content": f.content or "",
                               "time": _iso(f.follow_time)} for f in fus]}


# ─────────── 我的档案（脱敏） ───────────

def my_profile(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return {"hasData": False, "note": "演示模式"}
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return {"hasData": False, "note": "尚未建立你的学生档案"}
        _org_names(db, [stu])
        phone_plain = _primary_phone(db, stu.id)
        return {"hasData": True,
                "studentId": str(stu.id), "studentNo": stu.student_no, "name": stu.real_name,
                "gender": stu.gender or "", "collegeName": getattr(stu, "_college_name", "") or "",
                "majorName": getattr(stu, "_major_name", "") or "",
                "className": getattr(stu, "_class_name", "") or "",
                "grade": stu.grade or "",
                "phoneMasked": _mask_phone(phone_plain) if phone_plain else "",
                "idCardMasked": _mask_id_card(stu.id_card_encrypted) if stu.id_card_encrypted else "",
                # 家庭住址属敏感，移动端不返回明文，也不回脱敏串（最小化）
                "status": stu.student_status, "stage": stu.current_stage}


# ─────────── 我的申请（聚合本人可查询记录） ───────────

def my_applications(user: dict) -> dict:
    u = _require_student(user)
    tabs = [{"key": "all", "label": "全部"}, {"key": "processing", "label": "处理中"},
            {"key": "done", "label": "已办结"}, {"key": "rejected", "label": "已驳回"}]
    if not db_enabled():
        return {"hasData": False, "tabs": tabs, "applications": []}
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return {"hasData": False, "tabs": tabs, "applications": []}
        from app.models import CsGrant, CsLeave, CsServiceStudent, CsWorkOrder
        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.is_deleted.is_(False),
            (CsServiceStudent.student_no == stu.student_no) | (CsServiceStudent.name == stu.real_name))).first()
        apps = []
        if cs:
            _done = {"APPROVED", "COMPLETED", "CLOSED", "PASSED", "GRANTED"}
            _rej = {"REJECTED", "RETURNED", "VOIDED"}

            def _grp(s):
                s = (s or "").upper()
                return "done" if s in _done else "rejected" if s in _rej else "processing"

            for lv in db.scalars(select(CsLeave).where(CsLeave.tenant_id == _tid(),
                                 CsLeave.cs_student_id == cs.id, CsLeave.is_deleted.is_(False)
                                 ).order_by(CsLeave.id.desc())).all():
                apps.append({"id": "leave-" + str(lv.id), "no": lv.code or ("SV" + str(lv.id)),
                             "name": f"学生请假（{lv.leave_type}）", "group": _grp(lv.status),
                             "status": lv.status, "statusText": lv.status, "applyTime": _iso(lv.apply_time),
                             "dept": "学工处", "handler": lv.reviewer or "待分配",
                             "lastOpinion": lv.return_reason or "", "hasResult": _grp(lv.status) != "processing",
                             "sourceType": "LEAVE"})
            for gr in db.scalars(select(CsGrant).where(CsGrant.tenant_id == _tid(),
                                 CsGrant.cs_student_id == cs.id, CsGrant.is_deleted.is_(False)
                                 ).order_by(CsGrant.id.desc())).all():
                apps.append({"id": "grant-" + str(gr.id), "no": gr.code or ("GR" + str(gr.id)),
                             "name": f"资助申请（{gr.grant_type}）", "group": _grp(gr.status),
                             "status": gr.status, "statusText": gr.status, "applyTime": _iso(gr.apply_time),
                             "dept": "资助中心", "handler": gr.reviewer or "待分配",
                             "lastOpinion": gr.return_reason or "", "hasResult": _grp(gr.status) != "processing",
                             "sourceType": "GRANT"})
            for wo in db.scalars(select(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid(),
                                 CsWorkOrder.cs_student_id == cs.id, CsWorkOrder.is_deleted.is_(False)
                                 ).order_by(CsWorkOrder.id.desc())).all():
                apps.append({"id": "wo-" + str(wo.id), "no": wo.code or ("WO" + str(wo.id)),
                             "name": wo.title, "group": _grp(wo.status), "status": wo.status,
                             "statusText": wo.status, "applyTime": None, "dept": "服务中心",
                             "handler": wo.handler or "待分配", "lastOpinion": "",
                             "hasResult": _grp(wo.status) != "processing", "sourceType": "WORKORDER"})
        return {"hasData": bool(apps), "tabs": tabs, "applications": apps}


# ─────────── 学生写操作：提交服务申请 / 提交实习周报 ───────────

def campus_service_apply(user: dict, body: dict) -> dict:
    u = _require_student(user)
    service_key = str(body.get("serviceKey") or body.get("serviceType") or "").strip()
    content = str(body.get("reason") or body.get("content") or "").strip()
    if not service_key:
        raise AppException("VALIDATION_ERROR", "服务类型（serviceKey）必填")
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "申请事由至少 5 个字")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实提交")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案，无法提交")
        from app.models import CsLeave, CsServiceStudent, CsWorkOrder
        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.is_deleted.is_(False),
            (CsServiceStudent.student_no == stu.student_no) | (CsServiceStudent.name == stu.real_name))).first()
        if not cs:
            cs = CsServiceStudent(tenant_id=_tid(), student_no=stu.student_no, student_id=stu.id,
                                  name=stu.real_name, grade=stu.grade, record_status="ACTIVE")
            db.add(cs)
            db.flush()
        is_leave = service_key.upper() in ("LEAVE", "SV1", "请假")
        from datetime import datetime as _dt
        if is_leave:
            row = CsLeave(tenant_id=_tid(), cs_student_id=cs.id, leave_type="PERSONAL",
                          reason=content, status="PENDING_REVIEW", apply_time=_dt.utcnow(),
                          code=f"SV-{_dt.now():%Y%m%d}-{cs.id}")
        else:
            row = CsWorkOrder(tenant_id=_tid(), cs_student_id=cs.id, title=service_key,
                              wo_type="CONSULT", priority="MEDIUM", detail=content,
                              status="PENDING_HANDLE", code=f"WO-{_dt.now():%Y%m%d}-{cs.id}",
                              trail_json=[{"title": "学生提交", "desc": content,
                                           "time": _iso(_dt.utcnow()), "tone": "processing"}])
        db.add(row)
        db.flush()
        rid, status = row.id, row.status
        db.commit()
    audit_log.record("MOBILE_SERVICE_APPLY", f"campus-service:{service_key}",
                     {"studentNo": u.get("studentNo"), "serviceKey": service_key})
    return {"id": str(rid), "status": status, "message": "提交成功，等待处理"}


def internship_weekly_submit(user: dict, body: dict) -> dict:
    u = _require_student(user)
    week_no = body.get("weekNo") or body.get("weekNumber")
    content = str(body.get("content") or "").strip()
    if week_no in (None, ""):
        raise AppException("VALIDATION_ERROR", "周次（weekNo）必填")
    try:
        week_no = int(week_no)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "周次必须为数字")
    if len(content) < 20:
        raise AppException("VALIDATION_ERROR", "周报正文至少 20 个字")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实提交")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        from datetime import datetime as _dt

        from app.models import InternshipRecord, WeeklyReport
        rec = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
            InternshipRecord.is_deleted.is_(False))).first()
        if not rec:
            raise AppException("DATA_NOT_FOUND", "你当前没有实习记录，无法提交周报")
        dup = db.scalars(select(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id == rec.id,
            WeeklyReport.week_number == week_no, WeeklyReport.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"第 {week_no} 周周报已提交，请勿重复提交")
        w = WeeklyReport(tenant_id=_tid(), internship_id=rec.id, week_number=week_no,
                         work_content=content, harvest_content=str(body.get("problems") or ""),
                         plan_content=str(body.get("planNext") or ""), word_count=len(content),
                         report_version=1, status="PENDING_REVIEW", submitted_at=_dt.utcnow())
        db.add(w)
        db.flush()
        wid, status = w.id, w.status
        db.commit()
    audit_log.record("MOBILE_WEEKLY_SUBMIT", f"internship:week{week_no}",
                     {"studentNo": u.get("studentNo"), "weekNo": week_no})
    return {"id": str(wid), "status": status, "message": "周报提交成功"}
