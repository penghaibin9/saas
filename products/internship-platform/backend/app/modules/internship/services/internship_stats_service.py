"""岗位实习 · 统计中心（P3-B）。口径对齐《06 页面树》岗位实习业务指标矩阵。

15 项过程 + 结果指标 + 成绩分布 + 就业转化/帮扶/归档率（对接就业台账与归档中心）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.tenant_scoped import tenant_get
from app.adapters.employment_gateway import employment_gateway
from app.models import (College, InternshipAgreement, InternshipApplication, InternshipArchive,
                        InternshipCheckin, InternshipEnterpriseEval, InternshipFinalScore,
                        InternshipGuidance, InternshipLeave, InternshipRecord,
                        InternshipStudentEval, InternshipVisit, Major, RiskRecord, SchoolClass,
                        StudentProfile, WeeklyReport)
from app.services.db_service import _iso, _tid, session
from app.modules.internship.services.internship_report_quality_service import (
    SUBMITTED_REPORT_STATUSES, required_report_counts,
)
from app.modules.internship.services.internship_scope import apply_internship_record_scope

METRIC_VERSION = "internship-stats-v2"

# This is deliberately API data rather than a front-end-only legend: the same
# definitions travel with overview and drill-down results.
METRIC_DEFINITIONS = {
    "placementRate": {"key": "placementRate", "label": "实习落实率", "numeratorLabel": "已落实去向学生", "denominatorLabel": "本批次实习学生", "threshold": 95, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "去向为已分配岗位、自主实习或免实习的学生。"},
    "matchRate": {"key": "matchRate", "label": "岗位匹配率", "numeratorLabel": "已分配岗位学生", "denominatorLabel": "本批次实习学生", "threshold": 90, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "已分配岗位学生。"},
    "majorMatchRate": {"key": "majorMatchRate", "label": "专业对口率", "numeratorLabel": "明确专业对口学生", "denominatorLabel": "已确认专业对口事实学生", "threshold": 80, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "仅使用正式实习申请 major_match 明确真值；未知不默认是/否，也不以岗位分配率替代。"},
    "reportTaskCompletionRate": {"key": "reportTaskCompletionRate", "label": "周报任务完成率", "numeratorLabel": "按应交口径已提交周报篇数", "denominatorLabel": "按批次配置应交篇数", "threshold": 90, "emptyPolicy": "null", "distinctKey": "weeklyReportUnit", "note": "与报告应交台账使用同一批次配置及可见学生范围；0或未配置不计算完成率。按已提交原单计数，排除草稿和删除，退回、重交不另增篇数，每人最多计入应交数。"},
    "agreementSignRate": {"key": "agreementSignRate", "label": "协议签署率", "numeratorLabel": "已生效协议学生", "denominatorLabel": "本批次实习学生", "threshold": 95, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "协议状态为生效或已归档。"},
    "arrivalRate": {"key": "arrivalRate", "label": "到岗率", "numeratorLabel": "有有效打卡学生", "denominatorLabel": "应在岗学生", "threshold": 90, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "应在岗学生为状态 ONBOARD、ASSESSING、ARCHIVED；分子为该队列中至少一条有效打卡的不同实习记录，避免历史打卡与当前在岗状态混算。"},
    "checkinComplyRate": {"key": "checkinComplyRate", "label": "打卡合规率", "numeratorLabel": "合规打卡", "denominatorLabel": "全部打卡", "threshold": 85, "emptyPolicy": "null", "distinctKey": "checkinId", "note": "正常、补录或请假打卡为合规。"},
    "leaveComplyRate": {"key": "leaveComplyRate", "label": "请假合规率", "numeratorLabel": "已审批请假", "denominatorLabel": "全部请假", "threshold": 95, "emptyPolicy": "null", "distinctKey": "leaveId", "note": "已审批请假占全部请假。"},
    "weeklySubmitRate": {"key": "weeklySubmitRate", "label": "周报提交覆盖率", "numeratorLabel": "有周报学生", "denominatorLabel": "在岗或考核中学生", "threshold": 90, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "有周报学生覆盖率，不代表按应交周次的提交率；分母为 ONBOARD、ASSESSING 学生。"},
    "weeklyReviewRate": {"key": "weeklyReviewRate", "label": "周报批阅率", "numeratorLabel": "已批阅周报", "denominatorLabel": "已提交周报", "threshold": 90, "emptyPolicy": "null", "distinctKey": "weeklyReportId", "note": "已通过或退回的周报。"},
    "guidanceCoverRate": {"key": "guidanceCoverRate", "label": "指导覆盖率", "numeratorLabel": "有指导学生", "denominatorLabel": "在岗学生", "threshold": 95, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "正常指导记录覆盖。"},
    "visitCoverRate": {"key": "visitCoverRate", "label": "巡访覆盖率", "numeratorLabel": "有巡访学生", "denominatorLabel": "在岗学生", "threshold": 90, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "巡访记录覆盖。"},
    "riskCloseRate": {"key": "riskCloseRate", "label": "风险闭环率", "numeratorLabel": "已关闭风险", "denominatorLabel": "全部风险", "threshold": 95, "emptyPolicy": "null", "distinctKey": "riskId", "note": "风险工单闭环率。"},
    "enterpriseEvalRate": {"key": "enterpriseEvalRate", "label": "企业评价完成率", "numeratorLabel": "完成企业评价学生", "denominatorLabel": "考核或归档学生", "threshold": 95, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "仅对进入考核或已归档学生计算。"},
    "studentEvalRate": {"key": "studentEvalRate", "label": "学生自评完成率", "numeratorLabel": "已提交自评学生", "denominatorLabel": "考核或归档学生", "threshold": 95, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "仅对进入考核或已归档学生计算。"},
    "scorePublishRate": {"key": "scorePublishRate", "label": "成绩发布率", "numeratorLabel": "已发布成绩", "denominatorLabel": "考核或归档学生", "threshold": 100, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "空分母返回暂无数据。"},
    "employmentRate": {"key": "employmentRate", "label": "就业转化率", "numeratorLabel": "就业落实学生", "denominatorLabel": "考核或归档学生", "threshold": 85, "emptyPolicy": "null", "distinctKey": "studentId", "note": "就业台账已落实。"},
    "helpCoverRate": {"key": "helpCoverRate", "label": "未就业帮扶覆盖率", "numeratorLabel": "已分配就业老师", "denominatorLabel": "未就业学生", "threshold": 90, "emptyPolicy": "null", "distinctKey": "studentId", "note": "未就业台账学生中已分配就业老师。"},
    "archiveRate": {"key": "archiveRate", "label": "归档完成率", "numeratorLabel": "已实习归档学生", "denominatorLabel": "考核或归档学生", "threshold": 95, "emptyPolicy": "null", "distinctKey": "internshipId", "note": "实习归档记录已归档。"},
}

# 2026-10-14 用户确认：分母为本批次已分配学生，按稳定指导教师关系认定。
for _coverage_key in ('guidanceCoverRate','visitCoverRate'):
    METRIC_DEFINITIONS[_coverage_key].update(denominatorLabel='本批次已分配指导教师的学生',
        note='按本批次已分配指导教师的学生去重；分子仅计该范围内有有效记录的学生。考核、归档后仍保留在本批次分母。')
METRIC_DEFINITIONS['arrivalRate']['note']='应在岗范围含在岗、考核中和已归档学生；分子为其中有有效打卡的不同学生。'
METRIC_DEFINITIONS['weeklySubmitRate']['note']='在岗或考核中学生中，有正式提交周报的学生；草稿不算提交。'
METRIC_DEFINITIONS['majorMatchRate']['note']='只使用正式已批准申请中的专业对口事实，未知不默认对口或不对口。'
METRIC_DEFINITIONS['majorMatchRate']['sourceField']='major_match'


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope
    return _current_scope(user)


def _org_of(db, stu, cache):
    if not stu or stu.tenant_id != _tid():return ("", "", "")
    key=('student',stu.id)
    if key not in cache:cache.update(_preload_org_cache(db,[stu]))
    return cache.get(key,("", "", ""))


def _preload_org_cache(db, students):
    """与正式数据范围一致：学生直挂组织优先，班级关系兜底，所有引用须同校有效。"""
    students=[stu for stu in students if stu is not None and stu.tenant_id==_tid()]
    def load(model,ids):
        return {row.id:row for row in db.scalars(select(model).where(model.tenant_id==_tid(),
            model.is_deleted.is_(False),model.id.in_(ids))).all()} if ids else {}
    classes=load(SchoolClass,{stu.class_id for stu in students if stu.class_id})
    majors=load(Major,{stu.major_id for stu in students if stu.major_id}|{row.major_id for row in classes.values() if row.major_id})
    colleges=load(College,{stu.college_id for stu in students if stu.college_id}|{row.college_id for row in majors.values() if row.college_id})
    cache={}
    for stu in students:
        cls=classes.get(stu.class_id)
        major=majors.get(stu.major_id) or (majors.get(cls.major_id) if cls else None)
        college=colleges.get(stu.college_id) or (colleges.get(major.college_id) if major else None)
        cache[('student',stu.id)]=(college.college_name if college else '',major.major_name if major else '',cls.class_name if cls else '')
    return cache

def _rate(num, den):
    return round(num / den * 100, 1) if den else None


def _metric(key, label, num, den, threshold, note=""):
    rate = _rate(num, den)
    anomaly = num > den
    if anomaly:
        rate = None
    return {"key": key, "label": label, "numerator": num, "denominator": den,
            "rate": rate, "threshold": threshold,
            "warn": rate is not None and rate < threshold, "anomaly": anomaly,
            "definition": METRIC_DEFINITIONS.get(key), "note": note or METRIC_DEFINITIONS.get(key, {}).get("note", "")}


def _latest_approved_application_facts(db, record_ids: list[int]) -> dict[int, InternshipApplication]:
    """One approved legacy/self-arranged application fact per internship record.

    Recruitment-campaign rows are excluded here because G14 needs the explicitly confirmed
    major_match fact carried by the formal application snapshot. Unknown stays unknown.
    """
    ids = [int(value) for value in record_ids if value]
    if not ids:
        return {}
    rows = db.scalars(select(InternshipApplication).where(
        InternshipApplication.tenant_id == _tid(),
        InternshipApplication.campaign_id.is_(None),
        InternshipApplication.is_deleted.is_(False),
        InternshipApplication.status == "APPROVED",
        InternshipApplication.record_id.in_(ids),
    ).order_by(
        InternshipApplication.record_id,
        InternshipApplication.reviewed_at.desc(),
        InternshipApplication.id.desc(),
    )).all()
    out = {}
    for row in rows:
        rid = int(row.record_id or 0)
        if rid and rid not in out:
            out[rid] = row
    return out


def _weekly_task_facts(db, records: list[InternshipRecord], batch) -> dict:
    required = required_report_counts(batch)["weeklyRequiredCount"]
    student_ids = {int(row.student_id) for row in records}
    live_students = set(db.scalars(select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        StudentProfile.id.in_(student_ids),
    )).all()) if student_ids else set()
    expected_by_record = {
        int(row.id): required for row in records if row.student_id in live_students
    }
    valid_ids = list(expected_by_record)
    submitted_by_record = {rid: 0 for rid in expected_by_record}
    if valid_ids:
        rows = db.execute(select(
            WeeklyReport.internship_id,
            func.count(WeeklyReport.id),
        ).where(
            WeeklyReport.tenant_id == _tid(),
            WeeklyReport.is_deleted.is_(False),
            WeeklyReport.internship_id.in_(valid_ids),
            WeeklyReport.status.in_(SUBMITTED_REPORT_STATUSES),
        ).group_by(WeeklyReport.internship_id)).all()
        for rid, count in rows:
            submitted_by_record[int(rid)] = int(count or 0)
    expected_total = sum(expected_by_record.values())
    # Extra historical rows cannot raise completion above the authoritative planned units.
    submitted_total = sum(
        min(int(submitted_by_record.get(rid, 0)), int(expected or 0))
        for rid, expected in expected_by_record.items()
    )
    return {
        "expectedByRecord": expected_by_record,
        "submittedByRecord": submitted_by_record,
        "expectedTotal": expected_total,
        "submittedTotal": submitted_total,
    }


def _metric_members(db, records, application_facts, report_task):
    """分子/分母都保留逐实习贡献，图表与下钻共用；篇数不能冒充人数。"""
    ids={row.id for row in records}
    ones=lambda values:{int(value):1 for value in values}
    all_members=ones(ids)
    onsite=ones(row.id for row in records if row.status in {'ONBOARD','ASSESSING','ARCHIVED'})
    assessing=ones(row.id for row in records if row.status in {'ASSESSING','ARCHIVED'})
    weekly_base=ones(row.id for row in records if row.status in {'ONBOARD','ASSESSING'})
    def counts(model,*conditions,distinct=False):
        rows=db.execute(select(model.internship_id,func.count()).where(model.tenant_id==_tid(),
            model.is_deleted.is_(False),model.internship_id.in_(ids or {0}),*conditions).group_by(model.internship_id)).all()
        return {int(rid):1 if distinct else int(value) for rid,value in rows}
    def within(values,cohort):return {key:value for key,value in values.items() if key in cohort}
    required={rid:value for rid,value in report_task['expectedByRecord'].items() if value>0}
    submitted={rid:min(value,required.get(rid,0)) for rid,value in report_task['submittedByRecord'].items() if min(value,required.get(rid,0))>0}
    return {
        'placementRate':(ones(r.id for r in records if r.destination_type in {'ASSIGNED','SELF_ARRANGED','EXEMPTED'}),all_members),
        'matchRate':(ones(r.id for r in records if r.position_id or r.destination_type=='ASSIGNED'),all_members),
        'majorMatchRate':(ones(rid for rid,app in application_facts.items() if app.major_match is True),ones(rid for rid,app in application_facts.items() if app.major_match is not None)),
        'reportTaskCompletionRate':(submitted,required),
        'agreementSignRate':(counts(InternshipAgreement,InternshipAgreement.status.in_(('EFFECTIVE','ARCHIVED')),distinct=True),all_members),
        'arrivalRate':(within(counts(InternshipCheckin,InternshipCheckin.result.in_(('NORMAL','RECORDED','LEAVE')),distinct=True),onsite),onsite),
        'checkinComplyRate':(counts(InternshipCheckin,InternshipCheckin.result.in_(('NORMAL','RECORDED','LEAVE'))),counts(InternshipCheckin)),
        'leaveComplyRate':(counts(InternshipLeave,InternshipLeave.status.in_(('APPROVED','RETURNED'))),counts(InternshipLeave)),
        'weeklySubmitRate':(within(counts(WeeklyReport,WeeklyReport.status.in_(SUBMITTED_REPORT_STATUSES),distinct=True),weekly_base),weekly_base),
        'weeklyReviewRate':(counts(WeeklyReport,WeeklyReport.status.in_(('APPROVED','RETURNED'))),counts(WeeklyReport,WeeklyReport.status.in_(SUBMITTED_REPORT_STATUSES))),
        'guidanceCoverRate':(within(counts(InternshipGuidance,InternshipGuidance.status=='NORMAL',distinct=True),ones(r.id for r in records if r.advisor_user_id)),ones(r.id for r in records if r.advisor_user_id)),
        'visitCoverRate':(within(counts(InternshipVisit,distinct=True),ones(r.id for r in records if r.advisor_user_id)),ones(r.id for r in records if r.advisor_user_id)),
        'riskCloseRate':(counts(RiskRecord,RiskRecord.status=='CLOSED'),counts(RiskRecord)),
        'enterpriseEvalRate':(within(counts(InternshipEnterpriseEval,distinct=True),assessing),assessing),
        'studentEvalRate':(within(counts(InternshipStudentEval,InternshipStudentEval.submit_status=='SUBMITTED',distinct=True),assessing),assessing),
        'scorePublishRate':(within(counts(InternshipFinalScore,InternshipFinalScore.status=='PUBLISHED',distinct=True),assessing),assessing),
        'archiveRate':(within(counts(InternshipArchive,InternshipArchive.status=='ARCHIVED',distinct=True),assessing),assessing),
    }


def overview(user, college=None, major=None, class_name=None, batch_id=None) -> dict:
    from app.modules.internship.services.internship_batch_context import (
        batch_public_fields, resolve_batch)
    scope = _scope_ctx(user)
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        query = select(InternshipRecord, StudentProfile).outerjoin(StudentProfile,
            (StudentProfile.id == InternshipRecord.student_id) &
            (StudentProfile.tenant_id == InternshipRecord.tenant_id)).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id,
        )
        recs = db.execute(apply_internship_record_scope(query, user, resolved_scope=scope)).all()
        recs=[(rec,stu) for rec,stu in recs if stu is not None and not stu.is_deleted]
        cache = _preload_org_cache(db, [stu for _rec, stu in recs])
        col_f = (college or "").strip()
        maj_f = (major or "").strip()
        cls_f = (class_name or "").strip()
        kept = []
        for r, stu in recs:
            if col_f or maj_f or cls_f:
                oc, om, ocl = _org_of(db, stu, cache)
                if col_f and col_f != oc:
                    continue
                if maj_f and maj_f != om:
                    continue
                if cls_f and cls_f != ocl:
                    continue
            kept.append(r)
        rec_ids = [r.id for r in kept] or [0]
        total = len(kept)
        onboard = sum(1 for r in kept if r.status == "ONBOARD")

        application_facts = _latest_approved_application_facts(db, [r.id for r in kept])
        major_match_known = {
            rid: app for rid, app in application_facts.items()
            if app.major_match is not None
        }
        major_match_den = len(major_match_known)
        major_match_num = sum(1 for app in major_match_known.values() if app.major_match is True)
        report_task = _weekly_task_facts(
            db,
            kept,
            batch,
        )

        risk_students = db.scalar(select(func.count(func.distinct(RiskRecord.internship_id))).where(
            RiskRecord.tenant_id == _tid(), RiskRecord.is_deleted.is_(False),
            RiskRecord.internship_id.in_(rec_ids), RiskRecord.status.in_(("PENDING_HANDLE","PROCESSING")))) or 0
        cohort_ids = [int(r.student_id) for r in kept if r.status in ("ASSESSING", "ARCHIVED")]
        employment = employment_gateway.cohort_metrics(cohort_ids)
        employment_configured = bool(employment.get("configured"))
        members = _metric_members(db, kept, application_facts, report_task)
        metrics = []
        for key, definition in METRIC_DEFINITIONS.items():
            if key in members:
                numerator, denominator = members[key]
                metric = _metric(key, definition['label'], sum(numerator.values()),
                    sum(denominator.values()), definition['threshold'])
                metric['drilldownAvailable'] = True
            elif key in {'employmentRate','helpCoverRate'}:
                num = int(employment.get('employed' if key=='employmentRate' else 'helpCovered') or 0)
                den = (len(cohort_ids) if key=='employmentRate' else int(employment.get('unemployed') or 0)) if employment_configured else 0
                metric = _metric(key, definition['label'], num, den, definition['threshold'])
                metric['drilldownAvailable'] = False
            else:
                continue
            metrics.append(metric)
        counters = [
            {"key": "totalStudents", "label": "实习学生数", "value": total},
            {"key": "onboardStudents", "label": "在岗学生数", "value": onboard},
            {"key": "riskStudents", "label": "风险学生数", "value": risk_students,
             "warn": risk_students > 0},
        ]
        buckets = [("优(90-100)", 90, 101), ("良(80-89)", 80, 90), ("中(70-79)", 70, 80),
                   ("及格(60-69)", 60, 70), ("不及格(<60)", -1, 60)]
        dist = []
        for label, lo, hi in buckets:
            c = db.scalar(select(func.count()).select_from(InternshipFinalScore).where(
                InternshipFinalScore.tenant_id == _tid(), InternshipFinalScore.is_deleted.is_(False),
                InternshipFinalScore.internship_id.in_(rec_ids),
                InternshipFinalScore.status == "PUBLISHED",
                InternshipFinalScore.total_score >= lo, InternshipFinalScore.total_score < hi)) or 0
            dist.append({"bucket": label, "count": c})

        return {
            "metricVersion": METRIC_VERSION,
            "appliedFilters": {"batchId": str(batch.id), "college": col_f, "major": maj_f,
                               "className": cls_f, "scopeMode": scope.get("mode")},
            "dimensions": {"college": col_f, "major": maj_f, "className": cls_f,
                           "scopeMode": scope.get("mode"), **batch_public_fields(batch)},
            "counters": counters,
            "metrics": metrics,
            "scoreDistribution": dist,
            "procurementFacts": {
                "majorMatch": {
                    "knownStudents": major_match_den,
                    "matchedStudents": major_match_num,
                    "unknownStudents": max(0, total - major_match_den),
                },
                "weeklyReportTasks": {
                    "expected": report_task["expectedTotal"],
                    "submitted": report_task["submittedTotal"],
                    "frequency": str(((batch.rules_config or {}).get("weeklyReport") or {}).get("frequency") or "WEEKLY").upper(),
                },
            },
            "partial": ([] if employment_configured else [{
                "key": "employment",
                "status": employment.get("status") or "NOT_CONFIGURED",
                "message": "就业及帮扶统计暂不可用。",
            }]),
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            **batch_public_fields(batch),
        }


def _record_export(user,name,total,filters,sensitive_fields=None):
    from app.modules.internship.services.internship_export_util import write_export_audit
    with session() as db:
        write_export_audit(db,name,total,user=user,filters=filters,sensitive_fields=sensitive_fields)
        db.commit()


def export_metric_drilldown(user,metric_key,subset,**filters):
    from app.services import xlsx_util
    from app.core.exceptions import AppException
    data=metric_drilldown(user,metric_key,subset,page=1,page_size=10001,**filters)
    if data['total']>10000:
        raise AppException('DATA_CONFLICT','明细超过一万行，请缩小统计范围后导出')
    columns=[('studentName','学生姓名'),('studentNo','学号'),('college','院系'),('major','专业'),('className','班级'),('contribution','本指标计入数量')]
    rows=[[row.get(key) for key,_ in columns] for row in data['items']]
    name=data['definition']['label']+('分子明细' if subset=='numerator' else '分母明细')
    content=xlsx_util.build_ledger_xlsx(name,[label for _,label in columns],rows,watermark='统计明细 · 同条件导出')
    _record_export(user,name,len(rows),{**filters,'metric':metric_key,'subset':subset},['studentName','studentNo'])
    return xlsx_util.pack_xlsx_result(content,name+'.xlsx',len(rows))


def metric_definitions() -> dict:
    return {"metricVersion": METRIC_VERSION, "definitions": list(METRIC_DEFINITIONS.values()),
            "appliedFilters": {},
            "generatedAt": datetime.now().isoformat(timespec="seconds")}


def metric_drilldown(user, metric_key, subset, page=1, page_size=20, college=None,
                     major=None, class_name=None, batch_id=None) -> dict:
    """Return record rows from the exact visible overview cohort.

    The subset is intentionally record-oriented even when a metric's numerator
    is an event count; this preserves distinct-student denominator semantics.
    """
    if metric_key not in METRIC_DEFINITIONS:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "未知统计指标")
    if subset not in ("numerator", "denominator"):
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "subset 必须为 numerator 或 denominator")
    from app.modules.internship.services.internship_batch_context import batch_public_fields, resolve_batch
    scope = _scope_ctx(user)
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        query = select(InternshipRecord, StudentProfile).outerjoin(StudentProfile,
            (StudentProfile.id == InternshipRecord.student_id) &
            (StudentProfile.tenant_id == InternshipRecord.tenant_id)).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id)
        records = db.execute(apply_internship_record_scope(query, user, resolved_scope=scope)).all()
        records=[(rec,stu) for rec,stu in records if stu is not None and not stu.is_deleted]
        cache, kept = _preload_org_cache(db, [stu for _rec, stu in records]), []
        for rec, stu in records:
            org = _org_of(db, stu, cache)
            if (college and college != org[0]) or (major and major != org[1]) or (class_name and class_name != org[2]):
                continue
            kept.append(rec)
        application_facts = _latest_approved_application_facts(db, [r.id for r in kept])
        report_task = _weekly_task_facts(db, kept, batch)
        members=_metric_members(db,kept,application_facts,report_task)
        from app.core.exceptions import AppException
        if metric_key not in members:
            raise AppException('DATA_CONFLICT','该指标尚无可追溯的明细来源，不能生成名单')
        contributions=members[metric_key][0 if subset=='numerator' else 1]
        chosen=set(contributions)
        selected = [r for r in kept if r.id in chosen]
        selected.sort(key=lambda r: (r.updated_at or datetime.min, r.id), reverse=True)
        start = (max(1, int(page)) - 1) * int(page_size)
        rows = []
        for rec in selected[start:start + int(page_size)]:
            stu = tenant_get(db, StudentProfile, rec.student_id)
            org = _org_of(db, stu, cache)
            app_fact = application_facts.get(int(rec.id))
            rows.append({
                "internshipId": str(rec.id), "studentId": str(rec.student_id),
                "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
                "status": rec.status, "college": org[0], "major": org[1], "className": org[2],
                "majorMatch": app_fact.major_match if app_fact is not None else None,
                "weeklyExpected": int(report_task["expectedByRecord"].get(int(rec.id), 0)),
                "weeklySubmitted": int(report_task["submittedByRecord"].get(int(rec.id), 0)),
                "contribution":contributions[rec.id],
            })
        return {"metricVersion": METRIC_VERSION, "definition": METRIC_DEFINITIONS[metric_key],
                "subset": subset, "total": len(selected), "totalValue":sum(contributions.values()), "items": rows, "page": int(page),
                "pageSize": int(page_size), "appliedFilters": {"batchId": str(batch.id), "college": college or "",
                "major": major or "", "className": class_name or "", "scopeMode": scope.get("mode")},
                "generatedAt": datetime.now().isoformat(timespec="seconds"), **batch_public_fields(batch)}


def dimension_options(user, batch_id=None) -> dict:
    """可选学院/专业/班级（限当前批次 + 数据范围内出现过的组织）。"""
    from app.modules.internship.services.internship_batch_context import resolve_batch
    scope = _scope_ctx(user)
    with session() as db:
        batch = resolve_batch(db, batch_id, for_write=False)
        query = select(InternshipRecord, StudentProfile).outerjoin(StudentProfile,
            (StudentProfile.id == InternshipRecord.student_id) &
            (StudentProfile.tenant_id == InternshipRecord.tenant_id)).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id == batch.id)
        recs = db.execute(apply_internship_record_scope(query, user, resolved_scope=scope)).all()
        cache = _preload_org_cache(db, [stu for _rec, stu in recs])
        colleges, majors, classes = set(), set(), set()
        for r, stu in recs:
            oc, om, ocl = _org_of(db, stu, cache)
            if oc:
                colleges.add(oc)
            if om:
                majors.add(om)
            if ocl:
                classes.add(ocl)
        return {"colleges": sorted(colleges), "majors": sorted(majors), "classes": sorted(classes)}


def trends(user, college=None, major=None, class_name=None, months=6, batch_id=None) -> dict:
    """按学校自然月汇总同一可见范围，登记量与报告当前原单不混作人数。"""
    from app.core.timeutil import local_now,local_day_bounds_utc,iso_utc,utc_now
    from sqlalchemy import case
    from app.modules.internship.services.internship_procurement_stats_service import _visible
    months=max(3,min(int(months or 6),12))
    now=local_now();keys=[];year,month=now.year,now.month
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}");month-=1
        if month==0:year,month=year-1,12
    keys.reverse()
    bounds=[]
    for key in keys:
        start=datetime.strptime(key+'-01','%Y-%m-%d')
        end=datetime(start.year+1,1,1) if start.month==12 else datetime(start.year,start.month+1,1)
        bounds.append((local_day_bounds_utc(start)[0],local_day_bounds_utc(end)[0]))
    with session() as db:
        batch,pairs=_visible(db,user,batch_id,college,major,class_name)
        ids=[record.id for record,_ in pairs] or [0]
        def points_for(model,field,record=False):
            columns=[func.coalesce(func.sum(case((and_(field>=start,field<end),1),else_=0)),0) for start,end in bounds]
            query=select(*columns).where(model.tenant_id==_tid(),model.is_deleted.is_(False),
                (model.id if record else model.internship_id).in_(ids),field>=bounds[0][0],field<bounds[-1][1])
            if model is WeeklyReport:query=query.where(WeeklyReport.status.in_(SUBMITTED_REPORT_STATUSES))
            values=db.execute(query).one()
            return [{'month':key,'value':int(value or 0)} for key,value in zip(keys,values)]
        return {'months':keys,'series':[
            {'key':'records','label':'新增实习建档','points':points_for(InternshipRecord,InternshipRecord.created_at,True)},
            {'key':'reports','label':'周报提交','points':points_for(WeeklyReport,WeeklyReport.submitted_at)},
            {'key':'guidance','label':'指导登记','points':points_for(InternshipGuidance,InternshipGuidance.created_at)},
            {'key':'visits','label':'巡访登记','points':points_for(InternshipVisit,InternshipVisit.created_at)}],
            'generatedAt':iso_utc(utc_now()),'batchId':str(batch.id)}

def export_stats(user, college=None, major=None, class_name=None, batch_id=None) -> dict:
    from app.services import xlsx_util
    data = overview(user, college=college, major=major, class_name=class_name, batch_id=batch_id)
    headers = ["指标", "分子", "分母", "达成率(%)", "预警阈值(%)", "是否预警"]
    rows = [[m["label"], m["numerator"], m["denominator"],
             "—" if m["rate"] is None else m["rate"], m["threshold"], "是" if m["warn"] else "否"]
            for m in data["metrics"]]
    for c in data["counters"]:
        rows.append([c["label"], "—", "—", c["value"], "—", "是" if c.get("warn") else "否"])
    for d in data["scoreDistribution"]:
        rows.append([f"成绩分布·{d['bucket']}", "—", "—", d["count"], "—", "否"])
    op = (user or {}).get("realName") or "系统"
    dim = "/".join([x for x in [college, major, class_name] if x]) or "全部范围"
    bname = data.get("batchName") or ""
    wm = (f"岗位实习中心·统计报表（{bname}/{dim}）· 导出人：{op} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("实习统计报表", headers, rows, watermark=wm)
    _record_export(user,'实习统计报表',len(rows),data['appliedFilters'])
    return xlsx_util.pack_xlsx_result(content, "实习统计报表.xlsx", len(rows))
