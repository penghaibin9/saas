from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one old block, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Stage-2 前历史附件：仅允许安全、BIZ_SCOPED、明确业务元数据的首次绑定。
replace_once(
    "backend/app/services/file_service.py",
    '''    permission = _MEMORY_BIZ_VIEW_PERM.get(str(getattr(file_obj, "biz_type", "") or "").upper())
    return bool(permission and has_permission(user, permission))


def authorize_file_access(user: dict, file_obj, action: str = "download") -> bool:
''',
    '''    permission = _MEMORY_BIZ_VIEW_PERM.get(str(getattr(file_obj, "biz_type", "") or "").upper())
    return bool(permission and has_permission(user, permission))


_LEGACY_INTERNSHIP_BIND_PERMISSIONS = (
    "internship.student.material.view",
    "internship.application.review",
    "internship.attendance.review",
    "internship.leave.review",
    "internship.agreement.manage",
    "internship.eval.enterprise.manage",
    "internship.score.manage",
    "internship.risk.handle",
    "internship.archive.prepare",
)


def _legacy_unbound_business_authorized(user: dict, file_obj, action: str) -> bool:
    """Stage-2 前无 Binding 文件的窄兼容，只允许首次业务接管，不允许直接枚举下载。"""
    if action not in {"bind", "submit", "archive"} or not _ready(file_obj):
        return False
    if str(getattr(file_obj, "visibility", "") or "").upper() != "BIZ_SCOPED":
        return False
    biz_type = str(getattr(file_obj, "biz_type", "") or "").upper().strip()
    biz_id = str(getattr(file_obj, "biz_id", "") or "").strip()
    if not biz_type or not biz_id:
        return False
    actor = user or {}
    if is_super_admin(actor) or has_permission(actor, "systemAdmin.file.manage") or has_permission(actor, "*"):
        return True
    if str(actor.get("userType") or "").upper() == "STUDENT":
        values = {
            str(actor.get("studentId") or "").strip(),
            str(actor.get("studentNo") or "").strip(),
        }
        return any(value and (biz_id == value or biz_id.endswith(f":{value}")) for value in values)
    if biz_type == "INTERNSHIP" or biz_type.startswith("INTERNSHIP_"):
        return any(has_permission(actor, code) for code in _LEGACY_INTERNSHIP_BIND_PERMISSIONS)
    permission = _MEMORY_BIZ_VIEW_PERM.get(biz_type)
    return bool(permission and has_permission(actor, permission))


def authorize_file_access(user: dict, file_obj, action: str = "download") -> bool:
''',
)
replace_once(
    "backend/app/services/file_service.py",
    '''        # A freshly uploaded object has no business binding yet. Only its uploader
        # or an explicit file administrator may perform the first bind/submit after
        # the security gate has reached CLEAN/AVAILABLE. Once any binding exists,
        # the authoritative business resolver remains mandatory.
        if not bindings and action in {"bind", "submit"}:
            actor_id = _actor_user_id(actor)
            owner_id = getattr(file_obj, "owner_user_id", None) or getattr(file_obj, "created_by", None)
            return bool(
                _ready(file_obj)
                and (
                    is_super_admin(actor)
                    or has_permission(actor, "systemAdmin.file.manage")
                    or has_permission(actor, "*")
                    or (actor_id and owner_id and int(actor_id) == int(owner_id))
                )
            )
        return authorize_file_object(
''',
    '''        # A freshly uploaded object has no business binding yet. Only its uploader
        # or an explicit file administrator may perform the first bind/submit after
        # the security gate has reached CLEAN/AVAILABLE. Stage-2 前的历史 BIZ_SCOPED
        # 文件仅允许通过窄兼容完成首次业务接管；预览/下载仍必须走正式 resolver。
        if not bindings:
            if action in {"bind", "submit"}:
                actor_id = _actor_user_id(actor)
                owner_id = getattr(file_obj, "owner_user_id", None) or getattr(file_obj, "created_by", None)
                if bool(
                    _ready(file_obj)
                    and (
                        is_super_admin(actor)
                        or has_permission(actor, "systemAdmin.file.manage")
                        or has_permission(actor, "*")
                        or (actor_id and owner_id and int(actor_id) == int(owner_id))
                    )
                ):
                    return True
            if _legacy_unbound_business_authorized(actor, file_obj, action):
                return True
        return authorize_file_object(
''',
)

# 2) 结构化开题快照使用已提交的新会话对象，不在旧 REPEATABLE READ 事务中重新读取。
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''def _file_ready(row: FileObject) -> bool:
    scan = str(row.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(row.status) and scan in READY_SCAN_STATES and row.sha256)


def _require_file_ready(row: FileObject) -> None:
    if not _file_ready(row):
        raise AppException(
            "DATA_CONFLICT",
            "材料仍在安全扫描、扫描失败或已被隔离，不能提交、审核或归档",
            details={"fileId": str(row.id), "status": row.status, "scanStatus": row.scan_status},
        )
''',
    '''def _file_ready(row: FileObject | None) -> bool:
    if row is None:
        return False
    scan = str(row.scan_status or SCAN_NOT_REQUIRED).upper()
    return bool(is_downloadable_status(row.status) and scan in READY_SCAN_STATES and row.sha256)


def _require_file_ready(row: FileObject | None) -> None:
    if not _file_ready(row):
        raise AppException(
            "DATA_CONFLICT",
            "材料仍在安全扫描、扫描失败或已被隔离，不能提交、审核或归档",
            details={
                "fileId": str(getattr(row, "id", "") or ""),
                "status": getattr(row, "status", None),
                "scanStatus": getattr(row, "scan_status", None),
            },
        )
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''    if required and not ids:
        raise AppException("VALIDATION_ERROR", "请先上传毕业设计材料再提交")
''',
    '''    if required and not ids:
        raise AppException("VALIDATION_ERROR", "请先上传毕业设计材料附件再提交")
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_center_service.py",
    '''    if family == STAGE_PROPOSAL:
        snapshot = _store_proposal_snapshot(record, student, user)
        snapshot = db.get(FileObject, int(snapshot.id))
        _require_file_ready(snapshot)
''',
    '''    if family == STAGE_PROPOSAL:
        snapshot = _store_proposal_snapshot(record, student, user)
        # snapshot 已在独立写会话提交并从该会话分离；旧业务事务处于 MySQL
        # REPEATABLE READ 时不得再次 db.get，否则可能得到 None。
        _require_file_ready(snapshot)
''',
)

# 3) 固定统计路径先于动态详情路径，同时旧 URL 直接委托 Stage-6 权威 Service。
replace_once(
    "backend/app/api/v1/route_registration.py",
    '''    d = deps["gd"]
    api_router.include_router(graduation_p0_guard.router, dependencies=d)
    # 阶段6公共版本路由必须先于旧开题、成果和归档路由。
    api_router.include_router(graduation_material_center.router, dependencies=d)
''',
    '''    d = deps["gd"]
    api_router.include_router(graduation_p0_guard.router, dependencies=d)
    # 先注册旧聚合 Router 中的 /proposals/stats、/finals/stats 等固定路径；
    # 其同 URL 详情/审核函数已直接委托 Stage-6 权威 Service，不再依赖路由抢占。
    api_router.include_router(graduation.router, dependencies=d)
    api_router.include_router(graduation_material_center.router, dependencies=d)
''',
)
replace_once(
    "backend/app/api/v1/route_registration.py",
    '''    for r in (
        graduation, graduation_batch, graduation_student, graduation_topic,
''',
    '''    for r in (
        graduation_batch, graduation_student, graduation_topic,
''',
)
replace_once(
    "backend/app/api/v1/route_registration.py",
    '''    # 与旧移动端相同 URL，必须先于 mobile.router 注册。
''',
    '''    # 与旧移动端相同 URL，必须先于旧移动端聚合 Router 注册。
''',
)
replace_once(
    "backend/app/modules/graduation/routers/graduation.py",
    '''@router.get("/proposals/{pid}", summary="开题批阅详情")
def proposal_detail(pid: str, user=Depends(get_current_user)):
    return success(svc.get_proposal_detail(pid))
''',
    '''@router.get("/proposals/{pid}", summary="开题批阅详情")
def proposal_detail(pid: str, user=Depends(get_current_user)):
    from app.modules.graduation.services import graduation_material_center_service as material_center
    return success(material_center.proposal_detail(int(pid)))
''',
)
replace_once(
    "backend/app/modules/graduation/routers/graduation.py",
    '''@router.post("/proposals/{pid}/review", summary="批阅开题（驳回原因≥5字）")
def proposal_review(pid: str, body: ReviewBody, user=Depends(require_permission("graduationDesign.proposal.review"))):
    return success(svc.review_proposal(pid, body.action, body.comment), message="已批阅")
''',
    '''@router.post("/proposals/{pid}/review", summary="批阅开题（驳回原因≥5字）")
def proposal_review(pid: str, body: ReviewBody, user=Depends(require_permission("graduationDesign.proposal.review"))):
    from app.modules.graduation.services import graduation_material_catalog_service as material_catalog
    from app.modules.graduation.services import graduation_material_center_service as material_center
    result = material_center.review_proposal(int(pid), body.action, body.comment, user)
    material_catalog.sync_record("PROPOSAL", int(pid), user)
    return success(result, message="已批阅")
''',
)
replace_once(
    "backend/app/modules/graduation/routers/graduation.py",
    '''@router.post("/finals/{fid}/review", summary="批阅成果（退回原因≥5字；查重超标 GD-R09 不可直接通过）")
def final_review(fid: str, body: ReviewBody, user=Depends(get_current_user)):
    return success(svc.review_final(fid, body.action, body.comment), message="已批阅")
''',
    '''@router.post("/finals/{fid}/review", summary="批阅成果（退回原因≥5字；查重超标 GD-R09 不可直接通过）")
def final_review(fid: str, body: ReviewBody, user=Depends(get_current_user)):
    from app.modules.graduation.services import graduation_material_catalog_service as material_catalog
    from app.modules.graduation.services import graduation_material_center_service as material_center
    result = material_center.review_final(int(fid), body.action, body.comment, user)
    material_catalog.sync_record("FINAL", int(fid), user)
    return success(result, message="已批阅")
''',
)

# 4) 所有安全 Router 按“模块 + endpoint”显式登记权限，避免同名函数碰撞和未登记 403。
replace_once(
    "backend/app/core/graduation_permissions.py",
    '''GRADUATION_ENDPOINT_PERMISSION_OVERRIDES = {
    "graduation_batch.batch_archive": "graduationDesign.batch.archive",
    "graduation_student.batch_archive": "graduationDesign.student.manage",
}
''',
    '''GRADUATION_ENDPOINT_PERMISSION_OVERRIDES = {
    "graduation_batch.batch_archive": "graduationDesign.batch.archive",
    "graduation_student.batch_archive": "graduationDesign.student.manage",

    # Stage 6 材料中心：显式动作权限；文件对象范围仍由 resolver 二次收敛。
    "graduation_material_center.material_rules": "graduationDesign.student.view",
    "graduation_material_center.create_material_rule": "graduationDesign.student.manage",
    "graduation_material_center.activate_material_rule": "graduationDesign.student.manage",
    "graduation_material_center.material_overview": "graduationDesign.student.view",
    "graduation_material_center.backfill_materials": "graduationDesign.student.manage",
    "graduation_material_center.material_library": "graduationDesign.student.view",
    "graduation_material_center.submit_material": "graduationDesign.student.manage",
    "graduation_material_center.review_material_item": "graduationDesign.review.submit",
    "graduation_material_center.proposal_versions": "graduationDesign.proposal.view",
    "graduation_material_center.final_versions": "graduationDesign.final.view",
    "graduation_material_center.template_catalog": "graduationDesign.template.view",
    "graduation_material_center.publish_template_asset": "graduationDesign.template.manage",
    "graduation_material_center.update_template_status": "graduationDesign.template.manage",
    "graduation_material_center.template_versions": "graduationDesign.template.view",
    "graduation_material_center.archive_manifest": "graduationDesign.archive.view",
    "graduation_material_center.freeze_archive_manifest": "graduationDesign.archive.file",
    "graduation_material_center.revoke_archive_manifest": "graduationDesign.archive.file",
    "graduation_material_center.create_archive_export": "graduationDesign.archive.export",
    "graduation_material_center.archive_export_job": "graduationDesign.archive.view",
    "graduation_material_center.retry_archive_export": "graduationDesign.archive.export",
    "graduation_material_center.archive_export_ticket": "graduationDesign.archive.export",
    "graduation_material_center.revoke_archive_export": "graduationDesign.archive.export",
    "graduation_material_center.archive_package": "graduationDesign.archive.export",
    "graduation_material_center.batch_archive_package": "graduationDesign.archive.export",
    "graduation_material_center.material_file_ticket": "graduationDesign.student.view",
    "graduation_material_center.preview_material": "graduationDesign.student.view",
    "graduation_material_center.download_material": "graduationDesign.student.view",
    "graduation_material_center.download_package": "graduationDesign.archive.view",
    "graduation_material_center.proposal_detail": "graduationDesign.proposal.view",
    "graduation_material_center.review_proposal": "graduationDesign.proposal.review",
    "graduation_material_center.final_detail": "graduationDesign.final.view",
    "graduation_material_center.review_final": "graduationDesign.final.review",
    "graduation_material_center.batch_file": "graduationDesign.archive.file",
    "graduation_material_center.file_archive": "graduationDesign.archive.file",

    # 批次安全 Router：函数名与旧 Router 不同，必须按模块显式映射。
    "graduation_sensitive_router.gd_student_stats": "graduationDesign.student.view",
    "graduation_sensitive_router.gd_stats_overview": "graduationDesign.dashboard.view",
    "graduation_sensitive_router.gd_stats_college": "graduationDesign.dashboard.view",
    "graduation_sensitive_router.plagiarism_stats": "graduationDesign.plagiarism.view",
    "graduation_sensitive_router.plagiarism_list": "graduationDesign.plagiarism.view",
    "graduation_sensitive_router.plagiarism_submit": "graduationDesign.plagiarism.start",
    "graduation_sensitive_router.plagiarism_result": "graduationDesign.plagiarism.result",
    "graduation_sensitive_router.plagiarism_dispute": "graduationDesign.plagiarism.start",
    "graduation_sensitive_router.plagiarism_dispute_review": "graduationDesign.plagiarism.disputeReview",
    "graduation_sensitive_router.review_stats": "graduationDesign.review.view",
    "graduation_sensitive_router.review_list": "graduationDesign.review.view",
    "graduation_sensitive_router.review_assign": "graduationDesign.review.assign",
    "graduation_sensitive_router.review_submit": "graduationDesign.review.submit",
    "graduation_sensitive_router.review_return": "graduationDesign.review.return",
    "graduation_sensitive_router.defense_stats": "graduationDesign.defense.view",
    "graduation_sensitive_router.defense_list": "graduationDesign.defense.view",
    "graduation_sensitive_router.defense_entry": "graduationDesign.defense.score",
    "graduation_sensitive_router.defense_absence": "graduationDesign.defense.scoreConfirm",
    "graduation_sensitive_router.defense_confirm": "graduationDesign.defense.scoreConfirm",
    "graduation_sensitive_router.defense_revoke": "graduationDesign.defense.scoreConfirm",
    "graduation_sensitive_router.defense_second": "graduationDesign.defense.secondRound",
    "graduation_sensitive_router.grade_stats": "graduationDesign.grade.view",
    "graduation_sensitive_router.grade_list": "graduationDesign.grade.view",
    "graduation_sensitive_router.grade_detail": "graduationDesign.grade.view",
    "graduation_sensitive_router.grade_calculate": "graduationDesign.grade.calculate",
    "graduation_sensitive_router.grade_review": "graduationDesign.grade.review",
    "graduation_sensitive_router.grade_publish": "graduationDesign.grade.publish",
    "graduation_sensitive_router.grade_withdraw": "graduationDesign.grade.withdraw",
    "graduation_sensitive_router.archive_generate_preview": "graduationDesign.archive.preview",
    "graduation_sensitive_router.archive_generate_batch": "graduationDesign.archive.file",
    "graduation_sensitive_router.archive_file_preview": "graduationDesign.archive.preview",
    "graduation_sensitive_router.archive_file_batch": "graduationDesign.archive.file",
    "graduation_sensitive_router.student_import_confirm": "graduationDesign.student.import",

    "graduation_archive_sensitive_router.stats": "graduationDesign.archive.view",
    "graduation_archive_sensitive_router.list_rows": "graduationDesign.archive.view",
    "graduation_archive_sensitive_router.export_rows": "graduationDesign.archive.export",
    "graduation_archive_sensitive_router.batch_generate_preview": "graduationDesign.archive.preview",
    "graduation_archive_sensitive_router.batch_generate": "graduationDesign.archive.file",
    "graduation_archive_sensitive_router.batch_file_preview": "graduationDesign.archive.preview",
    "graduation_archive_sensitive_router.batch_file": "graduationDesign.archive.file",
    "graduation_archive_sensitive_router.detail": "graduationDesign.archive.view",
    "graduation_archive_sensitive_router.generate": "graduationDesign.archive.preview",
    "graduation_archive_sensitive_router.submit": "graduationDesign.archive.file",
    "graduation_archive_sensitive_router.file_record": "graduationDesign.archive.file",
    "graduation_archive_sensitive_router.reject": "graduationDesign.archive.file",

    "graduation_taskbook_sensitive_router.stats": "graduationDesign.taskbook.view",
    "graduation_taskbook_sensitive_router.list_rows": "graduationDesign.taskbook.view",
    "graduation_taskbook_sensitive_router.export_rows": "graduationDesign.taskbook.export",
    "graduation_taskbook_sensitive_router.detail": "graduationDesign.taskbook.view",
    "graduation_taskbook_sensitive_router.issue": "graduationDesign.taskbook.issue",
    "graduation_taskbook_sensitive_router.confirm": "graduationDesign.taskbook.confirmOnBehalf",
    "graduation_taskbook_sensitive_router.change": "graduationDesign.taskbook.update",
    "graduation_taskbook_sensitive_router.export_pdf": "graduationDesign.taskbook.export",

    "graduation_process_sensitive_router.guidance_stats": "graduationDesign.guidance.view",
    "graduation_process_sensitive_router.guidance_list": "graduationDesign.guidance.view",
    "graduation_process_sensitive_router.guidance_create": "graduationDesign.guidance.create",
    "graduation_process_sensitive_router.guidance_void": "graduationDesign.guidance.update",
    "graduation_process_sensitive_router.plan_list": "graduationDesign.guidance.view",
    "graduation_process_sensitive_router.plan_create": "graduationDesign.guidance.create",
    "graduation_process_sensitive_router.plan_checkin": "graduationDesign.guidance.update",
    "graduation_process_sensitive_router.plan_cancel": "graduationDesign.guidance.update",
    "graduation_process_sensitive_router.midterm_stats": "graduationDesign.midterm.review",
    "graduation_process_sensitive_router.midterm_list": "graduationDesign.midterm.review",
    "graduation_process_sensitive_router.midterm_detail": "graduationDesign.midterm.review",
    "graduation_process_sensitive_router.midterm_check": "graduationDesign.midterm.review",
    "graduation_process_sensitive_router.midterm_rectify": "graduationDesign.midterm.review",
    "graduation_process_sensitive_router.midterm_rectify_review": "graduationDesign.midterm.review",

    "graduation_material_sensitive_router.legacy_students": "graduationDesign.student.view",
    "graduation_material_sensitive_router.legacy_student_detail": "graduationDesign.student.view",
    "graduation_material_sensitive_router.final_detail": "graduationDesign.final.view",
}
''',
)

# 5) 材料审核动作完全由服务端 allowedActions 控制。
replace_once(
    "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
    '''from app.core.exceptions import AppException, not_found
''',
    '''from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
    '''            versions = file_maps.get(int(row.asset_id), []) if row.asset_id else []
            current_file = next((item for item in versions if item["isCurrent"]), None)
            spec = SPEC_BY_CODE.get(row.material_code, {})
            items.append({
''',
    '''            versions = file_maps.get(int(row.asset_id), []) if row.asset_id else []
            current_file = next((item for item in versions if item["isCurrent"]), None)
            spec = SPEC_BY_CODE.get(row.material_code, {})
            allowed_actions = list((current_file or {}).get("allowedActions", []))
            can_review = any(has_permission(user or {}, code) for code in (
                "graduationDesign.proposal.review",
                "graduationDesign.final.review",
                "graduationDesign.review.submit",
                "graduationDesign.defense.scoreConfirm",
                "graduationDesign.grade.review",
            ))
            if (
                current_file
                and current_file.get("readyForBusiness")
                and row.review_status == "PENDING"
                and can_review
                and "review" not in allowed_actions
            ):
                allowed_actions.append("review")
            items.append({
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_material_catalog_service.py",
    '''                "allowedActions": (current_file or {}).get("allowedActions", []),
''',
    '''                "allowedActions": allowed_actions,
''',
)
replace_once(
    "frontend/src/modules/graduation/views/GraduationMaterialCenterView.vue",
    '''                <div v-if="material.currentVersionId && material.reviewStatus === 'PENDING'" class="gm-review-actions">
''',
    '''                <div v-if="material.currentVersionId && material.reviewStatus === 'PENDING' && (material.allowedActions || []).includes('review')" class="gm-review-actions">
''',
)
replace_once(
    "frontend/src/modules/graduation/views/GraduationMaterialCenterView.vue",
    '''function normalizedFiles(material) { return (material.currentVersion ? [material.currentVersion] : []).map(normalizeFile) }
''',
    '''function normalizedFiles(material) { return (material.currentVersion ? [{ ...material.currentVersion, allowedActions: material.currentVersion.allowedActions || material.allowedActions || [] }] : []).map(normalizeFile) }
''',
)
replace_once(
    "backend/app/modules/graduation/routers/graduation_material_center.py",
    '''def update_template_status(policy_id: int, body: dict = Body(...), user=Depends(get_current_user)):
''',
    '''def update_template_status(policy_id: int, body: dict = Body(...), user=Depends(_require_material_manager)):
''',
)

print("Stage 6 root-cause patch applied")
