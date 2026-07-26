"""6 大业务域通用真实导出（xlsx：首行水印 + 敏感脱敏 + t_export_task 审计）。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker
from app.services.db_service import _tid
from app.services.import_export_service import upload_dir

# 域 → (标题, 列表函数路径, [(表头, 字段名)])
DOMAINS = {
    "student-affairs": ("学工历史迁移对账", "affairs_history_export_service.list_history",
                        [("业务类型", "bizType"), ("历史编号", "historyNo"),
                         ("入库记录ID", "recordId"), ("操作人", "operator"),
                         ("导入时间", "importedAt")]),
    "internship": ("岗位实习学生", "internship_service.list_internship_students",
                   [("姓名", "name"), ("学号", "studentNo"), ("班级", "className"),
                    ("实习单位", "enterpriseName"), ("岗位", "positionName"), ("状态", "statusLabel"),
                    ("风险", "riskLabel")]),
    "orientation": ("迎新新生台账", "orientation_service.list_students",
                    [("姓名", "name"), ("录取编号", "admissionNo"), ("班级", "className"),
                     ("报到状态", "reportStatusLabel"), ("缴费状态", "paymentStatusLabel"),
                     ("宿舍状态", "dormStatusLabel"), ("风险", "riskLabel")]),
    "campus-service": ("在校服务台账", "campus_service_service.list_students",
                       [("姓名", "name"), ("学号", "studentNo"), ("班级", "className"),
                        ("关怀级别", "careLevelLabel"), ("风险", "riskLabel"), ("辅导员", "counselor")]),
    "academic": ("学业过程台账", "academic_service.list_students",
                 [("姓名", "name"), ("学号", "studentNo"), ("班级", "className"),
                  ("GPA", "gpa"), ("已获学分", "obtainedCredits"), ("预警等级", "warningLabel"),
                  ("学业状态", "academicStatusLabel")]),
    "graduation": ("毕业设计台账", "graduation_service.list_students",
                   [("姓名", "name"), ("学号", "studentNo"), ("班级", "className"),
                    ("课题", "topicTitle"), ("指导教师", "advisorName"), ("阶段", "stageLabel"),
                    ("查重率", "plagiarismRate")]),
    "employment": ("就业服务台账", "employment_service.list_students",
                   [("姓名", "name"), ("学号", "studentNo"), ("班级", "className"),
                    ("去向", "destinationLabel"), ("单位", "companyName"), ("核验", "verifyLabel"),
                    ("帮扶", "helpLabel")]),
}


MAX_EXPORT_ROWS = 5000  # 单次导出上限：防止一次拉全表拖垮内存/阻塞主接口


def _import_service(mod_name):
    """定位服务模块：兼容旧 app.services.* 与目录收拢后的 app.modules.<中心>.services.*。

    仅改变“到哪里找模块”，不改导出数据/字段/函数行为（目录收拢后的接线兼容）。
    """
    import importlib
    import pkgutil
    try:
        return importlib.import_module(f"app.services.{mod_name}")
    except ModuleNotFoundError:
        pass
    import app.modules as _modules
    for _sub in pkgutil.iter_modules(_modules.__path__):
        try:
            return importlib.import_module(f"app.modules.{_sub.name}.services.{mod_name}")
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(f"服务模块未找到：app.services.{mod_name} 或 app.modules.*.services.{mod_name}")


def _call_list(path):
    mod_name, fn_name = path.split(".")
    mod = _import_service(mod_name)
    fn = getattr(mod, fn_name)
    items, total = fn(1, MAX_EXPORT_ROWS)
    if total > MAX_EXPORT_ROWS:
        raise AppException("VALIDATION_ERROR",
                           f"导出数据量 {total} 行超过单次上限 {MAX_EXPORT_ROWS} 行，请按班级/条件筛选后分批导出")
    return items, total


def export_domain(domain: str, purpose: str, user: dict | None = None) -> dict:
    if domain not in DOMAINS:
        raise AppException("VALIDATION_ERROR", f"未知导出域：{domain}")
    if not purpose or len(purpose.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于 5 字")
    if not db_enabled():
        raise AppException("SERVER_ERROR", "导出需启用数据库")
    title, list_path, cols = DOMAINS[domain]
    items, total = _call_list(list_path)
    user = user or get_current_user_ctx() or {}
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = title[:28]
    watermark = (f"高校学生全生命周期管理平台 · {title} · 导出人：{user.get('realName', '-')} · "
                 f"时间：{datetime.now():%Y-%m-%d %H:%M} · 用途：{purpose.strip()} · 敏感字段已脱敏")
    ws.append([watermark])
    ws.append([c[0] for c in cols])
    for r in items:
        ws.append([r.get(c[1], "") for c in cols])
    key = f"exports/{datetime.now():%Y%m%d}/{domain}_{uuid.uuid4().hex[:8]}.xlsx"
    target = upload_dir() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)
    task = {"taskId": "", "status": "SUCCESS", "rowCount": total, "fileKey": key,
            "fileName": target.name, "purpose": purpose.strip(),
            "securityNotice": f"{title}导出：已脱敏 + 首行水印 + 审计留痕；不得随意外发"}
    from app.models import ExportTask
    from app.services.message_identity import resolve_message_user_id
    db = get_sessionmaker()()
    try:
        row = ExportTask(tenant_id=_tid(), export_mode="LIST", module_code=domain, row_count=total,
                         purpose=purpose.strip(), file_hash=hashlib.sha256(target.read_bytes()).hexdigest(),
                         status="SUCCESS", remark=key,
                         created_by=resolve_message_user_id(user) or None)
        db.add(row)
        db.commit()
        db.refresh(row)
        task["taskId"] = str(row.id)
    finally:
        db.close()
    try:
        from app.services import audit_log
        audit_log.record("EXPORT", f"{domain}-export", detail={"rows": total, "purpose": purpose.strip()})
    except Exception:  # noqa: BLE001
        pass
    return task
