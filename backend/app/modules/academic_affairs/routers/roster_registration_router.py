"""D2-S 学籍名册与注册管理正式 Router。

纯结构迁移：复用 legacy DTO、URL、method、permission、参数默认值与 canonical service。
三条同步导出继续由 academic_export_compat_router 先行接管，不在这里复制第三份 owner。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Path, UploadFile

from app.core.permissions import require_any_permission, require_permission
from app.core.response import paginate, success
from app.core.security import require_staff
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_service as svc
from app.modules.academic_affairs.services import roster_registration_convenience_service as convenience

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

# Move Only：沿用历史 DTO 对象，避免 Pydantic/OpenAPI 合同漂移。
ExcelImportRows = legacy.ExcelImportRows
ExcelErrorRows = legacy.ExcelErrorRows
RosterCorrectionCreate = legacy.RosterCorrectionCreate
RosterCorrectionReview = legacy.RosterCorrectionReview
RosterRevealBody = legacy.RosterRevealBody
RegBatchCreate = legacy.RegBatchCreate
RegisterBody = legacy.RegisterBody
EligibilityVerifyBody = legacy.EligibilityVerifyBody
DeferralApplyBody = legacy.DeferralApplyBody
DeferralReviewBody = legacy.DeferralReviewBody
ExceptionCreateBody = legacy.ExceptionCreateBody
ExceptionResolveBody = legacy.ExceptionResolveBody
xlsx_util = legacy.xlsx_util

_ROSTER_VIEW = legacy._ROSTER_VIEW
_ROSTER_IMPORT = legacy._ROSTER_IMPORT
_ROSTER_CORRECTION_APPLY = legacy._ROSTER_CORRECTION_APPLY
_ROSTER_CORRECTION_VIEW = legacy._ROSTER_CORRECTION_VIEW
_ROSTER_CORRECTION_REVIEW = legacy._ROSTER_CORRECTION_REVIEW
_REG_ARCHIVE_VIEW = legacy._REG_ARCHIVE_VIEW
_REG_ARCHIVE_MANAGE = legacy._REG_ARCHIVE_MANAGE
_REG_ELIGIBILITY_VIEW = legacy._REG_ELIGIBILITY_VIEW
_REG_ELIGIBILITY_VERIFY = legacy._REG_ELIGIBILITY_VERIFY
_REG_UNREG_VIEW = legacy._REG_UNREG_VIEW
_REG_UNREG_SCAN = legacy._REG_UNREG_SCAN
_REG_DEFERRAL_VIEW = legacy._REG_DEFERRAL_VIEW
_REG_DEFERRAL_APPLY = legacy._REG_DEFERRAL_APPLY
_REG_DEFERRAL_APPROVE = legacy._REG_DEFERRAL_APPROVE
_REG_EXCEPTION_VIEW = legacy._REG_EXCEPTION_VIEW
_REG_EXCEPTION_CREATE = legacy._REG_EXCEPTION_CREATE
_REG_EXCEPTION_RESOLVE = legacy._REG_EXCEPTION_RESOLVE


@router.get("/roster", summary="学籍名册（只读主档，脱敏）")
def roster(keyword: Optional[str] = None, status: Optional[str] = None,
           page: int = 1, pageSize: int = 20,
           user=Depends(require_permission(_ROSTER_VIEW))):
    items, total = svc.roster(user, keyword, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# 字面量必须先于 /roster/{studentId}，保持历史 FastAPI 匹配顺序。
@router.get("/roster/status-summary", summary="学籍状态总览（13 态分布 + 在籍统计 + 近30天异动数）")
def roster_status_summary(user=Depends(require_permission(_ROSTER_VIEW))):
    return success(svc.roster_status_summary(user))


@router.get("/roster/import/template", summary="学籍导入·下载 Excel 模板(.xlsx)")
def roster_import_template(user=Depends(require_permission(_ROSTER_IMPORT))):
    import io
    from fastapi.responses import StreamingResponse
    data = svc.roster_import_template_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=roster_import_template.xlsx"})


@router.post("/roster/import/dry-run", summary="学籍导入·预校验（粘贴行/高级，不写库）")
def roster_import_dry_run(body: ExcelImportRows, user=Depends(require_permission(_ROSTER_IMPORT))):
    return success(svc.roster_import_dry_run(body.rows))


@router.post("/roster/import/xlsx", summary="学籍导入·上传 Excel 解析+预校验（不写库）")
async def roster_import_xlsx(file: UploadFile = File(...), user=Depends(require_permission(_ROSTER_IMPORT))):
    content = await xlsx_util.read_safe_upload(file)
    rows = svc.roster_import_read(content)
    dry = svc.roster_import_dry_run(rows)
    return success({"rows": rows, **dry})


@router.post("/roster/import/errors-xlsx", summary="学籍导入·下载错误行 Excel")
def roster_import_errors_xlsx(body: ExcelErrorRows, user=Depends(require_permission(_ROSTER_IMPORT))):
    return success(svc.roster_import_errors_pack(body.rows, [e.model_dump() for e in body.errors]))


@router.post("/roster/import/confirm", summary="学籍导入·确认（整批事务，须预校验全通过）")
def roster_import_confirm(body: ExcelImportRows, user=Depends(require_permission(_ROSTER_IMPORT))):
    result = svc.roster_import_confirm(body.rows)
    return success(result, message="导入完成")


@router.post("/roster/corrections", summary="发起学籍信息更正（学号/姓名/性别/证件号/年级）")
def roster_correction_create(body: RosterCorrectionCreate, user=Depends(require_permission(_ROSTER_CORRECTION_APPLY))):
    return success(svc.create_roster_correction(user, body.studentId, body.fieldKey, body.newValue, body.reason,
                                                body.materialFileIds), message="更正申请已提交")


@router.get("/roster/corrections", summary="学籍信息更正列表（范围过滤+敏感字段脱敏）")
def roster_correction_list(status: Optional[str] = None, studentId: Optional[str] = None,
                           fieldKey: Optional[str] = None, page: int = 1, pageSize: int = 20,
                           user=Depends(require_any_permission(_ROSTER_CORRECTION_VIEW, _ROSTER_CORRECTION_REVIEW))):
    items, total = svc.list_roster_corrections(user, status, studentId, fieldKey, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/roster/corrections/{correctionId}/review", summary="学籍信息更正审核（通过即同步主档/驳回）")
def roster_correction_review(body: RosterCorrectionReview, correctionId: int = Path(...),
                             user=Depends(require_permission(_ROSTER_CORRECTION_REVIEW))):
    return success(svc.review_roster_correction(correctionId, user, body.action, body.note), message="已处理")


@router.get("/roster/{studentId}", summary="学籍档案详情（主档+组织名称+学籍状态历史，数据范围收敛）")
def roster_detail(studentId: int = Path(...), user=Depends(require_permission(_ROSTER_VIEW))):
    return success(svc.roster_detail(studentId, user))


@router.post("/roster/{studentId}/reveal", summary="查看完整证件号（sensitiveView+强制审计）")
def roster_reveal(body: RosterRevealBody, studentId: int = Path(...), user=Depends(require_staff)):
    # 保留历史语义：viewSensitive 真授权与 SUCCESS/DENY 双向审计必须由 service 执行。
    return success(svc.reveal_roster_sensitive(studentId, user, body.reason))


@router.post("/registration-batches", summary="新建注册批次")
def reg_batch_create(body: RegBatchCreate,
                     user=Depends(require_permission("academicAffairs.registration.manage"))):
    return success(svc.create_registration_batch(body, user), message="已创建")


@router.get("/registration-batches", summary="注册批次列表（registerType 可收窄为入学/学年注册视图）")
def reg_batches(status: Optional[str] = None, registerType: Optional[str] = None,
                page: int = 1, pageSize: int = 20,
                user=Depends(require_permission("academicAffairs.registration.view"))):
    items, total = svc.list_registration_batches(user, status, page, pageSize, registerType)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/register", summary="学生注册（经 change_student_status 单一入口）")
def register(body: RegisterBody, batchId: int = Path(...),
             user=Depends(require_permission("academicAffairs.registration.manage"))):
    # D2-U 并发收口：旧单笔 URL/DTO/权限/正式 canonical 写入口完全不变，仅在真正写入临界区
    # 与批量 confirm 共用 tenant+batch+student 的 MySQL 短锁，避免双击/多 worker 重复事实。
    with convenience.registration_mutex(batchId, body.studentId):
        return success(svc.register_student(batchId, user, body.studentId), message="注册成功")


@router.get("/registration-batches/{batchId}/registrations", summary="注册记录列表")
def registrations(batchId: int = Path(...), page: int = 1, pageSize: int = 50,
                  user=Depends(require_permission("academicAffairs.registration.view"))):
    items, total = svc.list_registrations(batchId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/close", summary="关闭注册批次（OPEN→CLOSED，仅教务处）")
def reg_batch_close(batchId: int = Path(...), user=Depends(require_permission(_REG_ARCHIVE_MANAGE))):
    return success(svc.close_registration_batch(batchId, user), message="已关闭")


@router.post("/registration-batches/{batchId}/archive", summary="归档注册批次（CLOSED→ARCHIVED，仅教务处）")
def reg_batch_archive(batchId: int = Path(...), user=Depends(require_permission(_REG_ARCHIVE_MANAGE))):
    return success(svc.archive_registration_batch(batchId, user), message="已归档")


@router.get("/registration/archive", summary="注册归档：已归档批次列表")
def reg_archive_list(page: int = 1, pageSize: int = 20,
                     user=Depends(require_permission(_REG_ARCHIVE_VIEW))):
    items, total = svc.list_archived_registration_batches(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/registration/archive/{batchId}", summary="注册归档批次详情（含注册完成统计）")
def reg_archive_detail(batchId: int = Path(...), user=Depends(require_permission(_REG_ARCHIVE_VIEW))):
    return success(svc.registration_archive_detail(batchId, user))


@router.get("/registration-batches/{batchId}/eligibility", summary="注册资格核验候选名单")
def reg_eligibility_list(batchId: int = Path(...), status: Optional[str] = None,
                         keyword: Optional[str] = None, page: int = 1, pageSize: int = 20,
                         user=Depends(require_permission(_REG_ELIGIBILITY_VIEW))):
    items, total = svc.list_registration_eligibility(batchId, user, status, keyword, page, pageSize)
    items = convenience.enrich_eligibility_class_names(items)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/eligibility/{studentId}/verify", summary="核验单个学生注册资格")
def reg_eligibility_verify(body: EligibilityVerifyBody, batchId: int = Path(...), studentId: str = Path(...),
                           user=Depends(require_permission(_REG_ELIGIBILITY_VERIFY))):
    return success(svc.verify_registration_eligibility(batchId, user, studentId, body.result, body.note,
                                                        body.exceptionType), message="已核验")


@router.get("/registration/unregistered", summary="未注册学生名单（已判定 UNREGISTERED + 逾期待扫描）")
def reg_unregistered_list(batchId: Optional[int] = None, page: int = 1, pageSize: int = 20,
                          user=Depends(require_permission(_REG_UNREG_VIEW))):
    items, total = svc.list_unregistered_students(user, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/scan-unregistered", summary="扫描批次逾期未注册（仅教务处）")
def reg_scan_unregistered(batchId: int = Path(...), user=Depends(require_permission(_REG_UNREG_SCAN))):
    return success(svc.scan_unregistered(batchId, user), message="扫描完成")


@router.post("/registration-batches/{batchId}/deferrals", summary="提交暂缓注册申请")
def reg_deferral_apply(body: DeferralApplyBody, batchId: int = Path(...),
                       user=Depends(require_permission(_REG_DEFERRAL_APPLY))):
    return success(svc.apply_registration_deferral(batchId, user, body.studentId, body.reason,
                                                    body.requestedUntil), message="已提交")


@router.get("/registration/deferrals", summary="暂缓注册申请列表")
def reg_deferral_list(batchId: Optional[int] = None, status: Optional[str] = None,
                      page: int = 1, pageSize: int = 20,
                      user=Depends(require_permission(_REG_DEFERRAL_VIEW))):
    items, total = svc.list_registration_deferrals(user, batchId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration/deferrals/{deferralId}/review", summary="审批暂缓注册申请")
def reg_deferral_review(body: DeferralReviewBody, deferralId: int = Path(...),
                        user=Depends(require_permission(_REG_DEFERRAL_APPROVE))):
    return success(svc.review_registration_deferral(deferralId, user, body.action, body.note), message="已处理")


@router.post("/registration-batches/{batchId}/exceptions", summary="标记注册异常")
def reg_exception_create(body: ExceptionCreateBody, batchId: int = Path(...),
                         user=Depends(require_permission(_REG_EXCEPTION_CREATE))):
    return success(svc.create_registration_exception(batchId, user, body.studentId, body.exceptionType,
                                                      body.description), message="已标记异常")


@router.get("/registration/exceptions", summary="注册异常列表")
def reg_exception_list(batchId: Optional[int] = None, status: Optional[str] = None,
                       page: int = 1, pageSize: int = 20,
                       user=Depends(require_permission(_REG_EXCEPTION_VIEW))):
    items, total = svc.list_registration_exceptions(user, batchId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration/exceptions/{exceptionId}/resolve", summary="处理并解除注册异常")
def reg_exception_resolve(body: ExceptionResolveBody, exceptionId: int = Path(...),
                          user=Depends(require_permission(_REG_EXCEPTION_RESOLVE))):
    return success(svc.resolve_registration_exception(exceptionId, user, body.note), message="已处理")
