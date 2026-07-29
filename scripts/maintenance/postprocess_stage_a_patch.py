#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str, label: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: matches={count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# 旧 campus-service 请假实现已退出。移动工作台必须直接消费权威学工请假服务，
# 不新增兼容别名，也不绕过数据范围。
replace_once(
    "backend/app/services/mobile_teacher_service.py",
    "academic_service, approval_service, campus_service_service,",
    "academic_service, affairs_leave_service, approval_service, campus_service_service,",
    "teacher authoritative leave import",
)
replace_once(
    "backend/app/services/mobile_teacher_service.py",
    "    pending_leave = _total(campus_service_service.list_leaves, status=\"PENDING_REVIEW\")\n",
    "    _, pending_leave = affairs_leave_service.list_leaves(\n        u, status=\"PENDING\", page=1, page_size=1)\n",
    "teacher overview leave total",
)
replace_once(
    "backend/app/services/mobile_teacher_service.py",
    "    add(campus_service_service.list_leaves, \"待审请假\", \"campus-service\", \"approve\", status=\"PENDING_REVIEW\")\n",
    """    add(
        lambda page, ps, **_kw: affairs_leave_service.list_leaves(
            u, status="PENDING", page=page, page_size=ps),
        "待审请假", "student-affairs", "approve")
""",
    "teacher todos authoritative leave",
)

# Contract test records the architecture decision so the legacy call cannot return.
test_path = ROOT / "backend/tests/test_mobile_stage_a_contracts.py"
test_text = test_path.read_text(encoding="utf-8")
test_text += '''\n\ndef test_teacher_mobile_uses_authoritative_affairs_leave_service():\n    source = _read("app/services/mobile_teacher_service.py")\n    assert "affairs_leave_service.list_leaves" in source\n    assert "campus_service_service.list_leaves" not in source\n    assert 'status="PENDING"' in source\n'''
test_path.write_text(test_text, encoding="utf-8")

print("stage A generated patch postprocessed")
