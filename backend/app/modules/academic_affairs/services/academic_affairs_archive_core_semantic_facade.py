"""教务归档P0最终公开层：四域结构化语义门禁。

沿用现有AaArchiveBatch/AaArchiveItem和归档状态机；不新增第二套归档事实。
四域评估结果以JSON摘要写入AaArchiveItem.remark，旧数据仍可按普通文本读取。
"""
from __future__ import annotations

import json

from app.services.db_service import _tid

from . import academic_affairs_archive_textbook_facade as _base
from .academic_affairs_archive_rule_evaluator import evaluate_first_batch, normalize_legacy_result

_legacy = _base._legacy
_archive_executor = _base._archive_executor
_previous_evaluate_domains = _archive_executor._evaluate_domains


_ROUTE = {
    "STUDENT_STATUS": "/admin/academic-affairs/roster",
    "REGISTRATION": "/admin/academic-affairs/registration",
    "STATUS_CHANGE": "/admin/academic-affairs/status-changes",
    "PROGRAM": "/admin/academic-affairs/programs",
    "TEACHING_TASK": "/admin/academic-affairs/teaching-tasks",
    "SCHEDULE": "/admin/academic-affairs/scheduling",
    "SELECTION": "/admin/academic-affairs/selection/archive",
    "EXAM": "/admin/academic-affairs/exam",
    "GRADE": "/admin/academic-affairs/grade-tasks",
    "MAKEUP": "/admin/academic-affairs/makeup",
    "EVALUATION": "/admin/academic-affairs/evaluation",
    "TEXTBOOK": "/admin/academic-affairs/textbooks",
    "GRADUATION": "/admin/academic-affairs/graduation-audit",
}


def __getattr__(name):
    return getattr(_base, name)


def _public_result(code: str, result: dict) -> dict:
    normalized = normalize_legacy_result(code, result)
    normalized["route"] = normalized.get("route") or _ROUTE.get(
        code, "/admin/academic-affairs/archive/precheck"
    )
    normalized["remark"] = normalized.get("summary") or normalized.get("remark") or ""
    return normalized


def _persisted_remark(code: str, result: dict) -> str:
    normalized = _public_result(code, result)
    payload = {
        "schema": "AA_ARCHIVE_RULE_V2",
        "result": normalized["result"],
        "ruleCode": normalized["ruleCode"],
        "summary": normalized["summary"],
        "blockingCount": normalized["blockingCount"],
        "route": normalized["route"],
        "evidence": normalized["evidence"],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_persisted_remark(code: str, remark, *, present=False, record_count=0) -> dict:
    raw = str(remark or "")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict) and payload.get("schema") == "AA_ARCHIVE_RULE_V2":
        return {
            "domain": code,
            "recordCount": int(record_count or 0),
            "present": bool(present),
            "remark": payload.get("summary") or "",
            "result": payload.get("result") or ("PASS" if present else "BLOCKED"),
            "ruleCode": payload.get("ruleCode") or f"{code}_SEMANTIC_GATE",
            "summary": payload.get("summary") or "",
            "blockingCount": int(payload.get("blockingCount") or 0),
            "route": payload.get("route") or _ROUTE.get(code),
            "evidence": list(payload.get("evidence") or []),
        }
    normalized = normalize_legacy_result(code, {
        "recordCount": record_count,
        "present": present,
        "remark": raw,
        "route": _ROUTE.get(code),
    })
    return {"domain": code, **normalized}


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    previous = _previous_evaluate_domains(db, term_id, term_code, college_ids)
    results = evaluate_first_batch(
        db, term_id, term_code, previous, college_ids=college_ids,
    )
    # run_check沿用现有字段，只把结构化摘要装进remark；其它键供实时预检直接消费。
    for code, result in results.items():
        result["remark"] = _persisted_remark(code, result)
    return results


def _items_dto(db, batch_id):
    from app.models import AaArchiveItem

    rows = db.query(AaArchiveItem).filter(
        AaArchiveItem.batch_id == batch_id,
        AaArchiveItem.tenant_id == _tid(),
    ).order_by(AaArchiveItem.id).all()
    output = []
    for row in rows:
        parsed = parse_persisted_remark(
            row.domain,
            row.remark,
            present=row.present,
            record_count=row.record_count,
        )
        output.append({
            **parsed,
            "domain": row.domain,
            "domainLabel": row.domain_label,
        })
    return output


def _live_results(db, term_id, term_code, college_ids=None):
    raw = _evaluate_domains(db, term_id, term_code, college_ids)
    output = {}
    for code, result in raw.items():
        parsed = parse_persisted_remark(
            code,
            result.get("remark"),
            present=result.get("present"),
            record_count=result.get("recordCount"),
        )
        output[code] = parsed
    return output


def precheck(user, term_id=None):
    """实时预检返回结构化门禁，不落库。"""
    from app.models import AaTerm

    with _archive_executor.session() as db:
        ctx = _legacy._ctx(user, db)
        if term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == int(term_id),
                AaTerm.tenant_id == _tid(),
                AaTerm.is_deleted.is_(False),
            ).first()
            if not term:
                raise _legacy.not_found("学期不存在")
        else:
            term = db.query(AaTerm).filter(
                AaTerm.tenant_id == _tid(),
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            ).first()

        term_id_value = term.id if term else None
        term_code_value = f"{term.year_code}-{term.term_no}" if term else None
        college_ids = ctx.college_ids if ctx.scope_type == "COLLEGE" else None
        evaluated = _live_results(db, term_id_value, term_code_value, college_ids)
        domains = []
        for code, label in _legacy._DOMAINS:
            result = evaluated[code]
            domains.append({
                "domain": code,
                "domainLabel": label,
                "recordCount": result["recordCount"],
                "status": "OK" if result["result"] == "PASS" else "MISSING",
                "result": result["result"],
                "ruleCode": result["ruleCode"],
                "summary": result["summary"],
                "note": result["summary"],
                "blockingCount": result["blockingCount"],
                "route": result["route"],
                "evidence": result["evidence"],
            })
        blocking_count = sum(int(row["blockingCount"] or 0) for row in domains)
        blocked_domains = sum(1 for row in domains if row["result"] != "PASS")
        return {
            "termId": str(term_id_value) if term_id_value else None,
            "termCode": term_code_value,
            "result": "PASS" if blocked_domains == 0 else "BLOCKED",
            "blockingCount": blocking_count,
            "blockedDomains": blocked_domains,
            "scopeNote": (
                "教学任务、课表、学籍按本院范围检查；跨学院公共规则仍按其业务归属规则"
                if college_ids else None
            ),
            "domains": domains,
        }


# 归档执行器和旧批次详情均使用同一结构化规则/解析器。
_archive_executor._evaluate_domains = _evaluate_domains
_legacy._items_dto = _items_dto
