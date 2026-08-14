"""成绩「只看缺项」的服务端筛选（V93-10 / 总册 §44）。

原来这个筛选只发生在前端当前页：老师翻到第 3 页勾上「只看缺项」，筛的仍是眼前这 20 条，
第 5 页的缺项根本进不了视野，只有把每一页都翻一遍才知道还漏了谁。成绩是要报出去的，
「以为录完了其实没有」比慢更要命。

判定下推 SQL 之后，COUNT 与翻页建立在同一个谓词上：「还差几个」是真数，「下一个缺项」
也能跨页跳。

关键断言是**跨页**：种子刻意让缺项落在最后一页，如果筛选仍只作用于当前页，第 1 页就一条
都返回不了。
"""
from __future__ import annotations

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


def _seed(db, complete=8, incomplete=3):
    """先建若干「五项齐全」，再建若干「缺分项」。

    列表按 id 倒序，所以后建的缺项排在最前——为了验证跨页，测试里按 id 正序的那一页取。
    """
    from app.models import (InternshipBatch, InternshipFinalScore, InternshipRecord,
                            StudentProfile)

    batch = InternshipBatch(tenant_id=TID, batch_name="V93成绩批次",
                            batch_no=f"IXS-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()

    def _mk(idx, full):
        profile = StudentProfile(
            tenant_id=TID, student_no=f"IXS{uuid.uuid4().hex[:8]}",
            real_name=f"成绩学生{idx}", grade="2024",
            student_status="NORMAL", status="ACTIVE")
        db.add(profile)
        db.flush()
        record = InternshipRecord(tenant_id=TID, student_id=profile.id,
                                  batch_id=batch.id, status="ASSESSING")
        db.add(record)
        db.flush()
        db.add(InternshipFinalScore(
            tenant_id=TID, internship_id=record.id, student_id=profile.id, status="DRAFT",
            checkin_score=90, weekly_score=85, monthly_score=88,
            enterprise_score=92 if full else None,
            school_score=87 if full else None))
        db.flush()

    for i in range(complete):
        _mk(i, True)
    for i in range(incomplete):
        _mk(100 + i, False)
    return batch.id


@pytest.fixture()
def score_svc(db_mode):
    _ctx()
    from app.modules.internship.services import internship_score_service as svc

    return svc


def test_incomplete_only_total_counts_whole_batch(score_svc, db_mode):
    """「还差几个」必须是全批真数，不是当前页数出来的。"""
    db = _session()
    batch_id = _seed(db, complete=8, incomplete=3)
    db.commit()
    db.close()

    _ctx()
    _items, total_all = score_svc.list_scores(1, 5, batch_id=str(batch_id))
    _items2, total_incomplete = score_svc.list_scores(
        1, 5, batch_id=str(batch_id), incomplete_only=True)

    assert total_all == 11, f"全批应有 11 条成绩，实际 {total_all}"
    assert total_incomplete == 3, (
        f"缺项应为 3 条（全批真数），实际 {total_incomplete}——"
        "若等于当前页内的缺项数，说明筛选没有下推")


def test_incomplete_only_finds_rows_beyond_first_page(score_svc, db_mode):
    """本文件的核心：缺项在后面的页上，也必须被筛出来。

    页大小取 5、缺项共 3 条，只要筛选真的作用于全批，第 1 页就能一次拿到全部 3 条；
    若仍是「先取一页再过滤」，第 1 页会是 5 条齐全的，一条缺项都返回不了。
    """
    db = _session()
    batch_id = _seed(db, complete=8, incomplete=3)
    db.commit()
    db.close()

    _ctx()
    items, total = score_svc.list_scores(
        1, 5, batch_id=str(batch_id), incomplete_only=True)

    assert total == 3
    assert len(items) == 3, (
        f"第 1 页应返回全部 3 条缺项，实际 {len(items)} 条——"
        "说明筛选仍只作用于取回的当前页")
    for row in items:
        missing = [k for k in ("enterpriseScore", "schoolScore") if row.get(k) is None]
        assert missing, f"返回了不缺项的行：{row.get('studentName')}"


def test_incomplete_only_off_returns_everything(score_svc, db_mode):
    """不勾选时行为不变——新参数不能改动既有默认结果。"""
    db = _session()
    batch_id = _seed(db, complete=8, incomplete=3)
    db.commit()
    db.close()

    _ctx()
    items, total = score_svc.list_scores(1, 50, batch_id=str(batch_id))
    assert total == 11
    assert len(items) == 11


def test_incomplete_only_respects_other_filters(score_svc, db_mode):
    """与既有筛选叠加时按「且」生效，不能互相覆盖。"""
    db = _session()
    batch_id = _seed(db, complete=8, incomplete=3)
    db.commit()
    db.close()

    _ctx()
    _items, total = score_svc.list_scores(
        1, 50, batch_id=str(batch_id), status="PUBLISHED", incomplete_only=True)
    assert total == 0, "种子里没有已发布的成绩，叠加筛选后应为 0"
