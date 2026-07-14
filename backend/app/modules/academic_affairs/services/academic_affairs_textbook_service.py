"""13B 教材管理 service。

目录字典 → 选用(挂教学任务,DRAFT→SUBMITTED→APPROVED) → 审核批次(学院→教务备案PUBLISHED)
→ 征订批次(从APPROVED选用汇总合并明细,登记到货) → 发放批次(按班级生成名单,签收触发费用台账)
→ 费用台账(签收后应收,标记已收/减免) → 统计。

复用：AaTeachingTask(选用挂载)/StudentProfile(发放名单,只带外键不冗余隐私)/AffairsAuditTrail/
build_affairs_context(学院范围)。审计 biz_type=AA_TEXTBOOK_*。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _conflict(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _invalid(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow()))


def _ctx(user, db):
    return build_affairs_context(user, db)


def _require_school(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教材管理员/教务处可执行该操作")


def _fnum(v):
    return float(v) if v is not None else None


# ══════════ 教材目录 ══════════

def _tb_dto(t):
    return {"textbookId": str(t.id), "name": t.name, "isbn": t.isbn, "publisher": t.publisher,
            "edition": t.edition, "author": t.author, "subject": t.subject,
            "unitPrice": _fnum(t.unit_price), "isNationalStandard": t.is_national_standard, "status": t.status}


def create_textbook(user, body):
    from app.models import AaTextbook
    with session() as db:
        _require_school(_ctx(user, db))
        name = (getattr(body, "name", None) or "").strip()
        if not name:
            raise _bad("教材名称必填")
        isbn = getattr(body, "isbn", None)
        if isbn:
            dup = db.query(AaTextbook).filter(AaTextbook.tenant_id == _tid(), AaTextbook.isbn == isbn,
                                              AaTextbook.is_deleted.is_(False)).first()
            if dup:
                raise _bad("该 ISBN 教材已存在")
        t = AaTextbook(tenant_id=_tid(), name=name, isbn=isbn, publisher=getattr(body, "publisher", None),
                       edition=getattr(body, "edition", None), author=getattr(body, "author", None),
                       subject=getattr(body, "subject", None), unit_price=getattr(body, "unitPrice", None),
                       is_national_standard=bool(getattr(body, "isNationalStandard", False)), status="ENABLED")
        db.add(t); db.flush()
        _audit(db, "AA_TEXTBOOK_CATALOG", t.id, "TEXTBOOK_CREATE", name)
        db.commit()
        return _tb_dto(t)


def list_textbooks(user, keyword=None, status=None, page=1, page_size=20):
    from app.models import AaTextbook
    with session() as db:
        _ctx(user, db)
        q = db.query(AaTextbook).filter(AaTextbook.tenant_id == _tid(), AaTextbook.is_deleted.is_(False))
        if status:
            q = q.filter(AaTextbook.status == status)
        rows = q.order_by(AaTextbook.id.desc()).all()
        if keyword:
            kw = keyword.lower()
            rows = [t for t in rows if kw in (t.name or "").lower() or kw in (t.isbn or "").lower()]
        total = len(rows)
        return [_tb_dto(t) for t in rows[(page - 1) * page_size: page * page_size]], total


def update_textbook(user, tid, body):
    from app.models import AaTextbook
    with session() as db:
        _require_school(_ctx(user, db))
        t = db.query(AaTextbook).filter(AaTextbook.id == tid, AaTextbook.tenant_id == _tid()).first()
        if not t:
            raise not_found("教材不存在")
        for f, attr in (("name", "name"), ("publisher", "publisher"), ("edition", "edition"),
                        ("author", "author"), ("subject", "subject")):
            v = getattr(body, f, None)
            if v is not None:
                setattr(t, attr, v)
        if getattr(body, "unitPrice", None) is not None:
            t.unit_price = body.unitPrice
        if getattr(body, "status", None):
            t.status = body.status
        _audit(db, "AA_TEXTBOOK_CATALOG", t.id, "TEXTBOOK_UPDATE", t.name)
        db.commit()
        return _tb_dto(t)


# ══════════ 教材选用（挂教学任务） ══════════

def _sel_dto(s):
    return {"selectionId": str(s.id), "taskId": str(s.task_id), "textbookId": str(s.textbook_id),
            "textbookName": s.textbook_name, "courseName": s.course_name, "expectedQty": s.expected_qty,
            "officerKey": s.officer_key, "rejectReason": s.reject_reason, "status": s.status}


def create_selection(user, body):
    """教材负责人按教学任务申报选用。同 task 无未终结选用。"""
    from app.models import AaTextbook, AaTextbookSelection, AaTeachingTask, AaTeachingTaskBatch
    with session() as db:
        ctx = _ctx(user, db)
        task_id = int(body.taskId)
        tt = db.query(AaTeachingTask).filter(AaTeachingTask.id == task_id, AaTeachingTask.tenant_id == _tid()).first()
        if not tt:
            raise not_found("教学任务不存在")
        tb = db.query(AaTextbook).filter(AaTextbook.id == int(body.textbookId), AaTextbook.tenant_id == _tid()).first()
        if not tb:
            raise not_found("教材不存在")
        active = db.query(AaTextbookSelection).filter(
            AaTextbookSelection.tenant_id == _tid(), AaTextbookSelection.task_id == task_id,
            AaTextbookSelection.status.notin_(["RETURNED", "ORDERED"]),
            AaTextbookSelection.is_deleted.is_(False)).first()
        if active:
            raise _conflict("该教学任务已有未终结的教材选用")
        ttb = db.query(AaTeachingTaskBatch).filter(AaTeachingTaskBatch.id == tt.batch_id,
                                                   AaTeachingTaskBatch.tenant_id == _tid()).first()
        from app.core.affairs_security import _derive_keys
        keys = _derive_keys(user)
        s = AaTextbookSelection(tenant_id=_tid(), task_id=task_id, textbook_id=tb.id, textbook_name=tb.name,
                                course_name=getattr(tt, "course_name", None),
                                college_id=ttb.college_id if ttb else None,
                                officer_key=next(iter(keys), None) if keys else _op(),
                                expected_qty=getattr(body, "expectedQty", None),
                                remark=getattr(body, "remark", None), status="DRAFT")
        db.add(s); db.flush()
        _audit(db, "AA_TEXTBOOK_SELECTION", s.id, "TEXTBOOK_SELECTION_CREATE", f"选用 {tb.name}")
        db.commit()
        return _sel_dto(s)


def _get_sel(db, sid):
    from app.models import AaTextbookSelection
    s = db.query(AaTextbookSelection).filter(AaTextbookSelection.id == sid, AaTextbookSelection.tenant_id == _tid()).first()
    if not s:
        raise not_found("选用记录不存在")
    return s


def submit_selection(user, sid):
    with session() as db:
        _ctx(user, db)
        s = _get_sel(db, sid)
        if s.status not in ("DRAFT", "RETURNED"):
            raise _invalid("仅草稿/退回选用可提交")
        s.status = "SUBMITTED"
        _audit(db, "AA_TEXTBOOK_SELECTION", s.id, "TEXTBOOK_SELECTION_SUBMIT", "提交选用")
        db.commit()
        return _sel_dto(s)


def withdraw_selection(user, sid):
    with session() as db:
        _ctx(user, db)
        s = _get_sel(db, sid)
        if s.status != "DRAFT":
            raise _invalid("仅草稿可撤回")
        s.is_deleted = True
        _audit(db, "AA_TEXTBOOK_SELECTION", s.id, "TEXTBOOK_SELECTION_WITHDRAW", "撤回")
        db.commit()
        return {"selectionId": str(s.id), "withdrawn": True}


def list_selections(user, status=None, page=1, page_size=50):
    from app.models import AaTextbookSelection
    with session() as db:
        ctx = _ctx(user, db)
        q = db.query(AaTextbookSelection).filter(AaTextbookSelection.tenant_id == _tid(),
                                                 AaTextbookSelection.is_deleted.is_(False))
        if status:
            q = q.filter(AaTextbookSelection.status == status)
        rows = q.order_by(AaTextbookSelection.id.desc()).all()
        if not _is_school(ctx):
            allowed = getattr(ctx, "college_ids", None) or set()
            rows = [s for s in rows if s.college_id and int(s.college_id) in allowed]
        total = len(rows)
        return [_sel_dto(s) for s in rows[(page - 1) * page_size: page * page_size]], total


def _is_school(ctx):
    return ctx.scope_type == "TENANT_ALL"


# ══════════ 教材审核批次 ══════════

def _rb_dto(b):
    return {"reviewBatchId": str(b.id), "batchName": b.batch_name, "status": b.status,
            "rejectReason": b.reject_reason}


def create_review_batch(user, body):
    """把 SUBMITTED 选用纳入审核批次。"""
    from app.models import AaTextbookReviewBatch, AaTextbookReviewBatchItem, AaTextbookSelection
    with session() as db:
        _require_school(_ctx(user, db))
        b = AaTextbookReviewBatch(tenant_id=_tid(), batch_name=(getattr(body, "batchName", None) or "教材审核批次").strip(),
                                  term_id=int(body.termId) if getattr(body, "termId", None) else None, status="DRAFT")
        db.add(b); db.flush()
        sel_ids = [int(x) for x in (getattr(body, "selectionIds", None) or []) if str(x).isdigit()]
        for sid in sel_ids:
            s = db.query(AaTextbookSelection).filter(AaTextbookSelection.id == sid, AaTextbookSelection.tenant_id == _tid()).first()
            if s and s.status == "SUBMITTED":
                db.add(AaTextbookReviewBatchItem(tenant_id=_tid(), batch_id=b.id, selection_id=sid))
                s.status = "REVIEWING"
        _audit(db, "AA_TEXTBOOK_REVIEW", b.id, "TEXTBOOK_REVIEW_CREATE", f"纳入 {len(sel_ids)} 条选用")
        db.commit()
        return _rb_dto(b)


def _get_rb(db, bid):
    from app.models import AaTextbookReviewBatch
    b = db.query(AaTextbookReviewBatch).filter(AaTextbookReviewBatch.id == bid, AaTextbookReviewBatch.tenant_id == _tid()).first()
    if not b:
        raise not_found("审核批次不存在")
    return b


_RB_CHAIN = {"DRAFT": "COLLEGE_REVIEWING", "COLLEGE_REVIEWING": "COLLEGE_APPROVED",
             "COLLEGE_APPROVED": "ACADEMIC_APPROVED", "ACADEMIC_APPROVED": "PUBLISHED"}


def review_batch_advance(user, bid, action, reason=""):
    """审核批次推进：APPROVE 逐级(学院初审→教务终审→备案公示 PUBLISHED)；RETURN 退回选用。"""
    from app.models import AaTextbookReviewBatchItem, AaTextbookSelection
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_rb(db, bid)
        if action == "APPROVE":
            if b.status not in _RB_CHAIN:
                raise _invalid("该批次已完成审核")
            b.status = _RB_CHAIN[b.status]
            if b.status == "PUBLISHED":
                items = db.query(AaTextbookReviewBatchItem).filter(AaTextbookReviewBatchItem.batch_id == b.id,
                                                                   AaTextbookReviewBatchItem.tenant_id == _tid()).all()
                for it in items:
                    s = db.query(AaTextbookSelection).filter(AaTextbookSelection.id == it.selection_id,
                                                             AaTextbookSelection.tenant_id == _tid()).first()
                    if s:
                        s.status = "APPROVED"
        elif action == "RETURN":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _bad("退回原因必填且不少于5字")
            b.status = "RETURNED"
            b.reject_reason = reason
            items = db.query(AaTextbookReviewBatchItem).filter(AaTextbookReviewBatchItem.batch_id == b.id,
                                                               AaTextbookReviewBatchItem.tenant_id == _tid()).all()
            for it in items:
                s = db.query(AaTextbookSelection).filter(AaTextbookSelection.id == it.selection_id,
                                                         AaTextbookSelection.tenant_id == _tid()).first()
                if s:
                    s.status = "RETURNED"
                    s.reject_reason = reason
        else:
            raise _bad("非法审核动作")
        _audit(db, "AA_TEXTBOOK_REVIEW", b.id, "TEXTBOOK_REVIEW_ADVANCE", f"{action}->{b.status}")
        db.commit()
        return _rb_dto(b)


def list_review_batches(user, status=None, page=1, page_size=20):
    from app.models import AaTextbookReviewBatch
    with session() as db:
        _ctx(user, db)
        q = db.query(AaTextbookReviewBatch).filter(AaTextbookReviewBatch.tenant_id == _tid(),
                                                   AaTextbookReviewBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaTextbookReviewBatch.status == status)
        rows = q.order_by(AaTextbookReviewBatch.id.desc()).all()
        return [_rb_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


# ══════════ 教材征订 ══════════

def _ob_dto(b):
    return {"orderBatchId": str(b.id), "batchName": b.batch_name, "status": b.status}


def create_order_batch(user, body):
    """从 APPROVED 选用汇总生成征订批次（同教材合并数量）。"""
    from app.models import AaTextbook, AaTextbookOrderBatch, AaTextbookOrderItem, AaTextbookSelection
    with session() as db:
        _require_school(_ctx(user, db))
        b = AaTextbookOrderBatch(tenant_id=_tid(), batch_name=(getattr(body, "batchName", None) or "教材征订批次").strip(),
                                 term_id=int(body.termId) if getattr(body, "termId", None) else None, status="DRAFT")
        db.add(b); db.flush()
        sels = db.query(AaTextbookSelection).filter(AaTextbookSelection.tenant_id == _tid(),
                                                    AaTextbookSelection.status == "APPROVED",
                                                    AaTextbookSelection.is_deleted.is_(False)).all()
        merged = {}
        for s in sels:
            merged.setdefault(s.textbook_id, {"name": s.textbook_name, "qty": 0})
            merged[s.textbook_id]["qty"] += (s.expected_qty or 0)
            s.status = "ORDERED"
        for tbid, info in merged.items():
            tb = db.query(AaTextbook).filter(AaTextbook.id == tbid, AaTextbook.tenant_id == _tid()).first()
            db.add(AaTextbookOrderItem(tenant_id=_tid(), order_batch_id=b.id, textbook_id=tbid,
                                       textbook_name=info["name"], order_qty=info["qty"], arrived_qty=0,
                                       unit_price_snapshot=tb.unit_price if tb else None))
        _audit(db, "AA_TEXTBOOK_ORDER", b.id, "TEXTBOOK_ORDER_GENERATE", f"合并 {len(merged)} 种教材")
        db.commit()
        return {"orderBatchId": str(b.id), "itemCount": len(merged)}


def _get_ob(db, bid):
    from app.models import AaTextbookOrderBatch
    b = db.query(AaTextbookOrderBatch).filter(AaTextbookOrderBatch.id == bid, AaTextbookOrderBatch.tenant_id == _tid()).first()
    if not b:
        raise not_found("征订批次不存在")
    return b


def submit_order(user, bid):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_ob(db, bid)
        if b.status != "DRAFT":
            raise _invalid("仅 DRAFT 征订批次可提交")
        b.status = "ORDERED"
        b.submit_at = datetime.utcnow()
        _audit(db, "AA_TEXTBOOK_ORDER", b.id, "TEXTBOOK_ORDER_SUBMIT", "提交征订")
        db.commit()
        return _ob_dto(b)


def record_arrival(user, item_id, arrived_qty):
    """登记到货，批次到货状态联动（部分/全部到货）。"""
    from app.models import AaTextbookOrderItem
    with session() as db:
        _require_school(_ctx(user, db))
        it = db.query(AaTextbookOrderItem).filter(AaTextbookOrderItem.id == item_id, AaTextbookOrderItem.tenant_id == _tid()).first()
        if not it:
            raise not_found("征订明细不存在")
        b = _get_ob(db, it.order_batch_id)
        if b.status not in ("ORDERED", "PARTIALLY_ARRIVED"):
            raise _invalid("仅已征订批次可登记到货")
        it.arrived_qty = int(arrived_qty)
        items = db.query(AaTextbookOrderItem).filter(AaTextbookOrderItem.order_batch_id == b.id,
                                                     AaTextbookOrderItem.tenant_id == _tid()).all()
        all_arrived = all((x.arrived_qty or 0) >= (x.order_qty or 0) for x in items)
        any_arrived = any((x.arrived_qty or 0) > 0 for x in items)
        b.status = "ARRIVED" if all_arrived else ("PARTIALLY_ARRIVED" if any_arrived else b.status)
        _audit(db, "AA_TEXTBOOK_ORDER", b.id, "TEXTBOOK_ARRIVAL", f"到货 {arrived_qty}")
        db.commit()
        return {"itemId": str(it.id), "arrivedQty": it.arrived_qty, "batchStatus": b.status}


def list_order_batches(user, status=None, page=1, page_size=20):
    from app.models import AaTextbookOrderBatch
    with session() as db:
        _ctx(user, db)
        q = db.query(AaTextbookOrderBatch).filter(AaTextbookOrderBatch.tenant_id == _tid(),
                                                  AaTextbookOrderBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaTextbookOrderBatch.status == status)
        rows = q.order_by(AaTextbookOrderBatch.id.desc()).all()
        return [_ob_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], len(rows)


def order_items(user, bid):
    from app.models import AaTextbookOrderItem
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaTextbookOrderItem).filter(AaTextbookOrderItem.order_batch_id == bid,
                                                    AaTextbookOrderItem.tenant_id == _tid()).all()
        return [{"itemId": str(i.id), "textbookName": i.textbook_name, "orderQty": i.order_qty,
                 "arrivedQty": i.arrived_qty, "unitPrice": _fnum(i.unit_price_snapshot)} for i in rows]


def archive_order_batch(user, bid):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_ob(db, bid)
        if b.status == "ARCHIVED":
            return _ob_dto(b)
        if b.status != "ARRIVED":
            raise _invalid("仅 ARRIVED 批次可归档")
        b.status = "ARCHIVED"
        _audit(db, "AA_TEXTBOOK_ORDER", b.id, "TEXTBOOK_ORDER_ARCHIVE", "归档")
        db.commit()
        return _ob_dto(b)


# ══════════ 教材发放（签收触发费用台账） ══════════

def generate_distribution(user, order_batch_id, class_id, student_ids):
    """按班级+征订批次生成发放名单（排除非在籍）。批次须 ARRIVED/PARTIALLY_ARRIVED。"""
    from app.models import (AaTextbookDistributionBatch, AaTextbookDistributionRecord,
                            AaTextbookOrderItem, StudentProfile)
    with session() as db:
        _require_school(_ctx(user, db))
        ob = _get_ob(db, order_batch_id)
        if ob.status not in ("ARRIVED", "PARTIALLY_ARRIVED"):
            raise _invalid("对应征订批次未到货，不可发放")
        b = AaTextbookDistributionBatch(tenant_id=_tid(), order_batch_id=ob.id,
                                        class_id=int(class_id) if class_id else None, status="DISTRIBUTING",
                                        started_at=datetime.utcnow())
        db.add(b); db.flush()
        items = db.query(AaTextbookOrderItem).filter(AaTextbookOrderItem.order_batch_id == ob.id,
                                                     AaTextbookOrderItem.tenant_id == _tid()).all()
        sids = [int(x) for x in student_ids if str(x).isdigit()]
        students = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                                   StudentProfile.id.in_(sids)).all() if sids else []
        cnt = 0
        for s in students:
            enrolled = (s.student_status or "NORMAL") in ("NORMAL", "REGISTERED", "ON_CAMPUS")
            for it in items:
                db.add(AaTextbookDistributionRecord(tenant_id=_tid(), batch_id=b.id, student_id=s.id,
                                                    textbook_id=it.textbook_id, textbook_name=it.textbook_name,
                                                    qty=1, status="PENDING" if enrolled else "EXCLUDED",
                                                    exclude_reason=None if enrolled else "非在籍"))
                cnt += 1
        _audit(db, "AA_TEXTBOOK_DIST", b.id, "TEXTBOOK_DIST_GENERATE", f"{cnt} 条发放记录")
        db.commit()
        return {"distributionBatchId": str(b.id), "recordCount": cnt}


def sign_receipt(user, record_id):
    """学生签收 → RECEIVED，自动生成费用台账应收（幂等）。"""
    from app.models import (AaTextbook, AaTextbookDistributionRecord, AaTextbookFeeLedger)
    with session() as db:
        _require_school(_ctx(user, db))
        r = db.query(AaTextbookDistributionRecord).filter(AaTextbookDistributionRecord.id == record_id,
                                                          AaTextbookDistributionRecord.tenant_id == _tid()).first()
        if not r:
            raise not_found("发放记录不存在")
        if r.status == "EXCLUDED":
            raise _invalid("非在籍学生不可签收")
        if r.status == "RECEIVED":
            return {"recordId": str(r.id), "status": r.status}
        r.status = "RECEIVED"
        r.received_at = datetime.utcnow()
        r.received_by = _op()
        # 自动生成费用台账（幂等：distribution_record 唯一）
        exist = db.query(AaTextbookFeeLedger).filter(AaTextbookFeeLedger.tenant_id == _tid(),
                                                     AaTextbookFeeLedger.distribution_record_id == r.id).first()
        if not exist:
            tb = db.query(AaTextbook).filter(AaTextbook.id == r.textbook_id, AaTextbook.tenant_id == _tid()).first()
            amount = float(tb.unit_price) * (r.qty or 1) if tb and tb.unit_price else 0
            db.add(AaTextbookFeeLedger(tenant_id=_tid(), distribution_record_id=r.id, student_id=r.student_id,
                                       textbook_name=r.textbook_name, amount=amount, status="UNPAID"))
        _audit(db, "AA_TEXTBOOK_DIST", r.id, "TEXTBOOK_SIGN_RECEIPT", "签收")
        db.commit()
        return {"recordId": str(r.id), "status": r.status}


def list_distribution_records(user, batch_id, page=1, page_size=100):
    from app.models import AaTextbookDistributionRecord
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaTextbookDistributionRecord).filter(AaTextbookDistributionRecord.batch_id == batch_id,
                                                            AaTextbookDistributionRecord.tenant_id == _tid()).all()
        total = len(rows)
        return [{"recordId": str(r.id), "studentId": str(r.student_id), "textbookName": r.textbook_name,
                 "qty": r.qty, "status": r.status} for r in rows[(page - 1) * page_size: page * page_size]], total


# ══════════ 教材费用 ══════════

def list_fees(user, status=None, page=1, page_size=50):
    from app.models import AaTextbookFeeLedger
    with session() as db:
        _ctx(user, db)
        q = db.query(AaTextbookFeeLedger).filter(AaTextbookFeeLedger.tenant_id == _tid(),
                                                 AaTextbookFeeLedger.is_deleted.is_(False))
        if status:
            q = q.filter(AaTextbookFeeLedger.status == status)
        rows = q.order_by(AaTextbookFeeLedger.id.desc()).all()
        total = len(rows)
        return [{"feeId": str(f.id), "studentId": str(f.student_id), "textbookName": f.textbook_name,
                 "amount": _fnum(f.amount), "status": f.status, "waiveReason": f.waive_reason}
                for f in rows[(page - 1) * page_size: page * page_size]], total


def mark_fee(user, fee_id, action, waive_reason=""):
    """标记已收 / 减免。"""
    from app.models import AaTextbookFeeLedger
    with session() as db:
        _require_school(_ctx(user, db))
        f = db.query(AaTextbookFeeLedger).filter(AaTextbookFeeLedger.id == fee_id, AaTextbookFeeLedger.tenant_id == _tid()).first()
        if not f:
            raise not_found("费用记录不存在")
        if action == "PAID":
            f.status = "PAID"
            f.paid_at = datetime.utcnow()
        elif action == "WAIVE":
            waive_reason = (waive_reason or "").strip()
            if len(waive_reason) < 5:
                raise _bad("减免原因必填且不少于5字")
            f.status = "WAIVED"
            f.waive_reason = waive_reason
        else:
            raise _bad("非法操作")
        _audit(db, "AA_TEXTBOOK_FEE", f.id, "TEXTBOOK_FEE_MARK", action)
        db.commit()
        return {"feeId": str(f.id), "status": f.status}


# ══════════ 统计 ══════════

def stats(user):
    from app.models import (AaTextbookFeeLedger, AaTextbookOrderBatch, AaTextbookOrderItem,
                            AaTextbookSelection)
    with session() as db:
        _ctx(user, db)
        sel_total = db.query(AaTextbookSelection).filter(AaTextbookSelection.tenant_id == _tid(),
                                                         AaTextbookSelection.is_deleted.is_(False)).count()
        approved = db.query(AaTextbookSelection).filter(AaTextbookSelection.tenant_id == _tid(),
                                                        AaTextbookSelection.status.in_(["APPROVED", "ORDERED"])).count()
        order_batches = db.query(AaTextbookOrderBatch).filter(AaTextbookOrderBatch.tenant_id == _tid()).count()
        items = db.query(AaTextbookOrderItem).filter(AaTextbookOrderItem.tenant_id == _tid()).all()
        order_qty = sum(i.order_qty or 0 for i in items)
        arrived_qty = sum(i.arrived_qty or 0 for i in items)
        fees = db.query(AaTextbookFeeLedger).filter(AaTextbookFeeLedger.tenant_id == _tid()).all()
        unpaid = sum(float(f.amount or 0) for f in fees if f.status in ("UNPAID", "PARTIAL"))
        return {"selectionTotal": sel_total, "selectionApproved": approved, "orderBatchCount": order_batches,
                "orderQty": order_qty, "arrivedQty": arrived_qty,
                "arrivalRate": round(arrived_qty / order_qty, 4) if order_qty else 0,
                "unpaidAmount": round(unpaid, 2)}
