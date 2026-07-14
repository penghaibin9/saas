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


def _ind(key, label, value, unit="", num=None, den=None, rate=None, drill=None):
    return {"key": key, "label": label, "value": value, "unit": unit,
            "numerator": num, "denominator": den, "rate": rate, "drillRoute": drill}


def dashboard(user, term_id=None, college_id=None, major_id=None):
    """质量指标看板（实时聚合既有表；按数据范围收敛）。"""
    from app.models import (AaCourse, AaGradeTask, AaGraduationAuditResult, AaProgram,
                            AaScheduleChange, AaTeachingTask, AcademicGrade, AcademicWarning)
    with session() as db:
        build_affairs_context(user, db)  # 建立范围上下文（本期看板为全校聚合，学院/专业下钻见 drilldown）
        T = _tid()
        inds = []
        # 挂科率
        fail = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == T,
                                              AcademicGrade.pass_status.in_(["FAIL", "FAILED"]),
                                              AcademicGrade.record_status == "ACTIVE").count()
        total_g = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == T,
                                                 AcademicGrade.record_status == "ACTIVE").count()
        inds.append(_ind("failRate", "挂科率", _rate(fail, total_g), "%", fail, total_g, _rate(fail, total_g), "aa-grades"))
        # 学业预警数（未关闭）
        warn = db.query(AcademicWarning).filter(AcademicWarning.tenant_id == T,
                                                AcademicWarning.status != "CLOSED",
                                                AcademicWarning.record_status == "ACTIVE").count()
        inds.append(_ind("warningCount", "在办学业预警", warn, "条", drill="aa-warning"))
        # 成绩任务发布率
        pub = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.status == "PUBLISHED",
                                           AaGradeTask.is_deleted.is_(False)).count()
        total_gt = db.query(AaGradeTask).filter(AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False)).count()
        inds.append(_ind("gradePublishRate", "成绩任务发布率", _rate(pub, total_gt), "%", pub, total_gt, _rate(pub, total_gt), "aa-grade-review"))
        # 毕业资格通过率
        grad_ok = db.query(AaGraduationAuditResult).filter(AaGraduationAuditResult.tenant_id == T,
                                                           AaGraduationAuditResult.status.in_(["GRADUATED", "COMPLETED"])).count()
        grad_total = db.query(AaGraduationAuditResult).filter(AaGraduationAuditResult.tenant_id == T).count()
        inds.append(_ind("gradPassRate", "毕业资格通过率", _rate(grad_ok, grad_total), "%", grad_ok, grad_total, _rate(grad_ok, grad_total), "aa-graduation-qual"))
        # 方案发布率
        prog_pub = db.query(AaProgram).filter(AaProgram.tenant_id == T,
                                              AaProgram.status.in_(["PUBLISHED", "ENABLED"]),
                                              AaProgram.is_deleted.is_(False)).count()
        prog_total = db.query(AaProgram).filter(AaProgram.tenant_id == T, AaProgram.is_deleted.is_(False)).count()
        inds.append(_ind("programPublishRate", "培养方案发布率", _rate(prog_pub, prog_total), "%", prog_pub, prog_total, _rate(prog_pub, prog_total), "aa-training"))
        # 课程启用数
        course_on = db.query(AaCourse).filter(AaCourse.tenant_id == T, AaCourse.status == "ENABLED",
                                              AaCourse.is_deleted.is_(False)).count()
        inds.append(_ind("courseEnabled", "启用课程数", course_on, "门", drill="aa-courses"))
        # 教学任务完成率（已确认/就绪）
        task_done = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == T,
                                                    AaTeachingTask.status.in_(["TEACHER_CONFIRMED", "READY", "APPROVED"]),
                                                    AaTeachingTask.is_deleted.is_(False)).count()
        task_total = db.query(AaTeachingTask).filter(AaTeachingTask.tenant_id == T, AaTeachingTask.is_deleted.is_(False)).count()
        inds.append(_ind("taskCompleteRate", "教学任务确认率", _rate(task_done, task_total), "%", task_done, task_total, _rate(task_done, task_total), "aa-teaching-tasks"))
        # 调停课数
        chg = db.query(AaScheduleChange).filter(AaScheduleChange.tenant_id == T,
                                                AaScheduleChange.is_deleted.is_(False)).count()
        inds.append(_ind("scheduleChangeCount", "调停课单数", chg, "单", drill="aa-schedule-change"))
        return {"termId": str(term_id) if term_id else None, "indicators": inds,
                "generatedAt": datetime.utcnow().isoformat()}


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
