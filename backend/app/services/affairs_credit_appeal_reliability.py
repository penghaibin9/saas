"""第二课堂积分申诉的并发、引用与分页收口。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session


def install() -> None:
    from app.models import (
        AffairsActivity, AffairsActivityCredit, AffairsCreditAppeal, StudentProfile,
    )
    from app.services import affairs_activity_service as activity
    from app.services.affairs_dashboard_service import _allowed_class_ids
    from app.services.affairs_list_stats import status_counts_by_column

    def submit_credit_appeal(body, user):
        sid = int(getattr(body, "studentId", 0) or 0)
        appeal_type = str(getattr(body, "appealType", "MISSING") or "MISSING").upper()
        if appeal_type not in ("MISSING", "WRONG"):
            raise AppException("VALIDATION_ERROR", "申诉类型非法")
        reason = str(getattr(body, "reason", "") or "").strip()
        if not 5 <= len(reason) <= 1000:
            raise AppException("VALIDATION_ERROR", "申诉理由需5-1000字")
        credit_type = str(getattr(body, "claimCreditType", "SECOND_CLASS") or "SECOND_CLASS").upper()
        if credit_type not in activity.CREDIT_TYPES:
            raise AppException("VALIDATION_ERROR", "主张积分类型非法")
        raw_value = getattr(body, "claimValue", None)
        try:
            claim_value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "主张数值必填且格式正确") from exc
        if claim_value <= 0 or claim_value > Decimal("9999.99"):
            raise AppException("VALIDATION_ERROR", "主张数值应大于0且不超过9999.99")
        if claim_value.as_tuple().exponent < -2:
            raise AppException("VALIDATION_ERROR", "主张数值最多保留2位小数")
        raw_activity_id = getattr(body, "activityId", None)
        activity_id = int(raw_activity_id) if str(raw_activity_id or "").isdigit() else None

        with session() as db:
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == sid,
                StudentProfile.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("学生不存在")
            if activity_id:
                activity_row = db.scalars(select(AffairsActivity).where(
                    AffairsActivity.tenant_id == _tid(),
                    AffairsActivity.id == activity_id,
                    AffairsActivity.is_deleted.is_(False),
                )).first()
                if not activity_row:
                    raise not_found("涉及活动不存在")
                if appeal_type == "WRONG":
                    existing_credit = db.scalars(select(AffairsActivityCredit.id).where(
                        AffairsActivityCredit.tenant_id == _tid(),
                        AffairsActivityCredit.student_id == sid,
                        AffairsActivityCredit.activity_id == activity_id,
                        AffairsActivityCredit.is_deleted.is_(False),
                    ).limit(1)).first()
                    if not existing_credit:
                        raise AppException("DATA_CONFLICT", "没有可供更正的该活动积分记录")
            duplicate_conds = [
                AffairsCreditAppeal.tenant_id == _tid(),
                AffairsCreditAppeal.student_id == sid,
                AffairsCreditAppeal.appeal_type == appeal_type,
                AffairsCreditAppeal.status == "SUBMITTED",
                AffairsCreditAppeal.is_deleted.is_(False),
            ]
            duplicate_conds.append(
                AffairsCreditAppeal.activity_id == activity_id
                if activity_id is not None else AffairsCreditAppeal.activity_id.is_(None)
            )
            duplicate = db.scalars(select(AffairsCreditAppeal.id).where(*duplicate_conds).limit(1)).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "该记录已有待审核申诉")
            row = AffairsCreditAppeal(
                tenant_id=_tid(), student_id=sid, activity_id=activity_id,
                appeal_type=appeal_type, claim_credit_type=credit_type,
                claim_value=claim_value, reason=reason, status="SUBMITTED",
                created_by=activity._uid_int(user),
            )
            db.add(row)
            db.flush()
            activity._audit(db, row.id, "CREDIT_APPEAL_SUBMIT", appeal_type)
            db.commit()
            db.refresh(row)
            return activity._cappeal_row(row, student)

    def list_credit_appeals(user, status=None, page=1, page_size=50):
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 50)))
        with session() as db:
            allowed, _ = _allowed_class_ids(db, user)
            base_conds = [
                AffairsCreditAppeal.tenant_id == _tid(),
                AffairsCreditAppeal.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ]
            if allowed is not None:
                base_conds.append(StudentProfile.class_id.in_(allowed or {-1}))
            status_counts = status_counts_by_column(
                db, AffairsCreditAppeal, AffairsCreditAppeal.status,
                [AffairsCreditAppeal.tenant_id == _tid(), AffairsCreditAppeal.is_deleted.is_(False)],
                join_student=StudentProfile, allowed_class_ids=allowed,
            )
            conds = list(base_conds)
            if status:
                statuses = [x.strip() for x in str(status).split(",") if x.strip()]
                if statuses:
                    conds.append(AffairsCreditAppeal.status.in_(statuses))
            base_stmt = select(AffairsCreditAppeal, StudentProfile).join(
                StudentProfile, StudentProfile.id == AffairsCreditAppeal.student_id,
            ).where(*conds)
            total = int(db.scalar(select(func.count()).select_from(
                base_stmt.with_only_columns(AffairsCreditAppeal.id).subquery()
            )) or 0)
            rows = db.execute(
                base_stmt.order_by(AffairsCreditAppeal.id.desc())
                .offset((page - 1) * page_size).limit(page_size)
            ).all()
            return [activity._cappeal_row(row, student) for row, student in rows], total, status_counts

    activity.submit_credit_appeal = submit_credit_appeal
    activity.list_credit_appeals = list_credit_appeals
