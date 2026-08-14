"""毕业资格统计的大校规模与脱敏安全层。

只接管统计聚合/异常下钻读取，不改变毕业资格 evaluator、不可变 Run/Decision 或正式结论。
``item_results_json`` 是历史兼容 TEXT，不假设所有旧值都是合法 MySQL JSON：
- expected/passed 由 SQL 聚合；
- 异常项分布只流式读取 JSON 文本列；
- 未指定 itemType 的异常名单使用 SQL count + OFFSET/LIMIT；
- 指定 itemType 时保持逐条 JSON 精确判定，但用流式结果控制内存；
- 统计名单的学号统一不可逆展示掩码，兑现前端“学号（脱敏）”合同。
"""
from __future__ import annotations

import json

from sqlalchemy import case, func, or_, select

from app.core.exceptions import AppException

from . import academic_affairs_stats_service as stats
from .academic_affairs_production_audit_guard import _bounded_page_size


def _page_values(page, page_size) -> tuple[int, int]:
    try:
        page_no = int(1 if page is None else page)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    if page_no < 1:
        raise AppException("VALIDATION_ERROR", "page 必须大于等于 1")
    return page_no, _bounded_page_size(page_size, default=20)


def _mask_student_no(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"


def _fail_items(raw_json) -> list[str]:
    if not raw_json:
        return []
    try:
        payload = json.loads(raw_json)
    except (ValueError, TypeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    result = []
    for item in payload:
        if not isinstance(item, dict) or item.get("result") != "FAIL":
            continue
        key = str(item.get("item") or "UNKNOWN").strip() or "UNKNOWN"
        result.append(key)
    return result


def _scope_conditions(db, user, batch_id=None, college_id=None, *, abnormal_only=False):
    from app.models import AaGraduationAuditResult

    scope = stats._resolve_scope(user, db)
    stats._validate_college_param(scope, college_id)
    student_ids = stats._student_ids(db, scope, college_id)
    if student_ids is not None and not student_ids:
        return scope, None

    conditions = [
        AaGraduationAuditResult.tenant_id == stats._tid(),
        AaGraduationAuditResult.is_deleted.is_(False),
    ]
    if batch_id:
        conditions.append(AaGraduationAuditResult.batch_id == int(batch_id))
    if student_ids is not None:
        conditions.append(AaGraduationAuditResult.student_id.in_(student_ids))
    if abnormal_only:
        conditions.append(AaGraduationAuditResult.overall == "SYSTEM_ABNORMAL")
    return scope, conditions


def graduation_stats(user, batch_id=None, college_id=None) -> dict:
    """通过率走 SQL；异常项分布保持 TEXT JSON 精确语义但不 materialize ORM 全行。"""
    from app.models import AaGraduationAuditResult

    with stats.session() as db:
        scope, conditions = _scope_conditions(db, user, batch_id, college_id)
        if conditions is None:
            return {
                "passRate": None,
                "passed": 0,
                "expected": 0,
                "byAbnormalItem": [],
                "scope": {"blocked": scope.blocked},
            }

        passed_expr = or_(
            AaGraduationAuditResult.overall == "SYSTEM_PASSED",
            AaGraduationAuditResult.conclusion == "GRADUATED",
        )
        expected, passed = db.execute(
            select(
                func.count(AaGraduationAuditResult.id),
                func.coalesce(func.sum(case((passed_expr, 1), else_=0)), 0),
            ).where(*conditions)
        ).one()
        expected, passed = int(expected or 0), int(passed or 0)

        item_counts: dict[str, int] = {}
        json_query = (
            select(AaGraduationAuditResult.item_results_json)
            .where(*conditions, AaGraduationAuditResult.item_results_json.isnot(None))
            .execution_options(yield_per=500)
        )
        for raw_json in db.scalars(json_query):
            for item in _fail_items(raw_json):
                item_counts[item] = item_counts.get(item, 0) + 1

        return {
            "passRate": stats._rate(passed, expected),
            "passed": passed,
            "expected": expected,
            "byAbnormalItem": [
                {"key": key, "count": count}
                for key, count in sorted(item_counts.items())
            ],
            "scope": {"blocked": scope.blocked},
        }


graduation_stats._graduation_stats_scale_guard = True


def _profile_map(db, student_ids):
    from app.models import StudentProfile

    ids = {int(value) for value in student_ids if value is not None}
    if not ids:
        return {}
    return {
        profile.id: profile
        for profile in db.scalars(
            select(StudentProfile).where(
                StudentProfile.tenant_id == stats._tid(),
                StudentProfile.id.in_(ids),
            )
        ).all()
    }


def _dto(result_id, student_id, raw_json, status, profiles) -> dict:
    profile = profiles.get(student_id)
    return {
        "resultId": str(result_id),
        "studentName": profile.real_name if profile else "",
        "studentNo": _mask_student_no(profile.student_no if profile else ""),
        "abnormalItems": _fail_items(raw_json),
        "status": status,
    }


def graduation_abnormal(user, batch_id=None, college_id=None, item_type=None,
                        page=1, page_size=20) -> tuple[list[dict], int]:
    """异常名单：默认 SQL 真分页；指定 itemType 时对 TEXT JSON 做有界内存精确筛选。"""
    from app.models import AaGraduationAuditResult

    page_no, size = _page_values(page, page_size)
    with stats.session() as db:
        scope, conditions = _scope_conditions(
            db, user, batch_id, college_id, abnormal_only=True
        )
        if conditions is None:
            return [], 0

        if not str(item_type or "").strip():
            q = select(AaGraduationAuditResult).where(*conditions)
            total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
            rows = db.scalars(
                q.order_by(AaGraduationAuditResult.id.desc())
                .offset((page_no - 1) * size)
                .limit(size)
            ).all()
            profiles = _profile_map(db, [row.student_id for row in rows])
            items = [
                _dto(row.id, row.student_id, row.item_results_json, row.status, profiles)
                for row in rows
            ]
        else:
            wanted = str(item_type).strip()
            offset = (page_no - 1) * size
            total = 0
            selected = []
            projection = (
                select(
                    AaGraduationAuditResult.id,
                    AaGraduationAuditResult.student_id,
                    AaGraduationAuditResult.item_results_json,
                    AaGraduationAuditResult.status,
                )
                .where(*conditions)
                .order_by(AaGraduationAuditResult.id.desc())
                .execution_options(yield_per=500)
            )
            for row in db.execute(projection):
                fail_items = _fail_items(row.item_results_json)
                if wanted not in fail_items:
                    continue
                if offset <= total < offset + size:
                    selected.append((
                        row.id, row.student_id, row.item_results_json, row.status, fail_items
                    ))
                total += 1
            profiles = _profile_map(db, [row[1] for row in selected])
            items = []
            for result_id, student_id, raw_json, status, fail_items in selected:
                profile = profiles.get(student_id)
                items.append({
                    "resultId": str(result_id),
                    "studentName": profile.real_name if profile else "",
                    "studentNo": _mask_student_no(profile.student_no if profile else ""),
                    "abnormalItems": fail_items,
                    "status": status,
                })

        stats._audit(
            db,
            "STATS_DRILL_GRADUATION",
            f"毕业异常明细 total={total} batch={batch_id or '-'} item={item_type or '-'}",
        )
        db.commit()
        return items, total


graduation_abnormal._graduation_stats_scale_guard = True


def install() -> None:
    if not hasattr(stats, "_graduation_stats_scale_original_stats"):
        stats._graduation_stats_scale_original_stats = stats.graduation_stats
    if not hasattr(stats, "_graduation_stats_scale_original_abnormal"):
        stats._graduation_stats_scale_original_abnormal = stats.graduation_abnormal
    stats.graduation_stats = graduation_stats
    stats.graduation_abnormal = graduation_abnormal
