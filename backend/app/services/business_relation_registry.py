"""SYS-05 业务关系中心：统一发现与治理，但**不复制业务关系数据**。

分工必须先说清楚
────────────────
- 权威**数据**永远在业务表里（班级的辅导员在 t_school_class，导师在 t_gd_student…），
  系统管理不建一张"通用关系表"去镜像它们——镜像一定会和业务表对不上，还会诱使
  管理员在系统管理里直接改业务终态。
- 权威**目录**在 ``docs/architecture/business-relation-registry.yaml``：有哪些关系、
  谁是 owner、真实字段在哪、用哪个 resolver 解析数据范围、被哪个测试锁住。

登记不是自说自话：``validate_registry()`` 会真的去 import 模型、查字段、import
resolver、找测试文件。登记里写了一个不存在的字段，这里直接报 FAIL——这正是它抓到
GD_STUDENTS resolver 读空字段的方式。
"""
from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY_PATH = _ROOT / "docs" / "architecture" / "business-relation-registry.yaml"

# 校验结论
CHECK_OK = "OK"
CHECK_MODEL_MISSING = "MODEL_MISSING"
CHECK_FIELD_MISSING = "FIELD_MISSING"
CHECK_RESOLVER_MISSING = "RESOLVER_MISSING"
CHECK_RESOLVER_FIELD_MISSING = "RESOLVER_FIELD_MISSING"
CHECK_TEST_MISSING = "TEST_MISSING"
CHECK_UNSTABLE_KEY = "UNSTABLE_KEY"

# 关系数据问题
ISSUE_MISSING_SUBJECT = "MISSING_SUBJECT"      # 对象没有负责人（班级没辅导员…）
ISSUE_UNSTABLE_KEY_ONLY = "UNSTABLE_KEY_ONLY"  # 只填了姓名键，没填稳定 ID
ISSUE_DANGLING_SUBJECT = "DANGLING_SUBJECT"    # 负责人账号不存在或已停用
ISSUE_INACTIVE_OBJECT = "INACTIVE_OBJECT"      # 对象本身已失效（关系随之过期）

_ISSUE_TEXT = {
    ISSUE_MISSING_SUBJECT: "没有指定负责人，相关数据范围解析不出任何人",
    ISSUE_UNSTABLE_KEY_ONLY: "只填了姓名/文本键，没有稳定 ID，改名即失联",
    ISSUE_DANGLING_SUBJECT: "负责人账号不存在或已停用，关系实际失效",
    ISSUE_INACTIVE_OBJECT: "关系载体已失效（状态不在有效值内）",
}


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


@lru_cache(maxsize=1)
def load_registry() -> list[dict]:
    if not _REGISTRY_PATH.exists():
        raise AppException("SERVER_ERROR", "业务关系注册表缺失，无法治理关系完整性",
                           http_status=503)
    import yaml

    data = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    relations = data.get("relations") or []
    if not isinstance(relations, list) or not relations:
        raise AppException("SERVER_ERROR", "业务关系注册表为空", http_status=503)
    return relations


def _entry(relation_type: str) -> dict:
    for item in load_registry():
        if item.get("relationType") == relation_type:
            return item
    raise AppException("VALIDATION_ERROR", f"未登记的业务关系类型：{relation_type}")


def _import_attr(dotted: str):
    """``a.b.C`` → 类；``a.b._func`` → 函数。找不到返回 None，不抛。"""
    if not dotted:
        return None
    module_name, _, attr = str(dotted).rpartition(".")
    if not module_name:
        return None
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    return getattr(module, attr, None)


def _resolver_reads(resolver_dotted: str) -> list[str]:
    """把 resolver 源码里 getattr(r, "x") 读的字段名抓出来，用于交叉校验。"""
    import inspect
    import re

    fn = _import_attr(resolver_dotted)
    if fn is None:
        return []
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return []
    return sorted(set(re.findall(r'getattr\(\s*r\s*,\s*"([a-z_]+)"', src)))


def validate_registry() -> list[dict]:
    """逐条把登记拿去和真实代码对账。SYS05-T01 就锁在这里。"""
    out: list[dict] = []
    for item in load_registry():
        checks: list[dict] = []
        model = _import_attr(item.get("sourceModel") or "")
        if model is None:
            checks.append({"code": CHECK_MODEL_MISSING,
                           "message": f"模型无法导入：{item.get('sourceModel')}"})
        else:
            for field_key in ("subjectField", "legacySubjectField"):
                field = item.get(field_key)
                if field and not hasattr(model, field):
                    checks.append({"code": CHECK_FIELD_MISSING,
                                   "message": f"{item.get('sourceModel')} 没有字段 {field}"})
            validity = item.get("validity") or {}
            if validity.get("kind") == "STATUS" and validity.get("field") \
                    and not hasattr(model, validity["field"]):
                checks.append({"code": CHECK_FIELD_MISSING,
                               "message": f"{item.get('sourceModel')} 没有状态字段 {validity['field']}"})

        resolver = item.get("resolver")
        if not resolver:
            checks.append({"code": CHECK_RESOLVER_MISSING,
                           "message": f"未登记 resolver，数据范围 {item.get('scopeType')} 将默认拒绝"})
        elif _import_attr(resolver) is None:
            checks.append({"code": CHECK_RESOLVER_MISSING,
                           "message": f"resolver 无法导入：{resolver}"})
        elif model is not None:
            # 只看"人这一侧"的字段：对象侧的 id/student_id 本来就在，混进来会稀释判断
            reads = [f for f in _resolver_reads(resolver)
                     if f not in {"id", "student_id", "tenant_id", "is_deleted", "status"}]
            missing = [f for f in reads if not hasattr(model, f)]
            if reads and len(missing) == len(reads):
                checks.append({
                    "code": CHECK_RESOLVER_FIELD_MISSING,
                    "message": (f"resolver 读的字段 {missing} 在 {item.get('sourceModel')} 上"
                                f"全部不存在，该数据范围实际恒为拒绝"),
                })

        if str(item.get("subjectKeyKind") or "") == "NAME_TEXT":
            checks.append({"code": CHECK_UNSTABLE_KEY,
                           "message": f"关系键是文本（{item.get('subjectField')}），改名即失联，待整改"})

        test_path = item.get("test") or ""
        if not test_path or not (_ROOT / test_path.split("::")[0]).exists():
            checks.append({"code": CHECK_TEST_MISSING, "message": f"测试不存在：{test_path}"})

        out.append({
            "relationType": item.get("relationType"),
            "label": item.get("label"),
            "ownerModule": item.get("ownerModule"),
            "sourceModel": item.get("sourceModel"),
            "subjectField": item.get("subjectField"),
            "subjectKeyKind": item.get("subjectKeyKind"),
            "scopeType": item.get("scopeType"),
            "resolver": item.get("resolver"),
            "test": test_path,
            "notes": item.get("notes") or "",
            "checks": checks,
            "healthy": not checks,
        })
    return out


def list_types() -> dict:
    rows = validate_registry()
    return {
        "list": rows,
        "total": len(rows),
        "healthy": sum(1 for r in rows if r["healthy"]),
        "unhealthy": sum(1 for r in rows if not r["healthy"]),
    }


# ── 关系数据体检（读业务权威表，不落任何副本）─────────────────────────────────
def _active_user_ids(db, tenant_id: int) -> set[str]:
    from app.models import User

    return {str(r) for r in db.scalars(select(User.id).where(
        User.tenant_id == tenant_id, User.is_deleted.is_(False),
        User.status == "ACTIVE")).all()}


def inspect_relation(relation_type: str, *, tenant_id: int | None = None,
                     sample_limit: int = 20) -> dict:
    """按业务权威表统计一种关系的完整性。计数直接来自业务表，不来自任何缓存或副本。"""
    item = _entry(relation_type)
    tid = _tid(tenant_id)
    model = _import_attr(item.get("sourceModel") or "")
    if model is None:
        raise AppException("SERVER_ERROR",
                           f"业务模型不可用：{item.get('sourceModel')}", http_status=503)

    subject_field = item.get("subjectField")
    legacy_field = item.get("legacySubjectField")
    validity = item.get("validity") or {}
    active_values = [str(v) for v in (validity.get("activeValues") or [])]
    status_col = getattr(model, validity.get("field"), None) if validity.get("field") else None
    subject_col = getattr(model, subject_field, None) if subject_field else None
    legacy_col = getattr(model, legacy_field, None) if legacy_field else None
    if subject_col is None:
        raise AppException("SERVER_ERROR",
                           f"{item.get('sourceModel')} 没有字段 {subject_field}", http_status=503)

    db = get_sessionmaker()()
    try:
        base = select(model).where(model.tenant_id == tid, model.is_deleted.is_(False))
        total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        rows = db.scalars(base.limit(2000)).all()
        active_users = _active_user_ids(db, tid)

        issues: dict[str, list[dict]] = {k: [] for k in _ISSUE_TEXT}
        active_total = 0
        for row in rows:
            row_status = str(getattr(row, validity["field"], "") or "") if status_col is not None else ""
            is_active = (not active_values) or (row_status in active_values)
            if not is_active:
                issues[ISSUE_INACTIVE_OBJECT].append({"id": str(row.id), "status": row_status})
                continue
            active_total += 1
            subject = getattr(row, subject_field, None)
            legacy = getattr(row, legacy_field, None) if legacy_col is not None else None
            if subject in (None, "", 0):
                if legacy:
                    issues[ISSUE_UNSTABLE_KEY_ONLY].append({"id": str(row.id), "legacy": str(legacy)})
                else:
                    issues[ISSUE_MISSING_SUBJECT].append({"id": str(row.id)})
                continue
            if item.get("subjectKeyKind") == "USER_ID" and str(subject) not in active_users:
                issues[ISSUE_DANGLING_SUBJECT].append({"id": str(row.id), "subject": str(subject)})
            elif item.get("subjectKeyKind") == "NAME_TEXT":
                issues[ISSUE_UNSTABLE_KEY_ONLY].append({"id": str(row.id), "legacy": str(subject)})
    finally:
        db.close()

    return {
        "relationType": relation_type,
        "label": item.get("label"),
        "ownerModule": item.get("ownerModule"),
        "sourceModel": item.get("sourceModel"),
        "scanned": len(rows),
        "total": total,
        "truncated": total > len(rows),
        "activeObjects": active_total,
        "counts": {code: len(rowset) for code, rowset in issues.items()},
        "issues": [
            {"code": code, "message": _ISSUE_TEXT[code], "count": len(rowset),
             "samples": rowset[:sample_limit]}
            for code, rowset in issues.items() if rowset
        ],
    }


def list_issues(*, tenant_id: int | None = None) -> dict:
    """全部关系类型的缺口汇总。任一类型体检失败只标注该类型，不影响其他类型。"""
    tid = _tid(tenant_id)
    rows: list[dict] = []
    for item in load_registry():
        rtype = item.get("relationType")
        try:
            rows.append(inspect_relation(rtype, tenant_id=tid))
        except AppException as exc:
            rows.append({"relationType": rtype, "label": item.get("label"),
                         "ownerModule": item.get("ownerModule"),
                         "error": exc.message, "counts": {}, "issues": []})
    return {
        "list": rows,
        "total": len(rows),
        "issueTotal": sum(sum((r.get("counts") or {}).values()) for r in rows),
    }


def validate_type(relation_type: str, *, tenant_id: int | None = None) -> dict:
    """单类型的登记校验 + 数据体检，页面"校验"按钮用。"""
    registry = {r["relationType"]: r for r in validate_registry()}
    if relation_type not in registry:
        raise AppException("VALIDATION_ERROR", f"未登记的业务关系类型：{relation_type}")
    detail = registry[relation_type]
    try:
        data = inspect_relation(relation_type, tenant_id=tenant_id)
    except AppException as exc:
        data = {"error": exc.message, "counts": {}, "issues": []}
    return {"registry": detail, "data": data}
