"""岗位实习域真实数据服务（DB_ENABLED=true 走本模块）。租户过滤 + is_deleted + 脱敏 + 审计留痕。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (AttendanceException, InternshipAuditTrail, InternshipBatch,
                        InternshipRecord, RiskRecord, StudentContact, StudentProfile, WeeklyReport)
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


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, target_id: int, target_type: str, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=target_id, target_type=target_type,
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _students_map(db, ids: list[int]) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(StudentProfile).where(StudentProfile.id.in_(ids))).all()
    return {s.id: s for s in rows}


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
                             status=None, risk_level=None):
    with session() as db:
        q = select(InternshipRecord).where(InternshipRecord.tenant_id == _tid(),
                                           InternshipRecord.is_deleted.is_(False))
        if status:
            q = q.where(InternshipRecord.status == status)
        if risk_level:
            q = q.where(InternshipRecord.risk_level == risk_level)
        rows = db.scalars(q.order_by(InternshipRecord.id)).all()
        smap = _students_map(db, [r.student_id for r in rows])
        items = []
        for r in rows:
            stu = smap.get(r.student_id)
            if keyword:
                kw = keyword.strip()
                if not stu or (kw not in (stu.real_name or "") and kw not in (stu.student_no or "")):
                    continue
            if class_id and (not stu or str(stu.class_id) != str(class_id)):
                continue
            items.append(_record_row(r, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_internship_student_detail(record_id) -> dict:
    with session() as db:
        r = db.get(InternshipRecord, int(record_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("实习记录不存在或不在当前数据范围内")
        stu = db.get(StudentProfile, r.student_id)
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


def _exc_ctx(db, c: AttendanceException):
    rec = db.get(InternshipRecord, c.internship_id)
    stu = db.get(StudentProfile, rec.student_id) if rec else None
    return rec, stu


def list_attendance_exceptions(page, page_size, type=None, status=None, keyword=None):
    with session() as db:
        q = select(AttendanceException).where(AttendanceException.tenant_id == _tid(),
                                              AttendanceException.is_deleted.is_(False))
        if type:
            q = q.where(AttendanceException.exception_type == type)
        if status:
            q = q.where(AttendanceException.status == status)
        rows = db.scalars(q.order_by(AttendanceException.exception_date.desc())).all()
        items = []
        for c in rows:
            rec, stu = _exc_ctx(db, c)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            items.append(_exc_row(c, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_exception_detail(exception_id) -> dict:
    with session() as db:
        c = db.get(AttendanceException, int(exception_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("打卡异常不存在")
        rec, stu = _exc_ctx(db, c)
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


def handle_attendance_exception(exception_id, action: str, comment: str) -> dict:
    if action not in ("REASONABLE", "ABNORMAL", "TO_RISK"):
        raise AppException("VALIDATION_ERROR", "action 必须是 REASONABLE/ABNORMAL/TO_RISK")
    if not comment or len(comment.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理意见必填且不少于 5 字")
    with session() as db:
        c = db.get(AttendanceException, int(exception_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("打卡异常不存在")
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


def list_weekly_reports(page, page_size, status=None, keyword=None):
    with session() as db:
        q = select(WeeklyReport).where(WeeklyReport.tenant_id == _tid(),
                                       WeeklyReport.is_deleted.is_(False))
        if status:
            q = q.where(WeeklyReport.status == status)
        rows = db.scalars(q.order_by(WeeklyReport.submitted_at.desc().nullslast()
                                     if hasattr(WeeklyReport.submitted_at, 'desc') else WeeklyReport.id.desc())).all()
        items = []
        for w in rows:
            rec = db.get(InternshipRecord, w.internship_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            items.append(_report_row(w, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_weekly_report_detail(report_id) -> dict:
    with session() as db:
        w = db.get(WeeklyReport, int(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
        rec = db.get(InternshipRecord, w.internship_id)
        stu = db.get(StudentProfile, rec.student_id) if rec else None
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


def review_weekly_report(report_id, action: str, comment: str) -> dict:
    if action not in ("APPROVE", "RETURN"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/RETURN")
    if action == "RETURN" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        w = db.get(WeeklyReport, int(report_id))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("周报不存在")
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

def list_risk_students(page, page_size, level=None, status=None):
    with session() as db:
        q = select(RiskRecord).where(RiskRecord.tenant_id == _tid(),
                                     RiskRecord.is_deleted.is_(False))
        if level:
            q = q.where(RiskRecord.risk_level == level)
        if status:
            q = q.where(RiskRecord.status == status)
        rows = db.scalars(q.order_by(RiskRecord.id.desc())).all()
        items = []
        for k in rows:
            rec = db.get(InternshipRecord, k.internship_id)
            stu = db.get(StudentProfile, rec.student_id) if rec else None
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


# ═══ 看板 ═══

def get_dashboard_summary() -> dict:
    with session() as db:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False))).all()
        flow_map = {"PREPARING": 0, "READY": 0, "ONBOARD": 0, "ASSESSING": 0, "ARCHIVED": 0}
        for r in recs:
            flow_map[r.status] = flow_map.get(r.status, 0) + 1
        pending_exc = db.scalar(select(func.count()).select_from(AttendanceException).where(
            AttendanceException.tenant_id == _tid(), AttendanceException.status == "PENDING_HANDLE",
            AttendanceException.is_deleted.is_(False))) or 0
        pending_rep = db.scalar(select(func.count()).select_from(WeeklyReport).where(
            WeeklyReport.tenant_id == _tid(), WeeklyReport.status == "PENDING_REVIEW",
            WeeklyReport.is_deleted.is_(False))) or 0
        risk_cnt = db.scalar(select(func.count()).select_from(RiskRecord).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]),
            RiskRecord.is_deleted.is_(False))) or 0
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
