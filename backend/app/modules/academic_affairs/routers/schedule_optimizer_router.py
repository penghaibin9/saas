"""Unique route registration; the canonical schedule writers remain unchanged."""
from fastapi import APIRouter,Depends,Path,Query,BackgroundTasks
from pydantic import BaseModel,ConfigDict,Field,StrictInt
from app.core.permissions import require_permission,require_module
from app.core.response import success
from app.modules.academic_affairs.services import schedule_optimizer_readiness_service as readiness_service
from app.modules.academic_affairs.services import schedule_optimizer_jobs_service as service

router=APIRouter(prefix='/academic-affairs',tags=['Scheduling optimizer'],
    dependencies=[Depends(require_module('academicAffairs'))])
_BASE='/scheduling/batches/{batch_id}/optimizer'
VIEW='academicAffairs.schedule.view'
MANAGE='academicAffairs.schedule.rule.manage'

class EnqueueBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expectedSourceRevision:str=Field(pattern=r'^[a-f0-9]{64}$')
    idempotencyKey:str=Field(min_length=8,max_length=64)
    reason:str=Field(min_length=5,max_length=500)
    plan:dict
    options:dict=Field(default_factory=dict)

class CancelBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expectedVersion:StrictInt=Field(ge=0)

@router.get(_BASE+'/readiness')
def optimizer_readiness(batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),user=Depends(require_permission(VIEW))):
    service._authorize(user,batch_id)
    return success(readiness_service.readiness(user,batch_id))

@router.get(_BASE+'/context')
def optimizer_context(batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),user=Depends(require_permission(VIEW))):
    return success(service.context(user,batch_id))

@router.post(_BASE+'/jobs')
def optimizer_enqueue(body:EnqueueBody,background_tasks:BackgroundTasks,batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),user=Depends(require_permission(MANAGE))):
    result=service.enqueue(user,batch_id,body.model_dump())
    background_tasks.add_task(service.dispatch_worker, str(service._tid()))
    return success(result)

@router.get(_BASE+'/lookup')
def optimizer_lookup(batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),idempotencyKey:str=Query(min_length=8,max_length=64),user=Depends(require_permission(VIEW))):
    return success(service.lookup_job(user,batch_id,idempotencyKey))

@router.get(_BASE+'/jobs/{job_id}')
def optimizer_job(background_tasks:BackgroundTasks,batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),job_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),user=Depends(require_permission(VIEW))):
    result=service.get_job(user,batch_id,job_id)
    if result.get('state') in {'QUEUED','RUNNING'}:
        background_tasks.add_task(service.dispatch_worker, str(service._tid()))
    return success(result)

@router.get(_BASE+'/jobs/{job_id}/preview')
def optimizer_preview(batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),job_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),taskId:str|None=Query(default=None,pattern=r'^[1-9][0-9]{0,18}$'),week:str|None=Query(default=None,pattern=r'^W(?:0[1-9]|[12][0-9]|30)$'),user=Depends(require_permission(VIEW))):
    return success(service.preview_rows(user,batch_id,job_id,taskId,week))

@router.post(_BASE+'/jobs/{job_id}/cancel')
def optimizer_cancel(body:CancelBody,batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),job_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),user=Depends(require_permission(MANAGE))):
    return success(service.cancel_job(user,batch_id,job_id,body.expectedVersion))

@router.post(_BASE+'/jobs/{job_id}/apply')
def optimizer_apply(body:CancelBody,batch_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),job_id:str=Path(pattern=r'^[1-9][0-9]{0,18}$'),user=Depends(require_permission(MANAGE))):
    from app.modules.academic_affairs.services.schedule_optimizer_apply_service import apply_candidate
    return success(apply_candidate(user,batch_id,job_id,body.expectedVersion))
