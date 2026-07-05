"""
P4 · 学生导入（Dry-Run 两步，t_student_import_batch）与导出（真实 xlsx + 水印 + t_export_task）。
口径：tenant_id 隔离；导出敏感字段恒脱敏；用途必填写审计。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import db_enabled, get_sessionmaker
from app.services.file_service import upload_dir

_MEM_BATCHES: dict[str, dict] = {}


def _tid() -> int:
    try:
        return int(current_tenant_id() or 1000000000000000001)
    except (TypeError, ValueError):
        return 1000000000000000001


def _validate_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """行级校验：studentNo/realName 必填、studentNo 不重复（批内 + 库内）。"""
    ok_rows, errors = [], []
    seen = set()
    existing = set()
    if db_enabled():
        from sqlalchemy import select
        from app.models import StudentProfile
        db = get_sessionmaker()()
        try:
            existing = {r for r in db.scalars(select(StudentProfile.student_no).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)))}
        finally:
            db.close()
    for i, row in enumerate(rows, start=2):  # Excel 行号从 2（1 为表头）
        no = str(row.get("studentNo") or row.get("学号") or "").strip()
        name = str(row.get("realName") or row.get("name") or row.get("姓名") or "").strip()
        if not no or not name:
            errors.append({"rowNo": i, "rowIndex": i, "errorCode": "REQUIRED_MISSING",
                           "field": "studentNo" if not no else "realName",
                           "rawValue": no or name or "", "message": "学号/姓名必填"})
            continue
        if no in seen:
            errors.append({"rowNo": i, "rowIndex": i, "errorCode": "DUP_IN_FILE",
                           "field": "studentNo", "rawValue": no, "message": f"学号 {no} 在文件内重复"})
            continue
        if no in existing:
            errors.append({"rowNo": i, "rowIndex": i, "errorCode": "DUP_IN_DB",
                           "field": "studentNo", "rawValue": no, "message": f"学号 {no} 已存在"})
            continue
        seen.add(no)
        ok_rows.append({"studentNo": no, "realName": name,
                        "gender": str(row.get("gender") or row.get("性别") or "").strip(),
                        "grade": str(row.get("grade") or row.get("年级") or "").strip(),
                        "phone": str(row.get("phone") or row.get("手机号") or "").strip()})
    return ok_rows, errors


def parse_upload_rows(content: bytes, ext: str) -> list[dict]:
    """解析上传文件为行字典列表（xlsx 用 openpyxl；csv 用标准库）。"""
    if ext == "xlsx":
        import io as _io
        from openpyxl import load_workbook
        try:
            wb = load_workbook(_io.BytesIO(content), read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception:  # noqa: BLE001 — 畸形/伪造 xlsx 转 400，不冒泡到全局 500
            raise AppException("FILE_TYPE_NOT_ALLOWED", "文件不是有效的 xlsx，请用标准模板导出后再上传")
        if not rows:
            return []
        headers = [str(h or "").strip() for h in rows[0]]
        return [dict(zip(headers, [c if c is not None else "" for c in r])) for r in rows[1:]]
    if ext == "csv":
        import csv as _csv
        import io as _io
        text = content.decode("utf-8-sig", errors="replace")
        return list(_csv.DictReader(_io.StringIO(text)))
    raise AppException("FILE_TYPE_NOT_ALLOWED", "导入仅支持 .xlsx / .csv")


def dry_run(rows: list[dict]) -> dict:
    _ensure_feature("studentImport", "学生导入")
    max_rows = int(_rule("import", "importMaxRows") or 5000)
    if len(rows) > max_rows:
        raise AppException("VALIDATION_ERROR",
                           f"单次导入不能超过 {max_rows} 行（平台规则中心配置），当前 {len(rows)} 行")
    ok_rows, errors = _validate_rows(rows)
    batch_no = f"IMP{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:4]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    batch = {"batchNo": batch_no, "status": status, "totalRows": len(rows),
             "okRows": len(ok_rows), "errorRows": len(errors), "errors": errors[:50],
             "rows": ok_rows}
    if db_enabled():
        from app.models import StudentImportBatch
        db = get_sessionmaker()()
        try:
            db.add(StudentImportBatch(tenant_id=_tid(), batch_no=batch_no, total_rows=len(rows),
                                      success_rows=0, error_rows=len(errors), status=status,
                                      remark=f"dryRun ok={len(ok_rows)}"))
            db.commit()
        finally:
            db.close()
    _MEM_BATCHES[batch_no] = batch
    return {k: v for k, v in batch.items() if k != "rows"} | {"batchNo": batch_no}


def confirm(batch_no: str) -> dict:
    batch = _MEM_BATCHES.get(batch_no)
    if not batch:
        raise not_found("导入批次不存在或已过期，请重新校验")
    if batch["status"] != "DRY_RUN_PASSED":
        raise AppException("VALIDATION_ERROR", "该批次未通过 Dry-Run 校验，禁止确认导入")
    inserted = 0
    if db_enabled():
        from sqlalchemy import select
        from app.models import StudentContact, StudentImportBatch, StudentProfile
        db = get_sessionmaker()()
        try:
            for r in batch["rows"]:
                s = StudentProfile(tenant_id=_tid(), student_no=r["studentNo"], real_name=r["realName"],
                                   gender=r.get("gender") or None, grade=r.get("grade") or None,
                                   current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
                db.add(s)
                db.flush()
                if r.get("phone"):
                    db.add(StudentContact(tenant_id=_tid(), student_id=s.id, contact_type="PHONE",
                                          contact_value_encrypted=r["phone"], is_primary=True,
                                          verified_status="UNVERIFIED"))
                inserted += 1
            b = db.scalars(select(StudentImportBatch).where(
                StudentImportBatch.tenant_id == _tid(),
                StudentImportBatch.batch_no == batch_no)).first()
            if b:
                b.status = "SUCCESS"
                b.success_rows = inserted
            db.commit()  # 整批一个事务：任一行失败自动回滚
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    else:
        inserted = len(batch["rows"])
    batch["status"] = "SUCCESS"
    return {"batchNo": batch_no, "status": "SUCCESS", "insertedRows": inserted}


def _mask_phone(v: str | None) -> str:
    v = v or ""
    return v[:3] + "****" + v[-4:] if len(v) >= 7 else ("***" if v else "")


def create_students_export(purpose: str) -> dict:
    """真实导出 xlsx（敏感字段脱敏 + 首行水印），写 t_export_task。"""
    _ensure_feature("studentExport", "学生导出")
    need = _rule("export", "exportNeedPurpose")
    min_len = int(_rule("export", "exportPurposeMinLength") or 0)
    if need and (not purpose or len(purpose.strip()) < min_len):
        raise AppException("VALIDATION_ERROR", f"导出用途必填且不少于 {min_len} 字（平台规则中心配置）")
    user = get_current_user_ctx() or {}
    from openpyxl import Workbook
    from app.services import db_service
    items, total = (db_service.list_students(1, 10000) if db_enabled() else ([], 0))
    wb = Workbook()
    ws = wb.active
    ws.title = "学生主档"
    watermark = (f"高校学生全生命周期管理平台 · 导出人：{user.get('realName', '-')} · "
                 f"时间：{datetime.now():%Y-%m-%d %H:%M} · 用途：{purpose.strip()} · 敏感字段已脱敏")
    ws.append([watermark])
    ws.append(["学号", "姓名", "性别", "年级", "班级", "阶段", "学籍状态", "手机号(脱敏)", "风险"])
    for r in items:
        ws.append([r["studentNo"], r["realName"], r["gender"], r["grade"], r["className"],
                   r["currentStage"], r["studentStatus"], r["phoneMasked"], r["riskLevel"]])
    key = f"exports/{datetime.now():%Y%m%d}/students_{uuid.uuid4().hex[:8]}.xlsx"
    target = upload_dir() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)
    task = {"taskId": "", "status": "SUCCESS", "rowCount": total, "fileKey": key,
            "fileName": target.name, "purpose": purpose.strip(),
            "securityNotice": "导出含学生信息：已脱敏 + 首行水印 + 审计留痕；不得随意外发"}
    if db_enabled():
        import hashlib
        from app.models import ExportTask
        db = get_sessionmaker()()
        try:
            row = ExportTask(tenant_id=_tid(), export_mode="LIST", module_code="student",
                             row_count=total, purpose=purpose.strip(), file_hash=hashlib.sha256(target.read_bytes()).hexdigest(),
                             status="SUCCESS", remark=key)
            db.add(row)
            db.commit()
            db.refresh(row)
            task["taskId"] = str(row.id)
        finally:
            db.close()
    else:
        task["taskId"] = f"mem-{uuid.uuid4().hex[:8]}"
    return task


def export_file_path(task_id: str) -> Path:
    if db_enabled() and task_id.isdigit():
        from app.models import ExportTask
        db = get_sessionmaker()()
        try:
            row = db.get(ExportTask, int(task_id))
            if row and row.tenant_id == _tid() and row.remark:
                p = upload_dir() / row.remark
                if p.exists():
                    return p
        finally:
            db.close()
    raise not_found("导出任务不存在或文件已清理")


# ── P6 规则中心 / 功能开关接入 ──

def _rule(group: str, key: str):
    from app.services.platform_service import safe_rule
    return safe_rule(_tid(), group, key)


def _ensure_feature(key: str, label: str) -> None:
    from app.services.platform_service import feature_enabled
    if not feature_enabled(_tid(), key):
        raise AppException("MODULE_NOT_AUTHORIZED",
                           f"当前学校套餐未开通「{label}」功能，请联系平台方 13549666867")
