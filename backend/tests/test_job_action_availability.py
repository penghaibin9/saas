from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from app.services import job_registry as jobs


def task(**kwargs):
    return SimpleNamespace(**(dict(id=1,tenant_id=7,created_by=None,operator_id=42,status='CREATED',
        version=0,created_at=datetime(2026,10,25,10,54),updated_at=None,expires_at=None,template_version='v1')|kwargs))


@pytest.mark.parametrize('status,expired,expected',[
    ('CREATED',False,True),('SUCCEEDED',False,False),('CANCELLED',False,False),('CREATED',True,False)])
def test_export_actions_match_state_and_expiry(status,expired,expected):
    meta={'statusField':'status','retryableFrom':[],'cancellableFrom':['CREATED']}
    row=task(status=status,expires_at=datetime.utcnow()-timedelta(seconds=1) if expired else None)
    actions=jobs.available_actions(meta,row,can_manage=True)
    assert actions['retry']['allowed'] is False
    assert actions['cancel']['allowed'] is expected


def test_missing_authority_and_stale_revision_do_not_offer_retry():
    meta={'statusField':'status','retryableFrom':['FAILED'],'cancellableFrom':['UPLOADED'],
          'revisionField':'template_version','currentRevision':'v1'}
    assert jobs.available_actions(meta,task(status='FAILED'),can_manage=True)['retry']['allowed']
    assert not jobs.available_actions(meta,task(status='FAILED'),can_manage=False)['retry']['allowed']
    assert not jobs.available_actions(meta,task(status='FAILED',template_version='v0'),can_manage=True)['retry']['allowed']


def test_operator_is_not_mislabeled_as_system_task_and_time_has_zone():
    value=jobs._row_to_dto('EXPORT',{'statusField':'status','ownerModule':'dataExchange'},task())
    assert value['initiator']=='42'
    assert value['createdAt']=='2026-10-25T10:54:00Z'
    assert value['timeZone']=='Asia/Shanghai'
    sourced=jobs._row_to_dto('EXPORT',{'statusField':'status','ownerModule':'dataExchange'},task(module_code='systemAdmin'))
    assert sourced['ownerModule']=='systemAdmin'
