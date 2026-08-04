"""PLAT-10 问题管理、已知错误与事故复盘。

不重复实现：来源事件的判定权威仍是 PLAT-09（这里只存一个 source_incident_id
引用，不复制事件字段）；永久修复的变更流程权威仍是 PLAT-11（这里只存
permanent_fix_change_id 引用，链接前用 change_management_service.get_change
校验这个变更确实存在，不接受挂空引用）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.problem_management import Problem, ProblemPostmortem

STATUS_ORDER = ("OPEN", "INVESTIGATING", "KNOWN_ERROR", "RESOLVED", "CLOSED")
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "OPEN": frozenset({"INVESTIGATING", "KNOWN_ERROR"}),
    "INVESTIGATING": frozenset({"KNOWN_ERROR", "RESOLVED"}),
    "KNOWN_ERROR": frozenset({"INVESTIGATING", "RESOLVED"}),
    "RESOLVED": frozenset({"CLOSED", "INVESTIGATING"}),
    "CLOSED": frozenset(),
}


def _now() -> datetime:
    return datetime.utcnow()


def _session():
    return get_sessionmaker()()


def _actor_id(user: dict | None = None) -> int | None:
    u = user or get_current_user_ctx() or {}
    uid = u.get("userId")
    try:
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


def _problem_dto(row: Problem) -> dict:
    return {
        "id": str(row.id), "title": row.title, "status": row.status,
        "rootCause": row.root_cause or "", "workaround": row.workaround or "",
        "sourceIncidentId": str(row.source_incident_id) if row.source_incident_id else None,
        "permanentFixChangeId": str(row.permanent_fix_change_id) if row.permanent_fix_change_id else None,
        "knownErrorPublished": bool(row.known_error_published),
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "version": int(row.version or 0),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def create_problem(*, title: str, source_incident_id: int | None = None,
                   root_cause: str = "", workaround: str = "") -> dict:
    title = str(title or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "问题标题不能为空")
    with _session() as db:
        row = Problem(title=title, status="OPEN",
                     source_incident_id=int(source_incident_id) if source_incident_id else None,
                     root_cause=root_cause or None, workaround=workaround or None)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _problem_dto(row)


def create_problem_from_incident(incident_id: int, *, title: str) -> dict:
    """幂等：同一个事件重复申请转 Problem，不产生第二条 Problem。"""
    with _session() as db:
        existing = db.scalars(select(Problem).where(
            Problem.source_incident_id == int(incident_id), Problem.is_deleted.is_(False))).first()
        if existing is not None:
            return _problem_dto(existing)
        row = Problem(title=title or f"事件 #{incident_id} 转问题", status="OPEN",
                     source_incident_id=int(incident_id))
        db.add(row)
        db.commit()
        db.refresh(row)
        return _problem_dto(row)


def list_problems(*, status: str | None = None) -> list[dict]:
    with _session() as db:
        q = select(Problem).where(Problem.is_deleted.is_(False))
        if status:
            q = q.where(Problem.status == status)
        rows = db.scalars(q.order_by(Problem.id.desc())).all()
        return [_problem_dto(r) for r in rows]


def get_problem(problem_id: int) -> dict:
    with _session() as db:
        row = db.get(Problem, int(problem_id))
        if row is None or row.is_deleted:
            raise not_found("问题不存在")
        dto = _problem_dto(row)
        postmortems = db.scalars(select(ProblemPostmortem).where(
            ProblemPostmortem.problem_id == row.id, ProblemPostmortem.is_deleted.is_(False)
        ).order_by(ProblemPostmortem.id.desc())).all()
        dto["postmortems"] = [_postmortem_dto(p) for p in postmortems]
        return dto


def update_root_cause(problem_id: int, *, root_cause: str, workaround: str = "",
                      expected_version: int) -> dict:
    with _session() as db:
        row = db.get(Problem, int(problem_id))
        if row is None or row.is_deleted:
            raise not_found("问题不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "问题已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        row.root_cause = root_cause
        if workaround:
            row.workaround = workaround
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _problem_dto(row)


def transition_status(problem_id: int, *, target_status: str, expected_version: int) -> dict:
    target = str(target_status or "").upper()
    if target not in STATUS_ORDER:
        raise AppException("VALIDATION_ERROR", f"不支持的问题状态：{target}")
    with _session() as db:
        row = db.get(Problem, int(problem_id))
        if row is None or row.is_deleted:
            raise not_found("问题不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "问题已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        current = row.status
        if target == current:
            return _problem_dto(row)
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise AppException("STATE_TRANSITION_DENIED", f"不允许从 {current} 变更为 {target}",
                               http_status=409, details={"allowed": sorted(ALLOWED_TRANSITIONS.get(current, frozenset()))})
        if target == "KNOWN_ERROR" and not (row.workaround or "").strip():
            raise AppException("VALIDATION_ERROR", "标记为已知错误前必须填写临时规避方案")
        row.status = target
        row.version = int(row.version or 0) + 1
        if target == "KNOWN_ERROR":
            row.known_error_published = True
        if target == "RESOLVED":
            row.resolved_at = _now()
        if target == "CLOSED":
            row.closed_at = _now()
        db.commit()
        db.refresh(row)
        return _problem_dto(row)


def link_permanent_fix(problem_id: int, *, change_id: int, expected_version: int) -> dict:
    from app.core.exceptions import AppException as _AppException
    from app.services import change_management_service as chg

    try:
        chg.get_change(int(change_id))
    except _AppException:
        raise AppException("DATA_NOT_FOUND", f"变更不存在：{change_id}", http_status=404) from None

    with _session() as db:
        row = db.get(Problem, int(problem_id))
        if row is None or row.is_deleted:
            raise not_found("问题不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "问题已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        row.permanent_fix_change_id = int(change_id)
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _problem_dto(row)


def _postmortem_dto(row: ProblemPostmortem) -> dict:
    return {
        "id": str(row.id), "problemId": str(row.problem_id),
        "whatHappened": row.what_happened or "", "timeline": row.timeline_json or [],
        "impactSummary": row.impact_summary or "", "actionItems": row.action_items_json or [],
        "published": bool(row.published),
        "publishedAt": row.published_at.isoformat() if row.published_at else None,
        "authorUserId": str(row.author_user_id) if row.author_user_id else None,
        "version": int(row.version or 0),
    }


def create_postmortem(problem_id: int, *, what_happened: str = "", timeline: list | None = None,
                      impact_summary: str = "", action_items: list | None = None,
                      user: dict | None = None) -> dict:
    with _session() as db:
        problem = db.get(Problem, int(problem_id))
        if problem is None or problem.is_deleted:
            raise not_found("问题不存在")
        row = ProblemPostmortem(
            problem_id=int(problem_id), what_happened=what_happened or None,
            timeline_json=timeline or [], impact_summary=impact_summary or None,
            action_items_json=action_items or [], published=False,
            author_user_id=_actor_id(user))
        db.add(row)
        db.commit()
        db.refresh(row)
        return _postmortem_dto(row)


def publish_postmortem(postmortem_id: int, *, expected_version: int) -> dict:
    with _session() as db:
        row = db.get(ProblemPostmortem, int(postmortem_id))
        if row is None or row.is_deleted:
            raise not_found("复盘记录不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "复盘记录已被修改，请刷新后重试", http_status=409,
                               details={"currentVersion": int(row.version or 0)})
        problem = db.get(Problem, row.problem_id)
        if problem is None or problem.status not in ("RESOLVED", "CLOSED"):
            raise AppException("DATA_CONFLICT", "问题尚未解决前不能发布复盘", http_status=409)
        if not (row.what_happened or "").strip() or not (row.action_items_json or []):
            raise AppException("VALIDATION_ERROR", "复盘发布前必须填写经过说明与至少一项行动项")
        row.published = True
        row.published_at = _now()
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _postmortem_dto(row)


def governance_overview() -> dict:
    with _session() as db:
        problems = db.scalars(select(Problem).where(Problem.is_deleted.is_(False))).all()
        open_problems = [p for p in problems if p.status not in ("RESOLVED", "CLOSED")]
        known_errors = [p for p in problems if p.known_error_published]
        without_root_cause = [p for p in open_problems if not (p.root_cause or "").strip()]
        now = _now()
        aging = [p for p in open_problems if p.created_at and (now - p.created_at).days > 30]
        without_fix_link = [p for p in problems if p.status == "RESOLVED" and not p.permanent_fix_change_id]
        return {
            "totalCount": len(problems),
            "openCount": len(open_problems),
            "knownErrorCount": len(known_errors),
            "withoutRootCauseCount": len(without_root_cause),
            "agingOpenCount": len(aging),
            "resolvedWithoutFixLinkCount": len(without_fix_link),
        }
