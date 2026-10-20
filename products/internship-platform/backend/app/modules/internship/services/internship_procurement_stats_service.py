"""Yiyang C06 procurement-facing four-group statistics.

This service is intentionally read-only. Every card is derived from canonical facts and
keeps numerator/denominator/source semantics so mobile charts, PC and exports can agree.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from sqlalchemy import func, select

from app.models import (
    InternshipChangeRequest,
    InternshipFinalScore,
    InternshipPayrollStatement,
    InternshipPayrollVersion,
    InternshipRecord,
    StudentAccountLink,
    StudentProfile,
    WxAccountBinding,
)
from app.modules.internship.services.internship_batch_context import batch_public_fields, resolve_batch
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.modules.internship.services import internship_stats_service as base_stats
from app.services.db_service import _tid, session


def _rate(num: int, den: int):
    return round(int(num) * 100.0 / int(den), 1) if den else None


def _ratio(key, label, numerator, denominator, *, note="", source=""):
    return {
        "key": key,
        "label": label,
        "numerator": int(numerator or 0),
        "denominator": int(denominator or 0),
        "rate": _rate(int(numerator or 0), int(denominator or 0)),
        "note": note,
        "source": source,
    }


def _visible(db, user, batch_id):
    batch = resolve_batch(db, batch_id, for_write=False)
    query = select(InternshipRecord, StudentProfile).join(
        StudentProfile,
        (StudentProfile.id == InternshipRecord.student_id)
        & (StudentProfile.tenant_id == InternshipRecord.tenant_id),
    ).where(
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.batch_id == batch.id,
        InternshipRecord.is_deleted.is_(False),
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    )
    scoped_ids = apply_internship_record_scope(
        select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        ),
        user,
    ).subquery()
    rows = db.execute(query.where(InternshipRecord.id.in_(select(scoped_ids.c.id)))).all()
    return batch, rows


def overview(user, *, batch_id) -> dict:
    with session() as db:
        batch, pairs = _visible(db, user, batch_id)
        records = [row for row, _student in pairs]
        students = [student for _row, student in pairs]
        record_ids = [int(row.id) for row in records]
        student_ids = [int(row.student_id) for row in records]
        total = len(records)

        application_facts = base_stats._latest_approved_application_facts(db, record_ids)
        report_task = base_stats._weekly_task_facts(
            db,
            [row for row in records if row.status in ("ONBOARD", "ASSESSING", "ARCHIVED")],
            batch,
        )

        # ── 概况：账号关系/移动绑定/当前在岗/风险 ──
        account_links = set()
        linked_user_ids = set()
        if student_ids:
            links = db.execute(select(
                StudentAccountLink.student_id,
                StudentAccountLink.user_id,
            ).where(
                StudentAccountLink.tenant_id == _tid(),
                StudentAccountLink.student_id.in_(student_ids),
                StudentAccountLink.link_status == "ACTIVE",
                StudentAccountLink.is_deleted.is_(False),
            )).all()
            for student_id, user_id in links:
                account_links.add(int(student_id))
                linked_user_ids.add(int(user_id))

        wx_bound_user_ids = set()
        if linked_user_ids:
            wx_bound_user_ids = set(db.scalars(select(WxAccountBinding.user_id).where(
                WxAccountBinding.tenant_id == _tid(),
                WxAccountBinding.user_id.in_(list(linked_user_ids)),
                WxAccountBinding.status == "ACTIVE",
                WxAccountBinding.is_deleted.is_(False),
            )).all())
        wx_bound_students = sum(
            1 for student_id, user_id in links
            if int(user_id) in {int(value) for value in wx_bound_user_ids}
        ) if student_ids else 0

        onboard = sum(1 for row in records if row.status in ("ONBOARD", "ASSESSING"))
        risk_students = sum(1 for row in records if str(row.risk_level or "NONE").upper() not in {"", "NONE"})

        overview_group = {
            "key": "overview",
            "label": "学校概况",
            "counters": [
                {"key": "students", "label": "实习学生", "value": total},
                {"key": "onboard", "label": "当前在岗/考核", "value": onboard},
                {"key": "risk", "label": "风险学生", "value": risk_students},
            ],
            "ratios": [
                _ratio(
                    "accountBindingRate", "校园账号绑定率", len(account_links), total,
                    note="学生主档存在 ACTIVE StudentAccountLink。",
                    source="t_student_account_link",
                ),
                _ratio(
                    "wechatBindingRate", "微信绑定率", wx_bound_students, len(account_links),
                    note="已绑定校园账号学生中存在 ACTIVE 微信账号绑定；无账号绑定时为暂无数据。",
                    source="t_wx_account_binding",
                ),
            ],
        }

        # ── 去向：类型分布 / 实际工作城市 / 已审批转企转岗 ──
        destination_counter = Counter(str(row.destination_type or "NONE").upper() for row in records)
        city_counter = Counter(
            str(app.work_city or "").strip()
            for app in application_facts.values()
            if str(app.work_city or "").strip()
        )
        changed_records = set()
        change_type_counter = Counter()
        if record_ids:
            changes = db.execute(select(
                InternshipChangeRequest.internship_id,
                InternshipChangeRequest.change_type,
            ).where(
                InternshipChangeRequest.tenant_id == _tid(),
                InternshipChangeRequest.internship_id.in_(record_ids),
                InternshipChangeRequest.status == "APPROVED",
                InternshipChangeRequest.change_type.in_((
                    "CHANGE_POSITION", "CHANGE_ENTERPRISE", "SELF_ARRANGED",
                )),
                InternshipChangeRequest.is_deleted.is_(False),
            )).all()
            for record_id, change_type in changes:
                changed_records.add(int(record_id))
                change_type_counter[str(change_type)] += 1

        destination_group = {
            "key": "destination",
            "label": "实习去向",
            "distribution": [
                {"key": key, "label": {
                    "ASSIGNED": "学校分配",
                    "SELF_ARRANGED": "自主实习",
                    "EXEMPTED": "免实习",
                    "NONE": "未落实",
                }.get(key, key), "value": int(destination_counter.get(key, 0))}
                for key in ("ASSIGNED", "SELF_ARRANGED", "EXEMPTED", "NONE")
            ],
            "ratios": [
                _ratio(
                    "transferRate", "转企/转岗率", len(changed_records), total,
                    note="分子为存在已审批换岗、换单位或转自主实习变更的不同实习记录。",
                    source="t_internship_change_request",
                ),
                _ratio(
                    "stabilityRate", "未发生转企转岗率",
                    max(0, total - len(changed_records)), total,
                    note="当前批次未出现已审批转企/转岗事实的实习记录。",
                    source="t_internship_change_request",
                ),
            ],
            "cityTop10": [
                {"city": city, "count": count}
                for city, count in city_counter.most_common(10)
            ],
            "cityKnownStudents": sum(city_counter.values()),
            "changeBreakdown": [
                {"key": key, "label": {
                    "CHANGE_ENTERPRISE": "换单位",
                    "CHANGE_POSITION": "换岗位",
                    "SELF_ARRANGED": "转自主实习",
                }.get(key, key), "count": int(value)}
                for key, value in sorted(change_type_counter.items())
            ],
        }

        # ── 活动：应交实交 / 打卡 / 指导巡访用现有已验证口径 ──
        base = base_stats.overview(user, batch_id=str(batch.id))
        metric_by_key = {item["key"]: item for item in base.get("metrics") or []}
        activity_keys = (
            "reportTaskCompletionRate",
            "checkinComplyRate",
            "guidanceCoverRate",
            "visitCoverRate",
        )
        activity_group = {
            "key": "activity",
            "label": "过程活动",
            "metrics": [metric_by_key[key] for key in activity_keys if key in metric_by_key],
            "weeklyReportTasks": {
                "expected": int(report_task["expectedTotal"]),
                "submitted": int(report_task["submittedTotal"]),
                "frequency": str(
                    ((batch.rules_config or {}).get("weeklyReport") or {}).get("frequency")
                    or "WEEKLY"
                ).upper(),
            },
        }

        # ── 质量：专业对口 / 工资 / 优秀率。工资多币种绝不混算。 ──
        major_known = {
            rid: app for rid, app in application_facts.items()
            if app.major_match is not None
        }
        major_yes = sum(1 for app in major_known.values() if app.major_match is True)

        wage_groups: dict[str, list[Decimal]] = defaultdict(list)
        if record_ids:
            wage_rows = db.execute(select(
                InternshipPayrollVersion.currency,
                InternshipPayrollVersion.actual_amount,
            ).join(
                InternshipPayrollStatement,
                InternshipPayrollStatement.current_version_id == InternshipPayrollVersion.id,
            ).where(
                InternshipPayrollStatement.tenant_id == _tid(),
                InternshipPayrollStatement.internship_id.in_(record_ids),
                InternshipPayrollStatement.is_deleted.is_(False),
                InternshipPayrollVersion.tenant_id == _tid(),
                InternshipPayrollVersion.is_current.is_(True),
                InternshipPayrollVersion.status == "APPROVED",
                InternshipPayrollVersion.is_deleted.is_(False),
            )).all()
            for currency, amount in wage_rows:
                if amount is not None:
                    wage_groups[str(currency or "CNY").upper()].append(Decimal(str(amount)))

        wage_by_currency = []
        for currency in sorted(wage_groups):
            values = wage_groups[currency]
            avg = (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.01"))
            wage_by_currency.append({
                "currency": currency,
                "count": len(values),
                "averageActualAmount": float(avg),
                "totalActualAmount": float(sum(values, Decimal("0")).quantize(Decimal("0.01"))),
            })

        score_rows = []
        if record_ids:
            score_rows = db.scalars(select(InternshipFinalScore).where(
                InternshipFinalScore.tenant_id == _tid(),
                InternshipFinalScore.internship_id.in_(record_ids),
                InternshipFinalScore.status == "PUBLISHED",
                InternshipFinalScore.is_deleted.is_(False),
                InternshipFinalScore.total_score.is_not(None),
            )).all()
        excellent = sum(1 for row in score_rows if float(row.total_score or 0) >= 90.0)

        quality_group = {
            "key": "quality",
            "label": "实习质量",
            "ratios": [
                _ratio(
                    "majorMatchRate", "专业对口率", major_yes, len(major_known),
                    note="只认已审核申请 major_match 明确真值；未知不默认。",
                    source="t_internship_application.major_match",
                ),
                _ratio(
                    "excellentRate", "优秀率", excellent, len(score_rows),
                    note="已发布且有总分的成绩中，总分>=90 的学生。",
                    source="t_internship_final_score",
                ),
            ],
            "wageByCurrency": wage_by_currency,
            "wageRecordCount": sum(len(values) for values in wage_groups.values()),
            "wageNote": "实际工资按币种分别统计，不跨币种求平均；约定报酬不作为实际发放工资。",
        }

        return {
            "schemaVersion": "YIYANG_PROCUREMENT_STATS_V1",
            **batch_public_fields(batch),
            "scope": {
                "recordCount": total,
                "recordIds": [str(value) for value in record_ids],
            },
            "groups": [
                overview_group,
                destination_group,
                activity_group,
                quality_group,
            ],
            "metricDefinitions": {
                "majorMatch": "正式申请 major_match 明确真值",
                "reportCompletion": "学生实习周期 × 批次周报频率的应交任务",
                "transfer": "APPROVED 变更申请（换岗位/换单位/转自主）",
                "wage": "当前 APPROVED 工资版本，按币种分组",
                "excellent": "PUBLISHED 总成绩>=90",
            },
        }
