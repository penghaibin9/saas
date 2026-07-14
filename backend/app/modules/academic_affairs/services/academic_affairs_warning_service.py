"""13B-P5 学业预警规则引擎（复用既有 t_acad_warning，加列 source_code/rule_code）。

扫描 t_acad_grade 挂科情况按规则生成预警，幂等(student+source 去重)。阈值走规则中心。
生成的预警流入既有学业过程域处置全链路（分派/干预/关闭），本模块只负责规则触发。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_SOURCE = "EXAM_FAIL"
TODO_TYPE = "ACAD_WARNING_HANDLE"


def _counselor_of(db, acad_student_id):
    """学业台账生 → 全局学生 → 行政班 → 辅导员 user_id。
    返回 (counselor_user_id, global_student_id)；无绑定则 (0, sid|None)，对齐异动服务同款解析。"""
    from app.models import AcademicStudent, SchoolClass, StudentProfile
    a = db.get(AcademicStudent, int(acad_student_id))
    if not a or not a.student_id:
        return 0, None
    s = db.get(StudentProfile, int(a.student_id))
    if not s or not s.class_id:
        return 0, a.student_id
    c = db.get(SchoolClass, int(s.class_id))
    return (int(c.counselor_id) if c and c.counselor_id else 0), a.student_id


def _push_counselor_todo(db, warning, assignee, student_id) -> bool:
    """向辅导员工作台推送预警处置待办（统一待办，幂等：同预警同责任人只一条）。"""
    if not assignee:
        return False
    from app.models import UnifiedTodo
    exist = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_id == int(warning.id), UnifiedTodo.todo_type == TODO_TYPE,
        UnifiedTodo.assignee_id == int(assignee), UnifiedTodo.is_deleted.is_(False))).first()
    if exist:
        return False
    db.add(UnifiedTodo(tenant_id=_tid(), source_module="academic-affairs",
                       source_biz_type="ACAD_WARNING", source_biz_id=int(warning.id),
                       todo_type=TODO_TYPE, assignee_id=int(assignee),
                       student_id=int(student_id) if student_id else None,
                       title=f"学业预警待处理：{warning.reason or '挂科预警'}", status="PENDING"))
    return True


def mark_todos_done(db, warning_id) -> int:
    """预警在既有学业过程域被关闭/作废时，同步把辅导员待办置 DONE（闭环消办）。
    供 academic_service.close_warning/void_warning 在同事务内调用。"""
    from app.models import UnifiedTodo
    cnt = 0
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(warning_id), UnifiedTodo.todo_type == TODO_TYPE,
            UnifiedTodo.status != "DONE", UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1
        cnt += 1
    return cnt


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
        created = updated = notified = 0
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
            w = AcademicWarning(tenant_id=_tid(), acad_student_id=asid, warn_type="MULTI_FAIL",
                                level=level, reason=f"挂科 {n} 门", source_rule=rule_code,
                                source_code=_SOURCE, rule_code=rule_code, status="PENDING_HANDLE",
                                trigger_time=now, record_status="ACTIVE")
            db.add(w)
            db.flush()  # 取 warning.id 以关联辅导员待办
            created += 1
            # §四联动：新预警自动推送责任辅导员工作台（无绑定班级/辅导员则不推，assignee=0）
            cid, sid = _counselor_of(db, asid)
            if _push_counselor_todo(db, w, cid, sid):
                notified += 1
        db.commit()
        return {"threshold": thr, "created": created, "updated": updated, "notified": notified}


def list_warnings(user, level=None, status=None, source_code=None, acad_student_id=None, page=1, page_size=20):
    """学业预警列表（含 P5 规则来源标识）。与 t_acad_student 一次性 JOIN + DB 级分页，去逐行 N+1。
    acad_student_id：传入时仅返回该生本人预警（移动端学生自视图用）。"""
    from app.models import AcademicStudent, AcademicWarning
    with session() as db:
        join = and_(AcademicStudent.id == AcademicWarning.acad_student_id,
                    AcademicStudent.tenant_id == AcademicWarning.tenant_id)
        conds = [AcademicWarning.tenant_id == _tid(), AcademicWarning.record_status == "ACTIVE",
                 AcademicWarning.is_deleted.is_(False)]
        if level:
            conds.append(AcademicWarning.level == level)
        if status:
            conds.append(AcademicWarning.status == status)
        if source_code:
            conds.append(AcademicWarning.source_code == source_code)
        if acad_student_id:
            conds.append(AcademicWarning.acad_student_id == int(acad_student_id))
        total = db.scalar(select(func.count()).select_from(AcademicWarning)
                          .outerjoin(AcademicStudent, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AcademicWarning, AcademicStudent)
                          .outerjoin(AcademicStudent, join).where(*conds)
                          .order_by(AcademicWarning.id.desc()).offset(offset).limit(page_size)).all()
        out = [{"warningId": str(w.id), "studentName": a.name if a else "",
                "studentId": str(a.student_id or "") if a else "", "warnType": w.warn_type,
                "level": w.level, "reason": w.reason or "", "sourceCode": w.source_code or "",
                "ruleCode": w.rule_code or "", "status": w.status} for w, a in rows]
        return out, total
