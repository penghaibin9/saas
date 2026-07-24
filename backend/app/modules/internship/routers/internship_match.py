"""岗位实习中心 · 岗位匹配 API（/api/v1/internship/match/*）。

静态子路由在 /{match_id} 之前。写操作落审计。

权限（P3）：意向查看 internship.match.intention.view（含指导教师）；意向 PC 端管理
internship.match.intention.manage；匹配实行(跑匹配/手动/确认/驳回) internship.match.manual、
批量 internship.match.batch；结果台账 internship.match.result.view、冲突 internship.match.conflict.view；
导出 internship.match.export。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.schemas.internship_match import (BatchMatchBody, IntentionCreate, IntentionImport,
                                          IntentionImportErrors, IntentionUpdate, ManualMatchBody,
                                          MatchActionBody)
from app.services import audit_log
from app.modules.internship.services import internship_match_service as svc
from app.services import xlsx_util

router = APIRouter(prefix="/internship/match", tags=["岗位实习-岗位匹配"])

_INT_HEADERS = ["学号", "意向城市", "意向行业", "意向企业", "备注"]
_INT_MAP = {"学号": "studentNo", "意向城市": "city", "意向行业": "industry",
            "意向企业": "company", "备注": "note"}

_P_INT_VIEW = "internship.match.intention.view"
_P_INT_MANAGE = "internship.match.intention.manage"
_P_MANUAL = "internship.match.manual"
_P_BATCH = "internship.match.batch"
_P_RESULT = "internship.match.result.view"
_P_CONFLICT = "internship.match.conflict.view"
_P_EXPORT = "internship.match.export"


def _int_row_values(r: dict) -> list:
    return [r.get("studentNo", ""), r.get("city", ""), r.get("industry", ""),
            r.get("company", ""), r.get("note", "")]


# ── 意向 ──

@router.get("/intentions", summary="学生意向列表")
def intentions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               keyword: Optional[str] = None, status: Optional[str] = None,
               batchId: Optional[str] = None, user=Depends(require_permission(_P_INT_VIEW))):
    items, total = svc.list_intentions(page, pageSize, keyword=keyword, status=status, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/intentions", summary="新建学生意向（草稿）")
def create_intention(body: IntentionCreate, user=Depends(require_permission(_P_INT_MANAGE))):
    result = svc.create_intention(body, user=user)
    audit_log.record("新建实习意向", f"internship-match:intention:{result['id']}")
    return success(result, message="已创建")


@router.get("/intentions/import/template", summary="意向导入·下载 Excel 模板")
def intention_template(user=Depends(require_permission(_P_INT_MANAGE))):
    data = xlsx_util.build_template_xlsx(
        _INT_HEADERS, required=["学号"],
        samples=[["20240101", "上海", "互联网", "华信智能科技有限公司", "优先浦东"]],
        notes=["1. 学号须已有学生主档与实习学生记录。", "2. 意向企业填企业全称（企业库中可匹配）。",
               "3. 导入后意向直接为已提交。"])
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=intention_import_template.xlsx"})


@router.post("/intentions/import/xlsx", summary="意向导入·上传 Excel 预校验")
async def intention_import_xlsx(file: UploadFile = File(...), batchId: Optional[str] = None,
                                user=Depends(require_permission(_P_INT_MANAGE))):
    content = await file.read()
    rows = xlsx_util.read_xlsx(content, _INT_MAP)
    dry = svc.intention_import_dry_run(rows, batch_id=batchId)
    return success({"rows": rows, **dry})


@router.post("/intentions/import/dry-run", summary="意向导入·预校验")
def intention_dry_run(body: IntentionImport, user=Depends(require_permission(_P_INT_MANAGE))):
    return success(svc.intention_import_dry_run(body.rows, batch_id=body.batchId))


@router.post("/intentions/import/confirm", summary="意向导入·确认")
def intention_confirm(body: IntentionImport, user=Depends(require_permission(_P_INT_MANAGE))):
    result = svc.intention_import_confirm(body.rows, user=user, batch_id=body.batchId)
    audit_log.record("导入实习意向", "internship-match:intention:import",
                     detail={**result, "batchId": body.batchId})
    return success(result, message="导入完成")


@router.post("/intentions/import/errors-xlsx", summary="意向导入·错误行 Excel")
def intention_errors_xlsx(body: IntentionImportErrors, user=Depends(require_permission(_P_INT_MANAGE))):
    content = xlsx_util.build_error_rows_xlsx(_INT_HEADERS, body.rows, body.errors, _int_row_values)
    return success(xlsx_util.pack_xlsx_result(content, "意向导入错误行.xlsx", len(body.errors)))


@router.post("/intentions/export", summary="导出意向 Excel 台账")
def intention_export(keyword: Optional[str] = None, status: Optional[str] = None,
                     batchId: Optional[str] = None, user=Depends(require_permission(_P_EXPORT))):
    data = svc.export_intentions(keyword=keyword, status=status, batch_id=batchId)
    audit_log.record("导出实习意向", "internship-match:intention:export",
                     detail={"rowCount": data["rowCount"]})
    return success(data)


@router.put("/intentions/{intention_id}", summary="编辑学生意向")
def update_intention(intention_id: str, body: IntentionUpdate, user=Depends(require_permission(_P_INT_MANAGE))):
    result = svc.update_intention(intention_id, body, user=user)
    audit_log.record("编辑实习意向", f"internship-match:intention:{intention_id}")
    return success(result, message="已保存")


@router.post("/intentions/{intention_id}/submit", summary="提交意向")
def submit_intention(intention_id: str, user=Depends(require_permission(_P_INT_MANAGE))):
    result = svc.submit_intention(intention_id, user=user)
    audit_log.record("提交实习意向", f"internship-match:intention:{intention_id}")
    return success(result, message="已提交")


@router.post("/intentions/{intention_id}/withdraw", summary="撤回意向")
def withdraw_intention(intention_id: str, user=Depends(require_permission(_P_INT_MANAGE))):
    result = svc.withdraw_intention(intention_id, user=user)
    audit_log.record("撤回实习意向", f"internship-match:intention:{intention_id}")
    return success(result, message="已撤回")


# ── 匹配运行 / 台账 ──

@router.post("/run/major", summary="跑专业匹配（规则推荐）")
def run_major(batchId: Optional[str] = None, user=Depends(require_permission(_P_MANUAL))):
    result = svc.run_major_match(batch_id=batchId, user=user)
    audit_log.record("跑专业匹配", "internship-match:run:major", detail=result)
    return success(result, message=f"已生成/更新 {result['created']} 条")


@router.post("/run/enterprise", summary="跑企业匹配（按意向企业）")
def run_enterprise(batchId: Optional[str] = None, user=Depends(require_permission(_P_MANUAL))):
    result = svc.run_enterprise_match(batch_id=batchId, user=user)
    audit_log.record("跑企业匹配", "internship-match:run:enterprise", detail=result)
    return success(result, message=f"已生成/更新 {result['created']} 条")


@router.post("/manual", summary="手动匹配")
def manual(body: ManualMatchBody, user=Depends(require_permission(_P_MANUAL))):
    result = svc.manual_match(body.recordId, body.positionId, body.remark or "", user=user)
    audit_log.record("手动匹配", f"internship-match:{result['id']}")
    return success(result, message="已创建待确认匹配")


@router.post("/batch", summary="批量匹配")
def batch(body: BatchMatchBody, user=Depends(require_permission(_P_BATCH))):
    result = svc.batch_match(body.pairs, user=user)
    audit_log.record("批量匹配", "internship-match:batch", detail=result)
    return success(result)


@router.get("/results", summary="匹配结果台账")
def results(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            matchType: Optional[str] = None, batchId: Optional[str] = None,
            user=Depends(require_permission(_P_RESULT))):
    items, total = svc.list_matches(page, pageSize, keyword=keyword, status=status,
                                    match_type=matchType, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/conflicts", summary="匹配冲突列表")
def conflicts(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, batchId: Optional[str] = None,
              user=Depends(require_permission(_P_CONFLICT))):
    items, total = svc.list_conflicts(page, pageSize, keyword=keyword, batch_id=batchId, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats", summary="匹配统计")
def stats(batchId: Optional[str] = None, user=Depends(require_permission(_P_RESULT))):
    return success(svc.match_stats(batch_id=batchId))


@router.post("/export", summary="导出匹配 Excel 台账")
def export_matches(keyword: Optional[str] = None, status: Optional[str] = None,
                   matchType: Optional[str] = None, batchId: Optional[str] = None,
                   user=Depends(require_permission(_P_EXPORT))):
    data = svc.export_matches(keyword=keyword, status=status, match_type=matchType, batch_id=batchId)
    audit_log.record("导出岗位匹配", "internship-match:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/{match_id}/confirm", summary="确认匹配并落岗（复用 assign）")
def confirm(match_id: str, user=Depends(require_permission(_P_MANUAL))):
    result = svc.confirm_match(match_id, user=user)
    audit_log.record("确认岗位匹配", f"internship-match:{match_id}")
    return success(result, message="已确认并分配岗位")


@router.post("/{match_id}/reject", summary="驳回匹配")
def reject(match_id: str, body: MatchActionBody | None = None, user=Depends(require_permission(_P_MANUAL))):
    result = svc.reject_match(match_id, (body.reason if body else "") or "", user=user)
    audit_log.record("驳回岗位匹配", f"internship-match:{match_id}")
    return success(result, message="已驳回")
