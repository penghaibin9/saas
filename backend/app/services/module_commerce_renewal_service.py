"""M8 renewal follow-up bridge over paid module sources and existing RenewalTask.

The current paid TenantModuleSubscriptionSource is the renewal boundary. This service
does not create sales orders, mark a renewal successful, charge money, or mutate module
entitlement. It only projects the latest paid source per module generation and, after an
explicit operator action, atomically links that source to the existing customer-success
RenewalTask authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import db_enabled, get_sessionmaker

_SOURCE_STATES = ("ACTIVE", "SCHEDULED", "CANCEL_SCHEDULED")
_TASK_OPEN_STATES = {"PENDING", "CONTACTED", "COMMITTED"}
_MODULE_LABELS = {"internship": "岗位实习中心", "graduationDesign": "毕业设计中心",
                  "studentAffairs": "学工中心", "academicAffairs": "教务中心"}


def _require_db():
    if not db_enabled(): raise AppException("SERVER_ERROR", "商业续费治理需要数据库", http_status=503)


def _id(value, field):
    try:
        if isinstance(value, bool): raise ValueError
        result = int(value)
        if result <= 0: raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", f"{field} 无效", http_status=422) from None


def _bounded_int(value, field, *, minimum, maximum):
    try:
        if isinstance(value, bool): raise ValueError
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        raise AppException("VALIDATION_ERROR", f"{field} 必须是整数", http_status=422) from None
    if not minimum <= result <= maximum:
        raise AppException("VALIDATION_ERROR", f"{field} 必须在 {minimum}~{maximum} 之间", http_status=422)
    return result


def _utc_naive(value, field):
    if isinstance(value, datetime): parsed = value
    else:
        raw = str(value or "").strip()
        if not raw: raise AppException("VALIDATION_ERROR", f"{field} 必填", http_status=422)
        try: parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc: raise AppException("VALIDATION_ERROR", f"{field} 必须是ISO日期时间", http_status=422) from exc
    if parsed.tzinfo is not None: parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _iso(value):
    if value is None: return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.isoformat(timespec="seconds").replace("+00:00", "Z")


def _actor_id(user):
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def _ranked_paid_sources(tenant_id):
    from app.models import CommercialOrderItem, PlatformOrder, TenantModuleSubscriptionSource
    return select(
        TenantModuleSubscriptionSource.id.label("source_id"),
        func.row_number().over(
            partition_by=(TenantModuleSubscriptionSource.tenant_id, TenantModuleSubscriptionSource.module_key,
                          TenantModuleSubscriptionSource.module_generation),
            order_by=(TenantModuleSubscriptionSource.ends_at.desc(), TenantModuleSubscriptionSource.id.desc()),
        ).label("source_rank"),
    ).select_from(TenantModuleSubscriptionSource).join(
        CommercialOrderItem,
        (CommercialOrderItem.id == TenantModuleSubscriptionSource.order_item_id)
        & (CommercialOrderItem.tenant_id == TenantModuleSubscriptionSource.tenant_id)
        & (CommercialOrderItem.module_key == TenantModuleSubscriptionSource.module_key)
        & (CommercialOrderItem.module_generation == TenantModuleSubscriptionSource.module_generation),
    ).join(
        PlatformOrder,
        (PlatformOrder.id == CommercialOrderItem.order_id) & (PlatformOrder.tenant_id == CommercialOrderItem.tenant_id),
    ).where(
        TenantModuleSubscriptionSource.tenant_id == int(tenant_id),
        TenantModuleSubscriptionSource.source_type == "PAID_ORDER_ITEM",
        TenantModuleSubscriptionSource.status.in_(_SOURCE_STATES),
        TenantModuleSubscriptionSource.is_deleted.is_(False), CommercialOrderItem.is_deleted.is_(False),
        PlatformOrder.is_deleted.is_(False), PlatformOrder.status == "paid",
    ).subquery()


def _task_dto(task):
    if task is None: return None
    return {"taskId": str(task.id), "status": task.status, "dueAt": _iso(task.due_at),
            "ownerName": task.owner_name or "", "note": task.note or "",
            "lastContactedAt": _iso(task.last_contacted_at), "closedAt": _iso(task.closed_at),
            "version": int(task.version or 0)}


def _block_reason(tenant, source, state, link, task):
    if str(tenant.status or "").upper() != "ACTIVE": return {"code":"TENANT_NOT_ACTIVE","message":"学校当前不可销售，不能发起新的续费办理。"}
    if str(source.status or "").upper() == "CANCEL_SCHEDULED": return {"code":"STOP_RENEW_SCHEDULED","message":"此来源已安排期末停续；如确认继续合作，请先撤销停续。"}
    if state is None: return {"code":"MODULE_STATE_MISSING","message":"模块当前代次状态缺失，续费办理已停止。"}
    if int(state.generation or 0) != int(source.module_generation): return {"code":"GENERATION_CHANGED","message":"模块已进入新的代次；此旧来源不能再作为续费边界。"}
    if str(state.data_state or "") != "AVAILABLE": return {"code":"MODULE_DATA_NOT_AVAILABLE","message":"模块数据处于冻结、保留或销毁状态，不能从旧来源直接续费。"}
    if link is not None and task is None: return {"code":"RENEWAL_LINK_BROKEN","message":"续费关联存在但客户成功任务缺失，需要先修复关联。"}
    if task is not None and str(task.status or "").upper() == "CHURNED": return {"code":"RENEWAL_MARKED_CHURNED","message":"客户成功任务已标记流失；请先核对该结论再创建续费订单。"}
    if task is not None and str(task.status or "").upper() == "RENEWED": return {"code":"RENEWAL_MARKED_RENEWED","message":"客户成功任务已标记已续费，但当前仍未出现更新的已付来源，需要先对账。"}
    return None


def _candidate_dto(tenant, source, item, order, state, link, task, *, now):
    block = _block_reason(tenant, source, state, link, task); end = source.ends_at
    return {"tenantId":str(tenant.id),"tenantName":tenant.school_name,"sourceId":str(source.id),
            "sourceStatus":source.status,"sourceRef":source.source_ref,"moduleKey":source.module_key,
            "moduleLabel":_MODULE_LABELS.get(source.module_key,source.module_key),"moduleGeneration":int(source.module_generation),
            "moduleDataState":state.data_state if state is not None else None,"sourceStartsAt":_iso(source.starts_at),
            "sourceEndsAt":_iso(source.ends_at),"daysUntilEnd":int((end-now).total_seconds()//86400),"overdue":end<now,
            "orderId":str(order.id),"orderNo":order.order_no,"previousSkuCode":item.sku_code,
            "previousSkuRevision":int(item.sku_revision),"previousCurrency":item.currency,
            "followupLinkId":str(link.id) if link is not None else None,"renewalTask":_task_dto(task),"blocker":block,
            "canCreateFollowup":block is None and link is None,
            "canStartRenewalOrder":block is None and link is not None and task is not None and str(task.status or "").upper() in _TASK_OPEN_STATES,
            "renewalOrderInput":{"orderType":"RENEW","moduleKey":source.module_key,"requestedGeneration":int(source.module_generation),
                                 "startAt":_iso(source.ends_at),"priceMustBeReconfirmed":True,"endAtMustBeExplicit":True,"paymentRecorded":False},
            "renewalTaskAuthority":"CUSTOMER_SUCCESS_RENEWAL_TASK","salesAuthority":"MODULE_ITEMIZED_ORDER",
            "automaticRenewalExecuted":False,"paymentExecuted":False,"entitlementChangeApplied":False}


def list_renewal_candidates(tenant_id, *, within_days=120, page=1, page_size=20):
    _require_db()
    from app.models import CommercialOrderItem, CommercialRenewalFollowupLink, PlatformOrder, Tenant, TenantModuleState, TenantModuleSubscriptionSource
    from app.models.customer_success import RenewalTask
    tid=_id(tenant_id,"tenantId"); horizon=_bounded_int(within_days,"withinDays",minimum=1,maximum=3650)
    page=_bounded_int(page,"page",minimum=1,maximum=10000); page_size=_bounded_int(page_size,"pageSize",minimum=1,maximum=100)
    now=datetime.utcnow().replace(microsecond=0); cutoff=now+timedelta(days=horizon); db=get_sessionmaker()()
    try:
        tenant=db.scalars(select(Tenant).where(Tenant.id==tid,Tenant.is_deleted.is_(False))).first()
        if tenant is None: raise AppException("DATA_NOT_FOUND","学校不存在",http_status=404)
        ranked=_ranked_paid_sources(tid); source_filter=(ranked.c.source_rank==1,TenantModuleSubscriptionSource.ends_at<=cutoff)
        total=int(db.scalar(select(func.count()).select_from(TenantModuleSubscriptionSource).join(ranked,ranked.c.source_id==TenantModuleSubscriptionSource.id).where(*source_filter)) or 0)
        rows=db.execute(select(TenantModuleSubscriptionSource,CommercialOrderItem,PlatformOrder,TenantModuleState,CommercialRenewalFollowupLink,RenewalTask)
            .select_from(TenantModuleSubscriptionSource).join(ranked,ranked.c.source_id==TenantModuleSubscriptionSource.id)
            .join(CommercialOrderItem,(CommercialOrderItem.id==TenantModuleSubscriptionSource.order_item_id)&(CommercialOrderItem.tenant_id==TenantModuleSubscriptionSource.tenant_id))
            .join(PlatformOrder,(PlatformOrder.id==CommercialOrderItem.order_id)&(PlatformOrder.tenant_id==CommercialOrderItem.tenant_id))
            .outerjoin(TenantModuleState,(TenantModuleState.tenant_id==TenantModuleSubscriptionSource.tenant_id)&(TenantModuleState.module_key==TenantModuleSubscriptionSource.module_key)&(TenantModuleState.is_deleted.is_(False)))
            .outerjoin(CommercialRenewalFollowupLink,(CommercialRenewalFollowupLink.tenant_id==TenantModuleSubscriptionSource.tenant_id)&(CommercialRenewalFollowupLink.source_id==TenantModuleSubscriptionSource.id)&(CommercialRenewalFollowupLink.is_deleted.is_(False)))
            .outerjoin(RenewalTask,(RenewalTask.id==CommercialRenewalFollowupLink.renewal_task_id)&(RenewalTask.tenant_id==CommercialRenewalFollowupLink.tenant_id)&(RenewalTask.is_deleted.is_(False)))
            .where(*source_filter).order_by(TenantModuleSubscriptionSource.ends_at,TenantModuleSubscriptionSource.id)
            .offset((page-1)*page_size).limit(page_size)).all()
        return {"items":[_candidate_dto(tenant,*row,now=now) for row in rows],"total":total,"page":page,"pageSize":page_size,
                "withinDays":horizon,"asOf":_iso(now),"projectionRule":"LATEST_PAID_SOURCE_PER_MODULE_GENERATION","automaticRenewalExecuted":False}
    finally: db.close()


def ensure_renewal_followup(user, tenant_id, source_id, *, due_at, owner_name="", note=""):
    _require_db()
    from app.models import CommercialOrderItem, CommercialRenewalFollowupLink, PlatformOrder, Tenant, TenantModuleState, TenantModuleSubscriptionSource
    from app.models.customer_success import RenewalTask
    from app.services import audit_log, customer_success_p1_guard_service as customer_success
    tid=_id(tenant_id,"tenantId"); sid=_id(source_id,"sourceId"); due=_utc_naive(due_at,"dueAt")
    note_text=str(note or "").strip(); owner_text=str(owner_name or "").strip()
    if not 5<=len(note_text)<=900: raise AppException("VALIDATION_ERROR","续费跟进说明长度必须为5~900字符",http_status=422)
    if len(owner_text)>100: raise AppException("VALIDATION_ERROR","跟进负责人最多100字符",http_status=422)
    db=get_sessionmaker()()
    try:
        tenant=db.scalars(select(Tenant).where(Tenant.id==tid,Tenant.is_deleted.is_(False)).with_for_update()).first()
        if tenant is None: raise AppException("DATA_NOT_FOUND","学校不存在",http_status=404)
        source=db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.id==sid,TenantModuleSubscriptionSource.tenant_id==tid,TenantModuleSubscriptionSource.is_deleted.is_(False)).with_for_update()).first()
        if source is None: raise AppException("DATA_NOT_FOUND","订阅来源不存在或不属于该学校",http_status=404)
        existing=db.scalars(select(CommercialRenewalFollowupLink).where(CommercialRenewalFollowupLink.tenant_id==tid,CommercialRenewalFollowupLink.source_id==sid,CommercialRenewalFollowupLink.is_deleted.is_(False)).with_for_update()).first()
        if existing is not None:
            task=db.get(RenewalTask,int(existing.renewal_task_id))
            if task is None or task.is_deleted or int(task.tenant_id)!=tid: raise AppException("DATA_CONFLICT","续费来源已有关联但客户成功任务缺失，请先修复关联",http_status=409)
            return {"tenantId":str(tid),"sourceId":str(sid),"followupLinkId":str(existing.id),"renewalTask":_task_dto(task),"replayed":True,
                    "automaticRenewalExecuted":False,"paymentExecuted":False,"entitlementChangeApplied":False}
        if str(tenant.status or "").upper()!="ACTIVE": raise AppException("DATA_CONFLICT","学校当前不可销售，不能创建续费跟进",http_status=409)
        if source.source_type!="PAID_ORDER_ITEM" or source.order_item_id is None: raise AppException("DATA_CONFLICT","此来源不是已付分项合同来源，不能作为续费边界",http_status=409)
        if str(source.status or "").upper()=="CANCEL_SCHEDULED": raise AppException("DATA_CONFLICT","此来源已安排期末停续；请先撤销停续再发起续费",http_status=409)
        if str(source.status or "").upper() not in {"ACTIVE","SCHEDULED"}: raise AppException("DATA_CONFLICT","此来源当前不可续费",http_status=409)
        state=db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key==source.module_key,TenantModuleState.is_deleted.is_(False)).with_for_update()).first()
        if state is None or int(state.generation or 0)!=int(source.module_generation): raise AppException("DATA_CONFLICT","模块代次已变化，此来源不能再作为续费边界",http_status=409)
        if str(state.data_state or "")!="AVAILABLE": raise AppException("DATA_CONFLICT","模块数据状态当前不可续费",http_status=409)
        ownership=db.execute(select(CommercialOrderItem,PlatformOrder).join(PlatformOrder,(PlatformOrder.id==CommercialOrderItem.order_id)&(PlatformOrder.tenant_id==CommercialOrderItem.tenant_id)).where(
            CommercialOrderItem.id==int(source.order_item_id),CommercialOrderItem.tenant_id==tid,CommercialOrderItem.module_key==source.module_key,
            CommercialOrderItem.module_generation==source.module_generation,CommercialOrderItem.is_deleted.is_(False),PlatformOrder.is_deleted.is_(False),PlatformOrder.status=="paid")).first()
        if ownership is None: raise AppException("DATA_CONFLICT","续费来源没有可核验的已支付订单分项",http_status=409)
        latest_id=db.scalar(select(TenantModuleSubscriptionSource.id).join(CommercialOrderItem,(CommercialOrderItem.id==TenantModuleSubscriptionSource.order_item_id)&(CommercialOrderItem.tenant_id==TenantModuleSubscriptionSource.tenant_id)&(CommercialOrderItem.module_key==TenantModuleSubscriptionSource.module_key)&(CommercialOrderItem.module_generation==TenantModuleSubscriptionSource.module_generation)).join(PlatformOrder,(PlatformOrder.id==CommercialOrderItem.order_id)&(PlatformOrder.tenant_id==CommercialOrderItem.tenant_id)).where(
            TenantModuleSubscriptionSource.tenant_id==tid,TenantModuleSubscriptionSource.module_key==source.module_key,TenantModuleSubscriptionSource.module_generation==source.module_generation,
            TenantModuleSubscriptionSource.source_type=="PAID_ORDER_ITEM",TenantModuleSubscriptionSource.status.in_(_SOURCE_STATES),TenantModuleSubscriptionSource.is_deleted.is_(False),
            CommercialOrderItem.is_deleted.is_(False),PlatformOrder.is_deleted.is_(False),PlatformOrder.status=="paid").order_by(TenantModuleSubscriptionSource.ends_at.desc(),TenantModuleSubscriptionSource.id.desc()).limit(1))
        if int(latest_id or 0)!=sid: raise AppException("DATA_CONFLICT","此来源已不是当前代次最晚的已付服务边界，请刷新候选",http_status=409)
        task_note=(f"[商业续费来源#{sid} {source.module_key} generation {source.module_generation} 截止{_iso(source.ends_at)}] {note_text}")[:1000]
        task=customer_success.create_renewal_task_in_session(db,tenant_id=tid,due_at=due,owner_name=owner_text,note=task_note,user=user)
        link=CommercialRenewalFollowupLink(tenant_id=tid,source_id=sid,renewal_task_id=int(task.id),module_key=source.module_key,module_generation=int(source.module_generation),
            source_ends_at_snapshot=source.ends_at,source_status_snapshot=source.status,linked_at=datetime.utcnow().replace(microsecond=0),linked_by=_actor_id(user))
        db.add(link); db.flush()
        audit_log.record_critical_in_session(db,"COMMERCIAL_RENEWAL_FOLLOWUP_LINK",f"commercial-renewal-followup:{link.id}",
            detail={"tenantId":str(tid),"sourceId":str(sid),"renewalTaskId":str(task.id),"moduleKey":source.module_key,"moduleGeneration":int(source.module_generation),
                    "sourceEndsAt":_iso(source.ends_at),"automaticRenewalExecuted":False,"paymentExecuted":False,"entitlementChangeApplied":False},
            tenant_id=tid,resource_id=str(link.id))
        db.commit(); db.refresh(link); db.refresh(task)
        return {"tenantId":str(tid),"sourceId":str(sid),"followupLinkId":str(link.id),"renewalTask":_task_dto(task),
                "renewalOrderInput":{"orderType":"RENEW","moduleKey":source.module_key,"requestedGeneration":int(source.module_generation),"startAt":_iso(source.ends_at),"priceMustBeReconfirmed":True,"endAtMustBeExplicit":True},
                "replayed":False,"automaticRenewalExecuted":False,"paymentExecuted":False,"entitlementChangeApplied":False}
    except Exception:
        db.rollback(); raise
    finally: db.close()
