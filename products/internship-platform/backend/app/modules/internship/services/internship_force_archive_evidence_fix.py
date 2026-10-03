"""包 8：强制归档依据复用材料中心的唯一正式绑定并冻结快照。

材料中心在归档清单准备阶段已经把强制归档依据登记为：
``INTERNSHIP_ARCHIVE_FORCE / <internshipId>:<index> / MATERIAL``。
同一文件不得再创建第二套 ``INTERNSHIP_FORCE_ARCHIVE / <archiveId>`` 绑定。
本模块只消费事务内原始 fileId，校验并复用上述权威 binding，冻结
file/version/hash/binding 快照；后续失效巡检也按快照中的真实业务身份复核。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException
from app.models import InternshipArchive
from app.models.file import FileBinding, FileObject
from app.modules.internship.services import internship_evidence_authority_guard as evidence_guard
from app.modules.internship.services import internship_evidence_package_service as package_service
from app.services.db_service import _tid

_INSTALLED = False
_PREVIOUS_CAPTURE = None
_PREVIOUS_VALIDATE = None

_AUTH_BIZ_TYPE = "INTERNSHIP_ARCHIVE_FORCE"
_AUTH_RELATION = "MATERIAL"


def _snapshot_authoritative_bindings(db, *, archive, record, raw_ids) -> list[dict]:
    snapshots: list[dict] = []
    for index, value in enumerate(evidence_guard._file_ids(raw_ids), start=1):
        file_id = int(value)
        expected_biz_id = f"{record.id}:{index}"
        binding = db.scalar(select(FileBinding).where(
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == file_id,
            FileBinding.module_code == "INTERNSHIP",
            FileBinding.biz_type == _AUTH_BIZ_TYPE,
            FileBinding.biz_id == expected_biz_id,
            FileBinding.relation_type == _AUTH_RELATION,
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ).with_for_update())
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == file_id,
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ).with_for_update())
        if not binding or not file_obj:
            raise AppException(
                "DATA_CONFLICT",
                "强制归档依据未形成唯一、有效的归档材料绑定",
                details={
                    "fileId": str(file_id),
                    "expectedBizType": _AUTH_BIZ_TYPE,
                    "expectedBizId": expected_biz_id,
                    "expectedRelationType": _AUTH_RELATION,
                },
            )
        scope = binding.data_scope_snapshot_json or binding.scope_json or {}
        if (
            str(scope.get("internshipId") or "") != str(record.id)
            or str(binding.subject_type or "") != "STUDENT"
            or str(binding.subject_id or "") != str(record.student_id)
        ):
            raise AppException(
                "DATA_CONFLICT",
                "强制归档依据绑定对象与当前实习档案不一致",
                details={"fileId": str(file_id), "bindingId": str(binding.id)},
            )
        if str(file_obj.status or "").upper() not in {"AVAILABLE", "STORED"}:
            raise AppException("DATA_CONFLICT", "强制归档依据文件当前不可用")
        if str(file_obj.scan_status or "NOT_REQUIRED").upper() not in {"CLEAN", "NOT_REQUIRED"}:
            raise AppException("DATA_CONFLICT", "强制归档依据文件安全扫描状态无效")
        snapshots.append({
            "fileId": str(file_obj.id),
            "fileVersion": int(file_obj.version or 0),
            "fileSha256": file_obj.sha256 or "",
            "scanStatus": file_obj.scan_status,
            "fileStatus": file_obj.status,
            "bindingId": str(binding.id),
            "bindingVersion": int(binding.version or 0),
            "bindingStatus": binding.status,
            "bizType": binding.biz_type,
            "bizId": binding.biz_id,
            "relationType": binding.relation_type,
            "archiveId": str(archive.id),
        })
    return snapshots


def _capture_archive_snapshot(db, record, evaluation, user):
    archive = db.scalar(select(InternshipArchive).where(
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.internship_id == record.id,
        InternshipArchive.is_deleted.is_(False),
    ).order_by(InternshipArchive.id.desc()).with_for_update())

    raw = None
    if archive:
        # 延迟导入避免服务包安装阶段形成循环依赖。
        from app.modules.internship.services import (
            internship_archive_preflush_evidence_guard as preflush_guard,
        )

        raw = preflush_guard.pop_raw_evidence(db, archive)
        if raw is None:
            raw = archive.force_evidence_file_ids

    if archive and raw and not evidence_guard._is_snapshot_list(raw):
        # 材料中心已经完成正式绑定；这里只复用并冻结，严禁二次改绑。
        archive.force_evidence_file_ids = _snapshot_authoritative_bindings(
            db,
            archive=archive,
            record=record,
            raw_ids=raw,
        )
        db.flush()

    return _PREVIOUS_CAPTURE(db, record, evaluation, user)


def _validate_authoritative_snapshot(db, snapshots, archive_id) -> tuple[bool, str]:
    if not evidence_guard._is_snapshot_list(snapshots):
        return False, "强制归档依据缺少正式版本/hash/binding 快照"
    archive = db.scalar(select(InternshipArchive).where(
        InternshipArchive.id == int(archive_id),
        InternshipArchive.tenant_id == _tid(),
        InternshipArchive.is_deleted.is_(False),
    ))
    if not archive:
        return False, "实习归档不存在或已失效"
    expected_prefix = f"{archive.internship_id}:"
    for item in snapshots:
        if (
            str(item.get("bizType") or "") != _AUTH_BIZ_TYPE
            or str(item.get("relationType") or "") != _AUTH_RELATION
            or not str(item.get("bizId") or "").startswith(expected_prefix)
        ):
            return False, f"文件 {item.get('fileId')} 的归档证据身份不匹配"
        file_obj = db.scalar(select(FileObject).where(
            FileObject.id == int(item["fileId"]),
            FileObject.tenant_id == _tid(),
            FileObject.is_deleted.is_(False),
        ))
        binding = db.scalar(select(FileBinding).where(
            FileBinding.id == int(item["bindingId"]),
            FileBinding.tenant_id == _tid(),
            FileBinding.file_id == int(item["fileId"]),
            FileBinding.biz_type == item["bizType"],
            FileBinding.biz_id == str(item["bizId"]),
            FileBinding.relation_type == item["relationType"],
            FileBinding.status == "ACTIVE",
            FileBinding.is_current.is_(True),
            FileBinding.is_deleted.is_(False),
        ))
        if not file_obj or not binding:
            return False, f"文件 {item['fileId']} 或归档材料绑定已失效"
        scope = binding.data_scope_snapshot_json or binding.scope_json or {}
        if str(scope.get("internshipId") or "") != str(archive.internship_id):
            return False, f"文件 {item['fileId']} 的实习对象范围已变化"
        if str(file_obj.status or "").upper() not in {"AVAILABLE", "STORED"}:
            return False, f"文件 {item['fileId']} 当前不可用"
        if str(file_obj.scan_status or "NOT_REQUIRED").upper() not in {"CLEAN", "NOT_REQUIRED"}:
            return False, f"文件 {item['fileId']} 安全扫描状态无效"
        if int(file_obj.version or 0) != int(item.get("fileVersion") or 0):
            return False, f"文件 {item['fileId']} 版本已变化"
        if str(file_obj.sha256 or "") != str(item.get("fileSha256") or ""):
            return False, f"文件 {item['fileId']} hash 已变化"
        if int(binding.version or 0) != int(item.get("bindingVersion") or 0):
            return False, f"文件 {item['fileId']} 绑定版本已变化"
    return True, ""


def _validate_evidence(db, snapshots, *, biz_type: str, biz_id):
    # 兼容旧调用名，但强制归档只按材料中心的唯一权威 binding 复核。
    if biz_type == "INTERNSHIP_FORCE_ARCHIVE":
        return _validate_authoritative_snapshot(db, snapshots, biz_id)
    return _PREVIOUS_VALIDATE(
        db,
        snapshots,
        biz_type=biz_type,
        biz_id=biz_id,
    )


def install() -> None:
    global _INSTALLED, _PREVIOUS_CAPTURE, _PREVIOUS_VALIDATE
    if _INSTALLED:
        return
    # 在 evidence_guard.install() 之后调用，保留豁免证据与归档详情逻辑。
    _PREVIOUS_CAPTURE = package_service.capture_archive_snapshot
    _PREVIOUS_VALIDATE = evidence_guard.validate_evidence
    package_service.capture_archive_snapshot = _capture_archive_snapshot
    evidence_guard.validate_evidence = _validate_evidence
    _INSTALLED = True
