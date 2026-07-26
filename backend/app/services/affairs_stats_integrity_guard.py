"""学工统计口径安全门：列表、首页、驾驶舱使用同一租户与数据范围。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.services.db_service import _iso, _tid, session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import (
        AffairsActivity, AffairsActivityCredit, AffairsActivitySignup, ArchiveBatch,
        ArchivePackage, FamilyContactLog, SchoolClass, StudentProfile, WorkStudyRecord,
    )
    from app.services import affairs_activity_reliability_service as activity_scope
    from app.services import affairs_activity_service as activity
    from app.services import affairs_cockpit_service as cockpit
    from app.services import affairs_dashboard_service as dashboard

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
            activities = db.scalars(select(AffairsActivity).where(*activity_conds)).all()
            activity_ids = {int(row.id) for row in activities}

            from app.services.affairs_dashboard_service import _allowed_class_ids
            allowed_classes, _ = _allowed_class_ids(db, user)
            student_conds = [
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            ]
            if allowed_classes is not None:
                student_conds.append(StudentProfile.class_id.in_(allowed_classes or {-1}))

            credit_stmt = select(AffairsActivityCredit).join(
                StudentProfile, StudentProfile.id == AffairsActivityCredit.student_id,
            ).where(AffairsActivityCredit.tenant_id == _tid(), *student_conds)
            credits = db.scalars(credit_stmt).all()

            signup_conds = [
                AffairsActivitySignup.tenant_id == _tid(),
                AffairsActivitySignup.is_deleted.is_(False),
                AffairsActivitySignup.signup_status != "CANCELLED",
                *student_conds,
            ]
            if not tenant_all:
                signup_conds.append(AffairsActivitySignup.activity_id.in_(activity_ids or {-1}))
            signup_base = select(func.count()).select_from(AffairsActivitySignup).join(
                StudentProfile, StudentProfile.id == AffairsActivitySignup.student_id,
            ).where(*signup_conds)
            signups = int(db.scalar(signup_base) or 0)
            checkins = int(db.scalar(signup_base.where(
                AffairsActivitySignup.signup_status.in_(("CHECKED_IN", "CONFIRMED")),
            )) or 0)

            by_type, by_status = {}, {}
            for row in activities:
                by_type[row.activity_type] = by_type.get(row.activity_type, 0) + 1
                by_status[row.status] = by_status.get(row.status, 0) + 1
            credit_by_type, credit_by_category = {}, {}
            for row in credits:
                value = float(row.credit_value or 0)
                credit_by_type[row.credit_type] = round(credit_by_type.get(row.credit_type, 0) + value, 2)
                if row.category_code:
                    credit_by_category[row.category_code] = round(
                        credit_by_category.get(row.category_code, 0) + value, 2,
                    )
            return {
                "totalActivities": len(activities), "totalSignups": signups,
                "totalCheckins": checkins, "creditStudents": len({row.student_id for row in credits}),
                "byType": [{"key": key, "count": value} for key, value in by_type.items()],
                "byStatus": [{"key": key, "count": value} for key, value in by_status.items()],
                "creditByType": [{"key": key, "value": value} for key, value in credit_by_type.items()],
                "creditByCategory": [{"key": key, "value": value} for key, value in credit_by_category.items()],
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

            package_stmt = select(ArchivePackage).join(
                StudentProfile, StudentProfile.id == ArchivePackage.student_id,
            ).where(
                ArchivePackage.tenant_id == _tid(), ArchivePackage.is_deleted.is_(False),
                *student_conds,
            )
            packages = db.scalars(package_stmt).all()
            if allowed is None:
                archive_batches = int(db.scalar(select(func.count()).select_from(ArchiveBatch).where(
                    ArchiveBatch.tenant_id == _tid(), ArchiveBatch.is_deleted.is_(False),
                )) or 0)
            else:
                archive_batches = len({row.batch_id for row in packages})
            archive_pending = sum(1 for row in packages if row.status != "ARCHIVED")
            _replace_domain(result, {
                "key": "archive", "label": "学工归档", "status": "OK",
                "metrics": {"total": len(packages), "batches": archive_batches,
                            "pending": archive_pending},
                "total": len(packages), "highlight": archive_pending,
                "highlightLabel": "未归档档案包", "message": "", "updatedAt": now,
                "route": "/admin/student-affairs/archive",
            })

            work_stmt = select(WorkStudyRecord).join(
                StudentProfile, StudentProfile.id == WorkStudyRecord.student_id,
            ).where(
                WorkStudyRecord.tenant_id == _tid(), WorkStudyRecord.is_deleted.is_(False),
                *student_conds,
            )
            work_rows = db.scalars(work_stmt).all()
            work_pending = sum(1 for row in work_rows if row.status == "APPLIED")
            _replace_domain(result, {
                "key": "workStudy", "label": "勤工助学", "status": "OK",
                "metrics": {"total": len(work_rows), "pending": work_pending,
                            "onboard": sum(1 for row in work_rows if row.status == "ONBOARD")},
                "total": len(work_rows), "highlight": work_pending,
                "highlightLabel": "待审核", "message": "", "updatedAt": now,
                "route": "/admin/student-affairs/funding/work-study",
            })

            family_stmt = select(FamilyContactLog).join(
                StudentProfile, StudentProfile.id == FamilyContactLog.student_id,
            ).where(FamilyContactLog.tenant_id == _tid(), *student_conds)
            family_rows = db.scalars(family_stmt).all()
            pending_receipts = sum(1 for row in family_rows if (row.receipt_status or "PENDING") == "PENDING")
            _replace_domain(result, {
                "key": "family", "label": "家校联系", "status": "OK",
                "metrics": {"total": len(family_rows), "pendingReceipt": pending_receipts},
                "total": len(family_rows), "highlight": pending_receipts,
                "highlightLabel": "待回执", "message": "", "updatedAt": now,
                "route": "/admin/student-affairs/family",
            })
        result["updatedAt"] = now
        return result

    dashboard.get_dashboard = get_dashboard
    activity.activity_stats = activity_stats
    cockpit._safe_domain = safe_domain
    cockpit.cockpit = cockpit_view
    _INSTALLED = True
