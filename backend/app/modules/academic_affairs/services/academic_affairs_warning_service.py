"""13B-P5 学业预警规则引擎（复用既有 t_acad_warning，加列 source_code/rule_code）。

本轮（学业预警二级模块 Tier1）扩展：
- 挂科（既有 EXAM_FAIL）之外新增学分不足 / 低绩点 / 重修过多 / 毕业资格异常 4 类真实规则扫描；
- 预警看板/统计聚合（按来源/等级/状态分组）；
- 预警规则阈值配置（复用平台 PlatformConfig KV，ctype=ACAD_RULE，不新建规则表）；
- 预警跟进闭环（详情/指派/干预记录/关闭/升级/作废/提醒）——复用 t_acad_warning + t_acad_intervention
  两张既有表，不复用 /api/v1/academic/* 旧域端点（该域缺数据范围收敛，超出本轮改造边界，见施工记录）。

生成的预警流入本模块自身处置闭环（分派/干预/升级/关闭/作废），旧 /api/v1/academic/warnings/*
（academic_service.py）仍可读写同一张表，两域并存但本模块新端点是学业预警菜单的唯一主入口。

「预警通知」三级模块（本轮补建）：参照调停课/课表发布通知模式（academic_affairs_schedule_change_service
._msg / academic_affairs_schedule_service.publish），复用既有 t_unified_message（不新建表/不迁移）：
- 预警首次生成或再扫描升级等级时，自动向学生本人 + 责任辅导员各推一条站内通知（_push_warning_notice，
  message_type=ACAD_WARNING_NEW）；与 _push_counselor_todo（工作台待办）并行，互不替代；
- 「预警跟进」页「提醒」按钮（remind_warning）由原先仅计数改为真实推送一条通知
  （message_type=ACAD_WARNING_REMIND），避免空按钮；
- list_notifications / notification_summary 供新增「预警通知」页读取推送台账，数据范围收敛口径
  与 list_warnings 一致（经 source_biz_id 关联回 t_acad_warning.acad_student_id）。
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.core.field_crypto import mask_phone_encrypted
from app.services.db_service import _iso, _tid, session

_SOURCE = "EXAM_FAIL"
TODO_TYPE = "ACAD_WARNING_HANDLE"

# 预警来源枚举（对齐 13B-教务中心状态机与权限矩阵.md §13）。EXAM_FAIL 为历史内部编码，
# 对外统一按「挂科预警/FAIL_COURSE」展示，不改历史落库值（避免破坏既有幂等去重与统计口径）。
SOURCE_LABELS = {
    "EXAM_FAIL": "挂科预警",
    "CREDIT_SHORT": "学分预警",
    "LOW_GPA": "绩点预警",
    "RETAKE_EXCESS": "补考重修预警",
    "GRAD_ABNORMAL": "毕业风险预警",
    "OTHER": "其他预警",  # group_counts() 对 source_code 为空的记录归入字面量 "OTHER" 桶，此前该
                          # key 缺失导致"按来源分布"直接显示未翻译的英文 "OTHER"（见真实交互巡检）。
}
LEVEL_LABELS = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}
STATUS_LABELS = {"PENDING_HANDLE": "待处理", "PROCESSING": "跟进中", "ESCALATED": "已升级", "CLOSED": "已关闭"}

# 预警通知场景（t_unified_message.message_type 取值；见 _push_warning_notice）
NOTICE_NEW = "ACAD_WARNING_NEW"        # 预警首次生成 / 再扫描升级等级
NOTICE_REMIND = "ACAD_WARNING_REMIND"  # 「预警跟进」页人工提醒
NOTICE_TYPES = (NOTICE_NEW, NOTICE_REMIND)

# 规则键元数据（GET/PUT /warnings/rules；ctype=ACAD_RULE，与既有 warning_fail_threshold 同表同风格）
RULES_META = [
    {"key": "warning_fail_threshold", "label": "挂科预警：挂科门数阈值（达到即触发）",
     "sourceCode": "EXAM_FAIL", "type": "int", "min": 1, "max": 20, "default": 1},
    {"key": "warning_credit_ratio", "label": "学分预警：学分完成率低于该比例触发（0~1）",
     "sourceCode": "CREDIT_SHORT", "type": "float", "min": 0.1, "max": 0.95, "default": 0.6},
    {"key": "warning_gpa_threshold", "label": "绩点预警：绩点低于该值触发",
     "sourceCode": "LOW_GPA", "type": "float", "min": 0.5, "max": 4.0, "default": 2.0},
    {"key": "warning_retake_threshold", "label": "补考重修预警：重修门数达到该值触发",
     "sourceCode": "RETAKE_EXCESS", "type": "int", "min": 1, "max": 10, "default": 2},
    {"key": "warning_absent_threshold", "label": "旷课预警：已提交场次旷课次数达到该值触发",
     "sourceCode": "ATTENDANCE_ABSENT", "type": "int", "min": 1, "max": 30, "default": 3},
]
_RULES_BY_KEY = {m["key"]: m for m in RULES_META}


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _conflict(m):
    return AppException("DATA_CONFLICT", m, http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return ctx.get("realName") or "系统", ctx.get("currentRoleCode") or ""


def _audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    from app.models import AffairsAuditTrail
    name, role = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=biz_id, action=action,
                             operator=name, role_name=role, detail=(detail or "")[:990],
                             before_val=(before or "")[:990] or None, after_val=(after or "")[:990] or None,
                             occurred_at=datetime.utcnow()))


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
                       title=f"学业预警待处理：{warning.reason or SOURCE_LABELS.get(warning.source_code, '学业预警')}",
                       status="PENDING"))
    return True


def _push_warning_notice(db, warning, counselor_id, student_global_id, scene=NOTICE_NEW) -> int:
    """向学生本人 + 责任辅导员各推一条站内通知（t_unified_message），参照调停课
    （academic_affairs_schedule_change_service._msg）/ 课表发布（academic_affairs_schedule_service.publish）
    的既有通知模式。与 _push_counselor_todo（辅导员工作台待办）并行、互不替代：待办驱动处置任务队列，
    通知进消息中心与「预警通知」台账页留痕可查。
    receiver_id 语义：学生侧＝t_student_profile.id（全平台学生身份，与移动端 token.userId 同源，
    见 mobile_student_service._resolve_uid）；辅导员侧＝SchoolClass.counselor_id 对应的登录 user_id
    （与调停课 _msg(db, x.applicant_id, ...) 同源）。任一方解析不到（未绑定辅导员/学生未关联全局身份）
    则跳过该方，不臆造收件人。返回实际推送条数。"""
    from app.services.message_event_outbox_service import emit_message_event
    label = SOURCE_LABELS.get(warning.source_code or "", warning.source_code or "学业预警")
    reason = warning.reason or label
    is_remind = scene == NOTICE_REMIND
    remind_n = int(warning.remind_count or 0) if is_remind else 0
    sent = 0
    if student_global_id:
        title = f"再次提醒：{label}" if is_remind else f"学业预警通知：{label}"
        content = (f"你已被再次提醒关注「{reason}」，请尽快改善学业情况，如有疑问请主动联系辅导员或任课教师。"
                   if is_remind else
                   f"你被系统标记「{reason}」，请及时关注学业情况，必要时主动联系辅导员或任课教师。")
        emit_message_event(
            db,
            event_code="WARNING.CREATED",
            source_module="academic-affairs",
            source_biz_type="academic_warning",
            source_biz_id=int(warning.id),
            recipient_refs=[{"studentId": int(student_global_id)}],
            content=content,
            title=title,
            dedup_key=f"WARNING.CREATED:{warning.id}:student:{scene}:{remind_n}",
        )
        sent += 1
    if counselor_id:
        title = f"预警再次提醒：{label}" if is_remind else f"学生{label}：请跟进"
        content = f"「{reason}」，请及时跟进处置（预警编号 {warning.id}）。"
        emit_message_event(
            db,
            event_code="WARNING.CREATED",
            source_module="academic-affairs",
            source_biz_type="academic_warning",
            source_biz_id=int(warning.id),
            recipient_refs=[{"userId": int(counselor_id)}],
            content=content,
            title=title,
            dedup_key=f"WARNING.CREATED:{warning.id}:counselor:{scene}:{remind_n}",
        )
        sent += 1
    return sent


def mark_todos_done(db, warning_id) -> int:
    """预警在既有学业过程域被关闭/作废时，同步把辅导员待办置 DONE（闭环消办）。
    供 academic_service.close_warning/void_warning 在同事务内调用；本模块自身 close_warning/void_warning 亦调用。"""
    from app.models import UnifiedTodo
    cnt = 0
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(warning_id), UnifiedTodo.todo_type == TODO_TYPE,
            UnifiedTodo.status != "DONE", UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1
        cnt += 1
    return cnt


# ═══════════ 数据范围收敛（复用 stats_service 已验证的 scope 解析，不另造一套） ═══════════

def _scope_acad_ids(db, user):
    """当前用户可见的 acad_student_id 集合；None=不限（全校）。仅用于「未显式指定单一学生」的列表/看板/统计场景——
    学生自视图等显式传 acad_student_id 的调用不经过本函数（保持既有行为，见 list_warnings）。"""
    from app.modules.academic_affairs.services.academic_affairs_stats_service import (
        _acad_student_ids, _resolve_scope, _student_ids)
    scope = _resolve_scope(user, db)
    if scope.all:
        return None
    sids = _student_ids(db, scope)
    return _acad_student_ids(db, sids)


def _assert_handle_allowed(db, user, warning):
    """处置类写操作（指派/干预/升级/关闭/作废/提醒）越权校验：
    全校范围放行；范围内学生放行；范围外但本人是该预警被分配跟进人（统一待办 assignee）放行；否则 403。"""
    from app.core.affairs_security import no_data_scope
    scope_ids = _scope_acad_ids(db, user)
    if scope_ids is None or int(warning.acad_student_id) in scope_ids:
        return
    from app.models import UnifiedTodo
    uid = (get_current_user_ctx() or {}).get("userId")
    if uid:
        mine = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_biz_id == int(warning.id),
            UnifiedTodo.todo_type == TODO_TYPE, UnifiedTodo.assignee_id == int(uid),
            UnifiedTodo.is_deleted.is_(False))).first()
        if mine:
            return
    raise no_data_scope("该预警不在您的数据范围内")


# ═══════════ 规则扫描：共用 upsert ═══════════

def _rule_value(key):
    from app.services.platform_service import get_config_json
    meta = _RULES_BY_KEY[key]
    cfg = get_config_json(_tid(), "ACAD_RULE", key)
    raw = cfg.get("value") if cfg else None
    if raw is None:
        return meta["default"]
    try:
        return int(raw) if meta["type"] == "int" else float(raw)
    except (TypeError, ValueError):
        return meta["default"]


def _fail_threshold() -> int:
    """规则中心 academicAffairs.warning.fail_threshold，默认 1（挂 1 门即预警）。"""
    return int(_rule_value("warning_fail_threshold"))


def _level_for(fail_count: int) -> str:
    if fail_count >= 3:
        return "HIGH"
    if fail_count >= 2:
        return "MEDIUM"
    return "LOW"


def _upsert_warning(db, asid, source_code, warn_type, level, reason, rule_code, now) -> tuple[bool, bool]:
    """按 (acad_student_id, source_code) 幂等 upsert 一条预警：已有在办（非CLOSED/VOID）则按需更新等级，
    否则新建 + 推送责任辅导员待办。新建 / 等级变化两种场景均向学生本人+责任辅导员推送站内通知
    （_push_warning_notice，message_type=ACAD_WARNING_NEW；供「预警通知」页留痕）。返回 (created, updated)。"""
    from app.models import AcademicWarning
    exist = db.scalars(select(AcademicWarning).where(
        AcademicWarning.tenant_id == _tid(), AcademicWarning.acad_student_id == asid,
        AcademicWarning.source_code == source_code,
        AcademicWarning.status.notin_(["CLOSED", "VOID"]),
        AcademicWarning.record_status == "ACTIVE", AcademicWarning.is_deleted.is_(False))).first()
    if exist:
        if exist.level != level:
            exist.level, exist.reason = level, reason
            cid, sid = _counselor_of(db, asid)
            _push_warning_notice(db, exist, cid, sid, NOTICE_NEW)
            return False, True
        return False, False
    w = AcademicWarning(tenant_id=_tid(), acad_student_id=asid, warn_type=warn_type,
                        level=level, reason=reason, source_rule=rule_code,
                        source_code=source_code, rule_code=rule_code, status="PENDING_HANDLE",
                        trigger_time=now, record_status="ACTIVE")
    db.add(w)
    db.flush()  # 取 warning.id 以关联辅导员待办 / 通知
    cid, sid = _counselor_of(db, asid)
    _push_counselor_todo(db, w, cid, sid)
    _push_warning_notice(db, w, cid, sid, NOTICE_NEW)
    return True, False


def scan_warnings(user) -> dict:
    """挂科预警扫描：按学生统计挂科门数，达阈值生成/更新预警。幂等：同生同来源不重复建。"""
    thr = _fail_threshold()
    now = datetime.utcnow()
    with session() as db:
        from app.models import AcademicGrade
        from app.modules.academic_affairs.services.academic_affairs_grade_service import effective_grade_rows
        # 取全部有效成绩行按 (学生,课程) 去重后再统计挂科门数，避免补考/清考已通过的课程仍被计入挂科
        all_rows = db.scalars(select(AcademicGrade).where(
            AcademicGrade.tenant_id == _tid(), AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False))).all()
        counts: dict = {}
        for g in effective_grade_rows(all_rows):
            # 兼容历史迁移枚举 FAIL/PASS 与正式 PASSED/FAILED
            if g.pass_status in ("FAILED", "FAIL"):
                counts[g.acad_student_id] = counts.get(g.acad_student_id, 0) + 1
        fails = list(counts.items())
        created = updated = 0
        for asid, n in fails:
            if n < thr:
                continue
            rule_code = f"EXAM_FAIL_GE_{thr}"
            c, u = _upsert_warning(db, asid, _SOURCE, "MULTI_FAIL", _level_for(n),
                                   f"挂科 {n} 门", rule_code, now)
            created += int(c)
            updated += int(u)
        _audit(db, "ACAD_WARNING_SCAN", 0, "SCAN_FAIL_COURSE", f"created={created} updated={updated}")
        db.commit()
        return {"threshold": thr, "created": created, "updated": updated, "notified": created}


def scan_credit_warnings(user) -> dict:
    """学分预警扫描：学分完成率（已获学分/应修学分）低于阈值比例即触发。"""
    ratio = float(_rule_value("warning_credit_ratio"))
    now = datetime.utcnow()
    with session() as db:
        from app.models import AcademicStudent
        rows = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
            AcademicStudent.record_status == "ACTIVE")).all()
        created = updated = 0
        rule_code = f"CREDIT_RATIO_LT_{ratio}"
        for s in rows:
            required = float(s.required_credits or 0)
            if required <= 0:
                continue
            got = float(s.obtained_credits or 0)
            r = got / required
            if r >= ratio:
                continue
            level = "HIGH" if r < ratio * 0.5 else ("MEDIUM" if r < ratio * 0.8 else "LOW")
            reason = f"学分完成率 {r * 100:.0f}%（{got:g}/{required:g}）低于阈值 {ratio * 100:.0f}%"
            c, u = _upsert_warning(db, s.id, "CREDIT_SHORT", "CREDIT_GAP", level, reason, rule_code, now)
            created += int(c)
            updated += int(u)
        _audit(db, "ACAD_WARNING_SCAN", 0, "SCAN_CREDIT_SHORT", f"created={created} updated={updated}")
        db.commit()
        return {"threshold": ratio, "created": created, "updated": updated}


def scan_gpa_warnings(user) -> dict:
    """绩点预警扫描：绩点低于阈值即触发。"""
    thr = float(_rule_value("warning_gpa_threshold"))
    now = datetime.utcnow()
    with session() as db:
        from app.models import AcademicStudent
        rows = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
            AcademicStudent.record_status == "ACTIVE")).all()
        created = updated = 0
        rule_code = f"GPA_LT_{thr}"
        for s in rows:
            gpa = s.gpa
            if gpa is None:
                continue
            gpa = float(gpa)
            if gpa >= thr:
                continue
            level = "HIGH" if gpa < thr - 0.5 else ("MEDIUM" if gpa < thr - 0.2 else "LOW")
            reason = f"绩点 {gpa:.2f} 低于阈值 {thr:.2f}"
            c, u = _upsert_warning(db, s.id, "LOW_GPA", "GRADE_DROP", level, reason, rule_code, now)
            created += int(c)
            updated += int(u)
        _audit(db, "ACAD_WARNING_SCAN", 0, "SCAN_LOW_GPA", f"created={created} updated={updated}")
        db.commit()
        return {"threshold": thr, "created": created, "updated": updated}


def scan_retake_warnings(user) -> dict:
    """补考重修预警扫描：重修门数达到阈值即触发。"""
    thr = int(_rule_value("warning_retake_threshold"))
    now = datetime.utcnow()
    with session() as db:
        from app.models import AcademicStudent
        rows = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
            AcademicStudent.record_status == "ACTIVE", AcademicStudent.retake_count >= thr)).all()
        created = updated = 0
        rule_code = f"RETAKE_GE_{thr}"
        for s in rows:
            n = int(s.retake_count or 0)
            level = "HIGH" if n >= thr + 2 else ("MEDIUM" if n >= thr + 1 else "LOW")
            reason = f"重修 {n} 门（含补考 {int(s.makeup_count or 0)} 门）"
            c, u = _upsert_warning(db, s.id, "RETAKE_EXCESS", "MULTI_FAIL", level, reason, rule_code, now)
            created += int(c)
            updated += int(u)
        _audit(db, "ACAD_WARNING_SCAN", 0, "SCAN_RETAKE_EXCESS", f"created={created} updated={updated}")
        db.commit()
        return {"threshold": thr, "created": created, "updated": updated}


def scan_graduation_warnings(user) -> dict:
    """毕业风险预警扫描：毕业预审结果 SYSTEM_ABNORMAL 的学生联动生成预警（供数 SM-14，本模块只读快照）。"""
    now = datetime.utcnow()
    with session() as db:
        from app.models import AaGraduationAuditResult, AcademicStudent
        abnormal = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.is_deleted.is_(False),
            AaGraduationAuditResult.status == "SYSTEM_ABNORMAL")).all()
        student_ids = {int(r.student_id) for r in abnormal if r.student_id}
        created = updated = 0
        if student_ids:
            acads = db.scalars(select(AcademicStudent).where(
                AcademicStudent.tenant_id == _tid(), AcademicStudent.is_deleted.is_(False),
                AcademicStudent.student_id.in_(student_ids))).all()
            rule_code = "GRAD_PRECHECK_ABNORMAL"
            for a in acads:
                c, u = _upsert_warning(db, a.id, "GRAD_ABNORMAL", "GRAD_RISK", "HIGH",
                                       "毕业资格预审异常，存在未达标条件", rule_code, now)
                created += int(c)
                updated += int(u)
        _audit(db, "ACAD_WARNING_SCAN", 0, "SCAN_GRAD_ABNORMAL", f"created={created} updated={updated}")
        db.commit()
        return {"created": created, "updated": updated}


def scan_all(user) -> dict:
    """预警看板「一键扫描」：依次跑挂科/学分/绩点/重修/毕业/旷课规则。"""
    return {
        "EXAM_FAIL": scan_warnings(user),
        "CREDIT_SHORT": scan_credit_warnings(user),
        "LOW_GPA": scan_gpa_warnings(user),
        "RETAKE_EXCESS": scan_retake_warnings(user),
        "GRAD_ABNORMAL": scan_graduation_warnings(user),
        "ATTENDANCE_ABSENT": scan_attendance_warnings(user),
    }


def scan_attendance_warnings(user) -> dict:
    """旷课预警：汇总已提交课堂考勤场次中 ABSENT 次数，达阈值生成/更新预警（幂等）。"""
    thr = int(_rule_value("warning_absent_threshold"))
    now = datetime.utcnow()
    with session() as db:
        from app.models import AaAttendanceSession, AcademicStudent, StudentProfile
        import json as _json
        sessions = db.scalars(select(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.status == "SUBMITTED",
            AaAttendanceSession.is_deleted.is_(False),
        )).all()
        absent_counts: dict[int, int] = {}
        for t in sessions:
            try:
                items = _json.loads(t.roster_json) if t.roster_json else []
            except Exception:
                items = []
            for it in items:
                if str(it.get("status") or "").upper() != "ABSENT":
                    continue
                sid = it.get("studentId")
                if not sid:
                    continue
                try:
                    sid_i = int(sid)
                except (TypeError, ValueError):
                    continue
                absent_counts[sid_i] = absent_counts.get(sid_i, 0) + 1
        created = updated = 0
        rule_code = f"ABSENT_GE_{thr}"
        for profile_id, n in absent_counts.items():
            if n < thr:
                continue
            acad = db.scalars(select(AcademicStudent).where(
                AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == profile_id,
                AcademicStudent.is_deleted.is_(False))).first()
            if not acad:
                # 旷课预警不依赖成绩行：无台账时按成绩服务同口径建一行投影，再生成预警
                from app.modules.academic_affairs.services.academic_affairs_grade_service import _acad_student_id
                sp = db.get(StudentProfile, profile_id)
                acad = _acad_student_id(db, profile_id, name=(sp.real_name if sp else ""))
            level = "HIGH" if n >= thr * 2 else ("MEDIUM" if n >= thr else "LOW")
            c, u = _upsert_warning(
                db, acad.id, "ATTENDANCE_ABSENT", "ABSENT_EXCESS", level,
                f"旷课 {n} 次（阈值 {thr}）", rule_code, now)
            created += int(c)
            updated += int(u)
        _audit(db, "ACAD_WARNING_SCAN", 0, "SCAN_ATTENDANCE_ABSENT",
               f"created={created} updated={updated} thr={thr}")
        db.commit()
        return {"threshold": thr, "created": created, "updated": updated}


# ═══════════ 列表 / 看板 / 统计 ═══════════

def list_warnings(user, level=None, status=None, source_code=None, page=1, page_size=20, acad_student_id=None):
    """学业预警列表（含 P5 规则来源标识）。与 t_acad_student 一次性 JOIN + DB 级分页，去逐行 N+1。
    acad_student_id：传入时仅返回该生本人预警（移动端学生自视图/详情跳转用，保持既定行为不额外收敛范围）；
    未传入时按当前角色数据范围收敛（教务处/学院/学生全校口径见 stats_service._resolve_scope，与统计下钻一致）。
    置于末尾以不打乱既有位置调用方(academic_affairs.py)。"""
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
        else:
            scope_ids = _scope_acad_ids(db, user)
            if scope_ids is not None:
                if not scope_ids:
                    return [], 0
                conds.append(AcademicWarning.acad_student_id.in_(scope_ids))
        total = db.scalar(select(func.count()).select_from(AcademicWarning)
                          .outerjoin(AcademicStudent, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AcademicWarning, AcademicStudent)
                          .outerjoin(AcademicStudent, join).where(*conds)
                          .order_by(AcademicWarning.id.desc()).offset(offset).limit(page_size)).all()
        out = [{"warningId": str(w.id), "studentName": a.name if a else "",
                "studentId": str(a.student_id or "") if a else "", "className": a.class_name if a else "",
                "collegeName": a.college_name if a else "", "warnType": w.warn_type,
                "level": w.level, "reason": w.reason or "", "sourceCode": w.source_code or "",
                "sourceLabel": SOURCE_LABELS.get(w.source_code or "", w.source_code or ""),
                "ruleCode": w.rule_code or "", "status": w.status, "owner": w.owner or "",
                "remindCount": w.remind_count or 0, "triggerTime": _iso(w.trigger_time)} for w, a in rows]
        return out, total


def group_counts(db, acad_ids, dims=("source_code", "level", "status"), exclude_closed=False):
    """按任意维度组合对 AcademicWarning 分组计数——「教务统计·学业预警统计(11号卡)」与本模块
    「预警看板/统计」共用的唯一聚合实现，避免两处各写一套 GROUP BY（2026-07-15 甲方要求统一口径）。
    acad_ids: None=不限范围；[]=范围内无人（返回空）；list=限定该范围。
    exclude_closed: True 排除已关闭预警（供 BI 下钻"仅看在办"语义；模块内看板含历史用 False）。"""
    from app.models import AcademicWarning
    cols = [getattr(AcademicWarning, d) for d in dims]
    conds = [AcademicWarning.tenant_id == _tid(), AcademicWarning.record_status == "ACTIVE",
             AcademicWarning.is_deleted.is_(False)]
    if exclude_closed:
        conds.append(AcademicWarning.status != "CLOSED")
    if acad_ids is not None:
        if not acad_ids:
            return []
        conds.append(AcademicWarning.acad_student_id.in_(acad_ids))
    rows = db.execute(select(*cols, func.count()).where(*conds).group_by(*cols)).all()
    out = []
    for row in rows:
        item = {dims[i]: row[i] for i in range(len(dims))}
        item["count"] = int(row[-1])
        out.append(item)
    return out


def warning_summary(user) -> dict:
    """预警看板/统计聚合：按来源、等级、状态分组计数（数据范围同 list_warnings 未指定学生场景）。"""
    with session() as db:
        scope_ids = _scope_acad_ids(db, user)
        rows = group_counts(db, scope_ids, dims=("source_code", "level", "status"), exclude_closed=False)
        by_source, by_level, by_status = defaultdict(int), defaultdict(int), defaultdict(int)
        total = 0
        for r in rows:
            cnt = r["count"]
            total += cnt
            by_source[r["source_code"] or "OTHER"] += cnt
            by_level[r["level"] or "UNKNOWN"] += cnt
            by_status[r["status"] or "UNKNOWN"] += cnt
        return {
            "total": total,
            "bySource": [{"code": k, "label": SOURCE_LABELS.get(k, k), "count": v}
                        for k, v in sorted(by_source.items(), key=lambda x: -x[1])],
            "byLevel": [{"level": k, "label": LEVEL_LABELS.get(k, k), "count": v}
                       for k, v in by_level.items()],
            "byStatus": [{"status": k, "label": STATUS_LABELS.get(k, k), "count": v}
                        for k, v in by_status.items()],
        }


# ═══════════ 预警规则配置（复用 PlatformConfig KV，不新建规则表） ═══════════

def get_rules(user) -> list[dict]:
    return [{"key": m["key"], "label": m["label"], "sourceCode": m["sourceCode"], "type": m["type"],
             "min": m["min"], "max": m["max"], "default": m["default"], "value": _rule_value(m["key"])}
            for m in RULES_META]


def save_rule(user, key, value) -> dict:
    from app.services.platform_service import put_config_json
    meta = _RULES_BY_KEY.get(key)
    if not meta:
        raise _bad("未知规则键")
    try:
        num = int(value) if meta["type"] == "int" else float(value)
    except (TypeError, ValueError):
        raise _bad("规则值必须是数字")
    if num < meta["min"] or num > meta["max"]:
        raise _bad(f"规则值需在 {meta['min']}~{meta['max']} 之间")
    with session() as db:
        put_config_json(_tid(), "ACAD_RULE", key, {"value": num})
        _audit(db, "ACAD_WARNING_RULE", 0, "RULE_SAVE", f"{key}={num}")
        db.commit()
    return {"key": key, "value": num}


# ═══════════ 预警跟进闭环（详情/指派/干预/关闭/升级/作废/提醒） ═══════════

def _warning_or_404(db, warning_id):
    from app.core.exceptions import not_found
    from app.models import AcademicWarning
    w = db.get(AcademicWarning, int(warning_id))
    if not w or w.is_deleted or w.tenant_id != _tid():
        raise not_found("预警不存在或不在当前数据范围内")
    return w


def get_warning_detail(user, warning_id) -> dict:
    from app.models import AcademicIntervention, AcademicStudent
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        a = db.get(AcademicStudent, int(w.acad_student_id))
        itvs = db.scalars(select(AcademicIntervention).where(
            AcademicIntervention.tenant_id == _tid(), AcademicIntervention.warning_id == w.id,
        ).order_by(AcademicIntervention.id.desc())).all()
        return {
            "warning": {"warningId": str(w.id), "level": w.level, "status": w.status,
                       "warnType": w.warn_type, "reason": w.reason or "", "sourceCode": w.source_code or "",
                       "sourceLabel": SOURCE_LABELS.get(w.source_code or "", w.source_code or ""),
                       "ruleCode": w.rule_code or "", "owner": w.owner or "",
                       "remindCount": w.remind_count or 0, "closeResult": w.close_result or "",
                       "triggerTime": _iso(w.trigger_time), "recordStatus": w.record_status,
                       "voidReason": w.void_reason or ""},
            "student": ({"studentName": a.name, "studentNo": a.student_no or "", "className": a.class_name or "",
                        "collegeName": a.college_name or "", "gpa": float(a.gpa or 0),
                        "failedCount": a.failed_count or 0, "obtainedCredits": float(a.obtained_credits or 0),
                        "requiredCredits": float(a.required_credits or 0), "counselor": a.counselor or "",
                        "phone": mask_phone_encrypted(a.phone_encrypted)}
                       if a else None),
            "interventions": [{"id": str(i.id), "time": _iso(i.follow_time), "way": i.way,
                              "content": i.content or "", "result": i.result or "",
                              "nextPlan": i.next_plan or "", "operator": i.operator or "",
                              "status": i.status} for i in itvs],
        }


def assign_warning(user, warning_id, owner_id, owner_name) -> dict:
    if not owner_name:
        raise _bad("请选择跟进人")
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        if w.status == "CLOSED" or w.record_status == "VOIDED":
            raise _conflict("预警已关闭或已作废，无法指派")
        w.owner, w.version = owner_name, w.version + 1
        if w.status == "PENDING_HANDLE":
            w.status = "PROCESSING"
        if owner_id:
            from app.models import UnifiedTodo
            exist = db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_biz_id == w.id,
                UnifiedTodo.todo_type == TODO_TYPE, UnifiedTodo.assignee_id == int(owner_id),
                UnifiedTodo.is_deleted.is_(False))).first()
            if not exist:
                db.add(UnifiedTodo(tenant_id=_tid(), source_module="academic-affairs",
                                   source_biz_type="ACAD_WARNING", source_biz_id=w.id, todo_type=TODO_TYPE,
                                   assignee_id=int(owner_id), student_id=None,
                                   title=f"学业预警待处理：{w.reason or ''}", status="PENDING"))
        _audit(db, "ACAD_WARNING", w.id, "ASSIGN", f"指派给 {owner_name}")
        db.commit()
        return {"warningId": str(w.id), "owner": owner_name, "status": w.status}


def add_intervention(user, warning_id, way, content, result="", next_plan="") -> dict:
    content = (content or "").strip()
    if len(content) < 5:
        raise _bad("跟进内容不少于 5 个字")
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        if w.status == "CLOSED" or w.record_status == "VOIDED":
            raise _conflict("预警已关闭或已作废，无法记录跟进")
        from app.models import AcademicIntervention
        name, _role = _op()
        itv = AcademicIntervention(tenant_id=_tid(), warning_id=w.id, way=way or "TALK", content=content,
                                   result=(result or "").strip() or None,
                                   next_plan=(next_plan or "").strip() or None, operator=name, status="OPEN",
                                   follow_time=datetime.utcnow())
        db.add(itv)
        if w.status == "PENDING_HANDLE":
            w.status, w.version = "PROCESSING", w.version + 1
        _audit(db, "ACAD_WARNING", w.id, "INTERVENTION", content[:200])
        db.commit()
        return {"warningId": str(w.id), "interventionId": str(itv.id), "status": w.status}


def escalate_warning(user, warning_id, reason) -> dict:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _bad("升级说明不少于 5 个字")
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        if w.status == "CLOSED" or w.record_status == "VOIDED":
            raise _conflict("预警已关闭或已作废，无法升级")
        before = w.status
        w.status, w.level, w.version = "ESCALATED", "HIGH", w.version + 1
        _audit(db, "ACAD_WARNING", w.id, "ESCALATE", reason, before, "ESCALATED")
        db.commit()
        return {"warningId": str(w.id), "status": w.status}


def close_warning(user, warning_id, result) -> dict:
    result = (result or "").strip()
    if len(result) < 5:
        raise _bad("关闭说明不少于 5 个字")
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        if w.status == "CLOSED":
            raise _conflict("预警已关闭")
        if w.record_status == "VOIDED":
            raise _conflict("预警已作废，无法关闭")
        before = w.status
        w.status, w.close_result, w.version = "CLOSED", result, w.version + 1
        mark_todos_done(db, w.id)
        _audit(db, "ACAD_WARNING", w.id, "CLOSE", result, before, "CLOSED")
        db.commit()
        return {"warningId": str(w.id), "status": w.status}


def void_warning(user, warning_id, reason) -> dict:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise _bad("误报说明不少于 5 个字")
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        if w.status == "CLOSED":
            raise _conflict("预警已关闭，无法作废")
        if w.record_status == "VOIDED":
            raise _conflict("预警已作废")
        before = w.status
        w.record_status, w.void_reason, w.version = "VOIDED", reason, w.version + 1
        mark_todos_done(db, w.id)
        _audit(db, "ACAD_WARNING", w.id, "VOID", reason, before, "VOIDED")
        db.commit()
        return {"warningId": str(w.id), "recordStatus": w.record_status}


def remind_warning(user, warning_id) -> dict:
    """预警跟进页「提醒」：不再只是计数器，真实向学生本人+责任辅导员各推一条站内通知
    （message_type=ACAD_WARNING_REMIND），与预警首次生成的通知同源可查（见「预警通知」页）。"""
    with session() as db:
        w = _warning_or_404(db, warning_id)
        _assert_handle_allowed(db, user, w)
        if w.status == "CLOSED" or w.record_status == "VOIDED":
            raise _conflict("预警已关闭或已作废，无法提醒")
        w.remind_count, w.version = (w.remind_count or 0) + 1, w.version + 1
        cid, sid = _counselor_of(db, w.acad_student_id)
        sent = _push_warning_notice(db, w, cid, sid, NOTICE_REMIND)
        _audit(db, "ACAD_WARNING", w.id, "REMIND", f"第 {w.remind_count} 次提醒，推送通知 {sent} 条")
        db.commit()
        try:
            from app.services.message_event_outbox_service import process_pending_outbox
            process_pending_outbox(limit=20, worker_id="aa-warning-inline")
        except Exception:  # noqa: BLE001
            pass
        return {"warningId": str(w.id), "remindCount": w.remind_count, "notified": sent}


# ═══════════ 预警通知台账（读侧；t_unified_message，供「预警通知」三级菜单） ═══════════

def list_notifications(user, warning_id=None, page=1, page_size=20):
    """预警通知台账列表：t_unified_message 中 source_module=academic-affairs 且
    message_type∈{ACAD_WARNING_NEW,ACAD_WARNING_REMIND} 的推送记录，经 source_biz_id 关联回
    t_acad_warning 还原学生/级别/来源展示信息。数据范围收敛口径与 list_warnings 一致
    （未指定 warning_id 时按当前角色数据范围过滤）。warning_id 传入时仅看该预警下的通知
    （预警跟进详情页可复用），且仍需落在数据范围内，否则视为不可见（空列表，不 404，避免探测）。"""
    from app.models import AcademicStudent, AcademicWarning, UnifiedMessage
    with session() as db:
        join_w = and_(UnifiedMessage.source_biz_id == AcademicWarning.id,
                      UnifiedMessage.tenant_id == AcademicWarning.tenant_id)
        join_s = and_(AcademicStudent.id == AcademicWarning.acad_student_id,
                      AcademicStudent.tenant_id == AcademicWarning.tenant_id)
        conds = [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
                 UnifiedMessage.source_module == "academic-affairs",
                 UnifiedMessage.message_type.in_(NOTICE_TYPES)]
        if warning_id:
            conds.append(UnifiedMessage.source_biz_id == int(warning_id))
        scope_ids = _scope_acad_ids(db, user)
        if scope_ids is not None:
            if not scope_ids:
                return [], 0
            conds.append(AcademicWarning.acad_student_id.in_(scope_ids))
        total = db.scalar(select(func.count()).select_from(UnifiedMessage)
                          .join(AcademicWarning, join_w).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(UnifiedMessage, AcademicWarning, AcademicStudent)
                          .select_from(UnifiedMessage).join(AcademicWarning, join_w)
                          .outerjoin(AcademicStudent, join_s).where(*conds)
                          .order_by(UnifiedMessage.id.desc()).offset(offset).limit(page_size)).all()
        out = []
        for m, w, a in rows:
            receiver_is_student = bool(a and a.student_id and int(a.student_id) == int(m.receiver_id))
            out.append({
                "id": str(m.id), "warningId": str(w.id), "studentName": a.name if a else "",
                "className": a.class_name if a else "", "level": w.level,
                "sourceCode": w.source_code or "", "sourceLabel": SOURCE_LABELS.get(w.source_code or "", w.source_code or ""),
                "receiverType": "STUDENT" if receiver_is_student else "COUNSELOR",
                "title": m.title, "content": m.content or "", "scene": m.message_type,
                "status": m.status, "sentAt": _iso(m.created_at), "readAt": _iso(m.read_at),
            })
        return out, total


def notification_summary(user) -> dict:
    """预警通知台账统计：累计推送 / 未读 / 已读（数据范围同 list_notifications）。"""
    from app.models import AcademicWarning, UnifiedMessage
    with session() as db:
        join_w = and_(UnifiedMessage.source_biz_id == AcademicWarning.id,
                      UnifiedMessage.tenant_id == AcademicWarning.tenant_id)
        conds = [UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
                 UnifiedMessage.source_module == "academic-affairs",
                 UnifiedMessage.message_type.in_(NOTICE_TYPES)]
        scope_ids = _scope_acad_ids(db, user)
        if scope_ids is not None:
            if not scope_ids:
                return {"total": 0, "unread": 0, "read": 0}
            conds.append(AcademicWarning.acad_student_id.in_(scope_ids))
        rows = db.execute(select(UnifiedMessage.status, func.count()).select_from(UnifiedMessage)
                          .join(AcademicWarning, join_w).where(*conds)
                          .group_by(UnifiedMessage.status)).all()
        by_status = {r[0]: r[1] for r in rows}
        total = sum(by_status.values())
        return {"total": total, "unread": by_status.get("UNREAD", 0), "read": by_status.get("READ", 0)}
