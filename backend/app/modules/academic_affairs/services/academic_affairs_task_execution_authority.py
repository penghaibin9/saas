"""所有消费者共用的教学执行边界；承接关系不改写原任务、不自动转发写入。"""
from __future__ import annotations

from sqlalchemy import exists, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid


def independent_task_condition(task_model=None, *, tenant_id=None):
    """查询与汇总只计算独立执行任务；任何承接记录均不能开放后继写旁路。"""
    from app.models import AaTeachingTask, AaTeachingTaskSourceHandoff
    model = AaTeachingTask if task_model is None else task_model
    tenant = _tid() if tenant_id is None else int(tenant_id)
    return ~exists(select(AaTeachingTaskSourceHandoff.id).where(
        AaTeachingTaskSourceHandoff.tenant_id == tenant,
        AaTeachingTaskSourceHandoff.successor_task_id == model.id,
    ))


def require_independent_task(db, task, *, tenant_id=None, lock=True):
    """写入前当前读取共同任务锁；不能把后继编号悄悄替换为原任务编号。

    调用方先完成自己的对象权限裁决。承接确认取得任务锁后只非锁定读取
    子业务引用，避免与已有先锁业务对象、后锁任务的命令产生反向锁依赖。
    """
    from app.models import AaTeachingTask, AaTeachingTaskSourceHandoff
    tenant = _tid() if tenant_id is None else int(tenant_id)
    task_id = int(getattr(task, "id", task))
    query = select(AaTeachingTask).where(AaTeachingTask.tenant_id == tenant,
        AaTeachingTask.id == task_id, AaTeachingTask.is_deleted.is_(False))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    current = db.scalar(query)
    if current is None:
        raise not_found("教学任务不存在")
    relation = select(AaTeachingTaskSourceHandoff.id).where(
        AaTeachingTaskSourceHandoff.tenant_id == tenant,
        AaTeachingTaskSourceHandoff.successor_task_id == task_id)
    if lock:
        relation = relation.with_for_update()
    if db.scalar(relation.limit(1)) is not None:
        raise AppException("DATA_CONFLICT", "本任务已由原教学任务承接，请回读原任务后办理，不能重复执行。",
            http_status=409, details={"blocker": "TASK_EXECUTION_HANDOFF", "taskId": str(task_id)})
    return current


def load_execution_handoffs(db, task_ids, *, tenant_id=None, lock=False):
    """限于调用方已授权的任务集合，按批读取承接关系和原对象完整性。

    锁模式由调用方先升序锁候选任务，本方法只当前读不可编辑关系，不再
    从关系反向取得原任务锁。关联校验使用任务不可编辑的课程、行政班、
    来源和批次身份，避免部分候选缺原任务时引入关系→原任务锁倒序。
    """
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTeachingTaskSourceHandoff
    tenant = _tid() if tenant_id is None else int(tenant_id)
    ids = sorted({int(pk) for pk in task_ids})
    result = {}
    for start in range(0, len(ids), 500):
        relation_query = select(AaTeachingTaskSourceHandoff).where(
            AaTeachingTaskSourceHandoff.tenant_id == tenant,
            AaTeachingTaskSourceHandoff.successor_task_id.in_(ids[start:start + 500]))
        if lock:
            relation_query = relation_query.with_for_update(read=True).execution_options(populate_existing=True)
        relations = db.scalars(relation_query).all()
        if not relations:
            continue
        related_ids = {int(pk) for row in relations for pk in (row.execution_task_id, row.successor_task_id)}
        task_query = select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == tenant, AaTeachingTask.id.in_(related_ids),
            AaTeachingTask.is_deleted.is_(False)).order_by(AaTeachingTask.id)
        tasks = {int(row.id): row for row in db.scalars(task_query).all()}
        batches = {int(row.id): row for row in db.scalars(select(AaTeachingTaskBatch).where(
            AaTeachingTaskBatch.tenant_id == tenant,
            AaTeachingTaskBatch.id.in_({row.batch_id for row in tasks.values()}),
            AaTeachingTaskBatch.is_deleted.is_(False))).all()}
        anchor_query = select(AaTeachingTaskSourceHandoff.successor_task_id).where(
            AaTeachingTaskSourceHandoff.tenant_id == tenant,
            AaTeachingTaskSourceHandoff.successor_task_id.in_({row.execution_task_id for row in relations}))
        if lock:
            anchor_query = anchor_query.with_for_update(read=True)
        anchors = set(db.scalars(anchor_query).all())
        for row in relations:
            original, successor = tasks.get(int(row.execution_task_id)), tasks.get(int(row.successor_task_id))
            first = batches.get(int(original.batch_id)) if original else None
            second = batches.get(int(successor.batch_id)) if successor else None
            valid = bool(original and successor and first and second
                and original.id != successor.id and original.id not in anchors
                and first.term_id == second.term_id == row.term_id
                and first.college_id == second.college_id
                and original.course_id == successor.course_id
                and original.class_id is not None and original.class_id == successor.class_id
                and original.source_program_course_id == row.execution_source_id
                and successor.source_program_course_id == row.successor_source_id)
            if not valid:
                raise AppException("DATA_CONFLICT", "教学任务承接记录与当前对象不一致，请校教务核查。",
                    http_status=409, details={"blocker": "TASK_HANDOFF_REFERENCE_INVALID"})
            result[int(row.successor_task_id)] = row
    return result
