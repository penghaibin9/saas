"""学业过程域真实数据服务。租户过滤 + 脱敏 + 审计留痕 + 预警闭环。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (AcademicAuditTrail, AcademicGrade, AcademicIntervention, AcademicMakeup,
                        AcademicRetake, AcademicStudent, AcademicWarning)
from app.services.db_service import _iso, _mask_phone, _tid, session

L_WARN_T = {"MULTI_FAIL": "多门挂科", "CREDIT_GAP": "学分不足", "GRADE_DROP": "成绩持续下滑",
            "ATTENDANCE": "出勤异常", "GRAD_RISK": "毕业资格风险"}
L_LEVEL = {"NONE": "无", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
L_WARN_S = {"PENDING_HANDLE": "待处理", "PROCESSING": "跟进中", "CLOSED": "已关闭", "ESCALATED": "已升级"}
L_ACAD_S = {"NORMAL": "正常", "WARNING": "预警中", "HELPING": "帮扶中"}
L_PASS = {"PASSED": "通过", "FAILED": "未通过", "PENDING": "待发布"}
L_EXAM = {"FINAL": "期末考试", "MAKEUP": "补考", "RETAKE": "重修考核"}
L_NATURE = {"REQUIRED": "必修", "ELECTIVE": "选修", "PRACTICE": "实践"}
L_MK_S = {"PENDING_EXAM": "待补考", "PASSED": "补考通过", "FAILED": "补考未过", "ABSENT": "缺考"}
L_RT_S = {"ENROLLING": "报名中", "STUDYING": "修读中", "PASSED": "重修通过", "FAILED": "重修未过"}
L_WAY = {"TALK": "当面谈话", "PHONE": "电话联系", "FAMILY": "家校联系", "PLAN": "帮扶计划"}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, bt, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(AcademicAuditTrail(tenant_id=_tid(), biz_type=bt, biz_id=str(bid), action=action,
                              operator=n, role_name=r, detail=detail, before_val=before,
                              after_val=after, occurred_at=datetime.utcnow()))


def _page(items, page, ps):
    total = len(items)
    start = (max(1, page) - 1) * ps
    return items[start:start + ps], total


def _num(v):
    return float(v or 0)


def _get_stu(db, sid) -> AcademicStudent:
    s = db.get(AcademicStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("学业记录不存在或不在当前数据范围内")
    return s


def _stu_of(db, sid):
    return db.get(AcademicStudent, sid)


def _stu_row(s: AcademicStudent) -> dict:
    return {"id": str(s.id), "studentId": str(s.student_id or s.id), "studentNo": s.student_no or "",
            "name": s.name, "classId": s.class_id or "", "className": s.class_name or "",
            "collegeName": s.college_name or "", "majorName": s.major_name or "", "grade": s.grade or "",
            "phone": _mask_phone(s.phone_encrypted), "counselor": s.counselor or "",
            "gpa": _num(s.gpa), "avgScore": s.avg_score, "failedCount": s.failed_count,
            "obtainedCredits": _num(s.obtained_credits), "requiredCredits": _num(s.required_credits),
            "makeupCount": s.makeup_count, "retakeCount": s.retake_count,
            "warningLevel": s.warning_level, "warningLabel": L_LEVEL.get(s.warning_level, s.warning_level),
            "warningCount": s.warning_count, "academicStatus": s.academic_status,
            "academicStatusLabel": L_ACAD_S.get(s.academic_status, s.academic_status),
            "recordStatus": s.record_status, "updateTime": _iso(s.updated_at)}


# ═══ 学生台账 ═══

def list_students(page, ps, keyword=None, class_id=None, warning_level=None, academic_status=None):
    with session() as db:
        q = select(AcademicStudent).where(AcademicStudent.tenant_id == _tid(),
                                          AcademicStudent.is_deleted.is_(False),
                                          AcademicStudent.record_status == "ACTIVE")
        if class_id:
            q = q.where(AcademicStudent.class_id == class_id)
        if warning_level:
            q = q.where(AcademicStudent.warning_level == warning_level)
        if academic_status:
            q = q.where(AcademicStudent.academic_status == academic_status)
        rows = db.scalars(q.order_by(AcademicStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.student_no or "")]
        return _page([_stu_row(r) for r in rows], page, ps)


def get_student_detail(sid) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        grades = db.scalars(select(AcademicGrade).where(AcademicGrade.tenant_id == _tid(),
                            AcademicGrade.acad_student_id == s.id,
                            AcademicGrade.is_deleted.is_(False)).order_by(AcademicGrade.id.desc())).all()
        makeups = db.scalars(select(AcademicMakeup).where(AcademicMakeup.tenant_id == _tid(),
                             AcademicMakeup.acad_student_id == s.id).order_by(AcademicMakeup.id.desc())).all()
        retakes = db.scalars(select(AcademicRetake).where(AcademicRetake.tenant_id == _tid(),
                             AcademicRetake.acad_student_id == s.id).order_by(AcademicRetake.id.desc())).all()
        warns = db.scalars(select(AcademicWarning).where(AcademicWarning.tenant_id == _tid(),
                           AcademicWarning.acad_student_id == s.id,
                           AcademicWarning.is_deleted.is_(False)).order_by(AcademicWarning.id.desc())).all()
        logs = db.scalars(select(AcademicAuditTrail).where(AcademicAuditTrail.tenant_id == _tid(),
                          AcademicAuditTrail.biz_id == str(s.id)).order_by(AcademicAuditTrail.id.desc()).limit(20)).all()
        return {"student": _stu_row(s),
                "grades": [_grade_row(x, s) for x in grades],
                "credit": {"obtained": _num(s.obtained_credits), "required": _num(s.required_credits),
                           "gap": max(0.0, _num(s.required_credits) - _num(s.obtained_credits))},
                "makeups": [_mk_row(x, s) for x in makeups],
                "retakes": [_rt_row(x, s) for x in retakes],
                "warnings": [_warn_row(x, s) for x in warns],
                "auditLogs": [_log_row(x) for x in logs]}


def create_student(body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    no = str(body.get("studentNo") or "").strip()
    if not name or not no:
        raise AppException("VALIDATION_ERROR", "姓名与学号必填")
    with session() as db:
        dup = db.scalars(select(AcademicStudent).where(AcademicStudent.tenant_id == _tid(),
                         AcademicStudent.student_no == no, AcademicStudent.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"学号 {no} 已存在")
        s = AcademicStudent(tenant_id=_tid(), name=name, student_no=no, class_id=body.get("classId"),
                            class_name=body.get("className"), counselor=body.get("counselor"),
                            phone_encrypted=body.get("phone"),
                            obtained_credits=body.get("obtainedCredits") or 0,
                            required_credits=body.get("requiredCredits") or 120)
        db.add(s)
        db.flush()
        _audit(db, "RECORD", s.id, "新增学业记录", f"{name}（{no}）")
        db.commit()
        return {"id": str(s.id)}


def update_student(sid, body: dict) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        for k, col in {"name": "name", "classId": "class_id", "className": "class_name",
                       "counselor": "counselor"}.items():
            if body.get(k) is not None:
                setattr(s, col, body[k])
        if body.get("obtainedCredits") is not None:
            s.obtained_credits = body["obtainedCredits"]
        s.version += 1
        _audit(db, "RECORD", s.id, "编辑学业记录")
        db.commit()
        return {"id": str(s.id)}


def void_student(sid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        s = _get_stu(db, sid)
        s.record_status = "VOIDED"
        s.void_reason = reason.strip()
        s.is_deleted = True
        s.version += 1
        _audit(db, "RECORD", s.id, "作废学业记录", reason.strip())
        db.commit()
        return {"id": str(s.id)}


# ═══ 成绩 ═══

def _grade_row(x: AcademicGrade, stu=None) -> dict:
    return {"id": str(x.id), "studentId": str(x.acad_student_id), "name": stu.name if stu else "",
            "className": stu.class_name if stu else "", "courseName": x.course_name, "term": x.term or "",
            "nature": x.nature, "natureLabel": L_NATURE.get(x.nature, x.nature),
            "creditValue": _num(x.credit_value), "score": x.score,
            "passStatus": x.pass_status, "passStatusLabel": L_PASS.get(x.pass_status, x.pass_status),
            "examType": x.exam_type, "examTypeLabel": L_EXAM.get(x.exam_type, x.exam_type),
            "recordStatus": x.record_status, "updateTime": _iso(x.updated_at)}


def _pass_of(score):
    if score is None:
        return "PENDING"
    return "PASSED" if score >= 60 else "FAILED"


def list_grades(page, ps, keyword=None, term=None, pass_status=None, exam_type=None):
    with session() as db:
        q = select(AcademicGrade).where(AcademicGrade.tenant_id == _tid(),
                                        AcademicGrade.is_deleted.is_(False))
        if term:
            q = q.where(AcademicGrade.term == term)
        if pass_status:
            q = q.where(AcademicGrade.pass_status == pass_status)
        if exam_type:
            q = q.where(AcademicGrade.exam_type == exam_type)
        rows = db.scalars(q.order_by(AcademicGrade.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.acad_student_id)
            if keyword and (not stu or (keyword.strip() not in (stu.name or "") and keyword.strip() not in x.course_name)):
                continue
            items.append(_grade_row(x, stu))
        return _page(items, page, ps)


def create_grade(body: dict) -> dict:
    if not body.get("studentId") or not body.get("courseName"):
        raise AppException("VALIDATION_ERROR", "学生、课程必填")
    score = body.get("score")
    with session() as db:
        s = _get_stu(db, body["studentId"])
        g = AcademicGrade(tenant_id=_tid(), acad_student_id=s.id, course_name=body["courseName"],
                          term=body.get("term"), nature=body.get("nature") or "REQUIRED",
                          credit_value=body.get("creditValue") or 0, score=score,
                          pass_status=_pass_of(score), exam_type=body.get("examType") or "FINAL")
        db.add(g)
        db.flush()
        _audit(db, "GRADE", g.id, "新增成绩", f"{s.name} {body['courseName']} {score}")
        db.commit()
        return {"id": str(g.id)}


def update_grade(gid, score, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "成绩变更原因必填且不少于 5 字")
    if score is None or not (0 <= int(score) <= 100):
        raise AppException("VALIDATION_ERROR", "成绩需为 0~100 的整数")
    with session() as db:
        g = db.get(AcademicGrade, int(gid))
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("成绩记录不存在")
        before = f"{g.score}/{g.pass_status}"
        g.score = int(score)
        g.pass_status = _pass_of(int(score))
        g.version += 1
        _audit(db, "GRADE", g.id, "成绩变更", reason.strip(), before, f"{g.score}/{g.pass_status}")
        db.commit()
        return {"id": str(g.id)}


def void_grade(gid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        g = db.get(AcademicGrade, int(gid))
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("成绩记录不存在")
        g.record_status = "VOIDED"
        g.void_reason = reason.strip()
        g.is_deleted = True
        g.version += 1
        _audit(db, "GRADE", g.id, "作废成绩", reason.strip())
        db.commit()
        return {"id": str(g.id)}


# ═══ 补考 / 重修 ═══

def _mk_row(x: AcademicMakeup, stu=None) -> dict:
    return {"id": str(x.id), "studentId": str(x.acad_student_id), "name": stu.name if stu else "",
            "className": stu.class_name if stu else "", "courseName": x.course_name, "term": x.term or "",
            "originScore": x.origin_score, "examDate": x.exam_date or "待安排",
            "status": x.status, "statusLabel": L_MK_S.get(x.status, x.status),
            "remindCount": x.remind_count, "recordStatus": x.record_status}


def list_makeups(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(AcademicMakeup).where(AcademicMakeup.tenant_id == _tid(),
                                         AcademicMakeup.is_deleted.is_(False),
                                         AcademicMakeup.record_status == "ACTIVE")
        if status:
            q = q.where(AcademicMakeup.status == status)
        rows = db.scalars(q.order_by(AcademicMakeup.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.acad_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_mk_row(x, stu))
        return _page(items, page, ps)


def create_makeup(body: dict) -> dict:
    if not body.get("studentId") or not body.get("courseName"):
        raise AppException("VALIDATION_ERROR", "学生、课程必填")
    with session() as db:
        s = _get_stu(db, body["studentId"])
        m = AcademicMakeup(tenant_id=_tid(), acad_student_id=s.id, course_name=body["courseName"],
                           term=body.get("term"), origin_score=body.get("originScore"),
                           exam_date=body.get("examDate"), status="PENDING_EXAM")
        db.add(m)
        s.makeup_count = (s.makeup_count or 0) + 1
        db.flush()
        _audit(db, "MAKEUP", m.id, "新增补考", f"{s.name} {body['courseName']}")
        db.commit()
        return {"id": str(m.id)}


def update_makeup_status(mid, status) -> dict:
    if status not in ("PENDING_EXAM", "PASSED", "FAILED", "ABSENT"):
        raise AppException("VALIDATION_ERROR", "非法补考状态")
    with session() as db:
        m = db.get(AcademicMakeup, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("补考记录不存在")
        before = m.status
        m.status = status
        m.version += 1
        _audit(db, "MAKEUP", m.id, "更新补考状态", "", before, status)
        db.commit()
        return {"id": str(m.id), "status": status}


def _rt_row(x: AcademicRetake, stu=None) -> dict:
    return {"id": str(x.id), "studentId": str(x.acad_student_id), "name": stu.name if stu else "",
            "className": stu.class_name if stu else "", "courseName": x.course_name,
            "retakeTerm": x.retake_term or "", "reason": x.reason or "",
            "status": x.status, "statusLabel": L_RT_S.get(x.status, x.status),
            "recordStatus": x.record_status}


def list_retakes(page, ps, keyword=None, status=None):
    with session() as db:
        q = select(AcademicRetake).where(AcademicRetake.tenant_id == _tid(),
                                         AcademicRetake.is_deleted.is_(False),
                                         AcademicRetake.record_status == "ACTIVE")
        if status:
            q = q.where(AcademicRetake.status == status)
        rows = db.scalars(q.order_by(AcademicRetake.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.acad_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_rt_row(x, stu))
        return _page(items, page, ps)


def update_retake_status(rid, status) -> dict:
    if status not in ("ENROLLING", "STUDYING", "PASSED", "FAILED"):
        raise AppException("VALIDATION_ERROR", "非法重修状态")
    with session() as db:
        r = db.get(AcademicRetake, int(rid))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("重修记录不存在")
        before = r.status
        r.status = status
        r.version += 1
        _audit(db, "MAKEUP", r.id, "更新重修状态", "", before, status)
        db.commit()
        return {"id": str(r.id), "status": status}


# ═══ 学分（只读聚合）═══

def list_credits(page, ps, keyword=None, status=None):
    with session() as db:
        rows = db.scalars(select(AcademicStudent).where(AcademicStudent.tenant_id == _tid(),
                          AcademicStudent.is_deleted.is_(False),
                          AcademicStudent.record_status == "ACTIVE").order_by(AcademicStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "")]
        items = []
        for s in rows:
            obt = _num(s.obtained_credits)
            req = _num(s.required_credits)
            gap = max(0.0, req - obt)
            st = "ON_TRACK" if obt >= req / 2 else ("SEVERE" if gap >= 6 else "BEHIND")
            if status and st != status:
                continue
            items.append({"id": str(s.id), "studentId": str(s.id), "name": s.name,
                          "className": s.class_name or "", "obtained": obt, "required": req,
                          "gap": gap, "status": st,
                          "statusLabel": {"ON_TRACK": "达标", "BEHIND": "滞后", "SEVERE": "严重滞后"}[st]})
        return _page(items, page, ps)


# ═══ 预警（核心闭环）═══

def _warn_row(x: AcademicWarning, stu=None) -> dict:
    return {"id": str(x.id), "code": x.code or "", "studentId": str(x.acad_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "type": x.warn_type, "typeLabel": L_WARN_T.get(x.warn_type, x.warn_type),
            "level": x.level, "levelLabel": L_LEVEL.get(x.level, x.level), "reason": x.reason or "",
            "sourceRule": x.source_rule or "", "owner": x.owner or "",
            "status": x.status, "statusLabel": L_WARN_S.get(x.status, x.status),
            "triggerTime": _iso(x.trigger_time) or "", "deadline": x.deadline or "",
            "remindCount": x.remind_count, "closeResult": x.close_result or "",
            "recordStatus": x.record_status}


def list_warnings(page, ps, keyword=None, type=None, level=None, status=None, class_id=None):
    with session() as db:
        q = select(AcademicWarning).where(AcademicWarning.tenant_id == _tid(),
                                          AcademicWarning.is_deleted.is_(False),
                                          AcademicWarning.record_status == "ACTIVE")
        if type:
            q = q.where(AcademicWarning.warn_type == type)
        if level:
            q = q.where(AcademicWarning.level == level)
        if status:
            q = q.where(AcademicWarning.status == status)
        rows = db.scalars(q.order_by(AcademicWarning.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.acad_student_id)
            if class_id and (not stu or stu.class_id != class_id):
                continue
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_warn_row(x, stu))
        return _page(items, page, ps)


def get_warning_detail(wid) -> dict:
    with session() as db:
        x = db.get(AcademicWarning, int(wid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("预警不存在")
        stu = _stu_of(db, x.acad_student_id)
        itvs = db.scalars(select(AcademicIntervention).where(AcademicIntervention.tenant_id == _tid(),
                          AcademicIntervention.warning_id == x.id).order_by(AcademicIntervention.id.desc())).all()
        return {"warning": _warn_row(x, stu), "student": _stu_row(stu) if stu else None,
                "interventions": [{"id": str(i.id), "time": _iso(i.follow_time), "way": i.way,
                                   "wayLabel": L_WAY.get(i.way, i.way), "content": i.content or "",
                                   "result": i.result or "", "nextPlan": i.next_plan or "",
                                   "operator": i.operator or "", "status": i.status} for i in itvs]}


def _sync_student_warning(db, stu):
    db.flush()  # 让内存中刚改的预警状态（如关闭/作废）对下面的查询可见（autoflush=False）
    active = db.scalars(select(AcademicWarning).where(AcademicWarning.tenant_id == _tid(),
             AcademicWarning.acad_student_id == stu.id, AcademicWarning.is_deleted.is_(False),
             AcademicWarning.status.in_(["PENDING_HANDLE", "PROCESSING", "ESCALATED"]))).all()
    stu.warning_count = len(active)
    if not active:
        stu.warning_level = "NONE"
        stu.academic_status = "NORMAL"
    else:
        order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        stu.warning_level = max((a.level for a in active), key=lambda x: order.get(x, 0))
        stu.academic_status = "HELPING" if any(a.status == "ESCALATED" for a in active) else "WARNING"


def create_warning(body: dict) -> dict:
    reason = str(body.get("reason") or "").strip()
    if not body.get("studentId") or not body.get("type") or len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "学生、类型必填，原因不少于 5 字")
    with session() as db:
        s = _get_stu(db, body["studentId"])
        code = f"AW-{datetime.now():%Y}-{db.scalar(select(func.count()).select_from(AcademicWarning).where(AcademicWarning.tenant_id == _tid())) + 1:04d}"
        w = AcademicWarning(tenant_id=_tid(), acad_student_id=s.id, warn_type=body["type"],
                            level=body.get("level") or "MEDIUM", reason=reason, code=code,
                            owner=body.get("owner"), status="PENDING_HANDLE",
                            trigger_time=datetime.utcnow(), deadline=body.get("deadline"),
                            source_rule=body.get("sourceRule"))
        db.add(w)
        db.flush()
        _sync_student_warning(db, s)
        _audit(db, "WARNING", w.id, "新增预警", reason)
        db.commit()
        return {"id": str(w.id), "code": code}


def _get_warn(db, wid):
    w = db.get(AcademicWarning, int(wid))
    if not w or w.is_deleted or w.tenant_id != _tid():
        raise not_found("预警不存在")
    return w


def update_warning_level(wid, level, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因必填且不少于 5 字")
    if level not in ("LOW", "MEDIUM", "HIGH"):
        raise AppException("VALIDATION_ERROR", "非法风险等级")
    with session() as db:
        w = _get_warn(db, wid)
        before = w.level
        w.level = level
        w.version += 1
        s = _stu_of(db, w.acad_student_id)
        if s:
            _sync_student_warning(db, s)
        _audit(db, "WARNING", w.id, "调整预警等级", reason.strip(), before, level)
        db.commit()
        return {"id": str(w.id)}


def void_warning(wid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "误报原因必填且不少于 5 字")
    with session() as db:
        w = _get_warn(db, wid)
        w.record_status = "VOIDED"
        w.void_reason = reason.strip()
        w.is_deleted = True
        w.version += 1
        s = _stu_of(db, w.acad_student_id)
        if s:
            _sync_student_warning(db, s)
        _audit(db, "WARNING", w.id, "作废预警", reason.strip())
        db.commit()
        return {"id": str(w.id)}


def assign_warnings(ids, owner_name, owner_id=None) -> dict:
    if not owner_name:
        raise AppException("VALIDATION_ERROR", "跟进人必填")
    cnt = 0
    with session() as db:
        for wid in ids:
            w = db.get(AcademicWarning, int(wid))
            if not w or w.is_deleted or w.tenant_id != _tid():
                continue
            w.owner = owner_name
            if w.status == "PENDING_HANDLE":
                w.status = "PROCESSING"
                s = _stu_of(db, w.acad_student_id)
                if s:
                    _sync_student_warning(db, s)
            w.version += 1
            _audit(db, "WARNING", w.id, "分配跟进人", owner_name)
            cnt += 1
        db.commit()
        return {"count": cnt}


def remind_warnings(ids) -> dict:
    cnt = 0
    with session() as db:
        for wid in ids:
            w = db.get(AcademicWarning, int(wid))
            if not w or w.is_deleted or w.tenant_id != _tid():
                continue
            w.remind_count = (w.remind_count or 0) + 1
            _audit(db, "WARNING", w.id, "预警提醒")
            cnt += 1
        db.commit()
        return {"count": cnt}


def create_intervention(wid, body: dict) -> dict:
    content = str(body.get("content") or "").strip()
    if len(content) < 5:
        raise AppException("VALIDATION_ERROR", "跟进内容必填且不少于 5 字")
    with session() as db:
        w = _get_warn(db, wid)
        n, _ = _op()
        i = AcademicIntervention(tenant_id=_tid(), warning_id=w.id, way=body.get("way") or "TALK",
                                 content=content, result=body.get("result"), next_plan=body.get("nextPlan"),
                                 operator=n, status="OPEN", follow_time=datetime.utcnow())
        db.add(i)
        if w.status == "PENDING_HANDLE":
            w.status = "PROCESSING"
            s = _stu_of(db, w.acad_student_id)
            if s:
                _sync_student_warning(db, s)
        _audit(db, "INTERVENTION", w.id, "新增干预", content)
        db.commit()
        db.refresh(i)
        return {"id": str(i.id)}


def close_warning(wid, result) -> dict:
    if not result or len(result.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭说明必填且不少于 5 字")
    with session() as db:
        w = _get_warn(db, wid)
        if w.status == "CLOSED":
            raise AppException("DATA_CONFLICT", "该预警已关闭")
        before = w.status
        w.status = "CLOSED"
        w.close_result = result.strip()
        w.version += 1
        s = _stu_of(db, w.acad_student_id)
        if s:
            _sync_student_warning(db, s)
        _audit(db, "WARNING", w.id, "关闭预警", result.strip(), before, "CLOSED")
        db.commit()
        return {"id": str(w.id)}


def escalate_warning(wid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "升级说明必填且不少于 5 字")
    with session() as db:
        w = _get_warn(db, wid)
        before = w.status
        w.status = "ESCALATED"
        w.level = "HIGH"
        w.owner = "学院学业帮扶专班"
        w.version += 1
        s = _stu_of(db, w.acad_student_id)
        if s:
            _sync_student_warning(db, s)
        _audit(db, "WARNING", w.id, "升级预警", reason.strip(), before, "ESCALATED")
        db.commit()
        return {"id": str(w.id)}


# ═══ 审计 + 看板 ═══

def _log_row(x: AcademicAuditTrail) -> dict:
    return {"id": str(x.id), "time": _iso(x.occurred_at), "operator": x.operator or "",
            "roleName": x.role_name or "", "bizType": x.biz_type, "bizId": x.biz_id or "",
            "action": x.action, "detail": x.detail or "", "before": x.before_val or "",
            "after": x.after_val or ""}


def list_audit(page, ps, biz_type=None, keyword=None):
    with session() as db:
        q = select(AcademicAuditTrail).where(AcademicAuditTrail.tenant_id == _tid())
        if biz_type:
            q = q.where(AcademicAuditTrail.biz_type == biz_type)
        rows = db.scalars(q.order_by(AcademicAuditTrail.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.action or "") or kw in (r.detail or "")]
        return _page([_log_row(r) for r in rows], page, ps)


def get_dashboard() -> dict:
    with session() as db:
        total = db.scalar(select(func.count()).select_from(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
            AcademicStudent.record_status == "ACTIVE")) or 0
        warning = db.scalar(select(func.count()).select_from(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.academic_status.in_(["WARNING", "HELPING"]),
            AcademicStudent.is_deleted.is_(False))) or 0
        pend_warn = db.scalar(select(func.count()).select_from(AcademicWarning).where(
            AcademicWarning.tenant_id == _tid(), AcademicWarning.status == "PENDING_HANDLE",
            AcademicWarning.is_deleted.is_(False))) or 0
        pend_mk = db.scalar(select(func.count()).select_from(AcademicMakeup).where(
            AcademicMakeup.tenant_id == _tid(), AcademicMakeup.status == "PENDING_EXAM",
            AcademicMakeup.is_deleted.is_(False))) or 0
        return {"termName": "2025-2026 学年第二学期", "termRange": "2026-02 ~ 2026-07",
                "updateTime": _iso(datetime.now()),
                "kpis": [
                    {"key": "students", "label": "学业学生", "value": str(total), "trend": "", "trendQuality": "neutral"},
                    {"key": "warning", "label": "预警/帮扶学生", "value": str(warning),
                     "trend": f"待处理预警 {pend_warn}", "trendQuality": "bad" if warning else "good"},
                    {"key": "makeup", "label": "待补考", "value": str(pend_mk),
                     "trend": f"待补考 {pend_mk}", "trendQuality": "neutral"},
                    {"key": "pendWarn", "label": "待处理预警", "value": str(pend_warn),
                     "trend": "", "trendQuality": "bad" if pend_warn else "good"},
                ],
                "todos": [
                    {"id": "t1", "label": "待处理预警", "value": pend_warn, "link": "/admin/academic/warnings"},
                    {"id": "t2", "label": "待补考登记", "value": pend_mk, "link": "/admin/academic/makeup-retake"},
                ],
                "flow": [], "recentImportBatches": [], "riskAlerts": []}
