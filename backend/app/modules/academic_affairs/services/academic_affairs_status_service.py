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
# PRESERVED（保留学籍）为 R3 补建：与 RETAINED（留级）是法规层面两个完全不同的概念，不可合并——
#   · 保留学籍：教育部令41号第二十七/二十八条**直接规定**的非学业情形（应征入伍保留至退役后2年、
#     跨校联合培养期间保留），特征是"人不在校、学籍留着"，第二十八条明确"不享受在校学习学生待遇"；
#   · 留级：41号令全文仅第十五条一句"升级、跳级、留级、降级等要求，由学校规定"，属学校自定的
#     学业处理，特征是"人在校、年级退回重读"。
# 中职差异（如实标注）：《中等职业学校学生学籍管理办法》教职成〔2010〕7号全文无"保留学籍"，
#   中职依法服兵役按**休学**处理（第十七条），但留级明确存在（第二十四条）。本系统同时服务中职/
#   高职（见 SchoolClass.training_level），故两种状态都保留；中职租户可不使用保留学籍入口。
STATUSES = {"NORMAL", "MERGED", "RECYCLED", "PENDING_REGISTER", "REGISTERED", "UNREGISTERED",
            "SUSPENDED", "PRESERVED", "RETAINED", "WITHDRAWN", "TRANSFER_SCHOOL", "GRADUATED",
            "COMPLETED", "INCOMPLETE"}

# 在籍语义：这些状态视为"在籍"（可发起请假/选课等）。
# RETAINED（留级）在籍——学生正常在校上课，只是编入下一年级重读。
# PRESERVED（保留学籍）**不在籍**——人已离校（入伍/联培），41号令第二十八条"不享受在校学习学生待遇"；
#   与项目既有对外报送口径一致（demo-data/07-演示数据字段口径.md：自然口径=在册+休学+保留学籍+
#   保留入学资格，即"在册"口径不含保留学籍）。若误算入在籍，会虚增对教育主管部门报送的在册学生数。
_ENROLLED = {"NORMAL", "REGISTERED", "RETAINED"}

# 合法转移白名单（from → {允许的 to}）。P1 覆盖注册类；异动类 P2 扩展。
_TRANSITIONS = {
    "NORMAL": {"PENDING_REGISTER", "REGISTERED", "SUSPENDED", "PRESERVED", "WITHDRAWN",
               "TRANSFER_SCHOOL", "GRADUATED", "COMPLETED", "INCOMPLETE", "RECYCLED"},
    "PENDING_REGISTER": {"REGISTERED", "UNREGISTERED"},
    "UNREGISTERED": {"PENDING_REGISTER", "REGISTERED", "WITHDRAWN"},
    "REGISTERED": {"REGISTERED", "SUSPENDED", "PRESERVED", "WITHDRAWN", "TRANSFER_SCHOOL",
                   "RETAINED", "GRADUATED", "COMPLETED", "INCOMPLETE"},  # REGISTERED→REGISTERED 学年重复注册
    "SUSPENDED": {"REGISTERED", "RESUME", "WITHDRAWN", "RETAINED"},
    # 保留学籍期满复学→REGISTERED；期满未复学可退学（41号令第三十条(二)：休学、保留学籍期满，
    # 在学校规定期限内未提出复学申请或申请复学经复查不合格的，学校可予退学处理）。
    "PRESERVED": {"REGISTERED", "WITHDRAWN"},
    "RETAINED": {"REGISTERED", "SUSPENDED", "WITHDRAWN"},
}


def is_enrolled(student_status: str | None) -> bool:
    """在籍判定：REGISTERED/NORMAL/RETAINED 为 True；休学/保留学籍/退学/毕业等为 False。
    注意 RETAINED(留级) 在籍、PRESERVED(保留学籍) 不在籍，二者语义相反，勿混（见 STATUSES 注释）。"""
    return (student_status or "NORMAL") in _ENROLLED


def can_transition(from_status: str | None, to_status: str) -> bool:
    frm = from_status or "NORMAL"
    if frm == to_status and to_status in ("REGISTERED",):
        return True
    return to_status in _TRANSITIONS.get(frm, set())


def change_student_status(db, student_id, to_status, change_type, reason="", operator="",
                          source_biz_id=None, term_code=None, existing_change_id=None,
                          to_college_id=None, to_major_id=None, to_class_id=None) -> dict:
    """全平台唯一 student_status 写入口。db 为调用方事务会话（本函数不 commit）。

    existing_change_id：异动审批终审时把既有异动单置 EFFECTIVE（不新建流水）；无则新建一行（如注册）。
    to_college/major/class：转专业/复学定班时同步迁移主档院系班（真实业务需要）。
    """
    from app.models import AaStatusChange, StudentProfile, StudentStageEvent
    if to_status not in STATUSES:
        raise AppException("VALIDATION_ERROR", f"非法目标学籍状态：{to_status}")
    s = db.get(StudentProfile, int(student_id))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    frm = s.student_status
    # 终态学生禁再异动（MERGED/RECYCLED/WITHDRAWN/GRADUATED）
    if frm in ("MERGED", "RECYCLED", "WITHDRAWN", "GRADUATED") and to_status != frm:
        raise AppException("VALIDATION_ERROR", f"学生已处于终态 {frm}，不可再发起学籍异动")
    # ① 合法转移校验
    if not can_transition(frm, to_status):
        raise AppException("VALIDATION_ERROR", f"学籍状态不允许 {frm} → {to_status}")
    # ② 乐观锁更新主档（含转专业/复学迁移院系班）
    s.student_status = to_status
    if to_college_id is not None:
        s.college_id = int(to_college_id)
    if to_major_id is not None:
        s.major_id = int(to_major_id)
    if to_class_id is not None:
        s.class_id = int(to_class_id)
    s.version = (s.version or 0) + 1
    # ③ 写/更新异动流水
    if existing_change_id:
        row = db.get(AaStatusChange, int(existing_change_id))
        if row:
            row.from_status, row.to_status = frm, to_status
            row.effective_date, row.status = datetime.utcnow(), "EFFECTIVE"
    else:
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
