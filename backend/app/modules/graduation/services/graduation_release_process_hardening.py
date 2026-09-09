"""Graduation guidance/taskbook input and query hardening."""
from __future__ import annotations

import base64
import io
from datetime import datetime
from sqlalchemy import func, or_, select
from app.core.exceptions import AppException
from app.models import GraduationGuidance, GraduationStudent, GraduationTaskBook
from app.services.db_service import _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _strict_dt, _student_scope_select

def _install_process_hardening() -> None:
    from app.modules.graduation.services import graduation_guidance_service as guidance
    from app.modules.graduation.services import graduation_taskbook_service as taskbook

    old_create_guidance = guidance.create_guidance
    old_create_plan = guidance.create_plan
    old_checkin = guidance.checkin_plan

    def create_guidance(gd_student_id, body):
        data = dict(body)
        if data.get("guidanceDate") not in (None, ""): _strict_dt(data["guidanceDate"], "guidanceDate")
        method = str(data.get("method") or "ONLINE").strip().upper()
        if method not in {"ONLINE", "OFFLINE"}: raise AppException("VALIDATION_ERROR", "指导方式必须是 ONLINE/OFFLINE")
        data["method"] = method
        return old_create_guidance(gd_student_id, data)

    def create_plan(gd_student_id, body):
        data = dict(body)
        if data.get("planDate") not in (None, ""): _strict_dt(data["planDate"], "planDate")
        return old_create_plan(gd_student_id, data)

    def checkin_plan(plan_id, body=None):
        data = dict(body or {})
        method = str(data.get("method") or "MANUAL").strip().upper()
        if method not in {"ONLINE", "OFFLINE", "MANUAL"}: raise AppException("VALIDATION_ERROR", "签到方式必须是 ONLINE/OFFLINE/MANUAL")
        data["method"] = method
        return old_checkin(plan_id, data)

    def guidance_stats(threshold=3, batch_id=None):
        threshold = max(0, int(threshold))
        with session() as db:
            scope_q = _student_scope_select(db, _tid(), batch_id=batch_id)
            counts = select(GraduationGuidance.gd_student_id.label("sid"), func.count(GraduationGuidance.id).label("cnt")).where(GraduationGuidance.tenant_id == _tid(), GraduationGuidance.is_deleted.is_(False)).group_by(GraduationGuidance.gd_student_id).subquery()
            q = select(GraduationStudent.id, GraduationStudent.name, GraduationStudent.advisor_name, func.coalesce(counts.c.cnt, 0)).outerjoin(counts, counts.c.sid == GraduationStudent.id).where(GraduationStudent.tenant_id == _tid(), GraduationStudent.id.in_(scope_q), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE", GraduationStudent.stage.notin_(("TOPIC_SELECTING", "TASKBOOK_CONFIRM")))
            rows = db.execute(q).all(); total_count = sum(int(r[3] or 0) for r in rows)
            insufficient = [{"gdStudentId": str(sid), "studentName": name, "advisorName": advisor or "", "count": int(cnt or 0)} for sid, name, advisor, cnt in rows if int(cnt or 0) < threshold]
            return {"threshold": threshold, "studentCount": len(rows), "avgCount": round(total_count / len(rows), 1) if rows else 0, "insufficientCount": len(insufficient), "insufficientStudents": insufficient[:50], "batchId": str(batch_id) if batch_id else None}

    def _task_query(db, keyword=None, status=None, batch_id=None):
        scope_q = _student_scope_select(db, _tid(), batch_id=batch_id)
        filters = [GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.is_deleted.is_(False), GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_q)]
        if status: filters.append(GraduationTaskBook.status == status)
        if batch_id not in (None, ""): filters.append(GraduationStudent.batch_id == int(batch_id))
        if keyword:
            value = f"%{str(keyword).strip()}%"; filters.append(or_(GraduationStudent.name.like(value), GraduationStudent.student_no.like(value)))
        return select(GraduationTaskBook, GraduationStudent).join(GraduationStudent, GraduationStudent.id == GraduationTaskBook.gd_student_id).where(*filters)

    def list_taskbooks(page, page_size, keyword=None, status=None, batch_id=None):
        with session() as db:
            q = _task_query(db, keyword=keyword, status=status, batch_id=batch_id)
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0); size = min(200, max(1, int(page_size)))
            rows = db.execute(q.order_by(GraduationTaskBook.id.desc()).offset((max(1, int(page))-1)*size).limit(size)).all()
            return [taskbook._row(t, s) for t, s in rows], total

    def export_taskbooks_xlsx(status=None, batch_id=None):
        if not batch_id: raise AppException("VALIDATION_ERROR", "导出前必须选择毕业设计批次")
        from openpyxl import Workbook
        wb = Workbook(write_only=True); ws = wb.create_sheet("任务书台账")
        headers = ["学生", "学号", "导师", "版本", "状态", "任务目标", "成果要求", "确认时间"]
        operator, _ = taskbook._op(); ws.append([f"任务书台账　导出时间：{datetime.now():%Y-%m-%d %H:%M}　导出人：{operator}"] + [""]*(len(headers)-1)); ws.append(headers)
        row_count = 0; page = 1
        while True:
            items, _total = list_taskbooks(page, 200, status=status, batch_id=batch_id)
            if not items: break
            for it in items:
                ws.append([it["studentName"], it["studentNo"], it["advisorName"], it["taskbookVersion"], it["statusLabel"], it["objective"], it["outcomeRequirement"], (it["confirmedAt"] or "")[:19]]); row_count += 1
            if len(items) < 200: break
            page += 1
        buf = io.BytesIO(); wb.save(buf)
        return {"filename": f"任务书台账_{datetime.now():%Y%m%d_%H%M}.xlsx", "contentBase64": base64.b64encode(buf.getvalue()).decode("ascii"), "rowCount": row_count, "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    guidance.create_guidance = create_guidance
    guidance.create_plan = create_plan
    guidance.checkin_plan = checkin_plan
    guidance.guidance_stats = guidance_stats
    taskbook.list_taskbooks = list_taskbooks
    from app.modules.graduation.services.graduation_export_security import sanitize_xlsx_export
    taskbook.export_taskbooks_xlsx = sanitize_xlsx_export(export_taskbooks_xlsx)
