#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "backend/app/services/mobile_teacher_service.py"
text = TARGET.read_text(encoding="utf-8")

old_import = '''from app.services import (academic_service, approval_service, campus_service_service,
                          orientation_service)
'''
new_import = '''from app.services import (academic_service, affairs_leave_service, approval_service,
                          campus_service_service, orientation_service)
'''

old_helper = '''def _safe_list(fn, page, ps, **kw):
    try:
        rows, total = fn(page, ps, **kw)
        return rows, total
    except Exception:  # noqa: BLE001
        return [], 0


# ══════════ 工作台总览 / 待办 ══════════
'''
new_helper = '''def _safe_list(fn, page, ps, **kw):
    try:
        rows, total = fn(page, ps, **kw)
        return rows, total
    except Exception:  # noqa: BLE001
        return [], 0


def _list_teacher_leaves(page, page_size, *, user, status=None, **_kw):
    """移动教师端复用13A请假唯一事实源，并保持当前身份数据范围。"""
    mapped_status = "PENDING" if status == "PENDING_REVIEW" else status
    return affairs_leave_service.list_leaves(
        user,
        status=mapped_status,
        page=page,
        page_size=page_size,
    )


# ══════════ 工作台总览 / 待办 ══════════
'''

replacements = [
    (old_import, new_import),
    (old_helper, new_helper),
    (
        'pending_leave = _total(campus_service_service.list_leaves, status="PENDING_REVIEW")',
        'pending_leave = _total(_list_teacher_leaves, user=u, status="PENDING_REVIEW")',
    ),
    (
        'add(campus_service_service.list_leaves, "待审请假", "campus-service", "approve", status="PENDING_REVIEW")',
        'add(_list_teacher_leaves, "待审请假", "campus-service", "approve", user=u, status="PENDING_REVIEW")',
    ),
]

changed = False
for old, new in replacements:
    if new in text:
        continue
    if old not in text:
        raise SystemExit(f"expected source snippet missing: {old[:120]!r}")
    text = text.replace(old, new, 1)
    changed = True

if changed:
    TARGET.write_text(text, encoding="utf-8")
    print("teacher_leave_source_fix=applied")
else:
    print("teacher_leave_source_fix=already_applied")
