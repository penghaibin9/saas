"""企业考察审核的租户边界与并发合同（V93-05 / 总册 §14）。

企业考察审核通过会直接改写 `EmpCompany.access_valid_until`，也就是「这家企业还能不能继续
接收实习生」这条准入事实。原实现有两个缺口：

1. 租户边界：`create()` 直接把请求里的 companyId 存下来，`review()` 用裸 `db.get(EmpCompany, ...)`
   取企业再改它的准入日期，两处都没有校验企业属于哪个租户。路由层只查权限，不查归属。
   于是 A 校管理员用自己合法的 `internship.enterprise.inspection.manage` 权限，就能改掉
   B 校某家企业的准入有效期——跨租户写。

2. 并发：`submit()` / `review()` 都是「db.get → 查状态 → 改 → commit」，没有行锁也没有版本
   条件。两个管理员同时审同一条考察，可以一个 APPROVE 一个 REJECT 双双成功，最终准入事实
   取决于谁的事务晚提交。

真实 MySQL（db_mode 夹具）：跨租户和并发都要在真库上验，SQLite 压不出来。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta

import pytest

TENANT_A = 1000000000000000001
TENANT_B = 1000000000000000002


def _ctx(tenant_id=TENANT_A):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(tenant_id)})
    set_current_user({"userId": "1", "tenantId": str(tenant_id), "realName": "实习处",
                      "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
                      "activeContextId": "ctx"})


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed_company(db, tenant_id, valid_until=None):
    from app.models import EmpCompany

    company = EmpCompany(
        tenant_id=tenant_id, name=f"企业-{uuid.uuid4().hex[:6]}",
        coop_status="ACTIVE", access_valid_until=valid_until)
    db.add(company)
    db.flush()
    return company.id


@pytest.fixture()
def insp_svc(db_mode):
    _ctx()
    from app.modules.internship.services import internship_enterprise_inspection_service as svc

    return svc


def _company_valid_until(company_id):
    from app.models import EmpCompany

    db = _session()
    try:
        row = db.get(EmpCompany, company_id)
        return row.access_valid_until if row else None
    finally:
        db.close()


def _file(db, owner=1, scan="NOT_REQUIRED", tenant=TENANT_A):
    from app.models.file import FileObject
    row = FileObject(tenant_id=tenant, file_key=f"inspection/{uuid.uuid4().hex}.txt", file_name="考察材料.txt",
                     ext="txt", mime_type="text/plain", size_bytes=12, sha256="a" * 64,
                     biz_type="TEMP_PRIVATE", owner_user_id=owner, visibility="PRIVATE", status="AVAILABLE",
                     storage_backend="local", storage_zone="ACTIVE", upload_source="USER",
                     scan_required=scan != "NOT_REQUIRED", scan_status=scan)
    db.add(row); db.flush()
    return str(row.id)


def test_full_inspection_draft_file_binding_and_review(insp_svc):
    from app.core.exceptions import AppException
    from app.models.file import FileObject, FileBinding
    from app.services.file_access_service import authorize_file_object
    from sqlalchemy import select
    from app.core.context import get_current_user_ctx

    with _session() as db:
        company_id = _seed_company(db, TENANT_A)
        fid = _file(db)
        db.commit()
    row = insp_svc.create({"companyId": str(company_id), "inspectionType": "ONSITE", "inspectors": "学校验收人员",
                           "inspectionDate": "2026-09-06T10:30:00+08:00", "validUntil": "2027-09-06T23:59:00+08:00",
                           "conclusion": "现场条件已核查", "riskItems": "补充安全培训记录", "rectificationItems": "开岗前复核",
                           "workplaceAddress": "虚构验收园区", "safetyCondition": "已核对防护设施", "fileIds": [fid]})
    assert row["inspectionDate"] == "2026-09-06T02:30:00+00:00"
    assert row["riskItems"] == "补充安全培训记录"
    assert row["workplaceAddress"] == "虚构验收园区"
    with _session() as db:
        file_obj = db.get(FileObject, int(fid))
        bindings = list(db.scalars(select(FileBinding).where(FileBinding.file_id == int(fid))).all())
        assert file_obj.biz_type == "INTERNSHIP_ENTERPRISE_INSPECTION"
        assert authorize_file_object(file_obj, bindings, get_current_user_ctx(), db=db)
        assert not authorize_file_object(file_obj, bindings, {"userType": "STUDENT", "userId": "1", "currentRoleCode": "SCHOOL_ADMIN"}, db=db)
    updated = insp_svc.update(row["id"], {"expectedVersion": row["version"], "conclusion": "复核后可提交"})
    assert updated["fileIds"] == [fid]
    with pytest.raises(AppException) as exc:
        insp_svc.submit(row["id"], expected_version=row["version"])
    assert exc.value.http_status == 409
    submitted = insp_svc.submit(row["id"], expected_version=updated["version"])
    with pytest.raises(AppException):
        insp_svc.update(row["id"], {"expectedVersion": submitted["version"], "conclusion": "覆盖已提交材料"})
    approved = insp_svc.review(row["id"], "APPROVE", expected_version=submitted["version"])
    assert approved["status"] == "APPROVED"
    assert _company_valid_until(company_id) == datetime(2027, 9, 6, 15, 59)


@pytest.mark.parametrize("owner,scan,tenant", [(2, "NOT_REQUIRED", TENANT_A), (1, "PENDING", TENANT_A), (1, "NOT_REQUIRED", TENANT_B)])
def test_invalid_inspection_attachment_rolls_back_entire_draft(insp_svc, owner, scan, tenant):
    from app.core.exceptions import AppException
    from app.models import InternshipEnterpriseInspection
    from app.models.file import FileBinding
    from sqlalchemy import select, func
    with _session() as db:
        company_id = _seed_company(db, TENANT_A)
        fid = _file(db, owner=owner, scan=scan, tenant=tenant)
        db.commit()
    with pytest.raises(AppException):
        insp_svc.create({"companyId": str(company_id), "conclusion": "附件边界验收", "fileIds": [fid]})
    with _session() as db:
        assert db.scalar(select(func.count()).select_from(InternshipEnterpriseInspection).where(InternshipEnterpriseInspection.company_id == company_id)) == 0
        assert db.scalar(select(func.count()).select_from(FileBinding).where(FileBinding.file_id == int(fid))) == 0


def test_draft_attachment_removal_revokes_business_read_without_retargeting(insp_svc):
    from app.models.file import FileObject, FileBinding
    from app.services.file_access_service import authorize_file_object
    from app.core.context import get_current_user_ctx
    from sqlalchemy import select
    with _session() as db:
        company_id = _seed_company(db, TENANT_A)
        fid = _file(db)
        db.commit()
    row = insp_svc.create({"companyId": str(company_id), "fileIds": [fid]})
    insp_svc.update(row["id"], {"expectedVersion": row["version"], "fileIds": []})
    with _session() as db:
        file_obj = db.get(FileObject, int(fid))
        bindings = list(db.scalars(select(FileBinding).where(FileBinding.file_id == int(fid))).all())
        assert file_obj.biz_id == row["id"]
        assert not authorize_file_object(file_obj, bindings, get_current_user_ctx(), db=db)


def test_inspection_field_validation_reports_business_errors(insp_svc):
    from app.core.exceptions import AppException
    for body in ({"inspectionDate": "bad-date"}, {"inspectionType": "UNKNOWN"}, {"fileIds": ["not-a-file"]},
                 {"inspectionDate": "2026-09-06", "validUntil": "2026-09-05"}, {"inspectors": ["错误类型"]}):
        with pytest.raises(AppException) as exc:
            insp_svc._fields(body)
        assert exc.value.http_status == 400


def test_late_approval_of_old_inspection_does_not_overwrite_newer_admission(insp_svc):
    with _session() as db:
        company_id = _seed_company(db, TENANT_A)
        db.commit()
    older = insp_svc.create({"companyId": str(company_id), "conclusion": "旧考察", "validUntil": "2027-01-01"})
    newer = insp_svc.create({"companyId": str(company_id), "conclusion": "新考察", "validUntil": "2028-01-01"})
    insp_svc.submit(older["id"])
    insp_svc.submit(newer["id"])
    insp_svc.review(newer["id"], "APPROVE")
    insp_svc.review(older["id"], "APPROVE")
    assert _company_valid_until(company_id) == datetime(2028, 1, 1)


def test_cannot_create_inspection_for_another_tenant_company(insp_svc, db_mode):
    """A 校不能给 B 校的企业建考察记录——这是跨租户写的入口，必须在这里就堵死。"""
    from app.core.exceptions import AppException

    db = _session()
    foreign = _seed_company(db, TENANT_B)
    db.commit()
    db.close()

    _ctx(TENANT_A)
    with pytest.raises(AppException) as exc:
        insp_svc.create({"companyId": str(foreign), "conclusion": "看起来不错"})
    assert exc.value.http_status in (400, 403, 404), f"实际 {exc.value.http_status} {exc.value.code}"


def test_approve_never_touches_another_tenant_company(insp_svc, db_mode):
    """纵深防御：即便库里已存在一条指向他校企业的历史脏数据，审核通过也不许改对方的准入事实。

    第一道闸是 create 的归属校验；这条测的是第二道闸——审核落库前重新确认企业归属。
    只有一道闸的话，历史脏数据仍能在下一次审核时改掉他校数据。
    """
    from app.models import InternshipEnterpriseInspection

    original = datetime(2030, 1, 1)
    db = _session()
    foreign = _seed_company(db, TENANT_B, valid_until=original)
    # 绕过 service 直接造脏数据：模拟归属校验上线之前遗留的记录
    row = InternshipEnterpriseInspection(
        tenant_id=TENANT_A, company_id=foreign, inspection_type="DOCUMENT",
        status="SUBMITTED", conclusion="历史脏数据")
    db.add(row)
    db.flush()
    rid = row.id
    db.commit()
    db.close()

    _ctx(TENANT_A)
    tampered = datetime(2099, 12, 31)
    try:
        insp_svc.review(rid, "APPROVE", comment="通过", valid_until=tampered)
    except Exception:
        pass  # 拒绝也是可接受结果；这里只断言他校数据没被改

    assert _company_valid_until(foreign) == original, (
        "A 校的审核改掉了 B 校企业的准入有效期——跨租户写没有被挡住")


def test_serial_review_still_updates_own_company(insp_svc, db_mode):
    """先证明种子是真的：同租户正常审核必须真的把准入事实写进去。

    没有这条，上面「他校数据没被改」可能只是因为审核根本没生效。
    """
    db = _session()
    own = _seed_company(db, TENANT_A)
    db.commit()
    db.close()

    _ctx(TENANT_A)
    created = insp_svc.create({"companyId": str(own), "conclusion": "现场考察合格"})
    insp_svc.submit(created["id"])
    until = datetime.utcnow() + timedelta(days=365)
    insp_svc.review(created["id"], "APPROVE", comment="准入通过", valid_until=until)

    stored = _company_valid_until(own)
    assert stored is not None, "审核通过却没有写入准入有效期"
    assert abs((stored - until).total_seconds()) < 2


def test_concurrent_review_single_winner(insp_svc, db_mode):
    """两个管理员同毫秒一个 APPROVE 一个 REJECT：只能有一个赢。

    准入事实必须和审核结论自洽——不能出现「回执写着驳回，企业却被放行」。
    """
    from app.core.exceptions import AppException
    from app.models import InternshipEnterpriseInspection

    db = _session()
    own = _seed_company(db, TENANT_A)
    db.commit()
    db.close()

    _ctx(TENANT_A)
    created = insp_svc.create({"companyId": str(own), "conclusion": "现场考察"})
    insp_svc.submit(created["id"])
    rid = created["id"]

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)
    until = datetime.utcnow() + timedelta(days=180)

    def _run(action):
        _ctx(TENANT_A)
        from app.modules.internship.services import internship_enterprise_inspection_service as svc
        try:
            barrier.wait(timeout=30)
            result = svc.review(rid, action, comment=f"{action} 结论",
                                valid_until=until if action == "APPROVE" else None)
            with lock:
                ok.append((action, result["status"]))
        except AppException as exc:
            with lock:
                failed.append((action, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001 静默吞掉会把 500 伪装成通过
            with lock:
                failed.append((action, None, repr(exc)))

    threads = [threading.Thread(target=_run, args=(a,)) for a in ("APPROVE", "REJECT")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert len(ok) == 1, f"两个审核都成功了，准入结论出现双真值：成功={ok} 失败={failed}"
    assert failed and failed[0][1] == 409, f"输家应稳定 409，实际 {failed}"

    db = _session()
    row = db.get(InternshipEnterpriseInspection, int(rid))
    final_status = row.status
    db.close()

    stored = _company_valid_until(own)
    if final_status == "REJECTED":
        assert stored is None, "审核结论是驳回，企业却被写入了准入有效期——结论与准入事实矛盾"
    else:
        assert final_status == "APPROVED"
        assert stored is not None, "审核通过却没写入准入有效期"
