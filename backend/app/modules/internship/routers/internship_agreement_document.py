"""岗位实习中心 · 三方协议文档输出。

只负责协议实例的只读文档生成；协议状态机仍由 internship.py +
internship_agreement_service 管理。PDF 使用公共 pdf_util 真实生成，权限与数据范围
复用 agreement service 的 get_agreement()，禁止通过文档端点绕过 owner/scope。
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.exceptions import AppException
from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_agreement_service as agr
from app.services import audit_log
from app.services.pdf_util import build_text_pdf, pack_pdf_result

router = APIRouter(tags=["岗位实习-协议文档"])


@router.post("/agreements/{agreement_id}/pdf", summary="三方协议 PDF 套打（真实 PDF + 下载审计）")
def agreement_pdf(
    agreement_id: str,
    user=Depends(require_permission("internship.agreement.view")),
):
    detail = agr.get_agreement(agreement_id, user=user)
    body = str(detail.get("renderedBody") or "").strip()
    if not body:
        raise AppException("DATA_CONFLICT", "协议正文快照为空，无法生成 PDF")

    student_name = str(detail.get("studentName") or "学生")
    student_no = str(detail.get("studentNo") or "")
    status_label = str(detail.get("statusLabel") or detail.get("status") or "")
    operator = str((user or {}).get("realName") or "系统")
    title = f"{student_name} · 三方实习协议"
    watermark = (
        f"岗位实习中心 · 协议#{agreement_id} · 状态：{status_label} · "
        f"套打人：{operator} · {datetime.now():%Y-%m-%d %H:%M} · 下载留痕"
    )
    content = build_text_pdf(title, body, watermark=watermark)
    filename = "_".join(part for part in ("三方实习协议", student_no, student_name) if part)
    result = pack_pdf_result(content, filename)
    audit_log.record(
        "下载三方协议PDF套打",
        f"internship-agreement:{agreement_id}",
        detail={"filename": result["filename"], "status": detail.get("status") or ""},
    )
    return success(result)
