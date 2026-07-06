"""13B-P1 学籍状态单一写入口（集成③，全平台红线）。

change_student_status() 是全平台**唯一**允许写 t_student_profile.student_status 的函数。
五件事同一事务：①校验合法转移(非法→422) ②乐观锁改主档(version+1) ③写 t_aa_status_change 流水
④写 t_student_stage_event(source_module=academic-affairs) ⑤audit_log.record。
在籍判定 is_enrolled() 供 13A/13B 全域入口校验（休学生禁请假/选课等）。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.services.db_service import _tid, audit_insert

# 受控扩展的 student_status 取值（t_student_profile 零加列，仅扩枚举）。
STATUSES = {"NORMAL", "MERGED", "RECYCLED", "PENDING_REGISTER", "REGISTERED", "UNREGISTERED",
            "SUSPENDED", "RETAINED", "WITHDRAWN", "TRANSFER_SCHOOL", "GRADUATED", "COMPLETED",
            "INCOMPLETE"}

# 在籍语义：这些状态视为"在籍"（可发起请假/选课等）。
_ENROLLED = {"NORMAL", "REGISTERED", "RETAINED"}

# 合法转移白名单（from → {允许的 to}）。P1 覆盖注册类；异动类 P2 扩展。
_TRANSITIONS = {
    "NORMAL": {"PENDING_REGISTER", "REGISTERED", "SUSPENDED", "WITHDRAWN", "TRANSFER_SCHOOL",
               "GRADUATED", "COMPLETED", "INCOMPLETE", "RECYCLED"},
    "PENDING_REGISTER": {"REGISTERED", "UNREGISTERED"},
    "UNREGISTERED": {"PENDING_REGISTER", "REGISTERED", "WITHDRAWN"},
    "REGISTERED": {"REGISTERED", "SUSPENDED", "WITHDRAWN", "TRANSFER_SCHOOL", "RETAINED",
                   "GRADUATED", "COMPLETED", "INCOMPLETE"},  # REGISTERED→REGISTERED 学年重复注册
    "SUSPENDED": {"REGISTERED", "RESUME", "WITHDRAWN", "RETAINED"},
    "RETAINED": {"REGISTERED", "SUSPENDED", "WITHDRAWN"},
}


def is_enrolled(student_status: str | None) -> bool:
    """在籍判定：REGISTERED/NORMAL/RETAINED 为 True，休学/退学/毕业等为 False。"""
    return (student_status or "NORMAL") in _ENROLLED


def can_transition(from_status: str | None, to_status: str) -> bool:
    frm = from_status or "NORMAL"
    if frm == to_status and to_status in ("REGISTERED",):
        return True
    return to_status in _TRANSITIONS.get(frm, set())


def change_student_status(db, student_id, to_status, change_type, reason="", operator="",
                          source_biz_id=None, term_code=None) -> dict:
    """全平台唯一 student_status 写入口。db 为调用方事务会话（本函数不 commit）。"""
    from app.models import AaStatusChange, StudentProfile, StudentStageEvent
    if to_status not in STATUSES:
        raise AppException("VALIDATION_ERROR", f"非法目标学籍状态：{to_status}")
    s = db.get(StudentProfile, int(student_id))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    frm = s.student_status
    # ① 合法转移校验
    if not can_transition(frm, to_status):
        raise AppException("VALIDATION_ERROR", f"学籍状态不允许 {frm} → {to_status}")
    # ② 乐观锁更新主档
    s.student_status = to_status
    s.version = (s.version or 0) + 1
    # ③ 写异动流水
    db.add(AaStatusChange(tenant_id=_tid(), student_id=int(student_id), change_type=change_type,
                          from_status=frm, to_status=to_status, reason=reason,
                          effective_date=datetime.utcnow(), term_code=term_code,
                          source_biz_id=(int(source_biz_id) if source_biz_id else None),
                          status="EFFECTIVE"))
    # ④ 进 360
    db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(student_id), from_stage=frm,
                             to_stage=to_status, reason=f"学籍异动（{change_type}）",
                             source_module="academic-affairs"))
    # ⑤ 安全审计（延迟到调用方 commit 后由 audit_insert 自身事务落库）
    return {"studentId": str(student_id), "fromStatus": frm, "toStatus": to_status,
            "changeType": change_type}


def audit_status_change(student_id, from_status, to_status, change_type, operator=""):
    """在 change_student_status 所在事务 commit 后调用，落安全审计（audit_insert 自带事务）。"""
    audit_insert("STUDENT_STATUS_CHANGE", "student_profile",
                 {"studentId": str(student_id), "from": from_status, "to": to_status,
                  "changeType": change_type, "operator": operator}, "SUCCESS")
