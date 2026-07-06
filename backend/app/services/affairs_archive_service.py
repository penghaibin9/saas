"""13A-P6 学工归档（批次 + 学生档案包）。

批次：DRAFT→COLLECTING→COLLEGE_REVIEW→SA_CONFIRM→ARCHIVED。
档案包：每生一行，缺项清单；确认归档时登记 t_export_task（水印包 sha256），不建归档文件表。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

BATCH_FLOW = ["DRAFT", "COLLECTING", "COLLEGE_REVIEW", "SA_CONFIRM", "ARCHIVED"]


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="ARCHIVE", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _batch_row(b) -> dict:
    return {"batchId": str(b.id), "batchName": b.batch_name, "yearCode": b.year_code or "",
            "status": b.status, "confirmBy": b.confirm_by or "", "confirmAt": _iso(b.confirm_at)}


def create_batch(body, user) -> dict:
    with session() as db:
        from app.models import ArchiveBatch
        b = ArchiveBatch(tenant_id=_tid(), batch_name=body.batchName,
                         year_code=getattr(body, "yearCode", None),
                         scope_json=json.dumps(getattr(body, "scope", {}) or {}, ensure_ascii=False),
                         status="DRAFT")
        db.add(b)
        db.flush()
        _audit(db, b.id, "BATCH_CREATE")
        db.commit()
        db.refresh(b)
        return _batch_row(b)


def collect(batch_id, user, student_ids) -> dict:
    """圈定学生生成档案包（每生一行，缺项清单占位）。批次 → COLLECTING。"""
    sids = [int(s) for s in (student_ids or []) if str(s).strip()]
    if not sids:
        raise AppException("VALIDATION_ERROR", "至少圈定一名学生")
    with session() as db:
        from app.models import ArchiveBatch, ArchivePackage, StudentProfile
        b = db.get(ArchiveBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("归档批次不存在")
        if b.status not in ("DRAFT", "COLLECTING"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次不可再收集")
        made = 0
        for sid in sids:
            s = db.get(StudentProfile, sid)
            if not s or s.is_deleted or s.tenant_id != _tid():
                continue
            dup = db.scalars(select(ArchivePackage).where(
                ArchivePackage.tenant_id == _tid(), ArchivePackage.batch_id == b.id,
                ArchivePackage.student_id == sid, ArchivePackage.is_deleted.is_(False))).first()
            if dup:
                continue
            db.add(ArchivePackage(tenant_id=_tid(), batch_id=b.id, student_id=sid,
                                  missing_items_json=json.dumps([], ensure_ascii=False),
                                  status="PENDING_GEN"))
            made += 1
        b.status = "COLLECTING"
        _audit(db, b.id, "COLLECT", f"{made}生")
        db.commit()
        return {"batchId": str(batch_id), "packagesCreated": made, "status": "COLLECTING"}


def advance(batch_id, user, action="APPROVE") -> dict:
    """批次流转 COLLECTING→COLLEGE_REVIEW→SA_CONFIRM→ARCHIVED；ARCHIVED 时登记 t_export_task 水印包。"""
    with session() as db:
        from app.models import ArchiveBatch, ArchivePackage, ExportTask
        b = db.get(ArchiveBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("归档批次不存在")
        if b.status not in ("COLLECTING", "COLLEGE_REVIEW", "SA_CONFIRM"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次当前状态不可流转")
        i = BATCH_FLOW.index(b.status)
        nxt = BATCH_FLOW[i + 1]
        b.status = nxt
        if nxt == "ARCHIVED":
            n, _r, _u = _op()
            b.confirm_by, b.confirm_at = n, datetime.utcnow()
            pkgs = db.scalars(select(ArchivePackage).where(
                ArchivePackage.tenant_id == _tid(), ArchivePackage.batch_id == b.id,
                ArchivePackage.is_deleted.is_(False))).all()
            # 水印包登记 t_export_task（file_hash 占位；真实导出走 export 管线）
            task = ExportTask(tenant_id=_tid(), export_mode="ENCRYPTED_ARCHIVE",
                              module_code="affairs_archive", row_count=len(pkgs),
                              file_hash=f"placeholder-sha256-{b.id}", status="SUCCESS",
                              purpose="学工归档水印包导出")
            db.add(task)
            db.flush()
            for p in pkgs:
                p.export_task_id, p.status = task.id, "ARCHIVED"
            _audit(db, b.id, "ARCHIVED", f"export_task={task.id}")
        else:
            _audit(db, b.id, "ADVANCE", f"->{nxt}")
        db.commit()
        db.refresh(b)
        return _batch_row(b)


def get_batch(batch_id, user) -> dict:
    with session() as db:
        from app.models import ArchiveBatch, ArchivePackage
        b = db.get(ArchiveBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("归档批次不存在")
        pkgs = db.scalars(select(ArchivePackage).where(
            ArchivePackage.tenant_id == _tid(), ArchivePackage.batch_id == b.id,
            ArchivePackage.is_deleted.is_(False))).all()
        d = _batch_row(b)
        d["packages"] = [{"packageId": str(p.id), "studentId": str(p.student_id), "status": p.status,
                          "exportTaskId": str(p.export_task_id or "")} for p in pkgs]
        return d
