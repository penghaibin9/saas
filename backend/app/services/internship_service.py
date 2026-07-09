"""岗位实习域真实数据服务（DB_ENABLED=true 走本模块）。租户过滤 + is_deleted + 脱敏 + 审计留痕。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (AttendanceException, InternshipAuditTrail, InternshipBatch,
                        InternshipCheckin, InternshipRecord, RiskRecord, StudentContact,
                        StudentProfile, WeeklyReport)
from app.schemas.internship import RulesConfig, StageItem
from app.services.db_service import _iso, _mask_phone, _tid, session

STATUS_LABEL = {"PREPARING": "准备中", "READY": "待上岗", "ONBOARD": "在岗中",
                "ASSESSING": "考核中", "ARCHIVED": "已归档"}
RISK_LABEL = {"NONE": "无", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
RISK_TONE = {"HIGH": "danger", "MEDIUM": "warning", "LOW": "default", "NONE": "default"}
EXC_TYPE_LABEL = {"OUT_OF_RANGE": "超范围", "MOCK_LOCATION": "模拟定位", "MISSING": "缺卡"}
EXC_STATUS_LABEL = {"PENDING_HANDLE": "待核实", "COMPLETED": "已处理"}
REPORT_STATUS_LABEL = {"PENDING_REVIEW": "待批阅", "APPROVED": "已通过",
                       "RETURNED": "已退回", "OVERDUE": "逾期未交"}
RISK_STATUS_LABEL = {"PENDING_HANDLE": "待处理", "PROCESSING": "跟进中",
                     "RESOLVED": "已解决", "CLOSED": "已关闭"}
BATCH_STATUS_LABEL = {"DRAFT": "草稿", "RUNNING": "进行中", "CLOSED": "已结束",
                      "ARCHIVED": "已归档", "VOIDED": "已作废"}
DEFAULT_STAGES = [
    {"code": "PREP", "name": "岗前准备", "startDate": "", "endDate": ""},
    {"code": "ONBOARD", "name": "在岗实习", "startDate": "", "endDate": ""},
    {"code": "REVIEW", "name": "总结考核", "startDate": "", "endDate": ""},
]
DEFAULT_RULES = {
    "checkin": {"requireDaily": True, "geofenceRadiusM": 500,
                "allowedExceptionTypes": ["OUT_OF_RANGE", "MOCK_LOCATION", "MISSING"]},
    "weeklyReport": {"frequency": "WEEKLY", "minWordCount": 800, "deadlineWeekday": 7},
    "guidance": {"minVisitsPerTerm": 2, "minCommunicationsPerMonth": 2},
    "evaluation": {"enterpriseWeight": 0.4, "teacherWeight": 0.4, "selfWeight": 0.2},
    "score": {"passThreshold": 60.0, "components": [
        {"name": "企业评价", "weight": 0.4}, {"name": "教师评价", "weight": 0.4},
        {"name": "考核成绩", "weight": 0.2}]},
}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, target_id: int, target_type: str, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=target_id, target_type=target_type,
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def notify_counselor_for_student(db, student, title: str, content: str,
                                 source_biz_id=None, message_type="INTERNSHIP") -> bool:
    """向学生所在班级辅导员发真实站内信（t_unified_message）。

    解析路径：student.class_id → t_class.counselor_id（辅导员 user_id）。班级未配置
    辅导员或学生无班级时静默跳过（返回 False，不伪造）。用于指导转风险 / 请假等提醒。
    """
    from app.models import SchoolClass, UnifiedMessage
    if not student or not getattr(student, "class_id", None):
        return False
    cls = db.get(SchoolClass, student.class_id)
    if not cls or not getattr(cls, "counselor_id", None):
        return False
    db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(cls.counselor_id),
                          source_module="internship",
                          source_biz_id=int(source_biz_id) if source_biz_id else None,
                          title=title[:500], content=(content or "")[:2000],
                          message_type=message_type, status="UNREAD"))
    return True


def _parse_dt(v):
    if not v:
        return None
    s = str(v).strip().replace("Z", "").replace("/", "-")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19])
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _students_map(db, ids: list[int]) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(StudentProfile).where(StudentProfile.id.in_(ids))).all()
    return {s.id: s for s in rows}


# ═══════════ 数据范围（P0-D：管理端按教师范围收敛，不仅租户） ═══════════
# 与 internship_student_service 同一机制：user 由 API 层显式传入（FastAPI 同步端点 contextvar 不可靠）。

def _current_scope(user: dict | None = None) -> dict:
    from app.services.mobile_teacher_service import resolve_teacher_scope
    return resolve_teacher_scope(user or get_current_user_ctx() or {})


def _rec_in_scope(scope: dict, db, r: "InternshipRecord | None", stu) -> bool:
    """实习记录是否在教师数据范围内。非 SCOPED（管理员全校 / 无范围兜底）一律放行；
    SCOPED 按 指导教师姓名 / 学号 / 班级 / 学院 收敛。记录缺失（脏数据）时 SCOPED 下不放行。"""
    if scope.get("mode") != "SCOPED":
        return True
    if r is None:
        return False
    from app.services.mobile_teacher_service import scope_match_row
    class_name = college_name = None
    if stu is not None:
        from app.models import College, SchoolClass
        if getattr(stu, "class_id", None):
            c = db.get(SchoolClass, stu.class_id)
            class_name = c.class_name if c else None
        if getattr(stu, "college_id", None):
            col = db.get(College, stu.college_id)
            college_name = col.college_name if col else None
    return scope_match_row(scope, student_no=(stu.student_no if stu else None),
                           class_name=class_name, advisor_name=r.advisor_name,
                           college_name=college_name)


def _record_row(r: InternshipRecord, stu: StudentProfile | None) -> dict:
    return {
        "id": str(r.id), "studentId": str(r.student_id),
        "name": stu.real_name if stu else "-",
        "studentNo": stu.student_no if stu else "-",
        "className": (stu.grade + "级") if stu and stu.grade else "-",
        "classId": str(stu.class_id) if stu and stu.class_id else "",
        "enterpriseName": r.enterprise_name or "", "positionName": r.position_name or "",
        "advisorName": r.advisor_name or "", "enterpriseMentor": r.enterprise_mentor_name or "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "riskLevel": r.risk_level, "riskLabel": RISK_LABEL.get(r.risk_level, r.risk_level),
        "internRange": (f"{_iso(r.intern_start_date)[:10]} ~ {_iso(r.intern_end_date)[:10]}"
                        if r.intern_start_date and r.intern_end_date else ""),
    }


# ═══ 实习学生列表 / 详情 ═══

def list_internship_students(page, page_size, keyword=None, class_id=None,
                             status=None, risk_level=None, user=None):
    with session() as db:
        q = select(InternshipRecord).where(InternshipRecord.tenant_id == _tid(),
                                           InternshipRecord.is_deleted.is_(False))
        if status:
            q = q.where(InternshipRecord.status == status)
        if risk_level:
            q = q.where(InternshipRecord.risk_level == risk_level)
        rows = db.scalars(q.order_by(InternshipRecord.id)).all()
        smap = _students_map(db, [r.student_id for r in rows])
        scope = _current_scope(user)
        items = []
        for r in rows:
            stu = smap.get(r.student_id)
            if keyword:
                kw = keyword.strip()
                if not stu or (kw not in (stu.real_name or "") and kw not in (stu.student_no or "")):
                    continue
            if class_id and (not stu or str(stu.class_id) != str(class_id)):
                continue
            if not _rec_in_scope(scope, db, r, stu):  # P0-D
                continue
            items.append(_record_row(r, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_internship_student_detail(record_id, user=None) -> dict:
    with session() as db:
        r = db.get(InternshipRecord, int(record_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在或不在当前数据范围内")
        stu = db.get(StudentProfile, r.student_id)
        if not _rec_in_scope(_current_scope(user), db, r, stu):  # P0-D：越范围 → 403
            from app.core.exceptions import no_permission
            raise no_permission("该实习学生不在你的数据范围内")
        phone = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == r.student_id,
            StudentContact.contact_type == "PHONE")).first()
        checkins = db.scalars(select(AttendanceException).where(
            AttendanceException.tenant_id == _tid(),
            AttendanceException.internship_id == r.id).order_by(
            AttendanceException.exception_date.desc()).limit(6)).all()
        reports = db.scalars(select(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(), WeeklyReport.internship_id == r.id,
            WeeklyReport.is_deleted.is_(False)).order_by(WeeklyReport.week_number.desc())).all()
        risks = db.scalars(select(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.internship_id == r.id,
            RiskRecord.is_deleted.is_(False)).order_by(RiskRecord.id.desc())).all()
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_id == r.id).order_by(
            InternshipAuditTrail.id.desc()).limit(8)).all()
        base = _record_row(r, stu)
        base.update({
            "phone": _mask_phone(phone.contact_value_encrypted if phone else None),
            "insurance": r.insurance_info or "", "agreement": r.agreement_info or "",
            "checkins": [{"id": str(c.id), "date": _iso(c.exception_date)[:16] if c.exception_date else "",
                          "result": EXC_TYPE_LABEL.get(c.exception_type, c.exception_type),
                          "tone": "danger" if c.status == "PENDING_HANDLE" else "success",
                          "note": c.student_note or "",
                          "handle": EXC_STATUS_LABEL.get(c.status, c.status)} for c in checkins],
            "reports": [{"id": str(w.id), "week": f"第 {w.week_number} 周", "status": w.status,
                         "statusLabel": REPORT_STATUS_LABEL.get(w.status, w.status),
                         "submitAt": _iso(w.submitted_at) or "",
                         "version": f"v{w.report_version}"} for w in reports],
            "risks": [{"id": str(k.id), "code": k.risk_code, "title": k.risk_title,
                       "level": k.risk_level, "status": RISK_STATUS_LABEL.get(k.status, k.status),
                       "owner": k.owner_name or ""} for k in risks],
            "auditTrail": [{"who": t.operator_name or "系统", "time": _iso(t.occurred_at),
                            "action": t.action,
                            "affected": json.dumps(t.detail_json or {}, ensure_ascii=False)}
                           for t in trail],
        })
        return base


# ═══ 打卡异常 ═══

def _exc_row(c: AttendanceException, rec: InternshipRecord | None, stu: StudentProfile | None) -> dict:
    return {
        "id": str(c.id), "internId": str(c.internship_id),
        "studentName": stu.real_name if stu else "-",
        "className": (stu.grade + "级") if stu and stu.grade else "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "date": _iso(c.exception_date)[:16] if c.exception_date else "",
        "type": c.exception_type, "typeLabel": EXC_TYPE_LABEL.get(c.exception_type, c.exception_type),
        "distance": f"{c.distance_km} km" if c.distance_km else "—",
        "deviceRisk": c.device_risk_flag or "正常", "note": c.student_note or "",
        "streak": f"连续 {c.streak_days} 天" if c.streak_days else "",
        "status": c.status, "statusLabel": EXC_STATUS_LABEL.get(c.status, c.status),
    }


# ═══ 打卡台账（PC 管理端只读，over t_internship_checkin；移动端学生写入，按数据范围收敛） ═══

CHECKIN_RESULT_LABEL = {"RECORDED": "已记录", "NORMAL": "正常", "OUT_OF_RANGE": "超范围",
                        "NO_LOCATION": "无定位", "LEAVE": "请假"}


def _checkin_row(c: InternshipCheckin, rec, stu) -> dict:
    return {
        "id": str(c.id), "internId": str(c.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "enterpriseName": rec.enterprise_name if rec else "",
        "date": c.checkin_date, "at": _iso(c.checkin_at) or "",
        "result": c.result, "resultLabel": CHECKIN_RESULT_LABEL.get(c.result, c.result),
        "tone": "danger" if c.result in ("OUT_OF_RANGE", "NO_LOCATION") else "success",
        "address": c.address or "", "note": c.note or "",
    }


def list_checkins(page, page_size, result=None, keyword=None, internship_id=None, user=None):
    with session() as db:
        q = select(InternshipCheckin).where(InternshipCheckin.tenant_id == _tid(),
                                            InternshipCheckin.is_deleted.is_(False))
        if result:
            q = q.where(InternshipCheckin.result == result)
        if internship_id:
            q = q.where(InternshipCheckin.internship_id == int(internship_id))
        rows = db.scalars(q.order_by(InternshipCheckin.checkin_date.desc(),
                                     InternshipCheckin.id.desc())).all()
        scope = _current_scope(user)
        items = []
        for c in rows:
            rec = db.get(InternshipRecord, c.internship_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not _rec_in_scope(scope, db, rec, stu):  # P0-D 数据范围
                continue
            items.append(_checkin_row(c, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def export_checkins(result=None, keyword=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_checkins(1, 100000, result=result, keyword=keyword, user=user)
    headers = ["学号", "姓名", "校内指导教师", "企业", "打卡日期", "打卡时间", "结果", "地址", "备注"]
    data_rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
                  it["date"], it["at"], it["resultLabel"], it["address"], it["note"]] for it in items]
    wm = (f"岗位实习中心·打卡台账 · 导出人：{(get_current_user_ctx() or {}).get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("打卡台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "打卡台账.xlsx", len(items))


def export_exceptions(type=None, status=None, keyword=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_attendance_exceptions(1, 100000, type=type, status=status, keyword=keyword, user=user)
    headers = ["姓名", "班级", "企业", "异常类型", "异常时间", "距离", "连续", "设备", "处理状态"]
    data_rows = [[it["studentName"], it["className"], it["enterpriseName"], it["typeLabel"],
                  it["date"], it["distance"], it["streak"], it["deviceRisk"], it["statusLabel"]]
                 for it in items]
    wm = (f"岗位实习中心·打卡异常台账 · 导出人：{(get_current_user_ctx() or {}).get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("打卡异常台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "打卡异常台账.xlsx", len(items))


def _exc_ctx(db, c: AttendanceException):
    rec = db.get(InternshipRecord, c.internship_id)
    stu = db.get(StudentProfile, rec.student_id) if rec else None
    return rec, stu


def list_attendance_exceptions(page, page_size, type=None, status=None, keyword=None, user=None):
    with session() as db:
        q = select(AttendanceException).where(AttendanceException.tenant_id == _tid(),
                                              AttendanceException.is_deleted.is_(False))
        if type:
            q = q.where(AttendanceException.exception_type == type)
        if status:
            q = q.where(AttendanceException.status == status)
        rows = db.scalars(q.order_by(AttendanceException.exception_date.desc())).all()
        scope = _current_scope(user)
        items = []
        for c in rows:
            rec, stu = _exc_ctx(db, c)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not _rec_in_scope(scope, db, rec, stu):  # P0-D
                continue
            items.append(_exc_row(c, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_exception_detail(exception_id, user=None) -> dict:
    with session() as db:
        c = db.get(AttendanceException, int(exception_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("打卡异常不存在")
        rec, stu = _exc_ctx(db, c)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P0-D
            from app.core.exceptions import no_permission
            raise no_permission("该打卡异常不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_id == c.id,
            InternshipAuditTrail.target_type == "EXCEPTION").order_by(
            InternshipAuditTrail.id)).all()
        row = _exc_row(c, rec, stu)
        row.update({
            "positionName": rec.position_name if rec else "", "address": c.address or "",
            "accuracy": f"±{c.gps_accuracy} m" if c.gps_accuracy else "—",
            "studentNote": c.student_note or "", "handleComment": c.handle_comment or "",
            "trail": [{"title": t.action, "desc": json.dumps(t.detail_json or {}, ensure_ascii=False),
                       "time": _iso(t.occurred_at), "tone": "processing"} for t in trail],
        })
        return row


def handle_attendance_exception(exception_id, action: str, comment: str, user=None) -> dict:
    if action not in ("REASONABLE", "ABNORMAL", "TO_RISK"):
        raise AppException("VALIDATION_ERROR", "action 必须是 REASONABLE/ABNORMAL/TO_RISK")
    if not comment or len(comment.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理意见必填且不少于 5 字")
    with session() as db:
        c = db.get(AttendanceException, int(exception_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("打卡异常不存在")
        rec, stu = _exc_ctx(db, c)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P1：owner 级写校验
            from app.core.exceptions import no_permission
            raise no_permission("只能处理本人指导学生的打卡异常")
        if c.status == "COMPLETED":
            raise AppException("DATA_CONFLICT", "该异常已处理，请刷新")
        c.status = "COMPLETED"
        c.handle_action = action
        c.handle_comment = comment.strip()
        c.handled_by_name = _op_name()
        c.handled_at = datetime.utcnow()
        c.version += 1
        # 转风险：自动生成风险单
        if action == "TO_RISK":
            db.add(RiskRecord(tenant_id=_tid(), internship_id=c.internship_id,
                              risk_code="INT-R07", risk_title="打卡异常转风险跟进",
                              risk_level="HIGH", source_module="system", owner_name=_op_name(),
                              deadline_at=datetime.utcnow() + timedelta(days=3),
                              status="PENDING_HANDLE"))
            rec = db.get(InternshipRecord, c.internship_id)
            if rec:
                rec.risk_level = "HIGH"
        _trail(db, c.id, "EXCEPTION", f"HANDLE_{action}", {"comment": comment.strip()})
        db.commit()
        return {"id": str(c.id), "status": "COMPLETED",
                "statusLabel": {"REASONABLE": "已标记合理", "ABNORMAL": "已记为异常",
                                "TO_RISK": "已转风险"}[action]}


# ═══ 周报 ═══

def _report_row(w: WeeklyReport, rec: InternshipRecord | None, stu: StudentProfile | None) -> dict:
    return {
        "id": str(w.id), "internId": str(w.internship_id),
        "studentName": stu.real_name if stu else "-",
        "className": (stu.grade + "级") if stu and stu.grade else "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "week": f"第 {w.week_number} 周", "submitAt": _iso(w.submitted_at) or "",
        "version": f"v{w.report_version}", "isResubmit": w.report_version > 1,
        "wordCount": w.word_count, "riskFlag": w.risk_flag or "",
        "status": w.status, "statusLabel": REPORT_STATUS_LABEL.get(w.status, w.status),
    }


def list_weekly_reports(page, page_size, status=None, keyword=None, user=None):
    with session() as db:
        q = select(WeeklyReport).where(WeeklyReport.tenant_id == _tid(),
                                       WeeklyReport.is_deleted.is_(False))
        if status:
            q = q.where(WeeklyReport.status == status)
        rows = db.scalars(q.order_by(WeeklyReport.submitted_at.is_(None),
                                     WeeklyReport.submitted_at.desc(),
                                     WeeklyReport.id.desc())).all()
        scope = _current_scope(user)
        items = []
        for w in rows:
            rec = db.get(InternshipRecord, w.internship_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not _rec_in_scope(scope, db, rec, stu):  # P0-D
                continue
            items.append(_report_row(w, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_weekly_report_detail(report_id, user=None) -> dict:
    with session() as db:
        w = db.get(WeeklyReport, int(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
        rec = db.get(InternshipRecord, w.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P0-D
            from app.core.exceptions import no_permission
            raise no_permission("该周报不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == w.id,
            InternshipAuditTrail.target_type == "REPORT").order_by(InternshipAuditTrail.id)).all()
        row = _report_row(w, rec, stu)
        row.update({
            "positionName": rec.position_name if rec else "",
            "content": {"work": w.work_content or "", "harvest": w.harvest_content or "",
                        "plan": w.plan_content or ""},
            "reviewComment": w.review_comment or "",
            "trail": [{"who": t.operator_name or "系统", "time": _iso(t.occurred_at),
                       "action": t.action,
                       "affected": json.dumps(t.detail_json or {}, ensure_ascii=False)} for t in trail],
        })
        return row


def review_weekly_report(report_id, action: str, comment: str, user=None) -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        w = db.get(WeeklyReport, int(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
        rec = db.get(InternshipRecord, w.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # P1：owner 级写校验
            from app.core.exceptions import no_permission
            raise no_permission("只能批阅本人指导学生的周报")
        if w.status in ("APPROVED", "RETURNED"):
            raise AppException("DATA_CONFLICT", "该周报已批阅，请刷新")
        w.status = "APPROVED" if action == "APPROVE" else "RETURNED"
        w.review_action = action
        w.review_comment = (comment or "").strip()
        w.reviewed_by_name = _op_name()
        w.reviewed_at = datetime.utcnow()
        w.version += 1
        _trail(db, w.id, "REPORT", f"REVIEW_{action}", {"comment": (comment or "").strip()})
        db.commit()
        return {"id": str(w.id), "status": w.status,
                "statusLabel": REPORT_STATUS_LABEL.get(w.status, w.status)}


# ═══ 风险学生 ═══

def list_risk_students(page, page_size, level=None, status=None, user=None):
    with session() as db:
        q = select(RiskRecord).where(RiskRecord.tenant_id == _tid(),
                                     RiskRecord.is_deleted.is_(False))
        if level:
            q = q.where(RiskRecord.risk_level == level)
        if status:
            q = q.where(RiskRecord.status == status)
        rows = db.scalars(q.order_by(RiskRecord.id.desc())).all()
        scope = _current_scope(user)
        items = []
        for k in rows:
            rec = db.get(InternshipRecord, k.internship_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
            if not _rec_in_scope(scope, db, rec, stu):  # P0-D
                continue
            items.append({
                "id": str(k.id), "internId": str(k.internship_id),
                "studentName": stu.real_name if stu else "-",
                "className": (stu.grade + "级") if stu and stu.grade else "-",
                "source": f"{k.risk_code} {k.risk_title}", "level": k.risk_level,
                "owner": k.owner_name or "", "deadline": _iso(k.deadline_at)[:10] if k.deadline_at else "",
                "lastFollow": k.last_follow_note or "—",
                "status": k.status, "statusLabel": RISK_STATUS_LABEL.get(k.status, k.status),
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


# ═══ 实习批次（组织时间轴 + 规则骨架 + 状态机 DRAFT→RUNNING→CLOSED→ARCHIVED；VOIDED 仅草稿可达） ═══

def _batch_actual_count(db, batch_id: int) -> int:
    return db.scalar(select(func.count()).select_from(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.batch_id == batch_id,
        InternshipRecord.is_deleted.is_(False))) or 0


def _batch_row(db, b: InternshipBatch) -> dict:
    return {
        "id": str(b.id), "batchName": b.batch_name, "batchNo": b.batch_no,
        "academicYear": b.academic_year or "", "term": b.term or "",
        "startDate": _iso(b.start_date) or "", "endDate": _iso(b.end_date) or "",
        "signupStartDate": _iso(b.signup_start_date) or "", "signupEndDate": _iso(b.signup_end_date) or "",
        "plannedCount": int(b.planned_count or 0), "actualCount": _batch_actual_count(db, b.id),
        "status": b.status, "statusLabel": BATCH_STATUS_LABEL.get(b.status, b.status),
        "archiveStatus": b.archive_status or "NOT_ARCHIVED",
        "remark": b.remark or "", "updateTime": _iso(b.updated_at),
        "createTime": _iso(b.created_at) or "",
    }


def _batch_detail_row(db, b: InternshipBatch) -> dict:
    row = _batch_row(db, b)
    trail = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_id == b.id,
        InternshipAuditTrail.target_type == "BATCH").order_by(InternshipAuditTrail.id.desc())).all()
    row.update({
        "stages": b.stage_config or DEFAULT_STAGES,
        "rules": b.rules_config or DEFAULT_RULES,
        "previousStatus": b.previous_status or "",
        "lastTransitionAt": _iso(b.last_transition_at) or "",
        "lastTransitionBy": b.last_transition_by or "",
        "transitionReason": b.transition_reason or "",
        "archivedAt": _iso(b.archived_at) or "", "archivedBy": b.archived_by or "",
        "archiveBatchNo": b.archive_batch_no or "",
        "auditTrail": [{"id": str(t.id), "action": t.action, "operator": t.operator_name or "系统",
                        "time": _iso(t.occurred_at),
                        "detail": json.dumps(t.detail_json or {}, ensure_ascii=False)} for t in trail],
    })
    return row


def _get_batch(db, bid) -> InternshipBatch:
    b = db.get(InternshipBatch, int(bid))
    if not b or b.is_deleted or b.tenant_id != _tid():
        raise not_found("实习批次不存在或不在当前数据范围内")
    return b


def _deep_merge(base: dict, patch: dict) -> dict:
    """按 key 递归合并：patch 中未出现的分组/字段保留 base 原值，避免局部提交冲掉整段配置。"""
    out = dict(base or {})
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _merge_rules(base: dict | None, patch: dict | None) -> dict:
    """合并规则配置并回灌 RulesConfig 做一次类型/范围校验，返回校验后的标准 dict。"""
    merged = _deep_merge(base or DEFAULT_RULES, patch or {})
    try:
        return RulesConfig(**merged).model_dump()
    except Exception as e:  # noqa: BLE001 — pydantic ValidationError 统一转业务校验错误
        raise AppException("VALIDATION_ERROR", f"规则配置格式不正确：{e}") from e


def _dump_stages(stages) -> list:
    try:
        return [StageItem(**s).model_dump() if isinstance(s, dict) else s.model_dump() for s in stages]
    except Exception as e:  # noqa: BLE001
        raise AppException("VALIDATION_ERROR", f"阶段时间轴格式不正确：{e}") from e


def list_batches(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(InternshipBatch).where(InternshipBatch.tenant_id == _tid(),
                                          InternshipBatch.is_deleted.is_(False))
        if status:
            q = q.where(InternshipBatch.status == status)
        rows = db.scalars(q.order_by(InternshipBatch.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.batch_name or "") or kw in (r.batch_no or "")]
        items = [_batch_row(db, r) for r in rows]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_batch(bid) -> dict:
    with session() as db:
        return _batch_detail_row(db, _get_batch(db, bid))


def create_batch(body: dict) -> dict:
    name = str(body.get("batchName") or "").strip()
    no = str(body.get("batchNo") or "").strip()
    if not name or not no:
        raise AppException("VALIDATION_ERROR", "批次名称与批次编号必填")
    with session() as db:
        dup = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == _tid(), InternshipBatch.batch_no == no,
            InternshipBatch.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"批次编号 {no} 已存在")
        stages = _dump_stages(body.get("stages")) if body.get("stages") else list(DEFAULT_STAGES)
        rules = _merge_rules(DEFAULT_RULES, body.get("rules"))
        b = InternshipBatch(
            tenant_id=_tid(), batch_name=name, batch_no=no,
            academic_year=body.get("academicYear"), term=body.get("term"),
            start_date=_parse_dt(body.get("startDate")), end_date=_parse_dt(body.get("endDate")),
            signup_start_date=_parse_dt(body.get("signupStartDate")),
            signup_end_date=_parse_dt(body.get("signupEndDate")),
            planned_count=int(body.get("plannedCount") or 0), remark=body.get("remark"),
            status="DRAFT", stage_config=stages, rules_config=rules, archive_status="NOT_ARCHIVED")
        db.add(b)
        db.flush()
        _trail(db, b.id, "BATCH", "CREATE", {"batchName": name, "batchNo": no})
        db.commit()
        return {"id": str(b.id)}


def update_batch(bid, body: dict) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status in ("CLOSED", "ARCHIVED", "VOIDED"):
            raise AppException("INVALID_STATE", "已结束/已归档/已作废的批次不可编辑")
        for k, col in {"batchName": "batch_name", "academicYear": "academic_year",
                       "term": "term", "remark": "remark"}.items():
            if body.get(k) is not None:
                setattr(b, col, body[k])
        for k, col in {"startDate": "start_date", "endDate": "end_date",
                       "signupStartDate": "signup_start_date",
                       "signupEndDate": "signup_end_date"}.items():
            if body.get(k) is not None:
                setattr(b, col, _parse_dt(body[k]))
        if body.get("plannedCount") is not None:
            b.planned_count = int(body["plannedCount"] or 0)
        if body.get("stages") is not None:
            b.stage_config = _dump_stages(body["stages"])
        if body.get("rules") is not None:
            b.rules_config = _merge_rules(b.rules_config, body["rules"])
        b.version += 1
        _trail(db, b.id, "BATCH", "UPDATE")
        db.commit()
        return {"id": str(b.id)}


def activate_batch(bid) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "DRAFT":
            raise AppException("INVALID_STATE", "仅草稿批次可启用")
        b.previous_status, b.status = b.status, "RUNNING"
        b.last_transition_at = datetime.utcnow()
        b.last_transition_by = _op_name()
        b.version += 1
        _trail(db, b.id, "BATCH", "ACTIVATE", {"before": "DRAFT", "after": "RUNNING"})
        db.commit()
        return {"id": str(b.id), "status": b.status, "statusLabel": BATCH_STATUS_LABEL[b.status]}


def close_batch(bid) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "RUNNING":
            raise AppException("INVALID_STATE", "仅进行中批次可结束")
        b.previous_status, b.status = b.status, "CLOSED"
        b.last_transition_at = datetime.utcnow()
        b.last_transition_by = _op_name()
        b.version += 1
        _trail(db, b.id, "BATCH", "CLOSE", {"before": "RUNNING", "after": "CLOSED"})
        db.commit()
        return {"id": str(b.id), "status": b.status, "statusLabel": BATCH_STATUS_LABEL[b.status]}


def archive_batch(bid) -> dict:
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "CLOSED":
            raise AppException("INVALID_STATE", "仅已结束批次可归档")
        b.previous_status, b.status = b.status, "ARCHIVED"
        b.archive_status = "ARCHIVED"
        b.archived_at = datetime.utcnow()
        b.archived_by = _op_name()
        b.archive_batch_no = b.batch_no
        b.last_transition_at = b.archived_at
        b.last_transition_by = b.archived_by
        b.version += 1
        _trail(db, b.id, "BATCH", "ARCHIVE", {"before": "CLOSED", "after": "ARCHIVED"})
        db.commit()
        return {"id": str(b.id), "status": b.status, "statusLabel": BATCH_STATUS_LABEL[b.status]}


def void_batch(bid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        b = _get_batch(db, bid)
        if b.status != "DRAFT":
            raise AppException("INVALID_STATE", "仅草稿批次可作废；进行中/已结束请先按流程结束再归档")
        b.previous_status, b.status = b.status, "VOIDED"
        b.transition_reason = reason.strip()
        b.last_transition_at = datetime.utcnow()
        b.last_transition_by = _op_name()
        b.version += 1
        _trail(db, b.id, "BATCH", "VOID", {"reason": reason.strip()})
        db.commit()
        return {"id": str(b.id), "status": b.status, "statusLabel": BATCH_STATUS_LABEL[b.status]}


def export_batches(keyword=None, status=None) -> dict:
    """导出实习批次 Excel 台账（按当前筛选）。"""
    from app.core.context import get_current_user_ctx
    from app.services import xlsx_util

    items, _total = list_batches(1, 10000, keyword=keyword, status=status)
    headers = ["批次名称", "批次编号", "学年", "学期", "开始时间", "结束时间", "状态",
               "是否当前批次", "规则摘要", "创建时间"]
    data_rows = []
    for r in items:
        rule_summary = (r.get("remark") or "")[:120]
        is_current = "是" if r.get("status") == "RUNNING" else "否"
        data_rows.append([
            r["batchName"], r["batchNo"], r["academicYear"], r["term"],
            (r["startDate"] or "")[:10], (r["endDate"] or "")[:10],
            r["statusLabel"], is_current, rule_summary,
            (r.get("createTime") or r.get("updateTime") or "")[:19]])
    user = get_current_user_ctx() or {}
    wm = (f"岗位实习中心·实习批次台账 · 导出人：{user.get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M}")
    content = xlsx_util.build_ledger_xlsx("实习批次台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "实习批次台账.xlsx", len(items))


# ═══ 看板 ═══

def get_dashboard_summary(user=None) -> dict:
    with session() as db:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False))).all()
        # P0-D：SCOPED（指导教师/学院负责人）只统计本范围；管理员/兜底看全租户。
        scope = _current_scope(user)
        scoped = scope.get("mode") == "SCOPED"
        if scoped:
            recs = [r for r in recs
                    if _rec_in_scope(scope, db, r, db.get(StudentProfile, r.student_id))]
        scoped_ids = [r.id for r in recs] or [0]
        flow_map = {"PREPARING": 0, "READY": 0, "ONBOARD": 0, "ASSESSING": 0, "ARCHIVED": 0}
        for r in recs:
            flow_map[r.status] = flow_map.get(r.status, 0) + 1

        def _cnt(model, *conds):
            q = select(func.count()).select_from(model).where(
                model.tenant_id == _tid(), model.is_deleted.is_(False), *conds)
            if scoped:
                q = q.where(model.internship_id.in_(scoped_ids))
            return db.scalar(q) or 0
        pending_exc = _cnt(AttendanceException, AttendanceException.status == "PENDING_HANDLE")
        pending_rep = _cnt(WeeklyReport, WeeklyReport.status == "PENDING_REVIEW")
        risk_cnt = _cnt(RiskRecord, RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]))
        batch = db.scalars(select(InternshipBatch).where(
            InternshipBatch.tenant_id == _tid(),
            InternshipBatch.is_deleted.is_(False)).order_by(InternshipBatch.id.desc())).first()
        return {
            "batchName": batch.batch_name if batch else "实习批次",
            "batchRange": (f"{_iso(batch.start_date)[:10]} ~ {_iso(batch.end_date)[:10]}"
                           if batch and batch.start_date and batch.end_date else ""),
            "batchStatus": "进行中" if batch and batch.status == "RUNNING" else "—",
            "stats": [
                {"label": "在岗学生", "value": str(flow_map["ONBOARD"]), "trend": "", "trendQuality": "neutral"},
                {"label": "待处理打卡异常", "value": str(pending_exc),
                 "trend": f"待核实 {pending_exc}", "trendQuality": "bad" if pending_exc else "good"},
                {"label": "待批阅周报", "value": str(pending_rep),
                 "trend": f"待批阅 {pending_rep}", "trendQuality": "bad" if pending_rep else "good"},
                {"label": "风险学生", "value": str(risk_cnt),
                 "trend": f"跟进中 {risk_cnt}", "trendQuality": "bad" if risk_cnt else "good"},
            ],
            "flow": [{"label": lbl, "value": flow_map[k], "active": k == "ONBOARD"}
                     for k, lbl in STATUS_LABEL.items()],
            "todos": [
                {"id": "todo-1", "label": "待批阅周报", "count": pending_rep, "tone": "danger",
                 "route": "/admin/internship/reports"},
                {"id": "todo-2", "label": "待核实打卡异常", "count": pending_exc, "tone": "warning",
                 "route": "/admin/internship/exceptions"},
                {"id": "todo-3", "label": "风险学生待跟进", "count": risk_cnt, "tone": "warning",
                 "route": "/admin/internship/risks"},
            ],
            "riskAlerts": [],
        }
