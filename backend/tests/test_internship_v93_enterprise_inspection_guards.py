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
