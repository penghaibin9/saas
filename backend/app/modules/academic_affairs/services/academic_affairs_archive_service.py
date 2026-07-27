"""教务归档唯一公开 Service。

- 归档批次、确认封存、解冻、导出和审计复用 ``academic_affairs_archive_core_service``；
- 十三域语义规则只由纯策略模块编排；
- 不修改其它模块函数，不依赖 Facade 导入顺序，不建立第二套归档事实。
"""
from __future__ import annotations

import json
from datetime import datetime

from app.services.db_service import _tid

from . import academic_affairs_archive_core_service as _core
from . import academic_affairs_archive_domain_policy as _policy
from . import academic_affairs_archive_operational_policy as _operational

_DOMAINS = list(_policy.DOMAINS)
_ROUTE = dict(_policy.ROUTES)


def __getattr__(name):
    """未重写的批次、封存、解冻和导出能力显式复用稳定 core。"""
    return getattr(_core, name)


def _merge_blocking_result(code: str, base: dict, extra: dict, *, rule_code: str) -> dict:
    left = _public_result(code, base)
    right = _public_result(code, extra)
    if right["result"] == "PASS":
        left["evidence"] = [
            *left["evidence"],
            {"type": rule_code, "result": "PASS", "summary": right["summary"]},
        ]
        return left
    left["present"] = False
    left["result"] = "BLOCKED"
    left["ruleCode"] = rule_code
    left["blockingCount"] = int(left["blockingCount"] or 0) + max(1, int(right["blockingCount"] or 0))
    left["summary"] = "；".join(value for value in (left["summary"], right["summary"]) if value)
    left["remark"] = left["summary"]
    left["route"] = right["route"] or left["route"]
    left["evidence"] = [
        *left["evidence"],
        {"type": rule_code, "result": "BLOCKED", "summary": right["summary"]},
        *right["evidence"],
    ]
    return left


def _evaluate_domains(db, term_id, term_code, college_ids=None):
    results = _policy.evaluate_domains(db, term_id, term_code, college_ids)
    schedule_operational = _operational.evaluate_schedule(db, term_id, college_ids)
    results["SCHEDULE"] = _merge_blocking_result(
        "SCHEDULE",
        results["SCHEDULE"],
        schedule_operational,
        rule_code="SCHEDULE_OPERATIONAL_CLOSURE",
    )
    results["EXAM"] = _public_result(
        "EXAM",
        _operational.evaluate_exam(db, term_id),
    )
    return results


def _public_result(code: str, result: dict) -> dict:
    row = dict(result or {})
    row["domain"] = code
    row["recordCount"] = int(row.get("recordCount") or 0)
    row["present"] = bool(row.get("present"))
    row["result"] = row.get("result") or ("PASS" if row["present"] else "BLOCKED")
    row["ruleCode"] = row.get("ruleCode") or f"{code}_SEMANTIC_GATE"
    row["summary"] = str(row.get("summary") or row.get("remark") or "")
    row["remark"] = row["summary"]
    row["blockingCount"] = int(row.get("blockingCount") or (0 if row["present"] else 1))
    row["route"] = row.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck")
    row["evidence"] = list(row.get("evidence") or [])
    return row


def _persisted_remark(code: str, result: dict) -> str:
    """AaArchiveItem.remark 只有300字符，只保存可稳定回显的紧凑摘要。"""
    row = _public_result(code, result)
    summary = row["summary"][:150]
    payload = {
        "v": 2,
        "r": row["result"],
        "c": str(row["ruleCode"] or "")[:70],
        "b": int(row["blockingCount"] or 0),
        "s": summary,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded) <= 300:
        return encoded
    payload["s"] = summary[:80]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))[:300]


def parse_persisted_remark(code: str, remark, *, present=False, record_count=0) -> dict:
    raw = str(remark or "")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        payload = None
    if isinstance(payload, dict) and payload.get("v") == 2:
        summary = str(payload.get("s") or "")
        return _public_result(code, {
            "recordCount": record_count,
            "present": present,
            "remark": summary,
            "result": payload.get("r"),
            "ruleCode": payload.get("c"),
            "summary": summary,
            "blockingCount": payload.get("b"),
            "route": _ROUTE.get(code),
            "evidence": [],
        })
    if isinstance(payload, dict) and payload.get("schema") == "AA_ARCHIVE_RULE_V2":
        return _public_result(code, {
            "recordCount": record_count,
            "present": present,
            "remark": payload.get("summary"),
            "result": payload.get("result"),
            "ruleCode": payload.get("ruleCode"),
            "summary": payload.get("summary"),
            "blockingCount": payload.get("blockingCount"),
            "route": payload.get("route") or _ROUTE.get(code),
            "evidence": payload.get("evidence") or [],
        })
    return _public_result(code, {
        "recordCount": record_count,
        "present": present,
        "remark": raw,
        "route": _ROUTE.get(code),
    })


def _items_dto(db, batch_id):
    from app.models import AaArchiveItem

    rows = db.query(AaArchiveItem).filter(
        AaArchiveItem.batch_id == int(batch_id),
        AaArchiveItem.tenant_id == _tid(),
    ).order_by(AaArchiveItem.id).all()
    return [{
        **parse_persisted_remark(
            row.domain,
            row.remark,
            present=row.present,
            record_count=row.record_count,
        ),
        "domain": row.domain,
        "domainLabel": row.domain_label,
    } for row in rows]


def get_batch(user, batch_id):
    with _core.session() as db:
        _core._ctx(user, db)
        batch = _core._get_batch(db, int(batch_id))
        return _core._batch_dto(batch, items=_items_dto(db, batch.id))


def run_check(user, batch_id):
    """十三域实时检查后持久化紧凑摘要；完整证据只由precheck实时返回。"""
    from app.models import AaArchiveItem

    with _core.session() as db:
        _core._require_school(_core._ctx(user, db))
        batch = _core._get_batch(db, int(batch_id))
        if batch.status in {"ARCHIVED", "CANCELLED"}:
            raise _core._invalid("已归档/已取消批次不可再检查")

        results = _evaluate_domains(db, batch.term_id, batch.term_code)
        db.query(AaArchiveItem).filter(
            AaArchiveItem.batch_id == batch.id,
            AaArchiveItem.tenant_id == _tid(),
        ).delete(synchronize_session=False)

        blocked_domains = 0
        blocking_count = 0
        for code, label in _DOMAINS:
            result = _public_result(code, results[code])
            if result["result"] != "PASS":
                blocked_domains += 1
            blocking_count += int(result["blockingCount"] or 0)
            db.add(AaArchiveItem(
                tenant_id=_tid(),
                batch_id=batch.id,
                domain=code,
                domain_label=label,
                record_count=result["recordCount"],
                present=result["result"] == "PASS",
                remark=_persisted_remark(code, result),
            ))

        batch.missing_count = blocked_domains
        batch.checked_at = datetime.utcnow()
        batch.status = "READY" if blocked_domains == 0 else "MISSING_ITEMS"
        _core._audit(
            db,
            batch.id,
            "ARCHIVE_CHECK_V2",
            f"十三域语义检查 blockedDomains={blocked_domains};blockingCount={blocking_count}",
        )
        db.commit()
        return _core._batch_dto(batch, items=_items_dto(db, batch.id))


def precheck(user, term_id=None):
    """实时预检返回十三域结构化规则、下钻地址和证据，不写数据库。"""
    from app.models import AaTerm

    with _core.session() as db:
        ctx = _core._ctx(user, db)
        if term_id:
            term = db.query(AaTerm).filter(
                AaTerm.id == int(term_id),
                AaTerm.tenant_id == _tid(),
                AaTerm.is_deleted.is_(False),
            ).first()
            if not term:
                raise _core.not_found("学期不存在")
        else:
            term = db.query(AaTerm).filter(
                AaTerm.tenant_id == _tid(),
                AaTerm.is_current.is_(True),
                AaTerm.is_deleted.is_(False),
            ).first()

        term_id_value = term.id if term else None
        term_code_value = f"{term.year_code}-{term.term_no}" if term else None
        college_ids = ctx.college_ids if ctx.scope_type == "COLLEGE" else None
        evaluated = _evaluate_domains(db, term_id_value, term_code_value, college_ids)
        domains = []
        for code, label in _DOMAINS:
            result = _public_result(code, evaluated[code])
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
                "教学任务、课表、学籍按本院范围检查；跨学院公共规则按业务归属核验"
                if college_ids else None
            ),
            "domains": domains,
        }


def _count_one_domain(db, code, term_id, term_code, college_ids=None):
    return int(_evaluate_domains(db, term_id, term_code, college_ids).get(code, {}).get("recordCount") or 0)


def _count_domains(db, term_id, term_code):
    return {
        code: int(result.get("recordCount") or 0)
        for code, result in _evaluate_domains(db, term_id, term_code).items()
    }
