"""学生主档正式服务。

A2 / P0-02 + P0-03：
- 正式 `/students` 链路必须使用真实数据库；DB 不可用时 fail-closed，禁止回落内存学生。
- 身份核验、账号绑定、主档完整度都来自明确事实；缺事实返回 UNKNOWN/NOT_CONFIGURED，
  绝不补 VERIFIED / BOUND / 固定 90%。
- 学生主档写入继续复用 db_service 的事务、乐观锁、审计与学籍异动边界。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

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
    # 班级/专业/学院变更不属于学生主档动作：必须走教务学籍异动。
    return sorted(set(result))


def _fact_map(student_ids: list[int]) -> dict[int, dict]:
    if not student_ids:
        return {}
    from app.models import StudentContact, StudentProfile
    from app.models.student_account_link import (
        LINK_ACTIVE,
        LINK_SUSPENDED,
        StudentAccountLink,
    )
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
        # ACTIVE 为权威绑定；SUSPENDED 次之；历史 REVOKED/MERGED 不等于当前已绑定。
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
            # db_service 的历史兼容值在未登记手机时为 1**********；这里以真实联系表纠偏。
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
            # 无法解析事实时宁可 UNKNOWN，也不制造成功态。
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
        page,
        page_size,
        keyword,
        college,
        major,
        class_name,
        status,
        risk_level,
        class_ids=class_ids,
        student_ids=student_ids,
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
