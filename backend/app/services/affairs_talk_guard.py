"""谈心谈话/家校联系安全门：租户批量查询、动态敏感权限、动作证据与重复转介。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_INSTALLED = False


def _text(value, label: str, minimum: int, maximum: int) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}需{minimum}-{maximum}字")
    return text


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import StudentProfile
    from app.services import affairs_talk_service as talk

    old_row = talk._talk_row
    old_create = talk.create_talk
    old_record = talk.record_talk
    old_contact = talk.create_contact
    old_receipt = talk.mark_receipt

    def students_by_ids(db, rows, attr="student_id"):
        ids = {int(getattr(row, attr)) for row in rows if getattr(row, attr, None)}
        if not ids:
            return {}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(ids),
            StudentProfile.is_deleted.is_(False),
        )).all()
        return {int(student.id): student for student in students}

    def can_view_psy(user) -> bool:
        return has_permission(user or {}, "studentAffairs.risk.psyDetail.view")

    def talk_row(row, user, student=None):
        data = old_row(row, user, student)
        if row.status in ("COMPLETED", "FOLLOW_UP"):
            actions = ["FOLLOW", "CLOSE"]
            if not row.related_risk_id:
                actions.append("TO_RISK")
            if not row.related_contact_id:
                actions.append("TO_HOME_SCHOOL")
            data["allowedActions"] = actions
        else:
            data["allowedActions"] = []
        return data

    def create_talk(body, user):
        body.topic = _text(getattr(body, "topic", None), "谈话主题", 2, 200)
        ids = list(dict.fromkeys(str(value).strip() for value in (body.studentIds or []) if str(value).strip()))
        if not ids or any(not value.isdigit() for value in ids):
            raise AppException("VALIDATION_ERROR", "请选择有效学生")
        body.studentIds = ids
        scheduled = getattr(body, "scheduledAt", None)
        if scheduled and talk._parse_dt(scheduled) is None:
            raise AppException("VALIDATION_ERROR", "预约时间格式不正确")
        return old_create(body, user)

    def record_talk(talk_id, user, content, result="", need_follow=False, expected_version=None):
        content = _text(content, "谈话内容", 20, 2000)
        result = str(result or "").strip()
        if len(result) > 50:
            raise AppException("VALIDATION_ERROR", "谈话结果不能超过50字")
        return old_record(talk_id, user, content, result, need_follow, expected_version)

    def follow_up(talk_id, user, action, content="", expected_version=None):
        from app.models import AffairsRiskRecord, FamilyContactLog, StudentStageEvent
        action = str(action or "").upper()
        text = _text(content, {
            "FOLLOW": "跟进记录", "CLOSE": "办结结论",
            "TO_RISK": "转风险依据", "TO_HOME_SCHOOL": "转家校说明",
        }.get(action, "处理说明"), 5, 1000)
        with session() as db:
            row, student = talk._load_talk(db, talk_id)
            talk._scope_or_403(db, row.student_id, user)
            if row.status not in ("COMPLETED", "FOLLOW_UP"):
                raise AppException("APPROVAL_VERSION_CONFLICT", "仅已完成/跟进中的谈话可操作")
            talk.atomic_claim_version(db, row, expected_version)
            stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            if action == "FOLLOW":
                row.status = "FOLLOW_UP"
                row.content = ((row.content or "") + f"\n[跟进 {stamp}] {text}")[-2000:]
                talk._audit(db, "TALK", row.id, "FOLLOW", text[:200])
            elif action == "CLOSE":
                row.status, row.need_follow = "CLOSED", False
                row.result = text[:50]
                row.content = ((row.content or "") + f"\n[办结 {stamp}] {text}")[-2000:]
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(row.student_id), from_stage=None,
                    to_stage="TALK_CLOSED", reason="谈话办结", source_module="student-affairs",
                ))
                talk._audit(db, "TALK", row.id, "CLOSE", text[:200])
            elif action == "TO_RISK":
                if row.related_risk_id:
                    raise AppException("DATA_CONFLICT", "该谈话已转风险，不可重复创建")
                source = "MENTAL" if row.topic_type == "PSYCHOLOGY" else "MANUAL"
                risk = AffairsRiskRecord(
                    tenant_id=_tid(), student_id=row.student_id, source=source,
                    source_ref_id=row.id, risk_level="MEDIUM",
                    title=f"谈话转风险：{row.topic or ''}", detail=text, status="NEW",
                )
                db.add(risk); db.flush()
                row.related_risk_id = risk.id
                row.status = "FOLLOW_UP"
                talk._audit(db, "TALK", row.id, "TO_RISK", f"risk={risk.id};{text[:160]}")
            elif action == "TO_HOME_SCHOOL":
                if row.related_contact_id:
                    raise AppException("DATA_CONFLICT", "该谈话已转家校，不可重复创建")
                contact = FamilyContactLog(
                    tenant_id=_tid(), student_id=row.student_id, contact_type="PHONE",
                    contact_reason=f"谈话转家校：{row.topic or ''}", contact_result=text,
                    related_risk_id=row.related_risk_id, occurred_at=datetime.utcnow(),
                )
                db.add(contact); db.flush()
                row.related_contact_id = contact.id
                row.status = "FOLLOW_UP"
                talk._audit(db, "TALK", row.id, "TO_HOME_SCHOOL", f"contact={contact.id};{text[:160]}")
            else:
                raise AppException("VALIDATION_ERROR", "无效操作")
            row.version = int(row.version or 0) + 1
            db.commit(); db.refresh(row)
            return talk._talk_row(row, user, student)

    def create_contact(student_id, user, body):
        kind = str(getattr(body, "contactType", None) or "PHONE").upper()
        if kind not in ("PHONE", "WECHAT", "VISIT", "MESSAGE"):
            raise AppException("VALIDATION_ERROR", "家校联系类型非法")
        body.contactType = kind
        body.reason = _text(getattr(body, "reason", None), "联系事由", 2, 500)
        body.result = _text(getattr(body, "result", None), "联系结果", 2, 1000)
        return old_contact(student_id, user, body)

    def mark_receipt(contact_id, user, note=""):
        note = _text(note, "家长回执", 2, 500)
        data = old_receipt(contact_id, user, note)
        with session() as db:
            talk._audit(db, "FAMILY", contact_id, "RECEIPT", note[:200])
            db.commit()
        return data

    talk._students_by_ids = students_by_ids
    talk.create_talk = create_talk
    talk.record_talk = record_talk
    talk.follow_up = follow_up
    talk.create_contact = create_contact
    talk.mark_receipt = mark_receipt
    _INSTALLED = True
