"""教师移动端历史列表权威查询服务。

旧聚合 Service 的任务书、中期待办、成绩待复核分别只读取前 50/100 条；新批次
Router 再对这批已截断数据分页，会让后续页面永远漏人。本服务复用既有
毕业设计 Service 分页收齐，并由正式聚合 Service 静态引用。
不改变状态机、权限、接口地址或前端 DTO。
"""
from __future__ import annotations

_PAGE_SIZE = 200
_MAX_PAGES = 100


def _collect(fetch_page) -> list:
    """按 Service 返回的 total 收齐，设置硬上限防止异常 Service 无限循环。"""
    rows, total = fetch_page(1, _PAGE_SIZE)
    items = list(rows or [])
    expected = max(0, int(total or 0))
    page = 2
    while len(items) < expected and page <= _MAX_PAGES:
        chunk, _ = fetch_page(page, _PAGE_SIZE)
        chunk = list(chunk or [])
        if not chunk:
            break
        items.extend(chunk)
        page += 1
    return items[:expected] if expected else items


def _batch_id(user: dict):
    return (user or {}).get("graduationBatchId") or (user or {}).get("batchId")


def taskbooks(user: dict) -> list:
    from app.db.session import db_enabled
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_taskbook_service as svc
    return _collect(lambda page, size: svc.list_taskbooks(
        page, size, batch_id=_batch_id(user),
    ))


def midterms(user: dict) -> list:
    from app.db.session import db_enabled
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_midterm_service as svc
    rows = _collect(lambda page, size: svc.list_midterms(
        page, size, batch_id=_batch_id(user),
    ))
    return [row for row in rows if row.get("status") in {"PENDING", "RECTIFY_SUBMITTED"}]


def grades(user: dict) -> list:
    from app.db.session import db_enabled
    if not db_enabled():
        return []
    from app.modules.graduation.services import graduation_grade_service as svc
    return _collect(lambda page, size: svc.list_grades(
        page, size, status="CALCULATED", batch_id=_batch_id(user),
    ))
