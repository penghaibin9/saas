"""学工统计口径安全门：列表、首页、驾驶舱使用同一租户与数据范围。"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import case, func, select

from app.services.db_service import _iso, _tid, session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import (
        AffairsActivity, AffairsActivityCredit, AffairsActivitySignup, ArchiveBatch,
        ArchivePackage, FamilyContactLog, FundingDisbursement, SchoolClass, StudentProfile,
        WorkStudyRecord,
    )
    from app.services import affairs_activity_reliability_service as activity_scope
    from app.services import affairs_activity_service as activity
    from app.services import affairs_cockpit_service as cockpit
    from app.services import affairs_dashboard_service as dashboard
    from app.services import affairs_funding_service as funding

    old_dashboard = dashboard.get_dashboard
    old_safe_domain = cockpit._safe_domain
    old_cockpit = cockpit.cockpit

    def get_dashboard(user):
        data = old_dashboard(user)
        with session() as db:
            allowed, _scope = dashboard._allowed_class_ids(db, user)
            query = select(func.count()).select_from(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            )
            if allowed is not None:
                query = query.where(SchoolClass.id.in_(allowed or {-1}))
            count = int(db.scalar(query) or 0)
        for card in data.get("summaryCards") or []:
            if card.get("key") == "classTotal":
                card["value"] = count
        return data

    def activity_stats(user):
        with session() as db:
            tenant_all, class_tokens, college_tokens = activity_scope._teacher_scope_tokens(db, user)
            activity_conds = [AffairsActivity.tenant_id == _tid(), AffairsActivity.is_deleted.is_(False)]
            scope_cond = activity_scope._scope_condition(
                AffairsActivity, tenant_all, class_tokens, college_tokens,
            )
            if scope_cond is not None:
                activity_conds.append(scope_cond)

            scoped_activity_ids = select(AffairsActivity.id).where(*activity_conds)
            total_activities = int(db.scalar(
                select(func.count()).select_from(AffairsActivity).where(*activity_conds)
            ) or 0)
            by_type_rows = db.execute(
                select(AffairsActivity.activity_type, func.count())
                .where(*activity_conds)
                .group_by(AffairsActivity.activity_type)
                .order_by(AffairsActivity.activity_type)
            ).all()
            by_status_rows = db.execute(
                select(AffairsActivity.status, func.count())
                .where(*activity_conds)
                .group_by(AffairsActivity.status)
                .order_by(AffairsActivity.status)
            ).all()

            from app.services.affairs_dashboard_service import _allowed_class_ids
            allowed_classes, _ = _allowed_class_ids(db, user)
            student_conds = [
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            ]
            if allowed_classes is not None:
                student_conds.append(StudentProfile.class_id.in_(allowed_classes or {-1}))

            credit_students = int(db.scalar(
                select(func.count(func.distinct(AffairsActivityCredit.student_id)))
                .select_from(AffairsActivityCredit)
                .join(StudentProfile, StudentProfile.id == AffairsActivityCredit.student_id)
                .where(AffairsActivityCredit.tenant_id == _tid(), *student_conds)
            ) or 0)
            credit_type_rows = db.execute(
                select(AffairsActivityCredit.credit_type, func.coalesce(func.sum(AffairsActivityCredit.credit_value), 0))
                .select_from(AffairsActivityCredit)
                .join(StudentProfile, StudentProfile.id == AffairsActivityCredit.student_id)
                .where(AffairsActivityCredit.tenant_id == _tid(), *student_conds)
                .group_by(AffairsActivityCredit.credit_type)
                .order_by(AffairsActivityCredit.credit_type)
            ).all()
            credit_category_rows = db.execute(
                select(AffairsActivityCredit.category_code, func.coalesce(func.sum(AffairsActivityCredit.credit_value), 0))
                .select_from(AffairsActivityCredit)
                .join(StudentProfile, StudentProfile.id == AffairsActivityCredit.student_id)
                .where(
                    AffairsActivityCredit.tenant_id == _tid(),
                    AffairsActivityCredit.category_code.is_not(None),
                    AffairsActivityCredit.category_code != "",
                    *student_conds,
                )
                .group_by(AffairsActivityCredit.category_code)
                .order_by(AffairsActivityCredit.category_code)
            ).all()

            signup_conds = [
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.is_deleted.is_(False),
                AffairsActivitySignup.signup_status != "CANCELLED",
                *student_conds,
            ]
            if not tenant_all:
                signup_conds.append(AffairsActivitySignup.activity_id.in_(scoped_activity_ids))
            signup_from = (
                select(func.count())
                .select_from(AffairsActivitySignup)
                .join(StudentProfile, StudentProfile.id == AffairsActivitySignup.student_id)
                .where(*signup_conds)
            )
            signups = int(db.scalar(signup_from) or 0)
            checkins = int(db.scalar(signup_from.where(
                AffairsActivitySignup.signup_status.in_(("CHECKED_IN", "CONFIRMED")),
            )) or 0)

            def _number(value) -> float:
                return float(Decimal(str(value or 0)).quantize(Decimal("0.01")))

            return {
                "totalActivities": total_activities,
                "totalSignups": signups,
                "totalCheckins": checkins,
                "creditStudents": credit_students,
                "byType": [{"key": key, "count": int(count or 0)} for key, count in by_type_rows],
                "byStatus": [{"key": key, "count": int(count or 0)} for key, count in by_status_rows],
                "creditByType": [{"key": key, "value": _number(value)} for key, value in credit_type_rows],
                "creditByCategory": [
                    {"key": key, "value": _number(value)} for key, value in credit_category_rows
                ],
            }

    def safe_domain(key, label, route, fn, user, *, total_key="total", highlight_from=None,
                    highlight_label=""):
        def strict(scope_user):
            data = fn(scope_user)
            if not isinstance(data, dict) or total_key not in data:
                raise RuntimeError(f"统计口径缺少必需字段：{total_key}")
            return data
        return old_safe_domain(
            key, label, route, strict, user, total_key=total_key,
            highlight_from=highlight_from, highlight_label=highlight_label,
        )

    def _scoped_student_conds(db, user):
        from app.services.affairs_dashboard_service import _allowed_class_ids
        allowed, _ = _allowed_class_ids(db, user)
        conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(allowed or {-1}))
        return allowed, conds

    def disbursement_stats(user):
        with session() as db:
            _allowed, student_conds = _scoped_student_conds(db, user)
            rows = db.execute(
                select(
                    FundingDisbursement.bank_status,
                    func.count(),
                    func.coalesce(func.sum(FundingDisbursement.amount), 0),
                )
                .select_from(FundingDisbursement)
                .join(StudentProfile, StudentProfile.id == FundingDisbursement.student_id)
                .where(
                    FundingDisbursement.tenant_id == _tid(),
                    FundingDisbursement.is_deleted.is_(False),
                    *student_conds,
                )
                .group_by(FundingDisbursement.bank_status)
                .order_by(FundingDisbursement.bank_status)
            ).all()
        total = sum(int(count or 0) for _status, count, _amount in rows)
        issued_total = sum(
            (Decimal(str(amount or 0)) for status, _count, amount in rows if status == "ISSUED"),
            Decimal("0.00"),
        )
        result = {
            "total": total,
            "byStatus": [
                {"key": status, "label": funding._L_BANK.get(status, status), "count": int(count or 0)}
                for status, count, _amount in rows
            ],
        }
        if (user or {}).get("currentRoleCode") in funding._AMOUNT_ROLES:
            result["issuedAmountTotal"] = format(issued_total.quantize(Decimal("0.01")), ".2f")
        return result

    def _replace_domain(result: dict, domain: dict) -> None:
        domains = result.get("domains") or []
        replaced = False
        for index, existing in enumerate(domains):
            if existing.get("key") == domain["key"]:
                domains[index] = domain
                replaced = True
                break
        if not replaced:
            domains.append(domain)
        result["domains"] = domains
        result["domainsByKey"] = {row["key"]: row for row in domains}

    def cockpit_view(user):
        result = old_cockpit(user)
        now = _iso(__import__("datetime").datetime.utcnow())
        with session() as db:
            allowed, student_conds = _scoped_student_conds(db, user)

            package_total, scoped_batches, archive_pending = db.execute(
                select(
                    func.count(ArchivePackage.id),
                    func.count(func.distinct(ArchivePackage.batch_id)),
                    func.coalesce(func.sum(case((ArchivePackage.status != "ARCHIVED", 1), else_=0)), 0),
                )
                .select_from(ArchivePackage)
                .join(StudentProfile, StudentProfile.id == ArchivePackage.student_id)
                .where(
                    ArchivePackage.tenant_id == _tid(), ArchivePackage.is_deleted.is_(False),
                    *student_conds,
                )
            ).one()
            package_total = int(package_total or 0)
            archive_pending = int(archive_pending or 0)
            if allowed is None:
                archive_batches = int(db.scalar(select(func.count()).select_from(ArchiveBatch).where(
                    ArchiveBatch.tenant_id == _tid(), ArchiveBatch.is_deleted.is_(False),
                )) or 0)
            else:
                archive_batches = int(scoped_batches or 0)
            _replace_domain(result, {
                "key": "archive", "label": "学工归档", "status": "OK",
                "metrics": {"total": package_total, "batches": archive_batches,
                            "pending": archive_pending},
                "total": package_total, "highlight": archive_pending,
                "highlightLabel": "未归档档案包", "message": "", "updatedAt": now,
                "route": "/admin/student-affairs/archive",
            })

            work_total, work_pending, work_onboard = db.execute(
                select(
                    func.count(WorkStudyRecord.id),
                    func.coalesce(func.sum(case((WorkStudyRecord.status == "APPLIED", 1), else_=0)), 0),
                    func.coalesce(func.sum(case((WorkStudyRecord.status == "ONBOARD", 1), else_=0)), 0),
                )
                .select_from(WorkStudyRecord)
                .join(StudentProfile, StudentProfile.id == WorkStudyRecord.student_id)
                .where(
                    WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False),
                    *student_conds,
                )
            ).one()
            work_total = int(work_total or 0)
            work_pending = int(work_pending or 0)
            work_onboard = int(work_onboard or 0)
            _replace_domain(result, {
                "key": "workStudy", "label": "勤工助学", "status": "OK",
                "metrics": {"total": work_total, "pending": work_pending, "onboard": work_onboard},
                "total": work_total, "highlight": work_pending,
                "highlightLabel": "待审核", "message": "", "updatedAt": now,
                "route": "/admin/student-affairs/funding/work-study",
            })

            family_total, pending_receipts = db.execute(
                select(
                    func.count(FamilyContactLog.id),
                    func.coalesce(func.sum(case((
                        func.coalesce(FamilyContactLog.receipt_status, "PENDING") == "PENDING", 1
                    ), else_=0)), 0),
                )
                .select_from(FamilyContactLog)
                .join(StudentProfile, StudentProfile.id == FamilyContactLog.student_id)
                .where(FamilyContactLog.tenant_id == _tid(), *student_conds)
            ).one()
            family_total = int(family_total or 0)
            pending_receipts = int(pending_receipts or 0)
            _replace_domain(result, {
                "key": "family", "label": "家校联系", "status": "OK",
                "metrics": {"total": family_total, "pendingReceipt": pending_receipts},
                "total": family_total, "highlight": pending_receipts,
                "highlightLabel": "待回执", "message": "", "updatedAt": now,
                "route": "/admin/student-affairs/family",
            })
        result["updatedAt"] = now
        return result

    dashboard.get_dashboard = get_dashboard
    activity.activity_stats = activity_stats
    funding.disbursement_stats = disbursement_stats
    cockpit._safe_domain = safe_domain
    cockpit.cockpit = cockpit_view
    _INSTALLED = True
