"""13B-P1 学籍状态单一写入口（Stage C1 temporal fact canonicalized）。

change_student_status() 是全平台允许发起学籍状态/组织归属生效的统一命令入口。
Stage C1 起，当前 ``StudentProfile`` 只是热路径投影；真正的学籍身份变化必须先经过
``append_student_academic_fact``，由同一事务完成：事实版本切换 + Profile CAS 投影 +
异动流水 + 360 事件。任何事实缺失、重叠或 Profile/fact 漂移都 fail-closed。
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
                          to_college_id=None, to_major_id=None, to_class_id=None,
                          expected_student_version=None) -> dict:
    """Canonical academic-identity apply command. Caller owns commit/rollback.

    ``existing_change_id``: final approval reuses the existing status-change request.
    ``to_college/major/class``: transfer/resume may move the current organization projection.
    ``expected_student_version``: version frozen when the request was submitted. A stale
    request fails 409 before any fact/workflow/audit side effect can commit.
    """
    from app.models import AaStatusChange, StudentProfile, StudentStageEvent
    from app.modules.academic_affairs.services.academic_affairs_student_fact_service import (
        append_student_academic_fact,
        resolve_student_academic_fact,
    )

    if to_status not in STATUSES:
        raise AppException("VALIDATION_ERROR", f"非法目标学籍状态：{to_status}")

    # Lock current projection first so transition validation and the canonical append see
    # one serialized student identity. The append command locks the same row again in this
    # transaction and also performs its own CAS/ledger integrity checks.
    s = db.query(StudentProfile).filter(
        StudentProfile.id == int(student_id),
        StudentProfile.tenant_id == _tid(),
    ).with_for_update().first()
    if not s or s.is_deleted:
        raise AppException("DATA_NOT_FOUND", "学生不存在")
    if expected_student_version is not None and int(s.version or 0) != int(expected_student_version):
        raise AppException(
            "APPROVAL_VERSION_CONFLICT",
            "学生主档在本申请在途期间已被改写，请重新核对后再终审",
            details={"expectedVersion": int(expected_student_version), "currentVersion": int(s.version or 0)},
            http_status=409,
        )

    frm = s.student_status
    if frm in ("MERGED", "RECYCLED", "WITHDRAWN", "GRADUATED") and to_status != frm:
        raise AppException("VALIDATION_ERROR", f"学生已处于终态 {frm}，不可再发起学籍异动")
    if not can_transition(frm, to_status):
        raise AppException("VALIDATION_ERROR", f"学籍状态不允许 {frm} → {to_status}")

    target_college = s.college_id if to_college_id is None else int(to_college_id)
    target_major = s.major_id if to_major_id is None else int(to_major_id)
    target_class = s.class_id if to_class_id is None else int(to_class_id)
    identity_changed = (
        to_status != frm
        or target_college != s.college_id
        or target_major != s.major_id
        or target_class != s.class_id
    )
    applied_at = datetime.utcnow()

    if identity_changed:
        fact, s = append_student_academic_fact(
            db,
            int(student_id),
            effective_at=applied_at,
            student_status=to_status,
            college_id=target_college,
            major_id=target_major,
            class_id=target_class,
            source_type=change_type,
            source_ref_id=(int(existing_change_id) if existing_change_id else
                           int(source_biz_id) if source_biz_id else None),
            source_quality="EXACT",
            expected_student_version=expected_student_version,
            created_by=(int(operator) if str(operator or "").isdigit() else None),
        )
        fact_version = int(fact.version_no)
    else:
        # Annual re-registration can be REGISTERED -> REGISTERED. It is a business event,
        # not a new academic identity; do not manufacture an identical fact/version.
        fact = resolve_student_academic_fact(db, int(student_id), applied_at, for_update=True)
        fact_version = int(fact.version_no)

    if existing_change_id:
        row = db.get(AaStatusChange, int(existing_change_id))
        if row:
            row.from_status, row.to_status = frm, to_status
            row.effective_date, row.status = applied_at, "EFFECTIVE"
    else:
        db.add(AaStatusChange(tenant_id=_tid(), student_id=int(student_id), change_type=change_type,
                              from_status=frm, to_status=to_status, reason=reason,
                              effective_date=applied_at, term_code=term_code,
                              source_biz_id=(int(source_biz_id) if source_biz_id else None),
                              status="EFFECTIVE"))

    db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(student_id), from_stage=frm,
                             to_stage=to_status, reason=f"学籍异动（{change_type}）",
                             source_module="academic-affairs"))
    return {"studentId": str(student_id), "fromStatus": frm, "toStatus": to_status,
            "changeType": change_type, "academicFactVersion": fact_version}


def audit_status_change(student_id, from_status, to_status, change_type, operator=""):
    """在 change_student_status 所在事务 commit 后调用，落安全审计（audit_insert 自带事务）。"""
    audit_insert("STUDENT_STATUS_CHANGE", "student_profile",
                 {"studentId": str(student_id), "from": from_status, "to": to_status,
                  "changeType": change_type, "operator": operator}, "SUCCESS")
