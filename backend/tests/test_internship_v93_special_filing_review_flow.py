"""特殊备案：创建之后的审核链路与工作台列表（补 20260814_ix_filing_actor_cols 的验证缺口）。

背景：`create()` 曾经 100% 抛 TypeError（给模型传了不存在的 requested_by_name 等字段），
表里永远 0 行，于是**创建之后的所有代码从来没有被执行过**——包括 `review()` 里那条
「申请人与审核人必须分离」的守卫（它读 `row.requested_by_user_id`，字段不存在时是
AttributeError → 500）。

补列修好创建之后，这些路径会在真实学校那里第一次真正跑起来。只证明「能建出来」是不够的，
本文件证明「建出来之后审得动、守卫真的拦人、工作台列得出来」。

真实 MySQL（db_mode 夹具）。
"""
from __future__ import annotations

import uuid

import pytest

TID = 1000000000000000001

#: 申请人（也是学校管理员，用来验证「即使权限够，也不能自己审自己」）
REQUESTER = {"userId": "9001", "tenantId": str(TID), "realName": "申请管理员",
             "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN"}
#: 另一位学校管理员，负责真正的审核
REVIEWER = {"userId": "9002", "tenantId": str(TID), "realName": "审核管理员",
            "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN"}


def _ctx(user):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user(user)


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


@pytest.fixture()
def seeded(db_mode):
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    db = _session()
    batch = InternshipBatch(tenant_id=TID, batch_name="特殊备案审核批次",
                            batch_no=f"IXF-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()
    profile = StudentProfile(tenant_id=TID, student_no=f"IXF{uuid.uuid4().hex[:8]}",
                             real_name="备案甲", grade="2024",
                             student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    record = InternshipRecord(tenant_id=TID, student_id=profile.id, batch_id=batch.id,
                              status="ONBOARD")
    db.add(record)
    db.flush()
    db.commit()
    ids = {"batch": batch.id, "internship": record.id, "student": profile.id}
    db.close()
    return ids


def _create_filing(ids):
    """由 REQUESTER 建一条特殊备案，返回 (id, version)。"""
    from app.modules.internship.services import internship_special_filing_service as svc

    _ctx(REQUESTER)
    created = svc.create({
        "internshipId": str(ids["internship"]), "filingType": "OTHER",
        "triggerReason": "企业临时调整岗位安排，需补充备案说明情况。",
        "fileIds": ["f-evidence-1"],
    }, user=REQUESTER)
    return created["id"], created["version"]


def test_create_persists_requester_identity(seeded):
    """创建必须把申请人身份真正落库——这四列以前根本不存在。"""
    from app.models import InternshipSpecialFiling

    filing_id, _version = _create_filing(seeded)

    db = _session()
    try:
        row = db.get(InternshipSpecialFiling, int(filing_id))
        assert row is not None
        assert row.status == "DRAFT"
        assert row.requested_by_name == REQUESTER["realName"]
        assert row.requested_by_user_id == REQUESTER["userId"]
    finally:
        db.close()


def test_full_review_flow_reaches_approved(seeded):
    """草稿 → 提交 → 学院通过 → 学校通过，全链路走通并留下审核人。

    这条链路以前一步都走不到（表里建不出行）。
    """
    from app.models import InternshipSpecialFiling
    from app.modules.internship.services import internship_special_filing_service as svc

    filing_id, version = _create_filing(seeded)

    _ctx(REQUESTER)
    submitted = svc.submit(filing_id, user=REQUESTER, expected_version=version)
    assert submitted["status"] == "PENDING_COLLEGE"

    _ctx(REVIEWER)
    college = svc.review(filing_id, "COLLEGE", "APPROVE", comment="学院同意备案",
                         user=REVIEWER, expected_version=submitted["version"])
    assert college["status"] == "PENDING_SCHOOL"

    school = svc.review(filing_id, "SCHOOL", "APPROVE", comment="学校同意备案",
                        user=REVIEWER, expected_version=college["version"])
    assert school["status"] == "APPROVED"

    db = _session()
    try:
        row = db.get(InternshipSpecialFiling, int(filing_id))
        assert row.status == "APPROVED"
        # 审核人身份要真正落库（reviewed_* 也是本次补的列）
        assert row.reviewed_by_name == REVIEWER["realName"]
        assert row.reviewed_at is not None
        assert row.college_review_by == REVIEWER["realName"]
        assert row.school_review_by == REVIEWER["realName"]
        assert row.approved_by_name == REVIEWER["realName"]
        # 申请人身份不能被审核动作覆盖掉
        assert row.requested_by_user_id == REQUESTER["userId"]
    finally:
        db.close()


def test_requester_cannot_review_own_filing(seeded):
    """职责分离守卫：申请人即使是学校管理员，也不能审自己提的备案。

    **这是本次补列真正保住的东西**：守卫读 `row.requested_by_user_id`，
    字段不存在时那行是 AttributeError（500），等于守卫从来没生效过。
    删掉 service 里的字段引用也能让接口不报错，但会把这条守卫一起悄悄删掉——
    那是把功能缺陷改成合规缺陷，所以修法选的是补列。
    """
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_special_filing_service as svc

    filing_id, version = _create_filing(seeded)
    _ctx(REQUESTER)
    submitted = svc.submit(filing_id, user=REQUESTER, expected_version=version)

    with pytest.raises(AppException) as exc:
        svc.review(filing_id, "COLLEGE", "APPROVE", comment="我自己批了",
                   user=REQUESTER, expected_version=submitted["version"])
    assert exc.value.http_status == 403, f"应当拒绝自审，实际 {exc.value.http_status}"

    # 换一位审核人就应该能过——证明上面拦的是"自审"，不是"审核根本不能用"
    _ctx(REVIEWER)
    college = svc.review(filing_id, "COLLEGE", "APPROVE", comment="学院同意备案",
                         user=REVIEWER, expected_version=submitted["version"])
    assert college["status"] == "PENDING_SCHOOL"


def test_workbench_lists_filing_without_crashing(seeded):
    """合规工作台要能把新建的备案列出来。

    以前表里永远 0 行，`filings` 那段循环体一次都没执行过。
    """
    from app.modules.internship.services import internship_compliance_workbench_service as wb

    filing_id, _version = _create_filing(seeded)

    _ctx(REVIEWER)
    data = wb.get_workbench(str(seeded["batch"]), user=REVIEWER)
    filings = data.get("filings") or []
    hit = [f for f in filings if str(f.get("id")) == str(filing_id)]
    assert hit, f"工作台没有列出刚建的备案：{filings}"
    assert hit[0]["filingType"] == "OTHER"
    assert hit[0]["status"] == "DRAFT"
    # 计数口径也要把它算进待办
    assert (data.get("counts") or {}).get("filingPending", 0) >= 1
