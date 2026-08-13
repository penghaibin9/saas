"""V5-P1 公示天数生产口径合同。

生产界面和 OpenAPI 描述曾写"公示天数（快测可传 0）""默认 5，快测可填 0"，
但正式规则 affairs_publicity_rules.publicity_days 明确拒绝 0（1-30 天）。
这不只是把测试便利写进了学校老师的界面，而是**指引本身是错的**：
老师照着填 0 会直接被服务端驳回。

本合同锁住：正式规则是唯一口径，生产文案不得再出现测试用语，
也不得声称 0 可用。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_SURFACES = (
    "backend/app/api/v1/student_affairs.py",
    "frontend/src/modules/studentAffairs/views/aid/AidBatchView.vue",
    "frontend/src/modules/studentAffairs/views/AidWorkbenchView.vue",
    "frontend/src/modules/studentAffairs/views/funding/FundingBatchView.vue",
    "frontend/src/modules/studentAffairs/views/FundingWorkbenchView.vue",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_formal_rule_rejects_zero_and_accepts_one_to_thirty():
    """先钉死正式规则本身，后面的文案断言才有依据。"""
    from app.core.exceptions import AppException
    from app.services.affairs_publicity_rules import publicity_days

    with pytest.raises(AppException):
        publicity_days(0)
    with pytest.raises(AppException):
        publicity_days(31)
    assert publicity_days(1) == 1
    assert publicity_days(30) == 30
    assert publicity_days(None) == 5, "未填写时应落到默认 5 天"


def test_production_surfaces_carry_no_test_only_wording():
    """生产界面与 OpenAPI 描述不得出现"快测"这类测试用语。"""
    for path in PRODUCTION_SURFACES:
        assert "快测" not in _read(path), f"{path} 仍把测试便利写进生产文案"


def test_production_surfaces_do_not_advertise_zero_days():
    """不得再声称可填 0：正式规则会驳回，等于教老师提交一个必失败的表单。"""
    for path in PRODUCTION_SURFACES:
        source = _read(path)
        assert "填 0" not in source and "传 0" not in source, f"{path} 仍声称 0 可用"


def test_batch_forms_default_to_a_submittable_value():
    """新建批次表单的默认值必须落在 1-30，否则打开即不可提交。"""
    for path in (
        "frontend/src/modules/studentAffairs/views/AidWorkbenchView.vue",
        "frontend/src/modules/studentAffairs/views/FundingWorkbenchView.vue",
    ):
        source = _read(path)
        assert "publicityDays: 0" not in source, (
            f"{path} 的批次表单默认 publicityDays=0，服务端正式规则会驳回")
