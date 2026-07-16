"""13B-P8 课堂考勤（移动端首创，V1：教师按行政班逐场次考勤，DRAFT→SUBMITTED 二态）。

数据范围：仅任课教师本人（teacher_key 归属，复用成绩录入同款判定）；
提交后不可再改，如需更正走教务处线下人工处理（已知欠账，见施工记录）。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_STATUS_OK = ("PRESENT", "LATE", "ABSENT", "LEAVE")


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_ATTENDANCE", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, occurred_at=datetime.utcnow()))


def _user_keys(user) -> set[str]:
    uid = str((user or {}).get("userId") or "")
    login = (user or {}).get("loginName") or ""
    name = (user or {}).get("realName") or ""
    return {k for k in (uid, login, name, uid[2:] if uid.startswith("u_") else "") if k}


def _check_owner(t, user):
    role = ((user or {}).get("currentRoleCode") or "").upper()
    if role in ("ACADEMIC_ADMIN", "SCHOOL_ADMIN"):
        return
    if not t.teacher_key:
        return
    if t.teacher_key not in _user_keys(user):
        raise AppException("NO_DATA_SCOPE", "该考勤场次不在您的授课范围内")


def _row(t) -> dict:
    return {"sessionId": str(t.id), "classId": str(t.class_id or ""), "courseName": t.course_name or "",
            "termCode": t.term_code or "", "sessionDate": t.session_date, "slotNo": t.slot_no,
            "sessionType": t.session_type or "常规",
            "totalCount": t.total_count, "presentCount": t.present_count, "absentCount": t.absent_count,
            "status": t.status, "createdAt": _iso(t.created_at)}


def create_session(user, body) -> dict:
    """教师新建一次考勤：按行政班圈定名单快照为 roster_json，初值全 PRESENT。body 为原始 dict（移动端 JSON 直传）。"""
    from app.models import AaAttendanceSession, StudentProfile
    body = body or {}
    class_id = body.get("classId")
    if not class_id:
        raise AppException("VALIDATION_ERROR", "行政班必填")
    session_date = str(body.get("sessionDate") or "").strip()
    if not session_date:
        raise AppException("VALIDATION_ERROR", "考勤日期必填")
    slot_no = body.get("slotNo")
    with session() as db:
        rows = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.class_id == int(class_id),
            StudentProfile.is_deleted.is_(False))).all()
        if not rows:
            raise not_found("该行政班暂无学生名单")
        roster = [{"studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                  "status": "PRESENT"} for s in rows]
        teacher_key = next(iter(_user_keys(user)), None)
        t = AaAttendanceSession(
            tenant_id=_tid(), class_id=int(class_id), course_name=body.get("courseName"),
            term_code=body.get("termCode"), teacher_key=teacher_key, session_date=session_date,
            slot_no=(int(slot_no) if slot_no else None),
            session_type=(str(body.get("sessionType")).strip() or None) if body.get("sessionType") else None,
            roster_json=json.dumps(roster, ensure_ascii=False), total_count=len(roster),
            present_count=len(roster), absent_count=0, status="DRAFT")
        db.add(t)
        db.flush()
        _audit(db, t.id, "CREATE", f"{t.course_name or ''} {session_date}")
        db.commit()
        db.refresh(t)
        return _row(t)


def list_sessions(user, page=1, page_size=20, class_id=None, term_code=None, session_type=None):
    """考勤场次列表（教师按 teacher_key 归属；教务处/学校管理员可见全部）。可按行政班/学期/点名类别筛选。"""
    from app.models import AaAttendanceSession
    role = ((user or {}).get("currentRoleCode") or "").upper()
    with session() as db:
        conds = [AaAttendanceSession.tenant_id == _tid(), AaAttendanceSession.is_deleted.is_(False)]
        if role not in ("ACADEMIC_ADMIN", "SCHOOL_ADMIN"):
            keys = _user_keys(user)
            if not keys:
                return [], 0
            conds.append(AaAttendanceSession.teacher_key.in_(keys))
        if class_id:
            conds.append(AaAttendanceSession.class_id == int(class_id))
        if term_code:
            conds.append(AaAttendanceSession.term_code == term_code)
        if session_type:
            conds.append(AaAttendanceSession.session_type == session_type)
        rows = db.scalars(select(AaAttendanceSession).where(*conds)
                          .order_by(AaAttendanceSession.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        return [_row(t) for t in rows[start:start + page_size]], total


def attendance_stats(user, class_id=None, term_code=None, session_type=None):
    """跨堂次考勤统计（正方 教学点名查询 4.19 对标）：按学生汇总 出勤/迟到/旷课/请假 次数 + 缺勤率。
    仅统计 SUBMITTED（已定稿）场次；数据范围同 list_sessions（教师本人 / 教务处全部）。"""
    from app.models import AaAttendanceSession
    role = ((user or {}).get("currentRoleCode") or "").upper()
    with session() as db:
        conds = [AaAttendanceSession.tenant_id == _tid(), AaAttendanceSession.is_deleted.is_(False),
                 AaAttendanceSession.status == "SUBMITTED"]
        if role not in ("ACADEMIC_ADMIN", "SCHOOL_ADMIN"):
            keys = _user_keys(user)
            if not keys:
                return {"sessionCount": 0, "students": []}
            conds.append(AaAttendanceSession.teacher_key.in_(keys))
        if class_id:
            conds.append(AaAttendanceSession.class_id == int(class_id))
        if term_code:
            conds.append(AaAttendanceSession.term_code == term_code)
        if session_type:
            conds.append(AaAttendanceSession.session_type == session_type)
        rows = db.scalars(select(AaAttendanceSession).where(*conds)).all()
        agg: dict[str, dict] = {}
        for t in rows:
            for it in (json.loads(t.roster_json) if t.roster_json else []):
                sid = it.get("studentId")
                if not sid:
                    continue
                a = agg.setdefault(sid, {"studentId": sid, "studentNo": it.get("studentNo") or "",
                                         "realName": it.get("realName") or "", "present": 0,
                                         "late": 0, "absent": 0, "leave": 0, "sessions": 0})
                st = (it.get("status") or "PRESENT").upper()
                key = {"PRESENT": "present", "LATE": "late", "ABSENT": "absent", "LEAVE": "leave"}.get(st)
                if key:
                    a[key] += 1
                    a["sessions"] += 1
        students = []
        for a in agg.values():
            a["absentRate"] = round(a["absent"] / a["sessions"], 3) if a["sessions"] else 0.0
            students.append(a)
        students.sort(key=lambda x: (-x["absent"], -x["late"], x["studentNo"]))
        return {"sessionCount": len(rows), "students": students}


def get_session(session_id, user) -> dict:
    from app.models import AaAttendanceSession
    with session() as db:
        t = db.get(AaAttendanceSession, int(session_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("考勤场次不存在")
        _check_owner(t, user)
        items = json.loads(t.roster_json) if t.roster_json else []
        return {**_row(t), "items": items}


def mark_attendance(session_id, user, body) -> dict:
    """标记单生考勤状态（PRESENT/LATE/ABSENT/LEAVE），仅 DRAFT 可改，实时重算计数。"""
    from app.models import AaAttendanceSession
    with session() as db:
        t = db.get(AaAttendanceSession, int(session_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("考勤场次不存在")
        _check_owner(t, user)
        if t.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "已提交的考勤不可再修改")
        body = body or {}
        student_id = str(body.get("studentId") or "")
        status = str(body.get("status") or "").upper()
        if status not in _STATUS_OK:
            raise AppException("VALIDATION_ERROR", "考勤状态非法")
        items = json.loads(t.roster_json) if t.roster_json else []
        found = False
        for it in items:
            if it.get("studentId") == student_id:
                it["status"] = status
                found = True
                break
        if not found:
            raise not_found("该生不在本场次名单内")
        t.roster_json = json.dumps(items, ensure_ascii=False)
        t.present_count = sum(1 for it in items if it["status"] == "PRESENT")
        t.absent_count = sum(1 for it in items if it["status"] == "ABSENT")
        db.flush()
        db.commit()
        db.refresh(t)
        return {**_row(t), "items": items}


def submit_session(session_id, user) -> dict:
    from app.models import AaAttendanceSession
    with session() as db:
        t = db.get(AaAttendanceSession, int(session_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("考勤场次不存在")
        _check_owner(t, user)
        if t.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "该场次已提交")
        t.status = "SUBMITTED"
        _audit(db, t.id, "SUBMIT", f"present={t.present_count}/{t.total_count}")
        db.commit()
        db.refresh(t)
        return _row(t)
