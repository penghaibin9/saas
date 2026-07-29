"""活动撤销确认后的再次确认恢复。

活动积分账本采用 append-only：撤销确认不删除原 ACTIVITY 流水，而是追加负数冲正。
因此再次确认时，旧 confirm 会因原 ACTIVITY 流水仍存在而跳过该学生。此终态补丁在
旧 confirm 完成状态流转后，为仍处于 CHECKED_IN 的学生追加正向恢复流水并恢复报名状态，
保证账本可追溯且重复确认不会重复入账。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.services.db_service import _tid, session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.models import AffairsActivityCredit, AffairsActivitySignup, StudentStageEvent
    from app.services import affairs_activity_service as activity

    old_confirm = activity.confirm_activity

    def confirm_activity(activity_id, user, expected_version=None):
        result = old_confirm(activity_id, user, expected_version)
        restored = 0
        with session() as db:
            row = activity._load(db, activity_id)
            if row.status != "CONFIRMED":
                return result

            credit_type = row.credit_type or "SECOND_CLASS"
            pending = db.scalars(select(AffairsActivitySignup).where(
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.activity_id == row.id,
                AffairsActivitySignup.signup_status == "CHECKED_IN",
                AffairsActivitySignup.is_deleted.is_(False),
            ).with_for_update()).all()

            for signup in pending:
                original = db.scalars(select(AffairsActivityCredit).where(
                    AffairsActivityCredit.tenant_id == _tid(),
                    AffairsActivityCredit.student_id == signup.student_id,
                    AffairsActivityCredit.activity_id == row.id,
                    AffairsActivityCredit.credit_type == credit_type,
                    AffairsActivityCredit.source == "ACTIVITY",
                ).order_by(AffairsActivityCredit.id)).first()
                if not original:
                    # 没有历史正式流水时应由旧 confirm 正常生成；这里不凭空补账。
                    continue

                value = Decimal(str(original.credit_value or 0))
                db.add(AffairsActivityCredit(
                    tenant_id=_tid(),
                    student_id=signup.student_id,
                    activity_id=None,
                    credit_type=original.credit_type,
                    credit_value=value,
                    category_code=original.category_code,
                    source="MANUAL_ADJUST",
                    remark=(
                        f"活动#{row.id}重新确认恢复；原流水#{original.id}；"
                        "对应最近一次撤销确认冲正"
                    ),
                    created_by=activity._uid_int(user),
                ))
                signup.signup_status = "CONFIRMED"
                signup.version = int(signup.version or 0) + 1
                db.add(StudentStageEvent(
                    tenant_id=_tid(),
                    student_id=int(signup.student_id),
                    from_stage=None,
                    to_stage="ACTIVITY_RECONFIRMED",
                    reason=f"活动《{row.activity_name}》重新确认并恢复积分",
                    source_module="student-affairs",
                ))
                restored += 1

            if restored:
                activity._audit(db, row.id, "ACTIVITY_RECONFIRM", f"{restored}人恢复入账")
                db.commit()

        if restored:
            result = dict(result or {})
            result["creditsGranted"] = int(result.get("creditsGranted") or 0) + restored
        return result

    activity.confirm_activity = confirm_activity
    _INSTALLED = True
