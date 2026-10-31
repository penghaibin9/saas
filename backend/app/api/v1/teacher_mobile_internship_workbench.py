"""教师移动端岗位实习消息与分类待办；复用统一消息与待办事实。"""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from app.core.exceptions import AppException, not_found
from app.core.permissions import has_permission, require_module, require_permission
from app.core.response import success
from app.core.security import require_mobile_staff
from app.core.timeutil import utc_now_naive
from app.models import (UnifiedMessage, UnifiedTodo, InternshipApplication, InternshipRecord,
                        InternshipChangeRequest, InternshipCheckinExemption)
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services.db_service import _iso, _tid, session

router = APIRouter(prefix="/internship/workbench", tags=["teacher-mobile-internship-workbench"],
                   dependencies=[Depends(require_mobile_staff), Depends(require_module("internship"))])

TODO_META = {
    "INTERN_WEEKLY_REVIEW": ("REPORT", "周报批阅", "/pages/teacher-internship/internship-review/index"),
    "INTERN_DAILY_REVIEW": ("REPORT", "日报批阅", "/pages/teacher-internship/process-report-review/index"),
    "INTERN_MONTHLY_REVIEW": ("REPORT", "月报批阅", "/pages/teacher-internship/process-report-review/index"),
    "INTERN_SUMMARY_REVIEW": ("REPORT", "总结批阅", "/pages/teacher-internship/process-report-review/index"),
    "INTERN_LEAVE_APPROVAL": ("LEAVE", "请假审批", "/pages/teacher-internship/internship-approval/index?tab=leave"),
    "INTERN_LEAVE_RETURN": ("LEAVE", "返岗确认", "/pages/teacher-internship/internship-approval/index?tab=overdue"),
    "INTERN_MAKEUP_APPROVAL": ("ATTENDANCE", "补签审批", "/pages/teacher-internship/internship-approval/index?tab=makeup"),
    "INTERN_EXCEPTION_HANDLE": ("ATTENDANCE", "打卡异常", "/pages/teacher-internship/internship-review/index"),
    "INTERN_EXEMPTION_APPROVAL": ("ATTENDANCE", "免签审批", "/pages/teacher-internship/checkin-exemption/index"),
    "INTERN_APPLICATION_REVIEW": ("APPLICATION", "实习岗位申请", "/pages/teacher-internship/internship-application/index"),
    "INTERN_EXEMPTION_APPLICATION": ("APPLICATION", "免实习申请", "/pages/teacher-internship/internship-application/index"),
    "INTERN_CHANGE_APPROVAL": ("CHANGE", "岗位变更", "/pages/teacher-internship/internship-change/index"),
    "INTERN_ENTERPRISE_CHANGE": ("CHANGE", "企业变更", "/pages/teacher-internship/internship-change/index"),
    "INTERN_VISIT_RECTIFY": ("VISIT", "巡访整改", "/pages/teacher-internship/internship-review/index"),
    "INTERN_EMPLOYMENT_REPORT": ("OTHER", "就业上报", "/pages/teacher-internship/employment/index"),
}
GROUP_LABELS = {"ALL":"全部","REPORT":"报告批阅","ATTENDANCE":"考勤","APPLICATION":"岗位申请",
                "LEAVE":"请假","CHANGE":"变更","VISIT":"巡访","OTHER":"其他"}
_VOLUNTEER_MESSAGE_ACTIONS = frozenset({
    "INTERNSHIP_TEACHER_CONFIRM_ACCEPT_INTENT", "INTERNSHIP_STUDENT_UNLOCK_REQUEST",
    "INTERNSHIP_ACCEPT_INTENT_EXPIRED",
})


def _message_has_target(row) -> bool:
    return (str(row.action_key or "") in _VOLUNTEER_MESSAGE_ACTIONS
            and str(row.status or "").upper() in {"UNREAD", "READ"}
            and str(row.delivery_status or "").upper() not in {"WITHDRAWN", "CANCELLED", "REVOKED"}
            and (row.expire_at is None or row.expire_at > utc_now_naive()))

def _uid(user: dict) -> int:
    raw = str((user or {}).get("userId") or "").strip()
    if raw.lower().startswith("db-"): raw = raw[3:]
    if not raw.isdigit() or int(raw) <= 0:
        raise AppException("NO_PERMISSION", "当前教师账号无法解析为本地用户", http_status=403)
    return int(raw)

def _ctx(user: dict) -> str:
    return str((user or {}).get("activeContextId") or "").strip() or "GLOBAL"

def _msg_vis(uid: int, ctx: str):
    return or_(
        and_(UnifiedMessage.receiver_user_id == uid,
             or_(UnifiedMessage.receiver_context_key == "GLOBAL",
                 UnifiedMessage.receiver_context_key == ctx)),
        and_(UnifiedMessage.receiver_user_id.is_(None), UnifiedMessage.receiver_id == uid))

def _msg_source():
    return UnifiedMessage.source_module == "internship"

def _msg_category(row) -> str:
    if row.category:
        return str(row.category).upper()
    value = str(row.message_type or "").upper()
    if value == "EMERGENCY": return "EMERGENCY"
    if value in {"ANNOUNCEMENT","NOTICE"}: return "ANNOUNCEMENT"
    if value in {"TODO_NOTICE","TODO","REMINDER"}: return "TODO"
    if value in {"BUSINESS","BIZ"}: return "BUSINESS"
    return "SYSTEM"


def _msg(row, *, can_view_target=False):
    content=str(row.rendered_content_plain or row.content or "")
    return {"messageId":str(row.id),"category":_msg_category(row),
            "priority":str(row.priority or "NORMAL").upper(),"title":str(row.rendered_title or row.title or "站内消息"),
            "content":content,"summary":content[:120],"readStatus":str(row.status or "UNREAD").upper(),
            "readAt":_iso(row.read_at) if row.read_at else None,
            "createdAt":_iso(row.created_at) if row.created_at else None,
            "sourceModule":row.source_module or "internship",
            "sourceBizId":str(row.source_biz_id) if row.source_biz_id else None,
            "requireAck":bool(row.require_ack),"acked":bool(row.ack_at),
            "hasBusinessTarget":can_view_target and _message_has_target(row)}

def _todo_meta(value: str):
    code=str(value or "").upper()
    return TODO_META.get(code,("OTHER","岗位实习待办",""))

_FOCUSED_TODOS = {
    'INTERN_EXEMPTION_APPROVAL': (InternshipCheckinExemption, InternshipCheckinExemption.internship_id, 'exemptionId'),
    'INTERN_APPLICATION_REVIEW': (InternshipApplication, InternshipApplication.record_id, 'applicationId'),
    'INTERN_EXEMPTION_APPLICATION': (InternshipApplication, InternshipApplication.record_id, 'applicationId'),
    'INTERN_CHANGE_APPROVAL': (InternshipChangeRequest, InternshipChangeRequest.internship_id, 'changeId'),
    'INTERN_ENTERPRISE_CHANGE': (InternshipChangeRequest, InternshipChangeRequest.internship_id, 'changeId'),
}


def _todo_batches(db, rows, user):
    batches = {}
    for model, record_key in {(meta[0], meta[1]) for meta in _FOCUSED_TODOS.values()}:
        ids = {row.source_biz_id for row in rows if row.todo_type in _FOCUSED_TODOS and _FOCUSED_TODOS[row.todo_type][0] is model}
        if not ids:
            continue
        query = select(model.id, InternshipRecord.batch_id).join(InternshipRecord, InternshipRecord.id == record_key).where(
            model.id.in_(ids), model.tenant_id == _tid(), model.is_deleted.is_(False), model.student_id == InternshipRecord.student_id,
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False))
        for source_id, batch_id in db.execute(apply_internship_record_scope(query, user)):
            batches[(model, source_id)] = batch_id
    return batches


def _todo(row, batch_id=None):
    group,label,path=_todo_meta(row.todo_type)
    if row.todo_type in _FOCUSED_TODOS:
        key = _FOCUSED_TODOS[row.todo_type][2]
        path = f'{path}?batchId={batch_id}&{key}={row.source_biz_id}' if batch_id else ''
    elif row.todo_type == 'INTERN_EMPLOYMENT_REPORT' and path:
        path += '?registrationId='+str(row.source_biz_id)
    elif row.todo_type == 'INTERN_WEEKLY_REVIEW' and path:
        path += '?tab=weekly&recordId='+str(row.source_biz_id)
    elif row.todo_type == 'INTERN_EXCEPTION_HANDLE' and path:
        path += '?tab=abnormal&exceptionId='+str(row.source_biz_id)
    elif row.todo_type in ('INTERN_DAILY_REVIEW', 'INTERN_MONTHLY_REVIEW', 'INTERN_SUMMARY_REVIEW') and path:
        path += '?reportId='+str(row.source_biz_id)
    elif row.todo_type in ('INTERN_LEAVE_APPROVAL', 'INTERN_LEAVE_RETURN') and path:
        path += '&leaveId='+str(row.source_biz_id)
    elif row.todo_type == 'INTERN_VISIT_RECTIFY' and path:
        path += '?tab=visit&visitId='+str(row.source_biz_id)
    return {"todoId":str(row.id),"todoType":str(row.todo_type or ""),"group":group,
            "groupLabel":GROUP_LABELS.get(group,"其他"),"typeLabel":label,"title":row.title,
            "status":str(row.status or "PENDING").upper(),"dueAt":_iso(row.due_at) if row.due_at else None,
            "createdAt":_iso(row.created_at) if row.created_at else None,
            "studentId":str(row.student_id) if row.student_id else None,
            "sourceBizType":row.source_biz_type,"sourceBizId":str(row.source_biz_id),"actionPath":path}

@router.get("/messages", summary="教师本人岗位实习站内信")
def messages(category:str=Query("ALL",max_length=30), readStatus:str|None=Query(None,max_length=20),
             page:int=Query(1,ge=1), pageSize:int=Query(20,ge=1,le=100),
             user=Depends(require_permission("internship.dashboard.view"))):
    uid=_uid(user); category=str(category or "ALL").strip().upper(); read_status=str(readStatus or "").strip().upper()
    with session() as db:
        conds=[UnifiedMessage.tenant_id==_tid(),UnifiedMessage.is_deleted.is_(False),_msg_vis(uid,_ctx(user)),_msg_source()]
        if read_status:
            if read_status not in {"UNREAD","READ"}:
                raise AppException("VALIDATION_ERROR","请选择未读或已读消息",http_status=422)
            conds.append(UnifiedMessage.status==read_status)
        if category not in {"","ALL"}:
            aliases={
                "EMERGENCY":("EMERGENCY",),
                "ANNOUNCEMENT":("ANNOUNCEMENT","NOTICE"),
                "TODO":("TODO_NOTICE","TODO","REMINDER"),
                "BUSINESS":("BUSINESS","BIZ"),
                "SYSTEM":("SYSTEM",),
            }
            types=aliases.get(category,(category,))
            if category=="EMERGENCY":
                conds.append(or_(UnifiedMessage.category=="EMERGENCY",UnifiedMessage.priority=="EMERGENCY",
                                 UnifiedMessage.message_type.in_(types)))
            elif category=="SYSTEM":
                conds.append(or_(UnifiedMessage.category=="SYSTEM",UnifiedMessage.message_type.in_(types),
                                 and_(UnifiedMessage.category.is_(None),UnifiedMessage.message_type.is_(None))))
            else:
                conds.append(or_(UnifiedMessage.category==category,UnifiedMessage.message_type.in_(types)))
        total=int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(*conds)) or 0)
        rows=db.scalars(select(UnifiedMessage).where(*conds).order_by(
            UnifiedMessage.created_at.desc(),UnifiedMessage.id.desc()).offset((page-1)*pageSize).limit(pageSize)).all()
        unread=int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id==_tid(),UnifiedMessage.is_deleted.is_(False),
            _msg_vis(uid,_ctx(user)),_msg_source(),UnifiedMessage.status=="UNREAD")) or 0)
        can_view_target = has_permission(user, "internship.application.view")
        return success({"items":[_msg(r, can_view_target=can_view_target) for r in rows],"total":total,"page":page,"pageSize":pageSize,
                        "hasMore":page*pageSize<total,"unread":unread})

@router.get("/messages/{message_id}/target", summary="教师本人志愿消息原单",
            dependencies=[Depends(require_permission("internship.dashboard.view"))])
def message_target(message_id:int,user=Depends(require_permission("internship.application.view"))):
    from app.modules.internship.services.internship_school_volunteer_service import get_group
    uid = _uid(user)
    with session() as db:
        row = db.scalar(select(UnifiedMessage).where(
            UnifiedMessage.id == message_id, UnifiedMessage.tenant_id == _tid(), UnifiedMessage.is_deleted.is_(False),
            _msg_vis(uid, _ctx(user)), _msg_source()))
        if not row:
            raise not_found("站内消息不存在")
        if not _message_has_target(row):
            raise not_found("此消息没有可打开的原单，请从分类待办查看")
        params = row.action_params_json if isinstance(row.action_params_json, dict) else {}
        ids = [str(params.get(key) or "") for key in ("campaignId", "volunteerGroupId")]
        if any(not value.isascii() or not value.isdecimal() or not 0 < int(value) <= 9223372036854775807 for value in ids):
            raise not_found("消息关联信息不完整，请从分类待办查看")
    group = get_group(campaign_id=int(ids[0]), group_id=int(ids[1]), user=user)
    if str(group.get("campaignId")) != ids[0] or str(group.get("id")) != ids[1] or not group.get("batchId"):
        raise not_found("原单关联信息不一致，请从分类待办查看")
    return success({"messageId":str(message_id), "pageKey":"TEACHER_INTERNSHIP_VOLUNTEERS",
                    "batchId":str(group["batchId"]), "campaignId":str(group["campaignId"]), "groupId":str(group["id"])})


@router.post("/messages/{message_id}/read", summary="教师本人岗位实习站内信已读")
def read_message(message_id:int,user=Depends(require_permission("internship.dashboard.view"))):
    uid=_uid(user)
    with session() as db:
        row=db.scalar(select(UnifiedMessage).where(
            UnifiedMessage.id==message_id,UnifiedMessage.tenant_id==_tid(),UnifiedMessage.is_deleted.is_(False),
            _msg_vis(uid,_ctx(user)),_msg_source()))
        if not row: raise not_found("站内消息不存在")
        if str(row.status or "").upper()!="READ":
            row.status="READ";row.read_at=datetime.utcnow();row.version=int(row.version or 0)+1;db.commit()
        return success(_msg(row, can_view_target=has_permission(user, "internship.application.view")),message="已标记为已读")

@router.get("/todos", summary="教师本人岗位实习分类待办")
def todos(status:str=Query("PENDING",max_length=20),group:str=Query("ALL",max_length=30),
          page:int=Query(1,ge=1),pageSize:int=Query(50,ge=1,le=100),
          user=Depends(require_permission("internship.dashboard.view"))):
    uid=_uid(user);status=str(status or "PENDING").strip().upper();group=str(group or "ALL").strip().upper()
    if status not in {"PENDING","DONE","CANCELLED","ALL"}:
        raise AppException("VALIDATION_ERROR","待办状态无效",http_status=422)
    if group not in GROUP_LABELS:
        raise AppException("VALIDATION_ERROR","待办分类无效",http_status=422)
    base=[UnifiedTodo.tenant_id==_tid(),UnifiedTodo.is_deleted.is_(False),
          UnifiedTodo.source_module=="internship",UnifiedTodo.assignee_id==uid]
    status_conds=[] if status=="ALL" else [UnifiedTodo.status==status]
    with session() as db:
        # 分类计数必须由数据库聚合，不能把教师全部待办实体加载进 Python。
        # 5000+ 学生场景下，一个指导教师可能积累大量历史待办；这里只取 todo_type + count，
        # 页面实体仍严格按 page/pageSize 分页，避免移动工作台随历史数据量线性涨内存。
        type_counts=db.execute(
            select(UnifiedTodo.todo_type,func.count())
            .where(*base,*status_conds)
            .group_by(UnifiedTodo.todo_type)
        ).all()
        counts={key:0 for key in GROUP_LABELS}
        for todo_type,count in type_counts:
            g=_todo_meta(todo_type)[0]
            n=int(count or 0)
            counts["ALL"]+=n
            counts[g]=counts.get(g,0)+n
        conds=[*base,*status_conds]
        if group!="ALL":
            known=[code for code,meta in TODO_META.items() if meta[0]==group]
            if group=="OTHER":
                conds.append(or_(UnifiedTodo.todo_type.in_(known),~UnifiedTodo.todo_type.in_(list(TODO_META))))
            elif known: conds.append(UnifiedTodo.todo_type.in_(known))
            else: return success({"items":[],"total":0,"page":page,"pageSize":pageSize,"hasMore":False,
                                  "groupCounts":counts,"groupLabels":GROUP_LABELS})
        total=int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(*conds)) or 0)
        rows=db.scalars(select(UnifiedTodo).where(*conds).order_by(
            UnifiedTodo.due_at.is_(None).asc(), UnifiedTodo.due_at.asc(),UnifiedTodo.created_at.desc(),UnifiedTodo.id.desc())
            .offset((page-1)*pageSize).limit(pageSize)).all()
        batches = _todo_batches(db, rows, user)
        return success({"items":[_todo(r, batches.get((_FOCUSED_TODOS[r.todo_type][0], r.source_biz_id)) if r.todo_type in _FOCUSED_TODOS else None) for r in rows],"total":total,"page":page,"pageSize":pageSize,
                        "hasMore":page*pageSize<total,"groupCounts":counts,"groupLabels":GROUP_LABELS})
