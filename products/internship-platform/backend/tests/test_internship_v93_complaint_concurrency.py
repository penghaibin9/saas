"""实习投诉状态机并发回归（V93-07 / 总册 §14 后半）。

`transition()` 原来是「读 status → 校验 → 改字段 → Python 里 version+1 → commit」，两个处理人
同时对同一条投诉下不同结论（一个 RESOLVE、一个 REJECT），双方都读到同一状态、都通过白名单，
各自 commit——后提交者静默覆盖先提交者的结论。投诉是有对外答复的业务，结论被悄悄换掉意味着
学生收到的答复和系统留痕可能对不上。

同文件的 `to_risk()` 早就用了 `with_for_update`，说明这套保护在本模块本来就有先例，
`transition()` 是漏网的那个。

真实 MySQL（db_mode 夹具）：SQLite 压不出并发写语义。
"""
from __future__ import annotations

import threading
import uuid

import pytest

TID = 1000000000000000001


def _ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "realName": "实习处",
                      "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN",
                      "activeContextId": "ctx"})


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db, status="INVESTIGATING"):
    """种子状态必须是 INVESTIGATING：RESOLVE 的白名单前置只有它，
    而 REJECT 从 INVESTIGATING 也合法——两个动作都能真正执行，并发才压得出冲突。
    用 ACCEPTED 的话 RESOLVE 会先被状态校验挡下，「只有一个成功」就成了假象。"""
    from app.models import InternshipComplaint

    row = InternshipComplaint(
        tenant_id=TID, complaint_no=f"CP-{uuid.uuid4().hex[:10]}",
        content="投诉正文：宿舍安排与入职承诺不符，长度足够用于回归。",
        status=status, version=0)
    db.add(row)
    db.flush()
    return row.id


@pytest.fixture()
def complaint_svc(db_mode):
    _ctx()
    from app.modules.internship.services import internship_complaint_service as svc

    return svc


def _row(cid):
    from app.models import InternshipComplaint

    db = _session()
    try:
        return db.get(InternshipComplaint, cid)
    finally:
        db.close()


def test_serial_resolve_still_works(complaint_svc, db_mode):
    """先证明种子是真的：串行 RESOLVE 必须成功并把结论写进去。

    没有这条，并发用例里「只有一个成功」可能只是因为迁移本来就跑不通。
    """
    db = _session()
    cid = _seed(db)
    db.commit()
    db.close()

    result = complaint_svc.transition(cid, "RESOLVE", {"conclusion": "已协调企业更换宿舍并回访确认"})
    assert result["status"] == "RESOLVED"
    row = _row(cid)
    assert row.status == "RESOLVED"
    assert "更换宿舍" in (row.conclusion or "")


def test_stale_expected_version_is_rejected(complaint_svc, db_mode):
    """拿着过期版本来处理必须 409，而不是照着旧视图改。"""
    from app.core.exceptions import AppException

    db = _session()
    cid = _seed(db)
    db.commit()
    db.close()

    complaint_svc.transition(cid, "RESOLVE", {"conclusion": "第一次处理结论，已协调完成"})
    with pytest.raises(AppException) as exc:
        complaint_svc.transition(cid, "REJECT",
                                 {"conclusion": "驳回理由说明", "expectedVersion": 0})
    assert exc.value.http_status == 409
    assert _row(cid).status == "RESOLVED", "被拒绝的请求不该改动状态"


def test_concurrent_resolve_and_reject_single_winner(complaint_svc, db_mode):
    """两个处理人同毫秒一个 RESOLVE 一个 REJECT：只能有一个赢，结论必须与终态自洽。

    双方都在 version=0 时打开页面——这才是「同一份视图上的两个决定」。只靠 barrier 抢时序
    无法稳定复现：先跑完的提交后，后跑的会读到新版本，两次先后处理都成功本属正确行为。
    """
    from app.core.exceptions import AppException

    db = _session()
    cid = _seed(db)
    db.commit()
    db.close()

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)
    conclusions = {"RESOLVE": "已协调企业整改并回访确认",
                   "REJECT": "经核查投诉与事实不符，予以驳回"}

    def _run(action):
        _ctx()
        from app.modules.internship.services import internship_complaint_service as svc
        try:
            barrier.wait(timeout=30)
            result = svc.transition(cid, action, {"conclusion": conclusions[action],
                                                  "expectedVersion": 0})
            with lock:
                ok.append((action, result["status"]))
        except AppException as exc:
            with lock:
                failed.append((action, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001 静默吞掉会把 500 伪装成通过
            with lock:
                failed.append((action, None, repr(exc)))

    threads = [threading.Thread(target=_run, args=(a,)) for a in ("RESOLVE", "REJECT")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert len(ok) == 1, f"两个结论都成功了，投诉出现双真值：成功={ok} 失败={failed}"
    assert failed and failed[0][1] == 409, f"输家应稳定 409，实际 {failed}"

    row = _row(cid)
    winner_action, winner_status = ok[0]
    assert row.status == winner_status, (
        f"落库状态 {row.status} 与赢家回执 {winner_status} 不一致——回执和事实分叉了")
    assert (row.conclusion or "") == conclusions[winner_action], (
        "落库结论不是赢家写的那条，两次处理的字段混在了一起")
    assert int(row.version or 0) == 1, f"version 应恰好自增一次，实际 {row.version}"
