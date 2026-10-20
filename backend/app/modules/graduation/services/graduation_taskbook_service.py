"""毕业设计中心 · 任务书服务。

导师下达→学生确认→变更需重确认（对齐老系统 t_gd_task_book 语义与商业系统"任务书"惯例）。
一生一条当前记录；变更时旧内容快照进 history_json，版本号自增。
确认后若学生阶段仍处于 TASKBOOK_CONFIRM，则推进到 GUIDING（指导中）。

隔离说明：不引用实习/迎新域文件；Excel 台账导出用 openpyxl 直连。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.models import GraduationAuditTrail, GraduationStudent, GraduationTaskBook
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_export_security import sanitize_xlsx_export
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access
from app.modules.graduation.policies import taskbook_policy

STATUS_LABEL = {"PENDING_CONFIRM": "待学生确认", "CONFIRMED": "已确认", "CHANGE_PENDING": "变更待确认"}
STATUS_TONE = {"PENDING_CONFIRM": "warning", "CONFIRMED": "success", "CHANGE_PENDING": "warning"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="TASKBOOK", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before,
                                after_val=after, occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "taskbook")


def _row(t: GraduationTaskBook, stu=None) -> dict:
    return {
        "id": str(t.id), "gdStudentId": str(t.gd_student_id),
        "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
        "advisorName": stu.advisor_name if stu else "",
        "objective": t.objective or "", "content": t.content or "",
        "progressPlan": t.progress_plan or "", "outcomeRequirement": t.outcome_requirement or "",
        "taskbookVersion": t.taskbook_version, "status": t.status,
        "statusLabel": STATUS_LABEL.get(t.status, t.status), "statusTone": STATUS_TONE.get(t.status, "default"),
        "issuedBy": t.issued_by or "", "issuedAt": _iso(t.issued_at), "confirmedAt": _iso(t.confirmed_at),
        "changeReason": t.change_reason or "", "history": t.history_json or [],
        "updatedAt": _iso(t.updated_at),
    }


def list_taskbooks(page: int, page_size: int, keyword=None, status=None,
                   batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        q = select(GraduationTaskBook).where(GraduationTaskBook.tenant_id == _tid(),
                                              GraduationTaskBook.is_deleted.is_(False),
                                              GraduationTaskBook.gd_student_id.in_(scope_ids or [-1]))
        if status:
            q = q.where(GraduationTaskBook.status == status)
        rows = db.scalars(q.order_by(GraduationTaskBook.id.desc())).all()
        items = []
        for t in rows:
            stu = db.get(GraduationStudent, t.gd_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_row(t, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_taskbook(gd_student_id) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        t = db.scalars(select(GraduationTaskBook).where(
            GraduationTaskBook.tenant_id == _tid(), GraduationTaskBook.gd_student_id == stu.id,
            GraduationTaskBook.is_deleted.is_(False))).first()
        if not t:
            return {"exists": False, "gdStudentId": str(stu.id), "studentName": stu.name,
                    "advisorName": stu.advisor_name or ""}
        return {"exists": True, **_row(t, stu)}


@sanitize_xlsx_export
def export_taskbooks_xlsx(status=None, batch_id=None) -> dict:
    enforce_permission(get_current_user_ctx() or {}, "graduationDesign.taskbook.export")
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "导出前必须选择毕业设计批次")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    items, _ = list_taskbooks(1, 100000, status=status, batch_id=batch_id)
    headers = ["学生", "学号", "导师", "版本", "状态", "任务目标", "成果要求", "确认时间"]
    operator, _role = _op()
    title = f"任务书台账　导出时间：{datetime.now():%Y-%m-%d %H:%M}　导出人：{operator}"
    wb = Workbook()
    ws = wb.active
    ws.title = "任务书台账"
    ws.append([title])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws["A1"].font = Font(bold=True, color="555555", size=10)
    ws.append(headers)
    fill = PatternFill("solid", fgColor="DCE6F1")
    for c in ws[2]:
        c.font = Font(bold=True); c.fill = fill
    for it in items:
        ws.append([it["studentName"], it["studentNo"], it["advisorName"], it["taskbookVersion"],
                  it["statusLabel"], it["objective"], it["outcomeRequirement"], (it["confirmedAt"] or "")[:19]])
    for i in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + i)].width = 20
    ws.freeze_panes = "A3"
    import base64
    import io
    buf = io.BytesIO()
    wb.save(buf)
    return {"filename": f"任务书台账_{datetime.now():%Y%m%d_%H%M}.xlsx",
            "contentBase64": base64.b64encode(buf.getvalue()).decode("ascii"), "rowCount": len(items),
            "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def _taskbook_print_vars(stu: GraduationStudent, t: GraduationTaskBook) -> dict[str, str]:
    """套打占位变量（与 gd-templates TASKBOOK DEFAULT_VARS 对齐，并补任务内容/学号等）。"""
    issued = _iso(t.issued_at) or ""
    return {
        "学生姓名": stu.name or "",
        "学号": stu.student_no or "",
        "班级": stu.class_name or "",
        "课题名称": stu.topic_title or "",
        "指导教师": stu.advisor_name or "",
        "任务目标": t.objective or "",
        "任务内容": t.content or "",
        "进度安排": t.progress_plan or "",
        "成果要求": t.outcome_requirement or "",
        "下达日期": issued[:19] if issued else "",
        "下达人": t.issued_by or "",
        "状态": STATUS_LABEL.get(t.status, t.status or ""),
        "版本": str(t.taskbook_version or 1),
    }


def _fill_template(content: str, variables: dict[str, str]) -> str:
    text = content or ""
    for key, val in variables.items():
        text = text.replace("{" + key + "}", val or "")
    return text


def _builtin_taskbook_body(variables: dict[str, str]) -> str:
    return (
        f"学生姓名：{variables.get('学生姓名', '')}\n"
        f"学号：{variables.get('学号', '')}\n"
        f"班级：{variables.get('班级', '')}\n"
        f"课题名称：{variables.get('课题名称', '')}\n"
        f"指导教师：{variables.get('指导教师', '')}\n"
        f"状态：{variables.get('状态', '')}　版本：v{variables.get('版本', '1')}\n"
        "\n"
        "一、任务目标\n"
        f"{variables.get('任务目标', '') or '—'}\n"
        "\n"
        "二、任务内容\n"
        f"{variables.get('任务内容', '') or '—'}\n"
        "\n"
        "三、进度安排\n"
        f"{variables.get('进度安排', '') or '—'}\n"
        "\n"
        "四、成果要求\n"
        f"{variables.get('成果要求', '') or '—'}\n"
        "\n"
        f"下达人：{variables.get('下达人', '') or '—'}　下达日期：{variables.get('下达日期', '') or '—'}\n"
    )


from app.modules.graduation.services.graduation_taskbook_consistency import (
    change_taskbook,
    confirm_taskbook,
    confirm_taskbook_in_session,
    export_taskbook_pdf,
    issue_taskbook,
    taskbook_stats,
)
