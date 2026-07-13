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
        # 通知 → 本人接收的统一消息（receiver_id 精准匹配本人 user_id；
        # mock 演示令牌无数字 uid 时，以学生主档 id 兜底匹配演示种子消息）
        uid = _resolve_uid(u)
        if uid is None:
            uid = sid
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
    """从 token 尽力解析本人 user_id（int）；兼容 db-<id> / u_xxx 前缀形式。
    解析不到返回 None（则通知区不返回全校消息，绝不放开 receiver 过滤）。"""
    v = str(u.get("userId") or "")
    if v.startswith("db-"):
        v = v[3:]
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def message_mark_read(user: dict, message_id) -> dict:
    """标记本人接收的统一消息为已读。严格校验 receiver 归属：非本人消息 404（不泄露存在性）。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持")
    try:
        mid = int(str(message_id).replace("msg-", ""))
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "消息 id 无效")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        uid = _resolve_uid(u)
        if uid is None:
            uid = stu.id
        from datetime import datetime as _dt

        from app.models import UnifiedMessage
        m = db.get(UnifiedMessage, mid)
        if m is None or m.is_deleted or m.tenant_id != _tid() or m.receiver_id != uid:
            raise AppException("DATA_NOT_FOUND", "消息不存在")
        if (m.status or "") != "READ":
            m.status = "READ"
            m.read_at = _dt.utcnow()
            m.version += 1
            db.commit()
        return {"messageId": str(m.id), "status": "READ"}


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
        from datetime import datetime as _dt

        from app.models import AttendanceException, InternshipCheckin, InternshipRecord, WeeklyReport
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
        today = f"{_dt.now():%Y-%m-%d}"
        today_ck = db.scalars(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
            InternshipCheckin.checkin_date == today, InternshipCheckin.is_deleted.is_(False))).first()
        ck_total = db.scalar(select(func.count()).select_from(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
            InternshipCheckin.is_deleted.is_(False))) or 0
        return {"hasData": True,
                "enterpriseName": rec.enterprise_name or "", "positionName": rec.position_name or "",
                "advisorName": rec.advisor_name or "", "status": rec.status,
                "riskLevel": rec.risk_level,
                "todayCheckin": {"done": bool(today_ck),
                                 "time": _iso(today_ck.checkin_at) if today_ck else None,
                                 "totalDays": int(ck_total)},
                "weeklyReports": [{"week": r.week_number, "status": r.status,
                                   "reviewComment": r.review_comment or ""} for r in reports],
                "attendanceExceptions": [{"type": e.exception_type, "status": e.status,
                                          "date": _iso(e.exception_date)} for e in excs]}


# 毕设阶段流水线（选题→任务书→开题指导→中期→成果→答辩→归档），用于移动端真实节点进度条。
_GD_STAGE_FLOW = [
    ("TOPIC_SELECTING", "选题"),
    ("TASKBOOK_CONFIRM", "任务书"),
    ("GUIDING", "开题与指导"),
    ("MIDTERM", "中期检查"),
    ("FINAL_CHECK", "成果提交"),
    ("DEFENSE", "答辩"),
    ("ARCHIVED", "成绩归档"),
]


def _gd_timeline(stage: str) -> list:
    """按真实 stage 派生节点进度：已过 COMPLETED、当前 PROCESSING(current)、未到 NOT_STARTED。"""
    keys = [k for k, _ in _GD_STAGE_FLOW]
    cur = keys.index(stage) if stage in keys else 0
    nodes = []
    for i, (k, title) in enumerate(_GD_STAGE_FLOW):
        status = "COMPLETED" if i < cur else ("PROCESSING" if i == cur else "NOT_STARTED")
        nodes.append({"id": k, "title": title, "status": status, "current": i == cur})
    return nodes


def graduation_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return _empty()
        from app.models import (GraduationBatch, GraduationFinal, GraduationGuidance,
                                GraduationProposal, GraduationStudent)
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
        # 批次名（真实）：批次不存在时回退阶段前缀，不再返回 mock 固定串
        batch_name = ""
        if g.batch_id:
            b = db.get(GraduationBatch, g.batch_id)
            if b and b.tenant_id == _tid():
                batch_name = b.batch_name or ""
        # 指导记录（真实，最新 5 条）：from=本人指导教师；无记录时前端展示空态，不再用 mock 假记录
        logs = db.scalars(select(GraduationGuidance).where(
            GraduationGuidance.tenant_id == _tid(), GraduationGuidance.gd_student_id == g.id,
            GraduationGuidance.is_deleted.is_(False)).order_by(GraduationGuidance.id.desc()).limit(5)).all()
        guide_logs = [{"id": str(x.id), "date": _iso(x.guidance_date) or _iso(x.created_at) or "",
                       "from": g.advisor_name or "指导教师", "text": x.content or "",
                       "issues": x.issues or ""} for x in logs]
        return {"hasData": True, "topicTitle": g.topic_title or "（未选题）",
                "advisorName": g.advisor_name or "", "stage": g.stage,
                "stageLabel": dict(_GD_STAGE_FLOW).get(g.stage, g.stage),
                "batchName": batch_name, "nodes": _gd_timeline(g.stage), "guideLogs": guide_logs,
                "defenseGroup": g.defense_group or "待分组", "plagiarismRate": g.plagiarism_rate or "—",
                "proposals": [{"version": p.version or "", "status": p.status,
                               "reviewComment": p.review_comment or ""} for p in props],
                "finals": [{"type": f.final_type, "version": f.version or "", "status": f.status,
                            "plagiarismRate": f.plagiarism_rate or "—"} for f in finals]}


def _resolve_gd_student(db, u: dict):
    """解析当前登录学生对应的毕设学生档案 t_gd_student（学号优先，其次姓名）。找不到返回 None。"""
    from app.models import GraduationStudent
    stu = resolve_student(db, u)
    if not stu:
        return None
    g = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(), GraduationStudent.student_no == stu.student_no,
        GraduationStudent.is_deleted.is_(False))).first()
    if not g:
        g = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.name == stu.real_name,
            GraduationStudent.is_deleted.is_(False))).first()
    return g


def graduation_topics(user: dict, batch_id: str | None = None) -> list:
    """选题·浏览可选题目库（已入池「已审核+已确认」且未满员）。"""
    _require_student(user)
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_topic_service as topic_svc
    items, _ = topic_svc.list_topics(1, 500, batch_id=batch_id, review_status="APPROVED",
                                     status="CONFIRMED", is_full=False)
    return items


def graduation_active_round(user: dict) -> dict | None:
    """选题·当前进行中轮次 + 我的当前志愿。"""
    u = _require_student(user)
    if not db_enabled():
        return None
    from app.modules.graduation.services import graduation_topic_round_service as round_svc
    with _session() as db:
        g = _resolve_gd_student(db, u)
    r = round_svc.active_round(batch_id=g.batch_id if g else None)
    if r and g:
        r["gdStudentId"] = str(g.id)
        r["myChoices"] = round_svc.list_choices(r["id"], gd_student_id=g.id)
        r["myCurrentTopicId"] = str(g.topic_id) if g.topic_id else ""
        r["myCurrentTopicTitle"] = g.topic_title or ""
    return r


def graduation_submit_choices(user: dict, round_id: str, choices: list) -> dict:
    """选题·学生本人提交/调整志愿（仅进行中轮次；重复提交自动覆盖上一次，对齐"提交=进入待处理"语义）。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持提交志愿")
    with _session() as db:
        g = _resolve_gd_student(db, u)
    if not g:
        raise AppException("VALIDATION_ERROR", "未找到你的毕设学生档案，请联系毕设管理员")
    from app.modules.graduation.services import graduation_topic_round_service as round_svc
    result = round_svc.submit_choices(round_id, g.id, choices)
    audit_log.record("学生提交选题志愿", f"graduation-topic-round:{round_id}",
                     detail={"studentName": u.get("realName"), "count": result.get("submitted")})
    return result


def graduation_withdraw_choices(user: dict, round_id: str) -> dict:
    """选题·学生本人退选（撤回本轮全部待处理志愿，之后可重新提交）。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持退选")
    with _session() as db:
        g = _resolve_gd_student(db, u)
    if not g:
        raise AppException("VALIDATION_ERROR", "未找到你的毕设学生档案，请联系毕设管理员")
    from app.modules.graduation.services import graduation_topic_round_service as round_svc
    result = round_svc.withdraw_choices(round_id, g.id)
    audit_log.record("学生退选", f"graduation-topic-round:{round_id}",
                     detail={"studentName": u.get("realName"), "withdrawn": result.get("withdrawn")})
    return result


def graduation_request_change(user: dict, new_topic_id: str, reason: str) -> dict:
    """选题·学生本人发起课题变更申请（已有选题、进入指导阶段后换题的唯一合法途径）。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持发起变更申请")
    with _session() as db:
        g = _resolve_gd_student(db, u)
    if not g:
        raise AppException("VALIDATION_ERROR", "未找到你的毕设学生档案，请联系毕设管理员")
    from app.modules.graduation.services import graduation_topic_change_service as change_svc
    result = change_svc.request_change(g.id, new_topic_id, reason, requested_by=u.get("realName") or "学生本人")
    audit_log.record("学生发起选题变更申请", f"graduation-topic-change:{result['id']}",
                     detail={"studentName": u.get("realName")})
    return result


def graduation_my_change_requests(user: dict) -> list:
    """选题·我的历史变更申请。"""
    u = _require_student(user)
    if not db_enabled():
        return []
    with _session() as db:
        g = _resolve_gd_student(db, u)
    if not g:
        return []
    from app.modules.graduation.services import graduation_topic_change_service as change_svc
    items, _ = change_svc.list_change_requests(1, 50, gd_student_id=g.id)
    return items


def graduation_proposal(user: dict) -> dict:
    """开题·查看本人开题报告状态（最新版 + 是否可提交/可重交 + 驳回意见）。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    from app.models import GraduationProposal
    from app.modules.graduation.services import graduation_service as gd_svc
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return _empty("你暂无毕设记录")
        props = db.scalars(select(GraduationProposal).where(
            GraduationProposal.tenant_id == _tid(), GraduationProposal.gd_student_id == g.id,
            GraduationProposal.is_deleted.is_(False)).order_by(GraduationProposal.id.desc())).all()
        latest = props[0] if props else None
        # 已确认选题（有题）才允许提交开题
        can_submit_topic = bool(g.topic_id) or g.stage not in ("TOPIC_SELECTING", None, "")
        # 无记录 → 可首次提交；最新被驳回 → 可重交；待审/已通过 → 不可提交
        can_submit = can_submit_topic and (latest is None or latest.status == "REJECTED")
        return {"hasData": True, "topicTitle": g.topic_title or "（未选题）",
                "canSubmit": can_submit,
                "reason": "" if can_submit_topic else "请先完成选题确认后再提交开题报告",
                "latest": None if not latest else {
                    "id": str(latest.id), "version": latest.version or "", "status": latest.status,
                    "statusLabel": {"PENDING_REVIEW": "待指导教师审阅", "APPROVED": "已通过",
                                    "REJECTED": "已驳回，请修改后重交"}.get(latest.status, latest.status),
                    "reviewComment": latest.review_comment or "", "isResubmit": latest.is_resubmit,
                    "background": latest.background or "", "plan": latest.plan or "",
                    "outcome": latest.outcome or "",
                    "attachmentsList": gd_svc._resolve_attachments(latest.attachments_json or [])},
                "history": [{"version": p.version or "", "status": p.status,
                             "reviewComment": p.review_comment or ""} for p in props]}


def graduation_submit_proposal(user: dict, body: dict) -> dict:
    """开题·学生本人提交/重交开题报告。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持提交开题报告")
    with _session() as db:
        g = _resolve_gd_student(db, u)
    if not g:
        raise AppException("VALIDATION_ERROR", "未找到你的毕设学生档案，请联系毕设管理员")
    from app.modules.graduation.services import graduation_service as gd_svc
    result = gd_svc.submit_proposal(g.id, body.get("background") or "", body.get("plan") or "",
                                    body.get("outcome") or "", body.get("attachments") or [])
    audit_log.record("学生提交开题报告", f"graduation-proposal:{result['id']}",
                     detail={"studentName": u.get("realName"), "version": result.get("version")})
    return result


def graduation_final(user: dict) -> dict:
    """成果·查看本人论文提交状态（可提交初稿/定稿判定 + 各版本 + 退回意见）。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    from app.models import GraduationFinal
    from app.modules.graduation.services import graduation_service as gd_svc
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return _empty("你暂无毕设记录")
        finals = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(), GraduationFinal.gd_student_id == g.id,
            GraduationFinal.is_deleted.is_(False)).order_by(GraduationFinal.id.desc())).all()
        has_pending = any(f.status == "PENDING_REVIEW" for f in finals)
        draft_approved = any(f.final_type == "初稿" and f.status == "APPROVED" for f in finals)
        final_approved = any(f.final_type == "定稿" and f.status == "APPROVED" for f in finals)
        can_draft = not has_pending and not draft_approved
        can_final = not has_pending and draft_approved and not final_approved
        return {"hasData": True, "topicTitle": g.topic_title or "（未选题）",
                "canSubmitDraft": can_draft, "canSubmitFinal": can_final, "finalApproved": final_approved,
                "hint": ("论文已定稿通过" if final_approved else
                         "待指导教师批阅" if has_pending else
                         "可提交定稿" if can_final else "可提交初稿" if can_draft else "初稿待通过"),
                "items": [{"id": str(f.id), "type": f.final_type, "version": f.version or "",
                           "status": f.status, "statusLabel": {"PENDING_REVIEW": "待审阅",
                           "APPROVED": "已通过", "REJECTED": "已退回修改"}.get(f.status, f.status),
                           "reviewComment": f.review_comment or "", "plagiarismRate": f.plagiarism_rate or "—",
                           "attachmentsList": gd_svc._resolve_attachments(f.attachments_json or [])}
                          for f in finals]}


def graduation_submit_final(user: dict, body: dict) -> dict:
    """成果·学生本人提交/重交论文（初稿/定稿）。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持提交成果")
    with _session() as db:
        g = _resolve_gd_student(db, u)
    if not g:
        raise AppException("VALIDATION_ERROR", "未找到你的毕设学生档案，请联系毕设管理员")
    from app.modules.graduation.services import graduation_service as gd_svc
    # The client must never be allowed to declare its own plagiarism result.
    result = gd_svc.submit_final(
        g.id, body.get("finalType") or "初稿", attachments=body.get("attachments") or []
    )
    audit_log.record("学生提交论文成果", f"graduation-final:{result['id']}",
                     detail={"studentName": u.get("realName"), "finalType": result.get("finalType")})
    return result


def graduation_taskbook(user: dict) -> dict:
    """任务书·查看本人任务书（不存在返回 hasData=false）。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return _empty("你暂无毕设记录")
    from app.modules.graduation.services import graduation_taskbook_service as tb_svc
    detail = tb_svc.get_taskbook(g.id)
    if not detail.get("exists"):
        return {"hasData": False, "message": "导师尚未下达任务书"}
    return {"hasData": True, **detail}


def graduation_taskbook_confirm(user: dict) -> dict:
    """任务书·本人确认（含变更后重新确认）。"""
    u = _require_student(user)
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            raise AppException("NOT_FOUND", "你暂无毕设记录")
    from app.modules.graduation.services import graduation_taskbook_service as tb_svc
    return tb_svc.confirm_taskbook(g.id)


def graduation_midterm(user: dict) -> dict:
    """中期检查·查看本人中期检查状态。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return _empty("你暂无毕设记录")
    from app.modules.graduation.services import graduation_midterm_service as mt_svc
    return {"hasData": True, **mt_svc.get_midterm(g.id)}


def graduation_midterm_rectify(user: dict, content: str) -> dict:
    """中期检查·本人提交整改。"""
    u = _require_student(user)
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            raise AppException("NOT_FOUND", "你暂无毕设记录")
    from app.modules.graduation.services import graduation_midterm_service as mt_svc
    return mt_svc.submit_rectification(g.id, content)


def graduation_peer_tasks(user: dict) -> dict:
    """互查·本人待互查任务（我作为互查人）+ 我被互查需整改的记录。"""
    u = _require_student(user)
    if not db_enabled():
        return {"toReview": [], "myRectify": []}
    from app.models import GraduationPeerReview
    from app.modules.graduation.services import graduation_more_service as more
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return {"toReview": [], "myRectify": []}
        as_reviewer = db.scalars(select(GraduationPeerReview).where(
            GraduationPeerReview.tenant_id == _tid(),
            GraduationPeerReview.reviewer_gd_student_id == g.id,
            GraduationPeerReview.is_deleted.is_(False)).order_by(GraduationPeerReview.id.desc())).all()
        return {"toReview": [more._peer_row(db, p) for p in as_reviewer if p.status == "ASSIGNED"],
                "myRectify": [more._peer_row(db, p) for p in db.scalars(select(GraduationPeerReview).where(
                    GraduationPeerReview.tenant_id == _tid(), GraduationPeerReview.gd_student_id == g.id,
                    GraduationPeerReview.status == "REVIEWED",
                    GraduationPeerReview.is_deleted.is_(False))).all()]}


def graduation_peer_submit(user: dict, pid: str, opinion: str) -> dict:
    """互查·学生提交互查意见。"""
    _require_student(user)
    from app.modules.graduation.services import graduation_more_service as more
    result = more.submit_peer(pid, opinion)
    audit_log.record("学生提交互查意见", f"graduation-peer:{pid}")
    return result


def graduation_peer_rectify(user: dict, pid: str, note: str) -> dict:
    """互查·被评学生提交整改。"""
    _require_student(user)
    from app.modules.graduation.services import graduation_more_service as more
    result = more.rectify_peer(pid, note)
    audit_log.record("学生提交互查整改", f"graduation-peer:{pid}")
    return result


def graduation_grade_appeal(user: dict, reason: str) -> dict:
    """成绩·学生对已发布成绩发起更正申诉。"""
    u = _require_student(user)
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            raise AppException("NOT_FOUND", "你暂无毕设记录")
        gid = g.id
    from app.modules.graduation.services import graduation_more_service as more
    result = more.create_appeal(gid, reason)
    audit_log.record("学生发起成绩申诉", f"graduation-grade-appeal:{result['id']}")
    return result


def graduation_defense(user: dict) -> dict:
    """答辩·查看本人答辩安排（仅已发布展示时间/地点/评委）。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return _empty("你暂无毕设记录")
    from app.modules.graduation.services import graduation_service as gd_svc
    return gd_svc.student_defense_view(g.id)


def graduation_grade(user: dict) -> dict:
    """成绩·查看本人已发布成绩（未发布不展示分数明细，仅提示流转中）。"""
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        g = _resolve_gd_student(db, u)
        if not g:
            return _empty("你暂无毕设记录")
    from app.modules.graduation.services import graduation_grade_service as grade_svc
    detail = grade_svc.get_grade(g.id)
    if detail.get("status") != "PUBLISHED":
        return {"hasData": True, "published": False, "statusLabel": detail.get("statusLabel")}
    return {"hasData": True, "published": True, **detail}


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
        # 防重复提交：同一学生同一服务、相同事由且仍在待处理，视为重复（409）
        pending_leave = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.cs_student_id == cs.id,
            CsLeave.is_deleted.is_(False), CsLeave.status == "PENDING_REVIEW",
            CsLeave.reason == content)).first()
        pending_wo = db.scalars(select(CsWorkOrder).where(
            CsWorkOrder.tenant_id == _tid(), CsWorkOrder.cs_student_id == cs.id,
            CsWorkOrder.is_deleted.is_(False), CsWorkOrder.status == "PENDING_HANDLE",
            CsWorkOrder.title == service_key, CsWorkOrder.detail == content)).first()
        if pending_leave or pending_wo:
            raise AppException("DATA_CONFLICT", "相同申请已提交且仍在处理中，请勿重复提交")
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


def internship_checkin(user: dict, body: dict) -> dict:
    """实习每日打卡（真实落库）：一天一次（唯一约束兜底并发 409）。
    企业围栏未配置阶段 result=RECORDED/NO_LOCATION，定位仅留痕不作弊性判定。"""
    u = _require_student(user)
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实打卡")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        from datetime import datetime as _dt

        from app.models import InternshipCheckin, InternshipRecord
        rec = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
            InternshipRecord.is_deleted.is_(False))).first()
        if not rec:
            raise AppException("DATA_NOT_FOUND", "你当前没有实习记录，无法打卡")
        today = f"{_dt.now():%Y-%m-%d}"
        dup = db.scalars(select(InternshipCheckin).where(
            InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
            InternshipCheckin.checkin_date == today, InternshipCheckin.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "今日已打卡，请勿重复打卡")

        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        lat, lng = _f(body.get("lat")), _f(body.get("lng"))
        row = InternshipCheckin(tenant_id=_tid(), internship_id=rec.id, checkin_date=today,
                                checkin_at=_dt.utcnow(), lat=lat, lng=lng,
                                address=str(body.get("address") or "")[:300] or None,
                                result="RECORDED" if (lat is not None and lng is not None) else "NO_LOCATION",
                                note=str(body.get("note") or "")[:500] or None)
        db.add(row)
        try:
            db.flush()
            rid, result = row.id, row.result
            db.commit()
        except Exception as exc:  # 并发重复打卡：唯一约束兜底 → 409
            db.rollback()
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError):
                raise AppException("DATA_CONFLICT", "今日已打卡，请勿重复打卡")
            raise
    audit_log.record("MOBILE_CHECKIN", f"internship:checkin:{today}",
                     {"studentNo": u.get("studentNo"), "result": result})
    return {"id": str(rid), "date": today, "result": result,
            "message": "打卡成功" + ("" if result == "RECORDED" else "（未获取到定位，仅记录时间）")}


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
        try:
            db.flush()
            wid, status = w.id, w.status
            db.commit()
        except Exception as exc:  # 并发重复提交：唯一约束兜底 → 409（绝不 500）
            db.rollback()
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError):
                raise AppException("DATA_CONFLICT", f"第 {week_no} 周周报已提交，请勿重复提交")
            raise
    audit_log.record("MOBILE_WEEKLY_SUBMIT", f"internship:week{week_no}",
                     {"studentNo": u.get("studentNo"), "weekNo": week_no})
    return {"id": str(wid), "status": status, "message": "周报提交成功"}


# ─────────── 实习意向（学生本人填报，对接岗位匹配） ───────────

def _internship_record(db, u: dict):
    from app.models import InternshipRecord
    stu = resolve_student(db, u)
    if not stu:
        return None, None
    rec = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
        InternshipRecord.is_deleted.is_(False))).first()
    return rec, stu


def _active_intention(db, record_id: int):
    from app.models import InternshipIntention
    return db.scalars(select(InternshipIntention).where(
        InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
        InternshipIntention.record_id == record_id,
        InternshipIntention.status.in_(("DRAFT", "SUBMITTED"))
    ).order_by(InternshipIntention.id.desc())).first()


def _published_positions(db, batch_id, limit: int = 40) -> list[dict]:
    from app.models import EmpCompany, InternshipPosition
    q = select(InternshipPosition).where(
        InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False),
        InternshipPosition.status == "PUBLISHED")
    if batch_id:
        q = q.where(
            (InternshipPosition.batch_id == batch_id) | (InternshipPosition.batch_id.is_(None)))
    rows = db.scalars(q.order_by(InternshipPosition.id.desc()).limit(limit)).all()
    out = []
    for p in rows:
        company = db.get(EmpCompany, p.company_id) if p.company_id else None
        head = p.headcount or 0
        alloc = p.allocated_count or 0
        out.append({
            "id": str(p.id),
            "title": p.title or "",
            "companyName": company.name if company else "",
            "workLocation": p.work_location or "",
            "remaining": max(0, head - alloc),
        })
    return out


def internship_intention_my(user: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        return _empty("演示模式")
    with _session() as db:
        rec, _ = _internship_record(db, u)
        if not rec:
            return _empty("你暂无实习档案，暂无法填报意向")
        it = _active_intention(db, rec.id)
        intention = None
        if it:
            from app.modules.internship.services.internship_match_service import _intention_row
            intention = _intention_row(db, it)
        return {
            "hasData": True,
            "recordId": str(rec.id),
            "intention": intention,
            "positions": _published_positions(db, rec.batch_id),
            "canEdit": (not it) or it.status == "DRAFT",
            "canSubmit": bool(it) and it.status == "DRAFT",
            "canWithdraw": bool(it) and it.status == "SUBMITTED",
        }


def internship_intention_save(user: dict, body: dict) -> dict:
    from types import SimpleNamespace

    from app.core.exceptions import no_permission
    from app.modules.internship.schemas.internship_match import IntentionUpdate
    from app.modules.internship.services import internship_match_service as match_svc

    u = _require_student(user)
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "演示模式不可用")
    b = body or {}
    record_id = None
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            raise AppException("NOT_FOUND", "你暂无实习档案")
        it = _active_intention(db, rec.id)
        if it and it.status == "SUBMITTED":
            raise AppException("DATA_CONFLICT", "已提交意向不可编辑，请先撤回后再修改")
        if it and it.status == "DRAFT":
            if it.student_id != stu.id:
                raise no_permission("只能编辑本人的实习意向")
            upd = IntentionUpdate(
                preferredCity=b.get("preferredCity"),
                preferredIndustry=b.get("preferredIndustry"),
                preferredCompanyId=b.get("preferredCompanyId"),
                preferredPositionId=b.get("preferredPositionId"),
                intentionNote=b.get("intentionNote"),
            )
            result = match_svc.update_intention(str(it.id), upd)
            audit_log.record("MOBILE_INTENTION_SAVE", f"internship:intention:{it.id}",
                             {"studentNo": u.get("studentNo")})
            return result
        record_id = str(rec.id)
    payload = SimpleNamespace(
        recordId=record_id,
        preferredCity=(b.get("preferredCity") or "").strip() or None,
        preferredIndustry=(b.get("preferredIndustry") or "").strip() or None,
        preferredCompanyId=b.get("preferredCompanyId") or None,
        preferredPositionId=b.get("preferredPositionId") or None,
        intentionNote=(b.get("intentionNote") or "").strip() or None,
    )
    result = match_svc.create_intention(payload)
    audit_log.record("MOBILE_INTENTION_CREATE", f"internship:intention:{result['id']}",
                     {"studentNo": u.get("studentNo")})
    return result


def internship_intention_submit(user: dict) -> dict:
    from app.core.exceptions import no_permission
    from app.modules.internship.services import internship_match_service as match_svc

    u = _require_student(user)
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "演示模式不可用")
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            raise AppException("NOT_FOUND", "你暂无实习档案")
        it = _active_intention(db, rec.id)
        if not it or it.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "当前没有可提交的草稿意向")
        if it.student_id != stu.id:
            raise no_permission("只能提交本人的实习意向")
        iid = str(it.id)
    result = match_svc.submit_intention(iid)
    audit_log.record("MOBILE_INTENTION_SUBMIT", f"internship:intention:{iid}",
                     {"studentNo": u.get("studentNo")})
    return result


def internship_intention_withdraw(user: dict) -> dict:
    from app.core.exceptions import no_permission
    from app.modules.internship.services import internship_match_service as match_svc

    u = _require_student(user)
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "演示模式不可用")
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            raise AppException("NOT_FOUND", "你暂无实习档案")
        it = _active_intention(db, rec.id)
        if not it or it.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "当前没有可撤回的已提交意向")
        if it.student_id != stu.id:
            raise no_permission("只能撤回本人的实习意向")
        iid = str(it.id)
    result = match_svc.withdraw_intention(iid)
    audit_log.record("MOBILE_INTENTION_WITHDRAW", f"internship:intention:{iid}",
                     {"studentNo": u.get("studentNo")})
    return result


# ─────────── 过程报告（日报/月报/实习总结）───────────

def internship_process_report_submit(user: dict, body: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "演示模式不可用")
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            raise AppException("NOT_FOUND", "你暂无实习档案，无法提交")
    from app.modules.internship.services import internship_process_report_service as pr
    result = pr.student_submit(rec, body.get("reportType"), body.get("periodKey"), body.get("content"))
    audit_log.record("MOBILE_PROCESS_REPORT", f"internship:process:{body.get('reportType')}",
                     {"studentNo": u.get("studentNo"), "periodKey": body.get("periodKey")})
    return result


# ─────────── 实习变更（换岗/换单位/自主实习）───────────

def internship_change_list(user: dict) -> list:
    u = _require_student(user)
    if not db_enabled():
        return []
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            return []
    from app.modules.internship.services import internship_change_service as chg
    return chg.list_my_changes(rec, stu)


def internship_change_apply(user: dict, body: dict) -> dict:
    u = _require_student(user)
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "演示模式不可用")
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            raise AppException("NOT_FOUND", "你暂无实习档案")
    from app.modules.internship.services import internship_change_service as chg
    return chg.student_apply(rec, stu, body)


def internship_change_withdraw(user: dict, change_id: str) -> dict:
    u = _require_student(user)
    if not db_enabled():
        raise AppException("SERVICE_UNAVAILABLE", "演示模式不可用")
    with _session() as db:
        rec, stu = _internship_record(db, u)
        if not rec:
            raise AppException("NOT_FOUND", "你暂无实习档案")
    from app.modules.internship.services import internship_change_service as chg
    return chg.withdraw_change(change_id, rec, stu)
