"""公共 Excel 底座 · 导入记录服务（t_excel_import_job，DB_ENABLED=true 走真库）。

给业务模块在「确认导入」时登记一条作业记录，便于运维/审计追溯：谁、导了什么、结果如何。
- 复用 db_service 的 session()/_tid()/_iso()（同一套租户隔离 + 时间序列化口径）。
- DB_ENABLED=false 时静默跳过（不阻塞主流程），与审计 fire-and-forget 语义一致。
"""
from __future__ import annotations

from datetime import datetime

from app.core.context import get_current_user_ctx
from app.db.session import db_enabled

STATUS = ("UPLOADED", "VALIDATING", "VALIDATED", "CONFIRMING", "IMPORTED", "FAILED", "CANCELLED")


def _op() -> tuple:
    u = get_current_user_ctx() or {}
    return u.get("userId"), (u.get("realName") or "系统")


def _row(j) -> dict:
    from app.services.db_service import _iso
    return {
        "id": str(j.id), "moduleKey": j.module_key, "bizType": j.biz_type,
        "fileName": j.file_name or "", "templateVersion": j.template_version,
        "status": j.status, "totalRows": j.total_rows, "validRows": j.valid_rows,
        "invalidRows": j.invalid_rows, "successRows": j.success_rows, "failedRows": j.failed_rows,
        "operatorName": j.operator_name or "", "startedAt": _iso(j.started_at),
        "finishedAt": _iso(j.finished_at), "confirmAt": _iso(j.confirm_at),
        "remark": j.remark or "", "createdAt": _iso(j.created_at),
    }


def record_import(module_key: str, biz_type: str, *, file_name: str = "",
                  template_version: str = "v1", pre: dict | None = None,
                  result: dict | None = None, status: str = "IMPORTED",
                  remark: str = "") -> dict | None:
    """登记一条导入作业记录（确认导入成功/失败后调用）。返回记录 dict 或 None（未接库）。"""
    if not db_enabled():
        return None
    try:
        from app.models import ExcelImportJob
        from app.services.db_service import _tid, session
        pre = pre or {}
        result = result or {}
        op_id, op_name = _op()
        now = datetime.utcnow()
        success = int(result.get("created", 0))
        total = int(pre.get("total", success))
        invalid = int(pre.get("invalidRows", 0))
        with session() as db:
            job = ExcelImportJob(
                tenant_id=_tid(), module_key=module_key, biz_type=biz_type,
                file_name=file_name or None, template_version=template_version,
                status=status, total_rows=total,
                valid_rows=int(pre.get("validRows", total - invalid)),
                invalid_rows=invalid, success_rows=success,
                failed_rows=max(0, total - success), operator_id=op_id, operator_name=op_name,
                started_at=now, finished_at=now,
                confirm_at=now if status == "IMPORTED" else None,
                remark=remark or None, created_by=op_id, updated_by=op_id)
            db.add(job)
            db.commit()
            db.refresh(job)
            return _row(job)
    except Exception:  # noqa: BLE001 — 记录失败不阻塞主导入流程
        return None


def list_jobs(page: int = 1, page_size: int = 20, module_key: str | None = None,
              biz_type: str | None = None, status: str | None = None) -> tuple:
    """导入记录分页查询（租户隔离 + 软删过滤 + 时间倒序）。"""
    if not db_enabled():
        return [], 0
    from sqlalchemy import func, select

    from app.models import ExcelImportJob
    from app.services.db_service import _tid, session
    with session() as db:
        conds = [ExcelImportJob.tenant_id == _tid(), ExcelImportJob.is_deleted.is_(False)]
        if module_key:
            conds.append(ExcelImportJob.module_key == module_key)
        if biz_type:
            conds.append(ExcelImportJob.biz_type == biz_type)
        if status:
            conds.append(ExcelImportJob.status == status)
        total = db.scalar(select(func.count()).select_from(ExcelImportJob).where(*conds)) or 0
        rows = db.scalars(select(ExcelImportJob).where(*conds)
                          .order_by(ExcelImportJob.id.desc())
                          .offset((page - 1) * page_size).limit(page_size)).all()
        return [_row(r) for r in rows], total
