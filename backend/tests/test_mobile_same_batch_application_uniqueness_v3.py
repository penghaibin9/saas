import inspect

import pytest
from sqlalchemy import UniqueConstraint

from app.core.exceptions import AppException
from app.models import AidApply, FundingApplication
from app.services import affairs_student_atomic_service as atomic


def _unique_columns(model) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_same_batch_duplicate_policy_matches_schema_truth():
    expected = ("tenant_id", "batch_id", "student_id")
    assert expected in _unique_columns(FundingApplication)
    assert expected in _unique_columns(AidApply)

    source = inspect.getsource(atomic)
    aid_block = source[source.index("duplicate = db.scalars(select(AidApply)"):source.index("first = aid.AID_NODES[0]")]
    funding_block = source[source.index("duplicate = db.scalars(select(FundingApplication)"):source.index("snapshot = (")]

    for block in (aid_block, funding_block):
        assert "is_deleted" not in block, "唯一键不含 is_deleted，软删历史也必须在 INSERT 前拦截"
        assert "_TERMINAL" not in block, "唯一键不含 status，终态后不得走第二次 INSERT"
        assert "_reject_same_batch_duplicate" in block


def test_duplicate_guard_returns_business_conflict_instead_of_db_integrity_error():
    with pytest.raises(AppException) as exc:
        atomic._reject_same_batch_duplicate(object(), "资助申请")
    assert getattr(exc.value, "code", None) == "DATA_CONFLICT"
    assert "不可重复创建" in str(exc.value)
