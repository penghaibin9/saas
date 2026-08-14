"""D9-S1b 毕业/结业证书公开 Router：从 legacy academic_affairs Move Only。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


class CertGenerateBody(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=20, description="编号前缀(学校代码)")
    year: str = Field(..., min_length=4, max_length=4, description="签发年份")
    eRegPrefix: Optional[str] = Field(None, max_length=20, description="电子注册号前缀(空=不生成)")
    issueDate: Optional[str] = Field(None, description="签发日期 YYYY-MM-DD")


class CertVoidBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("/graduation-batches/{batchId}/certificates/generate",
             summary="按终审结论批量生成证书编号（毕业证/结业证，幂等跳过已有）")
def cert_generate(body: CertGenerateBody, batchId: int = Path(...),
                  user=Depends(require_permission("academicAffairs.graduationCert.manage"))):
    r = grad_svc.generate_certificates(batchId, user, body)
    return success(r, message=f"已生成 {r['created']} 张（跳过已有 {r['skipped']}）")


@router.get("/graduation-certificates", summary="证书台账")
def cert_list(status: Optional[str] = None, certType: Optional[str] = None,
              batchId: Optional[str] = None, keyword: Optional[str] = None,
              page: int = 1, pageSize: int = 50,
              user=Depends(require_permission("academicAffairs.graduationCert.view"))):
    items, total = grad_svc.list_certificates(user, status, certType, batchId, keyword, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/graduation-certificates/{certId}/issue", summary="登记发放（GENERATED→ISSUED）")
def cert_issue(certId: int = Path(...),
               user=Depends(require_permission("academicAffairs.graduationCert.manage"))):
    return success(grad_svc.issue_certificate(certId, user), message="已登记发放")


@router.post("/graduation-certificates/{certId}/void", summary="作废（原因≥5字；编号不回收）")
def cert_void(body: CertVoidBody, certId: int = Path(...),
              user=Depends(require_permission("academicAffairs.graduationCert.manage"))):
    return success(grad_svc.void_certificate(certId, user, body.reason), message="已作废")
