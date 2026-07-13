"""13A-D 学生活动 波次1 活动底座 · 模型与约束（真实 DB 模式）。

验证四表可建 + 防重复唯一约束：
- 报名 (tenant,activity_id,student_id) 唯一
- 学分流水 (tenant,student_id,activity_id,credit_type) 唯一（防重复入账）
- 二课类目 (tenant,category_code) 唯一
（service/router/前端为波次1 后续增量，本文件先锁数据底座正确性。）
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

TID = 1000000000000000001


def _mk_activity(db, name="迎新晚会", status="DRAFT"):
    from app.models import AffairsActivity
    a = AffairsActivity(tenant_id=TID, activity_name=name, activity_type="ACTIVITY",
                        status=status, credit_type="SECOND_CLASS", credit_value=2,
                        category_code="WENTI", publisher_id=1, publisher_name="团委老师")
    db.add(a); db.flush()
    return a


def test_activity_tables_build_and_crud(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AffairsActivityCredit, AffairsActivitySignup,
                            AffairsCreditCategory)
    db = get_sessionmaker()()
    try:
        db.add(AffairsCreditCategory(tenant_id=TID, category_code="WENTI",
                                     category_name="文体活动", credit_type="SECOND_CLASS"))
        a = _mk_activity(db)
        db.add(AffairsActivitySignup(tenant_id=TID, activity_id=a.id, student_id=1001,
                                     signup_status="ENROLLED"))
        db.add(AffairsActivityCredit(tenant_id=TID, student_id=1001, activity_id=a.id,
                                     credit_type="SECOND_CLASS", credit_value=2,
                                     category_code="WENTI", source="ACTIVITY"))
        db.commit()
        from sqlalchemy import func, select
        assert db.scalar(select(func.count()).select_from(AffairsActivitySignup)) == 1
        assert db.scalar(select(func.count()).select_from(AffairsActivityCredit)) == 1
    finally:
        db.close()


def test_signup_unique_per_student(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivitySignup
    db = get_sessionmaker()()
    try:
        a = _mk_activity(db); db.commit()
        db.add(AffairsActivitySignup(tenant_id=TID, activity_id=a.id, student_id=2001))
        db.commit()
        db.add(AffairsActivitySignup(tenant_id=TID, activity_id=a.id, student_id=2001))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback(); db.close()


def test_credit_unique_prevents_double_grant(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivityCredit
    db = get_sessionmaker()()
    try:
        db.add(AffairsActivityCredit(tenant_id=TID, student_id=3001, activity_id=555,
                                     credit_type="SECOND_CLASS", credit_value=2))
        db.commit()
        db.add(AffairsActivityCredit(tenant_id=TID, student_id=3001, activity_id=555,
                                     credit_type="SECOND_CLASS", credit_value=2))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback(); db.close()
