"""O5 college confirmation: one idempotent transaction into formal student lifecycle."""
from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, check_version, not_found
from app.core.security import hash_password
from app.core.student_lifecycle import ADMITTED, ENROLLED
from app.core.student_master_contract import SOURCE_ADMISSION, StudentCreateCommand
from app.models import (
    GreenChannelApplication,
    OrientationArrivalPlan,
    OrientationCheckinRecord,
    OrientationEnrollmentFinalize,
    OrientationMaterial,
    OrientationPaymentAccount,
    OrientationStudent,
    StudentAccountLink,
    StudentProfile,
    StudentStageEvent,
    UnifiedMessage,
    User,
)
from app.services.db_service import _iso, _tid, audit_insert_in_session, session


def _actor_id(user=None) -> int:
    raw = str((user or get_current_user_ctx() or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    if not raw.isdigit() or int(raw) <= 0:
        raise AppException("NO_PERMISSION", "无法识别学院确认操作人", http_status=403)
    return int(raw)


def _payload(row: OrientationEnrollmentFinalize, *, idempotent=False, credential=None) -> dict:
    return {
        "id": str(row.id),
        "orientationStudentId": str(row.orientation_student_id),
        "studentId": str(row.student_id),
        "studentNo": row.student_no_snapshot,
        "status": row.status,
        "stage": row.to_stage,
        "finalizedAt": _iso(row.finalized_at),
        "idempotent": bool(idempotent),
        "initialCredential": credential,
    }


class OrientationEnrollmentFinalizeService:
    """Named application service required by the orientation construction manual."""

    @staticmethod
    def _profile(db, student: OrientationStudent, body: dict, actor: dict | None):
        if student.student_id:
            profile = db.get(StudentProfile, int(student.student_id))
            if (
                not profile or profile.is_deleted
                or int(profile.tenant_id) != int(student.tenant_id)
            ):
                raise AppException("DATA_CONFLICT", "迎新记录绑定的学生主档无效，请先修复身份关联")
            return profile

        student_no = str((body or {}).get("studentNo") or "").strip()
        if not student_no:
            raise AppException("VALIDATION_ERROR", "未绑定主档的新生须填写正式学号")
        from app.services import student_master_application_service as master

        cmd = StudentCreateCommand(
            student_no=student_no,
            real_name=student.name,
            source=SOURCE_ADMISSION,
            gender=student.gender,
            grade=student.grade,
            college_id=student.college_id,
            major_id=student.major_id,
            class_id=student.class_id,
            current_stage=ADMITTED,
            student_status="NORMAL",
            require_complete_org=True,
            remark=f"由迎新台账 {student.id} 学院确认建档",
        )
        resolution = master.resolve_student_for_import(
            db, tenant_id=int(student.tenant_id), cmd=cmd,
        )
        if resolution.blocked:
            raise AppException("DATA_CONFLICT", resolution.message or "学生主档存在身份冲突")
        result = master.apply_resolution_in_session(
            db, tenant_id=int(student.tenant_id), cmd=cmd,
            resolution=resolution, actor=actor,
        )
        profile = db.get(StudentProfile, int(result.student_id))
        student.student_id = profile.id
        student.identity_status = "LINKED"
        for model in (
            OrientationMaterial,
            OrientationPaymentAccount,
            GreenChannelApplication,
            OrientationArrivalPlan,
        ):
            key = (
                model.orientation_student_id == student.id
                if hasattr(model, "orientation_student_id")
                else model.ori_student_id == student.id
            )
            for child in db.scalars(select(model).where(
                model.tenant_id == student.tenant_id, key,
                model.is_deleted.is_(False),
            )).all():
                child.student_id = profile.id
        db.flush()
        return profile

    @staticmethod
    def _account(db, profile: StudentProfile, student: OrientationStudent, body: dict):
        from app.services import student_account_link_service as links
        from app.services.saas_role_service import ensure_builtin_roles, ensure_user_roles

        existing_uid = links.get_user_id_by_student(
            db, tenant_id=int(student.tenant_id), student_id=profile.id,
        )
        initial_credential = None
        if existing_uid:
            account = db.get(User, int(existing_uid))
            if not account or account.is_deleted or account.status != "ACTIVE":
                raise AppException("DATA_CONFLICT", "学生主档绑定的登录账号不可用")
            return account, initial_credential

        requested_user_id = str((body or {}).get("accountUserId") or "").removeprefix("db-")
        account = db.get(User, int(requested_user_id)) if requested_user_id.isdigit() else None
        if account and (
            account.is_deleted or account.status != "ACTIVE"
            or account.user_type != "STUDENT"
            or int(account.tenant_id) != int(student.tenant_id)
        ):
            raise AppException("DATA_CONFLICT", "指定的预学生账号不可用")
        if not account:
            account = db.scalars(select(User).where(
                User.tenant_id == student.tenant_id,
                User.login_name.in_((profile.student_no, student.admission_no)),
                User.user_type == "STUDENT",
                User.status == "ACTIVE",
                User.is_deleted.is_(False),
            ).order_by(User.id)).first()
        if not account:
            temporary_password = "Stu@" + secrets.token_urlsafe(9)
            account = User(
                tenant_id=student.tenant_id,
                login_name=profile.student_no,
                real_name=profile.real_name,
                password_hash=hash_password(temporary_password),
                user_type="STUDENT", status="ACTIVE", must_change_password=True,
            )
            db.add(account)
            db.flush()
            initial_credential = {
                "loginName": account.login_name,
                "temporaryPassword": temporary_password,
                "mustChangePassword": True,
            }
        links.bind_in_session(
            db, tenant_id=int(student.tenant_id), student_id=int(profile.id),
            user_id=int(account.id), source="ORIENTATION_FINALIZE",
            login_name=account.login_name, student_no=profile.student_no,
            remark=f"迎新台账 {student.id} 学院确认",
        )
        ensure_builtin_roles(db, int(student.tenant_id))
        ensure_user_roles(db, int(student.tenant_id), int(account.id), ["STUDENT"])
        return account, initial_credential

    @classmethod
    def finalize(cls, orientation_student_id, body: dict, *, user=None) -> dict:
        from app.services.orientation_flow_service import set_student_step_status
        from app.services.orientation_qualification_service import evaluate
        from app.services.orientation_service import _audit, assert_orientation_student_scope

        actor = user or get_current_user_ctx() or {}
        actor_id = _actor_id(actor)
        request_id = str((body or {}).get("clientRequestId") or "").strip()
        if len(request_id) < 12 or len(request_id) > 100:
            raise AppException("VALIDATION_ERROR", "clientRequestId 长度须为 12-100 个字符")
        with session() as db:
            student = db.scalars(select(OrientationStudent).where(
                OrientationStudent.id == int(orientation_student_id),
                OrientationStudent.tenant_id == _tid(),
                OrientationStudent.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("新生记录不存在")
            assert_orientation_student_scope(db, student, actor)
            existing = db.scalars(select(OrientationEnrollmentFinalize).where(
                OrientationEnrollmentFinalize.tenant_id == _tid(),
                OrientationEnrollmentFinalize.orientation_student_id == student.id,
                OrientationEnrollmentFinalize.is_deleted.is_(False),
            ).with_for_update()).first()
            if existing:
                return _payload(existing, idempotent=True)
            reused_request = db.scalars(select(OrientationEnrollmentFinalize).where(
                OrientationEnrollmentFinalize.tenant_id == _tid(),
                OrientationEnrollmentFinalize.request_id == request_id,
                OrientationEnrollmentFinalize.is_deleted.is_(False),
            )).first()
            if reused_request:
                raise AppException("IDEMPOTENCY_CONFLICT", "clientRequestId 已用于其他新生确认")
            check_version(student.version, (body or {}).get("expectedVersion"))
            checkin = db.scalars(select(OrientationCheckinRecord).where(
                OrientationCheckinRecord.tenant_id == _tid(),
                OrientationCheckinRecord.orientation_student_id == student.id,
                OrientationCheckinRecord.status == "CONFIRMED",
                OrientationCheckinRecord.is_deleted.is_(False),
            ).with_for_update()).first()
            if not checkin or student.report_status != "CHECKED_IN":
                raise AppException("INVALID_STATE", "须先使用签名报到凭证完成现场报到", http_status=409)

            profile = cls._profile(db, student, body, actor)
            account, initial_credential = cls._account(db, profile, student, body)
            decision = evaluate(db, student)
            if decision["verdict"] != "QUALIFIED":
                raise AppException(
                    "ORIENTATION_QUALIFICATION_CHANGED",
                    "报到资格已变化，学院确认已阻止",
                    details={"verdict": decision["verdict"], "blockers": decision["blockers"]},
                    http_status=409,
                )

            now = datetime.utcnow()
            from_stage = profile.current_stage
            if profile.current_stage != ENROLLED:
                profile.current_stage = ENROLLED
                profile.enroll_date = profile.enroll_date or now
                profile.status = "ACTIVE"
                profile.version = int(profile.version or 0) + 1
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=profile.id,
                    from_stage=from_stage, to_stage=ENROLLED,
                    reason="迎新现场报到完成并由学院最终确认",
                    source_module="orientation", occurred_at=now,
                    created_at=now, created_by=actor_id,
                ))
            student.student_id = profile.id
            student.identity_status = "LINKED"
            before_report = student.report_status
            student.report_status = "COLLEGE_CONFIRMED"
            student.stage = ENROLLED
            set_student_step_status(
                db, student, "CONFIRM", "DONE", status_source="PROCESS_FACT",
                source_biz_id=f"orientation-finalize:{request_id}",
            )
            student.version = int(student.version or 0) + 1
            receipt = OrientationEnrollmentFinalize(
                tenant_id=_tid(), batch_id=student.batch_id,
                orientation_student_id=student.id, student_id=profile.id,
                request_id=request_id, student_no_snapshot=profile.student_no,
                from_stage=from_stage, to_stage=ENROLLED,
                finalized_at=now, finalized_by=actor_id, status="FINALIZED",
            )
            db.add(receipt)
            db.flush()
            db.add(UnifiedMessage(
                tenant_id=_tid(), receiver_id=profile.id,
                receiver_user_id=account.id, receiver_type="STUDENT",
                receiver_context_key="GLOBAL", source_module="orientation",
                source_biz_id=receipt.id, title="入学确认已完成",
                content="学院已完成你的入学确认，学生主档已正式进入在读阶段。",
                message_type="BUSINESS", status="UNREAD", priority="IMPORTANT",
                category="BUSINESS", delivered_at=now, delivery_status="DELIVERED",
                rendered_title="入学确认已完成",
                rendered_content_plain="学院已完成你的入学确认，学生主档已正式进入在读阶段。",
            ))
            _audit(
                db, "FINALIZE", student.id, "学院最终确认入学",
                f"studentId={profile.id}; studentNo={profile.student_no}",
                before_report, "COLLEGE_CONFIRMED",
            )
            audit_insert_in_session(
                db, "迎新学院最终确认", "orientation",
                {
                    "orientationStudentId": str(student.id),
                    "studentId": str(profile.id),
                    "studentNo": profile.student_no,
                    "fromStage": from_stage,
                    "toStage": ENROLLED,
                    "checkinRecordId": str(checkin.id),
                    "operator": actor.get("realName") or "",
                    "roleCode": actor.get("currentRoleCode") or "",
                },
                "SUCCESS", resource_id=str(receipt.id),
            )
            db.commit()
            return _payload(receipt, credential=initial_credential)


finalize = OrientationEnrollmentFinalizeService.finalize
