"""包 7/文件中心事务修复：系统生成过程报告快照必须写入当前归档事务。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.models.file import FileAsset, FileBinding, FileVersion
from app.modules.internship.services import internship_material_center_service as base
from app.services import file_service
from app.services.db_service import _iso, _tid

_INSTALLED = False


def _report_snapshot(db, report, record, student, user) -> str:
    code = base._asset_code(
        record.id,
        "PROCESS_REPORT",
        "INTERNSHIP_PROCESS_REPORT",
        str(report.id),
    )
    asset = db.scalar(select(FileAsset).where(
        FileAsset.tenant_id == _tid(),
        FileAsset.asset_code == code,
        FileAsset.is_deleted.is_(False),
    ))
    if asset and asset.current_version_id:
        version = db.get(FileVersion, asset.current_version_id)
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.version_id == asset.current_version_id,
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ))
        scope = (
            binding.data_scope_snapshot_json or binding.scope_json or {}
        ) if binding else {}
        if (
            version
            and version.is_current
            and str(scope.get("sourceBusinessVersion") or "")
            == str(int(report.version or 0))
        ):
            return str(version.file_object_id)

    payload = {
        "schemaVersion": "INTERNSHIP_PROCESS_REPORT_SNAPSHOT_V1",
        "internshipId": str(record.id),
        "studentId": str(record.student_id),
        "studentNo": getattr(student, "student_no", None),
        "studentName": getattr(student, "real_name", None),
        "reportId": str(report.id),
        "reportType": report.report_type,
        "periodKey": report.period_key,
        "content": report.content or "",
        "wordCount": int(report.word_count or 0),
        "businessVersion": int(report.version or 0),
        "submittedAt": _iso(report.submitted_at),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }
    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    name = (
        f"过程报告_{report.report_type}_{report.period_key}"
        f"_v{int(report.version or 0)}.txt"
    )
    # 关键：复用归档命令的 Session，避免 MySQL REPEATABLE READ 看不到另会话刚提交的文件。
    meta = file_service.store_bytes(
        content,
        name,
        biz_type="INTERNSHIP",
        biz_id=str(record.id),
        mime_type="text/plain",
        user=user,
        visibility="BIZ_SCOPED",
        security_level="PERSONAL",
        db=db,
    )
    return str(meta["fileId"])


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    base._report_snapshot = _report_snapshot
    _INSTALLED = True
