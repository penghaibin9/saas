"""岗位实习材料与证据中心，以及审核/归档安全优先路由。

本 Router 必须在历史 internship/insurance/process/archive Router 之前注册。
相同 URL 先执行文件扫描与真实版本清单门禁，再委托原业务 Service。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.api.v1.file_contract import validated_local_file_response
from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_agreement_service as agreement_svc
from app.modules.internship.services import internship_archive_service as archive_svc
from app.modules.internship.services import internship_insurance_service as insurance_svc
from app.modules.internship.services import internship_material_center_compat as material_svc
from app.modules.internship.services import internship_material_preview_access as material_tickets
from app.modules.internship.services import internship_process_report_service as report_svc
from app.services import audit_log

router = APIRouter(prefix="/internship", tags=["岗位实习-材料与证据中心"])


@router.get("/material-center", summary="实习材料与证据中心（按批次和数据范围）")
def material_center_list(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
    batchId: Optional[str] = None,
    keyword: Optional[str] = None,
    safetyStatus: Optional[str] = Query(None, pattern="^(READY|UNSAFE|NOT_SYNCED)?$"),
    user=Depends(require_permission("internship.archive.view")),
):
    items, total = material_svc.list_center(
        page, pageSize, batch_id=batchId, keyword=keyword,
        safety_status=safetyStatus, user=user,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/material-center/{internship_id}", summary="学生实习材料、文件版本和归档清单")
def material_center_detail(
    internship_id: int,
    user=Depends(require_permission("internship.archive.view")),
):
    return success(material_svc.record_detail(internship_id, user=user))


@router.post("/material-center/{internship_id}/sync", summary="将旧材料引用登记为资产和真实版本")
def material_center_sync(
    internship_id: int,
    user=Depends(require_permission("internship.archive.manage")),
):
    result = material_svc.synchronize(internship_id, user=user)
    audit_log.record(
        "同步实习材料版本", f"internship-material:{internship_id}",
        detail={"itemCount": len(result.get("items") or []),
                "unsafeCount": len(result.get("unsafe") or [])},
    )
    return success(result, message="材料版本已同步")


@router.get("/material-center/{internship_id}/manifest", summary="查看实习归档真实文件版本清单")
def material_center_manifest(
    internship_id: int,
    user=Depends(require_permission("internship.archive.view")),
):
    return success(material_svc.get_manifest(internship_id, user=user))


@router.post("/material-center/files/{file_id}/ticket", summary="签发实习材料预览/下载短时票据")
def material_file_ticket(
    file_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("internship.archive.view")),
):
    action = str((body or {}).get("action") or "preview")
    return success(material_tickets.issue_ticket(file_id, action, user))


@router.get("/material-center/files/{file_id}/preview", summary="使用业务票据站内预览当前安全实习材料")
def preview_material(
    file_id: int,
    ticket: str = Query(...),
    user=Depends(require_permission("internship.archive.view")),
):
    path, filename = material_tickets.consume_ticket(file_id, "preview", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="INTERNSHIP_VERSIONED_MATERIAL_PREVIEW",
        audit_target=f"internship-file:{file_id}",
        inline=True,
        audit_detail={"fileId": str(file_id), "surface": "STAFF_PC", "businessTicket": True},
    )


@router.get("/material-center/files/{file_id}/download", summary="使用一次性业务票据下载当前安全实习材料")
def download_material(
    file_id: int,
    ticket: str = Query(...),
    user=Depends(require_permission("internship.archive.view")),
):
    path, filename = material_tickets.consume_ticket(file_id, "download", ticket, user)
    return validated_local_file_response(
        path,
        filename=filename,
        audit_action="INTERNSHIP_VERSIONED_MATERIAL_DOWNLOAD",
        audit_target=f"internship-file:{file_id}",
        audit_detail={"fileId": str(file_id), "surface": "STAFF_PC", "businessTicket": True},
    )


# ── 安全优先覆盖：必须位于旧路由之前 ─────────────────────────────

@router.post("/agreements/{agreement_id}/school-confirm", summary="学校确认协议（安全版本门禁）")
def agreement_school_confirm_guard(
    agreement_id: str,
    body: dict | None = Body(default=None),
    user=Depends(require_permission("internship.agreement.schoolConfirm")),
):
    material_svc.preflight_agreement(agreement_id, user=user)
    result = agreement_svc.school_confirm(user, agreement_id, body)
    audit_log.record(
        "学校确认三方协议生效", f"internship-agreement:{agreement_id}",
        detail={**result, "fileVersionGate": "PASSED"},
    )
    return success(result, message="协议已生效")


@router.post("/insurances/{insurance_id}/verify", summary="核验实习保险（安全版本门禁）")
def insurance_verify_guard(
    insurance_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("internship.insurance.verify")),
):
    payload = body or {}
    action = str(payload.get("action") or "").upper()
    if action == "APPROVE":
        material_svc.preflight_insurance(insurance_id, user=user)
    result = insurance_svc.verify_insurance(
        insurance_id, action, payload.get("comment", ""),
        expected_version=payload.get("expectedVersion"), user=user,
    )
    return success(result)


@router.post("/process-reports/{report_id}/review", summary="复核过程报告（生成不可变版本快照）")
def process_report_review_guard(
    report_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("internship.report.review")),
):
    payload = body or {}
    action = str(payload.get("action") or "").upper()
    if action == "APPROVE":
        material_svc.preflight_process_report(report_id, user=user)
    result = report_svc.review_report(
        report_id, action, payload.get("comment", ""), user=user,
        expected_version=payload.get("expectedVersion", payload.get("version")),
    )
    return success(result)


@router.post("/archive/{internship_id}/archive", summary="归档学生（冻结真实 file_version 清单）")
def archive_student_guard(
    internship_id: int,
    body: dict = Body(default={}),
    user=Depends(require_permission("internship.archive.execute")),
):
    payload = body or {}
    result = material_svc.archive_with_manifest(
        user, internship_id,
        force=bool(payload.get("force")),
        force_reason=payload.get("forceReason") or "",
        evidence_file_ids=payload.get("evidenceFileIds") or [],
        expected_version=payload.get("expectedVersion", payload.get("version")),
        record_expected_version=payload.get(
            "recordExpectedVersion", payload.get("recordVersion")
        ),
    )
    receipt = result.get("operationReceipt") or {}
    audit_log.record(
        "归档实习学生", f"internship-archive:{internship_id}",
        detail={"manifestId": receipt.get("manifestId"),
                "manifestSha256": receipt.get("manifestSha256"),
                "fileVersionCount": receipt.get("fileVersionCount")},
    )
    return success(result, message="归档完成")


@router.post("/archive/{internship_id}/preflight", summary="归档预检（服务端事实与文件安全回执）")
def archive_preflight_guard(
    internship_id: int,
    user=Depends(require_permission("internship.archive.view")),
):
    result = archive_svc.preflight_archive(internship_id, user=user)
    audit_log.record(
        "预检实习归档", f"internship-archive:{internship_id}",
        detail=result.get("preflightReceipt") or {},
    )
    return success(result, message="归档预检完成")


@router.get("/archive/{internship_id}/employment-transition", summary="按已发布冻结结果衔接就业")
def archive_employment_transition(
    internship_id: int,
    user=Depends(require_permission("internship.employment.view")),
):
    return success(archive_svc.employment_transition_context(internship_id, user=user))


@router.post("/archive/{internship_id}/package", summary="按冻结 file_version 清单生成归档包")
def archive_package_guard(
    internship_id: int,
    user=Depends(require_permission("internship.archive.package")),
):
    result = material_svc.build_versioned_package(internship_id, user=user)
    audit_log.record(
        "生成实习归档包", f"internship-archive:{internship_id}",
        detail={"manifestId": result.get("manifestId"),
                "packageVersion": result.get("packageVersion"),
                "fileId": result.get("fileId")},
    )
    return success(result, message="归档包已生成")


@router.post("/archive-packages/{package_id}/restore-check", summary="校验归档包恢复行数与哈希")
def archive_package_restore_check(
    package_id: int,
    user=Depends(require_permission("internship.archive.package")),
):
    result = material_svc.verify_package_for_restore(package_id, user=user)
    audit_log.record(
        "校验实习归档恢复包", f"internship-archive-package:{package_id}",
        detail=result.get("operationReceipt") or {},
    )
    return success(result, message="恢复校验通过")


@router.post("/archive-batches/{batch_id}/packages", summary="按冻结 Manifest 流式生成批次归档分片")
def archive_batch_package_guard(
    batch_id: int,
    body: Optional[dict] = Body(None),
    user=Depends(require_permission("internship.archive.package")),
):
    payload = body or {}
    result = material_svc.build_batch_versioned_package(
        batch_id, user=user,
        after_id=payload.get("afterId", 0),
        limit=payload.get("limit", 20),
    )
    audit_log.record(
        "生成实习批次归档包", f"internship-archive-batch:{batch_id}",
        detail=result.get("operationReceipt") or {},
    )
    return success(result, message="批次归档分片已生成")


@router.get("/archive-batch-packages/{package_id}/download", summary="下载数据范围内的批次归档包")
def archive_batch_package_download(
    package_id: int,
    user=Depends(require_permission("internship.archive.package")),
):
    path, filename = material_svc.resolve_batch_package_download(package_id, user=user)
    return validated_local_file_response(
        path, filename=filename, media_type="application/zip",
        audit_action="INTERNSHIP_ARCHIVE_BATCH_PACKAGE_DOWNLOAD",
        audit_target=f"internship-archive-batch-package:{package_id}",
        audit_detail={"packageId": str(package_id), "scopeChecked": True},
    )


@router.post("/archive/{internship_id}/revoke", summary="撤销归档并失效版本清单")
def archive_revoke_guard(
    internship_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("internship.archive.manage")),
):
    payload = body or {}
    reason = str(payload.get("reason") or "").strip()
    result = material_svc.revoke_with_manifests(
        user, internship_id, reason,
        expected_version=payload.get("expectedVersion", payload.get("version")),
        record_expected_version=payload.get(
            "recordExpectedVersion", payload.get("recordVersion")
        ),
    )
    audit_log.record(
        "撤销实习归档", f"internship-archive:{internship_id}", detail=result,
    )
    return success(result, message="已撤销归档")
