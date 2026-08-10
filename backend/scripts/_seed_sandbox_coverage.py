"""为真实演示沙箱补齐四大业务域的页面与流程状态数据。

主流程由各领域的显式种子负责；本文件只兜底适合“独立状态行”的 ORM 业务表。
任何依赖真实父记录、追加式版本、唯一活动子流程或数据库规则维持关系完整性的表，
必须由领域显式 seed / service 构造，禁止用通用 marker 伪造外键。
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Float, Integer, JSON,
                        Numeric, String, Text, Time, func, inspect, select)

DOMAIN_PREFIXES = (
    "t_affairs_", "t_cs_", "t_internship_", "t_attendance_exception",
    "t_weekly_report", "t_risk_record", "t_emp_", "t_gd_",
)
DOMAIN_EXACT = {"t_teacher_student_scope"}

# 即使未来模型把某些关系列改为 nullable，这些 package 11 事实仍不得由 generic seed 构造。
RELATIONAL_INTEGRITY_TABLES = frozenset({
    "t_affairs_discipline_decision_version",
    "t_affairs_discipline_appeal",
    "t_affairs_discipline_remove_apply",
    "t_affairs_discipline_subflow_lock",
    "t_cs_discipline",
})

_STATUS_TOKEN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
_IGNORE_TOKENS = {
    "JSON", "JSONB", "TODO", "NULL", "TRUE", "FALSE", "ID", "API", "PC",
    "UI", "V1", "V2", "V3", "P1", "P2", "P3", "P4", "SELF", "SYSTEM",
}


def _domain_candidates(db):
    from app.models import Base
    existing = set(inspect(db.get_bind()).get_table_names())
    return [
        table for table in Base.metadata.sorted_tables
        if table.name in existing
        and "tenant_id" in table.c
        and (table.name in DOMAIN_EXACT or table.name.startswith(DOMAIN_PREFIXES))
    ]


def required_relation_columns(table) -> tuple[str, ...]:
    """返回 generic seed 无法安全解析的必填关系 ID。

    tenant_id 由调用方给定，student_id 会解析为本租户真实学生；其余必填 *_id
    都必须来自真实父记录，绝不能使用 900... marker 猜造。
    """
    safe_ids = {"id", "tenant_id", "student_id"}
    return tuple(
        column.name for column in table.c
        if column.name.endswith("_id")
        and column.name not in safe_ids
        and not column.nullable
        and column.default is None
        and column.server_default is None
    )


def requires_explicit_relationship_seed(table) -> bool:
    return table.name in RELATIONAL_INTEGRITY_TABLES or bool(required_relation_columns(table))


def _domain_tables(db):
    return [table for table in _domain_candidates(db) if not requires_explicit_relationship_seed(table)]


def _explicit_relationship_report(db) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {}
    for table in _domain_candidates(db):
        if not requires_explicit_relationship_seed(table):
            continue
        reasons = list(required_relation_columns(table))
        if table.name in RELATIONAL_INTEGRITY_TABLES:
            reasons.append("DOMAIN_INTEGRITY_CONTRACT")
        report[table.name] = reasons
    return report


def declared_statuses(table) -> tuple[str, ...]:
    if "status" not in table.c:
        return ()
    comment = str(table.c.status.comment or "")
    tokens = [x for x in _STATUS_TOKEN.findall(comment) if x not in _IGNORE_TOKENS]
    unique = []
    for token in tokens:
        if token not in unique:
            unique.append(token)
    if unique:
        return tuple(unique[:12])
    default = getattr(table.c.status.default, "arg", None)
    return (default,) if isinstance(default, str) else ("ACTIVE",)


def _value_for(column, seq: int, row_index: int, student_id: int):
    name = column.name
    marker = 900_000_000 + seq * 100 + row_index
    typ = column.type
    if name == "tenant_id":
        raise AssertionError("tenant_id is supplied separately")
    if name == "student_id":
        return student_id
    # 这里只可能处理可选关系 ID；必填关系 ID 已被 requires_explicit_relationship_seed 排除。
    if name.endswith("_id") or name in {"assignee_id", "applicant_id", "receiver_id"}:
        return marker
    if isinstance(typ, Boolean):
        return False
    if isinstance(typ, DateTime):
        return datetime(2026, 6, 15, 9, row_index % 60)
    if isinstance(typ, Date):
        return date(2026, 6, min(28, row_index + 1))
    if isinstance(typ, Time):
        return time(9, row_index % 60)
    if isinstance(typ, (Integer, BigInteger)):
        if "count" in name or "quota" in name or "capacity" in name:
            return 10 + row_index
        return marker
    if isinstance(typ, (Numeric, Float)):
        return Decimal("80.00")
    if isinstance(typ, JSON):
        return [] if any(k in name for k in ("list", "members", "students", "attachments")) else {}
    if isinstance(typ, (String, Text)):
        suffix = f"{seq:03d}-{row_index:02d}"
        if name.endswith("_json") or name in {"scope_json", "trail_json", "detail_json"}:
            return "[]"
        if "phone" in name:
            return f"1389000{seq % 100:02d}{row_index % 100:02d}"
        if "email" in name:
            return f"demo{suffix}@example.edu.cn"
        if "date" in name:
            return "2026-06-15"
        if "time" in name or name.endswith("_at"):
            return "2026-06-15 09:00"
        if name.endswith("_no") or name.endswith("_code") or name == "code":
            return f"DEMO-{suffix}"
        if "name" in name:
            return f"演示{column.table.name[-10:]}{row_index + 1}"
        if "title" in name:
            return f"演示流程 {suffix}"
        if "reason" in name or "comment" in name or "content" in name or "detail" in name:
            return f"用于现场演示的完整流程数据 {suffix}"
        return f"演示数据-{suffix}"
    return None


def _row_values(table, tenant_id: int, status: str | None, seq: int,
                row_index: int, student_id: int) -> dict:
    values = {"tenant_id": tenant_id}
    for column in table.c:
        if column.name in {"id", "tenant_id"}:
            continue
        if column.name == "status" and status is not None:
            values[column.name] = status
            continue
        if column.name == "is_deleted":
            values[column.name] = False
            continue
        if column.name == "version":
            values[column.name] = 0
            continue
        important = any(k in column.name for k in (
            "name", "title", "code", "no", "student_id", "content", "reason",
            "detail", "type", "level", "date", "time", "_at", "_json",
        ))
        if not column.nullable and column.default is None and column.server_default is None:
            important = True
        if important:
            value = _value_for(column, seq, row_index, student_id)
            if value is not None:
                values[column.name] = value
    return values


def seed_sandbox_flow_coverage(db, tenant_id: int) -> dict:
    from app.models import StudentProfile
    student_id = db.scalar(select(StudentProfile.id).where(
        StudentProfile.tenant_id == tenant_id).order_by(StudentProfile.id))
    if student_id is None:
        return {"skipped": True, "reason": "no students"}

    inserted: dict[str, int] = {}
    tables = _domain_tables(db)
    for seq, table in enumerate(tables, 1):
        statuses = declared_statuses(table) or (None,)
        count = 0
        for row_index, status in enumerate(statuses):
            conditions = [table.c.tenant_id == tenant_id]
            if status is not None and "status" in table.c:
                conditions.append(table.c.status == status)
            if db.scalar(select(func.count()).select_from(table).where(*conditions)):
                continue
            values = _row_values(table, tenant_id, status, seq, row_index, student_id)
            db.execute(table.insert().values(**values))
            count += 1
        if count:
            inserted[table.name] = count
    db.commit()
    return {
        "tables": len(tables),
        "inserted": inserted,
        "insertedRows": sum(inserted.values()),
        "explicitRelationshipTables": _explicit_relationship_report(db),
    }


def sandbox_flow_coverage_report(db, tenant_id: int) -> dict:
    missing = []
    covered = []
    tables = _domain_tables(db)
    for table in tables:
        statuses = declared_statuses(table) or (None,)
        for status in statuses:
            conditions = [table.c.tenant_id == tenant_id]
            if status is not None and "status" in table.c:
                conditions.append(table.c.status == status)
            count = int(db.scalar(select(func.count()).select_from(table).where(*conditions)) or 0)
            item = {"table": table.name, "status": status, "count": count}
            (covered if count else missing).append(item)
    return {
        "covered": covered,
        "missing": missing,
        "coveredCount": len(covered),
        "missingCount": len(missing),
        "explicitRelationshipTables": _explicit_relationship_report(db),
    }
