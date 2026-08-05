"""迁移期有效成绩兼容与真值修正。

- 新正式成绩继续冻结租户级版本化策略；
- 迁移前缺少策略字段的历史多次修读，明确按 LEGACY_LATEST_ATTEMPT_V1 读取并暴露治理欠账；
- 稳定课程代码优先于课程版本行 ID，避免同一门课换版本后重复计学分；
- 策略生效顺序按学期业务时间，而不是数据库自增 ID。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import event, select

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_service as _policy


def _compatible_group_strategy(rows, explicit=None):
    if explicit:
        strategy = str(explicit).upper()
    else:
        frozen = [row for row in rows if getattr(row, "effective_attempt_strategy", None)]
        if frozen:
            latest = max(frozen, key=lambda row: (_policy._base_rank(row)[0], _policy._base_rank(row)[5]))
            strategy = str(latest.effective_attempt_strategy).upper()
        elif len(rows) == 1:
            return "SINGLE_RECORD"
        else:
            strategy = "LATEST_ATTEMPT"
            _policy._LOG.warning(
                "legacy effective-grade fallback LEGACY_LATEST_ATTEMPT_V1; missing frozen policy; gradeIds=%s",
                [str(getattr(row, "id", "")) for row in rows[:20]],
            )
    if strategy not in _policy.VALID_ATTEMPT_STRATEGIES:
        raise AppException(
            "DATA_CONFLICT",
            f"不支持的有效成绩策略：{strategy}",
            http_status=409,
        )
    return strategy


def _stable_grade_identity_key(row):
    """课程代码是跨版本稳定业务身份；版本行 ID 只作为无代码时的次级身份。"""
    student_id = getattr(row, "acad_student_id", None)
    course_code = str(getattr(row, "course_code", None) or "").strip().upper()
    if course_code:
        return (student_id, "COURSE_CODE", course_code)
    course_id = getattr(row, "course_id", None)
    if course_id not in (None, ""):
        return (student_id, "COURSE_ID", str(course_id))
    return (
        student_id,
        "LEGACY_NAME_KEY",
        str(getattr(row, "id", None) or "UNPERSISTED"),
        _policy._normalize_name(getattr(row, "course_name", None)),
        str(getattr(row, "nature", None) or "").upper(),
        _policy._credit_key(getattr(row, "credit_value", None)),
    )


def _term_key(term):
    """可比较的学期业务顺序；优先正式开始日期，缺失时退回学年+学期序号。"""
    start = getattr(term, "start_date", None)
    if start is not None:
        return (2, start, "", 0, int(getattr(term, "id", 0) or 0))
    return (
        1,
        datetime.min,
        str(getattr(term, "year_code", None) or ""),
        int(getattr(term, "term_no", None) or 0),
        int(getattr(term, "id", 0) or 0),
    )


def _mapping_term_key(row):
    start = row.get("start_date")
    if start is not None:
        return (2, start, "", 0, int(row.get("id") or 0))
    return (
        1,
        datetime.min,
        str(row.get("year_code") or ""),
        int(row.get("term_no") or 0),
        int(row.get("id") or 0),
    )


def _policy_key(row, terms):
    term_id = getattr(row, "effective_from_term_id", None)
    if term_id in (None, ""):
        return (0, datetime.min, "", 0, 0)
    term = terms.get(int(term_id))
    if term is None:
        raise AppException(
            "DATA_CONFLICT",
            "有效成绩策略引用的生效学期不存在，禁止继续判定正式成绩",
            details={"policyId": str(getattr(row, "id", "")), "termId": str(term_id)},
            http_status=409,
        )
    return _term_key(term)


def _validate_policy(row):
    if str(getattr(row, "attempt_strategy", None) or "").upper() not in _policy.VALID_ATTEMPT_STRATEGIES:
        raise AppException("DATA_CONFLICT", "有效成绩策略包含不支持的attemptStrategy", http_status=409)
    return row


def _chronological_resolve_active_policy(db, term_id=None, *, required=True):
    from app.models import AaTerm
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    tenant_id = _policy._tid()
    rows = db.query(AaEffectiveGradePolicy).filter(
        AaEffectiveGradePolicy.tenant_id == tenant_id,
        AaEffectiveGradePolicy.status == "ACTIVE",
        AaEffectiveGradePolicy.is_deleted.is_(False),
    ).all()
    term_ids = {int(row.effective_from_term_id) for row in rows if row.effective_from_term_id}
    if term_id:
        term_ids.add(int(term_id))
    terms = {
        int(row.id): row
        for row in db.query(AaTerm).filter(
            AaTerm.tenant_id == tenant_id,
            AaTerm.id.in_(sorted(term_ids) or [-1]),
            AaTerm.is_deleted.is_(False),
        ).all()
    }
    target = terms.get(int(term_id)) if term_id else None
    if term_id and target is None:
        raise AppException("DATA_CONFLICT", "成绩业务引用的正式学期不存在", http_status=409)
    target_key = _term_key(target) if target is not None else None
    eligible = [
        row for row in rows
        if row.effective_from_term_id is None
        or target_key is None
        or _policy_key(row, terms) <= target_key
    ]
    if not eligible:
        if required:
            raise AppException(
                "DATA_CONFLICT",
                "当前租户未配置该学期可用的有效成绩策略，禁止发布或更正正式成绩",
                http_status=409,
            )
        return None
    eligible.sort(
        key=lambda row: (_policy_key(row, terms), int(row.policy_version or 1), int(row.id or 0)),
        reverse=True,
    )
    first = _validate_policy(eligible[0])
    if len(eligible) > 1 and eligible[1].effective_from_term_id == first.effective_from_term_id:
        raise AppException("DATA_CONFLICT", "同一生效学期存在多条有效成绩策略", http_status=409)
    return first


_original_policy_payload = _policy.policy_payload


def _stable_policy_payload(source=None):
    payload = _original_policy_payload(source)
    payload["identityOrder"] = ["COURSE_CODE", "COURSE_ID", "LEGACY_NAME_KEY"]
    return payload


def _term_code(row) -> str:
    return f"{str(row.get('year_code') or '').strip()}-{int(row.get('term_no') or 0)}"


def _chronological_before_grade_insert(_mapper, connection, target) -> None:
    """ORM兜底写入也按成绩所属学期选策略；无法证明学期时只允许租户基础策略。"""
    if not getattr(target, "tenant_id", None) or getattr(target, "effective_attempt_strategy", None):
        return

    from app.models import AaTerm
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    tenant_id = int(target.tenant_id)
    policy_table = AaEffectiveGradePolicy.__table__
    term_table = AaTerm.__table__
    policies = connection.execute(select(policy_table).where(
        policy_table.c.tenant_id == tenant_id,
        policy_table.c.status == "ACTIVE",
        policy_table.c.is_deleted.is_(False),
    )).mappings().all()
    if not policies:
        return

    term_ids = {int(row["effective_from_term_id"]) for row in policies if row["effective_from_term_id"]}
    # 必须读取租户全部正式学期，成绩可能落在两个策略边界之间的普通学期。
    term_rows = connection.execute(select(term_table).where(
        term_table.c.tenant_id == tenant_id,
        term_table.c.is_deleted.is_(False),
    )).mappings().all()
    terms = {int(row["id"]): row for row in term_rows}
    missing_term_refs = sorted(term_ids - set(terms))
    if missing_term_refs:
        raise AppException(
            "DATA_CONFLICT",
            "有效成绩策略引用的生效学期不存在，禁止写入正式成绩",
            details={"termIds": [str(value) for value in missing_term_refs]},
            http_status=409,
        )

    term_text = str(getattr(target, "term", None) or "").strip()
    target_term = None
    if term_text:
        matches = [
            row for row in term_rows
            if term_text == str(row.get("term_name") or "").strip() or term_text == _term_code(row)
        ]
        if len(matches) > 1:
            raise AppException("DATA_CONFLICT", "成绩学期文本对应多条正式学期，禁止猜测策略", http_status=409)
        target_term = matches[0] if matches else None

    if target_term is None:
        eligible = [row for row in policies if row["effective_from_term_id"] is None]
    else:
        target_key = _mapping_term_key(target_term)
        eligible = [
            row for row in policies
            if row["effective_from_term_id"] is None
            or _mapping_term_key(terms[int(row["effective_from_term_id"])]) <= target_key
        ]
    if not eligible:
        return
    eligible.sort(
        key=lambda row: (
            (0, datetime.min, "", 0, 0)
            if row["effective_from_term_id"] is None
            else _mapping_term_key(terms[int(row["effective_from_term_id"])]),
            int(row["policy_version"] or 1),
            int(row["id"] or 0),
        ),
        reverse=True,
    )
    first = eligible[0]
    strategy = str(first["attempt_strategy"] or "").upper()
    if strategy not in _policy.VALID_ATTEMPT_STRATEGIES:
        raise AppException("DATA_CONFLICT", "有效成绩策略包含不支持的attemptStrategy", http_status=409)
    target.effective_policy_code = first["policy_code"]
    target.effective_policy_version = first["policy_version"]
    target.effective_attempt_strategy = strategy


_policy._group_strategy = _compatible_group_strategy
_policy.grade_identity_key = _stable_grade_identity_key
_policy.resolve_active_policy = _chronological_resolve_active_policy
_policy.policy_payload = _stable_policy_payload

# 原监听器用数据库ID排序生效学期；替换为业务学期顺序，after_insert快照监听器继续复用。
from app.models.academic import AcademicGrade  # noqa: E402
from app.models import academic_affairs_effective_grade as _grade_model  # noqa: E402

if event.contains(AcademicGrade, "before_insert", _grade_model._before_grade_insert):
    event.remove(AcademicGrade, "before_insert", _grade_model._before_grade_insert)
if not event.contains(AcademicGrade, "before_insert", _chronological_before_grade_insert):
    event.listen(AcademicGrade, "before_insert", _chronological_before_grade_insert)
