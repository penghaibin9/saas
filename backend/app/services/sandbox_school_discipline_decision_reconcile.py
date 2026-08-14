"""20K sandbox · package-11 处分决定版本链建站与只读对账。

真实 Alembic schema 会在 package-11 迁移时给当时已经存在的生效处分回填
DisciplineDecisionVersion；20K 学校数据是在 alembic head 之后生成，因此必须在正式
建站链里同步生成 ORIGINAL 决定版本，并把主案与 CsDiscipline 投影都指向同一版本。

本模块不调用处分 workflow 来“事后补绿”。写阶段只执行 package-11 已冻结的追加式
ORIGINAL 语义；verify_discipline_decision_links 仅 SELECT，可供独立 smoke 使用。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import inspect, select, text

from app.models import DisciplineDecisionVersion

EXPECTED_EFFECTIVE_DISCIPLINE = 50
_REQUIRED_CASE_COLUMNS = {"current_decision_version_id", "current_decision_version_no"}
_REQUIRED_PROJECTION_COLUMNS = {"decision_version_id", "decision_version_no"}


def _package11_contract_ready(db) -> bool:
    inspector = inspect(db.get_bind())
    if not inspector.has_table("t_affairs_discipline_decision_version"):
        return False
    case_columns = {row["name"] for row in inspector.get_columns("t_affairs_discipline_case")}
    projection_columns = {row["name"] for row in inspector.get_columns("t_cs_discipline")}
    return _REQUIRED_CASE_COLUMNS <= case_columns and _REQUIRED_PROJECTION_COLUMNS <= projection_columns


def _require_formal_contract(db) -> None:
    if _package11_contract_ready(db):
        return
    if db.get_bind().dialect.name == "mysql":
        raise RuntimeError("20K 处分决定版本建站要求 package-11 Alembic schema")


def reconcile_discipline_decision_links(db, tenant_id: int) -> dict:
    """为 Alembic 之后 seed 的 50 条 EFFECTIVE 处分追加 ORIGINAL 决定版本。

    非 MySQL create_all 开发 schema 没有迁移专属 link columns，直接跳过；正式 20K
    MySQL 验收若缺 package-11 合同则 fail-closed。
    """
    _require_formal_contract(db)
    if not _package11_contract_ready(db):
        return {
            "schema": "dev-create-all",
            "createdDecisionVersions": 0,
            "linkedCases": 0,
            "linkedProjections": 0,
            "passed": True,
        }

    rows = db.execute(text("""
        SELECT c.id AS case_id,
               c.disc_type,
               c.reason,
               c.doc_no,
               c.decide_date,
               c.effective_at,
               c.cs_discipline_id AS projection_id
          FROM t_affairs_discipline_case c
         WHERE c.tenant_id = :tenant_id
           AND c.is_deleted = 0
           AND c.status = 'EFFECTIVE'
         ORDER BY c.id
    """), {"tenant_id": tenant_id}).mappings().all()
    if len(rows) != EXPECTED_EFFECTIVE_DISCIPLINE:
        raise RuntimeError(
            "20K 生效处分基数异常: "
            f"expected={EXPECTED_EFFECTIVE_DISCIPLINE} actual={len(rows)}"
        )

    case_ids = [int(row["case_id"]) for row in rows]
    existing = db.scalars(select(DisciplineDecisionVersion).where(
        DisciplineDecisionVersion.tenant_id == tenant_id,
        DisciplineDecisionVersion.case_id.in_(case_ids),
    ).order_by(
        DisciplineDecisionVersion.case_id,
        DisciplineDecisionVersion.version_no,
    )).all()
    by_case: dict[int, list[DisciplineDecisionVersion]] = {}
    for version in existing:
        by_case.setdefault(int(version.case_id), []).append(version)

    created = 0
    linked_cases = 0
    linked_projections = 0
    for row in rows:
        case_id = int(row["case_id"])
        projection_id = int(row["projection_id"] or 0)
        if projection_id <= 0:
            raise RuntimeError(f"EFFECTIVE 处分缺少 CsDiscipline 投影: case={case_id}")

        versions = by_case.get(case_id, [])
        if len(versions) > 1:
            raise RuntimeError(f"20K EFFECTIVE 处分出现多版本初始链: case={case_id} versions={len(versions)}")
        if versions:
            decision = versions[0]
            if (
                int(decision.version_no) != 1
                or decision.decision_kind != "ORIGINAL"
                or decision.previous_version_id is not None
                or decision.disc_type != row["disc_type"]
                or decision.doc_no != row["doc_no"]
            ):
                raise RuntimeError(f"20K 处分既有 ORIGINAL 版本与主案不一致: case={case_id}")
        else:
            decided_at = row["effective_at"] or row["decide_date"] or datetime(2026, 4, 18)
            decision = DisciplineDecisionVersion(
                tenant_id=tenant_id,
                case_id=case_id,
                version_no=1,
                decision_kind="ORIGINAL",
                previous_version_id=None,
                disc_type=str(row["disc_type"]),
                reason=row["reason"],
                doc_no=row["doc_no"],
                source_type="SANDBOX_REAL_SCHOOL_SEED",
                source_id=case_id,
                decided_by=None,
                decided_at=decided_at,
            )
            db.add(decision)
            db.flush()
            created += 1

        case_update = db.execute(text("""
            UPDATE t_affairs_discipline_case
               SET current_decision_version_id = :decision_id,
                   current_decision_version_no = 1
             WHERE tenant_id = :tenant_id
               AND id = :case_id
               AND is_deleted = 0
               AND status = 'EFFECTIVE'
        """), {
            "decision_id": int(decision.id),
            "tenant_id": tenant_id,
            "case_id": case_id,
        })
        if int(case_update.rowcount or 0) != 1:
            raise RuntimeError(f"20K 处分主案决定版本回链失败: case={case_id}")
        linked_cases += 1

        projection_update = db.execute(text("""
            UPDATE t_cs_discipline
               SET decision_version_id = :decision_id,
                   decision_version_no = 1
             WHERE tenant_id = :tenant_id
               AND id = :projection_id
               AND source_case_id = :case_id
               AND is_deleted = 0
               AND status = 'EFFECTIVE'
        """), {
            "decision_id": int(decision.id),
            "tenant_id": tenant_id,
            "projection_id": projection_id,
            "case_id": case_id,
        })
        if int(projection_update.rowcount or 0) != 1:
            raise RuntimeError(
                "20K 处分投影决定版本回链失败: "
                f"case={case_id} projection={projection_id}"
            )
        linked_projections += 1

    db.commit()
    report = verify_discipline_decision_links(db, tenant_id)
    return {
        "schema": "package11",
        "createdDecisionVersions": created,
        "linkedCases": linked_cases,
        "linkedProjections": linked_projections,
        "verification": report,
        "passed": report["passed"],
    }


def verify_discipline_decision_links(db, tenant_id: int) -> dict:
    """独立只读对账：EFFECTIVE 主案、ORIGINAL 决定版本、CsDiscipline 必须 1:1:1。"""
    _require_formal_contract(db)
    if not _package11_contract_ready(db):
        return {
            "schema": "dev-create-all",
            "effectiveCases": 0,
            "decisionVersions": 0,
            "linkedTriples": 0,
            "mismatches": 0,
            "passed": True,
        }

    effective_cases = int(db.execute(text("""
        SELECT COUNT(*)
          FROM t_affairs_discipline_case c
         WHERE c.tenant_id = :tenant_id
           AND c.is_deleted = 0
           AND c.status = 'EFFECTIVE'
    """), {"tenant_id": tenant_id}).scalar() or 0)

    decision_versions = int(db.execute(text("""
        SELECT COUNT(*)
          FROM t_affairs_discipline_decision_version v
          JOIN t_affairs_discipline_case c
            ON c.tenant_id = v.tenant_id
           AND c.id = v.case_id
           AND c.is_deleted = 0
           AND c.status = 'EFFECTIVE'
         WHERE v.tenant_id = :tenant_id
    """), {"tenant_id": tenant_id}).scalar() or 0)

    linked_triples = int(db.execute(text("""
        SELECT COUNT(*)
          FROM t_affairs_discipline_case c
          JOIN t_affairs_discipline_decision_version v
            ON v.tenant_id = c.tenant_id
           AND v.case_id = c.id
           AND v.id = c.current_decision_version_id
           AND v.version_no = c.current_decision_version_no
          JOIN t_cs_discipline d
            ON d.tenant_id = c.tenant_id
           AND d.id = c.cs_discipline_id
           AND d.source_case_id = c.id
           AND d.is_deleted = 0
           AND d.status = 'EFFECTIVE'
           AND d.decision_version_id = v.id
           AND d.decision_version_no = v.version_no
         WHERE c.tenant_id = :tenant_id
           AND c.is_deleted = 0
           AND c.status = 'EFFECTIVE'
           AND v.version_no = 1
           AND v.decision_kind = 'ORIGINAL'
           AND v.previous_version_id IS NULL
           AND v.source_type = 'SANDBOX_REAL_SCHOOL_SEED'
           AND v.source_id = c.id
           AND v.disc_type = c.disc_type
    """), {"tenant_id": tenant_id}).scalar() or 0)

    bad_version_cardinality = int(db.execute(text("""
        SELECT COUNT(*)
          FROM (
                SELECT c.id
                  FROM t_affairs_discipline_case c
                  LEFT JOIN t_affairs_discipline_decision_version v
                    ON v.tenant_id = c.tenant_id
                   AND v.case_id = c.id
                 WHERE c.tenant_id = :tenant_id
                   AND c.is_deleted = 0
                   AND c.status = 'EFFECTIVE'
                 GROUP BY c.id
                HAVING COUNT(v.id) <> 1
          ) bad
    """), {"tenant_id": tenant_id}).scalar() or 0)

    registered_with_versions = int(db.execute(text("""
        SELECT COUNT(*)
          FROM t_affairs_discipline_case c
         WHERE c.tenant_id = :tenant_id
           AND c.is_deleted = 0
           AND c.status = 'REGISTERED'
           AND EXISTS (
               SELECT 1
                 FROM t_affairs_discipline_decision_version v
                WHERE v.tenant_id = c.tenant_id
                  AND v.case_id = c.id
           )
    """), {"tenant_id": tenant_id}).scalar() or 0)

    mismatches = (
        abs(effective_cases - linked_triples)
        + bad_version_cardinality
        + registered_with_versions
    )
    passed = (
        effective_cases == EXPECTED_EFFECTIVE_DISCIPLINE
        and decision_versions == EXPECTED_EFFECTIVE_DISCIPLINE
        and linked_triples == EXPECTED_EFFECTIVE_DISCIPLINE
        and bad_version_cardinality == 0
        and registered_with_versions == 0
    )
    report = {
        "schema": "package11",
        "effectiveCases": effective_cases,
        "decisionVersions": decision_versions,
        "linkedTriples": linked_triples,
        "badVersionCardinality": bad_version_cardinality,
        "registeredCasesWithVersions": registered_with_versions,
        "mismatches": mismatches,
        "passed": passed,
    }
    if not passed:
        raise RuntimeError(f"20K 处分决定版本链只读对账失败: {report}")
    return report
