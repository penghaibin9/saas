"""学生主档正式服务。

A2 / P0-02 + P0-03：
- 正式 `/students` 链路必须使用真实数据库；DB 不可用时 fail-closed，禁止回落内存学生。
- 身份核验、账号绑定、主档完整度都来自明确事实；缺事实返回 UNKNOWN/NOT_CONFIGURED，
  绝不补 VERIFIED / BOUND / 固定 90%。
- 学生主档写入继续复用 db_service 的事务、乐观锁、审计与学籍异动边界。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.db.session import db_enabled

IDENTITY_CAPABILITY_STATUS = "NOT_CONFIGURED"
COMPLETENESS_DEFINITION = "CORE_PROFILE_V1"


def _require_db() -> None:
    if not db_enabled():
        raise AppException(
            "STUDENT_BACKEND_UNAVAILABLE",
            "学生主档必须使用真实数据库，当前不可返回内存演示数据",
            http_status=503,
        )


def _supported_actions() -> list[str]:
    user = get_current_user_ctx() or {}
    result: list[str] = []
    if has_permission(user, "*") or has_permission(user, "student.profile.view"):
        result.append("VIEW")
    if has_permission(user, "*") or has_permission(user, "student.profile.manage") or has_permission(user, "student.profile.update"):
        result.extend(["EDIT_IDENTITY", "VOID"])
    if has_permission(user, "*") or has_permission(user, "student.profile.create") or has_permission(user, "student.profile.manage"):
        result.append("CREATE")
    if has_permission(user, "*") or has_permission(user, "student.profile.restore"):
        result.append("RESTORE")
    if has_permission(user, "*") or has_permission(user, "student.export"):
        result.append("EXPORT")
    return sorted(set(result))


def _fact_map(student_ids: list[int]) -> dict[int, dict]:
    if not student_ids:
        return {}
    from app.models import StudentContact, StudentProfile
    from app.models.student_account_link import LINK_ACTIVE, LINK_SUSPENDED, StudentAccountLink
    from app.services import db_service

    tenant_id = db_service._tid()
    with db_service.session() as db:
        profiles = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.id.in_(student_ids),
        )).all()
        contacts = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == tenant_id,
            StudentContact.student_id.in_(student_ids),
            StudentContact.contact_type == "PHONE",
            StudentContact.is_deleted.is_(False),
        ).order_by(StudentContact.is_primary.desc(), StudentContact.id)).all()
        links = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.student_id.in_(student_ids),
            StudentAccountLink.is_deleted.is_(False),
        )).all()

    phone_present: set[int] = set()
    for contact in contacts:
        if contact.contact_value_encrypted or contact.contact_value_hash:
            phone_present.add(int(contact.student_id))

    link_status: dict[int, str] = {}
    for link in links:
        sid = int(link.student_id)
        status = str(link.link_status or "").upper()
        if status == LINK_ACTIVE:
            link_status[sid] = "BOUND"
        elif status == LINK_SUSPENDED and link_status.get(sid) != "BOUND":
            link_status[sid] = "SUSPENDED"

    actions = _supported_actions()
    facts: dict[int, dict] = {}
    for profile in profiles:
        sid = int(profile.id)
        required = {
            "studentNo": profile.student_no,
            "realName": profile.real_name,
            "gender": profile.gender,
            "collegeId": profile.college_id,
            "majorId": profile.major_id,
            "classId": profile.class_id,
            "grade": profile.grade,
            "phone": sid in phone_present,
            "idCard": bool(profile.id_card_encrypted or profile.id_card_hash),
        }
        missing = [key for key, value in required.items() if value is None or value is False or str(value).strip() == ""]
        completeness = round((len(required) - len(missing)) * 100 / len(required))
        facts[sid] = {
            "identityVerifyStatus": IDENTITY_CAPABILITY_STATUS,
            "identityVerificationCapability": {
                "status": IDENTITY_CAPABILITY_STATUS,
                "provider": None,
                "message": "第三方实名/人脸核验服务当前未配置；新生人工信息核验使用数字迎新。",
            },
            "accountBindStatus": link_status.get(sid, "UNBOUND"),
            "dataCompleteness": completeness,
            "missingFields": missing,
            "completenessDefinition": COMPLETENESS_DEFINITION,
            "supportedActions": actions,
            "dataQualityStatus": profile.data_quality_status or "UNKNOWN",
            "phoneRegistered": sid in phone_present,
        }
    return facts


def _enrich(rows: list[dict]) -> list[dict]:
    ids = [int(row.get("id") or row.get("studentId")) for row in rows if str(row.get("id") or row.get("studentId") or "").isdigit()]
    facts = _fact_map(ids)
    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        raw_id = str(item.get("id") or item.get("studentId") or "")
        fact = facts.get(int(raw_id)) if raw_id.isdigit() else None
        if fact:
            item.update(fact)
            if not fact.get("phoneRegistered"):
                item["phoneMasked"] = ""
        else:
            item.update({
                "identityVerifyStatus": "UNKNOWN",
                "accountBindStatus": "UNKNOWN",
                "dataCompleteness": None,
                "missingFields": [],
                "completenessDefinition": COMPLETENESS_DEFINITION,
                "supportedActions": [],
                "dataQualityStatus": "UNKNOWN",
            })
        item.pop("phoneRegistered", None)
        enriched.append(item)
    return enriched


def _scope_conditions(model, class_ids=None, student_ids=None):
    conditions = []
    if student_ids is not None:
        ids = [int(x) for x in student_ids if str(x).isdigit()]
        conditions.append(model.id.in_(ids) if ids else model.id == -1)
    elif class_ids is not None:
        ids = [int(x) for x in class_ids if str(x).isdigit()]
        conditions.append(model.class_id.in_(ids) if ids else model.id == -1)
    return conditions


def summary(*, class_ids=None, student_ids=None) -> dict:
    """学生中心权威摘要：只做数据库聚合，不读取浏览器/fixture。"""
    _require_db()
    from app.models import StudentProfile
    from app.models.student_account_link import LINK_ACTIVE, LINK_SUSPENDED, StudentAccountLink
    from app.services import db_service

    tenant_id = db_service._tid()
    scope_cond = _scope_conditions(StudentProfile, class_ids, student_ids)
    with db_service.session() as db:
        total = int(db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
            *scope_cond,
        )) or 0)
        visible_ids = select(StudentProfile.id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
            *scope_cond,
        )
        bound = int(db.scalar(select(func.count(func.distinct(StudentAccountLink.student_id))).where(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.is_deleted.is_(False),
            StudentAccountLink.link_status == LINK_ACTIVE,
            StudentAccountLink.student_id.in_(visible_ids),
        )) or 0)
        suspended = int(db.scalar(select(func.count(func.distinct(StudentAccountLink.student_id))).where(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.is_deleted.is_(False),
            StudentAccountLink.link_status == LINK_SUSPENDED,
            StudentAccountLink.student_id.in_(visible_ids),
        )) or 0)

    scope_type = "STUDENT" if student_ids is not None else "CLASS" if class_ids is not None else "TENANT"
    return {
        "totalStudents": total,
        "accountBinding": {
            "bound": bound,
            "suspended": suspended,
            "unbound": max(0, total - bound - suspended),
        },
        "identityVerification": {
            "status": IDENTITY_CAPABILITY_STATUS,
            "provider": None,
            "verified": None,
            "pending": None,
            "abnormal": None,
        },
        "completenessDefinition": COMPLETENESS_DEFINITION,
        "supportedActions": _supported_actions(),
        "scopeType": scope_type,
        "asOf": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "qualityFlags": ["IDENTITY_VERIFICATION_NOT_CONFIGURED"],
    }


def list_students(
    page: int,
    page_size: int,
    keyword: Optional[str] = None,
    college: Optional[str] = None,
    major: Optional[str] = None,
    class_name: Optional[str] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    class_ids=None,
    student_ids=None,
) -> tuple[list[dict], int]:
    _require_db()
    from app.services import db_service

    rows, total = db_service.list_students(
        page, page_size, keyword, college, major, class_name, status, risk_level,
        class_ids=class_ids, student_ids=student_ids,
    )
    return _enrich(rows), total


def get_student(student_id: str) -> dict:
    _require_db()
    from app.services import db_service
    return _enrich([db_service.get_student(student_id)])[0]


def create_student(body) -> dict:
    _require_db()
    from app.services import db_service
    return _enrich([db_service.create_student(body)])[0]


def restore_student(body) -> dict:
    _require_db()
    from app.services import db_service
    return _enrich([db_service.restore_student(body)])[0]


def update_student(student_id: str, body) -> dict:
    _require_db()
    from app.services import db_service
    return _enrich([db_service.update_student(student_id, body)])[0]


def void_student(student_id: str, reason: str) -> dict:
    _require_db()
    from app.services import db_service
    return db_service.void_student(student_id, reason)


def get_timeline(student_id: str) -> list[dict]:
    _require_db()
    from app.services import db_service
    return db_service.get_timeline(student_id)


def get_risk_summary(student_id: str) -> dict:
    _require_db()
    from app.services import db_service
    return db_service.get_risk_summary(student_id)
