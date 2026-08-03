"""岗位实习中心 · 岗位库 API（/api/v1/internship/positions/*）。

独立 router 文件，与实习域/批次 API 隔离；在 router.py 汇总处单独 include。
写操作落审计。静态子路由（stats/import/export）声明在 /{position_id} 之前。

权限（P3）：查询 internship.position.view（指导教师只读）；建档/编辑/导入/风险标记
=internship.position.manage；上下架状态机=internship.position.publish；导出=internship.position.export。
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services.internship_import_upload import read_safe_xlsx_upload
from app.modules.internship.schemas.internship_position import (PositionCreate, PositionImport, PositionImportErrors,
                                             PositionRiskRequest, PositionStatusAction, PositionUpdate)
from app.services import audit_log
from app.modules.internship.services import internship_position_service as pos
from app.services import xlsx_util

_POS_XLSX_HEADERS = [
    "模板版本", "实习批次编号", "岗位名称", "企业信用代码/企业名称", "工作内容", "工作地址",
    "每日工时", "每周工时", "班次", "是否夜班", "是否允许加班", "每周休息天数",
    "报酬类型", "报酬金额", "发放周期", "是否住宿", "是否供餐", "是否危险岗位",
    "特殊设备", "禁止安排原因", "容量", "专业要求", "年级要求", "企业导师", "备注"]
_POS_XLSX_MAP = dict(zip(_POS_XLSX_HEADERS, [
    "templateVersion", "batchNo", "title", "company", "workContent", "workAddress",
    "dailyHours", "weeklyHours", "shiftType", "nightShift", "overtimeAllowed",
    "restDaysPerWeek", "remunerationType", "remunerationAmount", "remunerationCycle",
    "accommodationProvided", "mealProvided", "hazardousFlag", "specialEquipment",
    "prohibitedReason", "headcount", "major", "grade", "mentor", "remark"]))


def _pos_row_values(r: dict) -> list:
    return [r.get(key, "") for key in _POS_XLSX_MAP.values()]

router = APIRouter(prefix="/internship", tags=["岗位实习-岗位库"])

_P_VIEW = "internship.position.view"
_P_MANAGE = "internship.position.manage"
_P_PUBLISH = "internship.position.publish"
_P_EXPORT = "internship.position.export"


@router.get("/positions", summary="岗位库列表（分页+筛选，含按批次）")
def positions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              companyId: Optional[str] = None, batchId: Optional[str] = None,
              risk: Optional[bool] = None, user=Depends(require_permission(_P_VIEW))):
    items, total = pos.list_positions(page, pageSize, keyword=keyword, status=status,
                                      company_id=companyId, batch_id=batchId, risk=risk)
    return success(paginate(items, total, page, pageSize))


@router.get("/positions/stats", summary="岗位库统计（按状态/风险/容量）")
def position_stats(user=Depends(require_permission(_P_VIEW))):
    return success(pos.position_stats())


@router.post("/positions/import/dry-run", summary="岗位导入·预校验（高级粘贴/Excel 共用，不写库）")
def position_import_dry_run(body: PositionImport, user=Depends(require_permission(_P_MANAGE))):
    return success(pos.import_dry_run(body.rows, body.templateVersion))


@router.get("/positions/import/template", summary="岗位库导入·下载 Excel 模板(.xlsx)")
def position_import_template(user=Depends(require_permission(_P_MANAGE))):
    data = xlsx_util.build_template_xlsx(
        _POS_XLSX_HEADERS,
        required=["模板版本", "实习批次编号", "岗位名称", "企业信用代码/企业名称",
                  "工作内容", "每日工时", "每周工时", "是否夜班", "是否允许加班",
                  "每周休息天数", "报酬类型", "是否住宿", "是否供餐", "是否危险岗位", "容量"],
        samples=[
            ["POSITION_IMPORT_V2", "2026-SPRING", "前端开发实习生", "华信智能科技有限公司",
             "参与前端功能开发与测试", "上海浦东", "8", "40", "DAY", "否", "否", "2",
             "MONTHLY", "3500", "MONTHLY", "否", "是", "否", "", "", "3",
             "软件技术", "2024级", "李导师", ""],
        ],
        notes=[
            "1. 模板版本固定 POSITION_IMPORT_V2；旧模板不会被静默导入。",
            "2. 黑名单/停用企业不能导入岗位；容量须为正整数。",
            "3. 导入后岗位默认为草稿态，须走审核上架流程。",
        ])
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=position_import_template.xlsx"})


@router.post("/positions/import/xlsx", summary="岗位库导入·上传 Excel 解析+预校验")
async def position_import_xlsx(file: UploadFile = File(...), user=Depends(require_permission(_P_MANAGE))):
    content = await read_safe_xlsx_upload(file)
    rows = xlsx_util.read_xlsx(content, _POS_XLSX_MAP)
    dry = pos.import_dry_run(rows, "POSITION_IMPORT_V2")
    return success({"templateVersion": "POSITION_IMPORT_V2", "rows": rows, **dry})


@router.post("/positions/import/errors-xlsx", summary="岗位库导入·下载错误行 Excel")
def position_import_errors_xlsx(body: PositionImportErrors, user=Depends(require_permission(_P_MANAGE))):
    content = xlsx_util.build_error_rows_xlsx(
        _POS_XLSX_HEADERS, body.rows, body.errors, _pos_row_values)
    packed = xlsx_util.pack_xlsx_result(content, "岗位导入错误行.xlsx", len(body.errors))
    return success(packed)


@router.post("/positions/import/confirm", summary="岗位导入·确认（整批事务，预校验须全通过）")
def position_import_confirm(body: PositionImport, user=Depends(require_permission(_P_MANAGE))):
    result = pos.import_confirm(body.rows, body.templateVersion)
    audit_log.record("导入岗位库", "internship-position:import", detail=result)
    return success(result, message="导入完成")


@router.post("/positions/export", summary="岗位库导出 Excel 台账（写审计）")
def position_export(keyword: Optional[str] = None, status: Optional[str] = None,
                    companyId: Optional[str] = None, batchId: Optional[str] = None,
                    user=Depends(require_permission(_P_EXPORT))):
    data = pos.export_positions(keyword=keyword, status=status, company_id=companyId,
                                batch_id=batchId)
    audit_log.record("导出岗位库", "internship-position:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/positions", summary="新增岗位（草稿；必须关联企业）")
def create_position(body: PositionCreate, user=Depends(require_permission(_P_MANAGE))):
    result = pos.create_position(body)
    audit_log.record("新增岗位", f"internship-position:{result['id']}", detail={"title": result["title"]})
    return success(result, message="已创建")


@router.get("/positions/{position_id}", summary="岗位详情（含企业合作状态/导师/审计）")
def position_detail(position_id: str, user=Depends(require_permission(_P_VIEW))):
    return success(pos.get_position(position_id))


@router.put("/positions/{position_id}", summary="编辑岗位（已归档不可编辑）")
def update_position(position_id: str, body: PositionUpdate, user=Depends(require_permission(_P_MANAGE))):
    result = pos.update_position(position_id, body)
    audit_log.record("编辑岗位", f"internship-position:{position_id}")
    return success(result, message="已保存")


@router.post("/positions/{position_id}/status",
             summary="岗位状态机（提交/上架/下架/暂停/归档；黑名单·停用企业不能上架）")
def position_status(position_id: str, body: PositionStatusAction, user=Depends(require_permission(_P_PUBLISH))):
    result = pos.set_status(position_id, body.action, body.reason or "")
    audit_log.record("岗位状态变更", f"internship-position:{position_id}", detail={"action": body.action})
    return success(result, message="已更新")


@router.post("/positions/{position_id}/risk", summary="风险岗位标记/解除（标记须说明）")
def position_risk(position_id: str, body: PositionRiskRequest, user=Depends(require_permission(_P_MANAGE))):
    result = pos.mark_risk(position_id, body.on, body.note or "")
    audit_log.record("岗位风险标记", f"internship-position:{position_id}", detail={"on": body.on})
    return success(result, message="已更新")
