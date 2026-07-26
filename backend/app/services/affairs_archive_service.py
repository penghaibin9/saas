"""13A-P6 学工归档（批次 + 学生档案包）。

批次：DRAFT→COLLECTING→COLLEGE_REVIEW→SA_CONFIRM→ARCHIVED。
档案包：每生一行，缺项清单；确认归档时登记 t_export_task（水印包 sha256），不建归档文件表。
"""

from app.core.optimistic_lock import atomic_claim_version

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
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
            "status": b.status, "confirmBy": b.confirm_by or "", "confirmAt": _iso(b.confirm_at),
            "version": b.version}


def list_batches(user, status=None, page=1, page_size=50):
    """归档批次列表（按创建倒序，可按状态筛选）。含各批次档案包计数。"""
    from app.models import ArchiveBatch, ArchivePackage
    from sqlalchemy import func
    with session() as db:
        conds = [ArchiveBatch.tenant_id == _tid(), ArchiveBatch.is_deleted.is_(False)]
        if status:
            conds.append(ArchiveBatch.status == status)
        rows = db.scalars(select(ArchiveBatch).where(*conds).order_by(ArchiveBatch.id.desc())).all()
        out = []
        for b in rows:
            d = _batch_row(b)
            d["packageCount"] = db.scalar(select(func.count()).select_from(ArchivePackage).where(
                ArchivePackage.tenant_id == _tid(), ArchivePackage.batch_id == b.id,
                ArchivePackage.is_deleted.is_(False))) or 0
            out.append(d)
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


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


def collect(batch_id, user, student_ids, expected_version=None) -> dict:
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
        atomic_claim_version(db, b, expected_version)
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
        b.status, b.version = "COLLECTING", b.version + 1
        _audit(db, b.id, "COLLECT", f"{made}生")
        db.commit()
        return {"batchId": str(batch_id), "packagesCreated": made, "status": "COLLECTING",
                "version": b.version}


def advance(batch_id, user, action="APPROVE", expected_version=None) -> dict:
    """批次流转 COLLECTING→COLLEGE_REVIEW→SA_CONFIRM→ARCHIVED；ARCHIVED 时登记 t_export_task 水印包。"""
    with session() as db:
        from app.models import ArchiveBatch, ArchivePackage, ExportTask
        b = db.get(ArchiveBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("归档批次不存在")
        if b.status not in ("COLLECTING", "COLLEGE_REVIEW", "SA_CONFIRM"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次当前状态不可流转")
        atomic_claim_version(db, b, expected_version)
        i = BATCH_FLOW.index(b.status)
        nxt = BATCH_FLOW[i + 1]
        b.status, b.version = nxt, b.version + 1
        if nxt == "ARCHIVED":
            n, _r, _u = _op()
            b.confirm_by, b.confirm_at = n, datetime.utcnow()
            pkgs = db.scalars(select(ArchivePackage).where(
                ArchivePackage.tenant_id == _tid(), ArchivePackage.batch_id == b.id,
                ArchivePackage.is_deleted.is_(False))).all()
            # 水印包登记 t_export_task：仅占位登记，真实文件尚未生成，不得标 SUCCESS。
            task = ExportTask(tenant_id=_tid(), export_mode="ENCRYPTED_ARCHIVE",
                              module_code="affairs_archive", row_count=len(pkgs),
                              file_hash=f"placeholder-sha256-{b.id}", status="PENDING",
                              purpose="学工归档水印包导出（待真实导出管线回填）")
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
    """批次元信息按租户全量可见（与 AidBatch/FundingBatch 同口径）；档案包含学生 student_id，
    按 _allowed_class_ids 数据范围收敛（辅导员限本班，绝不回退全租户）。"""
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        from app.models import ArchiveBatch, ArchivePackage
        b = db.get(ArchiveBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("归档批次不存在")
        allowed, _ = _allowed_class_ids(db, user)
        pkgs = db.scalars(select(ArchivePackage).where(
            ArchivePackage.tenant_id == _tid(), ArchivePackage.batch_id == b.id,
            ArchivePackage.is_deleted.is_(False))).all()
        d = _batch_row(b)
        out_pkgs = []
        for p in pkgs:
            if allowed is not None:
                s = db.get(StudentProfile, int(p.student_id)) if p.student_id else None
                if not s or s.class_id not in allowed:
                    continue
            out_pkgs.append({"packageId": str(p.id), "studentId": str(p.student_id), "status": p.status,
                             "exportTaskId": str(p.export_task_id or "")})
        d["packages"] = out_pkgs
        return d
