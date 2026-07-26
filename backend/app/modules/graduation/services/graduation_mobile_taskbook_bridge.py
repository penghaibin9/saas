"""教师移动端历史列表 DTO 与分页兼容桥。

旧聚合 Service 的任务书、中期待办、成绩待复核分别只读取前 50/100 条；新批次
Router 再对这批已截断数据分页，会让后续页面永远漏人。安装期统一改为复用既有
毕业设计 Service 分页收齐，再交给批次 Router 做稳定 ID 过滤和当前批次分页。
不改变状态机、权限、接口地址或前端 DTO。
"""
from __future__ import annotations

_INSTALLED = False
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


def install_mobile_taskbook_list_bridge() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from app.db.session import db_enabled
    from app.services import mobile_teacher_service as mobile

    original_taskbooks = mobile.graduation_taskbook_list
    original_midterms = mobile.graduation_midterm_queue
    original_grades = mobile.graduation_grade_queue

    def taskbooks(user: dict) -> list:
        # 保留历史包装的教师身份与演示模式校验。
        value = original_taskbooks(user)
        if not db_enabled():
            rows = value.get("items") if isinstance(value, dict) else value
            if isinstance(value, dict) and not isinstance(rows, list):
                rows = value.get("list")
            return rows if isinstance(rows, list) else []
        from app.modules.graduation.services import graduation_taskbook_service as svc
        return _collect(lambda page, size: svc.list_taskbooks(page, size))

    def midterms(user: dict) -> list:
        original_midterms(user)  # 教师身份与演示模式行为保持不变。
        if not db_enabled():
            return []
        from app.modules.graduation.services import graduation_midterm_service as svc
        rows = _collect(lambda page, size: svc.list_midterms(page, size))
        return [row for row in rows if row.get("status") in {"PENDING", "RECTIFY_SUBMITTED"}]

    def grades(user: dict) -> list:
        original_grades(user)  # 教师身份与演示模式行为保持不变。
        if not db_enabled():
            return []
        from app.modules.graduation.services import graduation_grade_service as svc
        return _collect(lambda page, size: svc.list_grades(page, size, status="CALCULATED"))

    mobile.graduation_taskbook_list = taskbooks
    mobile.graduation_midterm_queue = midterms
    mobile.graduation_grade_queue = grades
