"""13B-P2 学籍异动全链路（休学/复学/退学/转专业/留级/转班）。

各类异动多节点审批（ACAD_STATUS_*），终审经 change_student_status() 单一入口生效。
真实业务补充：休学到期日(最长年限 suspendMaxYears，规则中心默认2年)；复学校验未超期；
转专业/复学终审同步迁移主档院系班。在途异动重复 409；终态学生禁发起 422。

TRANSFER_CLASS（转班，学籍异动三级模块续工·第三轮补缺）：同专业换班，区别于跨专业的
TRANSFER_MAJOR——学院/专业不变，仅 to_class_id 变更；审批节点复用 SUSPEND/WITHDRAW 的三节点
序列（无需 OUT/IN 学院拆分，因专业不跨院）；目标班须同专业+在读(class_status=NORMAL)+非当前班，
校验失败 422/409；目标学院/专业由服务端按学生当前专业强制推导，不采信客户端传参，防止越权篡改。

数据范围（Tier1 R1 补强，对齐 13B-教务中心页面级交互与按钮动作矩阵 §2.7/2.8）：
教务处/校管（TENANT_ALL）全校；学院教务（COLLEGE）限本院（转专业按 from/to 学院双向可见）；
辅导员/普通教师限本班（TeacherStudentScope CLASS，from/to 双向可见）。范围解析复用
build_affairs_context（与调停课/选课等同族模块同一套安全上下文），fail-closed：未配置范围→空列表/403002。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.modules.academic_affairs.services.academic_affairs_status_service import (audit_status_change,
                                                          change_student_status, is_enrolled)
from app.services.db_service import _iso, _tid, session

# change_type → (目标学籍状态, 审批节点序列)
CHANGE_FLOW = {
    "SUSPEND": ("SUSPENDED", ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "WITHDRAW": ("WITHDRAWN", ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "RESUME": ("REGISTERED", ["COUNSELOR_REVIEW", "COLLEGE_ASSIGN_CLASS", "AA_OFFICE_FINAL"]),
    # 保留学籍（PRESERVE）与留级（RETAIN）是两个独立异动类型，勿合并——法规依据、在校状态、
    # 触发原因全不同（详见 academic_affairs_status_service.STATUSES 注释）。审批链沿用休学同款三级
    # （辅导员→学院→教务处）：41号令第二十七条的入伍情形，学校实务中另需武装部核验（如山东农业大学
    # 《学籍异动办理流程说明》"参军入伍保留学籍的报学校武装部审核通过后统一办理"），本系统未建武装部
    # 角色，该环节走线下，系统内以教务处终审为准——如实标注，不假装系统已覆盖武装部审核。
    "PRESERVE": ("PRESERVED", ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "RETAIN": ("RETAINED", ["COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    "TRANSFER_MAJOR": ("REGISTERED", ["COUNSELOR_REVIEW", "OUT_COLLEGE_REVIEW",
                                      "IN_COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
    # 转班（学籍异动三级模块续工）：同专业换班，学院/专业不变仅换班，三节点同 SUSPEND/WITHDRAW。
    "TRANSFER_CLASS": ("REGISTERED", ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "AA_OFFICE_FINAL"]),
}
_WF_CODE = {"SUSPEND": "ACAD_STATUS_SUSPEND", "WITHDRAW": "ACAD_STATUS_WITHDRAW",
            "RESUME": "ACAD_STATUS_RESUME", "PRESERVE": "ACAD_STATUS_PRESERVE",
            "RETAIN": "ACAD_STATUS_RETAIN",
            "TRANSFER_MAJOR": "ACAD_STATUS_TRANSFER_MAJOR",
            "TRANSFER_CLASS": "ACAD_STATUS_TRANSFER_CLASS"}
_ACTIVE = {"DRAFT", "SUBMITTED", "IN_REVIEW"}  # 在途（未终结）异动状态

L_CT = {"SUSPEND": "休学", "WITHDRAW": "退学", "RESUME": "复学",
        "PRESERVE": "保留学籍", "RETAIN": "留级",
        "TRANSFER_MAJOR": "转专业", "TRANSFER_CLASS": "转班"}

# 审批节点 → 所需 permissionCode（Tier1 R1：异动审批权限实例化）。
# COUNSELOR_REVIEW=辅导员初审；COLLEGE_REVIEW/OUT_COLLEGE_REVIEW/COLLEGE_ASSIGN_CLASS=原学院教务（转出/复学分班）；
# IN_COLLEGE_REVIEW=目标学院教务接收（仅转专业）；AA_OFFICE_FINAL=教务处终审。
_NODE_PERM = {
    "COUNSELOR_REVIEW": "academicAffairs.statusChange.counselorReview",
    "COLLEGE_REVIEW": "academicAffairs.statusChange.collegeReview",
    "OUT_COLLEGE_REVIEW": "academicAffairs.statusChange.collegeReview",
    "COLLEGE_ASSIGN_CLASS": "academicAffairs.statusChange.collegeReview",
    "IN_COLLEGE_REVIEW": "academicAffairs.statusChange.collegeReview",
    "AA_OFFICE_FINAL": "academicAffairs.statusChange.officeReview",
}


def _check_node_authority(db, user, node, x) -> None:
    """审批节点授权：permissionCode 命中 + 数据范围收敛（TENANT_ALL 全通过；COLLEGE/CLASS 按 from/to 双向）。

    IN_COLLEGE_REVIEW（转专业目标学院接收）按 to_college_id/to_class_id 收敛，
    其余节点（含转出/复学/休退学）按 from_college_id/from_class_id 收敛；AA_OFFICE_FINAL 仅 TENANT_ALL。
    """
    perm = _NODE_PERM.get(node)
    if not perm or not has_permission(user, perm):
        raise no_permission(f"无权审批当前节点（{node}）")
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return
    if node == "AA_OFFICE_FINAL":
        raise no_data_scope("教务处终审仅限教务处/校管操作")
    if node == "IN_COLLEGE_REVIEW":
        if ctx.scope_type == "COLLEGE":
            if x.to_college_id and int(x.to_college_id) in ctx.college_ids:
                return
            raise no_data_scope("该异动的目标学院不在您的管理范围内")
        allowed = ctx.allowed_class_ids(db)
        if x.to_class_id and allowed and int(x.to_class_id) in allowed:
            return
        raise no_data_scope("该异动不在您的数据范围内")
    if node == "COUNSELOR_REVIEW":
        allowed = ctx.allowed_class_ids(db)
        if x.from_class_id and allowed and int(x.from_class_id) in allowed:
            return
        raise no_data_scope("该异动不在您的班级范围内")
    # COLLEGE_REVIEW / OUT_COLLEGE_REVIEW / COLLEGE_ASSIGN_CLASS：原学院教务（本院/本班）
    if ctx.scope_type == "COLLEGE":
        if x.from_college_id and int(x.from_college_id) in ctx.college_ids:
            return
        raise no_data_scope("该异动的原学院不在您的管理范围内")
    allowed = ctx.allowed_class_ids(db)
    if x.from_class_id and allowed and int(x.from_class_id) in allowed:
        return
    raise no_data_scope("该异动不在您的数据范围内")


def _scope_conds(db, ctx):
    """列表/统计范围过滤条件（TENANT_ALL→无条件；COLLEGE→from/to 学院双向；CLASS→from/to 班级双向；
    fail-closed：未配置范围返回 False 恒假条件）。"""
    from app.models import AaStatusChange
    if ctx.scope_type == "TENANT_ALL":
        return []
    if ctx.scope_type == "COLLEGE":
        if not ctx.college_ids:
            return [AaStatusChange.id == -1]
        ids = list(ctx.college_ids)
        return [or_(AaStatusChange.from_college_id.in_(ids), AaStatusChange.to_college_id.in_(ids))]
    allowed = ctx.allowed_class_ids(db)
    if not allowed:
        return [AaStatusChange.id == -1]
    ids = list(allowed)
    return [or_(AaStatusChange.from_class_id.in_(ids), AaStatusChange.to_class_id.in_(ids))]


def _suspend_max_years() -> int:
    """规则中心 academicAffairs.status.suspendMaxYears，默认 2 年。"""
    from app.services.platform_service import get_config_json
    cfg = get_config_json(_tid(), "ACAD_RULE", "suspend_max_years")
    try:
        return int(cfg.get("years")) if cfg and cfg.get("years") else 2
    except (TypeError, ValueError):
        return 2


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_STATUS_CHANGE",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n or uid, role_name=r, detail=detail, occurred_at=datetime.utcnow()))


def _assignee_for(db, node, student_id):
    if node in ("COUNSELOR_REVIEW",) and student_id:
        from app.models import SchoolClass, StudentProfile
        s = db.get(StudentProfile, int(student_id))
        if s and s.class_id:
            c = db.get(SchoolClass, int(s.class_id))
            if c and c.counselor_id:
                return int(c.counselor_id)
    return 0


def _open_wf(db, wf_code, sc_id, applicant_id, title, first_node, assignee):
    from app.models import WorkflowInstance, WorkflowTask
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=wf_code, source_module="academic-affairs",
                            source_biz_type="AA_STATUS_CHANGE", source_biz_id=int(sc_id),
                            applicant_id=int(applicant_id or 0), title=title, status="RUNNING",
                            current_node=first_node)
    db.add(inst)
    db.flush()
    db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=first_node,
                        assignee_id=int(assignee or 0), status="PENDING"))
    return inst


def _todo_upsert(db, sc_id, assignee, student_id, title):
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_id == int(sc_id), UnifiedTodo.todo_type == "AA_STATUS_APPROVAL",
        UnifiedTodo.assignee_id == int(assignee or 0), UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", row.version + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module="academic-affairs",
                           source_biz_type="AA_STATUS_CHANGE", source_biz_id=int(sc_id),
                           todo_type="AA_STATUS_APPROVAL", assignee_id=int(assignee or 0),
                           student_id=student_id, title=title, status="PENDING"))


def _todo_done(db, sc_id):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
            UnifiedTodo.source_biz_id == int(sc_id), UnifiedTodo.todo_type == "AA_STATUS_APPROVAL",
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", r.version + 1


def _msg(db, receiver_id, title, content, mtype, sc_id):
    from app.models import UnifiedMessage
    db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=int(receiver_id or 0),
                          source_module="academic-affairs", source_biz_id=int(sc_id),
                          title=title, content=content, message_type=mtype, status="UNREAD"))


def _row(x, s=None) -> dict:
    return {"changeId": str(x.id), "studentId": str(x.student_id),
            "realName": s.real_name if s else "", "changeType": x.change_type,
            "changeTypeLabel": L_CT.get(x.change_type, x.change_type),
            "fromStatus": x.from_status, "toStatus": x.to_status, "reason": x.reason or "",
            "status": x.status, "currentNode": x.current_node or "",
            "effectiveDate": _iso(x.effective_date), "expireDate": _iso(x.expire_date),
            "toClassId": str(x.to_class_id or ""), "toMajorId": str(x.to_major_id or ""),
            "version": x.version}


def _load(db, sc_id):
    from app.models import AaStatusChange, StudentProfile
    x = db.get(AaStatusChange, int(sc_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("异动单不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


# ═══════════ 发起异动 ═══════════

def submit(body, user) -> dict:
    ct = (body.changeType or "").upper()
    if ct not in CHANGE_FLOW:
        raise AppException("VALIDATION_ERROR", "异动类型非法")
    student_id = int(body.studentId)
    with session() as db:
        from app.models import AaStatusChange, StudentProfile
        from app.modules.academic_affairs.services.academic_affairs_archive_service import (
            guard_term_writable_current)
        s = db.get(StudentProfile, student_id)
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        guard_term_writable_current(db)  # 归档11卡§6.2：已归档学期不应受理新异动申请（降级为当前学期判据）
        # 数据范围：教务处/校管全校代录；学院教务仅本院学生；未配置范围一律 403002（fail-closed）。
        # SELF（学生本人）豁免：本函数是移动端"唯一学生写入口"submit_status_change_my 的落地点，
        # 那里 studentId 恒由 _me(user) 服务端解析出的本人档案 id 构造，从不取客户端传参，此处
        # 已有的 db.get(StudentProfile,...) 存在性校验已覆盖越租户/软删；require_student() 只按
        # TENANT_ALL/COLLEGE/CLASS/STUDENT/DORM_BUILDING 裁决、无 SELF 分支，误命中会把"本人"当
        # "空范围"拒绝（真实 bug：学生自助异动此前恒 403，此次一并修复，非本模块新引入）。
        ctx = build_affairs_context(user, db)
        if ctx.scope_type not in ("TENANT_ALL", "SELF"):
            ctx.require_student(db, student_id)
        cur = s.student_status
        # 终态学生禁发起
        if cur in ("MERGED", "RECYCLED", "WITHDRAWN", "GRADUATED"):
            raise AppException("VALIDATION_ERROR", f"学生已处于终态 {cur}，不可发起异动")
        # 前置状态校验（真实业务）
        if ct == "RESUME":
            # 休学(SUSPENDED)与保留学籍(PRESERVED)都是"人离校、学籍留着"，都经复学回到在籍
            # （41号令第三十条(二)把两者并列："休学、保留学籍期满，在学校规定期限内未提出复学申请…"）。
            if cur not in ("SUSPENDED", "PRESERVED"):
                raise AppException("DATA_CONFLICT", "仅休学中或保留学籍中的学生可申请复学")
            # 真实业务：休学超期未复学应作退学处理，禁复学。
            # 保留学籍不做同款超期拦截——41号令第二十七条的期限是"退役后2年"，退役日期在提交保留学籍
            # 申请时无法预知，故 expire_date 恒空（见下方 submit 落库处注释），此处按空值自然跳过。
            prior = db.scalars(select(AaStatusChange).where(
                AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == student_id,
                AaStatusChange.change_type.in_(("SUSPEND", "PRESERVE")),
                AaStatusChange.status == "EFFECTIVE",
                AaStatusChange.is_deleted.is_(False)).order_by(AaStatusChange.id.desc())).first()
            if prior and prior.expire_date and prior.expire_date < datetime.utcnow():
                raise AppException("DATA_CONFLICT", "休学已超过最长年限，应作退学处理，不可复学")
        if (ct in ("SUSPEND", "PRESERVE", "WITHDRAW", "RETAIN", "TRANSFER_MAJOR", "TRANSFER_CLASS")
                and not is_enrolled(cur)):
            raise AppException("DATA_CONFLICT", "仅在籍学生可发起该异动")
        # 转班（TRANSFER_CLASS）真实业务校验：目标班须存在、在读、且与学生当前专业一致（跨专业请走
        # 「转专业申请」）；目标班不得与当前班相同。目标学院/专业由服务端按学生当前值强制推导，
        # 不采信客户端传参，防止越权篡改到无关学院/专业。
        tc_college_id = tc_major_id = tc_class_id = None
        if ct == "TRANSFER_CLASS":
            from app.models import SchoolClass
            target_id = getattr(body, "toClassId", None)
            if not target_id:
                raise AppException("VALIDATION_ERROR", "转班需指定目标班级")
            target = db.get(SchoolClass, int(target_id))
            if not target or target.is_deleted or target.tenant_id != _tid():
                raise not_found("目标班级不存在")
            if target.class_status != "NORMAL":
                raise AppException("DATA_CONFLICT", "目标班级非在读状态，不可转入")
            if int(target.major_id or 0) != int(s.major_id or 0):
                raise AppException("VALIDATION_ERROR", "转班仅限同专业换班，跨专业请使用「转专业申请」")
            if s.class_id and int(target.id) == int(s.class_id):
                raise AppException("DATA_CONFLICT", "学生已在目标班级")
            tc_college_id, tc_major_id, tc_class_id = s.college_id, s.major_id, target.id
        # 在途异动重复 → 409
        dup = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == student_id,
            AaStatusChange.status.in_(list(_ACTIVE)), AaStatusChange.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该生存在在途学籍异动，不可重复发起")
        to_status, nodes = CHANGE_FLOW[ct]
        first = nodes[0]
        x = AaStatusChange(tenant_id=_tid(), student_id=student_id, change_type=ct,
                           from_status=cur, to_status=to_status, reason=getattr(body, "reason", None),
                           from_college_id=s.college_id, from_major_id=s.major_id, from_class_id=s.class_id,
                           to_college_id=(tc_college_id if ct == "TRANSFER_CLASS" else
                                          (int(body.toCollegeId) if getattr(body, "toCollegeId", None) else None)),
                           to_major_id=(tc_major_id if ct == "TRANSFER_CLASS" else
                                        (int(body.toMajorId) if getattr(body, "toMajorId", None) else None)),
                           to_class_id=(tc_class_id if ct == "TRANSFER_CLASS" else
                                        (int(body.toClassId) if getattr(body, "toClassId", None) else None)),
                           status="SUBMITTED", current_node=first)
        # 休学到期日（真实补充：最长年限）
        if ct == "SUSPEND":
            x.expire_date = datetime.utcnow() + timedelta(days=365 * _suspend_max_years())
        # 保留学籍不设 expire_date：41号令第二十七条的法定期限是"至退役后 2 年"，而退役日期在提交
        # 申请时不可知；跨校联合培养同理（培养期由联培协议定）。此处留空是如实建模，不是遗漏——
        # 真实到期日应在学生退役/联培结束回校办理复学时按实际情况认定，不由系统臆测。
        db.add(x)
        db.flush()
        assignee = _assignee_for(db, first, student_id)
        inst = _open_wf(db, _WF_CODE[ct], x.id, student_id, f"{s.real_name} {L_CT[ct]}", first, assignee)
        x.workflow_instance_id = inst.id
        _todo_upsert(db, x.id, assignee, student_id, f"{L_CT[ct]}待审：{s.real_name}")
        _audit(db, x.id, "SUBMIT", ct)
        db.commit()
        db.refresh(x)
        return _row(x, s)


# ═══════════ 审批（多节点）═══════════

def review(sc_id, user, action, reason="") -> dict:
    action = (action or "").upper()
    _n, _r, uid = _op()
    with session() as db:
        from app.models import WorkflowInstance, WorkflowTask
        from app.modules.academic_affairs.services.academic_affairs_archive_service import (
            guard_term_writable_current)
        x, s = _load(db, sc_id)
        guard_term_writable_current(db)  # 归档11卡§6.2：已归档学期的异动不应继续审批流转（降级为当前学期判据）
        if x.status not in _ACTIVE and x.status != "IN_REVIEW":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该异动当前状态不可审批")
        # 节点授权：permissionCode + 数据范围（辅导员限本班/学院教务限本院/教务处终审限 TENANT_ALL）
        _check_node_authority(db, user, x.current_node, x)
        nodes = CHANGE_FLOW[x.change_type][1]
        inst = db.get(WorkflowInstance, int(x.workflow_instance_id)) if x.workflow_instance_id else None
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == (inst.id if inst else 0),
            WorkflowTask.node_code == x.current_node, WorkflowTask.status == "PENDING",
            WorkflowTask.is_deleted.is_(False))).first() if inst else None
        if action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回/退回原因必填且不少于 5 字")
            if task:
                task.status, task.action_reason, task.acted_at = ("REJECTED" if action == "REJECT" else "TRANSFERRED"), reason.strip(), datetime.utcnow()
            x.status = "REJECTED" if action == "REJECT" else "RETURNED"
            x.version += 1
            if inst:
                inst.status = "REJECTED" if action == "REJECT" else "RETURNED"
            _todo_done(db, x.id)
            _msg(db, x.student_id, f"{L_CT[x.change_type]}{'未通过' if action == 'REJECT' else '被退回'}",
                 reason.strip(), "WORKFLOW_RESULT" if action == "REJECT" else "RETURNED_NOTICE", x.id)
            _audit(db, x.id, x.status, reason.strip())
            db.commit()
            db.refresh(x)
            return _row(x, s)
        if action != "APPROVE":
            raise AppException("VALIDATION_ERROR", "无效操作")
        if task:
            task.status, task.acted_at = "APPROVED", datetime.utcnow()
        i = nodes.index(x.current_node) if x.current_node in nodes else 0
        if i + 1 < len(nodes):
            nxt = nodes[i + 1]
            x.current_node, x.status, x.version = nxt, "IN_REVIEW", x.version + 1
            if inst:
                inst.current_node = nxt
            assignee = _assignee_for(db, nxt, x.student_id)
            db.add(WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=nxt,
                                assignee_id=assignee, status="PENDING"))
            _todo_upsert(db, x.id, assignee, x.student_id, f"{L_CT[x.change_type]}待审（{nxt}）：{s.real_name if s else ''}")
            _audit(db, x.id, "STEP", f"->{nxt}")
            db.commit()
            db.refresh(x)
            return _row(x, s)
        # 终审通过 → 经单一入口生效
        res = change_student_status(
            db, x.student_id, x.to_status, change_type=x.change_type, reason=x.reason or "",
            operator=uid, existing_change_id=x.id,
            to_college_id=x.to_college_id, to_major_id=x.to_major_id, to_class_id=x.to_class_id)
        if inst:
            inst.status = "APPROVED"
        _todo_done(db, x.id)
        _msg(db, x.student_id, f"{L_CT[x.change_type]}已生效",
             f"你的{L_CT[x.change_type]}申请已通过并生效", "WORKFLOW_RESULT", x.id)
        _audit(db, x.id, "EFFECTIVE", f"{res['fromStatus']}->{res['toStatus']}")
        db.commit()
        db.refresh(x)
        out = _row(x, s)
    audit_status_change(x.student_id, res["fromStatus"], res["toStatus"], x.change_type, uid)
    return out


# ═══════════ 查询 ═══════════

def get_change(sc_id, user) -> dict:
    with session() as db:
        x, s = _load(db, sc_id)
        return _row(x, s)


def list_changes(user, change_type=None, status=None, student_id=None, page=1, page_size=20):
    from app.models import AaStatusChange, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_service import REGISTRATION_CHANGE_TYPES
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False),
                 AaStatusChange.change_type.notin_(REGISTRATION_CHANGE_TYPES)]
        conds += _scope_conds(db, ctx)
        if change_type:
            conds.append(AaStatusChange.change_type == change_type)
        if status:
            conds.append(AaStatusChange.status == status)
        if student_id:
            conds.append(AaStatusChange.student_id == int(student_id))
        join = and_(StudentProfile.id == AaStatusChange.student_id,
                    StudentProfile.tenant_id == AaStatusChange.tenant_id)
        total = db.scalar(select(func.count()).select_from(AaStatusChange)
                          .outerjoin(StudentProfile, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AaStatusChange, StudentProfile)
                          .outerjoin(StudentProfile, join).where(*conds)
                          .order_by(AaStatusChange.id.desc()).offset(offset).limit(page_size)).all()
        out = [_row(x, s) for x, s in rows]
        return out, total


def stats(user, term_code=None) -> dict:
    """异动统计（Tier1「异动统计」）：按类型/状态/在途节点聚合，范围收敛同 list_changes。"""
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services.academic_affairs_service import REGISTRATION_CHANGE_TYPES
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False),
                 AaStatusChange.change_type.notin_(REGISTRATION_CHANGE_TYPES)]
        conds += _scope_conds(db, ctx)
        if term_code:
            conds.append(AaStatusChange.term_code == term_code)
        rows = db.scalars(select(AaStatusChange).where(*conds)).all()
        by_type, by_status, by_node = {}, {}, {}
        for r in rows:
            by_type[r.change_type] = by_type.get(r.change_type, 0) + 1
            by_status[r.status] = by_status.get(r.status, 0) + 1
            if r.status in _ACTIVE:
                key = r.current_node or "UNKNOWN"
                by_node[key] = by_node.get(key, 0) + 1
        return {
            "total": len(rows),
            "byType": [{"key": k, "label": L_CT.get(k, k), "count": v} for k, v in by_type.items()],
            "byStatus": [{"key": k, "count": v} for k, v in by_status.items()],
            "pendingByNode": [{"key": k, "count": v} for k, v in by_node.items()],
            "effective": by_status.get("EFFECTIVE", 0),
            "rejected": by_status.get("REJECTED", 0),
            "pending": sum(by_node.values()),
        }
