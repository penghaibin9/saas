"""Graduation adapter for the PLAT-A immutable business snapshot contract."""
from __future__ import annotations

import re
from datetime import datetime

from app.modules.platform_integrity.contracts import SnapshotAssetRef
from app.modules.platform_integrity.snapshot_service import create_business_snapshot

from .definitions import MANIFEST_TARGET_TYPE, MODULE_CODE


def _int_or_none(value) -> int | None:
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError):
        return None
    return normalized or None


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="microseconds") + "Z"


def _safe_package_base_name(student, revision: int) -> str:
    raw = f"毕业设计归档-{student.student_no or student.id}-r{revision}"
    return re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", raw).strip(" .")[:160]


def create_graduation_business_snapshot(
    db,
    *,
    student,
    archive,
    archive_batch_no: str,
    revision: int,
    rule,
    frozen_at: datetime,
    user: dict,
) -> SnapshotAssetRef:
    """Freeze live graduation display facts before the generic builder can see them."""
    payload = {
        "schemaVersion": "PLATFORM_BUSINESS_SNAPSHOT_V1",
        "moduleCode": MODULE_CODE,
        "targetType": MANIFEST_TARGET_TYPE,
        "targetId": str(student.id),
        "identity": {
            "studentId": str(student.student_id or ""),
            "studentNo": str(student.student_no or ""),
            "displayName": str(student.name or ""),
        },
        "scope": {
            "batchId": str(student.batch_id or ""),
            "collegeId": str(student.college_id or ""),
            "classId": str(student.class_id or ""),
        },
        "display": {
            "archiveLabel": "毕业设计归档材料",
            "safePackageBaseName": _safe_package_base_name(student, revision),
        },
        "frozenFacts": {
            "gdStudentId": str(student.id),
            "topicId": str(student.topic_id or ""),
            "topicTitle": str(student.topic_title or ""),
            "advisorName": str(student.advisor_name or ""),
            "archiveBatchNo": archive_batch_no,
            "ruleCode": str(rule.rule_code),
            "ruleVersion": int(rule.rule_version),
        },
        "sourceVersions": {
            "graduationStudent": int(student.version or 0),
            "graduationArchiveRecord": int(archive.version or 0),
            "materialRule": int(rule.version or 0),
        },
        "sensitivityLevel": "PERSONAL",
        "frozenAt": _iso(frozen_at),
    }
    return create_business_snapshot(
        db,
        module_code=MODULE_CODE,
        target_type=MANIFEST_TARGET_TYPE,
        target_id=str(student.id),
        revision=int(revision),
        payload=payload,
        user=user,
        sensitivity_level="PERSONAL",
        subject_type="STUDENT",
        subject_id=str(student.student_id or student.id),
        batch_id=str(student.batch_id or "") or None,
        student_id=_int_or_none(student.student_id),
        college_id=_int_or_none(student.college_id),
        class_id=_int_or_none(student.class_id),
    )


__all__ = ["create_graduation_business_snapshot"]
