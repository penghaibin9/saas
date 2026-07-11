"""岗位实习 · 统计中心（P3-B）。口径对齐《06 页面树》岗位实习业务指标矩阵。

15 项过程 + 结果指标 + 成绩分布 + 就业转化/帮扶/归档率（对接就业台账与归档中心）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.models import (College, EmpStudent, InternshipAgreement, InternshipArchive,
                        InternshipCheckin, InternshipEnterpriseEval, InternshipFinalScore,
                        InternshipGuidance, InternshipLeave, InternshipRecord,
                        InternshipStudentEval, InternshipVisit, Major, RiskRecord, SchoolClass,
                        StudentProfile, WeeklyReport)
from app.services.db_service import _iso, _tid, session

EMPLOYED_DEST = frozenset({"SIGNED", "FLEXIBLE", "FURTHER_STUDY", "ENLISTED", "STARTUP", "FREELANCE"})


def _scope_ctx(user):
    from app.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _org_of(db, stu, cache):
    """学生 → (学院名, 专业名, 班级名)。带缓存避免重复 join。"""
    if not stu or not stu.class_id:
        return ("", "", "")
    if stu.class_id in cache:
        return cache[stu.class_id]
    cls = db.get(SchoolClass, stu.class_id)
    college = major = cname = ""
    if cls:
        cname = cls.class_name or ""
        mj = db.get(Major, cls.major_id) if cls.major_id else None
        if mj:
            major = mj.major_name or ""
            col = db.get(College, mj.college_id) if mj.college_id else None
            if col:
                college = col.college_name or ""
    cache[stu.class_id] = (college, major, cname)
    return cache[stu.class_id]


def _rate(num, den):
    return round(num / den * 100, 1) if den else None


def _metric(key, label, num, den, threshold, note=""):
    rate = _rate(num, den)
    return {"key": key, "label": label, "numerator": num, "denominator": den,
            "rate": rate, "threshold": threshold,
            "warn": rate is not None and rate < threshold, "note": note}


def overview(user, college=None, major=None, class_name=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    scoped = scope.get("mode") == "SCOPED"
    with session() as db:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False))).all()
        cache = {}
        col_f = (college or "").strip()
        maj_f = (major or "").strip()
        cls_f = (class_name or "").strip()
        kept = []
        for r in recs:
            stu = db.get(StudentProfile, r.student_id)
            if scoped and not in_scope(scope, db, r, stu):
                continue
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
        assessing_arch = sum(1 for r in kept if r.status in ("ASSESSING", "ARCHIVED"))
        eval_base = sum(1 for r in kept if r.status in ("ONBOARD", "ASSESSING", "ARCHIVED"))

        def _cnt(model, *conds):
            return db.scalar(select(func.count()).select_from(model).where(
                model.tenant_id == _tid(), model.is_deleted.is_(False),
                model.internship_id.in_(rec_ids), *conds)) or 0

        def _distinct(model, *conds):
            return db.scalar(select(func.count(func.distinct(model.internship_id))).where(
                model.tenant_id == _tid(), model.is_deleted.is_(False),
                model.internship_id.in_(rec_ids), *conds)) or 0

        # ── 落实 / 匹配 / 协议 ──
        placed = sum(1 for r in kept if r.status in ("READY", "ONBOARD", "ASSESSING", "ARCHIVED")
                     or r.destination_type != "NONE")
        matched = sum(1 for r in kept if r.position_id or r.destination_type == "ASSIGNED")
        agr_signed = _distinct(InternshipAgreement, InternshipAgreement.status.in_(["EFFECTIVE", "ARCHIVED"]))
        # ── 打卡 / 请假 ──
        checkin_total = _cnt(InternshipCheckin)
        checkin_ok = _cnt(InternshipCheckin, InternshipCheckin.result.in_(["NORMAL", "RECORDED", "LEAVE"]))
        arrived = _distinct(InternshipCheckin)
        leave_total = _cnt(InternshipLeave)
        leave_ok = _cnt(InternshipLeave, InternshipLeave.status == "APPROVED")
        # ── 周报 ──
        weekly_total = _cnt(WeeklyReport)
        weekly_reviewed = _cnt(WeeklyReport, WeeklyReport.status.in_(["APPROVED", "RETURNED"]))
        weekly_stu = _distinct(WeeklyReport)
        # ── 指导 / 巡访 / 风险 ──
        guided = _distinct(InternshipGuidance, InternshipGuidance.status == "NORMAL")
        visited = _distinct(InternshipVisit)
        risk_total = _cnt(RiskRecord)
        risk_closed = _cnt(RiskRecord, RiskRecord.status == "CLOSED")
        risk_students = _distinct(RiskRecord, RiskRecord.status.in_(["PENDING_HANDLE", "PROCESSING"]))
        # ── 评价 / 成绩 ──
        ent_eval = _distinct(InternshipEnterpriseEval)
        stu_eval = _distinct(InternshipStudentEval, InternshipStudentEval.submit_status == "SUBMITTED")
        score_published = _cnt(InternshipFinalScore, InternshipFinalScore.status == "PUBLISHED")
        score_base = assessing_arch or total

        # ── 就业转化 / 帮扶 / 归档（对接就业台账 + 归档中心，不伪造）──
        cohort_ids = [r.student_id for r in kept if r.status in ("ASSESSING", "ARCHIVED")]
        cohort_n = len(cohort_ids)
        sid_filter = cohort_ids or [0]
        employed = db.scalar(select(func.count()).select_from(EmpStudent).where(
            EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
            EmpStudent.student_id.in_(sid_filter),
            EmpStudent.destination_type.in_(EMPLOYED_DEST))) or 0
        unemployed = db.scalar(select(func.count()).select_from(EmpStudent).where(
            EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
            EmpStudent.student_id.in_(sid_filter),
            EmpStudent.destination_type == "UNEMPLOYED")) or 0
        help_covered = db.scalar(select(func.count()).select_from(EmpStudent).where(
            EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
            EmpStudent.student_id.in_(sid_filter),
            EmpStudent.destination_type == "UNEMPLOYED",
            EmpStudent.employment_teacher.isnot(None),
            EmpStudent.employment_teacher != "")) or 0
        archived_cnt = db.scalar(select(func.count()).select_from(InternshipArchive).where(
            InternshipArchive.tenant_id == _tid(), InternshipArchive.is_deleted.is_(False),
            InternshipArchive.internship_id.in_(rec_ids),
            InternshipArchive.status == "ARCHIVED")) or 0
        archive_base = sum(1 for r in kept if r.status in ("ASSESSING", "ARCHIVED")) or total

        metrics = [
            _metric("placementRate", "实习落实率", placed, total, 95),
            _metric("matchRate", "岗位匹配率", matched, total, 90),
            _metric("agreementSignRate", "协议签署率", agr_signed, total, 95),
            _metric("arrivalRate", "到岗率", arrived, onboard, 90, "有打卡学生/在岗学生"),
            _metric("checkinComplyRate", "打卡合规率", checkin_ok, checkin_total, 85),
            _metric("leaveComplyRate", "请假合规率", leave_ok, leave_total, 95),
            _metric("weeklySubmitRate", "周报提交覆盖率", weekly_stu, onboard, 90, "有周报学生/在岗学生"),
            _metric("weeklyReviewRate", "周报批阅率", weekly_reviewed, weekly_total, 90),
            _metric("guidanceCoverRate", "指导覆盖率", guided, onboard, 95),
            _metric("visitCoverRate", "巡访覆盖率", visited, onboard, 90),
            _metric("riskCloseRate", "风险闭环率", risk_closed, risk_total, 95),
            _metric("enterpriseEvalRate", "企业评价完成率", ent_eval, eval_base, 95),
            _metric("studentEvalRate", "学生自评完成率", stu_eval, eval_base, 95),
            _metric("scorePublishRate", "成绩发布率", score_published, score_base, 100),
            _metric("employmentRate", "就业转化率", employed, cohort_n, 85,
                    "考核期/已归档学生中就业台账已落实（无台账时分母仍计）"),
            _metric("helpCoverRate", "未就业帮扶覆盖率", help_covered, unemployed, 90,
                    "未就业台账学生中已分配就业老师（无未就业台账时分母为0）"),
            _metric("archiveRate", "归档完成率", archived_cnt, archive_base, 95,
                    "考核期/已归档学生中已执行实习归档"),
        ]
        # 计数型（非比率）
        counters = [
            {"key": "totalStudents", "label": "实习学生数", "value": total},
            {"key": "onboardStudents", "label": "在岗学生数", "value": onboard},
            {"key": "riskStudents", "label": "风险学生数", "value": risk_students,
             "warn": risk_students > 0},
        ]
        # 成绩分布（仅已发布）
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
            "dimensions": {"college": col_f, "major": maj_f, "className": cls_f,
                           "scopeMode": scope.get("mode")},
            "counters": counters,
            "metrics": metrics,
            "scoreDistribution": dist,
            "partial": [],
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
        }


def dimension_options(user) -> dict:
    """可选学院/专业/班级（限当前数据范围内出现过的组织）。"""
    scope, in_scope = _scope_ctx(user)
    scoped = scope.get("mode") == "SCOPED"
    with session() as db:
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False))).all()
        cache = {}
        colleges, majors, classes = set(), set(), set()
        for r in recs:
            stu = db.get(StudentProfile, r.student_id)
            if scoped and not in_scope(scope, db, r, stu):
                continue
            oc, om, ocl = _org_of(db, stu, cache)
            if oc:
                colleges.add(oc)
            if om:
                majors.add(om)
            if ocl:
                classes.add(ocl)
        return {"colleges": sorted(colleges), "majors": sorted(majors), "classes": sorted(classes)}


def export_stats(user, college=None, major=None, class_name=None) -> dict:
    from app.services import xlsx_util
    data = overview(user, college=college, major=major, class_name=class_name)
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
    wm = f"岗位实习中心·统计报表（{dim}）· 导出人：{op} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("实习统计报表", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "实习统计报表.xlsx", len(rows))
