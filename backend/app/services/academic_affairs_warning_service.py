"""13B-P5 学业预警规则引擎（复用既有 t_acad_warning，加列 source_code/rule_code）。

扫描 t_acad_grade 挂科情况按规则生成预警，幂等(student+source 去重)。阈值走规则中心。
生成的预警流入既有学业过程域处置全链路（分派/干预/关闭），本模块只负责规则触发。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_SOURCE = "EXAM_FAIL"


def _fail_threshold() -> int:
    """规则中心 academicAffairs.warning.fail_threshold，默认 1（挂 1 门即预警）。"""
    from app.services.platform_service import get_config_json
    cfg = get_config_json(_tid(), "ACAD_RULE", "warning_fail_threshold")
    try:
        return int(cfg.get("count")) if cfg and cfg.get("count") else 1
    except (TypeError, ValueError):
        return 1


def _level_for(fail_count: int) -> str:
    if fail_count >= 3:
        return "HIGH"
    if fail_count >= 2:
        return "MEDIUM"
    return "LOW"


def scan_warnings(user) -> dict:
    """挂科预警扫描：按学生统计挂科门数，达阈值生成/更新预警。幂等：同生同来源不重复建。"""
    thr = _fail_threshold()
    now = datetime.utcnow()
    with session() as db:
        from app.models import AcademicGrade, AcademicWarning
        # 按 acad_student 统计挂科门数
        fails = db.execute(select(AcademicGrade.acad_student_id, func.count().label("n")).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.pass_status == "FAIL",
            AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))
            .group_by(AcademicGrade.acad_student_id)).all()
        created = updated = 0
        for asid, n in fails:
            if n < thr:
                continue
            rule_code = f"EXAM_FAIL_GE_{thr}"
            level = _level_for(n)
            # 幂等：同生同来源在办预警存在则更新等级，否则新建
            exist = db.scalars(select(AcademicWarning).where(
                AcademicWarning.tenant_id == _tid(), AcademicWarning.acad_student_id == asid,
                AcademicWarning.source_code == _SOURCE,
                AcademicWarning.status.notin_(["CLOSED", "VOID"]),
                AcademicWarning.record_status == "ACTIVE", AcademicWarning.is_deleted.is_(False))).first()
            if exist:
                if exist.level != level:
                    exist.level, exist.reason = level, f"挂科 {n} 门"
                    updated += 1
                continue
            db.add(AcademicWarning(tenant_id=_tid(), acad_student_id=asid, warn_type="MULTI_FAIL",
                                   level=level, reason=f"挂科 {n} 门", source_rule=rule_code,
                                   source_code=_SOURCE, rule_code=rule_code, status="PENDING_HANDLE",
                                   trigger_time=now, record_status="ACTIVE"))
            created += 1
        db.commit()
        return {"threshold": thr, "created": created, "updated": updated}


def list_warnings(user, level=None, status=None, source_code=None, page=1, page_size=20):
    """学业预警列表（含 P5 规则来源标识）。"""
    from app.models import AcademicStudent, AcademicWarning
    with session() as db:
        conds = [AcademicWarning.tenant_id == _tid(), AcademicWarning.record_status == "ACTIVE",
                 AcademicWarning.is_deleted.is_(False)]
        if level:
            conds.append(AcademicWarning.level == level)
        if status:
            conds.append(AcademicWarning.status == status)
        if source_code:
            conds.append(AcademicWarning.source_code == source_code)
        rows = db.scalars(select(AcademicWarning).where(*conds).order_by(AcademicWarning.id.desc())).all()
        out = []
        for w in rows:
            a = db.get(AcademicStudent, int(w.acad_student_id))
            out.append({"warningId": str(w.id), "studentName": a.name if a else "",
                        "studentId": str(a.student_id or "") if a else "", "warnType": w.warn_type,
                        "level": w.level, "reason": w.reason or "", "sourceCode": w.source_code or "",
                        "ruleCode": w.rule_code or "", "status": w.status})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
