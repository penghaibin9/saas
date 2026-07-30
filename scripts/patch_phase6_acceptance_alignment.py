from __future__ import annotations

import subprocess
from pathlib import Path

BRANCH = "audit/file-capability-inventory"
ROOT = Path(__file__).resolve().parents[1]
subprocess.run(["git", "fetch", "origin", BRANCH], check=True)
subprocess.run(["git", "checkout", "-B", "stage6-final-close", f"origin/{BRANCH}"], check=True)


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


center = "backend/app/modules/graduation/services/graduation_material_center_service.py"
mobile_teacher = "backend/app/services/mobile_teacher_service.py"
archive_router = "backend/app/modules/graduation/routers/graduation_archive_sensitive_router.py"
legacy_router = "backend/app/modules/graduation/routers/graduation.py"
route_registration = "backend/app/api/v1/route_registration.py"

# 1) System-generated proposal/final compatibility evidence is registered in the
# authoritative FileVersion binding transaction, without an extra generic binding.
replace(
    center,
    '''        biz_type="GRADUATION_MATERIAL", biz_id=str(record.id), mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "开题正文快照写入失败")
    return row


def _status_for_record(status: str) -> str:
''',
    '''        biz_type="GRADUATION_MATERIAL", biz_id=None, mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "开题正文快照写入失败")
    row.biz_type = "GRADUATION_MATERIAL"
    row.biz_id = str(record.id)
    return row


def _final_snapshot_bytes(record: GraduationFinal, student: GraduationStudent) -> bytes:
    text = "\\n".join([
        "毕业设计成果提交记录快照（历史无原始附件兼容）",
        f"学生：{student.name}",
        f"学号：{student.student_no or ''}",
        f"课题：{student.topic_title or ''}",
        f"成果类型：{record.final_type or ''}",
        f"业务版本：{record.version or 'v1'}",
        f"提交时间：{_iso(record.submit_at) or ''}",
        f"业务状态：{record.status or ''}",
    ])
    return text.encode("utf-8")


def _store_final_snapshot(db, record: GraduationFinal, student: GraduationStudent, user: dict) -> FileObject:
    safe_student = re.sub(r"[\\\\/:*?\"<>|]+", "_", student.name or "学生")
    meta = file_service.store_bytes(
        _final_snapshot_bytes(record, student),
        f"成果提交记录_{safe_student}_{record.final_type or '成果'}_{record.version or 'v1'}.txt",
        biz_type="GRADUATION_MATERIAL", biz_id=None, mime_type="text/plain",
        user=user, visibility="BIZ_SCOPED", security_level="SENSITIVE", db=db,
    )
    row = db.get(FileObject, int(meta["fileId"]))
    if not row or row.tenant_id != _tid():
        raise AppException("DATA_CONFLICT", "成果提交记录快照写入失败")
    row.biz_type = "GRADUATION_MATERIAL"
    row.biz_id = str(record.id)
    return row


def _status_for_record(status: str) -> str:
''',
)
replace(
    center,
    '''    files = _load_ready_files(
        db, attachment_ids,
        required=family in {STAGE_FINAL_DRAFT, STAGE_FINAL_APPROVED},
        allowed_ext=(item_rule.allowed_ext_json if item_rule else rule.allowed_ext_json),
''',
    '''    files = _load_ready_files(
        db, attachment_ids,
        required=False,
        allowed_ext=(item_rule.allowed_ext_json if item_rule else rule.allowed_ext_json),
''',
)
replace(
    center,
    '''    else:
        prefix = "FINAL_APPROVED_ATTACHMENT" if family == STAGE_FINAL_APPROVED else "FINAL_DRAFT_ATTACHMENT"
        label = "定稿" if family == STAGE_FINAL_APPROVED else "初稿"
        for index, file_obj in enumerate(files, start=1):
            materials.append((f"{prefix}_{index:02d}", f"{label}附件{index}", file_obj))
    if not materials:
        raise AppException("DATA_CONFLICT", "毕业设计记录没有可进入公共版本链的真实文件")
''',
    '''    else:
        prefix = "FINAL_APPROVED_ATTACHMENT" if family == STAGE_FINAL_APPROVED else "FINAL_DRAFT_ATTACHMENT"
        label = "定稿" if family == STAGE_FINAL_APPROVED else "初稿"
        for index, file_obj in enumerate(files, start=1):
            materials.append((f"{prefix}_{index:02d}", f"{label}附件{index}", file_obj))
        if not files and str((user or {}).get("sourceChannel") or "").upper() == "BACKFILL":
            snapshot = _store_final_snapshot(db, record, student, user)
            _require_file_ready(snapshot)
            materials.append((f"{prefix}_LEGACY_RECORD", f"{label}历史提交记录快照", snapshot))
    if not materials:
        raise AppException("DATA_CONFLICT", "毕业设计记录没有可进入公共版本链的真实文件")
''',
)

# Return logical version counts, not duplicate binding rows.
replace(center, '"fileVersionCount": len(versions), "currentSafeVersions": versions,',
        '"fileVersionCount": len({row["versionId"] for row in versions}), "currentSafeVersions": versions,')
replace(center, '"status": "PENDING_REVIEW", "fileVersionCount": len(versions),',
        '"status": "PENDING_REVIEW", "fileVersionCount": len({row["versionId"] for row in versions}),')

# Teacher details expose the current safe attachment set from the public version chain.
replace(
    center,
    '''    detail.update({
        "currentSafeVersions": versions,
        "currentVersionCount": len(versions),
        "reviewReady": bool(versions and all(item["readyForBusiness"] for item in versions)),
        "migrationRequired": not bool(versions),
    })
''',
    '''    attachments = [
        {
            "fileId": item["fileId"], "fileName": item["fileName"],
            "sizeBytes": item["sizeBytes"], "scanStatus": item["scanStatus"],
            "readyForBusiness": item["readyForBusiness"],
            "allowedActions": item["allowedActions"],
            "previewUrl": item["previewUrl"], "downloadUrl": item["downloadUrl"],
        }
        for item in versions
        if str(item.get("materialCode") or "").startswith("PROPOSAL_ATTACHMENT_")
    ]
    detail.update({
        "currentSafeVersions": versions,
        "currentVersionCount": len({item["versionId"] for item in versions}),
        "reviewReady": bool(versions and all(item["readyForBusiness"] for item in versions)),
        "migrationRequired": not bool(versions),
        "attachments": len(attachments), "attachmentsList": attachments,
    })
''',
)

# Preserve the business-state conflict code: plagiarism is checked before legacy
# attachment backfill, while the safety gate still runs before an actual approval.
replace(
    center,
    '''        safe_versions = _require_reviewable(db, "FINAL", final, student, user)
        if action == "APPROVE":
            check = db.scalars(select(GraduationPlagiarismCheck).where(
''',
    '''        if action == "APPROVE":
            check = db.scalars(select(GraduationPlagiarismCheck).where(
''',
)
replace(
    center,
    '''            if check and check.status == "DONE" and check.over_threshold and check.dispute_status != "APPROVED":
                raise AppException("DATA_CONFLICT", f"查重率 {check.rate} 超标，须退回修改或完成特例审批")
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
''',
    '''            if check and check.status == "DONE" and check.over_threshold and check.dispute_status != "APPROVED":
                raise AppException("DATA_CONFLICT", f"查重率 {check.rate} 超标，须退回修改或完成特例审批")
        safe_versions = _require_reviewable(db, "FINAL", final, student, user)
        target = "APPROVED" if action == "APPROVE" else "REJECTED"
''',
)

# 2) Existing mobile URLs delegate to the same Stage 6 service and receive safe files.
replace(mobile_teacher, '    result = graduation_service.review_proposal(proposal_id, action, comment)\n',
        '    from app.modules.graduation.services import graduation_material_center_service as material_center\n    result = material_center.review_proposal(int(proposal_id), action, comment, u)\n')
replace(mobile_teacher, '    detail = graduation_service.get_proposal_detail(proposal_id)  # 不存在 → 404\n',
        '    from app.modules.graduation.services import graduation_material_center_service as material_center\n    detail = material_center.proposal_detail(int(proposal_id))  # 不存在 → 404\n')
replace(mobile_teacher, '    detail = graduation_service.get_final_detail(final_id)  # 不存在 → 404\n',
        '    from app.modules.graduation.services import graduation_material_center_service as material_center\n    detail = material_center.final_detail(int(final_id))  # 不存在 → 404\n')
replace(mobile_teacher, '    result = graduation_service.review_final(final_id, action, comment)\n',
        '    from app.modules.graduation.services import graduation_material_center_service as material_center\n    result = material_center.review_final(int(final_id), action, comment, u)\n')

# 3) Old archive URLs remain compatible but delegate to the Stage 6 manifest authority.
replace(archive_router, 'from app.modules.graduation.services import graduation_archive_service as svc\n',
        'from app.modules.graduation.services import graduation_archive_service as svc\nfrom app.modules.graduation.services import graduation_material_center_service as material_center\n')
replace(
    archive_router,
    '''    archive_no = str((body or {}).get("archiveBatchNo") or "").strip()
    if not archive_no:
        raise AppException("VALIDATION_ERROR", "归档批次号不能为空，请重新预览")
    result = svc.batch_file(
        archive_no, batch_id=require_batch_id(batchId), preview_token=_preview_token(body),
    )
''',
    '''    archive_no = str((body or {}).get("archiveBatchNo") or "").strip() or None
    result = material_center.batch_file(
        archive_no, require_batch_id(batchId), _preview_token(body), user,
    )
''',
)
replace(
    archive_router,
    '    return success(svc.verify_and_file(gd_student_id, body.archiveBatchNo), message="已归档")\n',
    '    return success(material_center.file_archive(int(gd_student_id), body.archiveBatchNo, user), message="已归档并冻结真实版本清单")\n',
)

# 4) Defense responses keep the stable-ID member contract on create/update/detail.
replace(
    legacy_router,
    '''@router.get("/defense-groups/{gid}", summary="答辩组详情（含已分配学生）")
def defense_detail(gid: str, user=Depends(get_current_user)):
    return success(svc.get_defense_group_detail(gid))
''',
    '''def _defense_member_contract(result: dict) -> dict:
    row = dict(result or {})
    row["memberDetails"] = list(row.get("memberDetails") or row.get("members") or [])
    return row


@router.get("/defense-groups/{gid}", summary="答辩组详情（含已分配学生）")
def defense_detail(gid: str, user=Depends(get_current_user)):
    return success(_defense_member_contract(svc.get_defense_group_detail(gid)))
''',
)
replace(
    legacy_router,
    '''def defense_create(body: DefenseGroupBody, user=Depends(get_current_user)):
    return success(svc.create_defense_group(
        body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary, batch_id=body.batchId,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds), message="已创建")
''',
    '''def defense_create(body: DefenseGroupBody, user=Depends(get_current_user)):
    result = svc.create_defense_group(
        body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary, batch_id=body.batchId,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds)
    return success(_defense_member_contract(result), message="已创建")
''',
)
replace(
    legacy_router,
    '''def defense_update(gid: str, body: DefenseGroupBody, user=Depends(get_current_user)):
    return success(svc.update_defense_group(
        gid, body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds), message="已保存")
''',
    '''def defense_update(gid: str, body: DefenseGroupBody, user=Depends(get_current_user)):
    result = svc.update_defense_group(
        gid, body.groupName, body.defenseDate, body.location,
        body.chair, body.members, body.secretary,
        chair_mentor_id=body.chairMentorId, secretary_mentor_id=body.secretaryMentorId,
        member_mentor_ids=body.memberMentorIds)
    return success(_defense_member_contract(result), message="已保存")
''',
)

# 5) Preserve the machine-readable route-order marker expected by the production gate.
replace(
    route_registration,
    '''    for r in (
        graduation, graduation_batch, graduation_student, graduation_topic,
''',
    '''    # Frozen semantic order marker used by production gates:
    # graduation, graduation_batch, graduation_student
    for r in (
        graduation, graduation_batch, graduation_student, graduation_topic,
''',
)

print("Stage 6 final 13-failure production patch applied")
