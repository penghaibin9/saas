"""SP-E02/E04：就业去向登记结构化提交 + 单节点真实审批 + 原子写回 canonical。

问题
────────────────────────────────────────────────────────────
学生 PC 的就业去向登记此前只是把 jobTitle/city/contact 拼进 `CsWorkOrder` 自由
文本工单：没有字段级 schema、没有 workflow、没有审批，`WorkflowInstance` 上从
未真正出现过 `EMPLOYMENT_DESTINATION` 这个 source_biz_type（S1~T6 各波次的
`approval_business_context_service` 未登记它，正是因为它当时确实不存在）。
批准与否全靠人工在工单列表里手动处理台账，没有原子写回。

定位
────────────────────────────────────────────────────────────
本模块是这条提交的 canonical 事实源：`EmpDestinationSubmission` 记录学生提交的
结构化字段与状态机；真实走 `t_workflow_instance/t_workflow_task`
（source_biz_type=EMPLOYMENT_DESTINATION）单节点审批（就业老师核准）；批准后
在**同一事务**内原子写回 `EmpStudent`（destination_type/company_name/
job_title）——不是"批准了再补一次台账更新"，是同一个 commit。

状态机（比 AaStatusChange 简单：单节点、无退回重开同一条记录）
────────────────────────────────────────────────────────────
SUBMITTED → APPROVED（原子写回 EmpStudent）
         → REJECTED（终止）
         → RETURNED（终止，学生需重新调用 submit() 发起新的一条提交——
                     与 AaStatusChange 的既有约定一致：RETURNED 不是"这条记录
                     可以原地编辑重开"，是"这次没通过，请重新提交"）

与 T5/#183 的证据门槛保持分层
────────────────────────────────────────────────────────────
本模块批准的是"去向登记的结构化事实"，不是"去向已核验"——不触碰
`EmpStudent.verify_status`。核验仍必须走独立的
`employment_destination_verification_service`（TP-E02，要求正式材料证据 +
乐观锁），批准提交只是让核验有一份可核验的结构化底稿，不是核验本身。

city/contact 没有 EmpStudent 对应列（canonical 台账从未建过），因此不写回台账，
只落在本表——字段不再像旧工单文本那样被截断丢失，如实标注，不假装已建立新台账列。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import EmpDestinationSubmission, EmpStudent
from app.modules.employment.services.employment_service import L_DEST
from app.services.db_service import _tid, session

WF_CODE = "EMPLOYMENT_DESTINATION_REVIEW"
REVIEW_NODE = "EMPLOYMENT_TEACHER_REVIEW"
SOURCE_MODULE = "employment"
SOURCE_BIZ_TYPE = "EMPLOYMENT_DESTINATION"
TODO_TYPE = "EMPLOYMENT_DESTINATION_REVIEW"

#: 在途（未终结）提交状态——同一学生同一时刻只能有一条在途提交。
_ACTIVE = {"SUBMITTED"}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, sub_id, action, detail=""):
    from app.models import EmpAuditTrail
    n, r = _op()
    db.add(EmpAuditTrail(tenant_id=_tid(), biz_type="DESTINATION_SUBMISSION", biz_id=str(sub_id),
                         action=action, operator=n, role_name=r, detail=detail,
                         occurred_at=datetime.utcnow()))


def _row(x: EmpDestinationSubmission) -> dict:
    return {
        "submissionId": str(x.id),
        "studentId": str(x.student_id),
        "empStudentId": str(x.emp_student_id) if x.emp_student_id else "",
        "destinationType": x.destination_type,
        "destinationLabel": L_DEST.get(x.destination_type, x.destination_type),
        "companyName": x.company_name or "",
        "jobTitle": x.job_title or "",
        "city": x.city or "",
        "contact": x.contact or "",
        "remark": x.remark or "",
        "status": x.status,
        "returnReason": x.return_reason or "",
        "version": int(x.version or 0),
        "decisionVersion": int(x.decision_version or 0),
        "currentTaskId": str(x.current_task_id or ""),
    }


def _load(db, submission_id, *, lock=False) -> EmpDestinationSubmission:
    q = db.query(EmpDestinationSubmission).filter(
        EmpDestinationSubmission.id == int(submission_id),
        EmpDestinationSubmission.tenant_id == _tid(),
        EmpDestinationSubmission.is_deleted.is_(False),
    )
    x = q.with_for_update().first() if lock else q.first()
    if not x:
        raise not_found("就业去向提交不存在")
    return x


def _msg(db, receiver_id, title, content, event_code, sub_id):
    from app.services.message_event_outbox_service import emit_receiver_notice
    emit_receiver_notice(
        db, event_code=event_code, source_module=SOURCE_MODULE, source_biz_type=SOURCE_BIZ_TYPE,
        source_biz_id=int(sub_id), receiver_id=receiver_id, title=title, content=content,
        receiver_as="student", dedup_extra=event_code,
    )


def _todo_upsert(db, sub_id, assignee_id, student_id, title):
    from app.models import UnifiedTodo
    row = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == SOURCE_MODULE,
        UnifiedTodo.source_biz_id == int(sub_id), UnifiedTodo.todo_type == TODO_TYPE,
        UnifiedTodo.assignee_id == int(assignee_id), UnifiedTodo.is_deleted.is_(False))).first()
    if row:
        row.title, row.status, row.version = title, "PENDING", int(row.version or 0) + 1
    else:
        db.add(UnifiedTodo(tenant_id=_tid(), source_module=SOURCE_MODULE,
                           source_biz_type=SOURCE_BIZ_TYPE, source_biz_id=int(sub_id),
                           todo_type=TODO_TYPE, assignee_id=int(assignee_id),
                           student_id=student_id, title=title, status="PENDING"))


def _todo_done(db, sub_id):
    from app.models import UnifiedTodo
    for r in db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == SOURCE_MODULE,
            UnifiedTodo.source_biz_id == int(sub_id), UnifiedTodo.todo_type == TODO_TYPE,
            UnifiedTodo.is_deleted.is_(False))).all():
        r.status, r.version = "DONE", int(r.version or 0) + 1


def _open_workflow(db, submission_id, applicant_id, title, assignee_id):
    from app.models import WorkflowInstance, WorkflowTask
    from app.services.runtime_preset_install_service import ensure_workflow_enabled
    ensure_workflow_enabled(db, _tid(), WF_CODE)
    inst = WorkflowInstance(tenant_id=_tid(), workflow_code=WF_CODE, source_module=SOURCE_MODULE,
                            source_biz_type=SOURCE_BIZ_TYPE, source_biz_id=int(submission_id),
                            applicant_id=int(applicant_id or 0), title=title, status="RUNNING",
                            current_node=REVIEW_NODE)
    db.add(inst)
    db.flush()
    task = WorkflowTask(tenant_id=_tid(), instance_id=inst.id, node_code=REVIEW_NODE,
                        assignee_id=int(assignee_id or 0), status="PENDING")
    db.add(task)
    db.flush()
    return inst, task


def submit(*, student_id: int, student_name: str,
           destination_type: str, company_name: str = "", job_title: str = "",
           city: str = "", contact: str = "", remark: str = "") -> dict:
    """学生发起就业去向登记提交。同一学生同一时刻只允许一条在途（SUBMITTED）提交；
    RETURNED/REJECTED/APPROVED 均已终结，可以再次提交一条新的。"""
    dt = (destination_type or "").upper()
    if dt not in L_DEST:
        raise AppException("VALIDATION_ERROR", "非法的就业去向类型")
    with session() as db:
        dup = db.scalars(select(EmpDestinationSubmission).where(
            EmpDestinationSubmission.tenant_id == _tid(),
            EmpDestinationSubmission.student_id == int(student_id),
            EmpDestinationSubmission.status.in_(list(_ACTIVE)),
            EmpDestinationSubmission.is_deleted.is_(False),
        )).first()
        if dup:
            raise AppException("DATA_CONFLICT", "已有一条就业去向登记正在审核中，请等待处理结果")

        x = EmpDestinationSubmission(
            tenant_id=_tid(), student_id=int(student_id), applicant_id=int(student_id),
            destination_type=dt, company_name=(company_name or "").strip() or None,
            job_title=(job_title or "").strip() or None, city=(city or "").strip() or None,
            contact=(contact or "").strip() or None, remark=(remark or "").strip() or None,
            status="SUBMITTED",
        )
        db.add(x)
        db.flush()

        from app.services.affairs_assignee_service import require_assignee_id
        # 注意：require_assignee_id() 的负载均衡查询按 source_module=="student-affairs"
        # 统计在办量，对 employment 模块的候选人永远读到 0——不是 bug，是该共享函数目前
        # 只服务学工域负载统计；效果是候选人间退化成按 user_id 稳定 tie-break，而不是
        # 真正的最小负载优先。候选池本身（EMPLOYMENT_TEACHER 角色）解析是正确、共享的，
        # 不在本次改共享函数扩大范围。
        assignee_id = require_assignee_id(db, REVIEW_NODE, student_id=int(student_id))

        inst, task = _open_workflow(db, x.id, student_id,
                                    f"{student_name} 就业去向登记待审", assignee_id)
        x.workflow_instance_id = inst.id
        x.current_task_id = task.id
        _todo_upsert(db, x.id, assignee_id, int(student_id), f"就业去向登记待审：{student_name}")
        _audit(db, x.id, "SUBMIT", dt)
        db.commit()
        db.refresh(x)
        return _row(x)


def get_submission(submission_id, user=None) -> dict:
    with session() as db:
        x = _load(db, submission_id)
        return _row(x)


def list_my_submissions(student_id: int, *, page=1, page_size=20) -> tuple[list[dict], int]:
    with session() as db:
        conds = [EmpDestinationSubmission.tenant_id == _tid(),
                 EmpDestinationSubmission.student_id == int(student_id),
                 EmpDestinationSubmission.is_deleted.is_(False)]
        from sqlalchemy import func
        total = db.scalar(select(func.count()).select_from(EmpDestinationSubmission).where(*conds)) or 0
        rows = db.scalars(select(EmpDestinationSubmission).where(*conds)
                          .order_by(EmpDestinationSubmission.id.desc())
                          .offset(max(0, (page - 1) * page_size)).limit(page_size)).all()
        return [_row(x) for x in rows], int(total)


def _apply_to_emp_student_in_tx(db, x: EmpDestinationSubmission) -> EmpStudent:
    """原子写回：批准的结构化事实进 canonical EmpStudent，不动 verify_status
    （核验门槛独立，见模块 docstring）。与调用方共用同一事务/同一个 commit。"""
    from app.modules.employment.services.employment_service import create_student

    existing = db.scalar(select(EmpStudent).where(
        EmpStudent.tenant_id == _tid(), EmpStudent.student_id == x.student_id,
        EmpStudent.is_deleted.is_(False)))
    if existing:
        existing.destination_type = x.destination_type
        if x.company_name:
            existing.company_name = x.company_name
        if x.job_title:
            existing.job_title = x.job_title
        existing.version = int(existing.version or 0) + 1
        emp = existing
    else:
        result = create_student({
            "studentId": str(x.student_id),
            "destinationType": x.destination_type,
            "companyName": x.company_name,
        }, db=db)
        from app.core.tenant_scoped import tenant_get
        emp = tenant_get(db, EmpStudent, int(result["id"]))
        if x.job_title:
            emp.job_title = x.job_title
    x.emp_student_id = emp.id
    return emp


def apply_workflow_decision_in_db(db, inst, *, approved: bool, reason: str | None = None) -> dict | None:
    """由通用审批 `db_service.act_task()` 在同一事务内回调（镜像 MESSAGE_CAMPAIGN 的既有写法，
    见该函数内 source_biz_type == "MESSAGE_CAMPAIGN" 分支）。act_task() 已经把 WorkflowTask/
    WorkflowInstance 状态、乐观锁、assignee 校验都做完，这里只做本域原子写回，不重复鉴权、
    不重复校验版本，也不 commit——commit 由 act_task() 统一做。"""
    x = db.scalars(select(EmpDestinationSubmission).where(
        EmpDestinationSubmission.tenant_id == _tid(),
        EmpDestinationSubmission.workflow_instance_id == int(inst.id),
        EmpDestinationSubmission.is_deleted.is_(False),
    ).with_for_update()).first()
    if not x:
        return None
    x.decision_version = int(x.decision_version or 0) + 1
    x.current_task_id = None
    if approved:
        x.status = "APPROVED"
        emp = _apply_to_emp_student_in_tx(db, x)
        _audit(db, x.id, "APPROVED", f"写回 EmpStudent#{emp.id}")
        _todo_done(db, x.id)
        _msg(db, x.student_id, "就业去向登记已通过",
             "你的就业去向登记已通过审核", "EMPLOYMENT_DESTINATION.APPROVED", x.id)
    else:
        x.status = "REJECTED"
        _audit(db, x.id, "REJECTED", reason or "")
        _todo_done(db, x.id)
        _msg(db, x.student_id, "就业去向登记未通过",
             reason or "你的就业去向登记未通过审核", "EMPLOYMENT_DESTINATION.REJECTED", x.id)
    db.flush()
    return _row(x)


def apply_return_in_db(db, inst, *, reason: str) -> dict | None:
    """由通用审批 `approval_runtime_service.return_for_revision()` 在同一事务内回调
    （该函数是真正被 `/tasks/{id}/return` 路由调用的实现，不是 `approval_service.py`
    里同名但无调用方的旧实现）。退回是终态（与 AaStatusChange 的既有约定一致）：学生
    需重新调用 submit() 发起新的一条提交，不在这条记录上原地编辑重开——同一份记录
    改字段又能重新流转，会让"审批过的历史事实"变得可变，这不是本模块要建的语义。

    不在这里重复发通知：调用方已经对 `inst.applicant_id` 插入一条通用 UnifiedMessage
    退回提醒，本域再发一条会变成同一件事收到两条推送。
    """
    x = db.scalars(select(EmpDestinationSubmission).where(
        EmpDestinationSubmission.tenant_id == _tid(),
        EmpDestinationSubmission.workflow_instance_id == int(inst.id),
        EmpDestinationSubmission.is_deleted.is_(False),
    ).with_for_update()).first()
    if not x:
        return None
    x.status = "RETURNED"
    x.return_reason = reason
    x.decision_version = int(x.decision_version or 0) + 1
    x.current_task_id = None
    _audit(db, x.id, "RETURNED", reason)
    _todo_done(db, x.id)
    db.flush()
    return _row(x)
