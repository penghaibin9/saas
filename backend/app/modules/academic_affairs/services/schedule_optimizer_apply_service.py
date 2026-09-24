"""Adopt a verified candidate through the existing draft writer, in one transaction."""
from sqlalchemy import select, update

from app.core.exceptions import AppException
from app.core.permissions import enforce_permission, require_module
from app.services.db_service import session, _tid
from app.modules.academic_affairs.optimizer.contracts import InputError, numeric_id
from app.modules.academic_affairs.optimizer.persistence import jobs, snapshots, unpack_snapshot, Repository
from app.modules.academic_affairs.optimizer.source_builder import compile_source
from app.modules.academic_affairs.optimizer.validation import validate_solution
from . import academic_affairs_schedule_final_service as schedule
from . import academic_affairs_schedule_resource_guard as resources
from . import academic_affairs_schedule_truth_service as truth
from .academic_affairs_schedule_write_scope_r3 import assert_schedule_write_scope
from .schedule_optimizer_source_service import capture_source


def _conflict(message="学校数据已变化，请重新智能试排。"):
    raise AppException("DATA_CONFLICT", message, http_status=409)


def apply_candidate(user, batch_id, job_id, expected_version):
    from .schedule_optimizer_jobs_service import _authorize, _repository, _enabled
    enforce_permission(user, "academicAffairs.schedule.rule.manage")
    enforce_permission(user, "academicAffairs.schedule.edit")
    require_module("academicAffairs")(user)
    from app.services.module_access_service import assert_module_access
    assert_module_access(_tid(), "academicAffairs", write=True)
    if not _enabled():
        _conflict("智能试排采用暂未开放，请联系教务管理员。")
    numeric_id(str(job_id), "jobId")
    if type(expected_version) is not int or expected_version < 0:
        _conflict("请刷新候选方案后重试。")
    # No reads in the write transaction before the shared formal authority lock.
    _authorize(user, batch_id)
    with session() as db:
        Repository._guard(db)
        resources.lock_formal_authority(db)
        batch = schedule._load_batch(db, int(batch_id), writable=False, lock=True)
        assert_schedule_write_scope(db, user, batch)
        schedule.policy.resolve_scope(db, batch_id=batch.id, writable=True)
        resources.lock_term(db, batch.term_id)
        job = db.execute(select(jobs).where(
            jobs.c.tenant_id == _tid(), jobs.c.batch_id == batch.id,
            jobs.c.id == int(job_id),
        ).with_for_update()).mappings().first()
        if job is None:
            raise AppException("DATA_NOT_FOUND", "候选方案不存在", http_status=404)
        result = job["result_json"] or {}
        # A lost acknowledgement/repeated click returns the original committed receipt.
        if job["state"] == "APPLIED":
            return {**result["application"], "idempotent": True}
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            _conflict("已发布课表不可采用候选，请使用原调停课或纠错流程。")
        if job["version"] != expected_version or job["state"] != "SUCCEEDED":
            _conflict("候选方案状态已变化，请刷新核对。")
        stored = db.execute(select(snapshots).where(
            snapshots.c.tenant_id == _tid(), snapshots.c.id == job["snapshot_id"],
        )).mappings().one()
        snapshot = unpack_snapshot(stored)
        try:
            facts, revision = capture_source(db, user, str(batch.id), lock=True)
            if revision != snapshot.revision:
                _conflict()
            current, binding = compile_source(facts, snapshot.raw["provenance"]["plan"], expected_revision=revision)
            if current.input_hash != snapshot.input_hash or result.get("inputHash") != snapshot.input_hash:
                _conflict()
            choices = result.get("choices", {})
            if validate_solution(current, choices):
                _conflict("候选方案未通过硬冲突检查，请重新智能试排。")
        except InputError as exc:
            raise AppException("DATA_CONFLICT", "学校数据已变化，请重新智能试排。",
                               details={"reasonCode": exc.code}, http_status=409) from exc
        replaced = []
        if snapshot.raw['provenance']['plan'].get('replaceAuto') is True:
            from app.models import AaScheduleItem
            for item in db.scalars(select(AaScheduleItem).where(
                AaScheduleItem.tenant_id==_tid(), AaScheduleItem.batch_id==batch.id,
                AaScheduleItem.source=='AUTO', AaScheduleItem.status=='EFFECTIVE',
                AaScheduleItem.is_deleted.is_(False),
            ).order_by(AaScheduleItem.id).with_for_update()).all():
                item.is_deleted=True
                replaced.append(str(item.id))
            db.flush()
        created = []
        for activity_id, option_id in sorted(choices.items()):
            placement = binding["bindings"][activity_id + "|" + option_id]
            task = schedule._resolve_task(db, batch, {"taskId": placement["taskId"]})
            parity = snapshot.raw['provenance']['plan'].get('taskParities',{}).get(placement['taskId'],'ALL')
            for slot in placement["slotNos"]:
                source = {"taskId": placement["taskId"], "weekday": placement["weekday"],
                          "slotNo": slot, "startWeek": task.start_week, "endWeek": task.end_week,
                          "weekParity": parity, "classroom": placement["classroomText"]}
                item = schedule._build_item(db, batch, task, source, item_source="AUTO")
                if str(item.classroom_id) != placement["roomId"]:
                    _conflict("候选教室与正式教室不一致，请重新智能试排。")
                db.add(item)
                db.flush()
                created.append(item)
        # Full existing gate, including roster validity and all published resource consumers.
        schedule.gate_service.require_publishable(db, batch)
        truth.require_no_school_wide_conflict(db, batch, replacing_batch_id=batch.supersedes_batch_id)
        term, _ = schedule.policy.term_bounds(db, batch.term_id)
        resources.require_no_booking_conflict(db, term, created)
        batch.status = "DRAFT"
        receipt = {"batchId": str(batch.id), "jobId": str(job_id), "status": "DRAFT",
                   "writtenItems": len(created), "itemIds": [str(i.id) for i in created],
                   "replacedAutoItemIds": replaced,
                   "nextAction": "CHECK_CONFLICTS", "idempotent": False}
        db.execute(update(jobs).where(jobs.c.tenant_id == _tid(), jobs.c.id == job["id"],
                                     jobs.c.version == expected_version).values(
            state="APPLIED", version=expected_version + 1,
            result_json={**result, "application": receipt}, updated_at=Repository._now(db)))
        _repository(user)._audit(db, "CANDIDATE_APPLY", job_id, {
            "batchId": str(batch.id), "inputHash": snapshot.input_hash,
            "writtenItems": len(created), "sourceRevision": revision,
            "replacedAutoItemCount": len(replaced),
        })
        db.commit()
        return receipt
