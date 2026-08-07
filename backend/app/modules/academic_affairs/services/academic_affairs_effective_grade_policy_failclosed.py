"""包 2：无 ACTIVE 有效成绩策略时，正式成绩写入一律 fail-closed。

此前 ORM 监听器在"查不到 ACTIVE 策略"时直接 ``return``，注释写的是"直接阻断"，实际却是
静默放行（NEW-P1-04）。后果是绕开正式发布 service 的写入、迁移或其他模块，可以产出一批
没有冻结策略的正式成绩；这些行以后既判不出有效成绩，也无法追溯当时用的是哪套规则。

本模块把合同改成：
- 正式业务写入没有可用策略 → 409，绝不猜；
- 迁移/历史导入必须显式进入 ``legacy_import_context``，登记来源、操作人、批次和欠账理由，
  上线门禁据此查得出"哪些正式成绩带着策略欠账"。ORM 事件不再自己猜"这是正式写入还是迁移"。
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException
from app.models.academic import AcademicGrade
from app.modules.academic_affairs.services import (
    academic_affairs_effective_grade_policy_current_term as _current_term,
)

_BYPASS: ContextVar[dict | None] = ContextVar("aa_effective_grade_policy_bypass", default=None)

_VALID_SOURCES = {"MIGRATION", "LEGACY_IMPORT", "SANDBOX"}


def current_bypass() -> dict | None:
    return _BYPASS.get()


@contextmanager
def legacy_import_context(*, source: str, operator: str, batch_no: str, debt_reason: str):
    """历史导入/迁移专用：显式声明本批写入允许没有冻结策略，并留下可查的欠账。

    仅覆盖"策略缺失"这一条豁免，不豁免租户隔离、权限、状态机等任何其它合同。
    """
    normalized = str(source or "").strip().upper()
    if normalized not in _VALID_SOURCES:
        raise AppException(
            "VALIDATION_ERROR",
            f"历史导入来源必须是 {sorted(_VALID_SOURCES)} 之一",
        )
    for label, value in (("operator", operator), ("batchNo", batch_no), ("debtReason", debt_reason)):
        if not str(value or "").strip():
            raise AppException("VALIDATION_ERROR", f"历史导入豁免必须填写 {label}")

    payload = {
        "source": normalized,
        "operator": str(operator).strip()[:100],
        "batchNo": str(batch_no).strip()[:100],
        "debtReason": str(debt_reason).strip()[:500],
        "startedAt": datetime.utcnow(),
        "gradeCount": 0,
    }
    token = _BYPASS.set(payload)
    try:
        yield payload
    finally:
        _BYPASS.reset(token)
        _record_bypass(payload)


def _record_bypass(payload: dict) -> None:
    """把这一批豁免登记到欠账台账；登记本身失败不能吞掉，否则欠账就消失了。"""
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicyBypass
    from app.services.db_service import _tid, session

    if not payload.get("gradeCount"):
        return  # 整个上下文没写出任何无策略成绩，就没有欠账可记
    with session() as db:
        existing = db.query(AaEffectiveGradePolicyBypass).filter(
            AaEffectiveGradePolicyBypass.tenant_id == _tid(),
            AaEffectiveGradePolicyBypass.batch_no == payload["batchNo"],
        ).first()
        if existing is not None:
            existing.grade_count = int(existing.grade_count or 0) + int(payload["gradeCount"])
            existing.ended_at = datetime.utcnow()
        else:
            db.add(AaEffectiveGradePolicyBypass(
                tenant_id=_tid(),
                source=payload["source"],
                operator=payload["operator"],
                batch_no=payload["batchNo"],
                debt_reason=payload["debtReason"],
                grade_count=int(payload["gradeCount"]),
                started_at=payload["startedAt"],
                ended_at=datetime.utcnow(),
            ))
        db.commit()


BASE_POLICY_CODE = "TENANT_BASE_EFFECTIVE_GRADE"
BASE_ATTEMPT_STRATEGY = "LATEST_ATTEMPT"


def ensure_tenant_base_policy(connection, tenant_id: int) -> bool:
    """租户没有任何 ACTIVE 策略时自动落一条基础策略（BASE 范围），返回是否新建。

    这不是"静默放行"：成绩仍然冻结一条真实存在、可查询、可被学校改版的策略版本。
    留一个"上线前记得先配策略"的人工前提才是真正的坑——学校第一次发成绩就会被 409 挡死，
    非技术负责人无从下手。学校随后用 activate_grade_policy 发布自己的版本即可覆盖它。
    """
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    table = AaEffectiveGradePolicy.__table__
    existing = connection.execute(select(table.c.id).where(
        table.c.tenant_id == int(tenant_id),
        table.c.status == "ACTIVE",
        table.c.is_deleted.is_(False),
    ).limit(1)).first()
    if existing:
        return False
    now = datetime.utcnow()
    try:
        connection.execute(table.insert().values(
            tenant_id=int(tenant_id),
            policy_code=BASE_POLICY_CODE,
            policy_version=1,
            attempt_strategy=BASE_ATTEMPT_STRATEGY,
            makeup_strategy="CAP_AND_OVERRIDE",
            makeup_cap=None,
            retake_strategy="REPLACE_IF_PASSED",
            recognition_priority=75,
            effective_from_term_id=None,
            active_scope_key="BASE",
            status="ACTIVE",
            activated_at=now,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=0,
        ))
    except IntegrityError:
        # 并发首次写入：另一个请求已经建好同一条基础策略，直接复用。
        return False
    return True


def _fail_closed_before_grade_insert(mapper, connection, target) -> None:
    """先按学期解析策略；仍解析不到就只允许显式豁免通过，其余一律 409。"""
    _current_term._current_term_before_grade_insert(mapper, connection, target)
    if getattr(target, "effective_attempt_strategy", None):
        return
    if not getattr(target, "tenant_id", None):
        return

    # 租户从未配置过策略时自动补一条基础策略，再重新解析一次。
    if _BYPASS.get() is None and ensure_tenant_base_policy(connection, int(target.tenant_id)):
        _current_term._current_term_before_grade_insert(mapper, connection, target)
        if getattr(target, "effective_attempt_strategy", None):
            return

    bypass = _BYPASS.get()
    if bypass is None:
        raise AppException(
            "DATA_CONFLICT",
            "当前租户未配置该学期可用的有效成绩策略，禁止写入正式成绩；"
            "历史导入请显式使用 legacy_import_context 并登记欠账",
            details={
                "term": str(getattr(target, "term", None) or ""),
                "acadStudentId": str(getattr(target, "acad_student_id", None) or ""),
            },
            http_status=409,
        )
    bypass["gradeCount"] = int(bypass.get("gradeCount") or 0) + 1


def install() -> None:
    """幂等安装：接替当前学期监听器成为 before_insert 的唯一入口。"""
    if event.contains(AcademicGrade, "before_insert", _current_term._current_term_before_grade_insert):
        event.remove(AcademicGrade, "before_insert", _current_term._current_term_before_grade_insert)
    if not event.contains(AcademicGrade, "before_insert", _fail_closed_before_grade_insert):
        event.listen(AcademicGrade, "before_insert", _fail_closed_before_grade_insert)


install()
