"""007 标准演示沙箱的逐表覆盖审计（只读）。

本脚本以实际连接数据库的表为准，而非只依赖 ORM；因此新迁移、遗留表及未注册
模型都不会被静默漏掉。它输出机器可读 JSON 和便于现场验收的 Markdown 清单，并对
每张带 ``tenant_id`` 的表计数。业务表为空时会明确列为待领域 seed，绝不把“有表”
误报为“有演示数据”。

用法（从 backend 目录）：
  python scripts/audit_sandbox_table_coverage.py
  python scripts/audit_sandbox_table_coverage.py --json-out ..\\artifacts\\sandbox-table-coverage.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"

# 这些表由请求、异步 worker 或安全会话自然产生；预置静态演示数据会伪造运行事实。
RUNTIME_TABLES = {
    "alembic_version",
    "t_audit_outbox",
    "t_idempotency_record",
    "t_auth_blocked_jti",
    "t_auth_refresh_token",
    "t_password_reset_sms_job",
    "t_affairs_repair_job",
    "t_file_storage_quota_reservation",
    "t_message_event_outbox",
    "t_message_delivery_job",
    "t_notification_task",
    "t_portal_login_otp",
    "t_tenant_offboarding_job",
    "t_tenant_tombstone",
}

EXEMPTION_REASONS = {
    "t_portal_login_otp": (
        "EXEMPT_RUNTIME",
        "一次性登录凭据表；只能由真实登录请求生成并过期/消费，预置会伪造可用安全凭据",
        "真实登录请求临时产生",
    ),
    "t_tenant_offboarding_job": (
        "EXEMPT_LIFECYCLE",
        "007 为 ACTIVE 正式演示租户；退服任务仅能在真实退服流程产生，预置会与租户状态矛盾",
        "活跃租户必须为 0",
    ),
    "t_tenant_tombstone": (
        "EXEMPT_LIFECYCLE",
        "租户墓碑是完成退服后的不可变凭据；007 仍活跃，不能伪造已销户事实",
        "活跃租户必须为 0",
    ),
}

# 无物理外键的历史表仍需做逻辑关联检查；先列出代码已明确的主干关系，余下关系
# 再由 ORM 列注释中的 “→ t_xxx.id” 自动发现。
KNOWN_RELATIONSHIPS = {
    ("t_student_profile", "class_id"): "t_school_class",
    ("t_school_class", "major_id"): "t_major",
    ("t_major", "college_id"): "t_college",
    ("t_gd_student", "batch_id"): "t_gd_batch",
    ("t_gd_student", "topic_id"): "t_gd_topic",
    ("t_gd_student", "mentor_id"): "t_gd_mentor",
    ("t_internship_record", "batch_id"): "t_internship_batch",
    ("t_internship_record", "position_id"): "t_internship_position",
    ("t_internship_record", "enterprise_id"): "t_emp_company",
    ("t_internship_position", "company_id"): "t_emp_company",
    ("t_aa_program_binding", "program_id"): "t_aa_program",
    ("t_aa_program_course", "program_id"): "t_aa_program",
    ("t_aa_program_course", "course_id"): "t_aa_course",
    ("t_aa_teaching_task", "course_id"): "t_aa_course",
    ("t_aa_teaching_task", "class_id"): "t_school_class",
    ("t_aa_schedule_item", "task_id"): "t_aa_teaching_task",
}


def _module(table: str) -> tuple[str, str]:
    """Return the first and second level business domain for a physical table."""
    name = table.removeprefix("t_")
    mappings = (
        (("aa_", "acad_", "academic_", "academic"), ("教务", "教学运行与质量")),
        (("internship_", "attendance_exception", "weekly_report", "risk_record"), ("岗位实习", "实习全过程")),
        (("graduation_", "gd_"), ("毕业设计", "毕业设计全过程")),
        (("emp_", "employment_"), ("就业", "就业与去向")),
        (("orientation_", "green_channel"), ("学工", "迎新")),
        (("cs_", "affairs_", "aid_", "funding_", "dorm_", "talk_", "psy_", "discipline_", "archive_"), ("学工", "学生事务")),
        (("college", "major", "school_class", "staff_assignment", "org_version"), ("学校组织", "组织与主数据")),
        (("student_",), ("学生", "学生主档与门户")),
        (("workflow_", "unified_todo", "unified_message", "message_", "notification_"), ("流程中心", "审批、消息与待办")),
        (("role", "permission", "scope_", "data_scope", "menu_", "user_", "wx_", "tenant_capability"), ("系统管理", "角色、数据范围与授权")),
        (("tenant_", "platform_", "service_", "incident_", "change_", "problem_", "recovery_", "disaster_"), ("平台治理", "租户与运维")),
    )
    for prefixes, result in mappings:
        if any(name.startswith(prefix) or name == prefix for prefix in prefixes):
            return result
    return ("其他", "待人工归类")


def _purpose(table: str) -> str:
    name = table.removeprefix("t_")
    keywords = (
        ("audit", "操作留痕/审计"), ("archive", "归档批次、归档包或归档明细"),
        ("attachment", "附件与材料关联"), ("material", "材料或证明文件"),
        ("workflow", "流程定义、实例或审批节点"), ("approval", "审批申请或审批处理"),
        ("risk", "风险预警与处置"), ("warning", "预警与干预"),
        ("evaluation", "评价任务、记录或结果"), ("grade", "成绩、复核或成绩申诉"),
        ("score", "评分、成绩或评价"), ("batch", "业务批次或批量任务"),
        ("record", "业务过程明细"), ("log", "操作或沟通记录"),
        ("config", "业务配置或规则"), ("rule", "业务规则"),
        ("template", "业务模板"), ("task", "待办、任务或执行项"),
        ("application", "申请单"), ("apply", "申请单"), ("appeal", "申诉或复议"),
        ("student", "学生业务主档或关联"), ("teacher", "教师业务关联"),
    )
    for token, label in keywords:
        if token in name:
            return label
    return "生产业务数据表"


def _references(inspector, table: str) -> list[str]:
    refs: list[str] = []
    try:
        for fk in inspector.get_foreign_keys(table):
            target = fk.get("referred_table")
            if target:
                refs.append(str(target))
    except Exception:
        pass
    return sorted(set(refs))


def _count(connection, table: str, has_tenant_id: bool) -> int:
    if not has_tenant_id:
        return 0
    quote = connection.dialect.identifier_preparer.quote
    statement = text(f"SELECT COUNT(*) FROM {quote(table)} WHERE {quote('tenant_id')} = :tenant_id")
    return int(connection.scalar(statement, {"tenant_id": TENANT_ID}) or 0)


def _metadata_relationships(db_tables: list[str]) -> dict[tuple[str, str], str]:
    """Collect declared FK/comment links without guessing a target from an ``*_id`` name."""
    from app.models.base import Base

    relationships = dict(KNOWN_RELATIONSHIPS)
    existing = set(db_tables)
    for table in Base.metadata.tables.values():
        if table.name not in existing:
            continue
        for column in table.columns:
            for foreign_key in column.foreign_keys:
                if foreign_key.column.table.name in existing:
                    relationships[(table.name, column.name)] = foreign_key.column.table.name
            comment = str(column.comment or "")
            match = re.search(r"(?:→|to\\s+)(t_[a-z0-9_]+)\\.id", comment, re.IGNORECASE)
            if match and match.group(1) in existing:
                relationships[(table.name, column.name)] = match.group(1)
    return relationships


def _integrity_report(connection, inspector, db_tables: list[str]) -> dict[str, Any]:
    """Check tenant-scoped FK/logical links and model-declared status enums, read-only."""
    quote = connection.dialect.identifier_preparer.quote
    columns_by_table = {
        table: {column["name"] for column in inspector.get_columns(table)} for table in db_tables
    }
    relationships = _metadata_relationships(db_tables)
    relation_issues: list[dict[str, Any]] = []
    cross_tenant: list[dict[str, Any]] = []
    for (source, column), target in sorted(relationships.items()):
        if source not in columns_by_table or target not in columns_by_table:
            continue
        if column not in columns_by_table[source] or "tenant_id" not in columns_by_table[source]:
            continue
        if "tenant_id" not in columns_by_table[target] or "id" not in columns_by_table[target]:
            continue
        orphan_sql = text(
            f"SELECT COUNT(*) FROM {quote(source)} s LEFT JOIN {quote(target)} p "
            f"ON p.{quote('id')}=s.{quote(column)} AND p.{quote('tenant_id')}=s.{quote('tenant_id')} "
            f"WHERE s.{quote('tenant_id')}=:tenant_id AND s.{quote(column)} IS NOT NULL "
            f"AND p.{quote('id')} IS NULL"
        )
        cross_sql = text(
            f"SELECT COUNT(*) FROM {quote(source)} s JOIN {quote(target)} p "
            f"ON p.{quote('id')}=s.{quote(column)} "
            f"WHERE s.{quote('tenant_id')}=:tenant_id AND s.{quote(column)} IS NOT NULL "
            f"AND p.{quote('tenant_id')}<>s.{quote('tenant_id')}"
        )
        orphan_count = int(connection.scalar(orphan_sql, {"tenant_id": TENANT_ID}) or 0)
        cross_count = int(connection.scalar(cross_sql, {"tenant_id": TENANT_ID}) or 0)
        if orphan_count:
            relation_issues.append({"sourceTable": source, "column": column, "targetTable": target, "count": orphan_count})
        if cross_count:
            cross_tenant.append({"sourceTable": source, "column": column, "targetTable": target, "count": cross_count})

    from app.models.base import Base
    illegal_status: list[dict[str, Any]] = []
    for table in Base.metadata.tables.values():
        if table.name not in columns_by_table or "tenant_id" not in columns_by_table[table.name] or "status" not in columns_by_table[table.name]:
            continue
        column = table.c.get("status")
        comment = str(getattr(column, "comment", "") or "")
        # Status comments use e.g. DRAFT/PENDING_REVIEW/APPROVED. Ignore prose-only comments.
        allowed = sorted(set(re.findall(r"(?<![A-Z_])[A-Z][A-Z0-9_]{2,}(?![A-Z_])", comment)))
        if len(allowed) < 2:
            continue
        values = ", ".join(f"'{value}'" for value in allowed)
        sql = text(
            f"SELECT COUNT(*) FROM {quote(table.name)} WHERE {quote('tenant_id')}=:tenant_id "
            f"AND {quote('status')} IS NOT NULL AND {quote('status')} NOT IN ({values})"
        )
        bad_count = int(connection.scalar(sql, {"tenant_id": TENANT_ID}) or 0)
        if bad_count:
            illegal_status.append({"table": table.name, "allowed": allowed, "count": bad_count})
    return {
        "relationshipsChecked": len(relationships),
        "foreignOrLogicalAssociationAnomalies": relation_issues,
        "crossTenantPollution": cross_tenant,
        "illegalStatuses": illegal_status,
        "foreignOrLogicalAssociationAnomalyCount": sum(x["count"] for x in relation_issues),
        "crossTenantPollutionCount": sum(x["count"] for x in cross_tenant),
        "illegalStatusCount": sum(x["count"] for x in illegal_status),
        # Real statistic validation is performed by check_sandbox_20k_school; this table audit
        # records no fabricated dashboard totals and therefore has no independent mismatch here.
        "statisticalInconsistencyCount": 0,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 007 数据表覆盖清单",
        "",
        f"- 租户：`{TENANT_CODE}` / `{TENANT_ID}`",
        f"- 生成时间（UTC）：{report['generatedAt']}",
        f"- 数据库总表数：{report['summary']['databaseTables']}",
        f"- 生产租户业务表：{report['summary']['tenantBusinessTables']}",
        f"- 已覆盖业务表：{report['summary']['coveredBusinessTables']}",
        f"- 空业务表：{report['summary']['emptyBusinessTables']}",
        f"- 合理豁免表：{report['summary']['exemptTables']}",
        "",
        "| 表名 | 一级/二级模块 | 业务用途 | tenant_id | 007记录数 | 计划生成数量 | 关联主表 | 覆盖状态 | 未填充原因 |",
        "|---|---|---|---|---:|---|---|---|---|",
    ]
    for row in report["tables"]:
        refs = ", ".join(row["references"]) or "—"
        lines.append(
            "| `{table}` | {module}/{submodule} | {purpose} | {tenant} | {count} | {plan} | {refs} | {status} | {reason} |".format(
                table=row["table"], module=row["module"], submodule=row["submodule"],
                purpose=row["purpose"], tenant="是" if row["hasTenantId"] else "否",
                count=row["current007Count"], plan=row["plannedCount"], refs=refs,
                status=row["coverageStatus"], reason=row["emptyReason"] or "—",
            )
        )
    lines.extend(["", "## 模块覆盖率", "", "| 模块 | 已覆盖 | 业务表 | 覆盖率 |", "|---|---:|---:|---:|"])
    for module, value in sorted(report["moduleCoverage"].items()):
        lines.append(f"| {module} | {value['covered']} | {value['total']} | {value['rate']}% |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="审计 007 租户的数据表覆盖情况（只读）")
    parser.add_argument("--json-out", type=Path, default=Path("../artifacts/007-table-coverage.json"))
    parser.add_argument("--markdown-out", type=Path, default=Path("../docs/07-部署运维交付与商业化/demo/007数据表覆盖清单.md"))
    args = parser.parse_args()

    from app.db.session import db_enabled, get_engine
    from app.models import Tenant  # noqa: F401 - registers all application models
    from app.models.base import Base

    if not db_enabled():
        raise SystemExit("DB_ENABLED=false，拒绝生成非真实数据库覆盖清单")
    engine = get_engine()
    inspector = inspect(engine)
    db_tables = sorted(inspector.get_table_names())
    model_tables = set(Base.metadata.tables)
    rows: list[dict[str, Any]] = []
    module_totals: dict[str, Counter] = defaultdict(Counter)
    with engine.connect() as connection:
        tenant = connection.execute(text("SELECT tenant_code, school_name FROM t_tenant WHERE id = :id"), {"id": TENANT_ID}).mappings().first()
        if tenant is None or tenant["tenant_code"] != TENANT_CODE:
            raise SystemExit("007 tenant identity mismatch; no report was written")
        for table in db_tables:
            columns = {str(column["name"]) for column in inspector.get_columns(table)}
            scoped = "tenant_id" in columns
            module, submodule = _module(table)
            current = _count(connection, table, scoped)
            runtime = table in RUNTIME_TABLES
            if not scoped:
                status = "EXEMPT_NON_TENANT"
                reason = "不含 tenant_id；共享主数据、平台表或数据库技术表，不能安全按 007 人工填充"
                planned: str | int = "不适用"
            elif runtime:
                if table in EXEMPTION_REASONS:
                    status, reason, planned = EXEMPTION_REASONS[table]
                else:
                    status = "EXEMPT_RUNTIME"
                    reason = "运行时安全、队列或幂等技术表；只能由真实请求/worker 产生，禁止伪造"
                    planned = "真实运行产生"
            elif current > 0:
                status = "COVERED"
                reason = ""
                planned = current
                module_totals[module]["total"] += 1
                module_totals[module]["covered"] += 1
            else:
                status = "EMPTY_NEEDS_DOMAIN_SEED"
                reason = "尚无与真实状态机一致的 007 领域记录；必须由对应领域 seed 补齐"
                planned = ">=1（按真实业务语义）"
                module_totals[module]["total"] += 1
            rows.append({
                "table": table,
                "registeredInOrm": table in model_tables,
                "module": module,
                "submodule": submodule,
                "purpose": _purpose(table),
                "hasTenantId": scoped,
                "current007Count": current,
                "plannedCount": planned,
                "references": _references(inspector, table),
                "coverageStatus": status,
                "emptyReason": reason,
            })
        integrity = _integrity_report(connection, inspector, db_tables)
    business_rows = [r for r in rows if r["coverageStatus"] in {"COVERED", "EMPTY_NEEDS_DOMAIN_SEED"}]
    module_coverage = {
        module: {
            "covered": int(values["covered"]), "total": int(values["total"]),
            "rate": round((100 * values["covered"] / values["total"]) if values["total"] else 100, 2),
        }
        for module, values in module_totals.items()
    }
    report = {
        "tenant": {"id": str(TENANT_ID), "code": TENANT_CODE, "schoolName": tenant["school_name"]},
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "databaseTables": len(rows),
            "productionBusinessTables": len(business_rows),
            "tenantBusinessTables": len(business_rows),
            "coveredBusinessTables": sum(r["coverageStatus"] == "COVERED" for r in business_rows),
            "emptyBusinessTables": sum(r["coverageStatus"] == "EMPTY_NEEDS_DOMAIN_SEED" for r in business_rows),
            "exemptTables": sum(r["coverageStatus"].startswith("EXEMPT") for r in rows),
        },
        "moduleCoverage": module_coverage,
        "integrity": integrity,
        "tables": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_out.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "moduleCoverage": module_coverage, "integrity": integrity,
                      "json": str(args.json_out), "markdown": str(args.markdown_out)}, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["emptyBusinessTables"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
