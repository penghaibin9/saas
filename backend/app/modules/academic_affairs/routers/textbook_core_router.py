"""D9-S4 教材管理公开 Router：从 legacy academic_affairs Move Only。

正式教材闭环增强入口继续由 ``textbook_closure_router`` 持有；本 Router 只迁移
legacy 的目录、选用、审核、征订、到货、发放签收、费用、库存与统计主面。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_textbook_read_service as textbook_read
from app.modules.academic_affairs.services import academic_affairs_textbook_service as textbook_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

_TB_CATALOG = "academicAffairs.textbook.catalog.manage"
_TB_SELECTION = "academicAffairs.textbook.selection.manage"
_TB_REVIEW = "academicAffairs.textbook.review.manage"
_TB_ORDER = "academicAffairs.textbook.order.manage"
_TB_DIST = "academicAffairs.textbook.distribution.manage"
_TB_FEE = "academicAffairs.textbook.fee.manage"
_TB_VIEW = "academicAffairs.textbook.view"


class TextbookBody(BaseModel):
    name: str = Field(..., min_length=1)
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    unitPrice: Optional[float] = None
    isNationalStandard: Optional[bool] = False
    status: Optional[str] = None


class SelectionBody(BaseModel):
    taskId: str = Field(..., min_length=1)
    textbookId: str = Field(..., min_length=1)
    expectedQty: Optional[int] = None
    remark: Optional[str] = None


class ReviewBatchBody(BaseModel):
    batchName: Optional[str] = None
    termId: Optional[str] = None
    selectionIds: list[str] = Field(default_factory=list)


class ReviewAdvanceBody(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN")
    reason: Optional[str] = Field("", max_length=500)


class OrderBatchBody(BaseModel):
    batchName: Optional[str] = None
    termId: Optional[str] = None


class ArrivalBody(BaseModel):
    arrivedQty: int = Field(..., ge=0)


class DistGenerateBody(BaseModel):
    orderBatchId: str = Field(..., min_length=1)
    classId: Optional[str] = None
    studentIds: list[str] = Field(default_factory=list)


class FeeMarkBody(BaseModel):
    action: str = Field(..., description="PAID/PARTIAL/WAIVE")
    amount: Optional[float] = Field(None, ge=0, description="PARTIAL 部分收款金额")
    waiveReason: Optional[str] = Field("", max_length=500)


@router.post("/textbooks", summary="新增教材目录")
def textbook_create(body: TextbookBody, user=Depends(require_permission(_TB_CATALOG))):
    return success(textbook_svc.create_textbook(user, body), message="已创建")


@router.get("/textbooks", summary="教材目录列表")
def textbooks(keyword: Optional[str] = None, status: Optional[str] = None, page: int = 1, pageSize: int = 20,
              user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_read.list_textbooks(user, keyword, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.put("/textbooks/{tid}", summary="编辑教材目录")
def textbook_update(body: TextbookBody, tid: int = Path(...), user=Depends(require_permission(_TB_CATALOG))):
    return success(textbook_svc.update_textbook(user, tid, body), message="已保存")


@router.post("/textbooks/selections", summary="按教学任务申报选用")
def selection_create(body: SelectionBody, user=Depends(require_permission(_TB_SELECTION))):
    return success(textbook_svc.create_selection(user, body), message="已创建")


@router.get("/textbooks/selections", summary="选用列表")
def selections(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
               user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_svc.list_selections(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/selections/{sid}/submit", summary="提交选用")
def selection_submit(sid: int = Path(...), user=Depends(require_permission(_TB_SELECTION))):
    return success(textbook_svc.submit_selection(user, sid), message="已提交")


@router.post("/textbooks/selections/{sid}/withdraw", summary="撤回选用（仅草稿）")
def selection_withdraw(sid: int = Path(...), user=Depends(require_permission(_TB_SELECTION))):
    return success(textbook_svc.withdraw_selection(user, sid), message="已撤回")


@router.post("/textbooks/review-batches", summary="创建教材审核批次")
def review_create(body: ReviewBatchBody, user=Depends(require_permission(_TB_REVIEW))):
    return success(textbook_svc.create_review_batch(user, body), message="已创建")


@router.get("/textbooks/review-batches", summary="审核批次列表")
def review_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                   user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_read.list_review_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/review-batches/{bid}/advance", summary="审核推进（学院→教务→备案公示）")
def review_advance(body: ReviewAdvanceBody, bid: int = Path(...), user=Depends(require_permission(_TB_REVIEW))):
    return success(textbook_svc.review_batch_advance(user, bid, body.action, body.reason), message="已处理")


@router.post("/textbooks/order-batches", summary="从已备案选用生成征订批次")
def order_create(body: OrderBatchBody, user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.create_order_batch(user, body), message="已生成")


@router.get("/textbooks/order-batches", summary="征订批次列表")
def order_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20,
                  user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_read.list_order_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/textbooks/order-batches/{bid}/items", summary="征订明细")
def order_batch_items(bid: int = Path(...), user=Depends(require_permission(_TB_VIEW))):
    return success({"items": textbook_svc.order_items(user, bid)})


@router.post("/textbooks/order-batches/{bid}/submit", summary="提交征订")
def order_submit(bid: int = Path(...), user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.submit_order(user, bid), message="已提交")


@router.post("/textbooks/order-items/{itemId}/arrival", summary="登记到货")
def order_arrival(body: ArrivalBody, itemId: int = Path(...), user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.record_arrival(user, itemId, body.arrivedQty), message="已登记")


@router.post("/textbooks/order-batches/{bid}/archive", summary="归档征订批次")
def order_archive(bid: int = Path(...), user=Depends(require_permission(_TB_ORDER))):
    return success(textbook_svc.archive_order_batch(user, bid), message="已归档")


@router.post("/textbooks/distribution-batches", summary="生成发放名单（按班级+征订批次）")
def dist_generate(body: DistGenerateBody, user=Depends(require_permission(_TB_DIST))):
    return success(textbook_svc.generate_distribution(user, int(body.orderBatchId), body.classId, body.studentIds), message="已生成")


@router.get("/textbooks/distribution-batches/{bid}/records", summary="发放明细")
def dist_records(bid: int = Path(...), page: int = 1, pageSize: int = 100, user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_read.list_distribution_records(user, bid, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/distribution-records/{rid}/sign", summary="登记签收（触发费用台账）")
def dist_sign(rid: int = Path(...), user=Depends(require_permission(_TB_DIST))):
    return success(textbook_svc.sign_receipt(user, rid), message="已签收")


@router.get("/textbooks/fee-ledger", summary="教材费用台账")
def fee_ledger(status: Optional[str] = None, page: int = 1, pageSize: int = 50,
               user=Depends(require_permission(_TB_VIEW))):
    items, total = textbook_read.list_fees(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/textbooks/fee-ledger/{fid}/mark", summary="标记已收/部分收款/减免")
def fee_mark(body: FeeMarkBody, fid: int = Path(...), user=Depends(require_permission(_TB_FEE))):
    return success(textbook_svc.mark_fee(user, fid, body.action, body.amount, body.waiveReason), message="已处理")


@router.get("/textbooks/stock", summary="教材库存（到货量-已发放签收量）")
def textbook_stock(user=Depends(require_permission(_TB_VIEW))):
    return success({"items": textbook_read.textbook_stock(user)})


@router.get("/textbooks/stats", summary="教材统计（征订/到货率/欠费）")
def textbook_stats(user=Depends(require_permission(_TB_VIEW))):
    return success(textbook_read.stats(user))
