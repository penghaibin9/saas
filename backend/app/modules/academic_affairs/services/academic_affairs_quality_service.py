"""13B 教学质量 service（零新表；R9 冻结范围仅"质量统计看板 + 质量报告导出"两项）。

施工卡 D-03/D-06：不建任何 t_aa_quality* 表。质量指标全部实时聚合既有表；
报告导出复用 xlsx_util，导出历史用 AffairsAuditTrail(biz_type=AA_QUALITY_REPORT) 记录。
其余 7 项三级（督导听课/巡课/教学检查/教学事故/质量整改/整改跟进/质量归档）本轮范围外(planned)。
"""
from __future__ import annotations

from datetime import datetime

from app.core.affairs_security import build_affairs_context
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_QUALITY_REPORT", biz_id=None, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990], occurred_at=datetime.utcnow()))


def _rate(num, den):
    return round(num / den * 100, 2) if den else 0.0


def _ind(key, label, value, unit="", num=None, den=None, rate=None, drill=None, applied=None):
    """applied: 本指标真实生效的筛选维度列表（term/college/major）——
    未生效的维度前端必须提示"该指标不支持按X筛选"，禁止让用户以为筛选过了。"""
    return {"key": key, "label": label, "value": value, "unit": unit,
            "numerator": num, "denominator": den, "rate": rate, "drillRoute": drill,
            "appliedFilters": applied or []}


def _class_ids(db, college_id=None, major_id=None):
    """学院/专业 → 行政班 id 集合（班级→专业→学院链）。无筛选返回 None（不过滤）。"""
    from app.models import Major, SchoolClass
    if not college_id and not major_id:
        return None
    q = db.query(SchoolClass.id).join(Major, SchoolClass.major_id == Major.id).filter(
        SchoolClass.tenant_id == _tid())
    if major_id:
        q = q.filter(Major.id == int(major_id))
    if college_id:
        q = q.filter(Major.college_id == int(college_id))
    return [cid for (cid,) in q.all()]


def _profile_ids(db, college_id=None, major_id=None):
    """学院/专业 → 学生主档 id 集合。无筛选返回 None。"""
    from app.models import StudentProfile
    if not college_id and not major_id:
        return None
    q = db.query(StudentProfile.id).filter(StudentProfile.tenant_id == _tid(),
                                           StudentProfile.is_deleted.is_(False))
    if college_id:
        q = q.filter(StudentProfile.college_id == int(college_id))
    if major_id:
        q = q.filter(StudentProfile.major_id == int(major_id))
    return [pid for (pid,) in q.all()]


def _acad_ids(db, profile_ids):
    """学生主档 id → 学业台账(t_acad_student) id 集合（AcademicGrade/Warning 挂在台账上）。"""
    from app.models import AcademicStudent
    if profile_ids is None:
        return None
    if not profile_ids:
        return []
    return [aid for (aid,) in db.query(AcademicStudent.id).filter(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id.in_(profile_ids)).all()]


def dashboard(user, term_id=None, college_id=None, major_id=None):
    """质量指标看板（实时聚合既有表，筛选真实生效）。

    每个指标底层表支持的筛选维度不同：能过滤的维度真过滤，不支持的维度在
    appliedFilters 中如实缺席（如挂科率的学期维度——成绩表的学期是自由文本，
    与学期 id 无可靠映射，宁可声明不支持也不给错数）。
    """
    from app.models import (AaCourse, AaGradeTask, AaGraduationAuditResult, AaProgram,
                            AaScheduleChange, AaTeachingTask, AaTeachingTaskBatch,
                            AcademicGrade, AcademicWarning, Major, SchoolClass)
    with session() as db:
        build_affairs_context(user, db)
        T = _tid()
        term_id = int(term_id) if term_id else None
        college_id = int(college_id) if college_id else None
        major_id = int(major_id) if major_id else None
        has_org = bool(college_id or major_id)
        org_dims = (["college"] if college_id else []) + (["major"] if major_id else [])

        class_ids = _class_ids(db, college_id, major_id)      # None=不过滤
        profile_ids = _profile_ids(db, college_id, major_id)
        acad_ids = _acad_ids(db, profile_ids)
        inds = []

        # 挂科率：按学生台账收敛学院/专业；学期为自由文本无法可靠映射 → 不支持
        gq = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == T,
                                            AcademicGrade.record_status == "ACTIVE")
        if acad_ids is not None:
            gq = gq.filter(AcademicGrade.acad_student_id.in_(acad_ids or [0]))
        fail = gq.filter(AcademicGrade.pass_status.in_(["FAIL", "FAILED"])).count()
        total_g = gq.count()
        inds.append(_ind("failRate", "挂科率", _rate(fail, total_g), "%", fail, total_g,
                         _rate(fail, total_g), "aa-grades", applied=org_dims))

        # 在办学业预警：按学生台账收敛学院/专业
        wq = db.query(AcademicWarning).filter(AcademicWarning.tenant_id == T,
                                              AcademicWarning.status != "CLOSED",
                                              AcademicWarning.record_status == "ACTIVE")
        if acad_ids is not None:
            wq = wq.filter(AcademicWarning.acad_student_id.in_(acad_ids or [0]))
        inds.append(_ind("warningCount", "在办学业预警", wq.count(), "条",
                         drill="aa-warning", applied=org_dims))

        # 成绩任务发布率：term_id 直接支持；学院/专业经班级链
        tq = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False))
        gt_dims = list(org_dims)
        if term_id:
            tq = tq.filter(AaGradeTask.term_id == term_id)
            gt_dims = ["term"] + gt_dims
        if class_ids is not None:
            tq = tq.filter(AaGradeTask.class_id.in_(class_ids or [0]))
        pub = tq.filter(AaGradeTask.status == "PUBLISHED").count()
        total_gt = tq.count()
        inds.append(_ind("gradePublishRate", "成绩任务发布率", _rate(pub, total_gt), "%",
                         pub, total_gt, _rate(pub, total_gt), "aa-grade-review", applied=gt_dims))

        # 毕业资格通过率：按学生主档收敛学院/专业
        grq = db.query(AaGraduationAuditResult).filter(AaGraduationAuditResult.tenant_id == T)
        if profile_ids is not None:
            grq = grq.filter(AaGraduationAuditResult.student_id.in_(profile_ids or [0]))
        grad_ok = grq.filter(AaGraduationAuditResult.status.in_(["GRADUATED", "COMPLETED"])).count()
        grad_total = grq.count()
        inds.append(_ind("gradPassRate", "毕业资格通过率", _rate(grad_ok, grad_total), "%",
                         grad_ok, grad_total, _rate(grad_ok, grad_total),
                         "aa-graduation-qual", applied=org_dims))

        # 培养方案发布率：major 直接支持，college 经专业链
        pq = db.query(AaProgram).filter(AaProgram.tenant_id == T, AaProgram.is_deleted.is_(False))
        if major_id:
            pq = pq.filter(AaProgram.major_id == major_id)
        elif college_id:
            mids = [m for (m,) in db.query(Major.id).filter(
                Major.tenant_id == T, Major.college_id == college_id).all()]
            pq = pq.filter(AaProgram.major_id.in_(mids or [0]))
        prog_pub = pq.filter(AaProgram.status.in_(["PUBLISHED", "ENABLED"])).count()
        prog_total = pq.count()
        inds.append(_ind("programPublishRate", "培养方案发布率", _rate(prog_pub, prog_total), "%",
                         prog_pub, prog_total, _rate(prog_pub, prog_total),
                         "aa-training", applied=org_dims))

        # 启用课程数：仅 college（课程归属学院）
        cq = db.query(AaCourse).filter(AaCourse.tenant_id == T, AaCourse.status == "ENABLED",
                                       AaCourse.is_deleted.is_(False))
        if college_id:
            cq = cq.filter(AaCourse.owner_college_id == college_id)
        inds.append(_ind("courseEnabled", "启用课程数", cq.count(), "门",
                         drill="aa-courses", applied=(["college"] if college_id else [])))

        # 教学任务确认率：term/college 经任务批次，major 经班级链
        ttq = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == T,
                                              AaTeachingTask.is_deleted.is_(False))
        tt_dims = []
        if term_id or college_id:
            bq = db.query(AaTeachingTaskBatch.id).filter(AaTeachingTaskBatch.tenant_id == T)
            if term_id:
                bq = bq.filter(AaTeachingTaskBatch.term_id == term_id)
                tt_dims.append("term")
            if college_id:
                bq = bq.filter(AaTeachingTaskBatch.college_id == college_id)
                tt_dims.append("college")
            ttq = ttq.filter(AaTeachingTask.batch_id.in_([b for (b,) in bq.all()] or [0]))
        if major_id:
            major_classes = [c for (c,) in db.query(SchoolClass.id).filter(
                SchoolClass.tenant_id == T, SchoolClass.major_id == major_id).all()]
            ttq = ttq.filter(AaTeachingTask.class_id.in_(major_classes or [0]))
            tt_dims.append("major")
        task_done = ttq.filter(AaTeachingTask.status.in_(
            ["TEACHER_CONFIRMED", "READY", "APPROVED"])).count()
        task_total = ttq.count()
        inds.append(_ind("taskCompleteRate", "教学任务确认率", _rate(task_done, task_total), "%",
                         task_done, task_total, _rate(task_done, task_total),
                         "aa-teaching-tasks", applied=tt_dims))

        # 调停课单数：term 直接支持，学院/专业经班级链
        sq = db.query(AaScheduleChange).filter(AaScheduleChange.tenant_id == T,
                                               AaScheduleChange.is_deleted.is_(False))
        sc_dims = []
        if term_id:
            sq = sq.filter(AaScheduleChange.term_id == term_id)
            sc_dims.append("term")
        if class_ids is not None:
            sq = sq.filter(AaScheduleChange.class_id.in_(class_ids or [0]))
            sc_dims += org_dims
        inds.append(_ind("scheduleChangeCount", "调停课单数", sq.count(), "单",
                         drill="aa-schedule-change", applied=sc_dims))

        return {"termId": str(term_id) if term_id else None,
                "collegeId": str(college_id) if college_id else None,
                "majorId": str(major_id) if major_id else None,
                "indicators": inds, "generatedAt": datetime.utcnow().isoformat()}


def export_report(user, term_id=None, college_id=None, major_id=None, purpose="") -> bytes:
    """导出教务运行质量报告 xlsx（水印+审计；复用 xlsx_util）。"""
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx
    data = dashboard(user, term_id, college_id, major_id)
    ctx = get_current_user_ctx() or {}
    watermark = (f"导出人：{ctx.get('realName') or ctx.get('loginName') or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}")
    headers = ["质量指标", "值", "单位", "分子", "分母", "比率(%)"]
    rows = [[i["label"], i["value"], i["unit"], i["numerator"], i["denominator"], i["rate"]] for i in data["indicators"]]
    content = build_ledger_xlsx("教务运行质量报告", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "QUALITY_REPORT_EXPORT", f"质量报告导出 用途={purpose.strip()[:100]}")
        db.commit()
    return content


def list_reports(user, page=1, page_size=20):
    """质量报告导出历史（读 AffairsAuditTrail 的导出事件）。"""
    from app.models import AffairsAuditTrail
    with session() as db:
        build_affairs_context(user, db)
        rows = db.query(AffairsAuditTrail).filter(AffairsAuditTrail.tenant_id == _tid(),
                                                  AffairsAuditTrail.biz_type == "AA_QUALITY_REPORT",
                                                  AffairsAuditTrail.action == "QUALITY_REPORT_EXPORT").order_by(
            AffairsAuditTrail.id.desc()).all()
        total = len(rows)
        items = [{"exportId": str(r.id), "operator": r.operator, "roleName": r.role_name,
                  "detail": r.detail, "occurredAt": r.occurred_at.isoformat() if r.occurred_at else None}
                 for r in rows[(page - 1) * page_size: page * page_size]]
        return items, total
