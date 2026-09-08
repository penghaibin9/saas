from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from app.core.exceptions import AppException

BASE = 1000000000000015000
MODULE_FEATURE = {"internship": "internship", "graduationDesign": "graduation"}


def _seed_tenant(tid: int):
    from app.db.session import get_sessionmaker
    from app.models import PlatformConfig, Tenant
    db=get_sessionmaker()()
    try:
        db.add(Tenant(id=tid,tenant_code=f"m345-{tid}",school_name=f"M345-{tid}",deploy_mode="SAAS",db_mode="SHARED",status="ACTIVE"))
        db.add(PlatformConfig(tenant_id=tid,config_type="TENANT_META",config_key="-",config_json={"status":"trial","packageCode":"trial","environment":"test"},enabled=True,status="ACTIVE")); db.commit()
    finally: db.close()


def _sku(module: str, code: str):
    from app.services import commercial_catalog_service as catalog
    payload={"skuCode":code,"revision":1,"name":f"{module} M345","productType":"MODULE","moduleKey":module,
        "features":{MODULE_FEATURE[module]:True,"studentProfile":True,"fileUpload":True},
        "quotas":{"students":{"limit":3000,"unit":"COUNT","aggregation":"MAX"},"storageBytes":{"limit":104857600,"unit":"BYTES","aggregation":"MAX"}},
        "pricePolicy":{"unitPrice":"100.00","currency":"CNY","taxTreatment":"UNSPECIFIED"},"lifecyclePolicyVersion":"M345-TEST-1"}
    published=catalog.publish_sku(payload,reason="M345测试发布商品"); return catalog.get_sku_snapshot(published["skuCode"],published["revision"])


def _pay(tid: int, snapshots, key: str):
    from app.services import commercial_order_item_service as orders, platform_service
    start=datetime.now(timezone.utc)-timedelta(minutes=1); end=start+timedelta(days=30); items=[]
    for line,snapshot in enumerate(snapshots,1):
        sku=snapshot.as_dict(); items.append({"lineNo":line,"skuCode":sku["skuCode"],"skuRevision":sku["revision"],"skuContentHash":snapshot.content_hash,"quantity":1,"unitPrice":"100.00","discountAmount":"0.00","netAmount":"100.00","startAt":start.isoformat(),"endAt":end.isoformat(),"requestedGeneration":1})
    created=orders.create_itemized_order({"tenantId":str(tid),"currency":"CNY","totalAmount":f"{100*len(items):.2f}","items":items,"orderType":"NEW","remark":"M345完整链路测试"},idempotency_key=key,actor_id="0")
    paid=platform_service.order_action(created["orderNo"],"mark-paid",expected_version=created["version"],reason="M345真实支付授权验收"); assert paid["repairTaskRequired"] is False; return created,paid


def _source(tid: int,module: str):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleSubscriptionSource
    db=get_sessionmaker()()
    try: return db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.tenant_id==tid,TenantModuleSubscriptionSource.module_key==module,TenantModuleSubscriptionSource.is_deleted.is_(False)).order_by(TenantModuleSubscriptionSource.id.desc())).first()
    finally: db.close()


def _cancel_source_now(tid:int,module:str):
    from app.services import module_subscription_service as subs
    row=_source(tid,module); return subs.cancel_subscription_source_now(tid,int(row.id),expected_version=int(row.version or 0),reason=f"M345结束{module}有效来源")


def test_m3_portfolio_and_cancel_schedule_do_not_cut_paid_access(db_mode):
    from app.services import commercial_entitlement_authority_service as authority
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid=BASE+1; _seed_tenant(tid); _pay(tid,[_sku("internship","M345-PORT-I"),_sku("graduationDesign","M345-PORT-G")],"m345-port")
    assert set(authority.commercial_state(tid)["moduleEntitlements"])=={"internship","graduationDesign"}
    src=_source(tid,"internship"); planned=lifecycle.schedule_source_cancellation({"userId":"0"},tid,int(src.id),expected_version=int(src.version or 0),reason="本期结束后停止实习续费")
    assert planned["status"]=="CANCEL_SCHEDULED" and authority.commercial_state(tid)["features"]["internship"] is True
    portfolio=lifecycle.tenant_module_portfolio(tid); internship=next(r for r in portfolio["modules"] if r["moduleKey"]=="internship"); graduation=next(r for r in portfolio["modules"] if r["moduleKey"]=="graduationDesign")
    assert internship["entitled"] is True and internship["sources"][0]["status"]=="CANCEL_SCHEDULED" and internship["quotas"]["students"]["limit"]==3000 and graduation["entitled"] is True and portfolio["physicalBytesMayBeShared"] is True
    resumed=lifecycle.resume_source_renewal({"userId":"0"},tid,int(src.id),expected_plan_version=int(planned["version"]),reason="学校确认继续续费实习模块")
    assert resumed["status"]=="ACTIVE" and authority.commercial_state(tid)["features"]["internship"] is True


def test_m3_delivery_acceptance_is_generation_and_source_bound(db_mode):
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid=BASE+2; _seed_tenant(tid); _pay(tid,[_sku("internship","M345-ACCEPT-I")],"m345-accept")
    row=lifecycle.accept_module_delivery({"userId":"0"},tid,"internship",acceptance_ref="SCHOOL-ACC-001",reason="学校确认岗位实习模块交付通过",expected_generation=1)
    assert row["moduleKey"]=="internship" and row["moduleGeneration"]==1 and len(row["sourceDigest"])==64
    assert lifecycle.accept_module_delivery({"userId":"0"},tid,"internship",acceptance_ref="SCHOOL-ACC-001",reason="学校确认岗位实习模块交付通过",expected_generation=1)["replayed"] is True
    with pytest.raises(AppException) as caught: lifecycle.accept_module_delivery({"userId":"0"},tid,"internship",acceptance_ref="SCHOOL-ACC-002",reason="错误代次不得形成验收",expected_generation=2)
    assert caught.value.http_status==409


def test_m4_module_freeze_never_freezes_tenant_or_sibling_and_is_reversible(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Tenant,TenantModuleState,TenantModuleSubscriptionSource
    from app.services import commercial_entitlement_authority_service as authority,module_access_service,module_commerce_lifecycle_service as lifecycle
    tid=BASE+3; _seed_tenant(tid); _pay(tid,[_sku("internship","M345-FREEZE-I"),_sku("graduationDesign","M345-FREEZE-G")],"m345-freeze"); _cancel_source_now(tid,"internship")
    db=get_sessionmaker()()
    try: lifecycle_version=int(db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="internship")).one().lifecycle_version)
    finally: db.close()
    preview=lifecycle.preview_module_offboarding(tid,"internship"); assert preview["canRequest"] is True
    job=lifecycle.request_module_offboarding({"userId":"0"},tid,"internship",expected_lifecycle_version=lifecycle_version,reason="学校合同终止后办理岗位实习模块退出",retention_days=30,retention_policy_version="POLICY-2026-09")
    assert job["state"]=="FROZEN" and job["physicalPurgeAuthorized"] is False
    db=get_sessionmaker()()
    try:
        assert db.get(Tenant,tid).status=="ACTIVE"
        istate=db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="internship")).one(); gstate=db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="graduationDesign")).one()
        assert istate.data_state=="FROZEN" and gstate.data_state=="AVAILABLE"
        source=db.scalars(select(TenantModuleSubscriptionSource).where(TenantModuleSubscriptionSource.tenant_id==tid,TenantModuleSubscriptionSource.module_key=="internship")).one(); source.status="ACTIVE"; source.cancelled_at=None; db.commit()
    finally: db.close()
    assert authority.commercial_state(tid)["features"]["internship"] is True
    with pytest.raises(AppException) as denied: module_access_service.assert_module_access(tid,"internship",write=True,expected_generation=1)
    assert denied.value.http_status==403 and module_access_service.assert_module_access(tid,"graduationDesign",write=True)["writable"] is True
    _cancel_source_now(tid,"internship"); cancelled=lifecycle.cancel_module_offboarding({"userId":"0"},int(job["jobId"]),expected_version=int(job["version"]),reason="保留期前学校撤回模块退出")
    assert cancelled["state"]=="CANCELLED"
    db=get_sessionmaker()()
    try: assert db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="internship")).one().data_state=="AVAILABLE"
    finally: db.close()
    assert authority.commercial_state(tid)["features"]["internship"] is False


def test_m4_active_source_blocks_module_freeze(db_mode):
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid=BASE+4; _seed_tenant(tid); _pay(tid,[_sku("internship","M345-BLOCK-I")],"m345-block"); preview=lifecycle.preview_module_offboarding(tid,"internship")
    assert preview["canRequest"] is False and {r["code"] for r in preview["blockers"]}=={"ACTIVE_SUBSCRIPTION_SOURCE"}
    with pytest.raises(AppException) as caught: lifecycle.request_module_offboarding({"userId":"0"},tid,"internship",expected_lifecycle_version=int(preview["lifecycleVersion"]),reason="仍有有效来源时不得冻结岗位实习模块",retention_days=30,retention_policy_version="POLICY-2026-09")
    assert caught.value.http_status==409


def _frozen_job(tid:int):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState
    from app.services import module_commerce_lifecycle_service as lifecycle
    _seed_tenant(tid); _pay(tid,[_sku("internship",f"M345-EXPORT-{tid}")],f"m345-export-{tid}"); _cancel_source_now(tid,"internship"); db=get_sessionmaker()()
    try: version=int(db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="internship")).one().lifecycle_version)
    finally: db.close()
    return lifecycle.request_module_offboarding({"userId":"0"},tid,"internship",expected_lifecycle_version=version,reason="学校已确认岗位实习模块合同结束并办理资料交付",retention_days=30,retention_policy_version="POLICY-2026-09")


def _export_evidence(tid:int,job:dict):
    from app.db.session import get_sessionmaker
    from app.models.data_exchange import ExportJob
    from app.models.file import ArchiveManifest,FileObject
    db=get_sessionmaker()()
    try:
        f=FileObject(tenant_id=tid,file_key=f"m345/{tid}/offboard.zip",file_name="岗位实习模块退出资料.zip",ext="zip",mime_type="application/zip",size_bytes=1234,sha256="a"*64,biz_type="INTERNSHIP_OFFBOARD_EXPORT",biz_id=job["jobId"],visibility="PRIVATE",security_level="NORMAL",status="AVAILABLE",storage_backend="local",storage_zone="ACTIVE",upload_source="SYSTEM",scan_required=False,scan_status="NOT_REQUIRED",available_at=datetime.utcnow()); db.add(f); db.flush()
        m=ArchiveManifest(tenant_id=tid,module_code="internship",archive_type="MODULE_OFFBOARD",target_type="MODULE_GENERATION",target_id="1",revision=1,status="PACKAGED",rule_version="M345-EXPORT-1",manifest_sha256="b"*64,package_file_id=int(f.id),created_by_name="M345 test",frozen_at=datetime.utcnow()); db.add(m); db.flush()
        e=ExportJob(tenant_id=tid,module_code="internship",export_type="MODULE_OFFBOARD",purpose="模块退出最终数据交付",adapter_type="MODULE_OFFBOARD",adapter_ref=f"offboard:{job['jobId']}",status="SUCCEEDED",progress=100,row_count=2,file_object_id=int(f.id),finished_at=datetime.utcnow(),filter_snapshot_json={"moduleGeneration":int(job["moduleGeneration"]),"scopeHash":job["scopeHash"]},data_scope_snapshot_json={"tenantId":str(tid),"moduleKey":"internship"},result_json={"fileSha256":"a"*64,"fileSizeBytes":1234,"manifestSha256":"b"*64,"manifestId":str(m.id),"scopeHash":job["scopeHash"],"moduleGeneration":int(job["moduleGeneration"]),"objectCount":2,"attachmentCount":1}); db.add(e); db.commit(); return int(e.id),int(m.id),int(f.id)
    finally: db.close()


def test_m5_real_export_manifest_file_and_school_acceptance_start_retention(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import TenantModuleState
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid=BASE+5; job=_frozen_job(tid); export_id,manifest_id,file_id=_export_evidence(tid,job)
    bound=lifecycle.bind_module_export({"userId":"0"},int(job["jobId"]),export_job_id=export_id,manifest_id=manifest_id,scope_hash=job["scopeHash"],expected_version=int(job["version"])); assert bound["state"]=="WAIT_EXPORT_ACCEPT" and int(bound["exportFileId"])==file_id
    accepted=lifecycle.accept_module_export({"userId":"0"},int(job["jobId"]),acceptance_ref="SCHOOL-RECEIPT-001",expected_version=int(bound["version"])); assert accepted["state"]=="RETENTION" and accepted["physicalPurgeAuthorized"] is False
    accepted_at=datetime.fromisoformat(accepted["acceptedAt"]); retention_until=datetime.fromisoformat(accepted["retentionUntil"]); assert timedelta(days=29)<retention_until-accepted_at<=timedelta(days=30,seconds=1)
    db=get_sessionmaker()()
    try:
        state=db.scalars(select(TenantModuleState).where(TenantModuleState.tenant_id==tid,TenantModuleState.module_key=="internship")).one(); assert state.data_state=="RETAINED" and state.purged_at is None
    finally: db.close()


def test_m5_wrong_scope_or_unverified_sha_cannot_enter_retention(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.data_exchange import ExportJob
    from app.services import module_commerce_lifecycle_service as lifecycle
    tid=BASE+6; job=_frozen_job(tid); export_id,manifest_id,_=_export_evidence(tid,job)
    with pytest.raises(AppException) as wrong_scope: lifecycle.bind_module_export({"userId":"0"},int(job["jobId"]),export_job_id=export_id,manifest_id=manifest_id,scope_hash="0"*64,expected_version=int(job["version"]))
    assert wrong_scope.value.http_status==409
    db=get_sessionmaker()()
    try:
        e=db.get(ExportJob,export_id); e.result_json={**dict(e.result_json or {}),"fileSha256":"c"*64}; db.commit()
    finally: db.close()
    with pytest.raises(AppException) as bad_hash: lifecycle.bind_module_export({"userId":"0"},int(job["jobId"]),export_job_id=export_id,manifest_id=manifest_id,scope_hash=job["scopeHash"],expected_version=int(job["version"]))
    assert bad_hash.value.http_status==409; current=lifecycle.get_module_offboarding_job(int(job["jobId"])); assert current["state"]=="FROZEN" and current["physicalPurgeAuthorized"] is False
